"""Managed native definitions remain private and frozen through every file entry point."""

from odoo import api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain

NATIVE = ("survey.survey", "survey.question", "survey.question.answer", "survey.user_input", "survey.user_input.line")
AUTHOR = "training_mock_exam.group_mock_exam_author"


def exam_for(record):
    target = record.sudo()
    if target._name == "ir.attachment" and target.res_model in NATIVE:
        target = record.env[target.res_model].sudo().browse(target.res_id).exists()
    if target._name == "survey.survey":
        survey = target
    elif target._name == "survey.question.answer":
        survey = (target.question_id | target.matrix_question_id).survey_id
    elif target._name in NATIVE:
        survey = target.survey_id
    else:
        survey = record.env["survey.survey"]
    return survey.filtered("training_course_id").with_env(record.env)


def check_read(record):
    exam = exam_for(record)
    target_model = record.sudo().res_model if record._name == "ir.attachment" else record._name
    if exam and target_model in ("survey.user_input", "survey.user_input.line"):
        raise AccessError(record.env._("Learner evidence requires an authorized context."))
    if exam and (
        not record.env.user.active
        or not record.env.user.has_group(AUTHOR)
        or any(e.mock_company_id not in record.env.companies for e in exam.sudo())
    ):
        raise AccessError(record.env._("This private mock exam file is unavailable."))


class Binary(models.AbstractModel):
    _inherit = "ir.binary"

    def _find_record(self, xmlid=None, res_model="ir.attachment", res_id=None, access_token=None, field=None):
        record = super()._find_record(xmlid, res_model, res_id, access_token, field)
        check_read(record)
        return record

    def _get_stream_from(self, record, *args, **kwargs):
        check_read(record)
        return super()._get_stream_from(record, *args, **kwargs)


class Attachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def _access_domain(self, operation):
        domain = super()._access_domain(operation)
        if operation != "read":
            return domain
        blocked = Domain("training_course_id", "!=", False)
        if self.env.user.active and self.env.user.has_group(AUTHOR):
            blocked &= Domain("mock_company_id", "not in", self.env.companies.ids)
        exams = self.env["survey.survey"].sudo()._search(blocked, active_test=False)
        for model in NATIVE:
            scoped_exams = exams
            if model in ("survey.user_input", "survey.user_input.line"):
                # Definition authors never gain learner evidence through public files.
                scoped_exams = (
                    self.env["survey.survey"]
                    .sudo()
                    ._search(Domain("training_course_id", "!=", False), active_test=False)
                )
            if model == "survey.survey":
                records = exams
            else:
                parent = (
                    Domain("question_id.survey_id", "any!", exams)
                    | Domain("matrix_question_id.survey_id", "any!", exams)
                    if model == "survey.question.answer"
                    else Domain("survey_id", "any!", scoped_exams)
                )
                records = self.env[model].sudo()._search(parent, active_test=False)
            domain &= ~(Domain("res_model", "=", model) & Domain("res_id", "any!", records))
        return domain

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            exam = exam_for(self.new(self._add_missing_default_values(dict(vals))))
            if exam:
                exam._mock_edit()
                if (
                    vals.get("public")
                    or vals.get("access_token")
                    or vals.get("url")
                    or vals.get("type", "binary") != "binary"
                ):
                    raise ValidationError(self.env._("Keep mock exam files private."))
                vals["company_id"] = exam.mock_company_id.id
        return super().create(vals_list)

    def write(self, vals):
        for attachment in self:
            source = exam_for(attachment)
            target = exam_for(
                self.new(
                    {
                        "res_model": vals.get("res_model", attachment.sudo().res_model),
                        "res_id": vals.get("res_id", attachment.sudo().res_id),
                    }
                )
            )
            if source or target:
                (source | target)._mock_edit()
                if {
                    "res_model",
                    "res_id",
                    "res_field",
                    "public",
                    "access_token",
                    "url",
                    "type",
                    "company_id",
                } & vals.keys():
                    raise ValidationError(self.env._("Keep mock exam files private."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _mock_keep_files(self):
        for attachment in self:
            exam_for(attachment)._mock_edit()

    def copy_data(self, default=None):
        if any(exam_for(attachment) for attachment in self):
            raise ValidationError(self.env._("Import files into a new draft instead of copying private attachments."))
        return super().copy_data(default)

    def _to_http_stream(self):
        check_read(self)
        return super()._to_http_stream()


class Attempt(models.Model):
    _inherit = "survey.user_input"

    @api.model_create_multi
    def create(self, vals_list):
        surveys = self.env["survey.survey"].browse(
            [
                v.get("survey_id") or self.env.context.get("default_survey_id")
                for v in vals_list
                if v.get("survey_id") or self.env.context.get("default_survey_id")
            ]
        )
        if (
            surveys.sudo().filtered("training_course_id")
            or any(
                "default_" + field in self.env.context
                for field in ("mock_context_key", "training_family_id", "training_review_ids")
            )
            or any(
                any(field in vals for field in ("mock_context_key", "training_family_id", "training_review_ids"))
                for vals in vals_list
            )
        ):
            raise AccessError(self.env._("Use an authorized learner context for this mock exam."))
        return super().create(vals_list)

    @api.private
    def _training_create(self, values):
        return super().create(values)  # pylint: disable=super-method-mismatch  # private checked factory only

    @api.private
    def _training_store(self, values):
        return super().write(values)  # pylint: disable=super-method-mismatch  # private checked transition only

    def write(self, vals):
        if (
            self._mock_exam_records()
            or "mock_context_key" in vals
            or "training_family_id" in vals
            or "training_review_ids" in vals
        ):
            raise AccessError(self.env._("Exam evidence is generated by the server."))
        if self.survey_id.sudo().filtered("training_course_id") or self.env["survey.survey"].sudo().browse(
            vals.get("survey_id")
        ).filtered("training_course_id"):
            raise AccessError(self.env._("Use an authorized learner context for this mock exam."))
        return super().write(vals)


class AnswerLine(models.Model):
    _inherit = "survey.user_input.line"

    @api.model_create_multi
    def create(self, vals_list):
        questions = (
            self.env["survey.question"]
            .sudo()
            .browse(
                [
                    v.get("question_id") or self.env.context.get("default_question_id")
                    for v in vals_list
                    if v.get("question_id") or self.env.context.get("default_question_id")
                ]
            )
        )
        inputs = (
            self.env["survey.user_input"]
            .sudo()
            .browse(
                [
                    v.get("user_input_id") or self.env.context.get("default_user_input_id")
                    for v in vals_list
                    if v.get("user_input_id") or self.env.context.get("default_user_input_id")
                ]
            )
        )
        if questions.survey_id.filtered("training_course_id") and any(
            not attempt.mock_context_key or questions.survey_id != attempt.survey_id for attempt in inputs
        ):
            raise AccessError(self.env._("Use an authorized learner context for this mock exam."))
        if questions.survey_id.filtered("training_course_id") and not inputs:
            raise AccessError(self.env._("Use an authorized learner context for this mock exam."))
        return super().create(vals_list)

    def write(self, vals):
        surveys = self.sudo().survey_id | self.sudo().question_id.survey_id
        surveys |= self.env["survey.question"].sudo().browse(vals.get("question_id")).survey_id
        surveys |= self.env["survey.user_input"].sudo().browse(vals.get("user_input_id")).survey_id
        if surveys.filtered("training_course_id"):
            self._training_mutable(self.user_input_id)
            if {"question_id", "user_input_id", "survey_id"} & vals.keys():
                raise AccessError(self.env._("Keep native answer identities unchanged."))
        return super().write(vals)


class Course(models.Model):
    _inherit = "training.course"

    def write(self, vals):
        self.check_access("write")
        if "company_id" in vals:
            self.lock_for_update()
            self.invalidate_recordset()
            changed = self.filtered(lambda course: course.company_id.id != vals["company_id"])
            # Classification only: never reveal private exam details to catalogue editors.
            if changed and self.env["survey.survey"].sudo().with_context(active_test=False).search_count(
                [("training_course_id", "in", changed.ids)]
            ):
                raise ValidationError(self.env._("Keep the company of a course referenced by mock exams."))
        return super().write(vals)
