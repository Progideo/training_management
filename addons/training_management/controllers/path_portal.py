"""Read-only path navigation in the native authenticated participant portal."""

from odoo import http
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.http import request

from .material_portal import TrainingParticipantPortal


class TrainingPathPortal(http.Controller):
    @http.route(
        ["/my/training-paths", "/my/training-paths/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def paths(self, page=1, **kwargs):
        rows = request.env["training.path.portal"]._rows()
        pager = portal_pager(url="/my/training-paths", total=len(rows), page=page, step=20)
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_training_paths",
                {"paths": rows[pager["offset"] : pager["offset"] + 20], "pager": pager},
            )
        )

    @http.route("/my/training-paths/<int:path_id>", type="http", auth="user", website=True, methods=["GET"])
    def path(self, path_id, **kwargs):
        rows = request.env["training.path.portal"]._rows(path_id)
        if not rows:
            raise request.not_found()
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_training_path",
                {"path": rows[0]},
            )
        )
