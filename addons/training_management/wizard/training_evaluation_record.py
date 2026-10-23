from odoo import fields, models


class EvaluationRecord(models.TransientModel):
    _name = "training.evaluation.record"
    _description = "Evaluation Validation or Motivated Revision"

    assignment_id = fields.Many2one("training.evaluation.assignment", required=True)
    revision = fields.Integer(required=True)
    score = fields.Float()
    score_confirmed = fields.Boolean(string="Score explicitly checked, including zero")
    conclusion = fields.Text(required=True)
    source = fields.Text(required=True, help="Observed assessment, paper reference or completed native questionnaire.")
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        self.env["training.evaluation.service"]._validate(
            self.assignment_id.id,
            revision=self.revision,
            score=self.score if self.score_confirmed else None,
            conclusion=self.conclusion,
            source=self.source,
            reason=self.reason,
        )
        return {"type": "ir.actions.act_window_close"}
