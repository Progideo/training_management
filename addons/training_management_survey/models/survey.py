"""Extend the native question editor. Published versions are the historical snapshot."""

import math

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

COORDINATOR = "training_management.group_training_coordinator"


class Survey(models.Model):
    _inherit = "survey.survey"  # pylint: disable=consider-merging-classes-inherited  # purpose-specific extensions live separately

    training_program_id = fields.Many2one("training.program.version", ondelete="restrict", copy=True)
    training_company_id = fields.Many2one(related="training_program_id.company_id", store=True)
    training_state = fields.Selection([("draft", "Draft"), ("published", "Published")], default="draft", copy=False)
    training_origin_id = fields.Many2one("survey.survey", ondelete="restrict", copy=False)
    training_version = fields.Char(default="1", copy=False)
    training_revision_reason = fields.Text(copy=False)

    @api.private
    def _training_editor(self):
        if not self.env.su and not self.env.user.has_group(COORDINATOR):
            raise AccessError(self.env._("Training coordination is required."))
        self.check_access("write")

    @api.private
    def _training_edit(self):
        exams = self.filtered("training_program_id")
        if exams:
            exams._training_editor()
            exams.lock_for_update()
            exams.invalidate_recordset()
            if any(e.training_state == "published" for e in exams):
                raise ValidationError(self.env._("Published exams are immutable. Create a new version."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(value for key, value in vals.items() if key.startswith("training_")):
                self._training_editor()
            origin_id = vals.get("training_origin_id") or self.env.context.get("default_training_origin_id")
            if origin_id:
                origin = self.browse(origin_id)
                origin.check_access("read")
                program_id = vals.get("training_program_id") or self.env.context.get("default_training_program_id")
                if origin.training_program_id.id != program_id:
                    raise ValidationError(self.env._("Use the published original exam from the same programme."))
            if vals.get("training_program_id") or self.env.context.get("default_training_program_id"):
                self._training_editor()
                if vals.get("training_state", self.env.context.get("default_training_state", "draft")) != "draft":
                    raise AccessError(self.env._("Publish exams through the checked action."))
        return super().create(vals_list)

    def write(self, vals):
        marked = self.filtered("training_program_id")
        if any(value for key, value in vals.items() if key.startswith("training_")):
            self._training_editor()
        if marked and set(vals) <= {"active"}:
            marked._training_editor()
            marked.lock_for_update()
            return super().write(vals)
        if marked or vals.get("training_program_id"):
            self._training_edit()
            if not marked:
                self._training_editor()
            if "training_state" in vals or "training_program_id" in vals or "training_origin_id" in vals:
                raise ValidationError(self.env._("Keep the exam programme and publication history unchanged."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _training_keep_versions(self):
        self._training_edit()

    def action_training_publish(self):
        self._training_edit()
        for exam in self:
            if not exam.training_program_id or not exam.training_version:
                raise ValidationError(self.env._("Choose a programme and version."))
            if exam.training_origin_id and not (exam.training_revision_reason or "").strip():
                raise ValidationError(self.env._("Explain the new version."))
            if exam.training_origin_id and (
                exam.training_origin_id.training_state != "published"
                or exam.training_origin_id.training_origin_id
                or exam.training_origin_id.training_program_id != exam.training_program_id
            ):
                raise ValidationError(self.env._("Use the published original exam from the same programme."))
            questions = exam.question_ids
            if not questions or (
                (not (exam.training_evaluation_id or exam.training_feedback_id) or exam.is_time_limited)
                and (not math.isfinite(exam.time_limit) or exam.time_limit <= 0)
            ):
                raise ValidationError(self.env._("Use a positive duration and at least one question."))
            if not 0 <= exam.scoring_success_min <= 100:
                raise ValidationError(self.env._("Use a threshold between 0 and 100."))
            if exam.training_feedback_id or (exam.training_evaluation_id and not exam.training_evaluation_id.scored):
                if any(
                    q.question_type not in ("simple_choice", "multiple_choice", "char_box", "text_box")
                    or q.triggering_answer_ids
                    or q.save_as_email
                    or q.save_as_nickname
                    for q in questions
                ):
                    raise ValidationError(self.env._("Use fixed, non-identifying choice or text questions."))
            for question in (
                questions
                if not exam.training_feedback_id
                and (not exam.training_evaluation_id or exam.training_evaluation_id.scored)
                else self.env["survey.question"]
            ):
                correct = question.suggested_answer_ids.filtered("is_correct")
                if (
                    question.question_type not in ("simple_choice", "multiple_choice")
                    or not correct
                    or len(question.suggested_answer_ids) < 2
                    or (question.question_type == "simple_choice" and len(correct) != 1)
                    or not math.isfinite(question.answer_score)
                    or question.answer_score <= 0
                    or question.comments_allowed
                    or question.triggering_answer_ids
                ):
                    raise ValidationError(
                        self.env._("Use fixed QCU/QCM questions, positive points and a valid correction.")
                    )
            # Use the native quiz configuration, without Certification or its effects.
            super(Survey, exam).write(  # pylint: disable=super-method-mismatch  # validated publication only
                {
                    "training_state": "published",
                    "questions_selection": "all",
                    "questions_layout": "one_page",
                    "survey_type": "custom",
                    "scoring_type": "scoring_with_answers"
                    if not exam.training_feedback_id
                    and (not exam.training_evaluation_id or exam.training_evaluation_id.scored)
                    else "no_scoring",
                    "is_attempts_limited": False,
                    "is_time_limited": True
                    if not (exam.training_evaluation_id or exam.training_feedback_id)
                    else exam.is_time_limited,
                    "users_login_required": True,
                    "access_mode": "token",
                    "certification": False,
                    "certification_give_badge": False,
                    "users_can_go_back": True,
                }
            )
        return True

    def action_training_new_version(self):
        self.ensure_one()
        self._training_editor()
        if self.training_state != "published":
            raise ValidationError(self.env._("Publish this version first."))
        if self.training_feedback_id:
            return self.training_feedback_id.action_new_version()
        if self.training_evaluation_id:
            return self.training_evaluation_id.action_new_version()
        new = self.copy({"training_origin_id": (self.training_origin_id or self).id, "training_version": False})
        return {"type": "ir.actions.act_window", "res_model": "survey.survey", "res_id": new.id, "view_mode": "form"}

    def copy(self, default=None):
        if self.training_program_id:
            self._training_editor()
            default = {**(default or {}), "training_state": "draft"}
        return super().copy(default)

    def _create_answer(self, *args, **kwargs):
        if self.training_program_id:
            raise AccessError(self.env._("Start this mock exam from your training space."))
        return super()._create_answer(*args, **kwargs)


class Question(models.Model):
    _inherit = "survey.question"

    training_program_id = fields.Many2one(related="survey_id.training_program_id")
    training_theme = fields.Char(string="Main Theme", translate=True)
    training_explanation = fields.Text(string="Final Explanation", translate=True)
    training_material_id = fields.Many2one("training.material", ondelete="restrict", string="Revision PDF")

    @api.model_create_multi
    def create(self, vals_list):
        if any(v for k, v in self.env.context.items() if k.startswith("default_training_")):
            self.env["survey.survey"]._training_editor()
        for vals in vals_list:
            if any(value for key, value in vals.items() if key.startswith("training_")):
                self.env["survey.survey"]._training_editor()
            material_id = vals.get("training_material_id") or self.env.context.get("default_training_material_id")
            if material_id:
                self.env["training.material"].browse(material_id).check_access("read")
        self.env["survey.survey"].browse(
            list(
                filter(None, [vals.get("survey_id") or self.env.context.get("default_survey_id") for vals in vals_list])
            )
        )._training_edit()
        return super().create(vals_list)

    def write(self, vals):
        if any(value for key, value in vals.items() if key.startswith("training_")):
            self.env["survey.survey"]._training_editor()
        if vals.get("training_material_id"):
            self.env["training.material"].browse(vals["training_material_id"]).check_access("read")
        if vals.get("survey_id"):
            target = self.env["survey.survey"].browse(vals["survey_id"])
            target.check_access("read")
            if target.sudo().orientation_company_id and any(q.survey_id != target for q in self):
                raise ValidationError(
                    self.env._("Create or duplicate questions in the diagnostic; do not move existing definitions.")
                )
        self.survey_id._training_edit()
        if vals.get("survey_id"):
            self.env["survey.survey"].browse(vals["survey_id"])._training_edit()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _training_keep_questions(self):
        self.survey_id._training_edit()


class Choice(models.Model):
    _inherit = "survey.question.answer"

    @api.model_create_multi
    def create(self, vals_list):
        self.env["survey.question"].browse(
            list(
                {
                    vals.get(field, self.env.context.get("default_" + field))
                    for vals in vals_list
                    for field in ("question_id", "matrix_question_id")
                    if vals.get(field, self.env.context.get("default_" + field))
                }
            )
        ).survey_id._training_edit()
        return super().create(vals_list)

    def write(self, vals):
        for field in ("question_id", "matrix_question_id"):
            if vals.get(field):
                target = self.env["survey.question"].browse(vals[field])
                target.check_access("read")
                if target.sudo().survey_id.orientation_company_id and any(choice[field] != target for choice in self):
                    raise ValidationError(
                        self.env._("Create or duplicate questions in the diagnostic; do not move existing definitions.")
                    )
        (self.question_id | self.matrix_question_id).survey_id._training_edit()
        if vals.get("matrix_question_id"):
            self.env["survey.question"].browse(vals["matrix_question_id"]).survey_id._training_edit()
        if vals.get("question_id"):
            self.env["survey.question"].browse(vals["question_id"]).survey_id._training_edit()
        return super().write(vals)

    @api.constrains("question_id", "matrix_question_id")
    def _check_orientation_choice_parent(self):
        for choice in self:
            if (
                choice.question_id
                and choice.matrix_question_id
                and (
                    choice.sudo().question_id.survey_id.orientation_company_id
                    or choice.sudo().matrix_question_id.survey_id.orientation_company_id
                )
            ):
                raise ValidationError(
                    self.env._("Create or duplicate questions in the diagnostic; do not move existing definitions.")
                )

    @api.ondelete(at_uninstall=False)
    def _training_keep_choices(self):
        (self.question_id | self.matrix_question_id).survey_id._training_edit()
