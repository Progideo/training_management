"""Actual row locks and stale snapshots for reviewer transfer and rectification."""

from psycopg2.errors import SerializationFailure

from odoo import api
from odoo.exceptions import AccessError, LockError
from odoo.tests import new_test_user

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable closure continuity database only")

dossier = env.ref("training_management_test.s08_dossier")
coordinator_id = env.ref("training_management_test.s052_coordinator").id
previous_quality_id = dossier.quality_id.id
new_quality_id = new_test_user(
    env, login="continuity_race_quality", groups="training_management.group_training_quality"
).id
dossier_id = dossier.id
verification_id = dossier.verification_ids.filtered(lambda v: v.state == "valid").id
context = {"allowed_company_ids": dossier.company_id.ids}
env.cr.commit()  # Release synthetic fixture locks only.

with env.registry.cursor() as first, env.registry.cursor() as second:
    one = api.Environment(first, coordinator_id, context)["training.closure"].browse(dossier_id)
    two = api.Environment(second, previous_quality_id, context)["training.certificate.verification"].browse(
        verification_id
    )
    assert one.quality_id.id == two.dossier_id.quality_id.id == previous_quality_id
    one.action_reassign_quality(new_quality_id, "Fictional first transfer")
    try:
        two.action_revoke(reason="Concurrent former reviewer decision")
    except LockError:
        pass
    else:
        raise AssertionError("Revocation bypassed reviewer transfer lock")
    first.commit()
    try:
        two.action_revoke(reason="Stale former reviewer decision")
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale authority did not require retry")

with env.registry.cursor() as retry:
    former = api.Environment(retry, previous_quality_id, context)["training.certificate.verification"].browse(
        verification_id
    )
    try:
        former.action_revoke(reason="Former reviewer after retry")
    except AccessError:
        pass
    else:
        raise AssertionError("Former reviewer retained authority after retry")

with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [
        api.Environment(c, new_quality_id, context)["training.closure"].browse(dossier_id) for c in (first, second)
    ]
    assert one.state == two.state == "closed"
    old_count = len(one.event_ids.filtered(lambda e: e.operation == "rectify"))
    last_close_id = one.event_ids.filtered(lambda e: e.operation == "close")[:1].id
    one.action_rectify("Fictional first rectification", expected_closure_event_id=last_close_id)
    try:
        two.action_rectify("Concurrent rectification", expected_closure_event_id=last_close_id)
    except LockError:
        pass
    else:
        raise AssertionError("Rectification ignored the held lock")
    first.commit()
    try:
        two.action_rectify("Stale rectification", expected_closure_event_id=last_close_id)
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale rectification did not require retry")

with env.registry.cursor() as retry:
    record = api.Environment(retry, new_quality_id, context)["training.closure"].browse(dossier_id)
    record.action_rectify("Repeated rectification", expected_closure_event_id=last_close_id)
    events = record.event_ids.filtered(lambda e: e.operation == "rectify")
    assert len(events) == old_count + 1
    assert events[:1].reason == "Fictional first rectification"
    record.action_close()
    retry.commit()
print(
    "CONTINUITY_CONCURRENCY_OK: transfer versus revocation, double rectification, stale retry and unchanged first reason"
)
