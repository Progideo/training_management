from odoo import http
from odoo.addons.mail.controllers.attachment import AttachmentController
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.web.controllers.binary import Binary
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.http.stream import content_disposition
from odoo.tools.misc import format_datetime


class TrainingParticipantPortal(http.Controller):
    @http.route(
        ["/my/trainings", "/my/trainings/page/<int:page>"], type="http", auth="user", website=True, methods=["GET"]
    )
    def trainings(self, page=1, **kwargs):
        enrollments = request.env["training.document.policy"]._enrollments()
        active = enrollments.filtered(lambda e: e._effective_state() == "active")
        pager = portal_pager(url="/my/trainings", total=len(active), page=page, step=40)
        rows = [
            {"id": e.id, "name": e.delivery_id.name, "programme": e.program_id.title}
            for e in active[pager["offset"] : pager["offset"] + 40]
        ]
        return self._private(
            request.render("training_management.portal_trainings", {"enrollments": rows, "pager": pager})
        )

    @http.route("/my/trainings/<int:enrollment_id>", type="http", auth="user", website=True, methods=["GET"])
    def training(self, enrollment_id, **kwargs):
        enrollment = request.env["training.document.policy"]._enrollments().filtered(lambda e: e.id == enrollment_id)
        if not enrollment or enrollment._effective_state() != "active":
            raise request.not_found()
        delivery = enrollment.delivery_id
        tz = request.env.user.tz or delivery.timezone
        sessions = [
            {
                "name": s.name,
                "start": format_datetime(request.env, s.start_at, tz=tz),
                "end": format_datetime(request.env, s.end_at, tz=tz),
                "location": s.location or s.room_id.name,
                "meeting_url": s.meeting_url,
                "timezone": tz,
                "reference_timezone": s.timezone,
            }
            for s in delivery.session_ids.filtered(lambda s: not s.cancelled).sorted("start_at")
        ]
        values = {
            "name": delivery.name,
            "programme": enrollment.program_id.title,
            "sessions": sessions,
            "programme_url": f"/web/content/{enrollment.program_id.pdf_attachment_id.id}?download=true"
            if enrollment.program_id.pdf_attachment_id
            else False,
            "materials": self._material_rows(delivery),
        }
        # Import lazily: the tutoring controller reuses the participant response
        # and privacy headers without copying its programme/schedule workflow.
        from .learning_portal import learning_values

        values["learning"] = learning_values(enrollment)
        return self._private(request.render("training_management.portal_training", values))

    @staticmethod
    def _material_rows(delivery):
        # Called only after an exact enrollment or trainer-session grant. No
        # privileged recordset is passed to QWeb or any caller-controlled domain.
        return [
            {
                "name": ref.material_id.name,
                "version": ref.material_id.version,
                "url": f"/web/content/training.material/{ref.material_id.id}/data?filename_field=filename&download=true",
            }
            for ref in delivery.sudo().material_assignment_ids
            if not ref.withdrawn and not ref.material_id.withdrawn and ref.material_id.frozen_at
        ]

    @staticmethod
    def _private(response):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers.add("Vary", "Cookie")
        return response


class TrainingPrivateBinary(Binary):
    def _private_training_response(self, response, xmlid, model, record_id, field, access_token):
        # Native controllers may set public/immutable caching *after* streaming.
        # Amend only the two protected pedagogical categories, after their native
        # identity/field resolution; conditional and range requests recheck grants.
        record = (
            request.env.ref(xmlid, raise_if_not_found=False)
            if xmlid
            else request.env[model].browse(record_id).exists()
            if model in request.env and record_id
            else False
        )
        if record:
            policy = request.env["training.document.policy"]
            document = policy._document(record)
            if policy._is_pedagogical(document):
                try:
                    policy._check_read(record)
                except (AccessError, MissingError):
                    raise request.not_found() from None
                if document._name in (
                    "training.learning.entry",
                    "training.attendance.event",
                    "training.attendance.edit",
                ):
                    response.headers["Content-Disposition"] = content_disposition(
                        document.sudo().filename or "download"
                    )
                return TrainingParticipantPortal._private(response)
        return response

    @http.route()
    def content_common(
        self,
        xmlid=None,
        model="ir.attachment",
        id=None,
        field="raw",
        filename=None,
        filename_field="name",
        mimetype=None,
        unique=False,
        download=False,
        access_token=None,
        nocache=False,
    ):
        response = super().content_common(
            xmlid, model, id, field, filename, filename_field, mimetype, unique, download, access_token, nocache
        )
        return self._private_training_response(response, xmlid, model, id and int(id), field, access_token)

    @http.route()
    def content_image(
        self,
        xmlid=None,
        model="ir.attachment",
        id=None,
        field="raw",
        filename_field="name",
        filename=None,
        mimetype=None,
        unique=False,
        download=False,
        width=0,
        height=0,
        crop=False,
        access_token=None,
        nocache=False,
    ):
        response = super().content_image(
            xmlid=xmlid,
            model=model,
            id=id,
            field=field,
            filename_field=filename_field,
            filename=filename,
            mimetype=mimetype,
            unique=unique,
            download=download,
            width=width,
            height=height,
            crop=crop,
            access_token=access_token,
            nocache=nocache,
        )
        return self._private_training_response(response, xmlid, model, id and int(id), field, access_token)


class TrainingPrivateAttachment(AttachmentController):
    def _render_text_attachment(self, attachment, head=False, unique=False):
        policy = request.env["training.document.policy"]
        policy._check_read(attachment)
        response = super()._render_text_attachment(attachment, head=head, unique=unique)
        return (
            TrainingParticipantPortal._private(response)
            if policy._is_pedagogical(policy._document(attachment))
            else response
        )

    def _make_zip(self, name, attachments):
        # Native ZIP already calls ir.binary for every file; keep those checks.
        response = super()._make_zip(name, attachments)
        policy = request.env["training.document.policy"]
        if any(policy._restricted(policy._document(attachment)) for attachment in attachments):
            return TrainingParticipantPortal._private(response)
        return response

    def _get_pdf_first_page_response(self, attachment):
        # Native ownership tokens bypass the parent's ACL and extract bytes
        # directly, without ir.binary. Recheck the current grant before extraction.
        policy = request.env["training.document.policy"]
        document = policy._document(attachment)
        if policy._is_pedagogical(document):
            try:
                policy._check_read(attachment)
            except (AccessError, MissingError):
                raise request.not_found() from None
            response = super()._get_pdf_first_page_response(attachment)
            policy._audit_file_read(attachment)
            return TrainingParticipantPortal._private(response)
        return super()._get_pdf_first_page_response(attachment)
