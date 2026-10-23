"""Plain authorized values only; no portal ORM access to evaluation evidence."""

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager

from .material_portal import TrainingParticipantPortal


class EvaluationPortal(http.Controller):
    @http.route(
        ["/my/training-evaluations", "/my/training-evaluations/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def evaluations(self, page=1, **kwargs):
        service = request.env["training.evaluation.service"]
        domain = service._visible_domain()
        model = request.env["training.evaluation.assignment"].sudo()
        pager = portal_pager(url="/my/training-evaluations", total=model.search_count(domain), page=page, step=40)
        rows = model.search(domain, offset=pager["offset"], limit=40)
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_evaluations",
                {
                    "rows": [
                        {
                            "id": row.id,
                            "name": row.name,
                            "purpose": row.purpose,
                            "state": service._state_label(row),
                            "scored": row.evaluation_id.scored,
                            "validated": row.state == "validated",
                            "due": row.due_at,
                            "has_score": row.result_available,
                            "score": row.score,
                        }
                        for row in rows
                    ],
                    "pager": pager,
                },
            )
        )

    @http.route(
        "/my/training-evaluations/<int:assignment_id>", type="http", auth="user", website=True, methods=["GET", "POST"]
    )
    def evaluation(self, assignment_id, **post):
        service = request.env["training.evaluation.service"]
        try:
            row = service._assignment(assignment_id)
            error = False
            if request.httprequest.method == "POST":
                try:
                    with request.env.cr.savepoint():
                        operation = post.get("operation")
                        if operation == "start":
                            service._start(row.id)
                        elif operation == "validate":
                            service._validate(
                                row.id,
                                revision=int(post["revision"]),
                                score=float(post["score"]) if post.get("score") else None,
                                conclusion=post.get("conclusion"),
                                source=post.get("source"),
                                reason=post.get("reason"),
                            )
                        elif operation == "reopen":
                            service._reopen(
                                row.id,
                                revision=int(post["revision"]),
                                reason=post.get("reason"),
                                due_at=post.get("due_at"),
                            )
                        elif operation in ("save", "submit"):
                            service._portal_answers(
                                row.id,
                                {
                                    key: request.httprequest.form.getlist(key)
                                    for key in request.httprequest.form
                                    if key.startswith("q_")
                                },
                                submit=operation == "submit",
                            )
                        else:
                            raise ValidationError(request.env._("Choose an evaluation action."))
                except (ValidationError, ValueError, KeyError) as exc:
                    error = str(exc)
                row = service._assignment(assignment_id)
            values = service._portal_values(row)
            values["error"] = error
            return TrainingParticipantPortal._private(request.render("training_management.portal_evaluation", values))
        except (AccessError, MissingError):
            raise request.not_found() from None
