from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class BankTransferNotice(models.Model):
    _name = "training.bank.transfer.notice"
    _description = "Unverified Bank Transfer Notice"
    _rec_name = "reference"
    _check_company_auto = True

    order_id = fields.Many2one(
        "sale.order",
        string="Training Order",
        required=True,
        ondelete="restrict",
        check_company=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="order_id.company_id",
        store=True,
        readonly=True,
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Claimed Invoice",
        ondelete="restrict",
        check_company=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Claimed Currency",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.company.currency_id,
    )
    amount = fields.Monetary(string="Claimed Amount", required=True)
    claimed_date = fields.Date(string="Claimed Transfer Date", required=True)
    reference = fields.Char(string="Claimed Reference", required=True)
    reported_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("reported", "Unverified"),
            ("void", "Voided"),
        ],
        default="reported",
        required=True,
        readonly=True,
    )

    @api.constrains("order_id", "invoice_id", "amount", "claimed_date", "reference")
    def _check_notice(self):
        for notice in self:
            if not notice.order_id.training_request_kind or notice.order_id.state != "sale":
                raise ValidationError(self.env._("A transfer notice requires a confirmed training order."))
            if notice.amount <= 0:
                raise ValidationError(self.env._("The claimed transfer amount must be positive."))
            if not notice.reference.strip():
                raise ValidationError(self.env._("Enter the reference provided with the transfer notice."))
            if notice.invoice_id and (
                notice.invoice_id not in notice.order_id.invoice_ids or notice.invoice_id.move_type != "out_invoice"
            ):
                raise ValidationError(self.env._("The claimed invoice must belong to the order."))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("state", "reported") != "reported" for vals in vals_list):
            raise ValidationError(self.env._("A new transfer notice must be unverified."))
        values = []
        for vals in vals_list:
            vals = {**vals, "reported_by_id": self.env.user.id}
            if "currency_id" not in vals:
                order = self.env["sale.order"].browse(vals.get("order_id") or self.env.context.get("default_order_id"))
                vals["currency_id"] = self.env.context.get("default_currency_id") or order.currency_id.id
            values.append(vals)
        return super().create(values)

    def write(self, vals):
        if set(vals) != {"state"} or vals["state"] != "void":
            raise AccessError(self.env._("A transfer notice cannot be changed after reporting."))
        if not self.env.user.has_group("account.group_account_invoice"):
            raise AccessError(self.env._("Only accounting staff can void a transfer notice."))
        return super().write(vals)

    def action_void(self):
        self.write({"state": "void"})

    def export_data(self, fields_to_export):
        self.check_access("read")
        return super().export_data(fields_to_export)
