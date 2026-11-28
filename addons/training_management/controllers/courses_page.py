"""« My courses »: one page gathering what the signed-in person learns, teaches or manages.

Every list comes from the services that already authorize the destination pages;
this page only adds plain values (titles, dates, links) for rows the person can open.
Modules add their own sections or actions by overriding ``_courses_todo`` or
``_courses_values`` in a subclass of the participant portal controller.
"""

from odoo import fields
from odoo.http import request
from odoo.tools.misc import format_date, format_datetime

ROWS_SHOWN = 5


class TrainingCoursesMixin:
    """Values of the « My courses » page (/my/trainings)."""

    def _courses_values(self):
        env = request.env
        now = fields.Datetime.now()
        enrollments = env["training.document.policy"]._enrollments()
        active = enrollments.filtered(lambda e: e._effective_state() == "active")
        trainings = sorted(
            (self._course_training_row(enrollment, now) for enrollment in active),
            key=lambda row: (row["order"], row["sort"]),
        )
        sessions = self._course_session_rows(now)
        company = env["training.company.service"]._rows()
        todo = sorted(self._courses_todo(active, now), key=lambda item: item["sort"])
        roles = [
            role
            for role, present in (
                ("participant", bool(trainings)),
                ("trainer", bool(sessions)),
                ("company", bool(company)),
            )
            if present
        ]
        upcoming = [row for row in trainings if row["next_at"]]
        return {
            "todo": todo,
            "trainings": trainings,
            "sessions": sessions,
            "company": company,
            "roles": roles,
            "mixed_roles": len(roles) > 1,
            "next_session": min(upcoming, key=lambda row: row["next_at"]) if upcoming else False,
            "rows_shown": ROWS_SHOWN,
            "training_links": env["training.portal.navigation"]._links(),
        }

    # ------------------------------------------------------------------ rows
    @staticmethod
    def _course_dates(start, end, tz):
        env = request.env
        first = format_date(env, fields.Datetime.context_timestamp(env.user.with_context(tz=tz), start).date())
        last = format_date(env, fields.Datetime.context_timestamp(env.user.with_context(tz=tz), end).date())
        return first if first == last else f"{first} → {last}"

    @staticmethod
    def _before(value):
        env = request.env
        local = fields.Datetime.context_timestamp(env.user, fields.Datetime.to_datetime(value))
        return env._("Before %(date)s", date=format_date(env, local.date(), date_format="d MMM"))

    def _course_training_row(self, enrollment, now):
        env = request.env
        delivery = enrollment.delivery_id
        sessions = delivery.session_ids.filtered(lambda s: not s.cancelled and s.start_at and s.end_at).sorted(
            "start_at"
        )
        coming = sessions.filtered(lambda s: s.end_at >= now)
        if not sessions or sessions[0].start_at > now:
            status, label, order = "upcoming", env._("Upcoming"), 1
        elif coming:
            status, label, order = "ongoing", env._("Ongoing"), 0
        else:
            status, label, order = "done", env._("Finished"), 2
        tz = delivery.timezone or env.user.tz or "UTC"
        details = []
        if sessions:
            details.append(self._course_dates(sessions[0].start_at, sessions[-1].end_at, tz))
        nxt = coming[:1]
        if nxt and status != "done":
            details.append(
                env._(
                    "next session %(date)s",
                    date=format_datetime(env, nxt.start_at, tz=tz, dt_format="EEE d MMM · HH:mm"),
                )
            )
        elif not sessions:
            details.append(env._("dates to be announced"))
        done = len(sessions - coming)
        return {
            "id": enrollment.id,
            "name": delivery.name,
            "programme": enrollment.program_id.title,
            "status": status,
            "label": label,
            "order": order,
            "sort": sessions[0].start_at if sessions else now,
            "detail": " · ".join(details),
            "progress": round(100 * done / len(sessions)) if status == "ongoing" and sessions else False,
            "next_at": nxt.start_at if nxt and status != "done" else False,
            "next_label": format_datetime(env, nxt.start_at, tz=tz, dt_format="EEE d MMM · HH:mm") if nxt else "",
            "url": f"/my/trainings/{enrollment.id}",
        }

    def _course_session_rows(self, now):
        from .trainer_portal import TrainingTrainerPortal  # noqa: PLC0415

        env = request.env
        domain = TrainingTrainerPortal()._session_domain() + [("end_at", ">=", now)]
        sessions = env["training.session"].sudo().search(domain, order="start_at, id", limit=50)
        rows = []
        for session in sessions:
            tz = session.timezone or env.user.tz or "UTC"
            start = format_datetime(env, session.start_at, tz=tz, dt_format="EEE d MMM")
            hours = "%s – %s" % (
                format_datetime(env, session.start_at, tz=tz, dt_format="HH:mm"),
                format_datetime(env, session.end_at, tz=tz, dt_format="HH:mm"),
            )
            rows.append(
                {
                    "id": session.id,
                    "label": start,
                    "name": session.delivery_id.name,
                    "detail": " · ".join(filter(None, [session.name, hours])),
                    "ongoing": session.start_at <= now,
                    "url": f"/my/training-sessions/{session.id}",
                }
            )
        return rows

    # ------------------------------------------------------------------ to do
    def _courses_todo(self, enrollments, now):
        """Actions waiting for the person, each linking to the page where it is done.

        Item keys: ``role`` (participant, trainer, company), ``tag``, ``urgent``,
        ``title``, ``detail``, ``url``, ``button`` and ``sort`` (a datetime).
        """
        return (
            self._todo_attendance(enrollments, now)
            + self._todo_attendance_review(now)
            + self._todo_evaluations(enrollments, now)
            + self._todo_practice(now)
        )

    def _todo_attendance(self, enrollments, now):
        from .attendance_portal import AttendancePortal  # noqa: PLC0415

        env = request.env
        learning = env["training.learning.service"]
        service = env["training.attendance.service"]
        portal = AttendancePortal()
        expected = {env._("To declare"), env._("Declaration invalidated")}
        items = []
        for enrollment in enrollments.filtered(learning._is_participant):
            sessions = enrollment.delivery_id.session_ids.filtered(
                lambda s: not s.cancelled and s.start_at and s.start_at <= now and s.attendance_mode != "paper"
            )
            if not sessions:
                continue
            starts = {p["key"]: p["start"] for s in sessions for p in service._periods(s)}
            pending = [
                row
                for row in portal._participant_rows(sessions, enrollment)
                if row["state"] in expected and starts.get(row["period_key"], now) <= now
            ]
            if not pending:
                continue
            elapsed = all(row["elapsed"] for row in pending)
            if len(pending) == 1:
                title = env._("Sign your attendance: %(period)s", period=pending[0]["period"])
            else:
                title = env._("Sign your attendance: %(count)s half-days", count=len(pending))
            items.append(
                {
                    "role": "participant",
                    "tag": env._("To regularize") if elapsed else env._("Now"),
                    "urgent": True,
                    "title": title,
                    "detail": enrollment.delivery_id.name,
                    "url": f"/my/trainings/{enrollment.id}/attendance",
                    "button": env._("Sign"),
                    "sort": min(starts.get(row["period_key"], now) for row in pending),
                }
            )
        return items

    def _todo_attendance_review(self, now):
        from .attendance_portal import AttendancePortal  # noqa: PLC0415
        from .trainer_portal import TrainingTrainerPortal  # noqa: PLC0415

        env = request.env
        domain = TrainingTrainerPortal()._session_domain() + [
            ("start_at", "<=", now),
            ("end_at", ">=", fields.Datetime.subtract(now, days=30)),
        ]
        sessions = env["training.session"].sudo().search(domain, order="start_at, id", limit=20)
        portal = AttendancePortal()
        items = []
        for session in sessions:
            enrollments = session.delivery_id.enrollment_ids.filtered(lambda e: e.state == "confirmed")
            pending = [
                row
                for row in portal._all_rows(session, enrollments)
                if row["review_url"] and row["has_source"] and not row["validated"] and row["can_review"]
            ]
            if not pending:
                continue
            items.append(
                {
                    "role": "trainer",
                    "tag": env._("To check"),
                    "urgent": False,
                    "title": env._("Check %(count)s signed attendances", count=len(pending))
                    if len(pending) > 1
                    else env._("Check 1 signed attendance"),
                    "detail": " · ".join(filter(None, [session.delivery_id.name, session.name])),
                    "url": f"/my/training-sessions/{session.id}/attendance",
                    "button": env._("Check"),
                    "sort": session.start_at,
                }
            )
        return items

    def _todo_evaluations(self, enrollments, now):
        env = request.env
        service = env["training.evaluation.service"]
        model = env["training.evaluation.assignment"].sudo()
        own = enrollments.filtered(env["training.learning.service"]._is_participant)
        visible = service._visible_domain()
        items = []
        for row in model.search(
            visible
            + [
                ("enrollment_id", "in", own.ids),
                ("submitted_at", "=", False),
                ("opens_at", "<=", now),
                ("due_at", ">=", now),
            ],
            order="due_at, id",
            limit=20,
        ):
            items.append(
                {
                    "role": "participant",
                    "tag": self._before(row.due_at),
                    "urgent": False,
                    "title": row.evaluation_id.name or row.name,
                    "detail": row.delivery_id.name,
                    "url": f"/my/training-evaluations/{row.id}",
                    "button": env._("Start"),
                    "sort": row.due_at,
                }
            )
        to_review = model.search(
            visible + [("enrollment_id", "not in", own.ids), ("submitted_at", "!=", False)],
            order="submitted_at, id",
            limit=50,
        ).filtered(lambda r: r.state == "submitted")
        reviewable = env["training.evaluation.assignment"]
        for row in to_review:
            try:
                service._assignment(row.id, evaluate=True)
            except Exception:  # noqa: BLE001 - not this person's to validate
                continue
            reviewable |= row
        for delivery in reviewable.delivery_id:
            rows = reviewable.filtered(lambda r, d=delivery: r.delivery_id == d)
            items.append(
                {
                    "role": "trainer",
                    "tag": env._("To validate"),
                    "urgent": False,
                    "title": env._("Validate %(count)s evaluations", count=len(rows))
                    if len(rows) > 1
                    else env._("Validate 1 evaluation"),
                    "detail": delivery.name,
                    "url": f"/my/training-evaluations/{rows[:1].id}",
                    "button": env._("Validate"),
                    "sort": min(rows.mapped("submitted_at")),
                }
            )
        return items

    def _todo_practice(self, now):
        env = request.env
        items = []
        for row in env["training.practice.action"]._portal_rows():
            if row["role"] != "participant" or row["state"] != "planned":
                continue
            due = row["due"]
            items.append(
                {
                    "role": "participant",
                    "tag": self._before(due) if due else "",
                    "urgent": bool(due and due <= fields.Date.context_today(env.user)),
                    "title": row["name"],
                    "detail": row["training"],
                    "url": f"/my/training-practice#practice_body_{row['id']}",
                    "button": env._("Open page"),
                    "sort": fields.Datetime.to_datetime(due) if due else now,
                }
            )
        return items
