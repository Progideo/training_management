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
        company = TrainingPublicCatalogue._company()
        error = False
        keys = (
            "contact",
            "email",
            "organisation",
            "phone",
            "kind",
            "request_type",
            "program",
            "course",
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
        course_id = values.pop("course")
        course = request.env["training.course"]
        if course_id:
            if not course_id.isascii() or not course_id.isdecimal() or len(course_id) > 10:
                raise request.not_found()
            course = course._published_catalogue_course(company, int(course_id))
            if not course:
                raise request.not_found()
            values["course"] = course_id
            programs = programs.filtered(lambda program: program.course_id.id == course.id)
        if request.httprequest.method == "POST":
            token = post.get("submission_token", "")
            tokens = request.session.get("training_request_tokens", [])
            if token not in tokens:
                raise request.not_found()
            try:
                with request.env.cr.savepoint():
                    request.env["crm.lead"]._submit_public_request(
                        company,
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
            values["request_type"] = values["request_type"] or (
                "catalogue" if values["program"] or course else "custom"
            )
            values["count"] = values["count"] or "1"
            selected = programs.filtered(lambda program: str(program.id) == values["program"])
            if selected and not values["mode"]:
                values["mode"] = selected.delivery_mode
        return TrainingParticipantPortal._private(
            request.render(
                "training_management_sale.public_request",
                {
                    "values": values,
                    "course": {"id": course.id, "name": course.name} if course else False,
                    "error": error,
                    "token": token,
                    "programs": [{"id": p.id, "title": p.title, "version": p.version} for p in programs],
                    "currencies": request.env["res.currency"].sudo().search([]),
                    "countries": [(c.id, c.name) for c in request.env["res.country"].sudo().search([])],
                },
            )
        )


class TrainingCommercialCatalogue(TrainingPublicCatalogue):
    def _catalogue_options(self, kind="", **kwargs):
        options = super()._catalogue_options(**kwargs)
        options["kind"] = kind if kind in ("group", "individual") else ""
        return options

    @http.route()
    def course(self, course_id, **kwargs):
        response = super().course(course_id, **kwargs)
        response.qcontext["kind"] = kwargs.get("kind") if kwargs.get("kind") in ("group", "individual") else ""
        return response

    @http.route()
    def programme(self, program_id, **post):
        response = super().programme(program_id, **post)
        response.qcontext["kind"] = post.get("kind") if post.get("kind") in ("group", "individual") else ""
        return response
