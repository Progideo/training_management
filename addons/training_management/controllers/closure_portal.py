from odoo import http
from odoo.http import request


class TrainingDocumentsPortal(http.Controller):
    @http.route("/my/training-documents", type="http", auth="user", website=True, methods=["GET"])
    def documents(self, **kwargs):
        user = request.env.user
        # Search only candidate authorization metadata. Each candidate is then
        # checked against the real user's company, identity and explicit grant.
        docs = (
            request.env["training.document"]
            .sudo()
            .search(
                [
                    ("company_id", "in", user.company_ids.ids),
                    "|",
                    ("dossier_id.enrollment_id.user_id", "=", user.id),
                    ("dossier_id.client_contact_ids", "in", user.partner_id.ids),
                ]
            )
        )
        policy = request.env["training.document.policy"]
        rows = [
            {"name": d.filename, "url": f"/web/content/training.document/{d.id}/data/{d.filename}?download=true"}
            for d in docs
            if policy._can_read(d)
        ]
        response = request.render("training_management.portal_documents", {"rows": rows})
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
