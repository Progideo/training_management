"""Merged P20 closed dossier -> audited continuity, with byte-exact preservation."""

import json
import os

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable closure continuity database only")

phase = os.environ["CONTINUITY_PHASE"]
params = env["ir.config_parameter"]
dossier = env.ref("training_management_test.s08_dossier")
coordinator = env.ref("training_management_test.s052_coordinator")


def snapshot(table, ids):
    env.flush_all()
    if not ids:
        return "[]"
    # Fixed caller table names and synthetic IDs only; compare every stored column.
    env.cr.execute(f"SELECT to_jsonb(t) FROM {table} t WHERE id IN %s ORDER BY id", [tuple(ids)])
    return json.dumps([row[0] for row in env.cr.fetchall()], sort_keys=True, default=str)


def remember(name, table, records):
    params.set_str("continuity_" + name + "_ids", json.dumps(records.ids))
    params.set_str("continuity_" + name, snapshot(table, records.ids))


def preserved(name, table):
    assert snapshot(table, json.loads(params.get_str("continuity_" + name + "_ids"))) == params.get_str(
        "continuity_" + name
    )


if phase == "baseline":
    # The old version accepted this incomplete activity. Preserve it on upgrade
    # and require an explicit configuration repair instead of inventing an exam.
    activity = (
        env["training.learning.activity"]
        .with_user(coordinator)
        .create(
            {
                "name": "Fictional legacy incomplete evaluation",
                "delivery_id": dossier.delivery_id.id,
                "criterion": "evaluation",
                "evaluation_threshold": 75,
            }
        )
    )
    remember("legacy_activity", "training_learning_activity", activity)
    dossier.with_user(coordinator).verify_certificates = True
    dossier.enrollment_id.with_user(dossier.quality_id).action_certificate_participation()
    for category in dossier._missing_keys():
        proof = (
            env["training.proof"]
            .with_user(coordinator)
            .create(
                {
                    "dossier_id": dossier.id,
                    "category": category,
                    "source": "Fictional controlled baseline",
                    "author": "Fictional reviewer",
                    "produced_at": fields.Datetime.now(),
                    "disposition": "waiver",
                    "reason": "Fictional non-applicable baseline evidence",
                }
            )
        )
        proof.with_user(dossier.quality_id).action_validate()
    dossier.with_user(dossier.quality_id).action_close()
    verification = env["training.certificate.verification"].search([("dossier_id", "=", dossier.id)])
    assert len(verification) == 1
    dossier.quality_id.active = False
    remember("legacy_dossier", "training_closure", dossier)
    remember("legacy_proofs", "training_proof", dossier.evidence_ids)
    remember("legacy_documents", "training_document", dossier.output_ids)
    remember("legacy_verification", "training_certificate_verification", verification)
    env.cr.commit()  # Disposable fictitious fixture only.
    print("CONTINUITY_BASELINE_PREPARED")
elif phase == "verify_legacy":
    preserved("legacy_activity", "training_learning_activity")
    for name, table in (
        ("legacy_dossier", "training_closure"),
        ("legacy_proofs", "training_proof"),
        ("legacy_documents", "training_document"),
        ("legacy_verification", "training_certificate_verification"),
    ):
        preserved(name, table)
    assert not dossier.event_ids
    print("CONTINUITY_LEGACY_OK: closed dossier, archived reviewer, evidence and both PDF generations unchanged")
elif phase == "prepare":
    activity = (
        env["training.learning.activity"]
        .with_user(coordinator)
        .browse(json.loads(params.get_str("continuity_legacy_activity_ids")))
    )
    try:
        with env.cr.savepoint():
            activity.create(
                {
                    "name": "Fictional dependent",
                    "delivery_id": dossier.delivery_id.id,
                    "dependency_ids": [Command.set(activity.ids)],
                }
            )
    except ValidationError:
        pass
    else:
        raise AssertionError("New dependency accepted an unusable legacy evaluation")
    activity.write({"criterion": "declaration"})
    previous_quality = dossier.quality_id
    replacement_quality = new_test_user(
        env, login="continuity_history_quality", groups="training_management.group_training_quality"
    )
    dossier.with_user(coordinator).action_reassign_quality(replacement_quality.id, "Fictional reviewer departure")
    old = dossier.with_user(replacement_quality).verification_ids
    public = old._public_values(old.token)
    try:
        old.with_user(previous_quality).action_revoke(reason="Archived reviewer")
    except AccessError:
        pass
    else:
        raise AssertionError("Archived reviewer retained authority")
    dossier.with_user(replacement_quality).action_rectify(
        "Fictional beneficiary correction", expected_closure_event_id=False
    )
    dossier.enrollment_id.participant_id.name = "Fictional corrected beneficiary"
    dossier.enrollment_id.with_user(replacement_quality).action_certificate_participation()
    new = dossier.with_user(replacement_quality).verification_ids - old
    assert len(new) == 1
    old.action_replace(new.id, "Fictional corrected identity")
    assert old._public_values(old.token) == dict(public, state="replaced")
    assert new._public_values(new.token)["state"] == "valid"
    dossier.with_user(replacement_quality).action_close()
    assert sorted(dossier.event_ids.mapped("operation")) == ["close", "reassign", "rectify"]
    for name, table in (("legacy_proofs", "training_proof"), ("legacy_documents", "training_document")):
        preserved(name, table)
    for name, table, records in (
        ("dossier", "training_closure", dossier),
        ("events", "training_closure_event", dossier.event_ids),
        ("documents", "training_document", dossier.output_ids),
        ("verification", "training_certificate_verification", old | new),
    ):
        remember(name, table, records)
    env.cr.commit()
    print("CONTINUITY_RECTIFICATION_PREPARED")
else:
    for name, table in (
        ("dossier", "training_closure"),
        ("events", "training_closure_event"),
        ("documents", "training_document"),
        ("verification", "training_certificate_verification"),
        ("legacy_proofs", "training_proof"),
        ("legacy_documents", "training_document"),
    ):
        preserved(name, table)
    print("CONTINUITY_HISTORY_OK: complete lifecycle, replacement projection and every original PDF preserved")
