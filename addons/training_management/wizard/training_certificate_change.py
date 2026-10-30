from odoo import fields, models


class TrainingCertificateChange(models.TransientModel):
    _name = "training.certificate.change"
    _description = "Change Certificate Status"

    verification_id = fields.Many2one("training.certificate.verification", required=True, readonly=True)
    state = fields.Selection([("revoked", "Revoked"), ("replaced", "Replaced")], required=True, readonly=True)
    dossier_id = fields.Many2one(related="verification_id.dossier_id")
    kind = fields.Selection(related="verification_id.kind")
    replacement_id = fields.Many2one(
        "training.certificate.verification",
        domain="[('dossier_id', '=', dossier_id), ('kind', '=', kind), ('state', '=', 'valid'), ('id', '!=', verification_id)]",
    )
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        if self.state == "replaced":
            self.verification_id.action_replace(replacement_id=self.replacement_id.id, reason=self.reason)
        else:
            self.verification_id.action_revoke(reason=self.reason)
        return {"type": "ir.actions.act_window_close"}
