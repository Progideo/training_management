from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class BankTransferNotice(models.Model):
    _name = "training.bank.transfer.notice"
    _description = "Unverified Bank Transfer Notice"
    _rec_name = "reference"
    _check_company_auto = True

    order_id = fields.Many2one(
        "sale.order", string="Training Order", required=True,
        ondelete="restrict", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        "res.company", related="order_id.company_id", store=True, readonly=True,
    )
    invoice_id = fields.Many2one(
        "account.move", string="Claimed Invoice", ondelete="restrict",
        check_company=True,
    )
    currency_id = fields.Many2one(
        "res.currency", related="order_id.currency_id", store=True, readonly=True,
    )
    amount = fields.Monetary(string="Claimed Amount", required=True)
    claimed_date = fields.Date(string="Claimed Transfer Date", required=True)
    reference = fields.Char(string="Claimed Reference", required=True)
    reported_by_id = fields.Many2one(
        "res.users", string="Reported By", default=lambda self: self.env.user,
        readonly=True,
    )
    state = fields.Selection([
        ("reported", "Unverified"), ("void", "Voided"),
    ], default="reported", required=True, readonly=True)

    @api.constrains("order_id", "invoice_id", "amount", "claimed_date", "reference")
    def _check_notice(self):
        for notice in self:
            if not notice.order_id.training_request_kind or notice.order_id.state != "sale":
                raise ValidationError(_("A transfer notice requires a confirmed training order."))
            if notice.amount <= 0:
                raise ValidationError(_("The claimed transfer amount must be positive."))
            if not notice.reference.strip():
                raise ValidationError(_("Enter the reference provided with the transfer notice."))
            if notice.invoice_id and (
                notice.invoice_id not in notice.order_id.invoice_ids
                or notice.invoice_id.move_type != "out_invoice"
                or notice.invoice_id.currency_id != notice.currency_id
            ):
                raise ValidationError(_("The claimed invoice must belong to the order in its currency."))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("state", "reported") != "reported" for vals in vals_list):
            raise ValidationError(_("A new transfer notice must be unverified."))
        return super().create([
            {**vals, "reported_by_id": self.env.user.id} for vals in vals_list
        ])

    def write(self, vals):
        if set(vals) != {"state"} or vals["state"] != "void":
            raise AccessError(_("A transfer notice cannot be changed after reporting."))
        if not self.env.user.has_group("account.group_account_invoice"):
            raise AccessError(_("Only accounting staff can void a transfer notice."))
        return super().write(vals)

    def action_void(self):
        self.write({"state": "void"})
