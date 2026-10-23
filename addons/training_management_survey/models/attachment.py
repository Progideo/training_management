"""Native parent permissions do not enforce its immutable write method."""

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

from .binary import _training_exam


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def _access_domain(self, operation):
        domain = super()._access_domain(operation)
        if operation != "read":
            return domain
        # Native attachment permissions also accept public=True. Exclude files
        # whose private parent is forbidden, including pre-existing public files.
        blocked = Domain("training_program_id", "!=", False)
        if self.env.user.has_group("training_management.group_training_coordinator"):
            blocked &= Domain("training_company_id", "not in", self.env.companies.ids)
        exams = self.env["survey.survey"].sudo()._search(blocked, active_test=False)
        for model in (
            "survey.survey",
            "survey.question",
            "survey.question.answer",
            "survey.user_input",
            "survey.user_input.line",
        ):
            if model == "survey.survey":
                records = exams
            else:
                parent = (
                    Domain("question_id.survey_id", "any!", exams)
                    | Domain("matrix_question_id.survey_id", "any!", exams)
                    if model == "survey.question.answer"
                    else Domain("survey_id", "any!", exams)
                )
                records = self.env[model].sudo()._search(parent, active_test=False)
            domain &= ~(Domain("res_model", "=", model) & Domain("res_id", "any!", records))
        return domain

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            values = self._add_missing_default_values(dict(vals))
            exam = _training_exam(self.new(values))
            if exam:
                exam._training_edit()
                if (
                    values.get("public")
                    or values.get("access_token")
                    or values.get("url")
                    or values.get("type", "binary") != "binary"
                ):
                    raise ValidationError(self.env._("Private exam files cannot be detached, shared or copied."))
                vals["company_id"] = exam.training_company_id.id
        return super().create(vals_list)

    def write(self, vals):
        for attachment in self:
            exam = _training_exam(attachment)
            target = _training_exam(
                self.new(
                    {
                        "res_model": vals.get("res_model", attachment.sudo().res_model),
                        "res_id": vals.get("res_id", attachment.sudo().res_id),
                    }
                )
            )
            if exam or target:
                (exam | target)._training_edit()
                if set(vals) & {
                    "res_model",
                    "res_id",
                    "res_field",
                    "public",
                    "access_token",
                    "type",
                    "url",
                    "company_id",
                }:
                    raise ValidationError(self.env._("Private exam files cannot be detached, shared or copied."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _training_keep_files(self):
        for attachment in self:
            _training_exam(attachment)._training_edit()

    def copy_data(self, default=None):
        if any(_training_exam(attachment) for attachment in self):
            raise ValidationError(self.env._("Private exam files cannot be detached, shared or copied."))
        return super().copy_data(default)

    def _can_return_content(self, field_name=None, access_token=None):
        self.env["ir.binary"]._check_training_binary_access(self)
        return super()._can_return_content(field_name, access_token)

    def _to_http_stream(self):
        self.env["ir.binary"]._check_training_binary_access(self)
        return super()._to_http_stream()
