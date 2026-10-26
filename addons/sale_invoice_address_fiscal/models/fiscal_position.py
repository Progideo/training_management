from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sale_fiscal_by_invoice_address = fields.Boolean(
        string="Sales fiscal position by invoice address",
        help="Use the billing country for domestic/export sales. Purchases keep native rules.",
    )
    sale_export_fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Export sales fiscal position",
        check_company=True,
    )

    def _sale_invoice_fiscal_position(self, partner):
        self.ensure_one()
        # An unknown country must never qualify as an export.
        if partner.country_id and partner.country_id != self.account_fiscal_country_id:
            return self.sale_export_fiscal_position_id
        return self.domestic_fiscal_position_id


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends("partner_invoice_id", "partner_invoice_id.country_id")
    def _compute_fiscal_position_id(self):
        policy = self.filtered(lambda order: order.company_id.sale_fiscal_by_invoice_address)
        result = super(SaleOrder, self - policy)._compute_fiscal_position_id()
        for order in policy:
            order.fiscal_position_id = order.company_id._sale_invoice_fiscal_position(order.partner_invoice_id)
        return result


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends("order_id.fiscal_position_id")
    def _compute_tax_ids(self):
        # Native Odoo offers a manual tax-update action on fiscal position change.
        # This opt-in policy also updates draft lines when the billing address changes.
        return super()._compute_tax_ids()


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
