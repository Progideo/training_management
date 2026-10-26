"""Native launch contract, using only fictional data in the isolated CI database."""

from datetime import date

from odoo import Command

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
env.cr.rollback()
assert before == {name: env[name].search_count([]) for name in before}
print("LAUNCH_SETTINGS_NATIVE_SMOKE_OK")
