from odoo import api, models
from odoo.exceptions import ValidationError


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.model_create_multi
    def create(self, vals_list):
        line_ids = {
            vals[field] for vals in vals_list for field in ("debit_move_id", "credit_move_id") if vals.get(field)
        }
        lines = {line.id: line for line in self.env["account.move.line"].browse(line_ids)}
        for vals in vals_list:
            debit_line = lines.get(vals.get("debit_move_id"))
            credit_line = lines.get(vals.get("credit_move_id"))
            for invoice_line, payment_line in ((debit_line, credit_line), (credit_line, debit_line)):
                if not invoice_line or not payment_line:
                    continue
                if not invoice_line.move_id._training_sale_invoices():
                    continue
                statement_line = payment_line.statement_line_id
                if statement_line and (
                    statement_line.journal_id.type != "bank"
                    or statement_line.currency_id != invoice_line.move_id.currency_id
                ):
                    raise ValidationError(
                        self.env._(
                            "A training invoice can only be matched with a bank statement line in the invoice currency."
                        )
                    )
                if statement_line:
                    continue
                if not payment_line.payment_id:
                    continue
                payment = payment_line.payment_id
                if (
                    not payment.training_bank_reference
                    or not payment.training_bank_verified
                    or not payment.training_bank_verified_by_id
                    or not payment.training_bank_verified_at
                    or payment.payment_type != "inbound"
                    or payment.journal_id.type != "bank"
                    or payment.payment_method_line_id.code != "manual"
                    or payment.currency_id != invoice_line.move_id.currency_id
                ):
                    raise ValidationError(
                        self.env._(
                            "A training invoice can only be matched with an incoming manual bank payment "
                            "bearing a bank reference in the invoice currency."
                        )
                    )
        return super().create(vals_list)
