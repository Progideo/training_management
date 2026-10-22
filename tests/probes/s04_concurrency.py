"""ORG02: two reservations, one room/instructor; held and stale snapshots."""

from uuid import uuid4

from psycopg2.errors import SerializationFailure
from odoo import api, Command
from odoo.exceptions import LockError, ValidationError
from odoo.tests import new_test_user

if not env.cr.dbname.startswith("tm_s04_test_"):
    raise RuntimeError("Disposable S04 databases only")
suffix = uuid4().hex[:8]
coord = new_test_user(
    env,
    login="s04_race_" + suffix,
    groups="training_management.group_training_coordinator",
    company_id=env.company.id,
    company_ids=[Command.set(env.company.ids)],
)
trainer = env["res.partner"].create({"name": "Fictional S04 race trainer " + suffix})
room = (
    env["resource.resource"]
    .with_user(coord)
    .create(
        {
            "name": "Fictional race room " + suffix,
            "training_room": True,
            "resource_type": "material",
            "company_id": env.company.id,
            "training_capacity": 10,
        }
    )
)
course = env["training.course"].create({"name": "Fictional S04 race " + suffix})
program = env["training.program.version"].create(
    {
        "course_id": course.id,
        "version": suffix,
        "title": "Fictional race programme",
        "objectives": "Practice",
        "target_audience": "Beginners",
        "prerequisites": "None",
        "content": "Workshop",
        "duration_hours": 3,
        "delivery_mode": "onsite",
        "language_id": env.ref("base.lang_en").id,
        "teaching_methods": "Exercises",
        "evaluation_criteria": "Review",
        "access_conditions": "Manual",
        "accessibility_contact_id": trainer.id,
        "accessibility_information": "Contact coordination",
    }
)
program.action_validate()
deliveries = (
    env["training.delivery"]
    .with_user(coord)
    .create(
        [
            {
                "name": "Fictional reservation " + str(i),
                "program_id": program.id,
                "kind": "session",
                "start_at": "2027-05-01",
                "end_at": "2027-05-02",
                "timezone": "UTC",
                "access_policy": "duration",
                "access_days": 30,
            }
            for i in range(2)
        ]
    )
)
for delivery in deliveries:
    env["training.session"].with_user(coord).create(
        {
            "name": "Fictional race session",
            "delivery_id": delivery.id,
            "instructor_id": trainer.id,
            "room_id": room.id,
            "start_date": "2027-05-01",
            "end_date": "2027-05-01",
            "start_hour": 9,
            "end_hour": 12,
        }
    )
context = {"allowed_company_ids": env.company.ids}
env.cr.commit()  # Only synthetic fixtures in an explicitly disposable database.
with env.registry.cursor() as first, env.registry.cursor() as second:
    e1, e2 = [api.Environment(cursor, coord.id, context) for cursor in (first, second)]
    for current in (e1, e2):
        assert current["training.delivery"].browse(deliveries.ids).mapped("state") == ["preparation", "preparation"]
    e1["training.delivery"].browse(deliveries[0].id).action_confirm()
    try:
        e2["training.delivery"].browse(deliveries[1].id).action_confirm()
    except LockError:
        pass
    else:
        raise AssertionError("Held company reservation lock must reject the competing confirmation")
    first.commit()
    try:
        e2["training.delivery"].browse(deliveries[1].id).action_confirm()
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale reservation snapshot must fail")
with env.registry.cursor() as retry:
    current = api.Environment(retry, coord.id, context)
    try:
        current["training.delivery"].browse(deliveries[1].id).action_confirm()
    except ValidationError:
        retry.rollback()
    else:
        raise AssertionError("Fresh retry must refuse instructor/room conflict")
    assert current["training.delivery"].browse(deliveries.ids).mapped("state") == ["confirmed", "preparation"]
    current["training.delivery"].browse(deliveries[1].id).action_confirm(conflict_reason="Fictional explicit exception")
    assert (
        current["training.delivery"]
        .browse(deliveries[1].id)
        .operation_ids.filtered(lambda item: "conflicts" in (item.after or ""))
    )
    retry.rollback()
print("S04_CONCURRENCY_OK: held lock, stale snapshot, fresh refusal and motivated exception")
env.cr.rollback()
