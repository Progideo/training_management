"""Main after #103/#104 -> P20: old PDFs unchanged, no retroactive publication."""

import json
import os

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable P20 CI database only")

phase = os.environ["P20_PHASE"]
params = env["ir.config_parameter"]
dossier = env.ref("training_management_test.s08_dossier")


def snapshot(table, ids):
    env.flush_all()
    # Fixed caller table names and fixture IDs only.
    env.cr.execute(f"SELECT to_jsonb(t) FROM {table} t WHERE id IN %s ORDER BY id", [tuple(ids)])
    return json.dumps([row[0] for row in env.cr.fetchall()], sort_keys=True, default=str)


if phase == "baseline":
    ids = dossier.output_ids.ids
    params.set_str("p20_legacy_ids", json.dumps(ids))
    params.set_str("p20_legacy_documents", snapshot("training_document", ids))
    params.set_str("p20_legacy_proofs", snapshot("training_proof", dossier.evidence_ids.ids))
    env.cr.commit()  # Persist synthetic fixture only, never real records.
    print("P20_BASELINE_PREPARED")
elif phase == "verify_legacy":
    ids = json.loads(params.get_str("p20_legacy_ids"))
    assert snapshot("training_document", ids) == params.get_str("p20_legacy_documents")
    assert snapshot("training_proof", dossier.evidence_ids.ids) == params.get_str("p20_legacy_proofs")
    assert not dossier.verify_certificates
    assert not env["training.certificate.verification"].search([])
    print("P20_LEGACY_OK: complete PDF bytes, snapshots, hashes and evidence unchanged; no public registration")
elif phase == "prepare":
    dossier.with_user(env.ref("training_management_test.s052_coordinator")).verify_certificates = True
    dossier.enrollment_id.with_user(dossier.quality_id).action_certificate_participation()
    verification = env["training.certificate.verification"].search([("dossier_id", "=", dossier.id)])
    assert len(verification) == 1
    params.set_str("p20_verification_id", str(verification.id))
    params.set_str("p20_verification", snapshot("training_certificate_verification", verification.ids))
    params.set_str("p20_document", snapshot("training_document", verification.document_id.ids))
    env.cr.commit()
    print("P20_VERIFICATION_PREPARED")
else:
    verification = env["training.certificate.verification"].browse(int(params.get_str("p20_verification_id")))
    assert snapshot("training_certificate_verification", verification.ids) == params.get_str("p20_verification")
    assert snapshot("training_document", verification.document_id.ids) == params.get_str("p20_document")
    assert snapshot("training_document", json.loads(params.get_str("p20_legacy_ids"))) == params.get_str(
        "p20_legacy_documents"
    )
    print("P20_HISTORY_OK: new QR PDF, token, URL, projection and original legacy PDFs preserved")
