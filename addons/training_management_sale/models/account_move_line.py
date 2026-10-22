from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_aml_vals(self, hide_taxes):
        values = super()._get_aml_vals(hide_taxes)
        if self.move_id.training_is_sale_invoice and self.is_downpayment:
            values["label"] = self.env._("Down Payment")
        return values
