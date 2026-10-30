from odoo import models


class AccountPaymentRegister(models.TransientModel):  # pylint: disable=no-wizard-in-models
    _inherit = "account.payment.register"

    def _training_payment_privacy_values(self):
        self.ensure_one()
        return {"training_receipt_restricted": bool(self.line_ids.move_id._training_sale_invoices())}

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        vals.update(self._training_payment_privacy_values())
        return vals

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        invoices = batch_result["lines"].move_id._training_sale_invoices()
        vals["training_receipt_restricted"] = bool(invoices)
        return vals
