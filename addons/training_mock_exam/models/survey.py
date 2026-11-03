"""Native Survey identities, versions and fixed-question policy shared by both modes."""

import math
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

AUTHOR = "training_mock_exam.group_mock_exam_author"


class SharedSurvey(models.Model):
    _inherit = "survey.survey"

    training_course_id = fields.Many2one("training.course", ondelete="restrict", copy=True)
    mock_company_id = fields.Many2one(related="training_course_id.company_id", store=True)
    training_state = fields.Selection([("draft", "Draft"), ("published", "Published")], default="draft", copy=False)
    training_origin_id = fields.Many2one("survey.survey", ondelete="restrict", copy=False)
    training_version = fields.Char(default="1", copy=False)
    training_revision_reason = fields.Text(copy=False)

    _mock_version_unique = models.UniqueIndex(
        "(COALESCE(training_origin_id, id), training_version) WHERE training_course_id IS NOT NULL AND training_version IS NOT NULL",
        "This version reference already exists in the exam family.",
    )

    @api.private
    def _mock_definition_allowed(self):
        self.ensure_one()
        return bool(self.training_course_id)

    @api.private
    def _mock_definition_edit(self):
        self._mock_edit()

    @api.private
    def _mock_editor(self):
        if not self.env.su and (not self.env.user.active or not self.env.user.has_group(AUTHOR)):
            raise AccessError(self.env._("Mock exam author permission required."))
        self.check_access("write")

    @api.private
    def _mock_edit(self):
        exams = self.filtered("training_course_id")
        if exams:
            exams._mock_editor()
            exams.lock_for_update()
            exams.invalidate_recordset()
            if any(exam.training_state == "published" for exam in exams):
                raise ValidationError(self.env._("Published exams are immutable. Create a new version."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            course_id = vals.get("training_course_id") or self.env.context.get("default_training_course_id")
            if not course_id:
                continue
            self._mock_editor()
            course = self.env["training.course"].browse(course_id)
            course.check_access("read")
            course.lock_for_update()
            course.invalidate_recordset()
            if course.company_id not in self.env.companies:
                raise AccessError(self.env._("Use a course in your active companies."))
            if vals.get("training_state", self.env.context.get("default_training_state", "draft")) != "draft":
                raise AccessError(self.env._("Publish through the checked action."))
            origin = self.browse(vals.get("training_origin_id") or self.env.context.get("default_training_origin_id"))
            if origin:
                origin.check_access("read")
                if (
                    origin.training_course_id != course
                    or origin.training_origin_id
                    or origin.training_state != "published"
                ):
                    raise ValidationError(self.env._("Use the published original from the same course."))
        return super().create(vals_list)

    def write(self, vals):
        marked = self.filtered("training_course_id")
        if "training_course_id" in vals:
            raise ValidationError(self.env._("Create a new exam instead of changing its course."))
        if marked:
            marked._mock_editor()
            if set(vals) != {"active"}:
                marked._mock_edit()
                if {"training_state", "training_origin_id"} & vals.keys():
                    raise ValidationError(self.env._("Keep the publication and version history unchanged."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _mock_keep_versions(self):
        self._mock_edit()

    @api.private
    def _mock_validate_fixed_questions(self, questions):
        for question in questions:
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

    def action_mock_publish(self):  # pylint: disable=super-method-mismatch  # checked publication transition
        self._mock_edit()
        self._mock_editor()
        for exam in self:
            if not exam.training_course_id or not (exam.training_version or "").strip():
                raise ValidationError(self.env._("Choose a course and version."))
            if exam.training_origin_id and not (exam.training_revision_reason or "").strip():
                raise ValidationError(self.env._("Explain the new version."))
            if not exam.question_ids or not math.isfinite(exam.time_limit) or exam.time_limit <= 0:
                raise ValidationError(self.env._("Use a positive duration and at least one question."))
            exam.question_ids._validate_interaction()
            exam._mock_validate_fixed_questions(exam.question_ids)
        return super(SharedSurvey, self).write(  # pylint: disable=super-method-mismatch  # checked publication only
            {
                "training_state": "published",
                "questions_selection": "all",
                "questions_layout": "one_page",
                "survey_type": "custom",
                "scoring_type": "scoring_with_answers",
                "is_attempts_limited": False,
                "is_time_limited": True,
                "users_login_required": True,
                "access_mode": "token",
                "certification": False,
                "certification_give_badge": False,
                "users_can_go_back": True,
            }
        )

    def action_mock_new_version(self):
        self.ensure_one()
        self._mock_editor()
        self.lock_for_update()
        if not self.training_course_id or self.training_state != "published":
            raise ValidationError(self.env._("Publish this version first."))
        new = self.copy(
            {
                "training_origin_id": (self.training_origin_id or self).id,
                "training_version": False,
                "training_revision_reason": False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "survey.survey",
            "res_id": new.id,
            "view_mode": "form",
            "view_id": self.env.ref("survey.survey_survey_view_form").id,
        }

    def copy(self, default=None):
        if self.training_course_id:
            self._mock_editor()
            default = {**(default or {}), "training_state": "draft"}
        return super().copy(default)

    def _create_answer(self, *args, **kwargs):
        if self.filtered("training_course_id"):
            raise AccessError(self.env._("Use an authorized learner context for this mock exam."))
        return super()._create_answer(*args, **kwargs)


class SharedQuestion(models.Model):
    _inherit = "survey.question"  # pylint: disable=consider-merging-classes-inherited  # native immutability and enriched editors are separate concerns

    training_course_id = fields.Many2one(related="survey_id.training_course_id")
    training_theme = fields.Char(string="Main Theme", translate=True)
    training_explanation = fields.Text(string="Final Explanation", translate=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.env["survey.survey"].browse(
            [
                v.get("survey_id") or self.env.context.get("default_survey_id")
                for v in vals_list
                if v.get("survey_id") or self.env.context.get("default_survey_id")
            ]
        )._mock_edit()
        return super().create(vals_list)

    def write(self, vals):
        self.survey_id._mock_edit()
        self.env["survey.survey"].browse(vals.get("survey_id"))._mock_edit()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _mock_keep_questions(self):
        self.survey_id._mock_edit()


class SharedChoice(models.Model):
    _inherit = "survey.question.answer"  # pylint: disable=consider-merging-classes-inherited  # native immutability and enriched editors are separate concerns

    @api.model_create_multi
    def create(self, vals_list):
        questions = self.env["survey.question"].browse(
            [
                v.get(field) or self.env.context.get("default_" + field)
                for v in vals_list
                for field in ("question_id", "matrix_question_id")
                if v.get(field) or self.env.context.get("default_" + field)
            ]
        )
        questions.survey_id._mock_edit()
        return super().create(vals_list)

    def write(self, vals):
        (self.question_id | self.matrix_question_id).survey_id._mock_edit()
        self.env["survey.question"].browse(
            [vals[k] for k in ("question_id", "matrix_question_id") if vals.get(k)]
        ).survey_id._mock_edit()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _mock_keep_choices(self):
        (self.question_id | self.matrix_question_id).survey_id._mock_edit()
