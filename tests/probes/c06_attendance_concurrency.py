"""Two real Repeatable Read transactions: duplicates and stale revocation."""

from psycopg2.errors import SerializationFailure

from odoo import api
from odoo.exceptions import AccessError, LockError

if env.cr.dbname != "tm_suite_test":
    raise RuntimeError("Disposable attendance CI database only")
original = env.ref("training_management_test.s07_presence")
enrollment = original.enrollment_id
session = original.session_id
participant = enrollment.user_id
coordinator = env.ref("training_management_test.s052_coordinator")
context = {"allowed_company_ids": enrollment.company_id.ids}
definition = env["training.attendance.service"]._definition(session)
env.cr.commit()  # Release the probe's fixture transaction, never used on real data.

with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [
        api.Environment(cursor, participant.id, context)["training.attendance.service"] for cursor in (first, second)
    ]
    for service in (one, two):
        assert service.env["training.learning.service"]._enrollment(enrollment.id)
    result = one._declare(enrollment.id, session.id, 30, 120, accepted=True, definition=definition)
    try:
        two._declare(enrollment.id, session.id, 30, 120, accepted=True, definition=definition)
    except LockError:
        pass
    else:
        raise AssertionError("Duplicate declaration bypassed the held delivery lock")
    first.commit()
    try:
        two._declare(enrollment.id, session.id, 30, 120, accepted=True, definition=definition)
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A stale declaration snapshot must retry")
with env.registry.cursor() as retry:
    service = api.Environment(retry, participant.id, context)["training.attendance.service"]
    presence = service._declare(enrollment.id, session.id, 30, 120, accepted=True, definition=definition)
    assert presence.id == result.id
    assert len(presence.event_ids.filtered(lambda e: e.kind == "declaration")) == 2
    retry.commit()

trainer = env.ref("training_management_test.s07_trainer")
env.cr.rollback()
env.invalidate_all()
revision = original.revision
env.cr.commit()
with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [
        api.Environment(cursor, trainer.id, context)["training.attendance.service"] for cursor in (first, second)
    ]
    assert two._session(session.id)
    one._invalidate(
        session.id, enrollment.id, reason="Fictional concurrent invalidation", revision=revision, definition=definition
    )
    try:
        two._invalidate(
            session.id, enrollment.id, reason="Stale concurrent invalidation", revision=revision, definition=definition
        )
    except LockError:
        pass
    else:
        raise AssertionError("Invalidation bypassed the held delivery lock")
    first.commit()
    try:
        two._invalidate(
            session.id, enrollment.id, reason="Stale concurrent invalidation", revision=revision, definition=definition
        )
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale invalidation snapshot must retry")

with env.registry.cursor() as first, env.registry.cursor() as second:
    staff = api.Environment(first, coordinator.id, context)
    student = api.Environment(second, participant.id, context)["training.attendance.service"]
    assert student.env["training.learning.service"]._enrollment(enrollment.id)
    staff["training.enrollment"].browse(enrollment.id).action_suspend_access(reason="Fictional concurrent suspension")
    try:
        student._declare(enrollment.id, session.id, 30, 120, accepted=True, definition=definition)
    except LockError:
        pass
    else:
        raise AssertionError("Declaration bypassed a concurrent suspension")
    first.commit()
    try:
        student._declare(enrollment.id, session.id, 30, 120, accepted=True, definition=definition)
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Pre-suspension snapshot must retry")
with env.registry.cursor() as retry:
    service = api.Environment(retry, participant.id, context)["training.attendance.service"]
    try:
        service._declare(enrollment.id, session.id, 30, 120, accepted=True, definition=definition)
    except AccessError:
        pass
    else:
        raise AssertionError("Fresh request ignored suspension")
print("S07_CONCURRENCY_OK: serialization, one declaration, stale retry and immediate suspension")
