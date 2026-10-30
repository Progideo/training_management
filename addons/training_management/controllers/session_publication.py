"""Public session scalars and own opt-in through native Odoo authentication."""

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools import format_datetime

from .public_catalogue import TrainingPublicCatalogue


class SessionPublicationPortal(http.Controller):
    @staticmethod
    def _private(response):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @http.route("/formations/<int:program_id>/sessions", type="http", auth="public", website=True, methods=["GET"])
    def sessions(self, program_id, **kwargs):
        program = TrainingPublicCatalogue._program(program_id)
        # Publication is the explicit grant. Never pass delivery records to QWeb.
        deliveries = (
            request.env["training.delivery"]
            .sudo()
            .search(
                [
                    ("program_id", "=", program.id),
                    ("company_id", "=", program.company_id.id),
                    ("session_public", "=", True),
                    ("session_sales_open", "=", True),
                ],
                order="start_at, id",
                limit=200,
            )
        )
        rows = []
        for delivery in deliveries:
            row = delivery._session_public_row()
            if row:
                rows.append(
                    {
                        **row,
                        "start": format_datetime(
                            request.env, row["start_at"], tz=row["timezone"], dt_format="d MMMM y HH:mm XXX"
                        ),
                        "end": format_datetime(
                            request.env, row["end_at"], tz=row["timezone"], dt_format="d MMMM y HH:mm XXX"
                        ),
                    }
                )
        return self._private(
            request.render(
                "training_management.public_session_dates",
                {
                    "program_id": program.id,
                    "title": program.title,
                    "mode": dict(program._fields["delivery_mode"]._description_selection(request.env)).get(
                        program.delivery_mode
                    ),
                    "rows": rows,
                },
            )
        )

    @http.route(
        "/formations/<int:program_id>/date-alert", type="http", auth="user", website=True, methods=["GET", "POST"]
    )
    def subscribe(self, program_id, **post):
        program = TrainingPublicCatalogue._program(program_id)
        model = request.env["training.session.alert.subscription"]
        error = False
        if request.httprequest.method == "POST":
            try:
                model._subscribe(program, accepted=post.get("accepted") == "yes", definition=post.get("definition"))
                return request.redirect("/my/training-date-alerts", code=303)
            except (AccessError, ValidationError) as exc:
                error = str(exc)
        policy = program.company_id.sudo().training_session_alert_retention_id
        response = self._private(
            request.render(
                "training_management.session_date_consent",
                {
                    "program_id": program.id,
                    "title": program.title,
                    "wording": model._wording(),
                    "definition": model._definition(program),
                    "policy": {"days": policy.duration_days} if policy and policy.approved_at else False,
                    "error": error,
                },
            )
        )
        if error:
            response.status_code = 400
        return response

    @http.route("/my/training-date-alerts", type="http", auth="user", website=True, methods=["GET"])
    def subscriptions(self, **kwargs):
        user = request.env.user
        # Owner equality only: no employer/partner hierarchy, no generic ORM grant.
        rows = (
            request.env["training.session.alert.subscription"]
            .sudo()
            .search(
                [("owner_id", "=", user.id), ("owner_partner_id", "=", user.partner_id.id)], order="id desc", limit=200
            )
        )
        public_programs = {
            (program.company_id.id, program.course_id.id): program.id
            for program in TrainingPublicCatalogue._programs().sorted("id")
        }
        return self._private(
            request.render(
                "training_management.session_date_subscriptions",
                {
                    "rows": [
                        {
                            "id": row.id,
                            "title": row.public_title,
                            "operator": row.company_id.name,
                            "active": row.active_consent,
                            "subscribe_url": (
                                "/formations/%s/date-alert" % public_programs[(row.company_id.id, row.course_id.id)]
                                if (row.company_id.id, row.course_id.id) in public_programs
                                else False
                            ),
                        }
                        for row in rows
                    ]
                },
            )
        )

    @http.route(
        "/my/training-date-alerts/<int:subscription_id>/unsubscribe",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def unsubscribe(self, subscription_id, **kwargs):
        try:
            row = request.env["training.session.alert.subscription"].sudo().browse(subscription_id).exists()
            if not row:
                raise request.not_found()
            row._unsubscribe()
        except (AccessError, MissingError):
            raise request.not_found() from None
        return request.redirect("/my/training-date-alerts", code=303)
