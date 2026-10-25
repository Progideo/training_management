"""S10 -> S11: retain evidence, attachments, holds and existing journals."""
# ruff: noqa: F821 -- env is provided by the disposable Odoo shell.

import hashlib
import json
import os

from odoo.tests import new_test_user
from odoo.tools import SQL

if env.cr.dbname != "tm_s01_test_s11":
    raise RuntimeError("Disposable S11 history database only")
phase = os.environ["S11_PHASE"]
key = "training_management_test.s11_history"


def schema():
    env.cr.execute("""SELECT table_name,array_agg(column_name::text ORDER BY ordinal_position)
        FROM information_schema.columns WHERE table_schema='public'
        AND (table_name LIKE 'training_%' OR table_name LIKE 'survey_%'
             OR table_name IN ('res_users','res_partner','res_company','sale_order','sale_order_line','account_move','account_move_line','account_payment','ir_attachment'))
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

        # psycopg returns bytea as memoryview: str(value) includes a process
        # address and changes even for identical bytes. Hash the actual bytes.
        def stable(value):
            return (
                hashlib.sha256(value).hexdigest() if isinstance(value, (bytes, bytearray, memoryview)) else str(value)
            )

        result[table] = hashlib.sha256(
            json.dumps(sorted(json.dumps(row, default=stable, sort_keys=True) for row in env.cr.fetchall())).encode()
        ).hexdigest()
    return result


if phase == "baseline":
    user = new_test_user(
        env,
        login="s11_migration_coord",
        groups="training_management.group_training_coordinator,training_management.group_training_quality,base.group_allow_export",
    )
    course = env["training.course"].with_user(user).create({"name": "Fictional S11 migration"})
    course.category_id = env["training.category"].with_user(user).create({"name": "Fictional category"})
    program = (
        env["training.program.version"]
        .with_user(user)
        .create(
            {
                "course_id": course.id,
                "version": "S11-HISTORY",
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
    adaptation = (
        env["training.adaptation"]
        .with_user(user)
        .create(
            {
                "delivery_id": delivery.id,
                "enrollment_id": enrollment.id,
                "details": "Fictional confidential requirement",
                "decision": "Fictional decision",
            }
        )
    )
    attachment = (
        env["ir.attachment"]
        .with_user(user)
        .create(
            {
                "name": "fictional-confidential.pdf",
                "res_model": adaptation._name,
                "res_id": adaptation.id,
                "raw": program.pdf_attachment_id.raw.content,
            }
        )
    )
    policy = (
        env["training.retention.category"]
        .with_user(user)
        .create(
            {
                "name": "Fictional retention",
                "purpose": "Migration fixture",
                "responsible_id": user.id,
                "duration_days": 365,
                "archive_policy": "Restricted archive",
                "deletion_policy": "Human review only",
            }
        )
    )
    policy.action_approve()
    dossier = (
        env["training.closure"]
        .with_user(user)
        .create(
            {
                "enrollment_id": enrollment.id,
                "quality_id": user.id,
                "retention_id": policy.id,
            }
        )
    )
    enrollment.export_data(["id", "state"])
    adaptation.export_data(["details"])
    env["training.dashboard.line"].with_user(user).browse(enrollment.id).export_data(["name", "state"])
    dossier.action_export_internal()
    document = env["training.document"].search([("dossier_id", "=", dossier.id)], limit=1)
    files = {
        "attachment": hashlib.sha256(attachment.raw.content).hexdigest(),
        "program": hashlib.sha256(program.pdf_attachment_id.raw.content).hexdigest(),
        "archive": hashlib.sha256(document.data.content).hexdigest(),
    }
    columns = schema()
    env["ir.config_parameter"].create(
        {
            "key": key,
            "value": json.dumps(
                {
                    "notices": env["training.notification"].search_count([]),
                    "requests": env["training.request.notice"].search_count([]),
                    "attachment": attachment.id,
                    "dossier": dossier.id,
                    "document": document.id,
                    "files": files,
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
    print("S11_BASELINE_HISTORY_READY")
elif phase == "verify":
    saved = json.loads(env["ir.config_parameter"].search([("key", "=", key)]).value)
    actual = fingerprints(saved["columns"])
    changed = [table for table, expected in saved["fingerprints"].items() if actual[table] != expected]
    assert not changed, "Retained table fingerprints changed: %s" % changed
    assert visibility_schema() == saved["visibility"]
    assert env["training.notification"].search_count([]) == saved["notices"]
    assert env["training.request.notice"].search_count([]) == saved["requests"]
    user = env["res.users"].browse(saved["user"])
    lines = env["training.dashboard.line"].with_user(user).search([])
    assert lines.ids == [saved["enrollment"]]
    data = env["training.dashboard.service"].with_user(user)._dashboard(saved["delivery"])
    assert data["population"] == 1 and data["rows"][0]["attendance_na"]
    assert env["training.closure"].browse(saved["dossier"]).frozen
    assert (
        hashlib.sha256(env["ir.attachment"].browse(saved["attachment"]).raw.content).hexdigest()
        == saved["files"]["attachment"]
    )
    assert (
        hashlib.sha256(
            env["training.enrollment"].browse(saved["enrollment"]).program_id.pdf_attachment_id.raw.content
        ).hexdigest()
        == saved["files"]["program"]
    )
    assert (
        hashlib.sha256(env["training.document"].browse(saved["document"]).data.content).hexdigest()
        == saved["files"]["archive"]
    )
    assert env["training.export.audit"].search_count([]) == 0
    assert len(lines.read(["name", "state", "details"])) == 1
    print("S11_HISTORY_FILES_HOLDS_AND_JOURNALS_PRESERVED")
else:
    raise RuntimeError("Unknown S11 history phase")
