"""Synthetic S08 evidence and PDFs remain byte-identical after an update."""

import hashlib
import json
import os

from odoo import fields
from odoo.tests import new_test_user
from odoo.tools.binary import BinaryBytes

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S08 CI database only")


def remember(name, record):
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": name, "model": record._name, "res_id": record.id}
    )


def snapshot():
    env.flush_all()  # Capture persisted stored-related fields, not pending ORM recomputations.
    dossier = env.ref("training_management_test.s08_dossier")
    result = {}
    for table, column, value in (
        ("training_closure", "id", dossier.id),
        ("training_proof", "dossier_id", dossier.id),
        ("training_document", "dossier_id", dossier.id),
    ):
        env.cr.execute(f"SELECT to_jsonb(t) FROM {table} t WHERE {column}=%s ORDER BY id", [value])
        result[table] = [r[0] for r in env.cr.fetchall()]
    # P20: new opt-in stays disabled; all original columns remain compared below.
    for row in result["training_closure"]:
        if "verify_certificates" in row:
            assert row.pop("verify_certificates") in (None, False)
    if "training.certificate.verification" in env:
        assert not env["training.certificate.verification"].search([("dossier_id", "=", dossier.id)])
    result["pdf"] = [hashlib.sha256(d.data.content).hexdigest() for d in dossier.output_ids]
    return json.dumps(result, default=str, sort_keys=True)


if os.environ["S08_PHASE"] == "prepare":
    presence = env.ref("training_management_test.s07_presence")
    quality = new_test_user(env, login="s08_history_quality", groups="training_management.group_training_quality")
    coordinator = env.ref("training_management_test.s052_coordinator")
    policy = (
        env["training.retention.category"]
        .with_user(quality)
        .create(
            {
                "name": "Fictional history policy",
                "purpose": "Synthetic evidence",
                "responsible_id": quality.id,
                "duration_days": 365,
                "archive_policy": "Restricted archive",
                "deletion_policy": "Human review, no automatic purge",
            }
        )
    )
    policy.action_approve()
    dossier = (
        env["training.closure"]
        .with_user(coordinator)
        .create({"enrollment_id": presence.enrollment_id.id, "quality_id": quality.id, "retention_id": policy.id})
    )
    proof = (
        env["training.proof"]
        .with_user(coordinator)
        .create(
            {
                "dossier_id": dossier.id,
                "category": "attendance",
                "source": f"training.attendance:{presence.id} revision:{presence.revision}",
                "author": "Fictional trainer",
                "produced_at": fields.Datetime.now(),
                "data": BinaryBytes(b"%PDF-1.4\nFictional evidence\n%%EOF"),
            }
        )
    )
    proof.with_user(quality).action_validate()
    presence.enrollment_id.with_user(quality).action_certificate_participation()
    remember("s08_dossier", dossier)
    env["ir.config_parameter"].sudo().set_str("training_management_test.s08_snapshot", snapshot())
    env.cr.commit()  # Synthetic disposable fixture only.
    print("S08_HISTORY_PREPARED")
else:
    assert snapshot() == env["ir.config_parameter"].sudo().get_str("training_management_test.s08_snapshot")
    print("S08_HISTORY_OK: dossier, version, validation, source and PDF bytes preserved")
