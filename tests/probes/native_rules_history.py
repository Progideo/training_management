"""Fictional retained documents and queue around native rules migrations."""

import json
import os
from email.utils import parseaddr
from psycopg2 import sql

if env.cr.dbname != "tm_s01_test_s021_native_rules":
    raise RuntimeError("Only the isolated native rules test database is allowed")
params = env["ir.config_parameter"]
key = "training_management.native_rules_history"


def snapshot(table, columns):
    env.cr.execute(
        sql.SQL("SELECT {} FROM {} ORDER BY id").format(
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.Identifier(table),
        )
    )
    return json.dumps(env.cr.fetchall(), default=str, sort_keys=True)


if os.environ["S021_PHASE"] == "prepare":
    assert not params.get_str(key)
    company = env.company
    company.training_notification_address = "previous@example.invalid"
    second = env["res.company"].create(
        {"name": "Fictional second operator", "training_notification_address": "second@example.invalid"}
    )
    export = env["account.fiscal.position"].create({"name": "Fictional former export", "company_id": company.id})
    company.write({"sale_fiscal_by_invoice_address": True, "sale_export_fiscal_position_id": export.id})
    queue = env["mail.mail"]
    for state in ("outgoing", "exception", "sent"):
        queue |= env["mail.mail"].create(
            {
                "subject": "Fictional preserved " + state,
                "email_from": "previous@example.invalid",
                "reply_to": "previous@example.invalid",
                "email_to": "recipient@example.invalid",
                "state": state,
                "auto_delete": False,
                "model": "res.company",
                "res_id": company.id,
            }
        )
    env.flush_all()
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
        "mail_mail",
    ]
    data = {"companies": [company.id, second.id], "export": export.id, "queue": queue.ids, "tables": {}}
    for table in tables:
        env.cr.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
            [table],
        )
        columns = [row[0] for row in env.cr.fetchall()]
        # Relation tables have no id; their complete rows are covered by the existing document probe.
        if "id" in columns:
            data["tables"][table] = {"columns": columns, "rows": snapshot(table, columns)}
    params.set_str(key, json.dumps(data))
    env.cr.commit()
    print("NATIVE_RULES_BASELINE_SAVED")
else:
    data = json.loads(params.get_str(key))
    for table, before in data["tables"].items():
        assert snapshot(table, before["columns"]) == before["rows"], table
    companies = env["res.company"].browse(data["companies"])
    assert len(companies.training_notification_template_id) == 2
    for company in companies:
        identity = env["mail.mail"]._training_identity(company)
        assert parseaddr(identity["email_from"])[1] == company.training_notification_address
        assert identity["reply_to"] == company.training_notification_address
    position = env["account.fiscal.position"].browse(data["export"])
    assert position.auto_apply and position.country_group_id
    assert companies[0].account_fiscal_country_id not in position.country_group_id.country_ids
    count = env["mail.template"].search_count([("id", "in", companies.training_notification_template_id.ids)])
    assert count == 2
    queue = env["mail.mail"].browse(data["queue"])
    assert set(queue.mapped("state")) == {"outgoing", "exception", "sent"}
    identities = json.dumps(
        {
            "templates": companies.training_notification_template_id.ids,
            "country_group": position.country_group_id.id,
            "template_count": env["mail.template"].search_count([("model", "=", "res.company")]),
        },
        sort_keys=True,
    )
    previous = params.get_str(key + ".native_ids")
    if previous:
        assert identities == previous, "Repeated migration changed native configuration identities"
        env.cr.rollback()
    else:
        params.set_str(key + ".native_ids", identities)
        env.cr.commit()  # Test-only marker compared after the second upgrade.
    print("NATIVE_RULES_HISTORY_QUEUE_AND_NATIVE_IDENTITIES_PRESERVED")
