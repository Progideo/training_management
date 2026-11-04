from odoo import http
from odoo.http import request
from odoo.http.stream import Stream
from odoo.addons.training_catalog.controllers.catalogue import TrainingCatalogue


class TrainingPublicCatalogue(TrainingCatalogue):
    @staticmethod
    def _company():
        website = request.env.website
        return website.company_id if website else request.env.company

    @classmethod
    def _programs(cls):
        # Publication is the explicit public grant. Only this fixed projection,
        # scoped to the website operator, uses sudo; never accept a caller domain.
        return (
            request.env["training.program.version"]
            .sudo()
            .search(
                [
                    ("state", "=", "published"),
                    ("public_catalogue", "=", True),
                    ("course_id.active", "=", True),
                    ("company_id", "=", cls._company().id),
                ]
            )
        )

    @classmethod
    def _program(cls, program_id):
        program = cls._programs().filtered(lambda p: p.id == program_id)
        if not program:
            raise request.not_found()
        return program

    @http.route("/formations/<int:program_id>", type="http", auth="public", website=True, methods=["GET"])
    def programme(self, program_id, **kwargs):
        program = self._program(program_id)
        return request.render(
            "training_management.public_programme",
            {
                "program": {
                    "id": program.id,
                    "course_id": program.course_id.id,
                    "title": program.title,
                    "version": program.version,
                    "duration": program.duration_hours,
                    "mode": dict(program._fields["delivery_mode"]._description_selection(program.env)).get(
                        program.delivery_mode
                    ),
                    "presentation": program.course_id.presentation or "",
                    "sections": program._public_general_sections(),
                }
            },
        )

    @http.route(
        ["/formations/<int:program_id>/pdf", "/formations/<int:program_id>/apercu.pdf"],
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def retired_public_file(self, program_id, **kwargs):
        # November 3 scope: detailed programmes and demonstrations stay private.
        # The original frozen PDF and authorized participant download are kept.
        raise request.not_found()

    @staticmethod
    def _pdf(raw, filename):
        # Shared response builder for already-authorized private company files.
        # No public programme route calls this helper.
        response = Stream(type="data", data=raw, mimetype="application/pdf", download_name=filename).get_response(
            as_attachment=True
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
