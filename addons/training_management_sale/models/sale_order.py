from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    training_request_kind = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
        ],
        string="Training Request",
        copy=True,
    )
    training_requested_program_id = fields.Many2one(
        "training.program.version",
        string="Requested Programme Version",
        ondelete="restrict",
        check_company=True,
        copy=True,
    )
    training_attendee_count = fields.Integer(string="Expected Participants", copy=True)
    training_requested_currency_id = fields.Many2one(
        "res.currency",
        string="Requested Currency",
        ondelete="restrict",
        copy=True,
    )
    training_sponsor_id = fields.Many2one(
        "res.partner",
        ondelete="restrict",
        check_company=True,
        copy=True,
        groups="base.group_user",
        help="Person or organisation ordering the training; it can differ from the customer.",
    )
    training_expected_payer_id = fields.Many2one(
        "res.partner",
        string="Expected Payer",
        ondelete="restrict",
        check_company=True,
        copy=True,
        groups="base.group_user",
        help="Planned payer only; this does not change the invoice debtor or grant access.",
    )
    training_admin_contact_id = fields.Many2one(
        "res.partner",
        string="Administrative Contact",
        ondelete="restrict",
        check_company=True,
        copy=True,
        groups="base.group_user",
        help="Contact for commercial administration, without automatic document access.",
    )
    training_transfer_notice_ids = fields.One2many(
        "training.bank.transfer.notice",
        "order_id",
        string="Transfer Notices",
        groups="base.group_user",
    )
    training_portal_partner_ids = fields.Many2many(
        "res.partner",
        "training_sale_portal_partner_rel",
        "order_id",
        "partner_id",
        string="Authorized Portal Contacts",
        groups="base.group_user",
        copy=False,
        help="Only these named contacts may view this training quotation or order in the portal.",
    )

    def _get_thread_with_access(self, thread_id, *, mode="read", **kwargs):
        thread = super()._get_thread_with_access(thread_id, mode=mode, **kwargs)
        # Native token/author paths still need the current document grant.
        if thread and not self.env["training.document.policy"]._can_read(thread):
            return self.browse()
        return thread

    @api.model_create_multi
    def create(self, vals_list):
        with self.env.cr.savepoint():
            orders = super().create(vals_list)
            orders.filtered(lambda order: order.state in ("sent", "sale"))._check_training_offer()
            return orders

    def write(self, vals):
        if "currency_id" in vals and any(
            order.state == "sale" and order.training_request_kind and order.currency_id.id != vals["currency_id"]
            for order in self
        ):
            raise ValidationError(self.env._("Revise the training offer instead of changing its confirmed currency."))
        if any(order.state == "sale" for order in self) and set(vals) & {
            "training_request_kind",
            "training_requested_program_id",
            "training_requested_currency_id",
            "training_sponsor_id",
            "training_expected_payer_id",
            "training_admin_contact_id",
        }:
            raise ValidationError(self.env._("Revise the training offer instead of changing its confirmed request."))
        with self.env.cr.savepoint():
            result = super().write(vals)
            if vals.get("state") in ("sent", "sale"):
                self._check_training_offer()
            return result

    def _check_training_offer(self):
        for order in self:
            lines = order.order_line.filtered(lambda line: line.product_id.product_tmpl_id.training_course_id)
            if lines and not order.training_request_kind:
                raise ValidationError(self.env._("Qualify the training request before sending its quotation."))
            if not order.training_request_kind:
                continue
            if not order.training_requested_program_id or order.training_requested_program_id.state not in (
                "validated",
                "published",
            ):
                raise ValidationError(
                    self.env._("A training order requires a validated or published programme version.")
                )
            if order.training_attendee_count <= 0:
                raise ValidationError(self.env._("Enter a positive participant count on the training quotation."))
            if not lines or any(line.training_program_id != order.training_requested_program_id for line in lines):
                raise ValidationError(self.env._("Training lines must use the requested programme version."))
            lines._check_training_program()
            for line in lines:
                line._check_training_quantity()

    def action_quotation_send(self):
        self._check_training_offer()
        return super().action_quotation_send()

    def _message_get_default_recipients(self, with_cc=False, all_tos=False):
        recipients = super()._message_get_default_recipients(with_cc=with_cc, all_tos=all_tos)
        for order in self.filtered("training_request_kind"):
            recipients[order.id] = {
                "partner_ids": self.env["training.document.policy"]._partners(order, email_only=True).ids,
                "email_to": "",
                "email_cc": "",
            }
        return recipients

    def _notify_get_recipients(self, message, **kwargs):
        recipients = super()._notify_get_recipients(message, **kwargs)
        return self.env["training.document.policy"]._filter_notifications(self, recipients)

    def action_confirm(self):
        self._check_training_offer()
        return super().action_confirm()
