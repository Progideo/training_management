"""Independent learner writes keep administrative revocation locks intact."""

from uuid import uuid4

from odoo import api
from odoo.exceptions import LockError
from odoo.tests import new_test_user

if env.cr.dbname not in ("tm_suite_test", "tm_s01_test_s021_s052"):
    raise RuntimeError("Disposable C06 test databases only")
coordinator = new_test_user(
    env(context={"no_reset_password": True}),
    login="c06_parallel_" + uuid4().hex[:8],
    email="coordinator@example.invalid",
    groups="training_management.group_training_coordinator",
)
company = env.company
course = env["training.course"].with_user(coordinator).create({"name": "Fictional parallel learning"})
course.category_id = env["training.category"].create({"name": "Fictional concurrency", "company_id": company.id})
program = (
    env["training.program.version"]
    .with_user(coordinator)
    .create(
        {
            "course_id": course.id,
            "version": "CONCURRENT-1",
            "title": "Fictional parallel programme",
            "objectives": "Test",
            "target_audience": "Fictional learners",
            "prerequisites": "None",
            "content": "Fictional exercise",
            "duration_hours": 1,
            "delivery_mode": "elearning",
            "language_id": env.ref("base.lang_en").id,
            "teaching_methods": "Exercise",
            "evaluation_criteria": "Submission",
            "access_conditions": "Manual authorization",
            "accessibility_contact_id": coordinator.partner_id.id,
            "accessibility_information": "Fictional coordination",
        }
    )
)
program.action_validate()
delivery = (
    env["training.delivery"]
    .with_user(coordinator)
    .create(
        {
            "name": "Fictional parallel delivery",
            "program_id": program.id,
            "kind": "autonomous",
            "access_policy": "months",
            "access_months": 12,
            "learning_tutor_id": coordinator.id,
        }
    )
)
activity = (
    env["training.learning.activity"]
    .with_user(coordinator)
    .create({"name": "Fictional parallel exercise", "delivery_id": delivery.id, "criterion": "submission"})
)
context = {"allowed_company_ids": company.ids}
env.cr.commit()

# Independent learners must make progress while another submission is uncommitted.
# This used to fail because every learning POST wrote the delivery revision.
parallel = []
for number in range(2):
    learner = new_test_user(
        env, login="s052_parallel_" + uuid4().hex[:8], groups="base.group_portal", email="learner@example.invalid"
    )
    row = (
        env["training.enrollment"]
        .with_user(coordinator)
        .create(
            {
                "delivery_id": delivery.id,
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
delivery_revision = delivery.revision
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
assert delivery.revision == delivery_revision
for _, eid in parallel:
    assert env["training.learning.entry"].search_count([("enrollment_id", "=", eid)]) == 1
print("C06_LEARNING_PARALLEL_OK: independent learners commit concurrently; administrative lock preserved")
