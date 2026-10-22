"""COM03: real REPEATABLE READ transactions, run with `odoo shell` in CI.

Only on disposable test databases. Deliberate fixture commits allow independent
connections to see the same records. Never load this probe as an addon test or
run it on an existing development/production database.
"""

from uuid import uuid4

from psycopg2.errors import SerializationFailure

from odoo import Command, api
from odoo.exceptions import ValidationError
from odoo.tests import new_test_user

if not env.cr.dbname.startswith(("tm_s01_test_", "tm_s02_test_")):  # noqa: F821
    raise RuntimeError("Only disposable training test databases are allowed.")

suffix = uuid4().hex[:10]
company = env["res.company"].create({"name": "Fictional Concurrent " + suffix})
finance = new_test_user(
    env,
    login="fictional_concurrent_" + suffix,
    groups="account.group_account_invoice",
    company_id=company.id,
    company_ids=[Command.set(company.ids)],
)
accounts = {}
for code, kind, reconcile in (
    ("510", "asset_cash", False),
    ("341", "asset_current", True),
    ("340", "asset_receivable", True),
):
    accounts[code] = (
        env["account.account"]
        .with_company(company)
        .create(
            {
                "name": "Fictional Concurrent " + code,
                "code": code,
                "account_type": kind,
                "reconcile": reconcile,
                "company_ids": [Command.set(company.ids)],
            }
        )
    )
partner = env["res.partner"].create({"name": "Fictional Concurrent Buyer"})
partner.with_company(company).property_account_receivable_id = accounts["340"]
journal = (
    env["account.journal"]
    .with_company(company)
    .create(
        {
            "name": "Fictional Concurrent Bank",
            "code": "FXC",
            "type": "bank",
            "company_id": company.id,
            "default_account_id": accounts["510"].id,
        }
    )
)
method = journal.inbound_payment_method_line_ids.filtered(lambda m: m.code == "manual")
method.payment_account_id = accounts["341"]
values = {
    "partner_id": partner.id,
    "company_id": company.id,
    "journal_id": journal.id,
    "payment_method_line_id": method.id,
    "payment_type": "inbound",
    "partner_type": "customer",
    "amount": 10,
    "currency_id": company.currency_id.id,
    "training_bank_reference": "FICTIONAL-CONCURRENT-" + suffix.upper(),
    "training_bank_verified": True,
}
payments = env["account.payment"].with_user(finance).with_company(company).create([values.copy(), values.copy()])
env.cr.commit()
context = {"allowed_company_ids": company.ids}
domain = [("id", "in", payments.ids), ("state", "in", ("paid", "reconciled"))]
with env.registry.cursor() as first, env.registry.cursor() as second:
    e1 = api.Environment(first, finance.id, context)
    e2 = api.Environment(second, finance.id, context)
    for cr, current in ((first, e1), (second, e2)):
        cr.execute("SHOW transaction_isolation")
        assert cr.fetchone()[0] == "repeatable read"
        assert not current.su
        assert current["account.payment"].search_count(domain) == 0
    e1["account.payment"].browse(payments[0].id).action_post()
    first.commit()
    try:
        e2["account.payment"].browse(payments[1].id).action_post()
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A stale snapshot must not validate the second payment")
# Inspect committed results using an independent snapshot, never the seed env.
with env.registry.cursor() as third:
    e3 = api.Environment(third, finance.id, context)
    paid = e3["account.payment"].search(domain)
    assert paid.ids == payments[:1].ids
    assert paid.move_id.state == "posted"
    assert paid.training_bank_verified_by_id.id == finance.id
    retry = e3["account.payment"].browse(payments[1].id)
    try:
        with third.savepoint():
            retry.action_post()
    except ValidationError:
        pass
    else:
        raise AssertionError("A full retry must detect the already committed reference")
    assert retry.state == "draft" and not retry.move_id
    retry.write({"training_duplicate_reference_reason": "Intentional allocation to another invoice"})
    retry.action_post()
    third.commit()
with env.registry.cursor() as fourth:
    e4 = api.Environment(fourth, finance.id, context)
    paid = e4["account.payment"].search(domain)
    assert len(paid) == 2
    assert len(paid.filtered("training_duplicate_reference_reason")) == 1
print("TRAINING_CONCURRENCY_OK: stale snapshot rejected; fresh retry refused; motivated split accepted")
env.cr.rollback()
