from odoo import fields, models


class TrainingClosureChange(models.TransientModel):
    _name = "training.closure.change"
    _description = "Change Closure Dossier"

    dossier_id = fields.Many2one("training.closure", required=True, readonly=True)
    company_id = fields.Many2one(related="dossier_id.company_id")
    operation = fields.Selection(
        [("reassign", "Reassign Quality Reviewer"), ("rectify", "Rectify Closed Dossier")], required=True, readonly=True
    )
    expected_quality_id = fields.Many2one("res.users", readonly=True)
    expected_closure_event_id = fields.Many2one("training.closure.event", readonly=True)
    quality_id = fields.Many2one(
        "res.users",
        string="New Quality Reviewer",
        domain=lambda self: (
            "[('active', '=', True), ('company_ids', 'in', company_id), ('all_group_ids', 'in', %s)]"
            % self.env.ref("training_management.group_training_quality").ids
        ),
    )
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        if self.operation == "reassign":
            self.dossier_id.action_reassign_quality(
                self.quality_id.id, self.reason, expected_quality_id=self.expected_quality_id.id
            )
        else:
            self.dossier_id.action_rectify(self.reason, expected_closure_event_id=self.expected_closure_event_id.id)
        return {"type": "ir.actions.act_window_close"}
