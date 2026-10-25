import uuid

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.training_management.controllers.public_catalogue import TrainingPublicCatalogue
from odoo.addons.training_management.controllers.material_portal import TrainingParticipantPortal


class TrainingPublicRequest(http.Controller):
    @http.route("/formations/demande", type="http", auth="public", website=True, methods=["GET", "POST"])
    def training_request(self, **post):
        programs = TrainingPublicCatalogue._programs()
        error = False
        keys = (
            "contact",
            "email",
            "organisation",
            "phone",
            "kind",
            "request_type",
            "program",
            "objectives",
            "level",
            "count",
            "country",
            "mode",
            "currency",
            "date_from",
            "date_to",
            "tools",
            "advice",
            "dates_flexible",
        )
        values = {k: post.get(k, "") for k in keys}
        if request.httprequest.method == "POST":
            token = post.get("submission_token", "")
            tokens = request.session.get("training_request_tokens", [])
            if token not in tokens:
                raise request.not_found()
            try:
                with request.env.cr.savepoint():
                    request.env["crm.lead"]._submit_public_request(
                        TrainingPublicCatalogue._company(),
                        values,
                        token,
                        request.httprequest.files.get("specification"),
                    )
                return TrainingParticipantPortal._private(
                    request.render("training_management_sale.request_received", {})
                )
            except ValidationError as exc:
                error = str(exc)
        else:
            token = uuid.uuid4().hex
            request.session["training_request_tokens"] = (request.session.get("training_request_tokens", []) + [token])[
                -20:
            ]
            values["kind"] = values["kind"] if values["kind"] in ("group", "individual") else "group"
            values["request_type"] = values["request_type"] or ("catalogue" if values["program"] else "custom")
            values["count"] = values["count"] or "1"
        return TrainingParticipantPortal._private(
            request.render(
                "training_management_sale.public_request",
                {
                    "values": values,
                    "error": error,
                    "token": token,
                    "programs": [{"id": p.id, "title": p.title, "version": p.version} for p in programs],
                    "countries": [(c.id, c.name) for c in request.env["res.country"].sudo().search([])],
                },
            )
        )


class TrainingCommercialCatalogue(TrainingPublicCatalogue):
    @http.route()
    def catalogue(self, search="", category="", mode="", **kwargs):
        response = super().catalogue(search=search, category=category, mode=mode, **kwargs)
        response.qcontext["kind"] = kwargs.get("kind") if kwargs.get("kind") in ("group", "individual") else ""
        return response

    @http.route()
    def programme(self, program_id, **post):
        response = super().programme(program_id, **post)
        response.qcontext["kind"] = post.get("kind") if post.get("kind") in ("group", "individual") else ""
        return response
