from odoo import fields, models


class Import(models.TransientModel):
    _name = "training.elearning.import"
    _description = "Import Interactive Package"
    resource_id = fields.Many2one("training.elearning.resource", required=True)
    number = fields.Char(required=True)
    data = fields.Binary(required=True, attachment=False)
    filename = fields.Char()
    license_note = fields.Char(required=True)
    provenance = fields.Text(required=True)

    def action_import(self):
        self.ensure_one()
        self.check_access("read")
        version = self.env["training.elearning.version"]._import(
            self.resource_id, self.number, self.data.content, self.license_note, self.provenance
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": version._name,
            "res_id": version.id,
            "view_mode": "form",
            "target": "current",
        }


class Withdraw(models.TransientModel):
    _name = "training.elearning.withdraw"
    _description = "Withdraw Interactive Version"
    version_id = fields.Many2one("training.elearning.version", required=True)
    reason = fields.Text(required=True)

    def action_withdraw(self):
        self.ensure_one()
        self.check_access("read")
        self.version_id._withdraw(self.reason)
        return {"type": "ir.actions.act_window_close"}
