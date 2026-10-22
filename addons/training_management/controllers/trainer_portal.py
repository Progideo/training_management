from odoo import http
from odoo.http import request
from odoo.tools.misc import format_datetime


class TrainingTrainerPortal(http.Controller):
    @http.route("/my/training-sessions", type="http", auth="user", website=True, methods=["GET"])
    def sessions(self, **kwargs):
        return request.render("training_management.portal_trainer_sessions", {"sessions": self._authorized_sessions()})

    @http.route("/my/training-sessions/<int:session_id>", type="http", auth="user", website=True, methods=["GET"])
    def session(self, session_id, **kwargs):
        rows = self._authorized_sessions(session_id)
        if not rows:
            raise request.not_found()
        return request.render("training_management.portal_trainer_session", {"session": rows[0]})

    def _authorized_sessions(self, session_id=None):
        # Narrow elevation: match the authenticated partner and its allowed
        # companies before reading anything. Return a whitelist of plain values,
        # never a sudo recordset to a QWeb template. No token grants access.
        user = request.env.user
        domain = [
            ("instructor_id", "=", user.partner_id.id),
            ("company_id", "in", user.company_ids.ids),
            ("delivery_id.state", "in", ("confirmed", "ongoing")),
            ("cancelled", "=", False),
        ]
        if session_id is not None:
            domain.append(("id", "=", session_id))
        rows = []
        for session in request.env["training.session"].sudo().search(domain, limit=200):
            participants = []
            for enrollment in session.delivery_id.enrollment_ids.filtered(lambda item: item.state == "confirmed"):
                adaptation = (
                    request.env["training.adaptation"].sudo().search([("enrollment_id", "=", enrollment.id)], limit=1)
                )
                participants.append(
                    {
                        "name": enrollment.participant_id.name,
                        "summary": enrollment.instructor_summary,
                        "instruction": adaptation.instructor_instruction,
                    }
                )
            tz = user.tz or session.timezone
            rows.append(
                {
                    "id": session.id,
                    "name": session.name,
                    "delivery": session.delivery_id.name,
                    "start": format_datetime(request.env, session.start_at, tz=tz),
                    "end": format_datetime(request.env, session.end_at, tz=tz),
                    "timezone": tz,
                    "reference_timezone": session.timezone,
                    "location": session.location or session.room_id.name,
                    "meeting_url": session.meeting_url,
                    "equipment": session.equipment,
                    "participants": participants,
                }
            )
        return rows
