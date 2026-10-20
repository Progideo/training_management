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

    def write(self, vals):
        if any(order.state == "sale" for order in self) and set(vals) & {
            "training_request_kind", "training_requested_program_id", "training_requested_currency_id",
        }:
            raise ValidationError(_("Revise the training offer instead of changing its confirmed request."))
        return super().write(vals)

    def action_confirm(self):
        for order in self:
            lines = order.order_line.filtered(lambda line: line.product_id.product_tmpl_id.training_course_id)
            if lines and not order.training_request_kind:
                raise ValidationError(_("Qualify the training request before confirming its order."))
            if not order.training_request_kind:
                continue
            if not order.training_requested_program_id or order.training_requested_program_id.state not in ("validated", "published"):
                raise ValidationError(_("A training order requires a validated or published programme version."))
            if order.training_requested_currency_id != order.currency_id:
                raise ValidationError(_("Choose a pricelist in the requested currency before confirming."))
            if not lines or any(line.training_program_id != order.training_requested_program_id for line in lines):
                raise ValidationError(_("Training lines must use the requested programme version."))
            lines._check_training_program()
        return super().action_confirm()
