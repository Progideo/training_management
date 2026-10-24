"""No portal ORM rights, arbitrary assignees, attachment URLs or internal notes."""

from uuid import uuid4

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager

from .material_portal import TrainingParticipantPortal


class QualityPortal(http.Controller):
    @http.route(
        ["/my/training-complaints", "/my/training-complaints/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def complaints(self, page=1, **kwargs):
        service = request.env["training.quality.service"]
        domain = service._visible_domain()
        model = request.env["training.complaint"].sudo()
        pager = portal_pager(url="/my/training-complaints", total=model.search_count(domain), page=page, step=40)
        rows = model.search(domain, offset=pager["offset"], limit=40)
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_complaints", {"rows": [service._values(r) for r in rows], "pager": pager}
            )
        )

    @http.route("/my/training-complaints/new", type="http", auth="user", website=True, methods=["GET", "POST"])
    def new_complaint(self, **post):
        service = request.env["training.quality.service"]
        error = False
        if request.httprequest.method == "POST":
            try:
                with request.env.cr.savepoint():
                    row = service._receive(
                        int(post.get("enrollment_id", 0)),
                        post.get("submission_key"),
                        post.get("subject"),
                        post.get("description"),
                    )
                return request.redirect("/my/training-complaints/%s" % row.id, code=303)
            except (AccessError, MissingError):
                raise request.not_found()
            except (ValueError, ValidationError) as exc:
                error = (
                    str(exc) if isinstance(exc, ValidationError) else request.env._("Check your enrollment selection.")
                )
        enrollments = request.env["training.enrollment"].sudo().search(service._enrollment_domain())
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_complaint_new",
                {
                    "enrollments": [{"id": e.id, "name": e.delivery_id.name} for e in enrollments],
                    "error": error,
                    "key": post.get("submission_key") or str(uuid4()),
                    "form_values": post if error else {},
                },
            )
        )

    @http.route("/my/training-complaints/<int:complaint_id>", type="http", auth="user", website=True, methods=["GET"])
    def complaint(self, complaint_id, **kwargs):
        try:
            service = request.env["training.quality.service"]
            return TrainingParticipantPortal._private(
                request.render(
                    "training_management.portal_complaint", service._values(service._complaint(complaint_id))
                )
            )
        except (AccessError, MissingError):
            raise request.not_found()
