"""S09.4 -> S10: no retrospective notices; preserve existing business columns."""
# ruff: noqa: F821 -- env is provided by the disposable Odoo shell.

import hashlib
import json
import os

from odoo.tests import new_test_user
from odoo.tools import SQL

if env.cr.dbname != "tm_s01_test_s10":
    raise RuntimeError("Disposable S10 history database only")
phase = os.environ["S10_PHASE"]
key = "training_management_test.s10_history"


def schema():
    env.cr.execute("""SELECT table_name,array_agg(column_name::text ORDER BY ordinal_position)
        FROM information_schema.columns WHERE table_schema='public'
        AND (table_name LIKE 'training_%' OR table_name LIKE 'survey_%'
             OR table_name IN ('res_users','res_partner','res_company','sale_order','sale_order_line','account_move','account_move_line','account_payment'))
        AND table_name IN (SELECT tablename FROM pg_tables WHERE schemaname='public') GROUP BY table_name ORDER BY table_name""")
    return dict(env.cr.fetchall())


def visibility_schema():
    env.cr.execute("""SELECT a.attnotnull,pg_get_expr(d.adbin,d.adrelid)
        FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE a.attrelid='ir_ui_view'::regclass AND a.attname='visibility'""")
    return list(env.cr.fetchone())


def fingerprints(columns):
    env.flush_all()
    result = {}
    for table, names in columns.items():
        env.cr.execute(SQL("SELECT %s FROM %s", SQL(",").join(map(SQL.identifier, names)), SQL.identifier(table)))
        result[table] = hashlib.sha256(
            json.dumps(sorted(json.dumps(row, default=str, sort_keys=True) for row in env.cr.fetchall())).encode()
        ).hexdigest()
    return result


if phase == "baseline":
    user = new_test_user(env, login="s10_migration_coord", groups="training_management.group_training_coordinator")
    course = env["training.course"].with_user(user).create({"name": "Fictional S10 migration"})
    course.category_id = env["training.category"].with_user(user).create({"name": "Fictional category"})
    program = (
        env["training.program.version"]
        .with_user(user)
        .create(
            {
                "course_id": course.id,
                "version": "S10-HISTORY",
                "title": "Fictional historical programme",
                "objectives": "Practice",
                "target_audience": "Testers",
                "prerequisites": "None",
                "content": "Fictional",
                "duration_hours": 7,
                "delivery_mode": "elearning",
                "language_id": env.ref("base.lang_en").id,
                "teaching_methods": "Practice",
                "evaluation_criteria": "Observation",
                "access_conditions": "Manual",
                "accessibility_contact_id": user.partner_id.id,
                "accessibility_information": "Fictional contact",
            }
        )
    )
    program.action_validate()
    delivery = (
        env["training.delivery"]
        .with_user(user)
        .create(
            {
                "name": "Fictional history delivery",
                "program_id": program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 10,
            }
        )
    )
    enrollment = (
        env["training.enrollment"]
        .with_user(user)
        .create(
            {
                "delivery_id": delivery.id,
                "participant_id": user.partner_id.id,
                "user_id": user.id,
                "free_reason": "Fictional",
            }
        )
    )
    enrollment.action_validate_prerequisites(reason="Fictional")
    enrollment.action_confirm()
    columns = schema()
    env["ir.config_parameter"].create(
        {
            "key": key,
            "value": json.dumps(
                {
                    "columns": columns,
                    "fingerprints": fingerprints(columns),
                    "visibility": visibility_schema(),
                    "user": user.id,
                    "delivery": delivery.id,
                    "enrollment": enrollment.id,
                }
            ),
        }
    )
    env.cr.commit()
    print("S10_BASELINE_HISTORY_READY")
elif phase == "verify":
    saved = json.loads(env["ir.config_parameter"].search([("key", "=", key)]).value)
    assert fingerprints(saved["columns"]) == saved["fingerprints"]
    assert visibility_schema() == saved["visibility"]
    assert env["training.notification"].search_count([]) == 0
    assert env["training.request.notice"].search_count([]) == 0
    user = env["res.users"].browse(saved["user"])
    lines = env["training.dashboard.line"].with_user(user).search([])
    assert lines.ids == [saved["enrollment"]]
    data = env["training.dashboard.service"].with_user(user)._dashboard(saved["delivery"])
    assert data["population"] == 1 and data["rows"][0]["attendance_na"]
    assert data["notifications"] == []
    assert len(lines.read(["name", "state", "details"])) == 1
    print("S10_ALL_PREEXISTING_COLUMNS_PRESERVED_NO_RETROSPECTIVE_NOTICES")
else:
    raise RuntimeError("Unknown S10 history phase")
