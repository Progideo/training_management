"""Explicit reasons and effectiveness decisions; no implicit approval from a button."""

from odoo import fields, models
from odoo.exceptions import ValidationError


class QualityOperation(models.TransientModel):
    _name = "training.quality.operation"
    _description = "Quality Dossier Decision"

    complaint_id = fields.Many2one("training.complaint")
    improvement_id = fields.Many2one("training.improvement")
    operation = fields.Selection(
        [
            ("reopen", "Reopen Complaint"),
            ("revoke", "Withdraw Participant Access"),
            ("verify", "Verify Effectiveness"),
            ("replan", "Replan Action"),
        ],
        required=True,
    )
    reason = fields.Text()
    result = fields.Selection([("effective", "Effective"), ("ineffective", "Not Effective")])
    verification = fields.Text()
    follow_up = fields.Text()

    def action_apply(self):
        self.ensure_one()
        self.check_access("read")
        if bool(self.complaint_id) == bool(self.improvement_id):
            raise ValidationError(self.env._("Choose exactly one quality dossier."))
        if self.operation == "reopen" and self.complaint_id:
            self.complaint_id.action_reopen(self.reason)
        elif self.operation == "revoke" and self.complaint_id:
            self.complaint_id.action_revoke_portal(self.reason)
        elif self.operation == "replan" and self.improvement_id:
            self.improvement_id.action_replan(self.reason)
        elif self.operation == "verify" and self.improvement_id and self.result:
            self.improvement_id.action_verify(self.result == "effective", self.verification, self.follow_up)
        else:
            raise ValidationError(self.env._("Choose a decision applicable to this dossier."))
        return {"type": "ir.actions.act_window_close"}
