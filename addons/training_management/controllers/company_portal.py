from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.tools.misc import format_datetime

from .material_portal import TrainingParticipantPortal
from .portal_utils import portal_datetime
from .public_catalogue import TrainingPublicCatalogue


class TrainingCompanyPortal(http.Controller):
    @http.route("/my/company-trainings", type="http", auth="user", website=True, methods=["GET"])
    def company_trainings(self, **kwargs):
        service = request.env["training.company.service"]
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.company_trainings", {"rows": service._rows(), "requests": service._request_rows()}
            )
        )

    @staticmethod
    def _allocation(allocation_id):
        try:
            return request.env["training.company.service"]._allocation(allocation_id)
        except AccessError:
            raise request.not_found() from None

    @http.route(
        "/my/company-trainings/<int:allocation_id>", type="http", auth="user", website=True, methods=["GET", "POST"]
    )
    def company_training(self, allocation_id, **post):
        allocation = self._allocation(allocation_id)
        error = False
        if request.httprequest.method == "POST":
            try:
                with request.env.cr.savepoint():
                    request.env["training.company.service"]._nominate(
                        allocation_id, post.get("name"), post.get("email")
                    )
                return request.redirect(f"/my/company-trainings/{allocation_id}?saved=1#company-feedback")
            except ValidationError as exc:
                error = str(exc)
        delivery = allocation.delivery_id
        versions = (
            request.env["training.intra.version"]
            .sudo()
            .search(
                [
                    ("delivery_id", "=", delivery.id),
                    ("customer_id", "=", allocation.customer_id.commercial_partner_id.id),
                    ("state", "!=", "draft"),
                ]
            )
        )
        documents = (
            request.env["training.company.document"]
            .sudo()
            .search([("allocation_id", "=", allocation.id), ("released", "=", True)])
        )
        nominations = request.env["training.company.nomination"].sudo().search([("allocation_id", "=", allocation.id)])
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.company_training",
                {
                    "practice_summaries": request.env["training.practice.summary"]._client_rows(allocation),
                    "allocation_id": allocation.id,
                    "saved": post.get("saved") == "1",
                    "lot_quantity": allocation.quantity,
                    "lot_remaining": allocation.unnamed_seats,
                    "lot_deadline": portal_datetime(allocation.expires_at) if allocation.state == "reserved" else False,
                    "can_nominate": allocation._available()
                    and delivery.state not in ("closed", "cancelled", "delivered"),
                    "pending_nominations": len(nominations.filtered(lambda nomination: nomination.state == "proposed")),
                    "name": delivery.name,
                    "program": delivery.program_id.title,
                    "error": error,
                    "values": {"name": post.get("name", ""), "email": post.get("email", "")},
                    "participants": [
                        {
                            "name": e.participant_id.name,
                            "state": dict(e._fields["state"]._description_selection(request.env)).get(e.state),
                        }
                        for e in allocation.enrollment_ids
                    ],
                    "nominations": [
                        {
                            "name": n.name,
                            "state": dict(n._fields["state"]._description_selection(request.env)).get(n.state),
                        }
                        for n in nominations
                    ],
                    "sessions": [
                        {
                            "name": s.name,
                            "start": format_datetime(request.env, s.start_at, tz=s.timezone),
                            "end": format_datetime(request.env, s.end_at, tz=s.timezone),
                            "timezone": s.timezone,
                        }
                        for s in delivery.session_ids
                        if not s.cancelled
                    ],
                    "documents": [{"id": d.id, "name": d.name} for d in documents],
                    "versions": [
                        {
                            "id": v.id,
                            "version": v.version,
                            "program": v.program_id.display_name,
                            "objectives": v.objectives,
                            "cases": v.business_cases,
                            "instructions": v.instructions,
                            "state": v.state,
                            "pdf": bool(v.data),
                            "approved_at": str(v.approved_at or ""),
                            "contact": v.approved_contact_id.name,
                            "selected": delivery.intra_version_id == v,
                        }
                        for v in versions
                    ],
                },
            )
        )

    @http.route(
        "/my/company-trainings/<int:allocation_id>/documents/<int:document_id>",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def company_document(self, allocation_id, document_id, **kwargs):
        allocation = self._allocation(allocation_id)
        document = (
            request.env["training.company.document"]
            .sudo()
            .search([("id", "=", document_id), ("allocation_id", "=", allocation.id), ("released", "=", True)], limit=1)
        )
        if not document:
            raise request.not_found()
        return TrainingParticipantPortal._private(
            TrainingPublicCatalogue._pdf(document.data.content, document.filename)
        )

    def _version(self, allocation_id, version_id):
        allocation = self._allocation(allocation_id)
        version = (
            request.env["training.intra.version"]
            .sudo()
            .search(
                [
                    ("id", "=", version_id),
                    ("delivery_id", "=", allocation.delivery_id.id),
                    ("customer_id", "=", allocation.customer_id.commercial_partner_id.id),
                    ("state", "!=", "draft"),
                ],
                limit=1,
            )
        )
        if not version:
            raise request.not_found()
        return version

    @http.route(
        "/my/company-trainings/<int:allocation_id>/versions/<int:version_id>/pdf",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def intra_pdf(self, allocation_id, version_id, **kwargs):
        version = self._version(allocation_id, version_id)
        if not version.data:
            raise request.not_found()
        return TrainingParticipantPortal._private(TrainingPublicCatalogue._pdf(version.data.content, version.filename))

    @http.route(
        "/my/company-trainings/<int:allocation_id>/versions/<int:version_id>/approve",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def intra_approve(self, allocation_id, version_id, **post):
        version = self._version(allocation_id, version_id)
        # Exact current allocation/company/client grant has been checked above.
        version._approve(request.env.user, request.env.user.partner_id)
        return request.redirect(f"/my/company-trainings/{allocation_id}?saved=1#company-feedback")
