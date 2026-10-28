"""P09.3: preserve accepted native contracts, race two distinct beneficiaries."""

# ruff: noqa: F821 -- env is supplied by the isolated Odoo shell.
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
import os
import threading

from odoo import Command, api, fields
from odoo.exceptions import LockError, ValidationError
from odoo.http.retrying import retrying
from odoo.tools import SQL

if env.cr.dbname != "tm_s01_test_p09":
    raise RuntimeError("Disposable P09 history database only")
phase = os.environ["P09_PHASE"]
params = env["ir.config_parameter"]
key = "training_management_test.p093"


def snapshot():
    env.flush_all()
    result = {}
    for table in (
        "sale_order",
        "sale_order_line",
        "training_seat_allocation",
        "training_enrollment",
        "training_path_assignment",
        "training_path_sale_usage",
        "training_operation",
    ):
        env.cr.execute(SQL("SELECT to_jsonb(t)::text FROM %s t ORDER BY id", SQL.identifier(table)))
        result[table] = hashlib.sha256(json.dumps(env.cr.fetchall()).encode()).hexdigest()
    return result


if phase == "commerce_prepare":
    previous = json.loads(params.get_str("training_management_test.p09"))
    coord = env["res.users"].browse(previous["coord"])
    coord.group_ids = [Command.link(env.ref("sales_team.group_sale_salesman").id)]
    actor = env(user=coord)
    program = env["training.program.version"].browse(previous["program"])
    course = actor["training.course"].create(
        {"name": "Fictional commercial second course", "category_id": program.course_id.category_id.id}
    )
    second = program.copy({"course_id": course.id, "version": "P093"})
    second.action_validate()
    path = actor["training.path"].create(
        {
            "name": "Fictional common commercial group",
            "step_ids": [
                Command.create({"program_id": program.id, "sequence": 10}),
                Command.create({"program_id": second.id, "sequence": 20}),
            ],
        }
    )
    path.action_validate()
    env.ref("base.EUR").active = True
    pricelist = env["product.pricelist"].create({"name": "Fictional agreed EUR", "currency_id": env.ref("base.EUR").id})
    customer = env["res.partner"].create({"name": "Fictional path buyer"})
    order = actor["sale.order"].create({"partner_id": customer.id, "user_id": coord.id, "pricelist_id": pricelist.id})
    wizard = actor["training.path.quote"].create(
        {
            "order_id": order.id,
            "path_id": path.id,
            "request_kind": "individual",
            "attendee_count": 1,
            "price_basis": "package",
        }
    )
    for step in path.step_ids:
        product = env["product.product"].create(
            {
                "name": step.program_id.title,
                "type": "service",
                "company_id": env.company.id,
                "training_course_id": step.course_id.id,
                "training_price_basis": "package",
                "taxes_id": [Command.clear()],
            }
        )
        actor["training.path.quote.line"].create(
            {"wizard_id": wizard.id, "step_id": step.id, "product_id": product.id, "selected": True, "price_unit": 100}
        )
    wizard.action_apply()
    order.action_confirm()
    lots = []
    for line in order.order_line.filtered("training_path_step_id"):
        delivery = actor["training.delivery"].create(
            {
                "name": "Fictional independent path delivery",
                "program_id": line.training_program_id.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 30,
            }
        )
        lot = actor["training.seat.allocation"].create(
            {
                "delivery_id": delivery.id,
                "customer_id": customer.id,
                "quantity": 1,
                "sale_line_id": line.id,
                "source_reference": f"FICT-P093-{line.id}",
                "expires_at": fields.Datetime.now() + timedelta(days=2),
            }
        )
        lot.action_confirm()
        lots.append(lot.id)
    people = env["res.partner"].create([{"name": "Fictional race member A"}, {"name": "Fictional race member B"}])
    saved = {"coord": coord.id, "order": order.id, "lots": lots, "people": people.ids, "snapshot": snapshot()}
    params.set_str(key, json.dumps(saved))
    env.cr.commit()
    print("P093_ACCEPTED_NATIVE_CONTRACT_CAPTURED")
elif phase == "commerce_verify":
    saved = json.loads(params.get_str(key))
    assert snapshot() == saved["snapshot"], "Accepted terms or pedagogical histories changed during update"
    order = env["sale.order"].browse(saved["order"])
    assert order.training_agreed_at and order.amount_untaxed == 200
    print("P093_ACCEPTED_CONTRACT_AND_HISTORIES_IDENTICAL_AFTER_UPDATE")
elif phase == "commerce_concurrency":
    saved = json.loads(params.get_str(key))
    barrier = threading.Barrier(2)
    registry = env.registry
    env.cr.commit()

    def task(index):
        with registry.cursor() as cursor:
            actor = api.Environment(cursor, saved["coord"], {})
            actor.transaction.default_env = actor
            actor["sale.order"].browse(saved["order"]).read(["state"])
            barrier.wait(timeout=30)

            def nominate():
                try:
                    with cursor.savepoint():
                        lot = actor["training.seat.allocation"].browse(saved["lots"][index])
                        return (
                            actor["training.enrollment"]
                            .create(
                                {
                                    "delivery_id": lot.delivery_id.id,
                                    "allocation_id": lot.id,
                                    "participant_id": saved["people"][index],
                                }
                            )
                            .id
                        )
                except (ValidationError, LockError):
                    return False

            return retrying(nominate, actor)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(task, range(2)))
    assert sum(bool(result) for result in results) == 1, results
    with registry.cursor() as cursor:
        actor = api.Environment(cursor, saved["coord"], {})
        rows = actor["training.enrollment"].search([("allocation_id", "in", saved["lots"])])
        assert len(rows) == 1
        assert len(rows.participant_id) == 1
        assert actor["training.path.sale.usage"].search_count([("order_id", "=", saved["order"])]) == 1
        assert rows.access_state == "unopened"
    print("P093_REAL_RACE_DISTINCT_DELIVERIES_ONE_COMMON_BENEFICIARY")
elif phase == "commerce_pdf":
    saved = json.loads(params.get_str(key))
    params.set_str("report.url", os.environ["P09_REPORT_URL"])
    env.cr.commit()
    pdf, kind = env["ir.actions.report"]._render_qweb_pdf("sale.report_saleorder", [saved["order"]])
    assert kind == "pdf" and pdf.startswith(b"%PDF-"), "Native quotation must render a real PDF"
    with open("/var/lib/odoo/p093-quotation.pdf", "wb") as output:
        output.write(pdf)
    print("P093_NATIVE_QUOTATION_PDF_RENDERED_WITH_NATIVE_ASSETS")
else:
    raise RuntimeError("Unknown commercial probe phase")
