"""Plain authorized values only; no portal ORM access to evaluation evidence."""

from odoo import fields, http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager

from .material_portal import TrainingParticipantPortal
from .portal_utils import local_deadline, portal_datetime


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
                            "due": portal_datetime(row.due_at),
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
            operation = None
            if request.httprequest.method == "POST":
                try:
                    with request.env.cr.savepoint():
                        operation = post.get("operation")
                        if operation == "start":
                            service._participant_attempt(row.id, int(post["attempt_number"]))
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
                                due_at=local_deadline(post.get("due_at_local"), request.env.user.tz or "UTC")
                                if "due_at_local" in post
                                else post.get("due_at"),
                            )
                        elif operation in ("save", "submit"):
                            service._portal_answers(
                                row.id,
                                {
                                    key: request.httprequest.form.getlist(key)
                                    for key in request.httprequest.form
                                    if key.startswith("q_")
                                },
                                attempt_number=int(post["attempt_number"]),
                                submit=operation == "submit",
                            )
                        else:
                            raise ValidationError(request.env._("Choose an evaluation action."))
                except ValidationError as exc:
                    error = str(exc)
                except (ValueError, KeyError):
                    error = request.env._("Check the entered values and try again.")
                row = service._assignment(assignment_id)
            values = service._portal_values(row)
            values["error"] = error
            values["form_values"] = {}
            values["message"] = False
            if error:
                # Restore only the authorized current form, never another attempt.
                if (
                    operation in ("save", "submit")
                    and values["own"]
                    and not values["submitted"]
                    and post.get("attempt_number") == str(values["attempt_number"])
                ):
                    for question in values["questions"]:
                        answers = request.httprequest.form.getlist("q_%s" % question["id"])
                        for choice in question["choices"]:
                            choice["selected"] = str(choice["id"]) in answers
                        question["text"] = (answers[0] if answers else "")[:20000]
                if (
                    (operation == "validate" and values["can_evaluate"])
                    or (operation == "reopen" and values["can_reopen"])
                ) and post.get("revision") == str(values["revision"]):
                    values["form_values"] = {
                        key: post.get(key, "")
                        for key in ("score", "conclusion", "source", "reason", "due_at", "due_at_local")
                    }
            else:
                values["message"] = {
                    "start": request.env._("Evaluation started."),
                    "save": request.env._("Answers saved."),
                    "submit": request.env._("Answers submitted for pedagogical validation."),
                    "validate": request.env._("Evaluation result validated."),
                    "reopen": request.env._("A new attempt has been authorized."),
                }.get(operation)
                if operation in ("save", "submit") and values["submitted"] and values["due"] <= fields.Datetime.now():
                    values["message"] = request.env._(
                        "The deadline has passed. Only previously saved answers were submitted."
                    )
            values["timezone"] = request.env.user.tz or "UTC"
            values["due"] = portal_datetime(values["due"])
            for item in values["history"]:
                item["date"] = portal_datetime(item["date"])
            return TrainingParticipantPortal._private(request.render("training_management.portal_evaluation", values))
        except (AccessError, MissingError):
            raise request.not_found() from None
