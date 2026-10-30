"""V2 conservation: compare original columns/rows, including all bank audit metadata."""

import json
import os

from psycopg2 import sql

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
