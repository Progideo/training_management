from odoo import fields, http
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.http import request
from odoo.tools.misc import format_datetime

from .material_portal import TrainingParticipantPortal


class TrainingTrainerPortal(http.Controller):
    @http.route(
        ["/my/training-sessions", "/my/training-sessions/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def sessions(self, page=1, filterby="upcoming", **kwargs):
        filterby = filterby if filterby in ("upcoming", "past", "all") else "upcoming"
        domain = self._session_domain()
        if filterby != "all":
            domain.append(("end_at", ">=" if filterby == "upcoming" else "<", fields.Datetime.now()))
        # Both count and page use the same narrow, server-built authorization
        # domain. No unrestricted recordset is returned to the template.
        sessions = request.env["training.session"].sudo()
        pager = portal_pager(
            url="/my/training-sessions",
            total=sessions.search_count(domain),
            page=page,
            step=40,
            url_args={"filterby": filterby},
        )
        records = sessions.search(domain, limit=40, offset=pager["offset"])
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_trainer_sessions",
                {"sessions": self._session_rows(records), "pager": pager, "filterby": filterby},
            )
        )

    @http.route("/my/training-sessions/<int:session_id>", type="http", auth="user", website=True, methods=["GET"])
    def session(self, session_id, **kwargs):
        records = (
            request.env["training.session"].sudo().search(self._session_domain() + [("id", "=", session_id)], limit=1)
        )
        if not records:
            raise request.not_found()
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_trainer_session", {"session": self._session_rows(records, details=True)[0]}
            )
        )

    def _session_domain(self):
        user = request.env.user
        return [
            ("instructor_id", "=", user.partner_id.id),
            ("company_id", "in", user.company_ids.ids),
            ("delivery_id.state", "in", ("confirmed", "ongoing")),
            ("cancelled", "=", False),
        ]

    def _session_rows(self, sessions, details=False):
        # Whitelist plain values. Participant instructions are only fetched on
        # an individually authorized detail page, never for the entire list.
        user = request.env.user
        rows = []
        for session in sessions:
            participants = []
            if details:
                for enrollment in session.delivery_id.enrollment_ids.filtered(lambda item: item.state == "confirmed"):
                    adaptation = (
                        request.env["training.adaptation"]
                        .sudo()
                        .search([("enrollment_id", "=", enrollment.id)], limit=1)
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
                    "materials": TrainingParticipantPortal._material_rows(session.delivery_id) if details else [],
                }
            )
        return rows
