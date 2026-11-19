"""Website forms for pending inter-company enrollment requests."""

from uuid import uuid4

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import format_datetime

from odoo.addons.training_management.controllers.material_portal import TrainingParticipantPortal

from .public_request import TrainingCommercialCatalogue

FORM_FIELDS = ("contact", "email", "phone", "organisation", "count")


class TrainingSessionRegistration(TrainingCommercialCatalogue):
    @staticmethod
    def _local_hour(env, value, zone):
        # Wall-clock hour in the session time zone, written "9 h" or "9 h 30".
        local = format_datetime(env, value, tz=zone, dt_format="H:mm")
        hour, minute = local.split(":")
        return f"{hour} h" if minute == "00" else f"{hour} h {minute}"

    @classmethod
    def _session_schedule(cls, env, delivery):
        """Public dates and daily hours, in the session's own time zone, without UTC offset."""
        zone = delivery.timezone
        start = format_datetime(env, delivery.start_at, tz=zone, dt_format="y-MM-dd")
        end = format_datetime(env, delivery.end_at, tz=zone, dt_format="y-MM-dd")
        if start == end:
            dates = format_datetime(env, delivery.start_at, tz=zone, dt_format="d MMMM y")
        elif start[:7] == end[:7]:
            dates = "%s – %s" % (
                format_datetime(env, delivery.start_at, tz=zone, dt_format="d"),
                format_datetime(env, delivery.end_at, tz=zone, dt_format="d MMMM y"),
            )
        elif start[:4] == end[:4]:
            dates = "%s – %s" % (
                format_datetime(env, delivery.start_at, tz=zone, dt_format="d MMMM"),
                format_datetime(env, delivery.end_at, tz=zone, dt_format="d MMMM y"),
            )
        else:
            dates = "%s – %s" % (
                format_datetime(env, delivery.start_at, tz=zone, dt_format="d MMMM y"),
                format_datetime(env, delivery.end_at, tz=zone, dt_format="d MMMM y"),
            )
        sittings = delivery.session_ids.filtered(lambda session: not session.cancelled).sorted("start_at")
        first = sittings[:1]
        hours = (
            "%s – %s" % (cls._local_hour(env, first.start_at, zone), cls._local_hour(env, first.end_at, zone))
            if first and first.start_at and first.end_at
            else ""
        )
        return dates, hours, sittings

    @classmethod
    def _session_card(cls, delivery):
        program = delivery.program_id
        env = request.env
        dates, hours, sittings = cls._session_schedule(env, delivery)
        public = delivery._session_public_row() or {}
        # The public mode is the one of the scheduled sittings, not the programme default.
        # Sitting locations stay private: they may hold practical access instructions.
        modes = set(sittings.mapped("mode"))
        if len(modes) == 1:
            mode = dict(sittings._fields["mode"]._description_selection(delivery.env))[modes.pop()]
        elif modes:
            mode = dict(sittings._fields["mode"]._description_selection(delivery.env))["blended"]
        else:
            mode = dict(program._fields["delivery_mode"]._description_selection(delivery.env))[program.delivery_mode]
        return {
            "url": f"/formations/catalogue/{program.course_id.id}/inscription/{delivery.id}",
            "dates": dates,
            "hours": hours,
            "mode": mode,
            "confirmed": delivery.state == "confirmed",
            "location": delivery.public_location or "",
            "seats_left": public.get("seats_left"),
            "few_seats": public.get("few_seats", False),
            "limit": delivery._public_registration_limit(),
        }

    @http.route()
    def course(self, course_id, **kwargs):
        response = super().course(course_id, **kwargs)
        rows = request.env["training.delivery"]._public_registration_sessions(self._company(), course_id)
        response.qcontext["public_sessions"] = [self._session_card(row) for row in rows]
        return response

    @http.route(
        "/formations/catalogue/<int:course_id>/inscription/<int:delivery_id>",
        type="http",
        auth="public",
        website=True,
        methods=["GET", "POST"],
    )
    def session_registration(self, course_id, delivery_id, **post):
        company = self._company()
        delivery = request.env["training.delivery"]._public_registration_sessions(company, course_id, delivery_id)
        if not delivery or not delivery._session_public_row():
            raise request.not_found()
        card = self._session_card(delivery)
        schedule = [
            company.id,
            course_id,
            delivery.id,
            delivery.program_id.id,
            delivery.timezone,
            fields.Datetime.to_string(delivery.start_at),
            fields.Datetime.to_string(delivery.end_at),
        ]
        tokens = dict(request.session.get("training_session_registration_tokens", {}))
        error = False
        if request.httprequest.method == "POST":
            token = post.get("submission_token", "")
            if tokens.get(token) != schedule:
                raise request.not_found()
            values = {name: post.get(name, "").strip() for name in FORM_FIELDS}
            try:
                with request.env.cr.savepoint():
                    request.env["crm.lead"]._submit_public_session_request(delivery, values, token)
                return TrainingParticipantPortal._private(request.render("training_management_sale.request_received"))
            except ValidationError as exc:
                error = str(exc)
        else:
            if not card["limit"]:
                raise request.not_found()
            token = uuid4().hex
            tokens[token] = schedule
            request.session["training_session_registration_tokens"] = dict(list(tokens.items())[-20:])
            values = dict.fromkeys(FORM_FIELDS, "")
            values["count"] = "1"
        return TrainingParticipantPortal._private(
            request.render(
                "training_management_sale.public_session_registration",
                {
                    "course_id": course_id,
                    "title": delivery.program_id.course_id.name,
                    "session": card,
                    "values": values,
                    "token": token,
                    "error": error,
                },
            )
        )
