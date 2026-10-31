from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools.misc import format_datetime

from .material_portal import TrainingParticipantPortal


class AttendancePortal(http.Controller):
    @http.route(
        "/my/trainings/<int:enrollment_id>/attendance", type="http", auth="user", website=True, methods=["GET", "POST"]
    )
    def participant(self, enrollment_id, **post):
        service = request.env["training.attendance.service"]
        try:
            enrollment = request.env["training.learning.service"]._enrollment(enrollment_id)
            error = False
            if request.httprequest.method == "POST":
                try:
                    self._check_choice(post)
                    service._declare_halfday(
                        enrollment.id,
                        post.get("period_key"),
                        absent=post.get("attendance") == "absent",
                        accepted=post.get("accepted") == "yes",
                        definition=post.get("definition"),
                    )
                    return TrainingParticipantPortal._private(request.redirect(request.httprequest.path))
                except (ValueError, ValidationError) as exc:
                    error = str(exc) if isinstance(exc, ValidationError) else request.env._("Choose a valid session.")
            sessions = enrollment.delivery_id.session_ids.filtered(lambda s: not s.cancelled)
            rows = self._participant_rows(sessions, enrollment)
            if error:
                self._draft(rows, post, trainer=False)
        except (AccessError, MissingError):
            raise request.not_found() from None
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_attendance",
                {"rows": rows, "error": error, "trainer": False, "name": enrollment.delivery_id.name},
            )
        )

    @http.route(
        "/my/training-sessions/<int:session_id>/attendance",
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
    )
    def trainer(self, session_id, **post):
        service = request.env["training.attendance.service"]
        try:
            session = service._session(session_id)
            error = False
            if request.httprequest.method == "POST":
                try:
                    if post.get("operation") != "invalidate":
                        self._check_choice(post)
                    operation = service._invalidate if post.get("operation") == "invalidate" else service._review
                    key = post.get("period_key", "")
                    interval = (
                        ()
                        if post.get("operation") == "invalidate"
                        else (0, 0)
                        if post.get("attendance") == "absent"
                        else self._review_interval(session, int(post.get("enrollment_id", 0)), key)
                    )
                    options = (
                        {} if post.get("operation") == "invalidate" else {"absent": post.get("attendance") == "absent"}
                    )
                    operation(
                        session.id,
                        int(post.get("enrollment_id", 0)),
                        *interval,
                        **options,
                        revision=int(post.get("revision", 0)),
                        period_key=key,
                        definition=post.get("definition"),
                        reason=post.get("reason", ""),
                    )
                    return TrainingParticipantPortal._private(request.redirect(request.httprequest.path))
                except (ValueError, ValidationError) as exc:
                    error = (
                        str(exc) if isinstance(exc, ValidationError) else request.env._("Choose a valid participant.")
                    )
            enrollments = session.delivery_id.enrollment_ids.filtered(lambda e: e.state == "confirmed")
            rows = [row for enrollment in enrollments for row in self._rows(session, enrollment)]
            if error:
                self._draft(rows, post, trainer=True)
        except (AccessError, MissingError):
            raise request.not_found() from None
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_attendance",
                {"rows": rows, "error": error, "trainer": True, "name": session.name},
            )
        )

    @staticmethod
    def _check_choice(post):
        if post.get("attendance") not in ("present", "absent"):
            raise ValidationError(request.env._("Choose present or absent for this half-day."))

    @staticmethod
    def _review_interval(session, enrollment_id, key):
        if key != "legacy":
            return 0, 0  # the server derives the complete planned half-day
        presence = (
            request.env["training.attendance"]
            .sudo()
            .search(
                [
                    ("session_id", "=", session.id),
                    ("enrollment_id", "=", enrollment_id),
                    ("period_key", "=", "legacy"),
                ],
                limit=1,
            )
        )
        last = presence.event_ids.filtered(lambda e: e.start_at and e.end_at).sorted("id")[-1:]
        if not last:
            raise ValidationError(request.env._("There is no historical declaration to validate."))
        return (
            (last.start_at - session.start_at).total_seconds() / 60,
            (last.end_at - session.start_at).total_seconds() / 60,
        )

    def _draft(self, rows, post, *, trainer):
        for row in rows:
            if row["period_key"] == post.get("period_key") and (
                not trainer or str(row["enrollment_id"]) == post.get("enrollment_id")
            ):
                row.update(absent=post.get("attendance") == "absent", reason=post.get("reason", ""))

    def _participant_rows(self, sessions, enrollment):
        service = request.env["training.attendance.service"]
        grouped = {}
        for row in self._rows(sessions, enrollment):
            # Historical intervals remain separately reviewable; no history is reinterpreted.
            key = (row["period_key"], row["mode"] == "paper", row["session_id"] if row["period_key"] == "legacy" else 0)
            grouped.setdefault(key, []).append(row)
        result = []
        for rows in grouped.values():
            row = dict(rows[0])
            day_sessions = sessions.filtered(lambda session: session.id in [r["session_id"] for r in rows])
            row.update(
                name=" · ".join(r["name"] for r in rows),
                timezone=" / ".join(dict.fromkeys(r["timezone"] for r in rows)),
                declared=all(r["declared"] for r in rows),
                minutes=sum(r["minutes"] for r in rows),
                history=[event for r in rows for event in r["history"]],
                wording=" ".join(dict.fromkeys(r["wording"] for r in rows)),
                definition=service._day_definition(day_sessions),
                state=request.env._("Validated")
                if all(r["validated"] for r in rows)
                else request.env._("Pending Review"),
            )
            result.append(row)
        return result

    def _rows(self, sessions, enrollment):
        rows = []
        service = request.env["training.attendance.service"]
        for session in sessions:
            for period in service._visible_periods(session, enrollment.id):
                presence = (
                    request.env["training.attendance"]
                    .sudo()
                    .search(
                        [
                            ("session_id", "=", session.id),
                            ("enrollment_id", "=", enrollment.id),
                            ("period_key", "=", period["key"]),
                        ],
                        limit=1,
                    )
                )
                events = presence.event_ids.sorted("id")
                last = events[-1:]
                invalidation = events.filtered(lambda e: e.kind == "invalidation")[-1:]
                tz = session.timezone
                rows.append(
                    {
                        "session_id": session.id,
                        "enrollment_id": enrollment.id,
                        "period_key": period["key"],
                        "period": period["label"],
                        "name": session.name,
                        "participant": enrollment.participant_id.name,
                        "timezone": tz,
                        "wording": session.attendance_wording,
                        "definition": service._definition(session),
                        "mode": session.attendance_mode,
                        "revision": presence.revision if presence else 0,
                        "absent": bool(last.absent),
                        "reason": "",
                        "minutes": presence.minutes if presence else 0,
                        "state": dict(presence._fields["state"]._description_selection(request.env)).get(
                            presence.state, request.env._("Not Declared")
                        )
                        if presence
                        else request.env._("Not Declared"),
                        "declared": bool(
                            events.filtered(lambda e: e.kind == "declaration" and e.id > (invalidation.id or 0))
                        ),
                        "can_invalidate": bool(
                            events.filtered(lambda e: e.kind in ("declaration", "paper"))
                            and last.kind != "invalidation"
                            and enrollment.user_id != request.env.user
                        ),
                        "validated": presence.state == "validated" if presence else False,
                        "history": [
                            {
                                "kind": dict(e._fields["kind"]._description_selection(request.env))[e.kind],
                                "date": format_datetime(request.env, e.occurred_at, tz=tz),
                                "actor": e.actor_id.name,
                                "anomaly": e.anomaly,
                                "reason": e.reason,
                            }
                            for e in events
                        ],
                    }
                )
        return rows
