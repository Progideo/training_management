"""Participants of one delivery start, answer and submit in parallel transactions."""

from uuid import uuid4

from odoo import Command, api
from odoo.exceptions import LockError
from odoo.tests import new_test_user

if env.cr.dbname != "tm_suite_test":
    raise RuntimeError("Disposable suite database only")
context = {"no_reset_password": True}
coordinator = new_test_user(
    env(context=context),
    login="exam_parallel_" + uuid4().hex[:8],
    email="coordinator@example.invalid",
    groups="training_management.group_training_coordinator",
)
company = env.company
course = env["training.course"].create({"name": "Fictional parallel exam", "company_id": company.id})
course.category_id = env["training.category"].create({"name": "Fictional parallel", "company_id": company.id})
contact = env["res.partner"].create({"name": "Fictional accessibility contact"})
program = env["training.program.version"].create(
    {
        "course_id": course.id,
        "version": "PARALLEL-1",
        "title": "Fictional parallel programme",
        "objectives": "Test",
        "target_audience": "Fictional learners",
        "prerequisites": "None",
        "content": "Test",
        "duration_hours": 1,
        "delivery_mode": "elearning",
        "language_id": env.ref("base.lang_en").id,
        "teaching_methods": "Test",
        "evaluation_criteria": "Test",
        "access_conditions": "Test",
        "accessibility_contact_id": contact.id,
        "accessibility_information": "Test",
    }
)
program.action_validate()
exam = (
    env["survey.survey"]
    .with_user(coordinator)
    .create(
        {
            "title": "Fictional parallel exam",
            "training_program_id": program.id,
            "survey_type": "custom",
            "scoring_type": "scoring_with_answers",
            "time_limit": 60,
            "scoring_success_min": 50,
        }
    )
)
question = (
    env["survey.question"]
    .with_user(coordinator)
    .create(
        {
            "survey_id": exam.id,
            "title": "Fictional question",
            "question_type": "simple_choice",
            "answer_score": 1,
            "suggested_answer_ids": [
                Command.create({"value": "Right", "is_correct": True, "answer_score": 1}),
                Command.create({"value": "Wrong", "is_correct": False}),
            ],
        }
    )
)
exam.action_training_publish()
delivery = (
    env["training.delivery"]
    .with_user(coordinator)
    .create(
        {
            "name": "Fictional parallel class",
            "company_id": company.id,
            "program_id": program.id,
            "kind": "autonomous",
            "capacity": 2,
            "access_policy": "duration",
            "access_days": 10,
        }
    )
)
activity = (
    env["training.learning.activity"]
    .with_user(coordinator)
    .create(
        {
            "name": "Exam",
            "delivery_id": delivery.id,
            "criterion": "evaluation",
            "evaluation_threshold": 50,
            "training_exam_id": exam.id,
        }
    )
)
learners = []
for _index in range(2):
    learner = new_test_user(
        env(context=context),
        login="exam_parallel_" + uuid4().hex[:8],
        email="learner@example.invalid",
        groups="base.group_portal",
    )
    row = (
        env["training.enrollment"]
        .with_user(coordinator)
        .create(
            {
                "delivery_id": delivery.id,
                "participant_id": learner.partner_id.id,
                "user_id": learner.id,
                "free_reason": "Fictional parallel learner",
            }
        )
    )
    row.action_validate_prerequisites(reason="Fictional review")
    row.action_confirm()
    row.action_authorize(reason="Fictional authorization")
    row.action_open_access(reason="Fictional opening")
    learners.append((learner.id, row.id))
env.cr.commit()
revision = delivery.revision
right, wrong = question.suggested_answer_ids.sorted(lambda a: not a.is_correct).ids


def services(first, second):
    return [
        api.Environment(cursor, uid, context)["training.exam.service"]
        for cursor, (uid, _eid) in zip((first, second), learners)
    ]


with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = services(first, second)
    attempts = [service._start(eid, activity.id).id for service, (_uid, eid) in zip((one, two), learners)]
    second.commit()
    first.commit()
with env.registry.cursor() as first, env.registry.cursor() as second, env.registry.cursor() as administrative:
    one, two = services(first, second)
    one._save(attempts[0], question.id, [right], False)
    # The second participant answers and commits while the first still holds their locks.
    two._save(attempts[1], question.id, [wrong], True)
    staff = api.Environment(administrative, coordinator.id, context)
    try:
        staff["training.enrollment"].browse(learners[0][1]).action_suspend_access(reason="Fictional concurrent revoke")
    except LockError:
        administrative.rollback()
    else:
        raise AssertionError("Administrative access changes must respect a running answer")
    second.commit()
    first.commit()
with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = services(first, second)
    one._submit(attempts[0])
    two._submit(attempts[1])
    second.commit()
    first.commit()
env.cr.rollback()
env.invalidate_all()
assert delivery.revision == revision
rows = env["survey.user_input"].browse(attempts)
assert rows.mapped("state") == ["done", "done"]
assert rows[0].user_input_line_ids.suggested_answer_id.id == right
assert rows[1].user_input_line_ids.suggested_answer_id.id == wrong
print("EXAM_PARALLEL_OK: one delivery, parallel start, answers and submission; administrative lock preserved")
