from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _training_sale_invoices(self):
        return self.filtered(lambda move:
            move.move_type == "out_invoice"
            and bool(move.invoice_line_ids.sale_line_ids.order_id.filtered("training_request_kind"))
        )

    @api.depends("company_id", "invoice_line_ids.sale_line_ids.order_id.training_request_kind")
    def _compute_display_link_qr_code(self):
        super()._compute_display_link_qr_code()
        for invoice in self._training_sale_invoices():
            invoice.display_link_qr_code = False

    def _get_portal_payment_link(self):
        self.ensure_one()
        if self._training_sale_invoices():
            return None
        return super()._get_portal_payment_link()

    def _generate_portal_payment_qr(self):
        self.ensure_one()
        if self._training_sale_invoices():
            return None
        return super()._generate_portal_payment_qr()
