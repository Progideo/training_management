from odoo import api, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.model_create_multi
    def create(self, vals_list):
        reconciliations = super().create(vals_list)
        for reconciliation in reconciliations:
            lines = reconciliation.debit_move_id | reconciliation.credit_move_id
            if lines.move_id._training_sale_invoices():
                # Only a privacy marker, never amounts or accounting decisions.
                # Accounting users can reconcile without write access to payments.
                lines.payment_id.sudo().write({"training_receipt_restricted": True})
        return reconciliations
