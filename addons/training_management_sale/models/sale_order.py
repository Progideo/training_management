from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    training_request_kind = fields.Selection([
        ("individual", "Individual"), ("group", "Group"),
    ], string="Training Request", copy=True)
    training_requested_program_id = fields.Many2one(
        "training.program.version", string="Requested Programme Version",
        ondelete="restrict", check_company=True, copy=True,
    )
    training_attendee_count = fields.Integer(string="Expected Participants", copy=True)
    training_requested_currency_id = fields.Many2one(
        "res.currency", string="Requested Currency", ondelete="restrict", copy=True,
    )
    training_sponsor_id = fields.Many2one(
        "res.partner", string="Training Sponsor", ondelete="restrict",
        check_company=True, copy=True, groups="base.group_user",
        help="Person or organisation ordering the training; it can differ from the customer.",
    )
    training_expected_payer_id = fields.Many2one(
        "res.partner", string="Expected Payer", ondelete="restrict",
        check_company=True, copy=True, groups="base.group_user",
        help="Planned payer only; this does not change the invoice debtor or grant access.",
    )
    training_admin_contact_id = fields.Many2one(
        "res.partner", string="Administrative Contact", ondelete="restrict",
        check_company=True, copy=True, groups="base.group_user",
        help="Contact for commercial administration, without automatic document access.",
    )
    training_transfer_notice_ids = fields.One2many(
        "training.bank.transfer.notice", "order_id", string="Transfer Notices",
        groups="base.group_user",
    )

    def write(self, vals):
        if any(order.state == "sale" for order in self) and set(vals) & {
            "training_request_kind", "training_requested_program_id", "training_requested_currency_id",
            "training_sponsor_id", "training_expected_payer_id", "training_admin_contact_id",
        }:
            raise ValidationError(_("Revise the training offer instead of changing its confirmed request."))
        return super().write(vals)

    def _check_training_offer(self):
        for order in self:
            lines = order.order_line.filtered(lambda line: line.product_id.product_tmpl_id.training_course_id)
            if lines and not order.training_request_kind:
                raise ValidationError(_("Qualify the training request before sending its quotation."))
            if not order.training_request_kind:
                continue
            if not order.training_requested_program_id or order.training_requested_program_id.state not in ("validated", "published"):
                raise ValidationError(_("A training order requires a validated or published programme version."))
            if order.training_attendee_count <= 0:
                raise ValidationError(_("Enter a positive participant count on the training quotation."))
            if (order.training_requested_currency_id.name not in ("MAD", "EUR")
                    or order.training_requested_currency_id != order.currency_id):
                raise ValidationError(_("Choose a pricelist in the requested MAD or EUR currency."))
            if not lines or any(line.training_program_id != order.training_requested_program_id for line in lines):
                raise ValidationError(_("Training lines must use the requested programme version."))
            lines._check_training_program()
            for line in lines:
                line._check_training_tariff()

    def action_quotation_send(self):
        self._check_training_offer()
        return super().action_quotation_send()

    def action_confirm(self):
        self._check_training_offer()
        return super().action_confirm()
