"""Definition tokens never grant learner access without a checked context adapter."""

from odoo import http
from odoo.http import request
from odoo.addons.survey.controllers.main import Survey


class SharedSurveyBoundary(Survey):
    def _fetch_from_access_token(self, survey_token, answer_token):
        survey, answer = super()._fetch_from_access_token(survey_token, answer_token)
        if survey.training_course_id:
            raise request.not_found()
        return survey, answer

    @http.route()
    def survey_get_question_image(self, survey_token, answer_token, question_id, suggested_answer_id):
        survey = request.env["survey.survey"].sudo().search([("access_token", "=", survey_token)], limit=1)
        if survey.training_course_id:
            raise request.not_found()
        return super().survey_get_question_image(survey_token, answer_token, question_id, suggested_answer_id)

    @http.route()
    def survey_report(self, survey, answer_token=None, **post):
        if survey.sudo().training_course_id:
            raise request.not_found()
        return super().survey_report(survey, answer_token=answer_token, **post)

    @http.route()
    def show_certification_pdf(self, survey, **kwargs):
        if survey.sudo().training_course_id:
            raise request.not_found()
        return super().show_certification_pdf(survey, **kwargs)

    @http.route()
    def survey_get_certification_preview(self, survey, **kwargs):
        if survey.sudo().training_course_id:
            raise request.not_found()
        return super().survey_get_certification_preview(survey, **kwargs)

    @http.route()
    def survey_get_certification(self, survey_id, **kwargs):
        if request.env["survey.survey"].sudo().browse(survey_id).exists().training_course_id:
            raise request.not_found()
        return super().survey_get_certification(survey_id, **kwargs)
