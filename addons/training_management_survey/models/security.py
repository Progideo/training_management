"""Apply the common preview/cache/mail boundary to private native exam files."""

from odoo import api, models
from odoo.exceptions import AccessError, ValidationError

from .binary import _training_exam


def private_source(record):
    target = record.sudo()
    if target._name in ("ir.attachment", "mail.message"):
        model = target.res_model if target._name == "ir.attachment" else target.model
        if model in (
            "survey.survey",
            "survey.question",
            "survey.question.answer",
            "survey.user_input",
            "survey.user_input.line",
        ):
            source_id = target.res_id
            target = record.env[model].sudo().browse(source_id).exists()
            if source_id and not target:
                raise AccessError(record.env._("This private training record is unavailable."))
    return target


def feedback_file(record):
    target = private_source(record)
    if target._name == "survey.user_input.line":
        target = target.user_input_id
    return target if target._name == "survey.user_input" and target.training_feedback_campaign_id else False


class SurveySecurityPolicy(models.AbstractModel):
    _inherit = "training.document.policy"

    @api.private
    def _document(self, record):
        response = feedback_file(record)
        if response:
            return response
        exam = _training_exam(private_source(record))
        return exam if exam else super()._document(record)

    @api.private
    def _is_pedagogical(self, document):
        return bool(feedback_file(document) or _training_exam(document)) or super()._is_pedagogical(document)

    @api.private
    def _restricted(self, document):
        return bool(feedback_file(document) or _training_exam(document)) or super()._restricted(document)

    @api.private
    def _can_read(self, record):
        if feedback_file(record):
            return False
        source = private_source(record)
        exam = _training_exam(source)
        if exam:
            return bool(
                self.env.user.active
                and self.env.user.has_group("training_management.group_training_coordinator")
                and exam.training_company_id in self.env.companies
                # Classification and coordinator membership never replace the
                # native parent rules, especially for S09 evaluation answers.
                and source.with_env(self.env(su=False)).has_access("read")
            )
        return super()._can_read(record)

    @api.private
    def _check_send(self, document, partners, **kwargs):
        if document and (feedback_file(document) or _training_exam(private_source(document))):
            raise ValidationError(self.env._("Do not distribute private exam or feedback files through email."))
        return super()._check_send(document, partners, **kwargs)


class SurveyExportScope(models.AbstractModel):
    _inherit = "base"

    @api.private
    def _training_export_records(self):
        if self._name in (
            "survey.survey",
            "survey.question",
            "survey.question.answer",
            "survey.user_input",
            "survey.user_input.line",
        ):
            return self.filtered(lambda row: bool(_training_exam(row)))
        return super()._training_export_records()

    @api.private
    def _training_export_company(self):
        exam = _training_exam(self)
        return exam.training_company_id if exam else super()._training_export_company()
