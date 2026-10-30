"""P20: actual held locks, stale transaction retry and terminal decision audit."""

from psycopg2.errors import SerializationFailure

from odoo import api
from odoo.exceptions import LockError, ValidationError

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable P20 CI database only")

dossier = env.ref("training_management_test.s08_dossier")
verification = env["training.certificate.verification"].search([("dossier_id", "=", dossier.id)])
verification_id, enrollment_id, quality_id = verification.id, dossier.enrollment_id.id, dossier.quality_id.id
context = {"allowed_company_ids": dossier.company_id.ids}
original_pdf = verification.document_id.data.content
expected = len(dossier.output_ids)
env.cr.commit()  # Release synthetic fixture locks only.

with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [api.Environment(c, quality_id, context) for c in (first, second)]
    assert (
        one["training.enrollment"].browse(enrollment_id).state == two["training.enrollment"].browse(enrollment_id).state
    )
    one["training.enrollment"].browse(enrollment_id).action_certificate_participation()
    try:
        two["training.enrollment"].browse(enrollment_id).action_certificate_participation()
    except LockError:
        pass
    else:
        raise AssertionError("Concurrent issuance bypassed the shared lock")
    first.commit()
    try:
        two["training.enrollment"].browse(enrollment_id).action_certificate_participation()
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale issuance must retry")
with env.registry.cursor() as retry:
    staff = api.Environment(retry, quality_id, context)
    staff["training.enrollment"].browse(enrollment_id).action_certificate_participation()
    assert staff["training.document"].search_count([("dossier_id", "=", dossier.id)]) == expected
    assert staff["training.certificate.verification"].search_count([("dossier_id", "=", dossier.id)]) == 1
    retry.commit()

# Prepare a genuine corrected PDF, to race replacement against revocation.
with env.registry.cursor() as prepare:
    staff = api.Environment(prepare, quality_id, context)
    coordinator = staff.ref("training_management_test.s052_coordinator")
    presence = staff.ref("training_management_test.s07_presence").with_user(coordinator)
    service = staff["training.attendance.service"].with_user(coordinator)
    service._review(
        presence.session_id.id,
        enrollment_id,
        60,
        120,
        revision=presence.revision,
        correction=True,
        reason="Fictional second signed correction",
        data=b"%PDF-1.4\nFictional corrected proof\n%%EOF",
        filename="correction.pdf",
        definition=service._definition(presence.session_id),
    )
    staff["training.enrollment"].browse(enrollment_id).action_certificate_participation()
    replacement = staff["training.certificate.verification"].search(
        [("dossier_id", "=", dossier.id), ("id", "!=", verification_id)]
    )
    assert len(replacement) == 1
    replacement_id = replacement.id
    prepare.commit()

with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [
        api.Environment(c, quality_id, context)["training.certificate.verification"].browse(verification_id)
        for c in (first, second)
    ]
    assert one.state == two.state == "valid"
    one.action_revoke(reason="Fictional first decision")
    try:
        two.action_replace(replacement_id=replacement_id, reason="Concurrent replacement")
    except LockError:
        pass
    else:
        raise AssertionError("Revocation bypassed the shared lock")
    first.commit()
    try:
        two.action_replace(replacement_id=replacement_id, reason="Stale replacement")
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale revocation must retry")
with env.registry.cursor() as retry:
    staff = api.Environment(retry, quality_id, context)
    record = staff["training.certificate.verification"].browse(verification_id)
    record.action_revoke(reason="Repeated request")
    assert record.reason == "Fictional first decision"
    assert record._public_values(record.token)["state"] == "revoked"
    assert record.document_id.data.content == original_pdf
    assert staff["training.certificate.verification"].browse(replacement_id).state == "valid"
    try:
        record.action_replace(replacement_id=replacement_id, reason="Conflicting terminal decision")
    except ValidationError:
        pass
    else:
        raise AssertionError("Terminal decision was overwritten")
    retry.commit()
print("P20_CONCURRENCY_OK: unique emission/registration, held locks, stale retry and revocation against replacement")
