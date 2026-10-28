"""Native authentication, CSRF and survey choice widgets; checked training grants."""

import json

from werkzeug.exceptions import BadRequest

from odoo import http, fields
from odoo.addons.survey.controllers.main import Survey
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.training_management.controllers.material_portal import TrainingParticipantPortal
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools.mimetypes import guess_mimetype


class NativeSurveyBoundary(Survey):
    def _fetch_from_access_token(self, survey_token, answer_token):
        survey, answer = super()._fetch_from_access_token(survey_token, answer_token)
        if survey.training_program_id or survey.orientation_company_id:
            raise request.not_found()
        return survey, answer

    @http.route()
    def survey_get_question_image(self, survey_token, answer_token, question_id, suggested_answer_id):
        survey = request.env["survey.survey"].sudo().search([("access_token", "=", survey_token)], limit=1)
        if survey.orientation_company_id:
            raise request.not_found()
        if not survey.training_program_id:
            return super().survey_get_question_image(survey_token, answer_token, question_id, suggested_answer_id)
        attempt = (
            request.env["survey.user_input"]
            .sudo()
            .search(
                [
                    ("access_token", "=", answer_token),
                    ("survey_id", "=", survey.id),
                    ("training_enrollment_id", "!=", False),
                ],
                limit=1,
            )
        )
        try:
            if not attempt:
                raise request.not_found()
            attempt = (
                request.env["training.evaluation.service"]._native_attempt(attempt.id)
                if attempt.training_evaluation_assignment_id
                else request.env["training.exam.service"]._attempt(attempt.id)
            )
            question = attempt.predefined_question_ids.filtered(lambda q: q.id == question_id)
            choice = question.suggested_answer_ids.filtered(lambda c: c.id == suggested_answer_id)
            if not choice or not choice.value_image:
                raise request.not_found()
            content = choice.value_image.content
            return TrainingParticipantPortal._private(
                request.make_response(
                    content,
                    headers=[
                        ("Content-Type", guess_mimetype(content, default="image/png")),
                        ("X-Content-Type-Options", "nosniff"),
                    ],
                )
            )
        except (AccessError, MissingError):
            raise request.not_found() from None

    @http.route()
    def survey_report(self, survey, answer_token=None, **post):
        if survey.sudo().training_program_id or survey.sudo().orientation_company_id:
            raise request.not_found()
        return super().survey_report(survey, answer_token=answer_token, **post)

    @http.route()
    def show_certification_pdf(self, survey, **kwargs):
        if survey.sudo().training_program_id or survey.sudo().orientation_company_id:
            raise request.not_found()
        return super().show_certification_pdf(survey, **kwargs)

    @http.route()
    def survey_get_certification_preview(self, survey, **kwargs):
        if survey.sudo().training_program_id or survey.sudo().orientation_company_id:
            raise request.not_found()
        return super().survey_get_certification_preview(survey, **kwargs)

    @http.route()
    def survey_get_certification(self, survey_id, **kwargs):
        if request.env["survey.survey"].sudo().browse(survey_id).exists().training_program_id:
            raise request.not_found()
        return super().survey_get_certification(survey_id, **kwargs)


class ExamPortal(http.Controller):
    @http.route(
        ["/my/training-exams", "/my/training-exams/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def history(self, page=1, **kwargs):
        user = request.env.user
        domain = [
            ("training_enrollment_id.user_id", "=", user.id),
            ("training_enrollment_id.participant_id", "=", user.partner_id.id),
            ("training_enrollment_id.company_id", "in", user.company_ids.ids),
            ("training_enrollment_id.access_state", "=", "active"),
            ("training_enrollment_id.state", "=", "confirmed"),
            ("training_evaluation_assignment_id", "=", False),
        ]
        model = request.env["survey.user_input"].sudo()
        pager = portal_pager(url="/my/training-exams", total=model.search_count(domain), page=page, step=40)
        attempts = model.search(domain, order="id desc", limit=40, offset=pager["offset"])
        return TrainingParticipantPortal._private(
            request.render(
                "training_management_survey.exam_history",
                {
                    "attempts": [{"id": a.id, "title": a.survey_id.title, "date": a.start_datetime} for a in attempts],
                    "pager": pager,
                },
            )
        )

    @http.route(
        "/my/trainings/<int:enrollment_id>/exams/<int:activity_id>",
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
    )
    def exam(self, enrollment_id, activity_id, **post):
        service = request.env["training.exam.service"]
        try:
            enrollment = service._enrollment(enrollment_id, history=True)
            activity = request.env["training.learning.activity"].sudo().browse(activity_id).exists()
            if not activity or activity.delivery_id != enrollment.delivery_id or not activity.training_exam_id:
                raise request.not_found()
            if request.httprequest.method == "POST":
                attempt = service._start(enrollment_id, activity_id)
                return request.redirect(f"/my/training-exams/{attempt.id}")
            attempts = (
                request.env["survey.user_input"]
                .sudo()
                .search(
                    [
                        ("training_enrollment_id", "=", enrollment.id),
                        ("survey_id", "=", activity.training_exam_id.id),
                    ],
                    order="id desc",
                )
            )
            values = {
                "title": activity.training_exam_id.title,
                "duration": activity.training_exam_id.time_limit,
                "can_start": bool(activity.training_exam_id.active)
                and enrollment._effective_state() == "active"
                and request.env["training.learning.service"]._available(enrollment, activity),
                "attempts": [{"id": a.id, "date": a.start_datetime, "done": a.state == "done"} for a in attempts],
                "has_active": any(a.state != "done" and a.deadline > fields.Datetime.now() for a in attempts),
                "back": f"/my/trainings/{enrollment.id}",
            }
            return TrainingParticipantPortal._private(request.render("training_management_survey.exam_start", values))
        except (AccessError, MissingError):
            raise request.not_found() from None
        except ValidationError as error:
            return TrainingParticipantPortal._private(request.make_response(str(error), status=400))

    @http.route("/my/training-exams/<int:attempt_id>", type="http", auth="user", website=True, methods=["GET"])
    def attempt(self, attempt_id, **kwargs):
        service = request.env["training.exam.service"]
        try:
            answer = service._attempt(attempt_id)
            exam = answer.survey_id
            values = {
                "answer": answer,
                "question": False,
                "page": False,
                "survey_data": False,
                "survey": exam,
                "scoring_display_correction": False,
                "survey_form_readonly": False,
                "use_half_col_lg": "",
                "letters": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "useKeySelection": False,
                "is_post_submit_question": False,
                "server_time": fields.Datetime.now(),
                "result": service._result(answer) if answer.state == "done" else False,
                "can_retake": answer.training_enrollment_id._effective_state() == "active" and exam.active,
                "back": f"/my/trainings/{answer.training_enrollment_id.id}/exams/{answer.training_activity_id.id}",
            }
            return TrainingParticipantPortal._private(request.render("training_management_survey.exam_attempt", values))
        except (AccessError, MissingError):
            raise request.not_found() from None

    @http.route("/my/training-exams/<int:attempt_id>/save", type="http", auth="user", methods=["POST"])
    def save(self, attempt_id, **post):
        try:
            kind = post.get("kind", "save")
            service = request.env["training.exam.service"]
            if kind == "submit":
                data = service._submit(attempt_id)
            elif kind == "save":
                choices = json.loads(post.get("choices", "[]"))
                if not isinstance(choices, list) or any(type(c) is not int for c in choices):
                    raise BadRequest()
                data = service._save(attempt_id, int(post["question"]), choices, post.get("marked") == "1")
            elif kind == "status":
                answer = service._attempt(attempt_id, mutate=True)
                data = {
                    "done": answer.state == "done",
                    "remaining": max(0, int((answer.deadline - fields.Datetime.now()).total_seconds())),
                }
            else:
                raise BadRequest()
            return TrainingParticipantPortal._private(request.make_json_response(data))
        except (AccessError, MissingError):
            raise request.not_found() from None
        except (ValueError, KeyError, ValidationError):
            raise BadRequest() from None
