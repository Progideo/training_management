from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    sale_fiscal_by_invoice_address = fields.Boolean(
        string="Sales fiscal position by invoice address",
        help="Use the billing country for domestic/export sales. Purchases keep native rules.",
    )
    sale_export_fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Legacy export sales fiscal position",
        readonly=True,
        check_company=True,
    )

    sale_domestic_currency_ids = fields.Many2many(
        "res.currency",
        "res_company_domestic_sale_currency_rel",
        string="Allowed domestic sales currencies",
        help="An empty list keeps the native currency choices for domestic sales.",
    )
    sale_foreign_currency_ids = fields.Many2many(
        "res.currency",
        "res_company_foreign_sale_currency_rel",
        string="Allowed foreign sales currencies",
        help="An empty list keeps the native currency choices for foreign sales.",
    )

    def _check_sale_invoice_currency(self, partner, currency):
        self.ensure_one()
        if not partner.country_id:
            return
        allowed = (
            self.sale_domestic_currency_ids
            if partner.country_id == self.account_fiscal_country_id
            else self.sale_foreign_currency_ids
        )
        if allowed and currency and currency not in allowed:
            raise ValidationError(
                self.env._(
                    "Sales billed to %(country)s must use %(currencies)s. Change the pricelist or invoice currency.",
                    country=partner.country_id.display_name,
                    currencies=", ".join(allowed.mapped("name")),
                )
            )

    def _sale_invoice_fiscal_position(self, partner):
        self.ensure_one()
        return self.env["account.fiscal.position"].with_company(self)._get_fiscal_position(partner, delivery=partner)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends("partner_invoice_id", "partner_invoice_id.country_id")
    def _compute_fiscal_position_id(self):
        policy = self.filtered(lambda order: order.company_id.sale_fiscal_by_invoice_address)
        result = super(SaleOrder, self - policy)._compute_fiscal_position_id()
        for order in policy:
            order.fiscal_position_id = order.company_id._sale_invoice_fiscal_position(order.partner_invoice_id)
        return result

    @api.constrains("partner_invoice_id", "currency_id", "company_id", "pricelist_id")
    def _check_sales_currency(self):
        for order in self:
            order.company_id._check_sale_invoice_currency(order.partner_invoice_id, order.currency_id)

    def action_confirm(self):
        # Recheck stored drafts, including a country changed on the contact itself.
        self._check_sales_currency()
        return super().action_confirm()


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends("partner_id.country_id")
    def _compute_fiscal_position_id(self):
        policy = self.filtered(
            lambda move: move.company_id.sale_fiscal_by_invoice_address and move.is_sale_document(include_receipts=True)
        )
        result = super(AccountMove, self - policy)._compute_fiscal_position_id()
        for move in policy:
            move.fiscal_position_id = move.company_id._sale_invoice_fiscal_position(move.partner_id)
        return result

    @api.constrains("partner_id", "currency_id", "company_id", "move_type")
    def _check_sales_currency(self):
        for move in self.filtered(lambda item: item.is_sale_document(include_receipts=True)):
            move.company_id._check_sale_invoice_currency(move.partner_id, move.currency_id)

    def _post(self, soft=True):
        self._check_sales_currency()
        return super()._post(soft=soft)
