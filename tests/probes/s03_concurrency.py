"""INS01/02: independent REPEATABLE READ transactions on disposable databases only.

Deliberate fixture commits are restricted to this standalone probe; no production
method commits. Run using odoo shell, never against neopro_dev or production.
"""

from datetime import timedelta
from uuid import uuid4

from psycopg2.errors import SerializationFailure
from odoo import Command, api, fields
from odoo.exceptions import LockError, ValidationError
from odoo.tests import new_test_user

if not env.cr.dbname.startswith("tm_s03_test_"):  # noqa: F821
    raise RuntimeError("Only disposable S03 test databases are allowed")

suffix = uuid4().hex[:8]
company = env.company
coordinator = new_test_user(
    env,
    login="s03_race_" + suffix,
    groups="training_management.group_training_coordinator,sales_team.group_sale_salesman",
    company_id=company.id,
    company_ids=[Command.set(company.ids)],
)
customer = env["res.partner"].create({"name": "Fictional S03 race buyer " + suffix})
people = env["res.partner"].create(
    [{"name": "Fictional S03 race A " + suffix}, {"name": "Fictional S03 race B " + suffix}]
)
course = env["training.course"].create({"name": "Fictional S03 race " + suffix})
program = env["training.program.version"].create(
    {
        "course_id": course.id,
        "version": suffix,
        "title": "Fictional concurrent programme",
        "objectives": "Practice",
        "target_audience": "Beginners",
        "prerequisites": "Reviewed",
        "content": "Workshop",
        "duration_hours": 2,
        "delivery_mode": "elearning",
        "language_id": env.ref("base.lang_en").id,
        "teaching_methods": "Practice",
        "evaluation_criteria": "Review",
        "access_conditions": "Manual",
        "accessibility_contact_id": customer.id,
        "accessibility_information": "Contact us",
    }
)
program.action_validate()
context = {"allowed_company_ids": company.ids}
restricted = env(user=coordinator, context=context)


def delivery(capacity=1):
    return restricted["training.delivery"].create(
        {
            "name": "Fictional S03 concurrency " + suffix,
            "program_id": program.id,
            "kind": "autonomous",
            "capacity": capacity,
            "access_policy": "duration",
            "access_days": 2,
        }
    )


first_delivery = delivery()
entries = restricted["training.enrollment"].create(
    [
        {"delivery_id": first_delivery.id, "participant_id": person.id, "free_reason": "Fictional invitation"}
        for person in people
    ]
)
entries.action_validate_prerequisites(reason="Review")
duplicate_delivery = delivery(10)
commercial_deliveries = delivery() | delivery()
product = (
    env["product.template"]
    .create(
        {
            "name": "Fictional race package " + suffix,
            "type": "service",
            "company_id": company.id,
            "training_course_id": course.id,
            "training_price_basis": "package",
            "taxes_id": [Command.clear()],
        }
    )
    .product_variant_id
)
currency = env.ref("base.EUR")
currency.active = True
pricelist = env["product.pricelist"].create({"name": "Fictional race EUR " + suffix, "currency_id": currency.id})
env["product.pricelist.item"].create(
    {
        "pricelist_id": pricelist.id,
        "product_tmpl_id": product.product_tmpl_id.id,
        "applied_on": "1_product",
        "compute_price": "fixed",
        "fixed_price": 100,
    }
)
order = restricted["sale.order"].create(
    {
        "partner_id": customer.id,
        "user_id": coordinator.id,
        "pricelist_id": pricelist.id,
        "training_request_kind": "group",
        "training_attendee_count": 1,
        "training_requested_program_id": program.id,
        "training_requested_currency_id": currency.id,
        "order_line": [
            Command.create(
                {"product_id": product.id, "product_uom_qty": 1, "price_unit": 100, "training_program_id": program.id}
            )
        ],
    }
)
order.action_confirm()
line_id = order.order_line.id
# Only synthetic probe fixtures are committed, making them visible to both cursors.
env.cr.commit()

with env.registry.cursor() as first, env.registry.cursor() as second:
    e1 = api.Environment(first, coordinator.id, context)
    e2 = api.Environment(second, coordinator.id, context)
    for cr, current in ((first, e1), (second, e2)):
        cr.execute("SHOW transaction_isolation")
        assert cr.fetchone()[0] == "repeatable read"
        assert not current.su
        assert (
            current["training.enrollment"].search_count(
                [("delivery_id", "=", first_delivery.id), ("state", "=", "confirmed")]
            )
            == 0
        )
    e1["training.enrollment"].browse(entries[0].id).action_confirm()
    try:
        e2["training.enrollment"].browse(entries[1].id).action_confirm()
    except LockError:
        pass
    else:
        raise AssertionError("A held delivery lock must reject the competing confirmation")
    first.commit()
    try:
        e2["training.enrollment"].browse(entries[1].id).action_confirm()
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A stale snapshot must not take the already committed last place")
with env.registry.cursor() as retry:
    current = api.Environment(retry, coordinator.id, context)
    try:
        current["training.enrollment"].browse(entries[1].id).action_confirm()
    except ValidationError:
        pass
    else:
        raise AssertionError("A fresh retry must report the exhausted capacity")
    assert (
        current["training.enrollment"].search_count(
            [("delivery_id", "=", first_delivery.id), ("state", "=", "confirmed")]
        )
        == 1
    )

with env.registry.cursor() as first, env.registry.cursor() as second:
    e1, e2 = [api.Environment(cr, coordinator.id, context) for cr in (first, second)]
    values = {
        "delivery_id": duplicate_delivery.id,
        "participant_id": people[0].id,
        "free_reason": "Fictional invitation",
    }
    for current in (e1, e2):
        assert not current["training.enrollment"].search_count([("delivery_id", "=", duplicate_delivery.id)])
    e1["training.enrollment"].create(values)
    first.commit()
    try:
        e2["training.enrollment"].create(values)
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Concurrent identity creation needs a fresh snapshot")
with env.registry.cursor() as retry:
    current = api.Environment(retry, coordinator.id, context)
    try:
        current["training.enrollment"].create(values)
    except ValidationError:
        pass
    else:
        raise AssertionError("Duplicate identity must be refused on fresh retry")

with env.registry.cursor() as first, env.registry.cursor() as second:
    e1, e2 = [api.Environment(cr, coordinator.id, context) for cr in (first, second)]
    for current in (e1, e2):
        assert not current["training.seat.allocation"].search_count([("sale_line_id", "=", line_id)])
    values = {
        "customer_id": customer.id,
        "quantity": 1,
        "source_reference": "FICTIONAL-" + suffix,
        "sale_line_id": line_id,
        "expires_at": fields.Datetime.now() + timedelta(days=1),
    }
    e1["training.seat.allocation"].create({**values, "delivery_id": commercial_deliveries[0].id})
    first.commit()
    try:
        e2["training.seat.allocation"].create({**values, "delivery_id": commercial_deliveries[1].id})
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("The same commercial entitlement cannot be allocated twice across deliveries")
with env.registry.cursor() as retry:
    current = api.Environment(retry, coordinator.id, context)
    try:
        current["training.seat.allocation"].create({**values, "delivery_id": commercial_deliveries[1].id})
    except ValidationError:
        pass
    else:
        raise AssertionError("Fresh retry must refuse the exhausted commercial entitlement")
print("S03_CONCURRENCY_OK: held lock, stale snapshots, last place, identity and cross-delivery commercial entitlement")
env.cr.rollback()
