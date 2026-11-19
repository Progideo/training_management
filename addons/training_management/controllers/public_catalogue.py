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
        course = program.course_id
        return request.render(
            "training_management.public_programme",
            {
                "program": {
                    "id": program.id,
                    "course_id": course.id,
                    "title": program.title,
                    "version": program.version,
                    "duration": program._public_duration_hours(),
                    "autonomous": program.delivery_mode == "elearning",
                    "mode": dict(program._fields["delivery_mode"]._description_selection(program.env)).get(
                        program.delivery_mode
                    ),
                    "presentation": course.presentation or "",
                    "pdf": bool(program.pdf_attachment_id),
                    "tags": course._catalogue_tags()[course.id],
                    "sections": program._public_general_sections(),
                    # Only a count: the link to verified publications is shown when one exists.
                    "publications": request.env["training.publication"]
                    .sudo()
                    .search_count(
                        [
                            ("program_id", "=", program.id),
                            ("company_id", "=", program.company_id.id),
                            ("state", "=", "published"),
                        ]
                    ),
                }
            },
        )

    @http.route("/formations/<int:program_id>/pdf", type="http", auth="public", website=True, methods=["GET"])
    def public_programme_pdf(self, program_id, **kwargs):
        # Decision of 19 November 2026: the programme is public. Only the frozen
        # reference PDF of a currently published public version is served, as
        # stored at validation; the attachment itself stays private.
        program = self._program(program_id)
        attachment = program.pdf_attachment_id
        if not attachment:
            raise request.not_found()
        raw = bytes(attachment.raw or b"")
        if not raw.startswith(b"%PDF-"):
            raise request.not_found()
        return self._pdf(raw, attachment.name or "programme-%s.pdf" % program.id)

    @http.route("/formations/<int:program_id>/apercu.pdf", type="http", auth="public", website=True, methods=["GET"])
    def retired_public_file(self, program_id, **kwargs):
        # Demonstration extracts stay private (November 3 scope).
        raise request.not_found()

    @staticmethod
    def _pdf(raw, filename):
        # Shared response builder for already-authorized files: private company
        # files, and the frozen PDF of a currently published public programme.
        response = Stream(type="data", data=raw, mimetype="application/pdf", download_name=filename).get_response(
            as_attachment=True
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
