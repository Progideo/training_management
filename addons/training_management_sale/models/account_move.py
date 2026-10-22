from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    training_is_sale_invoice = fields.Boolean(
        string="Training Sales Invoice",
        compute="_compute_training_is_sale_invoice",
        store=True,
    )
    training_portal_partner_ids = fields.Many2many(
        "res.partner",
        "training_invoice_portal_partner_rel",
        "move_id",
        "partner_id",
        string="Authorized Portal Contacts",
        groups="base.group_user",
        copy=False,
        help="Only these named contacts may view this training invoice in the portal.",
    )

    def action_copy_training_portal_contacts(self):
        self.ensure_one()
        if not self.env.user.has_group("sales_team.group_sale_salesman"):
            raise UserError(self.env._("Only a salesperson may copy authorized contacts from a training order."))
        self.check_access("write")
        if self.state != "draft" or not self.training_is_sale_invoice:
            raise UserError(self.env._("Copy authorized contacts only on a draft training invoice."))
        orders = self.invoice_line_ids.sale_line_ids.order_id
        orders.check_access("read")
        if not orders or any(
            not order.training_request_kind or order.company_id != self.company_id for order in orders
        ):
            raise UserError(self.env._("This invoice must be linked only to training orders of its company."))
        contacts = orders[0].training_portal_partner_ids
        for order in orders[1:]:
            contacts &= order.training_portal_partner_ids
        if not contacts:
            raise UserError(self.env._("No contact is authorized on every linked training order."))
        self.training_portal_partner_ids = [Command.set(contacts.ids)]

    def _get_thread_with_access(self, thread_id, *, mode="read", **kwargs):
        thread = super()._get_thread_with_access(thread_id, mode=mode, **kwargs)
        if (
            thread
            and self.env.user.share
            and thread.sudo().training_is_sale_invoice
            and (
                self.env.user._is_public() or self.env.user.partner_id not in thread.sudo().training_portal_partner_ids
            )
        ):
            return self.browse()
        return thread

    @api.depends("move_type", "invoice_line_ids.sale_line_ids.order_id.training_request_kind")
    def _compute_training_is_sale_invoice(self):
        for move in self:
            move.training_is_sale_invoice = move.move_type in ("out_invoice", "out_refund", "out_receipt") and any(
                move.invoice_line_ids.sale_line_ids.order_id.mapped("training_request_kind")
            )

    def _training_sale_invoices(self):
        return self.filtered(
            lambda move: (
                move.move_type == "out_invoice"
                and bool(move.invoice_line_ids.sale_line_ids.order_id.filtered("training_request_kind"))
            )
        )

    def _message_get_default_recipients(self, with_cc=False, all_tos=False):
        recipients = super()._message_get_default_recipients(with_cc=with_cc, all_tos=all_tos)
        for invoice in self.filtered("training_is_sale_invoice"):
            recipients[invoice.id] = {
                "partner_ids": invoice.training_portal_partner_ids.filtered("email").ids,
                "email_to": "",
                "email_cc": "",
            }
        return recipients

    def _notify_get_recipients(self, message, **kwargs):
        recipients = super()._notify_get_recipients(message, **kwargs)
        if not self.training_is_sale_invoice:
            return recipients
        authorized_ids = set(self.training_portal_partner_ids.ids)
        return [recipient for recipient in recipients if not recipient["share"] or recipient["id"] in authorized_ids]

    def _has_to_be_paid(self):
        self.ensure_one()
        return not self._training_sale_invoices() and super()._has_to_be_paid()

    @api.depends("company_id", "invoice_line_ids.sale_line_ids.order_id.training_request_kind")
    def _compute_display_link_qr_code(self):  # pylint: disable=missing-return  # compute method, nothing to return
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
