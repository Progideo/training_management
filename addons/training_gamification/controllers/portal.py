from odoo import http
from odoo.addons.training_management.controllers.courses_home import TrainingAccountCards
from odoo.http import request


class TrainingProgressPortal(http.Controller):
    @http.route("/my/training-progress", type="http", auth="user", website=True, methods=["GET", "POST"])
    def progress(self, **post):
        user = request.env.user
        saved = False
        if request.httprequest.method == "POST" and post.get("operation") in ("publish", "unpublish"):
            # Publication of one's own profile only: a choice left to each participant.
            if "website_published" in user._fields:
                user.sudo().website_published = post["operation"] == "publish"
                saved = True
        values = request.env["training.gamification.service"]._progress_values(user)
        response = request.render("training_gamification.portal_training_progress", {**values, "saved": saved})
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @http.route("/my/training-progress/badge/<int:badge_id>", type="http", auth="user", methods=["GET"])
    def badge_image(self, badge_id, **kwargs):
        """Image of a badge the user holds: portal users cannot read badges directly."""
        holding = (
            request.env["gamification.badge.user"]
            .sudo()
            .search_count([("user_id", "=", request.env.uid), ("badge_id", "=", badge_id)], limit=1)
        )
        if not holding:
            raise request.not_found()
        badge = request.env["gamification.badge"].sudo().browse(badge_id)
        stream = request.env["ir.binary"]._get_image_stream_from(badge, "image_128")
        response = stream.get_response()
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response


class TrainingProgressCard(TrainingAccountCards):
    def _prepare_portal_counter_values(self, counter):
        if counter == "training_progress_count":
            learning = request.env["training.learning.service"]
            shown = bool(request.env["training.document.policy"]._enrollments().filtered(learning._is_participant))
            return "res.users", [("id", "=", request.env.uid if shown else 0)], "sudo"
        return super()._prepare_portal_counter_values(counter)
