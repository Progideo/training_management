"""Live, read-only projections. No learning entries or raw questionnaire answers."""

import json
from datetime import timedelta

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools.misc import formatLang

from .training_evaluation import COORDINATOR, QUALITY, SUPERVISOR

STATES = [
    (s, label)
    for s, label in [
        ("requested", "Requested"),
        ("reserved", "Reserved"),
        ("waiting", "Waiting"),
        ("confirmed", "Confirmed"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
        ("replaced", "Replaced"),
        ("abandoned", "Abandoned"),
        ("postponed", "Postponed"),
    ]
]


class DashboardLine(models.Model):
    _name = "training.dashboard.line"
    _description = "Training Operational Dashboard"
    _auto = False
    _order = "delivery_id, name, id"

    name = fields.Char(string="Participant", readonly=True)
    enrollment_id = fields.Integer(readonly=True)
    delivery_id = fields.Many2one("training.delivery", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    program = fields.Char(string="Programme / Version", readonly=True)
    state = fields.Selection(STATES, string="Enrollment Status", readonly=True)
    attendance = fields.Text(compute="_compute_projection")
    questionnaires = fields.Text(compute="_compute_projection")
    evaluations = fields.Text(compute="_compute_projection")
    attendance_incomplete = fields.Boolean(compute="_compute_projection", search="_search_attendance")
    feedback_pending = fields.Boolean(compute="_compute_projection", search="_search_feedback")
    evaluation_pending = fields.Boolean(compute="_compute_projection", search="_search_evaluation")
    overdue = fields.Boolean(compute="_compute_projection", search="_search_overdue")
    details = fields.Html(compute="_compute_projection", sanitize=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW training_dashboard_line AS
            SELECT e.id, e.id AS enrollment_id, e.delivery_id, e.company_id,
                   p.name, e.state, COALESCE(v.title->>'en_US', '') || ' — ' || v.version AS program
            FROM training_enrollment e
            JOIN res_partner p ON p.id=e.participant_id
            JOIN training_delivery d ON d.id=e.delivery_id
            JOIN training_program_version v ON v.id=d.program_id
        """)

    @api.depends_context("uid", "lang", "allowed_company_ids")
    def _compute_projection(self):
        self.check_access("read")
        service = self.env["training.dashboard.service"]
        batch = service._batch(self.env["training.enrollment"].sudo().browse(self.mapped("enrollment_id")))
        for line in self:
            row = service._participant(line.enrollment_id, batch=batch)
            line.attendance = "\n".join(r["label"] for r in row["attendance"])
            line.questionnaires = "\n".join(r["label"] for r in row["feedback"])
            line.evaluations = "\n".join(
                (
                    r["label"]
                    + (
                        self.env._(
                            " · score %(score)s / threshold %(threshold)s", score=r["score"], threshold=r["threshold"]
                        )
                        if r.get("score") is not None
                        else ""
                    )
                )
                for r in row["evaluations"] + row["exams"]
            )
            line.attendance_incomplete = row["attendance_incomplete"]
            line.feedback_pending = row["feedback_pending"]
            line.evaluation_pending = row["evaluation_pending"]
            line.overdue = row["overdue"]
            line.details = self.env["ir.qweb"]._render("training_management.dashboard_participant", {"row": row})

    @api.model
    def _search_flag(self, name, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise ValidationError(self.env._("Choose a boolean dashboard filter."))
        lines = self.search([("company_id", "in", self.env.companies.ids)])
        service = self.env["training.dashboard.service"]
        batch = service._batch(self.env["training.enrollment"].sudo().browse(lines.mapped("enrollment_id")))
        expected = value if operator == "=" else not value
        return Domain(
            "id",
            "in",
            [
                line.id
                for line in lines
                if bool(service._participant(line.enrollment_id, batch=batch, details=False)[name]) == expected
            ],
        )

    def _search_attendance(self, operator, value):
        return self._search_flag("attendance_incomplete", operator, value)

    def _search_feedback(self, operator, value):
        return self._search_flag("feedback_pending", operator, value)

    def _search_evaluation(self, operator, value):
        return self._search_flag("evaluation_pending", operator, value)

    def _search_overdue(self, operator, value):
        return self._search_flag("overdue", operator, value)

    def action_delivery_dashboard(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_url",
            "url": "/my/training-dashboard/%s" % self.delivery_id.id,
            "target": "self",
        }


class DashboardService(models.AbstractModel):
    _name = "training.dashboard.service"
    _description = "Scoped Training Dashboard Projection"

    @api.private
    def _delivery(self, delivery_id):
        delivery = self.env["training.delivery"].sudo().browse(delivery_id).exists()
        user = self.env.user
        if (
            not delivery
            or not user.active
            or user._is_public()
            or delivery.company_id not in self.env.companies
            or not self.env["training.evaluation.service"]._staff(delivery)
        ):
            raise AccessError(self.env._("This training dashboard is unavailable."))
        return delivery

    @api.private
    def _deliveries(self):
        user = self.env.user
        if not user.active or user._is_public():
            return []
        domain = Domain("company_id", "in", self.env.companies.ids)
        if not user.has_group(COORDINATOR):
            rights = Domain("evaluation_instructor_ids", "in", user.partner_id.ids)
            rights |= Domain(
                "session_ids", "any", [("instructor_id", "=", user.partner_id.id), ("cancelled", "=", False)]
            )
            if user.has_group(SUPERVISOR):
                rights |= Domain("evaluation_supervisor_ids", "in", user.ids)
            if user.has_group(QUALITY):
                rights |= Domain("evaluation_quality_id", "=", user.id)
            domain &= rights
        return [{"id": d.id, "name": d.name} for d in self.env["training.delivery"].sudo().search(domain)]

    @api.private
    def _label(self, row, name):
        return dict(row._fields[name]._description_selection(self.env)).get(row[name], "")

    @api.private
    def _sessions(self, delivery):
        user = self.env.user
        sessions = delivery.session_ids.filtered(lambda s: not s.cancelled)
        broad = (
            user.has_group(COORDINATOR)
            or (user.has_group(SUPERVISOR) and user in delivery.evaluation_supervisor_ids)
            or (user.has_group(QUALITY) and user == delivery.evaluation_quality_id)
        )
        return sessions if broad else sessions.filtered(lambda s: s.instructor_id == user.partner_id)

    @api.private
    def _batch(self, enrollments):
        # Authorize the complete scope once before any elevated batched reads.
        deliveries = enrollments.delivery_id
        for delivery in deliveries:
            self._delivery(delivery.id)
        sessions = {d.id: self._sessions(d) for d in deliveries}
        session_ids = [session.id for rows in sessions.values() for session in rows]
        operations = (
            self.env["training.operation"]
            .sudo()
            .search(
                [
                    ("model_name", "=", "training.enrollment"),
                    ("record_id", "in", enrollments.ids),
                ],
                order="occurred_at, id",
            )
        )
        presences = (
            self.env["training.attendance"]
            .sudo()
            .search(
                [
                    ("enrollment_id", "in", enrollments.ids),
                    ("session_id", "in", session_ids),
                ]
            )
        )
        # Prefetch evidence metadata across the population; never fetch binary content.
        presences.event_ids.fetch(["kind", "start_at", "end_at", "absent", "anomaly"])
        campaigns = self.env["training.feedback.campaign"].sudo().search([("delivery_id", "in", deliveries.ids)])
        recipients = (
            self.env["training.feedback.recipient"]
            .sudo()
            .with_context(active_test=False)
            .search(
                [
                    ("campaign_id", "in", campaigns.ids),
                    ("enrollment_id", "in", enrollments.ids),
                    ("role", "=", "participant"),
                ]
            )
        )
        named = recipients.filtered(lambda r: not r.campaign_id.anonymous)
        return {
            "enrollments": enrollments,
            "by_id": {row.id: row for row in enrollments},
            "sessions": sessions,
            "operations": operations.grouped("record_id"),
            "presences": presences.grouped(lambda r: (r.enrollment_id.id, r.session_id.id)),
            "campaigns": campaigns.grouped("delivery_id"),
            "recipients": recipients.grouped(lambda r: (r.enrollment_id.id, r.campaign_id.id)),
            "feedback_states": self.env["training.feedback.service"]._nominative_states(named),
            "assignments": self.env["training.evaluation.assignment"]
            .sudo()
            .search(
                [
                    ("enrollment_id", "in", enrollments.ids),
                ]
            )
            .grouped("enrollment_id"),
        }

    @api.private
    def _eligible_at(self, enrollment, when, batch=None):
        # Historical state is read from controlled S03 transitions; an absent sheet
        # never becomes a validated absence, and cancellation before start is excluded.
        if enrollment.requested_at > when:
            return False
        history = (
            batch["operations"].get(enrollment.id, self.env["training.operation"])
            if batch is not None
            else (
                self.env["training.operation"]
                .sudo()
                .search(
                    [
                        ("model_name", "=", "training.enrollment"),
                        ("record_id", "=", enrollment.id),
                        ("occurred_at", "<=", when),
                    ],
                    order="occurred_at, id",
                )
            )
        )
        state = "requested"
        for event in history:
            if event.occurred_at > when:
                break
            state = json.loads(event.after or "{}").get("state", state)
        return state == "confirmed"

    @api.private
    def _attendance(self, enrollment, sessions, batch=None, details=True):
        result = []
        now = fields.Datetime.now()
        for session in sessions:
            applicable = self._eligible_at(enrollment, min(now, session.start_at), batch)
            presence = (
                batch["presences"].get((enrollment.id, session.id), self.env["training.attendance"])
                if batch is not None
                else (
                    self.env["training.attendance"]
                    .sudo()
                    .search([("session_id", "=", session.id), ("enrollment_id", "=", enrollment.id)])
                )
            )
            events = presence.event_ids.sorted("id")
            validated = presence.filtered(lambda r: r.state == "validated")
            expected = {p["key"] for p in self.env["training.attendance.service"]._periods(session)}
            complete = bool(validated.filtered(lambda r: r.period_key == "legacy")) or expected <= set(
                validated.mapped("period_key")
            )
            if not applicable:
                state = self.env._("Not applicable: not confirmed at session start")
            elif complete:
                state = (
                    self.env._("Validated absence")
                    if all(validated.mapped("absent"))
                    else self.env._("Validated presence")
                )
            elif presence.filtered(lambda r: r.state == "anomaly"):
                state = self.env._("Anomaly — review required")
            elif session.attendance_mode == "paper" or events.filtered(lambda e: e.kind == "paper"):
                state = (
                    self.env._("Paper deposited — awaiting review")
                    if events.with_context(bin_size=True).filtered("data")
                    else self.env._("Paper to deposit")
                )
            else:
                state = self.env._("Declared — awaiting review") if events else self.env._("Expected — not declared")
            result.append(
                {
                    "session": session.name,
                    "session_id": session.id,
                    "date": str(session.start_at),
                    "mode": self._label(session, "attendance_mode"),
                    "state": state,
                    "label": "%s: %s" % (session.name, state),
                    "applicable": applicable,
                    "validated": bool(applicable and complete),
                    "minutes": sum(validated.mapped("minutes")) if applicable and validated else None,
                    "planned": (session.end_at - session.start_at).total_seconds() / 60 if applicable else 0,
                    "revision": max(presence.mapped("revision"), default=0),
                    "history": [
                        {
                            "kind": self._label(e, "kind"),
                            "date": str(e.occurred_at),
                            "reason": e.reason or "",
                            "evidence_url": ("/web/content/training.attendance.event/%s/data?download=true" % e.id)
                            if e.with_context(bin_size=True).data and self.env["training.document.policy"]._can_read(e)
                            else "",
                        }
                        for e in events
                    ]
                    if details
                    else [],
                }
            )
        return result

    @api.private
    def _campaigns(self, delivery):
        return self.env["training.feedback.campaign"].sudo().search([("delivery_id", "=", delivery.id)])

    @api.private
    def _feedback(self, enrollment, batch=None):
        result = []
        campaigns = (
            batch["campaigns"].get(enrollment.delivery_id, self.env["training.feedback.campaign"])
            if batch is not None
            else self._campaigns(enrollment.delivery_id)
        )
        for campaign in campaigns:
            recipients = (
                batch["recipients"].get((enrollment.id, campaign.id), self.env["training.feedback.recipient"])
                if batch is not None
                else campaign.with_context(active_test=False).recipient_ids.filtered(
                    lambda r: r.role == "participant" and r.enrollment_id == enrollment
                )
            )
            if not recipients:
                continue
            recipient = recipients[:1]
            # Never call response state or touch answer tables for an anonymous row.
            code = (
                "anonymous"
                if campaign.anonymous
                else batch["feedback_states"][recipient.id]
                if batch is not None
                else recipient._nominative_state()
            )
            state = (
                self.env._("Anonymous collection — individual tracking unavailable")
                if campaign.anonymous
                else dict(recipient._fields["response_state"]._description_selection(self.env))[code]
            )
            result.append(
                {
                    "name": campaign.name,
                    "version": campaign.feedback_id.version,
                    "due": str(campaign.due_at),
                    "state": state,
                    "anonymous": campaign.anonymous,
                    "code": code,
                    "late": not campaign.anonymous
                    and code not in ("received", "not_applicable")
                    and campaign.due_at < fields.Datetime.now(),
                    "label": "%s · %s: %s" % (campaign.name, campaign.feedback_id.version, state),
                }
            )
        return result

    @api.private
    def _evaluations(self, enrollment, batch=None):
        result = []
        assignments = (
            batch["assignments"].get(enrollment, self.env["training.evaluation.assignment"])
            if batch is not None
            else self.env["training.evaluation.assignment"].sudo().search([("enrollment_id", "=", enrollment.id)])
        )
        for assignment in assignments:
            definition = assignment.evaluation_id
            state = self._label(assignment, "state")
            result.append(
                {
                    "id": assignment.id,
                    "name": definition.name,
                    "version": definition.version,
                    "purpose": self._label(definition, "purpose"),
                    "state": state,
                    "code": assignment.state,
                    "due": str(assignment.due_at),
                    "scored": definition.scored,
                    "score": assignment.score if assignment.result_available else None,
                    "threshold": assignment.threshold if definition.scored else None,
                    "revision": assignment.revision,
                    "attempt": assignment.attempt_number,
                    "late": assignment.state != "validated" and assignment.due_at < fields.Datetime.now(),
                    "label": "%s · %s · %s: %s"
                    % (self._label(definition, "purpose"), definition.name, definition.version, state),
                }
            )
        return result

    @api.private
    def _exams(self, enrollment, batch=None):
        return []  # optional native Surveys integration supplies scored mock exams

    @api.private
    def _participant(self, enrollment_id, batch=None, details=True):
        enrollment = (
            batch["by_id"].get(enrollment_id)
            if batch is not None
            else self.env["training.enrollment"].sudo().browse(enrollment_id).exists()
        )
        if not enrollment:
            raise AccessError(self.env._("This training dashboard is unavailable."))
        if batch is None:
            batch = self._batch(enrollment)
        if enrollment not in batch["enrollments"]:
            raise AccessError(self.env._("This training dashboard is unavailable."))
        delivery = enrollment.delivery_id
        attendance = self._attendance(enrollment, batch["sessions"][delivery.id], batch, details)
        feedback = self._feedback(enrollment, batch)
        evaluations = self._evaluations(enrollment, batch)
        return {
            "id": enrollment.id,
            "name": enrollment.participant_id.name,
            "state": self._label(enrollment, "state"),
            "state_code": enrollment.state,
            "attendance": attendance,
            "attendance_na": delivery.kind == "autonomous" and not delivery.session_ids,
            "attendance_missing": delivery.kind != "autonomous" and not delivery.session_ids,
            "feedback": feedback,
            "evaluations": evaluations,
            "exams": self._exams(enrollment, batch) if details else [],
            "attendance_incomplete": (delivery.kind != "autonomous" and not delivery.session_ids)
            or any(r["applicable"] and not r["validated"] for r in attendance),
            "feedback_pending": any(
                not r["anonymous"] and r["code"] not in ("received", "not_applicable") for r in feedback
            ),
            "evaluation_pending": any(r["code"] != "validated" for r in evaluations),
            "overdue": any(r["late"] for r in feedback + evaluations),
        }

    @api.private
    def _ratio(self, name, numerator, denominator, population, formula):
        rate = 100 * numerator / denominator if denominator else None
        return {
            "name": name,
            "numerator": numerator,
            "denominator": denominator,
            "population": population,
            "formula": formula,
            "version": "S10-1",
            "rate": rate,
            "rate_text": formatLang(self.env, rate, digits=2) if rate is not None else "",
            "coverage_numerator": denominator,
            "coverage_denominator": population,
        }

    @api.private
    def _quality(self, delivery):
        result = []
        for model_name in (
            "training.closure",
            "training.complaint",
            "training.improvement",
            "training.provider.dossier",
            "training.provider.obligation",
        ):
            model = self.env[model_name]
            if not model.has_access("read"):
                continue
            # Normal ORM rights only: no sensitive-quality access added by S10.
            domain = [("company_id", "=", delivery.company_id.id)]
            if "delivery_id" in model._fields:
                domain.append(("delivery_id", "=", delivery.id))
            records = model.search(domain)
            if model_name == "training.closure":
                result.append(
                    self._ratio(
                        self.env._("Dossiers without missing required proof"),
                        len(records.filtered(lambda r: not r._missing_keys())),
                        len(records),
                        len(records),
                        self.env._("complete dossiers / authorized dossiers"),
                    )
                )
            else:
                result.append(
                    {
                        "name": {
                            "training.complaint": self.env._("Authorized complaints"),
                            "training.improvement": self.env._("Authorized improvement actions"),
                            "training.provider.dossier": self.env._("Authorized provider registers"),
                            "training.provider.obligation": self.env._("Authorized contractual obligations"),
                        }[model_name],
                        "count": len(records),
                        "overdue_count": (
                            len(records.filtered("overdue"))
                            if "overdue" in model._fields
                            else len(
                                records.filtered(lambda r: r.state == "pending" and r.due_date < fields.Date.today())
                            )
                            if model_name == "training.provider.obligation"
                            else None
                        ),
                        "open_count": len(records.filtered(lambda r: r.state not in r._terminal_states()))
                        if model_name in ("training.complaint", "training.improvement")
                        else None,
                        "states": [
                            {
                                "state": self._label(r, "state"),
                                "id": r.id,
                                "name": r.display_name,
                                "url": "/odoo/%s/%s" % (model_name, r.id),
                            }
                            for r in records
                        ],
                    }
                )
        return result

    @api.private
    def _notifications(self, delivery):
        if not self.env.user.has_group(COORDINATOR):
            return []
        result = []
        # Private learning-entry notices are deliberately absent, including counts.
        for model_name, extra in (
            ("training.invitation", []),
            ("training.feedback.notice", []),
            ("training.learning.notice", [("entry_id", "=", False)]),
            ("training.practice.notice", []),
            ("training.notification", []),
        ):
            model = self.env[model_name]
            key = "campaign_id.delivery_id" if model_name == "training.feedback.notice" else "delivery_id"
            for notice in model.search([(key, "=", delivery.id)] + extra):
                mail = notice.sudo().mail_id
                result.append(
                    {
                        "kind": (
                            self._label(notice, "kind")
                            if model_name == "training.notification"
                            else self.env._("Invitation / reminder")
                            if model_name == "training.feedback.notice"
                            else self.env._("Practice Reminder")
                            if model_name == "training.practice.notice"
                            else self.env._("Inactivity Reminder")
                            if model_name == "training.learning.notice"
                            else self.env._("Training invitation / schedule update")
                        ),
                        "date": str(notice.create_date),
                        "state": self._label(mail, "state") if mail else self.env._("Not queued"),
                        "failure": (mail.failure_reason or "") if mail else self.env._("No authorized recipient"),
                        "recipient": (
                            notice.recipient_id.user_id.name
                            if model_name == "training.feedback.notice"
                            else notice.partner_id.name
                            if model_name == "training.invitation"
                            else notice.recipient_id.name
                        )
                        or self.env._("No recipient"),
                        "template": notice.template_version
                        if model_name == "training.notification"
                        else {
                            "training.feedback.notice": "S09.2 — stored native mail",
                            "training.invitation": "S04 — stored native mail",
                            "training.learning.notice": "S05 — stored native mail",
                            "training.practice.notice": "P11 — stored native mail",
                            "training.notification": "S10-LIFECYCLE-1",
                        }[model_name],
                        "source": model_name,
                        "id": notice.id,
                    }
                )
        return result

    @api.private
    def _cohort_metrics(self, delivery, enrollments, start, end, batch=None):
        now = fields.Datetime.now()
        started = enrollments.filtered(
            lambda e: (
                (delivery.start_at or e.access_start)
                and (delivery.start_at or e.access_start) <= now
                and (not start or (delivery.start_at or e.access_start).date() >= start)
                and (not end or (delivery.start_at or e.access_start).date() <= end)
                and (
                    (delivery.kind == "autonomous" and e.access_start)
                    or self._eligible_at(e, delivery.start_at or e.access_start, batch)
                )
            )
        )
        result = [
            self._ratio(
                self.env._("Started enrollments abandoned"),
                len(started.filtered(lambda e: e.state == "abandoned")),
                len(started),
                len(started),
                self.env._("abandoned after start / confirmed enrollments at start"),
            )
        ]
        result.append(
            self._ratio(
                self.env._("Confirmed seats / defined capacity"),
                len(enrollments.filtered(lambda e: e.state == "confirmed")),
                delivery.capacity,
                len(enrollments),
                self.env._("current confirmed enrollments / delivery capacity; zero capacity means undefined"),
            )
        )
        result.append(
            {
                "name": self.env._("Reserved enrollments — separate from confirmed seats"),
                "count": len(enrollments.filtered(lambda e: e.state == "reserved")),
            }
        )
        # Overall completion only; never project names, submissions or private exchanges.
        candidates = enrollments.filtered(lambda e: e.state in ("confirmed", "closed", "abandoned"))
        activities = delivery.learning_activity_ids.filtered(lambda a: not a.optional)
        due = candidates.filtered(
            lambda e: (
                e.access_start
                and delivery.learning_due_days
                and (not start or (e.access_start + timedelta(days=delivery.learning_due_days)).date() >= start)
                and (not end or (e.access_start + timedelta(days=delivery.learning_due_days)).date() <= end)
                and (e.access_start + timedelta(days=delivery.learning_due_days)) <= now
                and e.state in ("confirmed", "closed", "abandoned")
            )
        )
        complete = self.env["training.learning.service"]
        result.append(
            self._ratio(
                self.env._("Overall course completion"),
                len(due.filtered(lambda e: bool(activities) and all(complete._complete(e, a) for a in activities))),
                len(due) if activities else 0,
                len(candidates),
                self.env._("all required published criteria satisfied / applicable enrollments due in period"),
            )
        )
        result.append(
            {
                "name": self.env._("Missing course deadline or required completion criteria"),
                "count": len(
                    candidates.filtered(
                        lambda e: not e.access_start or not delivery.learning_due_days or not activities
                    )
                ),
            }
        )
        return result

    @api.private
    def _commercial(self, delivery, start, end):
        return []

    @api.private
    def _dashboard(
        self, delivery_id, *, state="all", session_id=0, start=None, end=None, issue="all", page=None, step=40
    ):
        delivery = self._delivery(delivery_id)
        if state != "all" and state not in dict(STATES):
            raise ValidationError(self.env._("Choose a valid enrollment status."))
        if issue not in ("all", "attendance", "feedback", "evaluation", "overdue"):
            raise ValidationError(self.env._("Choose a valid dashboard filter."))
        try:
            start = fields.Date.to_date(start) if start else None
            end = fields.Date.to_date(end) if end else None
        except (ValueError, TypeError):
            raise ValidationError(self.env._("Choose valid period dates.")) from None
        if start and end and start > end:
            raise ValidationError(self.env._("The end of the period must follow its start."))
        sessions = self._sessions(delivery)
        if session_id:
            sessions = sessions.filtered(lambda s: s.id == session_id)
            if not sessions:
                raise AccessError(self.env._("This training dashboard is unavailable."))
        sessions = sessions.filtered(
            lambda s: (not start or s.start_at.date() >= start) and (not end or s.start_at.date() <= end)
        )
        enrollments = delivery.enrollment_ids
        if state != "all":
            enrollments = enrollments.filtered(lambda e: e.state == state)
        batch = self._batch(enrollments)
        rows = []
        for enrollment in enrollments:
            row = self._participant(enrollment.id, batch=batch, details=False)
            row["attendance"] = [r for r in row["attendance"] if r["session_id"] in sessions.ids]
            for key in ("feedback", "evaluations"):
                row[key] = [
                    r
                    for r in row[key]
                    if (not start or r["due"][:10] >= str(start)) and (not end or r["due"][:10] <= str(end))
                ]
            row["attendance_incomplete"] = row["attendance_missing"] or any(
                r["applicable"] and not r["validated"] for r in row["attendance"]
            )
            row["feedback_pending"] = any(
                not r["anonymous"] and r["code"] not in ("received", "not_applicable") for r in row["feedback"]
            )
            row["evaluation_pending"] = any(r["code"] != "validated" for r in row["evaluations"])
            row["overdue"] = any(r["late"] for r in row["feedback"] + row["evaluations"])
            if (
                issue == "all"
                or row[
                    {
                        "attendance": "attendance_incomplete",
                        "feedback": "feedback_pending",
                        "evaluation": "evaluation_pending",
                        "overdue": "overdue",
                    }[issue]
                ]
            ):
                rows.append(row)
        # Group each definition/version separately: never mix repeats, purposes or thresholds.
        metrics = []
        assignments = (
            self.env["training.evaluation.assignment"]
            .sudo()
            .search([("enrollment_id", "in", [r["id"] for r in rows]), ("purpose", "=", "acquired")])
        )
        assignments = assignments.filtered(
            lambda a: (not start or a.due_at.date() >= start) and (not end or a.due_at.date() <= end)
        )
        for definition in assignments.evaluation_id:
            group = assignments.filtered(lambda a: a.evaluation_id == definition)
            validated = group.filtered(lambda a: a.state == "validated" and a.result_available)
            metrics.append(
                self._ratio(
                    definition.name + " · " + definition.version,
                    len(validated.filtered(lambda a: a.score >= a.threshold)),
                    len(validated),
                    len(group),
                    self.env._("validated at threshold / validated scored acquired assessments"),
                )
            )
        attendance = [a for r in rows for a in r["attendance"]]
        metrics.append(
            self._ratio(
                self.env._("Validated attendance minutes"),
                sum(a["minutes"] or 0 for a in attendance),
                sum(a["planned"] for a in attendance),
                len(rows),
                self.env._("validated minutes / applicable scheduled minutes"),
            )
        )
        metrics[-1].update(
            coverage_numerator=sum(bool(a["validated"]) for a in attendance),
            coverage_denominator=sum(bool(a["applicable"]) for a in attendance),
        )
        cohort_metrics = self._cohort_metrics(delivery, enrollments.browse([r["id"] for r in rows]), start, end, batch)
        campaigns = []
        for campaign in self._campaigns(delivery):
            if (start and campaign.due_at.date() < start) or (end and campaign.due_at.date() > end):
                continue
            summary = self.env["training.feedback.service"]._summary_text(campaign)
            campaigns.append(
                {
                    "name": campaign.name,
                    "version": campaign.feedback_id.version,
                    "purpose": self._label(campaign, "purpose"),
                    "population": campaign.population,
                    "anonymous": campaign.anonymous,
                    "summary": summary,
                    "rate_text": formatLang(self.env, campaign.snapshot["rate"], digits=2)
                    if campaign.state == "closed" and campaign.snapshot and campaign.snapshot.get("rate") is not None
                    else "",
                    "snapshot": campaign.snapshot
                    if campaign.state == "closed" and not campaign.snapshot.get("insufficient")
                    else None,
                }
            )
        population = len(rows)
        if page is not None:
            page = max(1, min(page, max(1, (population + step - 1) // step)))
            rows = rows[(page - 1) * step : page * step]
        # Rich history, file links and exam attempts are loaded only for the visible page.
        visible = enrollments.browse([row["id"] for row in rows])
        detail_batch = self._batch(visible)
        for row in rows:
            full = self._participant(row["id"], batch=detail_batch)
            histories = {a["session_id"]: a["history"] for a in full["attendance"]}
            for attendance_row in row["attendance"]:
                attendance_row["history"] = histories[attendance_row["session_id"]]
            row["exams"] = full["exams"]
        current = fields.Datetime.now()
        return {
            "delivery_id": delivery.id,
            "name": delivery.name,
            "program": delivery.program_id.display_name,
            "company": delivery.company_id.name,
            "extracted_at": str(current),
            "start": str(start or ""),
            "end": str(end or ""),
            "state": state,
            "issue": issue,
            "session_id": session_id,
            "population": population,
            "rows": rows,
            "sessions": [{"id": s.id, "name": s.name} for s in self._sessions(delivery)],
            "metrics": metrics,
            "cohort_metrics": cohort_metrics,
            "campaigns": campaigns,
            "notifications": self._notifications(delivery),
            "quality": self._quality(delivery),
            "commercial": self._commercial(delivery, start, end),
            "margin": self.env._("Deferred: documented direct costs and conversion rates required"),
        }
