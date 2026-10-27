"""Real cursors: one submission per key; revocation wins over stale requests."""

from uuid import uuid4

from psycopg2.errors import SerializationFailure

from odoo import api
from odoo.exceptions import AccessError, LockError, ValidationError
from odoo.tests import new_test_user

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S05 complement database only")
coordinator = env.ref("training_management_test.s052_coordinator")
participant = env.ref("training_management_test.s052_participant")
enrollment = env.ref("training_management_test.s052_enrollment")
tutor = new_test_user(env, login="s052_race_tutor_" + uuid4().hex[:8], groups="base.group_portal")
enrollment.with_user(coordinator).write({"learning_tutor_id": tutor.id})
activity = (
    env["training.learning.activity"]
    .with_user(coordinator)
    .create(
        {
            "name": "Fictional simultaneous work",
            "delivery_id": enrollment.delivery_id.id,
            "criterion": "validation",
        }
    )
)
first_entry = (
    env["training.learning.service"]
    .with_user(participant)
    ._post(
        enrollment.id,
        "submission",
        activity_id=activity.id,
        request_key=str(uuid4()),
        body="Fictional version one",
        data=b"%PDF-1.4\nFictional version one\n%%EOF",
        filename="one.pdf",
    )
)
env.cr.commit()  # Fictional fixtures in the explicitly guarded disposable database.
context = {"allowed_company_ids": enrollment.company_id.ids}
key = str(uuid4())
payload = {
    "activity_id": activity.id,
    "request_key": key,
    "body": "Fictional version two",
    "revision": 1,
    "parent_id": first_entry.id,
    "data": b"%PDF-1.4\nFictional version two\n%%EOF",
    "filename": "two.pdf",
}

with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [
        api.Environment(cursor, participant.id, context)["training.learning.service"] for cursor in (first, second)
    ]
    # Establish both Repeatable Read snapshots before the first mutation.
    assert one._enrollment(enrollment.id)._effective_state() == "active"
    assert two._enrollment(enrollment.id)._effective_state() == "active"
    created = one._post(enrollment.id, "submission", **payload)
    created_id = created.id
    try:
        two._post(enrollment.id, "submission", **payload)
    except LockError:
        pass
    else:
        raise AssertionError("A competing submission must respect the held S03 lock")
    first.commit()
    try:
        two._post(enrollment.id, "submission", **payload)
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A stale snapshot must retry before touching evidence")

with env.registry.cursor() as retry:
    service = api.Environment(retry, participant.id, context)["training.learning.service"]
    assert service._post(enrollment.id, "submission", **payload).id == created_id
    try:
        service._post(enrollment.id, "submission", **dict(payload, request_key=str(uuid4())))
    except ValidationError:
        pass
    else:
        raise AssertionError("A stale form with another key cannot create a third version")
    entries = service.env["training.learning.entry"].sudo().search([("enrollment_id", "=", enrollment.id)])
    assert len(entries) == 2
    assert entries.browse(first_entry.id).data.content.endswith(b"%%EOF")
    assert entries.browse(created_id).data.content == payload["data"]
    assert service.env["training.learning.notice"].sudo().search_count([("entry_id", "=", created_id)]) == 1
    retry.commit()

with env.registry.cursor() as first, env.registry.cursor() as second:
    staff = api.Environment(first, coordinator.id, context)
    student = api.Environment(second, participant.id, context)["training.learning.service"]
    assert student._enrollment(enrollment.id)._effective_state() == "active"
    staff["training.enrollment"].browse(enrollment.id).action_suspend_access(reason="Fictional concurrent suspension")
    next_payload = dict(payload, parent_id=created_id, revision=2, request_key=str(uuid4()))
    try:
        student._post(enrollment.id, "submission", **next_payload)
    except LockError:
        pass
    else:
        raise AssertionError("Work cannot bypass a concurrent suspension lock")
    first.commit()
    try:
        student._post(enrollment.id, "submission", **next_payload)
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A request predating revocation must retry")
with env.registry.cursor() as retry:
    student = api.Environment(retry, participant.id, context)["training.learning.service"]
    try:
        student._post(enrollment.id, "submission", **next_payload)
    except AccessError:
        pass
    else:
        raise AssertionError("A fresh retry must enforce the suspended enrollment")
    assert student.env["training.learning.entry"].sudo().search_count([("enrollment_id", "=", enrollment.id)]) == 2
print("S052_CONCURRENCY_OK: lock, stale retry, one version/notice per key, suspension and preserved files")

# Independent learners must make progress while another submission is uncommitted.
# This used to fail because every learning POST wrote the delivery revision.
env.cr.rollback()
env.invalidate_all()
parallel = []
for number in range(2):
    learner = new_test_user(env, login="s052_parallel_" + uuid4().hex[:8], groups="base.group_portal")
    row = (
        env["training.enrollment"]
        .with_user(coordinator)
        .create(
            {
                "delivery_id": enrollment.delivery_id.id,
                "participant_id": learner.partner_id.id,
                "user_id": learner.id,
                "free_reason": "Fictional independent concurrent learner",
            }
        )
    )
    row.action_validate_prerequisites(reason="Fictional review")
    row.action_confirm()
    row.action_authorize(reason="Fictional authorization")
    row.action_open_access(reason="Fictional opening")
    parallel.append((learner.id, row.id))
env.cr.commit()
delivery_revision = enrollment.delivery_id.revision
with env.registry.cursor() as first, env.registry.cursor() as second, env.registry.cursor() as administrative:
    for cursor, (uid, eid) in zip((first, second), parallel):
        service = api.Environment(cursor, uid, context)["training.learning.service"]
        service._post(
            eid, "submission", activity_id=activity.id, request_key=str(uuid4()), body="Fictional parallel submission"
        )
    staff = api.Environment(administrative, coordinator.id, context)
    try:
        staff["training.enrollment"].browse(parallel[0][1]).action_suspend_access(reason="Fictional concurrent revoke")
    except LockError:
        administrative.rollback()
    else:
        raise AssertionError("Administrative access changes must respect active learning locks")
    # Second learner commits while the first transaction still holds its locks.
    second.commit()
    first.commit()
env.cr.rollback()
env.invalidate_all()
assert enrollment.delivery_id.revision == delivery_revision
for _, eid in parallel:
    assert env["training.learning.entry"].search_count([("enrollment_id", "=", eid)]) == 1
print("S052_PARALLEL_OK: independent learners commit concurrently; administrative lock preserved")
