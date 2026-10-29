"""P11 uses authenticated Odoo forms; all elevated records remain private."""

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools.misc import format_date, format_datetime

from .material_portal import TrainingParticipantPortal


class PracticePortal(http.Controller):
    @http.route("/my/training-practice", type="http", auth="user", website=True, methods=["GET"])
    def plans(self, **kwargs):
        rows = request.env["training.practice.action"]._portal_rows()
        for row in rows:
            row["due"] = format_date(request.env, row["due"])
            for entry in row["entries"]:
                entry["date"] = format_datetime(request.env, entry["date"], tz=request.env.user.tz or "UTC")
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.practice_portal", {"rows": rows, "error": False, "draft": "", "draft_id": 0}
            )
        )

    @http.route("/my/training-practice/<int:action_id>", type="http", auth="user", website=True, methods=["POST"])
    def submit(self, action_id, **values):
        action = request.env["training.practice.action"].sudo().browse(action_id).exists()
        role = values.get("role")
        if not action or role not in ("participant", "trainer"):
            raise request.not_found()
        uploaded = request.httprequest.files.get("file")
        try:
            with request.env.cr.savepoint():
                action._submit(
                    role,
                    values.get("body", ""),
                    uploaded.read(20 * 1024 * 1024 + 1) if uploaded else b"",
                    uploaded.filename if uploaded else "",
                )
        except (AccessError, MissingError):
            raise request.not_found() from None
        except ValidationError as exc:
            response = self.plans()
            response.qcontext.update(error=str(exc), draft=values.get("body", ""), draft_id=action_id)
            response.status_code = 400
            return response
        return request.redirect("/my/training-practice", code=303)

    @http.route(
        "/my/training-practice/<int:action_id>/files/<int:entry_id>",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def file(self, action_id, entry_id, **kwargs):
        entry = request.env["training.practice.entry"].sudo().browse(entry_id).exists()
        if not entry or entry.action_id.id != action_id:
            raise request.not_found()
        try:
            request.env["training.document.policy"]._check_read(entry)
            stream = request.env["ir.binary"]._get_stream_from(entry, "data", filename=entry.filename)
        except (AccessError, MissingError):
            raise request.not_found() from None
        return TrainingParticipantPortal._private(stream.get_response(as_attachment=True))
