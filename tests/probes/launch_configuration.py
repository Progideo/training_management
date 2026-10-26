"""Native launch contract, using only fictional data in the isolated CI database."""

from datetime import date

from odoo import Command
from odoo.exceptions import AccessError

before = {name: env[name].search_count([]) for name in ("res.partner", "sale.order", "account.move")}
first = apply(env, PROFILE)
counts = {
    name: env[name].search_count([]) for name in ("account.account", "account.tax", "product.pricelist", "ir.default")
}
assert apply(env, PROFILE) == first
assert counts == {name: env[name].search_count([]) for name in counts}
pricelist = env["product.pricelist"].browse(first["pricelist_id"])
original_name = pricelist.name
try:
    apply(env, {**PROFILE, "pricelist_name": "Must roll back", "payment_term_days": 31})
except ValueError:
    pass
else:
    raise AssertionError("Inconsistent payment profile accepted")
assert pricelist.name == original_name
try:
    apply(env, {**PROFILE, "database": "different_database"})
except ValueError:
    pass
else:
    raise AssertionError("Wrong database accepted")
assert before == {name: env[name].search_count([]) for name in before}
env.cr.commit()

company = env.ref(PROFILE["company_xmlid"])
partner = env["res.partner"].create({"name": "Fictional launch customer", "country_id": company.country_id.id})
assert partner.property_product_pricelist == pricelist
assert partner.property_payment_term_id.id == first["payment_term_id"]
product = env["product.product"].create(
    {"name": "Fictional launch service", "type": "service", "invoice_policy": "order", "list_price": 1000}
)
order = env["sale.order"].create(
    {"partner_id": partner.id, "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1})]}
)
assert order.currency_id.name == PROFILE["currency"]
assert (order.amount_untaxed, order.amount_tax, order.amount_total) == (1000, 200, 1200)
assert order.payment_term_id.id == first["payment_term_id"]
order.action_confirm()
invoice = order._create_invoices()
invoice.invoice_date = date(2026, 10, 26)
assert invoice.state == "draft"
assert (invoice.amount_untaxed, invoice.amount_tax, invoice.amount_total) == (1000, 200, 1200)
assert invoice.invoice_date_due == date(2026, 11, 25)

# Billing address wins over both the commercial contact and delivery address.
foreign = env["res.partner"].create({"name": "Fictional foreign billing", "country_id": env.ref("base.fr").id})
unknown = env["res.partner"].create({"name": "Fictional unknown billing"})
export_position = env["account.fiscal.position"].browse(first["export_fiscal_position_id"])
export_tax = env["account.tax"].browse(first["export_sales_tax_id"])
for billing, shipping, expected in [(foreign, partner, 0), (partner, foreign, 200), (unknown, foreign, 200)]:
    quote = env["sale.order"].create(
        {
            "partner_id": partner.id,
            "partner_invoice_id": billing.id,
            "partner_shipping_id": shipping.id,
            "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1})],
        }
    )
    assert quote.amount_tax == expected, (billing.name, quote.amount_tax)
    assert quote.amount_total == 1000 + expected
    if expected == 0:
        assert not billing.vat
        assert quote.order_line.tax_ids == export_tax
        assert PROFILE["export_sales"]["invoice_note"] in str(quote.fiscal_position_id.note)
    quote.action_confirm()
    bill = quote._create_invoices()
    assert bill.partner_id == billing
    assert bill.amount_tax == expected
    assert bill.fiscal_position_id == quote.fiscal_position_id
    assert bill.state == "draft"
    # The native HTML reports carry the fiscal-position note on both documents.
    if expected == 0:
        for report, document in [("sale.report_saleorder", quote), ("account.account_invoices", bill)]:
            html, _kind = env["ir.actions.report"]._render_qweb_html(report, document.ids)
            assert PROFILE["export_sales"]["invoice_note"] in html.decode()

quote = env["sale.order"].create(
    {
        "partner_id": partner.id,
        "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1})],
    }
)
assert quote.amount_tax == 200
quote.partner_invoice_id = foreign
assert quote.fiscal_position_id == export_position
assert quote.amount_tax == 0
quote.partner_invoice_id = partner
assert quote.amount_tax == 200

# Disabling the policy retains native delivery-based selection. Purchases always do.
company.sale_fiscal_by_invoice_address = False
native_position = env["account.fiscal.position"]._get_fiscal_position(partner, foreign)
native = env["sale.order"].create({"partner_id": partner.id, "partner_shipping_id": foreign.id})
assert native.fiscal_position_id == native_position
company.sale_fiscal_by_invoice_address = True
purchase = env["account.move"].create({"move_type": "in_invoice", "partner_id": foreign.id})
assert purchase.fiscal_position_id != export_position

# A normal sales user can read/use the policy but cannot change company settings.
sales_user = env["res.users"].create(
    {
        "name": "Fictional sales user",
        "login": "fiscal-recipe@example.invalid",
        "group_ids": [Command.set([env.ref("sales_team.group_sale_salesman").id])],
        "company_id": company.id,
        "company_ids": [Command.set(company.ids)],
    }
)
assert company.with_user(sales_user)._sale_invoice_fiscal_position(foreign) == export_position
sales_quote = (
    env["sale.order"]
    .with_user(sales_user)
    .create(
        {
            "partner_id": foreign.id,
            "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1})],
        }
    )
)
assert sales_quote.amount_tax == 0
for move_type in ("out_invoice", "out_refund"):
    direct = env["account.move"].create(
        {
            "move_type": move_type,
            "partner_id": foreign.id,
            "partner_shipping_id": partner.id,
            "invoice_line_ids": [Command.create({"product_id": product.id, "quantity": 1, "price_unit": 1000})],
        }
    )
    assert direct.fiscal_position_id == export_position
    assert direct.amount_tax == 0
    assert direct.invoice_line_ids.tax_ids == export_tax

try:
    with env.cr.savepoint():
        company.with_user(sales_user).write({"sale_fiscal_by_invoice_address": False})
except AccessError:
    pass
else:
    raise AssertionError("Sales user can change company fiscal policy")
print("EXPORT_BILLING_POLICY_SMOKE_OK")
env.cr.rollback()
assert before == {name: env[name].search_count([]) for name in before}
print("LAUNCH_SETTINGS_NATIVE_SMOKE_OK")
