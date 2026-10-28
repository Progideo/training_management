"""P10: native question definitions, deterministic advice, no persisted responses."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

COORDINATOR = "training_management.group_training_coordinator"


class OrientationSurvey(models.Model):
    _inherit = "survey.survey"  # pylint: disable=consider-merging-classes-inherited  # separate pre-purchase purpose

    orientation_company_id = fields.Many2one("res.company", copy=True)
    orientation_published = fields.Boolean(readonly=True, copy=False)
    orientation_revision = fields.Integer(default=0, readonly=True, copy=False)
    orientation_rule_ids = fields.One2many(
        "training.orientation.rule", "survey_id", string="Recommendations", copy=True
    )
    orientation_contact = fields.Char(string="Advice Contact", help="Public contact email or telephone.", copy=True)

    @api.private
    def _orientation_edit(self):  # pylint: disable=missing-return  # lock and fence only
        surveys = self.filtered("orientation_company_id")
        if surveys:
            surveys._training_editor()
            surveys.lock_for_update()
            surveys.invalidate_recordset()
            if any(s.orientation_published for s in surveys):
                raise ValidationError(self.env._("Keep published diagnostics unchanged; duplicate to revise."))
            # Fence concurrent child edits against publication in REPEATABLE READ.
            for survey in surveys:
                super(OrientationSurvey, survey).write({"orientation_revision": survey.orientation_revision + 1})  # pylint: disable=super-method-mismatch  # checked revision fence

    @api.private
    def _training_edit(self):
        self._orientation_edit()
        return super()._training_edit()

    @api.model_create_multi
    def create(self, vals_list):
        if any(
            v.get("orientation_published", self.env.context.get("default_orientation_published"))
            or v.get("orientation_revision", self.env.context.get("default_orientation_revision"))
            for v in vals_list
        ):
            raise ValidationError(self.env._("Publish diagnostics through the checked action."))
        if any(
            v.get("orientation_company_id", self.env.context.get("default_orientation_company_id")) for v in vals_list
        ):
            self._training_editor()
        return super().create(vals_list)

    def copy(self, default=None):
        self.ensure_one()
        if not self.orientation_company_id:
            return super().copy(default)
        self._training_editor()
        new = super().copy({**(default or {}), "orientation_rule_ids": False})
        source_questions = self.question_and_page_ids.sorted(lambda q: (q.sequence, q.id))
        new_questions = new.question_and_page_ids.sorted(lambda q: (q.sequence, q.id))
        answer_map = {}
        for source, target in zip(source_questions, new_questions, strict=True):
            answer_map.update(
                zip(
                    source.suggested_answer_ids.sorted(lambda a: (a.sequence, a.id)).ids,
                    target.suggested_answer_ids.sorted(lambda a: (a.sequence, a.id)).ids,
                    strict=True,
                )
            )
        for rule in self.orientation_rule_ids:
            rule.copy({"survey_id": new.id, "answer_ids": [(6, 0, [answer_map[a.id] for a in rule.answer_ids])]})
        return new

    def write(self, vals):
        if {"orientation_published", "orientation_revision"} & vals.keys():
            raise ValidationError(self.env._("Publish diagnostics through the checked action."))
        marked = self.filtered("orientation_company_id")
        if "orientation_company_id" in vals and marked:
            raise ValidationError(self.env._("Keep the diagnostic company unchanged."))
        if vals.get("orientation_company_id"):
            raise ValidationError(self.env._("Create a new diagnostic instead of converting an existing survey."))
        if marked:
            if set(vals) == {"active"}:
                marked._training_editor()
                marked.lock_for_update()
            else:
                marked._orientation_edit()
        return super().write(vals)

    @api.constrains("orientation_company_id", "training_program_id")
    def _check_orientation_kind(self):
        if any(s.orientation_company_id and s.training_program_id for s in self):
            raise ValidationError(self.env._("Keep orientation separate from pedagogical evaluations and exams."))

    def action_orientation_publish(self):
        self.ensure_one()
        self._orientation_edit()
        questions = self.question_ids
        if (
            not self.orientation_company_id
            or not questions
            or not (self.orientation_contact or "").strip()
            or not self.orientation_rule_ids
            or self.user_input_ids
            or any(set(r.answer_ids.question_id.ids) != set(questions.ids) for r in self.orientation_rule_ids)
            or any(
                q.question_type != "simple_choice"
                or len(q.suggested_answer_ids) < 2
                or q.comments_allowed
                or q.triggering_answer_ids
                or q.save_as_email
                or q.save_as_nickname
                for q in questions
            )
        ):
            raise ValidationError(
                self.env._("Define fixed single-choice questions, recommendations and an advice contact.")
            )
        self.orientation_rule_ids._check_definition()
        if any(not rule._available() for rule in self.orientation_rule_ids):
            raise ValidationError(
                self.env._("Recommend only published programmes or validated paths with public steps.")
            )
        return super().write(  # pylint: disable=super-method-mismatch  # checked publication transition
            {
                "orientation_published": True,
                "access_mode": "token",
                "users_login_required": True,
                "scoring_type": "no_scoring",
                "certification": False,
                "certification_give_badge": False,
            }
        )

    def _create_answer(self, *args, **kwargs):
        if self.filtered("orientation_company_id"):
            raise AccessError(self.env._("Orientation responses are not recorded. Use the training catalogue."))
        return super()._create_answer(*args, **kwargs)

    @api.ondelete(at_uninstall=False)
    def _orientation_keep_published(self):
        self._orientation_edit()

    @api.private
    def _orientation_result(self, answers):
        """Only the checked public projection calls this; no ORM or session writes."""
        self.ensure_one()
        if not self.active or not self.orientation_published:
            return False
        questions = self.question_ids
        expected = {str(q.id) for q in questions}
        if set(answers) != expected:
            return False
        selected = set()
        for question in questions:
            choice = answers.get(str(question.id))
            if choice not in {str(a.id) for a in question.suggested_answer_ids}:
                return False
            selected.add(int(choice))
        matched = self.orientation_rule_ids.filtered(lambda r: set(r.answer_ids.ids) <= selected)
        if len(matched) != 1 or not matched._available():
            return False
        rule = matched
        return {
            "name": rule.level or rule.program_id.title or rule.path_id.name,
            "explanation": rule.explanation,
            "criteria": [(a.question_id.title, a.value) for a in rule.answer_ids.sorted("id")],
            "programs": [(p.id, p.title) for p in (rule.program_id or rule.path_id.step_ids.program_id)],
        }


class OrientationRule(models.Model):
    _name = "training.orientation.rule"
    _description = "Orientation Recommendation"
    _rec_name = "explanation"

    survey_id = fields.Many2one("survey.survey", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="survey_id.orientation_company_id", store=True)
    answer_ids = fields.Many2many("survey.question.answer", string="Required Answers", required=True)
    level = fields.Char(string="Recommended Level", translate=True)
    program_id = fields.Many2one("training.program.version", string="Recommended Programme", ondelete="restrict")
    path_id = fields.Many2one("training.path", string="Recommended Path", ondelete="restrict")
    explanation = fields.Text(string="Recommendation Explanation", required=True, translate=True)

    @api.constrains("survey_id", "answer_ids", "level", "program_id", "path_id", "explanation")
    def _check_definition(self):
        for rule in self:
            if (
                not rule.company_id
                or not rule.answer_ids
                or any(a.question_id.survey_id != rule.survey_id or a.question_id.is_page for a in rule.answer_ids)
                or len(rule.answer_ids.question_id) != len(rule.answer_ids)
                or sum(bool(v) for v in (rule.level and rule.level.strip(), rule.program_id, rule.path_id)) != 1
                or not (rule.explanation or "").strip()
                or (rule.program_id and rule.program_id.company_id != rule.company_id)
                or (rule.path_id and rule.path_id.company_id != rule.company_id)
            ):
                raise ValidationError(
                    self.env._(
                        "Choose answers from this diagnostic, one target and an explanation in the same company."
                    )
                )

    @api.private
    def _available(self):
        self.ensure_one()
        programs = self.program_id or self.path_id.step_ids.program_id
        return bool(
            self.level
            or (
                programs
                and (not self.path_id or (self.path_id.active and self.path_id.state == "validated"))
                and all(
                    p.state == "published"
                    and p.public_catalogue
                    and p.course_id.active
                    and p.company_id == self.company_id
                    for p in programs
                )
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        surveys = self.env["survey.survey"].browse(
            [v.get("survey_id") or self.env.context.get("default_survey_id") for v in vals_list]
        )
        surveys._orientation_edit()
        return super().create(vals_list)

    def write(self, vals):
        (self.survey_id | self.env["survey.survey"].browse(vals.get("survey_id")))._orientation_edit()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _orientation_keep_rules(self):
        self.survey_id._orientation_edit()


class OrientationAttempt(models.Model):
    _inherit = "survey.user_input"

    @api.model_create_multi
    def create(self, vals_list):
        surveys = (
            self.env["survey.survey"]
            .sudo()
            .browse([v.get("survey_id") or self.env.context.get("default_survey_id") for v in vals_list])
        )
        # Classification only: even native invitations/test entries must not persist answers.
        if surveys.filtered("orientation_company_id"):
            raise AccessError(self.env._("Orientation responses are not recorded. Use the training catalogue."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env["survey.survey"].sudo().browse(vals.get("survey_id")).orientation_company_id:
            raise AccessError(self.env._("Orientation responses are not recorded. Use the training catalogue."))
        return super().write(vals)
