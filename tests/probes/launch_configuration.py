"""Native launch contract, using only fictional data in the isolated CI database."""

from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, ValidationError

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
eur = env.ref("base.EUR")
eur_prices = env["product.pricelist"].create(
    {"name": "Fictional EUR", "currency_id": eur.id, "company_id": env.ref(PROFILE["company_xmlid"]).id}
)

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
            "pricelist_id": eur_prices.id if billing == foreign else pricelist.id,
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
quote.write({"partner_invoice_id": foreign.id, "pricelist_id": eur_prices.id})
assert quote.fiscal_position_id == export_position
assert quote.amount_tax == 200  # RPC does not silently overwrite existing line taxes.
quote._recompute_taxes()
assert quote.amount_tax == 0
quote.write({"partner_invoice_id": partner.id, "pricelist_id": pricelist.id})
quote._recompute_taxes()
assert quote.amount_tax == 200

# Disabling the policy retains native delivery-based selection. Purchases always do.
company.sale_fiscal_by_invoice_address = False
native_position = env["account.fiscal.position"]._get_fiscal_position(partner, foreign)
native = env["sale.order"].create({"partner_id": partner.id, "partner_shipping_id": foreign.id})
assert native.fiscal_position_id == native_position
company.sale_fiscal_by_invoice_address = True
purchase = env["account.move"].create({"move_type": "in_invoice", "partner_id": foreign.id})
assert purchase.fiscal_position_id == env["account.fiscal.position"]._get_fiscal_position(foreign, foreign)

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
            "pricelist_id": eur_prices.id,
            "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1})],
        }
    )
)
assert sales_quote.amount_tax == 0
for move_type in ("out_invoice", "out_refund"):
    direct = env["account.move"].create(
        {
            "move_type": move_type,
            "currency_id": eur.id,
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


def must_reject(operation):
    try:
        with env.cr.savepoint():
            operation()
    except ValidationError:
        return
    raise AssertionError("Forbidden domestic currency was accepted")


assert company.sale_domestic_currency_ids == company.currency_id
assert company.sale_foreign_currency_ids == eur
for billing, prices, tax_amount in [(partner, pricelist, 20), (foreign, eur_prices, 0)]:
    allowed = env["sale.order"].create(
        {
            "partner_id": partner.id,
            "partner_invoice_id": billing.id,
            "partner_shipping_id": partner.id,
            "pricelist_id": prices.id,
            "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1, "price_unit": 100})],
        }
    )
    assert allowed.currency_id == prices.currency_id
    assert (allowed.amount_untaxed, allowed.amount_tax, allowed.amount_total) == (100, tax_amount, 100 + tax_amount)
    allowed.action_confirm()
    allowed_invoice = allowed._create_invoices()
    allowed_invoice.invoice_date = date(2026, 10, 26)
    assert allowed_invoice.currency_id == prices.currency_id
    assert allowed_invoice.amount_total == 100 + tax_amount
    allowed_invoice._post()
    assert allowed_invoice.state == "posted"

must_reject(
    lambda: (
        env["sale.order"]
        .with_user(sales_user)
        .create(
            {
                "partner_id": foreign.id,
                "partner_invoice_id": partner.id,
                "partner_shipping_id": foreign.id,
                "pricelist_id": eur_prices.id,
            }
        )
    )
)
must_reject(lambda: quote.write({"pricelist_id": eur_prices.id}))
foreign_quote = env["sale.order"].create({"partner_id": foreign.id, "pricelist_id": eur_prices.id})
must_reject(lambda: foreign_quote.write({"partner_invoice_id": partner.id}))
for kind in ("out_invoice", "out_refund"):
    must_reject(
        lambda: env["account.move"].create({"move_type": kind, "partner_id": partner.id, "currency_id": eur.id})
    )
    permitted = env["account.move"].create({"move_type": kind, "partner_id": foreign.id, "currency_id": eur.id})
    must_reject(lambda: permitted.write({"partner_id": partner.id}))
must_reject(lambda: invoice.write({"currency_id": eur.id}))

# A later country change on a contact is caught at both workflow boundaries.
late_partner = env["res.partner"].create({"name": "Fictional changing address", "country_id": foreign.country_id.id})
late_quote = env["sale.order"].create({"partner_id": late_partner.id, "pricelist_id": eur_prices.id})
late_invoice = env["account.move"].create(
    {"move_type": "out_invoice", "partner_id": late_partner.id, "currency_id": eur.id}
)
late_partner.country_id = partner.country_id
must_reject(lambda: late_quote.action_confirm())
must_reject(lambda: late_invoice._post())
assert late_quote.state == "draft" and late_invoice.state == "draft"

# Purchases are out of scope. Company policy is explicit, not a global EUR ban.
env["account.move"].create({"move_type": "in_invoice", "partner_id": partner.id, "currency_id": eur.id})
other_company = env["res.company"].create({"name": "Fictional other operator", "country_id": partner.country_id.id})
assert not other_company.sale_domestic_currency_ids and not other_company.sale_foreign_currency_ids
other_company._check_sale_invoice_currency(partner, eur)
try:
    with env.cr.savepoint():
        company.with_user(sales_user).write({"sale_domestic_currency_ids": [Command.clear()]})
except AccessError:
    pass
else:
    raise AssertionError("Sales user can remove currency guard")
must_reject(lambda: env["sale.order"].create({"partner_id": foreign.id, "pricelist_id": pricelist.id}))
must_reject(lambda: foreign_quote.write({"pricelist_id": pricelist.id}))
for kind in ("out_invoice", "out_refund"):
    must_reject(
        lambda: env["account.move"].create(
            {"move_type": kind, "partner_id": foreign.id, "currency_id": company.currency_id.id}
        )
    )
# Same guard in the other direction after a contact country change.
late_partner.country_id = foreign.country_id
local_quote = env["sale.order"].create({"partner_id": partner.id})
local_invoice = env["account.move"].create({"move_type": "out_invoice", "partner_id": partner.id})
# Changing the invoice partner and currency together preserves an authorized export.
local_quote.write({"partner_invoice_id": foreign.id, "pricelist_id": eur_prices.id})
local_invoice.write({"partner_id": foreign.id, "currency_id": eur.id})
assert local_quote.currency_id == eur and local_invoice.currency_id == eur
late_local = env["res.partner"].create(
    {"name": "Fictional local changing address", "country_id": partner.country_id.id}
)
local_stored_quote = env["sale.order"].create({"partner_id": late_local.id})
local_stored_invoice = env["account.move"].create({"move_type": "out_invoice", "partner_id": late_local.id})
late_local.country_id = foreign.country_id
must_reject(lambda: local_stored_quote.action_confirm())
must_reject(lambda: local_stored_invoice._post())

# Policy activation preserves a pre-existing, now incompatible draft.
company.sale_foreign_currency_ids = False
legacy_quote = env["sale.order"].create({"partner_id": foreign.id})
legacy_invoice = env["account.move"].create({"move_type": "out_invoice", "partner_id": foreign.id})
legacy_amounts = (legacy_quote.amount_total, legacy_invoice.amount_total)
company.sale_foreign_currency_ids = eur
assert legacy_quote.state == "draft" and legacy_invoice.state == "draft"
assert legacy_amounts == (legacy_quote.amount_total, legacy_invoice.amount_total)
must_reject(lambda: legacy_quote.action_confirm())
must_reject(lambda: legacy_invoice._post())
print("SALES_CURRENCY_GUARD_SMOKE_OK")

print("EXPORT_BILLING_POLICY_SMOKE_OK")
env.cr.rollback()
assert before == {name: env[name].search_count([]) for name in before}
print("LAUNCH_SETTINGS_NATIVE_SMOKE_OK")
