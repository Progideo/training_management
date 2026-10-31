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
        service = request.env["training.dashboard.service"]
        try:
            # Authorize before parsing filters, including on the error path.
            delivery = service._delivery(delivery_id)
            try:
                session_id = int(kwargs.get("session_id", 0))
            except (ValueError, TypeError):
                raise ValidationError(request.env._("Choose a valid scheduled session.")) from None
            try:
                values = service._dashboard(
                    delivery_id,
                    page=page,
                    state=kwargs.get("state", "all"),
                    session_id=session_id,
                    start=kwargs.get("start"),
                    end=kwargs.get("end"),
                    issue=kwargs.get("issue", "all"),
                )
            except ValidationError as error:
                # Keep the user's filters editable; do not display fabricated totals.
                values = {
                    "name": delivery.name,
                    "program": delivery.program_id.display_name,
                    "company": delivery.company_id.name,
                    "state": kwargs.get("state", "all"),
                    "session_id": session_id,
                    "start": kwargs.get("start", ""),
                    "end": kwargs.get("end", ""),
                    "issue": kwargs.get("issue", "all"),
                    "sessions": [{"id": row.id, "name": row.name} for row in service._sessions(delivery)],
                    "filter_error": str(error),
                }
            else:
                pager = portal_pager(
                    url="/my/training-dashboard/%s" % delivery_id,
                    total=values["population"],
                    page=page,
                    step=40,
                    url_args={k: kwargs[k] for k in ("state", "session_id", "start", "end", "issue") if k in kwargs},
                )
                values.update(pager=pager, filter_error=False)
            values.update(
                states=request.env["training.enrollment"]._fields["state"]._description_selection(request.env),
                issues=[
                    ("attendance", request.env._("Attendance to review")),
                    ("feedback", request.env._("Feedback expected")),
                    ("evaluation", request.env._("Evaluation to finish / validate")),
                    ("overdue", request.env._("Overdue")),
                ],
            )
            return TrainingParticipantPortal._private(
                request.render(
                    "training_management.portal_dashboard", values, status=400 if values["filter_error"] else 200
                )
            )
        except (AccessError, MissingError, ValidationError):
            raise request.not_found() from None
