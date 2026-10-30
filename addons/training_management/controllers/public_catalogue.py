import hashlib

from odoo import http
from odoo.http import request
from odoo.http.stream import Stream


class TrainingPublicCatalogue(http.Controller):
    @staticmethod
    def _company():
        return request.website.company_id if hasattr(request, "website") and request.website else request.env.company

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

    @http.route("/formations", type="http", auth="public", website=True, methods=["GET"])
    def catalogue(self, search="", category="", mode="", **kwargs):
        programs = self._programs()
        categories = sorted({(p.category_id.id, p.category_id.name) for p in programs if p.category_id})
        if search:
            programs = programs.filtered(lambda p: search.casefold() in (p.title + " " + (p.content or "")).casefold())
        if category:
            programs = programs.filtered(lambda p: str(p.category_id.id) == category)
        if mode:
            programs = programs.filtered(lambda p: p.delivery_mode == mode)
        return request.render(
            "training_management.public_catalogue",
            {
                "programs": [{"id": p.id, "title": p.title, "version": p.version} for p in programs],
                "categories": categories,
                "search": search,
                "category": category,
                "mode": mode,
            },
        )

    @http.route("/formations/<int:program_id>", type="http", auth="public", website=True, methods=["GET", "POST"])
    def programme(self, program_id, **post):
        program = self._program(program_id)
        questions = [
            {
                "id": q.id,
                "name": q.name,
                "choices": [("a", q.choice_a), ("b", q.choice_b)],
                "feedback": (
                    q.explanation
                    if post.get(str(q.id)) == q.correct_choice
                    else request.env._("Try again. ") + q.explanation
                )
                if request.httprequest.method == "POST" and post.get(str(q.id)) in ("a", "b")
                else False,
            }
            for q in program.preview_question_ids
        ]
        return request.render(
            "training_management.public_programme",
            {
                "program": {
                    "id": program.id,
                    "title": program.title,
                    "version": program.version,
                    "duration": program.duration_hours,
                    "mode": dict(program._fields["delivery_mode"]._description_selection(program.env)).get(
                        program.delivery_mode
                    ),
                    "sections": program._catalogue_sections(),
                    "preview": bool(program.preview_pdf),
                },
                "questions": questions,
            },
        )

    @http.route("/formations/<int:program_id>/pdf", type="http", auth="public", website=True, methods=["GET"])
    def programme_pdf(self, program_id, **kwargs):
        program = self._program(program_id)
        attachment = program.pdf_attachment_id
        # Do not grant generic attachment/token access. Serve only the preserved
        # bytes of this currently published version from this explicit route.
        if not attachment or hashlib.sha256(attachment.raw or b"").hexdigest() != program.pdf_sha256:
            raise request.not_found()
        return self._pdf(bytes(attachment.raw), "programme.pdf")

    @http.route("/formations/<int:program_id>/apercu.pdf", type="http", auth="public", website=True, methods=["GET"])
    def preview_pdf(self, program_id, **kwargs):
        program = self._program(program_id)
        if not program.preview_pdf:
            raise request.not_found()
        return self._pdf(program.preview_pdf.content, "apercu.pdf")

    @staticmethod
    def _pdf(raw, filename):
        response = Stream(type="data", data=raw, mimetype="application/pdf", download_name=filename).get_response(
            as_attachment=True
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
