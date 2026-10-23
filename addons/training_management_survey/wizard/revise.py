from odoo import api, fields, models, Command
from odoo.exceptions import ValidationError


class ExamRevisionWizard(models.TransientModel):
    _name = "training.exam.revise"
    _description = "Revise a Completed Exam Result"

    attempt_id = fields.Many2one("survey.user_input", required=True)
    reason = fields.Text(required=True)
    line_ids = fields.One2many("training.exam.revise.line", "wizard_id")

    @api.model
    def default_get(self, field_names):
        result = super().default_get(field_names)
        if self.env.context.get("active_model") == "survey.user_input":
            attempt = self.env["survey.user_input"].browse(self.env.context.get("active_id")).exists()
            attempt.check_access("read")
            if not attempt.training_enrollment_id or attempt.state != "done":
                raise ValidationError(self.env._("Choose a completed mock exam attempt."))
            latest = attempt.training_adjustment_ids[:1]
            result.update(
                attempt_id=attempt.id,
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

    def action_apply(self):
        self.ensure_one()
        if len(self.line_ids.question_id) != len(self.line_ids):
            raise ValidationError(self.env._("Use one revision line per question."))
        self.env["training.exam.revision"]._record(
            self.attempt_id,
            {str(line.question_id.id): line.points for line in self.line_ids},
            self.reason,
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
