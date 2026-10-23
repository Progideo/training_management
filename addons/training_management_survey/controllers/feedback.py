"""Account-bound feedback: no invitation tokens and no individual anonymous status."""

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.training_management.controllers.material_portal import TrainingParticipantPortal


class FeedbackPortal(http.Controller):
    @http.route(
        ["/my/training-feedback", "/my/training-feedback/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def feedback_list(self, page=1, **kwargs):
        user = request.env.user
        candidates = (
            request.env["training.feedback.recipient"]
            .sudo()
            .search([("user_id", "=", user.id), ("company_id", "in", user.company_ids.ids)])
        )
        campaigns = candidates.filtered(lambda x: x._eligible()).campaign_id.filtered(lambda x: x.state != "draft")
        pager = portal_pager(url="/my/training-feedback", total=len(campaigns), page=page, step=40)
        rows = [
            {"id": x.id, "name": x.name, "due": x.due_at} for x in campaigns[pager["offset"] : pager["offset"] + 40]
        ]
        return TrainingParticipantPortal._private(
            request.render("training_management_survey.portal_feedback_list", {"rows": rows, "pager": pager})
        )

    @http.route(
        "/my/training-feedback/<int:campaign_id>", type="http", auth="user", website=True, methods=["GET", "POST"]
    )
    def feedback(self, campaign_id, **post):
        service = request.env["training.feedback.service"]
        try:
            campaign = service._campaign(campaign_id)
            form_values = request.httprequest.form.to_dict(flat=False) if request.httprequest.method == "POST" else {}
            saved_values, completed = service._own_answers(campaign)
            if request.httprequest.method != "POST":
                form_values = saved_values
            message = request.env._("Your feedback has already been received.") if completed else ""
            error = ""
            if request.httprequest.method == "POST":
                answers = {}
                for question in campaign.feedback_id.survey_id.question_ids:
                    value = form_values.get("q_%s" % question.id, [])
                    answers[question.id] = (
                        value
                        if question.question_type in ("simple_choice", "multiple_choice")
                        else (value[0] if value else "")
                    )
                role = "participant" if campaign.purpose in ("immediate", "delayed") else campaign.purpose
                try:
                    submit = post.get("operation") != "save"
                    service._submit(campaign_id, role, answers, submit=submit)
                    message = (
                        request.env._("Thank you. Your feedback has been received.")
                        if submit
                        else request.env._("Your draft has been saved.")
                    )
                    completed = submit
                    if submit:
                        form_values = {}
                except (ValidationError, ValueError) as exc:
                    error = str(exc) if isinstance(exc, ValidationError) else request.env._("Choose valid answers.")
            questions = [
                {
                    "id": q.id,
                    "title": q.title,
                    "type": q.question_type,
                    "required": q.constr_mandatory,
                    "choices": [{"id": c.id, "label": c.value_label} for c in q.suggested_answer_ids],
                }
                for q in campaign.feedback_id.survey_id.question_ids.sorted(lambda q: (q.sequence, q.id))
            ]
            now = fields.Datetime.now()
            values = {
                "campaign_id": campaign.id,
                "name": campaign.name,
                "version": campaign.feedback_id.version,
                "purpose": dict(campaign.feedback_id._fields["purpose"]._description_selection(request.env))[
                    campaign.purpose
                ],
                "criteria": campaign.feedback_id.criteria,
                "due": campaign.due_at,
                "anonymous": campaign.anonymous,
                "completed": completed,
                "available": campaign.state == "open" and campaign.opens_at <= now <= campaign.due_at,
                "questions": questions,
                "message": message,
                "error": error,
                "form_values": form_values,
            }
            return TrainingParticipantPortal._private(
                request.render("training_management_survey.portal_feedback", values)
            )
        except (AccessError, MissingError):
            raise request.not_found() from None

    @http.route(
        "/my/training-feedback/<int:campaign_id>/summary", type="http", auth="user", website=True, methods=["GET"]
    )
    def summary(self, campaign_id, **kwargs):
        try:
            service = request.env["training.feedback.service"]
            campaign = service._campaign(campaign_id, staff=True)
            summary = service._summary_text(campaign)
            snapshot = (
                campaign.snapshot
                if campaign.state == "closed" and not (campaign.snapshot or {}).get("insufficient")
                else None
            )
            return TrainingParticipantPortal._private(
                request.render(
                    "training_management_survey.portal_feedback_summary",
                    {
                        "name": campaign.name,
                        "summary": summary,
                        "snapshot": snapshot,
                        "named_details": service._named_details(campaign),
                    },
                )
            )
        except (AccessError, MissingError):
            raise request.not_found() from None
