"""S09.3 -> S09.4, immutable provider files and independent-transaction races."""

import hashlib
import json
import os

from psycopg2.errors import SerializationFailure
from odoo import Command, api, fields
from odoo.exceptions import AccessError, LockError
from odoo.tests import new_test_user
from odoo.tools import SQL
from odoo.tools.binary import BinaryBytes

if env.cr.dbname != "tm_s01_test_s094":
    raise RuntimeError("Disposable S09.4 fixture database only")
phase = os.environ["S094_PHASE"]
key = "training_management_test.s094_snapshot"


def save_reference(name, row):
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": name, "model": row._name, "res_id": row.id}
    )


def schema():
    env.cr.execute("""SELECT table_name, array_agg(column_name::text ORDER BY ordinal_position)
        FROM information_schema.columns WHERE table_schema='public' AND table_name LIKE 'training_%'
        GROUP BY table_name ORDER BY table_name""")
    return dict(env.cr.fetchall())


def snapshot(columns):
    env.flush_all()
    result = {}
    for table, names in columns.items():
        env.cr.execute(
            SQL(
                "SELECT to_jsonb(t) FROM (SELECT %s FROM %s) t ORDER BY to_jsonb(t)::text",
                SQL(", ").join(SQL.identifier(n) for n in names),
                SQL.identifier(table),
            )
        )
        result[table] = [r[0] for r in env.cr.fetchall()]
    if "training_provider_evidence" in columns:
        result["evidence_bytes"] = {
            str(r.id): hashlib.sha256(r.data.content).hexdigest() for r in env["training.provider.evidence"].search([])
        }
    env.cr.execute("""SELECT a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
        FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE a.attrelid='ir_ui_view'::regclass AND a.attname='visibility'""")
    result["native_view_schema"] = env.cr.fetchone()
    return result


if phase == "baseline":
    quality = new_test_user(env, login="fictional_s094_quality", groups="training_management.group_training_quality")
    staff = new_test_user(
        env, login="fictional_s094_coordinator", groups="training_management.group_training_coordinator"
    )
    partner = env["res.partner"].create({"name": "Fictional existing instructor"})
    retention = (
        env["training.retention.category"]
        .with_user(quality)
        .create(
            {
                "name": "Fictional approved policy",
                "purpose": "Provider evidence",
                "responsible_id": quality.id,
                "duration_days": 365,
                "archive_policy": "Restricted archive",
                "deletion_policy": "Manual review",
            }
        )
    )
    retention.action_approve()
    for name, row in (
        ("s094_quality", quality),
        ("s094_staff", staff),
        ("s094_partner", partner),
        ("s094_retention", retention),
    ):
        save_reference(name, row)
    complaint = (
        env["training.complaint"]
        .with_user(quality)
        .create(
            {
                "name": "Fictional retained S093 complaint",
                "description": "Original private S093 account",
                "complainant_id": partner.id,
                "quality_id": quality.id,
                "retention_id": retention.id,
                "due_date": fields.Date.today(),
            }
        )
    )
    env["training.quality.file"].with_user(quality).create(
        {
            "complaint_id": complaint.id,
            "name": "old-s093.txt",
            "source": "Original S093 issuer",
            "data": BinaryBytes(b"Immutable S093 original"),
        }
    )
    complaint.action_start()
    complaint.write({"treatment": "Fictional correction", "reply": "Communicable fictional reply"})
    complaint.action_resolve()
    complaint.action_close()
    improvement = (
        env["training.improvement"]
        .with_user(quality)
        .create(
            {
                "name": "Retained S093 improvement",
                "origin": "review",
                "origin_reference": "Original S093 quality review",
                "quality_id": quality.id,
                "retention_id": retention.id,
                "due_date": fields.Date.today(),
                "decision": "Correct support",
                "effectiveness_criterion": "No recurrence",
                "verification_plan": "Later review",
                "implementation": "New support",
                "output_reference": "Support V2",
            }
        )
    )
    improvement.action_plan()
    improvement.action_implement()
    improvement.action_check_effectiveness()
    improvement.action_verify(False, "Fictional recurrence", "Review V3")
    improvement.write({"frozen": True})
    assert not env["training.evaluation.authorization"].search([])

if phase == "prepare":
    quality = env.ref("training_management_test.s094_quality")
    staff = env.ref("training_management_test.s094_staff")
    assert not env["training.provider.dossier"].search([]), "Migration invented provider dossiers"
    assert not env["training.evaluation.authorization"].search([]), "Migration invented evaluator authorizations"
    for kind in ("instructor", "subcontract", "watch"):
        row = (
            env["training.provider.dossier"]
            .with_user(staff)
            .create(
                {
                    "name": "Fictional retained " + kind,
                    "kind": kind,
                    "partner_id": env.ref("training_management_test.s094_partner").id,
                    "quality_id": quality.id,
                    "retention_id": env.ref("training_management_test.s094_retention").id,
                    "competencies": "Fictional documented competence",
                    "source": "https://example.test/source",
                    "observed_on": fields.Date.today(),
                    "analysis": "Actual fictional analysis",
                    "decision": "Keep current programme",
                    "no_impact_reason": "Requirement already covered",
                }
            )
            .with_user(quality)
        )
        first = (
            env["training.provider.evidence"]
            .with_user(quality)
            .create(
                {
                    "dossier_id": row.id,
                    "name": "fictional.txt",
                    "competence": "Fictional scope",
                    "source": "Fictional issuer",
                    "data": BinaryBytes(b"Original retained evidence"),
                }
            )
        )
        env["training.provider.evidence"].with_user(quality).create(
            {
                "dossier_id": row.id,
                "name": "fictional-v2.txt",
                "competence": "Fictional scope",
                "source": "Fictional issuer",
                "data": BinaryBytes(b"Corrected retained evidence"),
                "previous_id": first.id,
            }
        )
        if kind == "subcontract":
            obligation = (
                env["training.provider.obligation"]
                .with_user(quality)
                .create(
                    {
                        "dossier_id": row.id,
                        "name": "Fictional contractual requirement",
                        "due_date": fields.Date.today(),
                        "evidence_id": first.id,
                        "control": "Fictional checked signed contract",
                    }
                )
            )
            obligation.action_nonconform()
        row.action_review()
        save_reference("s094_" + kind, row)

if phase in ("baseline", "prepare"):
    columns = schema()
    env["ir.config_parameter"].set_str(
        key, json.dumps({"columns": columns, "data": snapshot(columns)}, default=str, sort_keys=True)
    )
    env.cr.commit()  # Dedicated disposable fixtures only.
    print("S094_HISTORY_PREPARED")
elif phase == "verify":
    saved = json.loads(env["ir.config_parameter"].get_str(key))
    assert json.loads(json.dumps(snapshot(saved["columns"]), default=str, sort_keys=True)) == saved["data"]
    print("S094_HISTORY_OK: all prior rows, authorization decisions, immutable files and private events retained")
elif phase == "concurrency":
    row = env.ref("training_management_test.s094_instructor")
    quality = row.quality_id
    staff = env.ref("training_management_test.s094_staff")
    context = {"allowed_company_ids": row.company_id.ids}
    row_id = row.id
    env.cr.commit()
    with env.registry.cursor() as one, env.registry.cursor() as two:
        owner = api.Environment(one, quality.id, context)[row._name].browse(row_id)
        peer = api.Environment(two, staff.id, context)[row._name].browse(row_id)
        assert peer.has_access("read")
        owner.write({"member_ids": [Command.clear()]})
        try:
            peer.write({"competencies": "Stale edit"})
        except LockError:
            pass
        else:
            raise AssertionError("Edit ignored concurrent grant withdrawal")
        one.commit()
        try:
            peer.write({"competencies": "Stale edit"})
        except SerializationFailure:
            two.rollback()
        else:
            raise AssertionError("Stale snapshot accepted an edit")
    with env.registry.cursor() as retry:
        try:
            api.Environment(retry, staff.id, context)["training.provider.evidence"].create(
                {
                    "dossier_id": row_id,
                    "name": "late.txt",
                    "competence": "Scope",
                    "source": "Fictional",
                    "data": BinaryBytes(b"Late"),
                }
            )
        except AccessError:
            pass
        else:
            raise AssertionError("Withdrawn staff added evidence")
    print("S094_CONCURRENCY_OK: grant withdrawal lock, stale snapshot retry and late evidence refusal")
else:
    raise ValueError(phase)
