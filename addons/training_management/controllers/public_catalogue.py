from urllib.parse import urlencode

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

    @http.route()
    def course(self, course_id, **kwargs):
        response = super().course(course_id, **kwargs)
        if not getattr(response, "is_qweb", False):
            return response
        values = response.qcontext
        offered = [offer["program_id"] for offer in values["course"]["offers"] if offer.get("program_id")]
        programs = self._programs().filtered(lambda program: program.id in offered)
        # Details of the chosen version, else of the latest version led by a trainer.
        program = programs.filtered(lambda program: str(program.id) == kwargs.get("version"))
        if not program:
            ordered = [programs.browse(program_id) for program_id in offered]
            live = [program for program in ordered if program.delivery_mode != "elearning"]
            program = (live or ordered or [programs.browse()])[0]
        if not program:
            return response
        # Formats without a duration in days take the hours of their latest version.
        latest = {}
        for offered_program in (programs.browse(program_id) for program_id in offered):
            if offered_program.duration_hours:
                key = "autonomous" if offered_program.delivery_mode == "elearning" else "live"
                latest.setdefault(key, "%s h" % offered_program._public_duration_hours())
        self._complete_durations(
            values, {"inter": latest.get("live"), "intra": latest.get("live"), "autonomous": latest.get("autonomous")}
        )
        sections = program._public_page_sections()
        hours = program._public_duration_hours() if program.duration_hours else ""
        values.update(
            {
                "version_details": {
                    "id": program.id,
                    "title": program.title,
                    "version": program.version,
                    "hours": hours,
                    "mode": program._modes_label(),
                    "objectives": sections["objectives"],
                },
                "audience_sections": sections["audience"],
                "modality_sections": sections["modalities"],
                "programme_pdf_url": "/formations/%s/pdf" % program.id if program.pdf_attachment_id else False,
                # Only a count: the link to verified publications is shown when one exists.
                "publications_url": "/formations/%s/avis" % program.id
                if request.env["training.publication"]
                .sudo()
                .search_count(
                    [
                        ("program_id", "=", program.id),
                        ("company_id", "=", program.company_id.id),
                        ("state", "=", "published"),
                    ]
                )
                else False,
            }
        )
        if program.delivery_mode != "elearning":
            values["sessions_url"] = "/formations/%s/sessions" % program.id
            values["alert_url"] = "/formations/%s/date-alert" % program.id
        if program.duration_hours:
            whole = int(program.duration_hours)
            minutes = round((program.duration_hours - whole) * 60)
            values["course_schema"]["timeRequired"] = "PT%sH%s" % (whole, "%sM" % minutes if minutes else "")
        return response

    @http.route("/formations/<int:program_id>", type="http", auth="public", website=True, methods=["GET"])
    def programme(self, program_id, **kwargs):
        # A version is presented on its course page: one canonical address per course.
        program = self._program(program_id)
        course = program.course_id
        args = dict(request.httprequest.args)
        latest = request.env["training.course"]._catalogue_offers(self._company())
        if any(offer.get("program_id") == program.id for offer in latest):
            args["version"] = program.id
        path = self._course_path(course.id, course.name)
        return request.redirect(path + ("?" + urlencode(args) if args else ""), code=301)

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
