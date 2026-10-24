"""Disposable history proof: compare every old business column and genuine PDF byte."""

import hashlib
import json
import os

from odoo import fields
from odoo.tools import SQL
from odoo.tools.binary import BinaryBytes

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S09.3 fixture database only")
key = "training_management_test.s093_snapshot"
phase = os.environ["S093_PHASE"]


def reference(name, record):
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": name, "model": record._name, "res_id": record.id}
    )


def columns():
    env.cr.execute("""SELECT table_name, array_agg(column_name::text ORDER BY ordinal_position)
        FROM information_schema.columns WHERE table_schema='public'
        AND (table_name LIKE 'training_%' OR table_name IN ('survey_user_input', 'survey_user_input_line'))
        GROUP BY table_name ORDER BY table_name""")
    return dict(env.cr.fetchall())


def snapshot(schema):
    env.flush_all()
    result = {}
    for table, names in schema.items():
        projection = SQL(", ").join(SQL.identifier(name) for name in names)
        env.cr.execute(
            SQL(
                "SELECT to_jsonb(t) FROM (SELECT %s FROM %s) t ORDER BY to_jsonb(t)::text",
                projection,
                SQL.identifier(table),
            )
        )
        result[table] = [r[0] for r in env.cr.fetchall()]
    result["pdf"] = {
        str(p.id): hashlib.sha256(p.data.content).hexdigest() for p in env["training.proof"].search([]) if p.data
    }
    env.cr.execute("""SELECT column_name, is_nullable, column_default FROM information_schema.columns
        WHERE table_name='ir_ui_view' AND column_name='visibility'""")
    result["native_view_schema"] = env.cr.fetchall()
    return result


if phase == "prepare":
    dossier = env.ref("training_management_test.s08_dossier")
    actor = dossier.quality_id
    assert dossier.state == "open"
    complaint = (
        env["training.complaint"]
        .with_user(actor)
        .create(
            {
                "name": "Fictional retained S093 complaint",
                "description": "Private original fictional complaint",
                "delivery_id": dossier.delivery_id.id,
                "enrollment_id": dossier.enrollment_id.id,
                "complainant_id": dossier.enrollment_id.participant_id.id,
                "quality_id": actor.id,
                "retention_id": dossier.retention_id.id,
                "due_date": fields.Date.today(),
            }
        )
    )
    complaint.action_start()
    complaint.write({"treatment": "Fictional documented correction", "reply": "Fictional communicable reply"})
    complaint.action_resolve()
    complaint.action_close()
    action = (
        env["training.improvement"]
        .with_user(actor)
        .create(
            {
                "name": "Fictional retained improvement",
                "origin": "complaint",
                "complaint_id": complaint.id,
                "origin_reference": "Fictional source",
                "delivery_id": dossier.delivery_id.id,
                "quality_id": actor.id,
                "retention_id": dossier.retention_id.id,
                "due_date": fields.Date.today(),
                "decision": "Correct the support",
                "effectiveness_criterion": "No recurrence in review",
                "verification_plan": "Review following session",
                "implementation": "Published support",
                "output_reference": "Fictional support v2",
            }
        )
    )
    evidence = (
        env["training.quality.file"]
        .with_user(actor)
        .create(
            {
                "improvement_id": action.id,
                "name": "fictional.txt",
                "source": "Fictional original",
                "data": BinaryBytes(b"Fictional immutable evidence"),
            }
        )
    )
    action.action_plan()
    action.action_implement()
    action.action_check_effectiveness()
    action.action_verify(False, "Fictional recurrence observed", "Rework support and review again")
    proof = (
        env["training.quality.export"]
        .with_user(actor)
        .create(
            {
                "complaint_id": complaint.id,
                "dossier_id": dossier.id,
                "summary": "Approved minimum fictional summary",
            }
        )
        .action_export()
    )
    assert env["training.proof"].browse(proof["res_id"]).data.content.startswith(b"%PDF-")
    reference("s093_complaint", complaint)
    reference("s093_action", action)
    reference("s093_file", evidence)
    print("S093_QUALITY_PREPARED: closed complaint, separately ineffective action, immutable file, genuine S08 PDF")
if phase in ("baseline", "prepare"):
    schema = columns()
    env["ir.config_parameter"].sudo().set_str(
        key, json.dumps({"schema": schema, "data": snapshot(schema)}, default=str, sort_keys=True)
    )
    env.cr.commit()  # Isolated synthetic fixture only.
    print("S093_HISTORY_PREPARED")
else:
    saved = json.loads(env["ir.config_parameter"].sudo().get_str(key))
    assert json.loads(json.dumps(snapshot(saved["schema"]), default=str, sort_keys=True)) == saved["data"]
    print("S093_HISTORY_OK: all previous business rows, quality histories, PDF bytes and native schema retained")
