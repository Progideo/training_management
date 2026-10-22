from odoo import api, models, _
from odoo.exceptions import ValidationError


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _check_training_payment_links(self, values):
        for field_name, model_name in (
            ("sale_order_ids", "sale.order"),
            ("invoice_ids", "account.move"),
        ):
            if field_name not in values:
                continue
            document_ids = self._fields[field_name].convert_to_cache(
                values[field_name], self,
            )
            documents = self.env[model_name].browse(document_ids)
            if model_name == "sale.order":
                training_documents = documents.filtered("training_request_kind")
            else:
                training_documents = documents._training_sale_invoices()
            if training_documents:
                raise ValidationError(_(
                    "Online payment transactions are disabled for training orders and invoices."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._check_training_payment_links(values)
        return super().create(vals_list)

    def write(self, vals):
        if "sale_order_ids" in vals or "invoice_ids" in vals:
            for transaction in self:
                transaction._check_training_payment_links(vals)
        return super().write(vals)
