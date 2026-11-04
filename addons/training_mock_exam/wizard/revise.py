from uuid import uuid4
from odoo import api, fields, models, Command
from odoo.exceptions import AccessError, ValidationError


class ExamRevisionWizard(models.TransientModel):
    _name = "training.exam.revise"
    _description = "Revise a Completed Exam Result"

    attempt_id = fields.Many2one("survey.user_input", required=True)
    company_id = fields.Many2one("res.company", readonly=True)
    reader_group_id = fields.Many2one("res.groups", readonly=True)
    request_key = fields.Char(default=lambda self: str(uuid4()), required=True, copy=False)
    expected_previous = fields.Integer(default=0)
    reason = fields.Text(required=True)
    line_ids = fields.One2many("training.exam.revise.line", "wizard_id")

    @api.model
    def default_get(self, field_names):
        result = super().default_get(field_names)
        if self.env.context.get("active_model") == "survey.user_input":
            attempt = self.env["survey.user_input"].browse(self.env.context.get("active_id")).exists()
            attempt.check_access("read")
            attempt._mock_revision_scope()
            if attempt.state != "done":
                raise ValidationError(self.env._("Choose a completed mock exam attempt."))
            latest = attempt.training_adjustment_ids[:1]
            result.update(
                attempt_id=attempt.id,
                expected_previous=latest.id or 0,
                line_ids=[
                    Command.create(
                        {
                            "question_id": r["question"].id,
                            "maximum": r["maximum"],
                            "previous_points": latest.points_by_question[str(r["question"].id)]
                            if latest
                            else r["points"],
                            "points": latest.points_by_question[str(r["question"].id)] if latest else r["points"],
                        }
                    )
                    for r in attempt._training_scores()
                ],
            )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            identifier = values.get("attempt_id") or self.env.context.get("default_attempt_id")
            if not identifier and self.env.context.get("active_model") == "survey.user_input":
                identifier = self.env.context.get("active_id")
            attempt = self.env["survey.user_input"].browse(identifier)
            if not attempt or not self.env.user.active:
                raise ValidationError(self.env._("Choose a completed mock exam attempt."))
            policy = attempt._mock_revision_scope()
            values.update(company_id=policy["company"].id, reader_group_id=policy["reader_group"].id)
        return super().create(vals_list)

    def write(self, values):
        if {"company_id", "reader_group_id"} & values.keys():
            raise AccessError(self.env._("The server records result revision permissions."))
        result = True
        for wizard in self:
            attempt = self.env["survey.user_input"].browse(values.get("attempt_id") or wizard.attempt_id.id)
            policy = attempt._mock_revision_scope()
            scoped = dict(values, company_id=policy["company"].id, reader_group_id=policy["reader_group"].id)
            result = super(ExamRevisionWizard, wizard).write(scoped) and result
        return result

    def action_apply(self):
        self.ensure_one()
        if len(self.line_ids.question_id) != len(self.line_ids):
            raise ValidationError(self.env._("Use one revision line per question."))
        self.env["training.exam.revision"]._record(
            self.attempt_id,
            {str(line.question_id.id): line.points for line in self.line_ids},
            self.reason,
            request_key=self.request_key,
            expected_previous=self.expected_previous,
        )
        return {"type": "ir.actions.act_window_close"}


class ExamRevisionLine(models.TransientModel):
    _name = "training.exam.revise.line"
    _description = "Revised Question Points"

    wizard_id = fields.Many2one("training.exam.revise", required=True, ondelete="cascade")
    question_id = fields.Many2one("survey.question", required=True)
    previous_points = fields.Float(readonly=True)
    maximum = fields.Float(readonly=True)
    points = fields.Float(required=True)

    @api.constrains("wizard_id", "question_id")
    def _check_contextual_question(self):
        for line in self:
            if line.wizard_id.create_uid != self.env.user:
                raise AccessError(self.env._("Use your own result revision request."))
            line.wizard_id.attempt_id._mock_revision_scope()
            if line.question_id not in line.wizard_id.attempt_id.predefined_question_ids:
                raise ValidationError(self.env._("Use a question from this exact completed attempt."))
