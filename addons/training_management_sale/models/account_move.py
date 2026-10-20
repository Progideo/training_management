from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _training_sale_invoices(self):
        return self.filtered(lambda move:
            move.move_type == "out_invoice"
            and bool(move.invoice_line_ids.sale_line_ids.order_id.filtered("training_request_kind"))
        )
