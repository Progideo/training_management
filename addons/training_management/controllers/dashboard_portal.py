"""Authenticated, non-cacheable dashboard with fresh server-side scope checks."""

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager

from .material_portal import TrainingParticipantPortal


class DashboardPortal(http.Controller):
    @http.route("/my/training-dashboard", type="http", auth="user", website=True, methods=["GET"])
    def deliveries(self, **kwargs):
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_dashboard_deliveries",
                {"deliveries": request.env["training.dashboard.service"]._deliveries()},
            )
        )

    @http.route(
        ["/my/training-dashboard/<int:delivery_id>", "/my/training-dashboard/<int:delivery_id>/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def dashboard(self, delivery_id, page=1, **kwargs):
        try:
            values = request.env["training.dashboard.service"]._dashboard(
                delivery_id,
                state=kwargs.get("state", "all"),
                session_id=int(kwargs.get("session_id", 0)),
                start=kwargs.get("start"),
                end=kwargs.get("end"),
                issue=kwargs.get("issue", "all"),
            )
            pager = portal_pager(
                url="/my/training-dashboard/%s" % delivery_id,
                total=values["population"],
                page=page,
                step=40,
                url_args={k: kwargs[k] for k in ("state", "session_id", "start", "end", "issue") if k in kwargs},
            )
            values["rows"] = values["rows"][pager["offset"] : pager["offset"] + 40]
            values.update(
                pager=pager,
                states=request.env["training.enrollment"]._fields["state"]._description_selection(request.env),
                issues=[
                    ("attendance", request.env._("Attendance to review")),
                    ("feedback", request.env._("Feedback expected")),
                    ("evaluation", request.env._("Evaluation to finish / validate")),
                    ("overdue", request.env._("Overdue")),
                ],
            )
            return TrainingParticipantPortal._private(request.render("training_management.portal_dashboard", values))
        except (AccessError, MissingError, ValueError, ValidationError):
            raise request.not_found() from None
