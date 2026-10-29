"""P14 scalar projections through existing Odoo authentication and QWeb."""

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request

from .material_portal import TrainingParticipantPortal
from .public_catalogue import TrainingPublicCatalogue


class PublicationPortal(http.Controller):
    @staticmethod
    def _owned(publication_id):
        row = request.env["training.publication"].sudo().browse(publication_id).exists()
        if not row:
            raise request.not_found()
        row._owner()
        return row

    @http.route("/my/training-publications", type="http", auth="user", website=True, methods=["GET"])
    def home(self, **kwargs):
        user = request.env.user
        # Exact current owner; no commercial-partner inheritance or follower grant.
        rows = (
            request.env["training.publication"]
            .sudo()
            .search(
                [
                    ("owner_id", "=", user.id),
                    ("owner_partner_id", "=", user.partner_id.id),
                    ("company_id", "in", user.company_ids.ids),
                ],
                limit=200,
            )
        )
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.publication_home",
                {
                    "rows": [
                        {
                            "id": r.id,
                            "context": r.public_context,
                            "state": dict(r._fields["state"]._description_selection(request.env))[r.state],
                        }
                        for r in rows
                    ],
                },
            )
        )

    @http.route(
        "/my/training-publications/<int:publication_id>", type="http", auth="user", website=True, methods=["GET"]
    )
    def detail(self, publication_id, error=False, form_body=None, **kwargs):
        try:
            row = self._owned(publication_id)
            can_consent = row.state == ("invited" if row.kind == "review" else "submitted")
            if can_consent:
                try:
                    row._owner(grant=True)
                except AccessError:
                    can_consent = False
            return TrainingParticipantPortal._private(
                request.render(
                    "training_management.publication_form",
                    {
                        "row": {
                            "id": row.id,
                            "kind": row.kind,
                            "body": row.body if form_body is None else form_body,
                            "context": row.public_context,
                            "month": row.participation_month,
                            "state": dict(row._fields["state"]._description_selection(request.env))[row.state],
                            "name": row.owner_partner_id.name if row.kind == "review" else row.public_identity,
                            "terms": row.consent_wording,
                            "definition": row._definition(),
                            "identify_client": row.identify_client,
                            "can_consent": can_consent,
                            "can_withdraw": row.state != "withdrawn",
                        },
                        "error": error,
                    },
                )
            )
        except (AccessError, MissingError):
            raise request.not_found() from None

    @http.route(
        "/my/training-publications/<int:publication_id>", type="http", auth="user", website=True, methods=["POST"]
    )
    def operate(self, publication_id, **values):
        try:
            with request.env.cr.savepoint():
                row = self._owned(publication_id)
                if values.get("operation") == "withdraw":
                    row._withdraw()
                elif values.get("operation") == "consent":
                    row._consent(
                        definition=values.get("definition"),
                        body=values.get("body", ""),
                        identity=values.get("identity", "anonymous"),
                        accepted=values.get("accepted") == "yes",
                        identity_accepted=values.get("identity_accepted") == "yes",
                    )
                else:
                    raise request.not_found()
        except (AccessError, MissingError):
            raise request.not_found() from None
        except ValidationError as exc:
            response = self.detail(publication_id, error=str(exc), form_body=values.get("body"))
            response.status_code = 400
            return response
        return request.redirect("/my/training-publications/%s" % publication_id, code=303)

    @http.route("/formations/<int:program_id>/avis", type="http", auth="public", website=True, methods=["GET"])
    def published(self, program_id, **kwargs):
        program = TrainingPublicCatalogue._program(program_id)
        # Currently public programme in the website operator's company. A fixed
        # allowlist of scalars only; no privileged records, identities from S09,
        # source ids, customer dossiers or private consent evidence reach QWeb.
        rows = (
            request.env["training.publication"]
            .sudo()
            .search(
                [
                    ("program_id", "=", program.id),
                    ("company_id", "=", program.company_id.id),
                    ("state", "=", "published"),
                ],
                order="published_at desc, id desc",
                limit=200,
            )
        )
        response = request.render(
            "training_management.publication_public",
            {
                "title": program.title,
                "program_id": program.id,
                "rows": [value for row in rows if (value := row._public_row())],
            },
        )
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
