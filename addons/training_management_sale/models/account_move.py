from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    training_is_sale_invoice = fields.Boolean(
        string="Training Sales Invoice", compute="_compute_training_is_sale_invoice",
        store=True,
    )
    training_portal_partner_ids = fields.Many2many(
        "res.partner", "training_invoice_portal_partner_rel", "move_id", "partner_id",
        string="Authorized Portal Contacts", groups="base.group_user", copy=False,
        help="Only these named contacts may view this training invoice in the portal.",
    )

    def _get_thread_with_access(self, thread_id, *, mode="read", **kwargs):
        thread = super()._get_thread_with_access(thread_id, mode=mode, **kwargs)
        if (thread and self.env.user.share and thread.sudo().training_is_sale_invoice
                and (self.env.user._is_public()
                     or self.env.user.partner_id not in thread.sudo().training_portal_partner_ids)):
            return self.browse()
        return thread

    @api.depends("move_type", "invoice_line_ids.sale_line_ids.order_id.training_request_kind")
    def _compute_training_is_sale_invoice(self):
        for move in self:
            move.training_is_sale_invoice = (
                move.move_type in ("out_invoice", "out_refund", "out_receipt")
                and any(move.invoice_line_ids.sale_line_ids.order_id.mapped("training_request_kind"))
            )

    def _training_sale_invoices(self):
        return self.filtered(lambda move:
            move.move_type == "out_invoice"
            and bool(move.invoice_line_ids.sale_line_ids.order_id.filtered("training_request_kind"))
        )

    def _has_to_be_paid(self):
        self.ensure_one()
        return not self._training_sale_invoices() and super()._has_to_be_paid()

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
