"""Two actual transactions: serialized validation, stale retry and grant revocation."""

from psycopg2.errors import SerializationFailure
from odoo import api
from odoo.exceptions import AccessError, LockError, ValidationError

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S09.1 fixture database only")
row = env.ref("training_management_test.s091_assignment")
actor = env.ref("training_management_test.s052_coordinator")
quality = row.delivery_id.evaluation_quality_id
row_id, grant_id = (
    row.id,
    env["training.evaluation.authorization"]
    .search([("delivery_id", "=", row.delivery_id.id), ("user_id", "=", actor.id)], limit=1)
    .id,
)
revision = row.revision
context = {"allowed_company_ids": row.company_id.ids}
params = dict(
    revision=revision,
    score=81,
    conclusion="Concurrent observed score",
    source="Synthetic sheet",
    reason="Concurrent validation probe",
)
env.cr.commit()  # Release synthetic fixture locks.
with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [api.Environment(c, actor.id, context)["training.evaluation.service"] for c in (first, second)]
    one._validate(row_id, **params)
    try:
        two._validate(row_id, **params)
    except LockError:
        pass
    else:
        raise AssertionError("Concurrent validation ignored the held delivery lock")
    first.commit()
    try:
        two._validate(row_id, **params)
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A stale evaluation transaction must retry")
with env.registry.cursor() as retry:
    service = api.Environment(retry, actor.id, context)["training.evaluation.service"]
    try:
        service._validate(row_id, **params)
    except ValidationError:
        pass
    else:
        raise AssertionError("A stale decision overwrote a newer reference")
    retry.rollback()
with env.registry.cursor() as revoke:
    api.Environment(revoke, quality.id, context)["training.evaluation.authorization"].browse(grant_id).write(
        {"active": False}
    )
    revoke.commit()
with env.registry.cursor() as after:
    try:
        api.Environment(after, actor.id, context)["training.evaluation.service"]._validate(row_id, **params)
    except AccessError:
        pass
    else:
        raise AssertionError("A revoked authorization still validated an evaluation")
    after.rollback()
print("S091_CONCURRENCY_OK: held locks, stale retry, preserved reference and revoked authorization")
