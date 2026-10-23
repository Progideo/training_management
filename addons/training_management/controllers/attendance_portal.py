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
                    service._declare(
                        enrollment.id,
                        int(post.get("session_id", 0)),
                        post.get("start"),
                        post.get("end"),
                        accepted=post.get("accepted") == "yes",
                        definition=post.get("definition"),
                    )
                    return TrainingParticipantPortal._private(request.redirect(request.httprequest.path))
                except (ValueError, ValidationError) as exc:
                    error = str(exc) if isinstance(exc, ValidationError) else request.env._("Choose a valid session.")
            sessions = enrollment.delivery_id.session_ids.filtered(lambda s: not s.cancelled)
            rows = self._rows(sessions, enrollment)
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
                    service._review(
                        session.id,
                        int(post.get("enrollment_id", 0)),
                        post.get("start"),
                        post.get("end"),
                        absent=post.get("absent") == "yes",
                        revision=int(post.get("revision", 0)),
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

    def _draft(self, rows, post, *, trainer):
        """Keep only visible input on the rejected person's authorized form."""
        for row in rows:
            key = "enrollment_id" if trainer else "session_id"
            if str(row[key]) == post.get(key):
                row.update(start=post.get("start", ""), end=post.get("end", ""))
                if trainer:
                    row.update(absent=post.get("absent") == "yes", reason=post.get("reason", ""))

    def _rows(self, sessions, enrollment):
        rows = []
        for session in sessions:
            presence = (
                request.env["training.attendance"]
                .sudo()
                .search([("session_id", "=", session.id), ("enrollment_id", "=", enrollment.id)], limit=1)
            )
            events = presence.event_ids.sorted("id")
            last = events[-1:]
            tz = request.env.user.tz or session.timezone
            # No collective sheet or privileged recordset is exposed to QWeb.
            rows.append(
                {
                    "session_id": session.id,
                    "enrollment_id": enrollment.id,
                    "name": session.name,
                    "participant": enrollment.participant_id.name,
                    "schedule": "%s → %s"
                    % (
                        format_datetime(request.env, session.start_at, tz=tz),
                        format_datetime(request.env, session.end_at, tz=tz),
                    ),
                    "timezone": tz,
                    "wording": session.attendance_wording,
                    "definition": request.env["training.attendance.service"]._definition(session),
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
                    "start": (last.start_at - session.start_at).total_seconds() / 60 if last and last.start_at else 0,
                    "end": (last.end_at - session.start_at).total_seconds() / 60
                    if last and last.end_at
                    else (session.end_at - session.start_at).total_seconds() / 60,
                    "duration": (session.end_at - session.start_at).total_seconds() / 60,
                    "declared": bool(events.filtered(lambda e: e.kind == "declaration")),
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
