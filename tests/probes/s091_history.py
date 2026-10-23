"""Retain S09.1 decisions and generated S08 PDF bytes through another update."""

import hashlib
import json
import os
from datetime import timedelta

from odoo import Command, fields

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S09.1 fixture database only")
key = "training_management_test.s091_snapshot"


def snapshot():
    env.flush_all()
    result = {}
    for table in (
        "training_evaluation",
        "training_evaluation_assignment",
        "training_evaluation_result",
        "training_evaluation_authorization",
        "training_proof",
        "training_document",
    ):
        env.cr.execute(f"SELECT to_jsonb(t) FROM {table} t ORDER BY id")
        result[table] = [r[0] for r in env.cr.fetchall()]
    dossier = env.ref("training_management_test.s08_dossier")
    result["pdf"] = [hashlib.sha256(p.data.content).hexdigest() for p in dossier.evidence_ids if p.data]
    return json.dumps(result, default=str, sort_keys=True)


if os.environ["S091_PHASE"] == "prepare":
    dossier = env.ref("training_management_test.s08_dossier")
    coordinator = env.ref("training_management_test.s052_coordinator")
    delivery = dossier.delivery_id.with_user(coordinator)
    delivery.write(
        {
            "evaluation_quality_id": dossier.quality_id.id,
            "evaluation_instructor_ids": [Command.link(coordinator.partner_id.id)],
        }
    )
    evaluation = (
        env["training.evaluation"]
        .with_user(coordinator)
        .create(
            {
                "name": "Fictional S091 retained evaluation",
                "program_id": delivery.program_id.id,
                "purpose": "acquired",
                "criteria": "Observed synthetic answers",
                "threshold": 75,
            }
        )
    )
    evaluation.action_publish()
    row = (
        env["training.evaluation.assignment"]
        .with_user(coordinator)
        .create(
            {
                "evaluation_id": evaluation.id,
                "enrollment_id": dossier.enrollment_id.id,
                "opens_at": fields.Datetime.now() - timedelta(days=1),
                "due_at": fields.Datetime.now() + timedelta(days=1),
            }
        )
    )
    env["training.evaluation.authorization"].with_user(dossier.quality_id).create(
        {
            "delivery_id": delivery.id,
            "user_id": coordinator.id,
            "purpose": "acquired",
            "valid_from": fields.Datetime.now() - timedelta(days=1),
            "valid_until": fields.Datetime.now() + timedelta(days=1),
            "reason": "Fictional scoped qualification",
        }
    )
    env["training.evaluation.service"].with_user(coordinator)._validate(
        row.id,
        revision=row.revision,
        score=80,
        conclusion="Observed score",
        source="Synthetic retained source",
        reason="Checked synthetic result",
    )
    row.action_export_proof()
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": "s091_assignment", "model": row._name, "res_id": row.id}
    )
    env["ir.config_parameter"].sudo().set_str(key, snapshot())
    env.cr.commit()  # Persist synthetic disposable fixtures, never real records.
    print("S091_HISTORY_PREPARED")
else:
    assert snapshot() == env["ir.config_parameter"].sudo().get_str(key)
    print("S091_HISTORY_OK: versions, decisions, authorizations, proofs and PDF bytes preserved")
