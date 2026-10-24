"""Independent transactions: portal replay, immutable closure, grant withdrawal."""

from uuid import uuid4

from psycopg2.errors import SerializationFailure
from odoo import Command, api, fields
from odoo.exceptions import AccessError, LockError, ValidationError
from odoo.tools.binary import BinaryBytes

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S09.3 fixture database only")
retained = env.ref("training_management_test.s093_complaint")
quality = retained.quality_id
actor = env.ref("training_management_test.s052_coordinator")
participant = env.ref("training_management_test.s092_user_0")
enrollment = env["training.enrollment"].search([("user_id", "=", participant.id)], limit=1)
enrollment.delivery_id.with_user(actor).write(
    {
        "complaint_quality_id": quality.id,
        "complaint_retention_id": retained.retention_id.id,
        "complaint_response_days": 5,
    }
)
row = (
    env["training.complaint"]
    .with_user(actor)
    .create(
        {
            "name": "Fictional concurrent complaint",
            "description": "Fictional original",
            "delivery_id": enrollment.delivery_id.id,
            "enrollment_id": enrollment.id,
            "complainant_id": participant.partner_id.id,
            "quality_id": quality.id,
            "retention_id": retained.retention_id.id,
            "due_date": fields.Date.today(),
        }
    )
)
context = {"allowed_company_ids": row.company_id.ids}
row_id, enrollment_id = row.id, enrollment.id
key = str(uuid4())
env.cr.commit()  # Disposable fictional fixtures only.
with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [api.Environment(c, participant.id, context)["training.quality.service"] for c in (first, second)]
    received = one._receive(enrollment_id, key, "Fictional submission", "Fictional text")
    received_id = received.id
    try:
        two._receive(enrollment_id, key, "Changed replay", "Changed text")
    except LockError:
        pass
    else:
        raise AssertionError("Duplicate submission ignored the held enrollment lock")
    first.commit()
    try:
        two._receive(enrollment_id, key, "Changed replay", "Changed text")
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale transaction did not request retry")
with env.registry.cursor() as retry:
    result = api.Environment(retry, participant.id, context)["training.quality.service"]._receive(
        enrollment_id, key, "Changed replay", "Changed text"
    )
    assert result.id == received_id and result.description == "Fictional text"
    retry.commit()
with env.registry.cursor() as close, env.registry.cursor() as adding:
    closing = api.Environment(close, quality.id, context)["training.complaint"].browse(row_id)
    closing.action_start()
    closing.write({"treatment": "Fictional resolution", "reply": "Fictional reply"})
    closing.action_resolve()
    closing.action_close()
    try:
        api.Environment(adding, actor.id, context)["training.quality.file"].create(
            {
                "complaint_id": row_id,
                "name": "race.txt",
                "source": "Fictional source",
                "data": BinaryBytes(b"x"),
            }
        )
    except LockError:
        pass
    else:
        raise AssertionError("File addition raced past a closing complaint")
    close.commit()
with env.registry.cursor() as after:
    try:
        api.Environment(after, actor.id, context)["training.quality.file"].create(
            {
                "complaint_id": row_id,
                "name": "late.txt",
                "source": "Fictional source",
                "data": BinaryBytes(b"x"),
            }
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Closed complaint accepted a late file")
with env.registry.cursor() as revoke, env.registry.cursor() as editing:
    revoked = api.Environment(revoke, quality.id, context)["training.complaint"].browse(received_id)
    revoked.write({"member_ids": [Command.link(actor.id)]})
    revoke.commit()
    # Prime native read cache before withdrawal, then require a fresh write authorization.
    peer = api.Environment(editing, actor.id, context)["training.complaint"].browse(received_id)
    assert peer.has_access("read")
    revoked.write({"member_ids": [Command.clear()]})
    try:
        peer.write({"treatment": "Fictional stale edit"})
    except LockError:
        pass
    else:
        raise AssertionError("Edit ignored the held grant-withdrawal lock")
    revoke.commit()
    editing.rollback()
with env.registry.cursor() as after:
    try:
        api.Environment(after, actor.id, context)["training.complaint"].browse(received_id).write(
            {"treatment": "Late edit"}
        )
    except AccessError:
        pass
    else:
        raise AssertionError("Withdrawn staff edited the dossier")
print("S093_CONCURRENCY_OK: one original submission, stale retry, serialized closure and grant withdrawal")
