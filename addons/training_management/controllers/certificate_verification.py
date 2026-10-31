from odoo import http
from odoo.http import request


class TrainingCertificateVerification(http.Controller):
    @http.route(
        "/training/verify/<string:token>", type="http", auth="public", website=True, methods=["GET"], sitemap=False
    )
    def verify(self, token, **kwargs):
        values = request.env["training.certificate.verification"]._public_values(token)
        response = request.render("training_management.certificate_verification", {"certificate": values})
        response.status_code = 200 if values else 404
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
