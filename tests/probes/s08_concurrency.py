"""Actual Repeatable Read transactions: certificate duplicate and evidence validation."""

from psycopg2.errors import SerializationFailure

from odoo import api
from odoo.exceptions import LockError, ValidationError

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S08 CI database only")
dossier = env.ref("training_management_test.s08_dossier")
quality = dossier.quality_id
context = {"allowed_company_ids": dossier.company_id.ids}
enrollment = dossier.enrollment_id
expected = len(dossier.output_ids)
env.cr.commit()  # Release synthetic fixture locks, never used on real records.

with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [
        api.Environment(c, quality.id, context)["training.enrollment"].browse(enrollment.id) for c in (first, second)
    ]
    assert one.state == two.state == "confirmed"
    one.action_certificate_participation()
    try:
        two.action_certificate_participation()
    except LockError:
        pass
    else:
        raise AssertionError("Duplicate issuance ignored the held delivery lock")
    first.commit()
    try:
        two.action_certificate_participation()
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A stale issuance snapshot must retry")
with env.registry.cursor() as retry:
    staff = api.Environment(retry, quality.id, context)
    staff["training.enrollment"].browse(enrollment.id).action_certificate_participation()
    assert staff["training.document"].search_count([("dossier_id", "=", dossier.id)]) == expected
    retry.commit()

with env.registry.cursor() as prepare:
    staff = api.Environment(prepare, quality.id, context)
    proof = staff["training.proof"].create(
        {
            "dossier_id": dossier.id,
            "category": "incidents",
            "source": "Fictional review",
            "author": "Fictional quality",
            "produced_at": dossier.create_date,
            "disposition": "waiver",
            "reason": "Fictional justified exception",
        }
    )
    proof_id = proof.id
    prepare.commit()
with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [api.Environment(c, quality.id, context)["training.proof"].browse(proof_id) for c in (first, second)]
    assert not one.validated_at and not two.validated_at
    one.action_validate()
    try:
        two.write({"reason": "Concurrent alteration"})
    except LockError:
        pass
    else:
        raise AssertionError("Proof mutation ignored concurrent validation")
    first.commit()
    try:
        two.write({"reason": "Stale alteration"})
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale proof mutation must retry")
with env.registry.cursor() as retry:
    proof = api.Environment(retry, quality.id, context)["training.proof"].browse(proof_id)
    try:
        proof.write({"reason": "Unauthorized revision after approval"})
    except ValidationError:
        pass
    else:
        raise AssertionError("Validated evidence was rewritten after retry")
print("S08_CONCURRENCY_OK: duplicate issuance, held locks, stale retry and immutable approval")
