"""Reconciliation of training events with the points journal.

Each event type reads existing training evidence; nothing is added to the
training flows. A periodic task (or an administrator) compares, rule by rule,
the qualifying records with the active grants: a new qualifying record earns
points, a grant whose record no longer qualifies is withdrawn. Running it twice
changes nothing.

Participants without a portal account earn nothing, and an account created later
recovers nothing: only events dated after the account and the rule start count.
Extension modules add event types by overriding ``_event_types``.
"""

from odoo import api, fields, models
from odoo.exceptions import AccessError


class GamificationService(models.AbstractModel):
    _name = "training.gamification.service"
    _description = "Training Points Service"

    @api.model
    def _event_types(self):
        """Event key -> (label, method returning the candidates of some enrollments)."""
        return {
            "attendance": (self.env._("Validated attendance (half-day)"), self._events_attendance),
            "activity_completed": (self.env._("Learning activity completed"), self._events_activity_completed),
            "activity_submitted": (self.env._("Work submitted for validation"), self._events_activity_submitted),
            "activity_validated": (self.env._("Work validated by the trainer"), self._events_activity_validated),
            "practice_done": (self.env._("Practice action carried out"), self._events_practice_done),
            "feedback_received": (self.env._("Named evaluation answered"), self._events_feedback_received),
            "tutoring_attended": (self.env._("Tutoring session held"), self._events_tutoring_attended),
            "enrollment_closed": (self.env._("Training completed"), self._events_enrollment_closed),
        }

    @api.model
    def _event_selection(self):
        return [(key, label) for key, (label, _method) in self._event_types().items()]

    # Each method returns (enrollment, source_key, qualifies, date) for every
    # candidate of the given enrollments, qualifying or not: a missing key means
    # the record no longer exists and its points are withdrawn.

    @api.model
    def _events_attendance(self, enrollments):
        rows = self.env["training.attendance"].sudo().search([("enrollment_id", "in", enrollments.ids)])
        for row in rows:
            decision = row.event_ids.filtered(lambda e: e.kind in ("validation", "correction", "invalidation"))
            yield (
                row.enrollment_id,
                f"{row._name},{row.id}",
                row.state == "validated" and not row.absent,
                (decision[-1:] or row.event_ids[-1:]).occurred_at,
            )

    @api.model
    def _progress(self, enrollments, criterion=None):
        domain = [("enrollment_id", "in", enrollments.ids)]
        if criterion:
            domain.append(("activity_id.criterion", "=", criterion))
        return self.env["training.learning.progress"].sudo().search(domain)

    @api.model
    def _events_activity_completed(self, enrollments):
        for row in self._progress(enrollments):
            yield row.enrollment_id, f"{row._name},{row.id}", row.completed, row.declared_at or row.write_date

    @api.model
    def _events_activity_submitted(self, enrollments):
        # A deposit stays a deposit when the trainer asks for changes.
        for row in self._progress(enrollments, "validation"):
            yield row.enrollment_id, f"{row._name},{row.id}", row.state != "pending", row.write_date

    @api.model
    def _events_activity_validated(self, enrollments):
        for row in self._progress(enrollments, "validation"):
            yield row.enrollment_id, f"{row._name},{row.id}", row.state == "validated", row.write_date

    @api.model
    def _events_practice_done(self, enrollments):
        rows = self.env["training.practice.action"].sudo().search([("enrollment_id", "in", enrollments.ids)])
        for row in rows:
            done = row.state in ("done", "closed") and not row.access_withdrawn
            yield row.enrollment_id, f"{row._name},{row.id}", done, row.write_date

    @api.model
    def _events_feedback_received(self, enrollments):
        # Anonymous campaigns have no individual tracking: they never earn points.
        rows = (
            self.env["training.feedback.recipient"]
            .sudo()
            .with_context(active_test=False)
            .search(
                [
                    ("enrollment_id", "in", enrollments.ids),
                    ("role", "=", "participant"),
                    ("campaign_id.anonymous", "=", False),
                ]
            )
        )
        for row in rows:
            yield row.enrollment_id, f"{row._name},{row.id}", row.response_state == "received", row.write_date

    @api.model
    def _events_tutoring_attended(self, enrollments):
        now = fields.Datetime.now()
        rows = self.env["training.tutoring.booking"].sudo().search([("enrollment_id", "in", enrollments.ids)])
        for row in rows:
            held = row.state == "confirmed" and row.slot_id.state != "cancelled" and row.slot_id.end_at <= now
            yield row.enrollment_id, f"{row._name},{row.id}", held, row.slot_id.end_at

    @api.model
    def _events_enrollment_closed(self, enrollments):
        # Dated by the recorded transition, not by a later technical update.
        closed = enrollments.filtered(lambda e: e.state == "closed")
        dates = {}
        for operation in (
            self.env["training.operation"]
            .sudo()
            .search(
                [("model_name", "=", "training.enrollment"), ("record_id", "in", closed.ids)],
                order="occurred_at, id",
            )
        ):
            dates[operation.record_id] = operation.occurred_at
        for row in enrollments:
            yield row, f"{row._name},{row.id}", row.state == "closed", dates.get(row.id, row.write_date)

    @api.model
    def _participant_user(self, enrollment):
        """The participant's own account, never a coordinator's; none means no points."""
        user = enrollment.sudo().user_id
        if not user:
            users = enrollment.participant_id.user_ids.filtered("active")
            user = users if len(users) == 1 else self.env["res.users"]
        if not user.active or user.partner_id != enrollment.participant_id:
            return self.env["res.users"]
        return user

    @api.model
    def _reconcile(self, rules=None):
        if not self.env.su and not self.env.user._is_system():
            raise AccessError(self.env._("Only an administrator can apply points rules."))
        Rule = self.env["training.gamification.rule"].sudo()
        rules = Rule.browse(rules.ids) if rules is not None else Rule.search([("active", "=", True)])
        for rule in rules.filtered("active"):
            self._reconcile_rule(rule)

    @api.model
    def _reconcile_rule(self, rule):
        Point = self.env["training.gamification.point"].sudo()
        domain = [("company_id", "=", rule.company_id.id)]
        if rule.course_ids:
            domain.append(("program_id.course_id", "in", rule.course_ids.ids))
        enrollments = self.env["training.enrollment"].sudo().with_context(active_test=False).search(domain)
        active = {
            (point.enrollment_id.id, point.source_key): point
            for point in Point.search([("rule_id", "=", rule.id), ("kind", "=", "grant"), ("withdrawn", "=", False)])
        }
        counts = {}
        for point in active.values():
            counts[point.enrollment_id.id] = counts.get(point.enrollment_id.id, 0) + 1
        start = fields.Datetime.to_datetime(rule.date_from)
        seen = set()
        grants, karma = [], {}
        method = self._event_types()[rule.event_type][1]
        for enrollment, key, qualifies, date in sorted(method(enrollments), key=lambda e: (e[3] or start, e[1])):
            seen.add((enrollment.id, key))
            point = active.get((enrollment.id, key))
            if point and not qualifies:
                self._withdraw(point, karma)
                counts[enrollment.id] -= 1
            elif qualifies and not point:
                user = self._participant_user(enrollment)
                limit = rule.max_per_enrollment
                if (
                    not user
                    or not date
                    or date < start
                    or date < user.create_date
                    or (limit and counts.get(enrollment.id, 0) >= limit)
                ):
                    continue
                counts[enrollment.id] = counts.get(enrollment.id, 0) + 1
                grants.append(
                    {
                        "rule_id": rule.id,
                        "enrollment_id": enrollment.id,
                        "user_id": user.id,
                        "kind": "grant",
                        "points": rule.points,
                        "date": date,
                        "source_key": key,
                    }
                )
        for (enrollment_id, key), point in active.items():
            if (enrollment_id, key) not in seen:
                self._withdraw(point, karma)
        for point in Point.create(grants):
            karma.setdefault(point.user_id, []).append(point)
        self._credit(karma)

    @api.model
    def _withdraw(self, grant, karma):
        grant.write({"withdrawn": True})
        withdrawal = grant.create(
            {
                "rule_id": grant.rule_id.id,
                "enrollment_id": grant.enrollment_id.id,
                "user_id": grant.user_id.id,
                "kind": "withdrawal",
                "points": -grant.points,
                "date": fields.Datetime.now(),
                "source_key": grant.source_key,
                "grant_id": grant.id,
            }
        )
        karma.setdefault(grant.user_id, []).append(withdrawal)

    @api.model
    def _credit(self, karma):
        """One native karma line per journal line, named after its rule (no personal data)."""
        Tracking = self.env["gamification.karma.tracking"].sudo()
        values = []
        for user, points in karma.items():
            value = user.karma
            for point in points:
                values.append(
                    {
                        "user_id": user.id,
                        "old_value": value,
                        "new_value": value + point.points,
                        "origin_ref": f"{point._name},{point.id}",
                        "reason": point.rule_id.name,
                    }
                )
                value += point.points
        Tracking.create(values)

    @api.model
    def _progress_values(self, user):
        """What a participant sees of their own progress: never anyone else's."""
        user = user.sudo()
        points = (
            self.env["training.gamification.point"]
            .sudo()
            .search([("user_id", "=", user.id)], order="date desc, id desc", limit=20)
        )
        goals = (
            self.env["gamification.goal"]
            .sudo()
            .search(
                [
                    ("user_id", "=", user.id),
                    ("challenge_id.state", "=", "inprogress"),
                    ("challenge_id.visibility_mode", "=", "personal"),
                    ("state", "in", ("inprogress", "reached")),
                ],
                order="state, id",
            )
        )
        next_rank = user.next_rank_id
        return {
            "karma": user.karma,
            "rank": user.rank_id.name,
            "next_rank": next_rank.name,
            "to_next_rank": max(next_rank.karma_min - user.karma, 0) if next_rank else 0,
            "badges": [
                {"id": line.badge_id.id, "name": line.badge_id.name, "date": line.create_date.date()}
                for line in user.badge_ids.sorted("create_date", reverse=True)
                if line.badge_id.active
            ],
            "goals": [
                {
                    "challenge": goal.challenge_id.name,
                    "goal": goal.definition_id.name,
                    "current": goal.current,
                    "target": goal.target_goal,
                    "reached": goal.state == "reached",
                }
                for goal in goals
            ],
            "points": [
                {
                    "date": point.date.date(),
                    "rule": point.rule_id.name,
                    "training": point.enrollment_id.program_id.course_id.name,
                    "points": point.points,
                }
                for point in points
            ],
            "can_publish": "website_published" in user._fields,
            "published": bool(user["website_published"]) if "website_published" in user._fields else False,
        }

    CLIENT_MINIMUM = 3

    @api.model
    def _client_indicator(self, allocation_id):
        """Collective engagement of a client's participants, never an individual figure.

        Shown from three participants only, so that nobody's result can be read.
        """
        allocation = self.env["training.company.service"]._allocation(allocation_id)
        enrollments = allocation.sudo().enrollment_ids.filtered(lambda e: e.state in ("confirmed", "closed"))
        if len(enrollments) < self.CLIENT_MINIMUM:
            return False
        active = (
            self.env["training.gamification.point"]
            .sudo()
            .search([("enrollment_id", "in", enrollments.ids), ("kind", "=", "grant"), ("withdrawn", "=", False)])
            .enrollment_id
        )
        challenges = (
            self.env["gamification.challenge"]
            .sudo()
            .search([("training_delivery_id", "=", allocation.delivery_id.id), ("state", "in", ("inprogress", "done"))])
        )
        reached = False
        if challenges:
            users = {enrollment.id: self._participant_user(enrollment) for enrollment in enrollments}
            winners = (
                self.env["gamification.goal"]
                .sudo()
                .search(
                    [
                        ("challenge_id", "in", challenges.ids),
                        ("state", "=", "reached"),
                        ("user_id", "in", [user.id for user in users.values() if user]),
                    ]
                )
                .user_id
            )
            reached = round(100 * len([e for e, user in users.items() if user and user in winners]) / len(enrollments))
        return {
            "participants": len(enrollments),
            "active": round(100 * len(active) / len(enrollments)),
            "challenges": reached,
        }
