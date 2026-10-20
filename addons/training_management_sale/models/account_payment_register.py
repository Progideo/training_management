from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    training_bank_payment_required = fields.Boolean(
        compute="_compute_training_bank_payment_required",
    )
    training_bank_reference = fields.Char(string="Training Bank Reference")
    training_duplicate_reference_exists = fields.Boolean(
        compute="_compute_training_duplicate_reference_exists",
    )
    training_duplicate_reference_reason = fields.Char(string="Repeated Reference Reason")

    def _training_invoices(self):
        self.ensure_one()
        return self.line_ids.move_id.filtered(lambda move:
            move.move_type == "out_invoice"
            and bool(move.invoice_line_ids.sale_line_ids.order_id.filtered("training_request_kind"))
        )

    @api.depends("line_ids", "journal_id", "payment_type")
    def _compute_training_bank_payment_required(self):
        for wizard in self:
            wizard.training_bank_payment_required = bool(
                wizard.payment_type == "inbound"
                and wizard.journal_id.type == "bank"
                and wizard._training_invoices()
            )

    @api.depends("training_bank_reference", "journal_id", "company_id")
    def _compute_training_duplicate_reference_exists(self):
        for wizard in self:
            reference = (wizard.training_bank_reference or "").strip().upper()
            wizard.training_duplicate_reference_exists = bool(
                reference and wizard.journal_id and wizard.company_id
                and self.env["account.payment"].sudo().search_count([
                    ("company_id", "=", wizard.company_id.id),
                    ("journal_id", "=", wizard.journal_id.id),
                    ("training_bank_reference", "=", reference),
                    ("state", "in", ("paid", "reconciled")),
                ])
            )

    def _training_payment_values(self):
        self.ensure_one()
        if not self.training_bank_payment_required:
            return {}
        return {
            "training_bank_reference": self.training_bank_reference,
            "training_duplicate_reference_reason": self.training_duplicate_reference_reason,
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        vals.update(self._training_payment_values())
        return vals

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        vals.update(self._training_payment_values())
        return vals

    def action_create_payments(self):
        self.ensure_one()
        if self.training_bank_payment_required:
            if not (self.training_bank_reference or "").strip():
                raise ValidationError(_("Enter the bank reference before recording a training payment."))
            if any(invoice.currency_id != self.currency_id for invoice in self._training_invoices()):
                raise ValidationError(_(
                    "A training payment in another currency requires an explicit accounting review."
                ))
        return super().action_create_payments()
