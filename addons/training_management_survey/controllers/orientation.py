from odoo import http
from odoo.http import request

from odoo.addons.training_management.controllers.material_portal import TrainingParticipantPortal
from odoo.addons.training_management.controllers.public_catalogue import TrainingPublicCatalogue


class TrainingOrientation(http.Controller):
    @staticmethod
    def _surveys():
        # Explicit publication grants only the fixed public projection, scoped to
        # the website operator. No visitor-controlled domain or raw record output.
        return (
            request.env["survey.survey"]
            .sudo()
            .search(
                [
                    ("orientation_company_id", "=", TrainingPublicCatalogue._company().id),
                    ("orientation_published", "=", True),
                    ("active", "=", True),
                ]
            )
        )

    @http.route("/formations/orientation", type="http", auth="public", website=True, methods=["GET"])
    def diagnostics(self, **kwargs):
        return TrainingParticipantPortal._private(
            request.render(
                "training_management_survey.orientation_list",
                {"diagnostics": [(s.id, s.title) for s in self._surveys()]},
            )
        )

    @http.route(
        "/formations/orientation/<int:survey_id>", type="http", auth="public", website=True, methods=["GET", "POST"]
    )
    def diagnostic(self, survey_id, **post):
        survey = self._surveys().filtered(lambda s: s.id == survey_id)
        if not survey:
            raise request.not_found()
        submitted = request.httprequest.method == "POST"
        answers = {key: value for key, value in post.items() if key != "csrf_token"} if submitted else {}
        # Reject duplicate parameters as well as foreign question/answer ids.
        duplicate = any(len(v) != 1 for _, v in request.httprequest.form.lists())
        result = survey._orientation_result(answers) if submitted and not duplicate else False
        response = TrainingParticipantPortal._private(
            request.render(
                "training_management_survey.orientation_form",
                {
                    "diagnostic": {"title": survey.title, "contact": survey.orientation_contact},
                    "questions": [
                        {"id": q.id, "title": q.title, "choices": [(a.id, a.value) for a in q.suggested_answer_ids]}
                        for q in survey.question_ids.sorted(lambda q: (q.sequence, q.id))
                    ],
                    "answers": answers,
                    "submitted": submitted,
                    "result": result,
                    "guided_request": "training_request_type" in request.env["crm.lead"]._fields
                    if "crm.lead" in request.env
                    else False,
                },
            )
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
