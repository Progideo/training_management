"""V2 conservation: compare original columns/rows, including all bank audit metadata."""

import json
import os

from psycopg2 import sql

from odoo import Command

if env.cr.dbname != "tm_s01_test_s021_native_commercial":
    raise RuntimeError("Only the disposable native commercial upgrade database is allowed")
params = env["ir.config_parameter"]
key = "training_management.native_commercial_history"


def rows(table, columns):
    env.cr.execute(
        sql.SQL("SELECT {} FROM {} ORDER BY 1").format(
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.Identifier(table),
        )
    )
    return json.dumps(sorted(json.dumps(row, default=str, sort_keys=True) for row in env.cr.fetchall()))


if os.environ["S021_PHASE"] == "prepare":
    assert not params.get_str(key), "Do not overwrite V2 evidence"
    # Seed a valid V2 declaration before replacing its related currency by a snapshot.
    program = env.ref("training_management_test.upgrade_program")
    product = env["product.product"].create(
        {
            "name": "Fictional historical notice service",
            "type": "service",
            "company_id": env.company.id,
            "training_course_id": program.course_id.id,
            "training_price_basis": "package",
            "taxes_id": [Command.clear()],
        }
    )
    pricelist = env["product.pricelist"].create(
        {
            "name": "Fictional historical notice EUR",
            "currency_id": env.ref("base.EUR").id,
        }
    )
    order = env["sale.order"].create(
        {
            "partner_id": env["res.partner"].create({"name": "Fictional historical notice buyer"}).id,
            "pricelist_id": pricelist.id,
            "training_request_kind": "group",
            "training_requested_program_id": program.id,
            "training_requested_currency_id": env.ref("base.EUR").id,
            "training_attendee_count": 1,
            "training_price_source": "quote",
            "order_line": [
                Command.create(
                    {
                        "product_id": product.id,
                        "training_program_id": program.id,
                        "product_uom_qty": 1,
                        "price_unit": 100,
                    }
                )
            ],
        }
    )
    order.action_confirm()
    env["training.bank.transfer.notice"].create(
        {
            "order_id": order.id,
            "amount": 30,
            "claimed_date": "2026-10-20",
            "reference": "HISTORICAL-NATIVE-COMMERCIAL",
        }
    )
    env.cr.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'training_%'")
    tables = [row[0] for row in env.cr.fetchall()]
    tables += [
        "sale_order",
        "sale_order_line",
        "account_move",
        "account_move_line",
        "account_payment",
        "account_partial_reconcile",
        "account_full_reconcile",
    ]
    snapshot = {}
    for table in tables:
        env.cr.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s "
            "ORDER BY ordinal_position",
            [table],
        )
        columns = [row[0] for row in env.cr.fetchall()]
        snapshot[table] = {"columns": columns, "rows": rows(table, columns)}
    params.set_str(key, json.dumps(snapshot))
    env.cr.commit()  # Fictional fixture evidence for separate upgrade processes.
    print("NATIVE_COMMERCIAL_V2_SNAPSHOT_PERSISTED")
else:
    for table, expected in json.loads(params.get_str(key)).items():
        assert rows(table, expected["columns"]) == expected["rows"], "Historical rows changed: " + table
    payment = env["account.payment"].search([("training_bank_reference", "=", "HISTORICAL-S021")])
    assert len(payment) == 1 and payment.training_receipt_restricted
    assert not env.ref("training_management_sale.view_account_payment_register_form_training").active
    print("NATIVE_COMMERCIAL_V2_ROWS_AUDIT_AND_PRIVACY_PRESERVED")
    env.cr.rollback()
