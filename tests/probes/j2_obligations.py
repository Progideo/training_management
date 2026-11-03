"""Persisted shared offer obligations, real native evidence and independent contexts."""

import json
from odoo import Command

if env.cr.dbname != "tm_s01_test_p09":
    raise RuntimeError("Use the isolated J2 database")
params = env["ir.config_parameter"]
key = "training_mock_exam.j2_obligations"
saved = params.get_str(key)


def snapshot(spec):
    env.flush_all()
    requirements = env["training.exam.requirement"].search([("enrollment_id", "in", spec["enrollments"])], order="id")
    attempts = env["survey.user_input"].browse(spec["attempts"])
    learning = env["training.learning.service"]
    return {
        "requirements": requirements.read(
            ["id", "enrollment_id", "activity_id", "exam_id", "obligation", "company_id"]
        ),
        "attempts": attempts.read(
            [
                "id",
                "survey_id",
                "training_enrollment_id",
                "training_activity_id",
                "mock_context_key",
                "mock_reader_group_id",
                "mock_company_id",
                "deadline",
                "state",
                "scoring_percentage",
            ]
        ),
        "answers": attempts.user_input_line_ids.sorted("id").read(
            ["id", "user_input_id", "question_id", "suggested_answer_id", "answer_score"]
        ),
        "completion": [
            learning._complete(env["training.enrollment"].browse(e), env["training.learning.activity"].browse(a))
            for e, a in zip(spec["enrollments"], spec["activities"])
        ],
        "optional": learning._required_for_certificate(env["training.learning.activity"].browse(spec["optional"])),
    }


if not saved:
    previous = json.loads(params.get_str("training_management_test.p09"))
    coord = previous["coord"]
    original = env["training.enrollment"].browse(previous["enrollment"])
    exams = env["survey.survey"]
    for label in ("Main", "Optional"):
        exam = (
            env["survey.survey"]
            .with_user(coord)
            .create(
                {
                    "title": "Fictional J2 " + label,
                    "training_course_id": original.delivery_id.program_id.course_id.id,
                    "time_limit": 10,
                    "scoring_success_min": 80,
                }
            )
        )
        env["survey.question"].with_user(coord).create(
            {
                "survey_id": exam.id,
                "title": "Fictional J2 question",
                "question_type": "simple_choice",
                "answer_score": 2,
                "suggested_answer_ids": [
                    Command.create({"value": "Expected", "is_correct": True}),
                    Command.create({"value": "Other"}),
                ],
            }
        )
        exam.action_mock_publish()
        exams |= exam.with_env(env)
    enrollments, activities = [], []
    for obligation in ("complete", "pass"):
        delivery = (
            env["training.delivery"]
            .with_user(coord)
            .create(
                {
                    "name": "Fictional J2 " + obligation,
                    "program_id": previous["program"],
                    "kind": "autonomous",
                    "access_policy": "duration",
                    "access_days": 30,
                }
            )
        )
        activity = (
            env["training.learning.activity"]
            .with_user(coord)
            .create(
                {
                    "name": "Fictional J2 required exam",
                    "delivery_id": delivery.id,
                    "criterion": "evaluation",
                    "training_exam_id": exams[0].id,
                    "exam_obligation": obligation,
                }
            )
        )
        optional = (
            env["training.learning.activity"]
            .with_user(coord)
            .create(
                {
                    "name": "Fictional J2 optional exam",
                    "delivery_id": delivery.id,
                    "criterion": "evaluation",
                    "training_exam_id": exams[1].id,
                    "exam_obligation": "optional",
                }
            )
        )
        enrollment = (
            env["training.enrollment"]
            .with_user(coord)
            .create(
                {
                    "delivery_id": delivery.id,
                    "participant_id": original.participant_id.id,
                    "user_id": original.user_id.id,
                    "free_reason": "Fictional J2 invitation",
                }
            )
        )
        enrollment.action_validate_prerequisites(reason="Fictional J2 prerequisites")
        enrollment.action_confirm()
        enrollment.action_authorize(reason="Fictional J2 authorization")
        enrollment.action_open_access(reason="Fictional J2 opening")
        enrollments.append(enrollment.id)
        activities.append(activity.id)
    service = env["training.exam.service"].with_user(original.user_id)
    attempts = []
    for index, (enrollment_id, activity_id) in enumerate(zip(enrollments, activities)):
        attempt = service._start(enrollment_id, activity_id)
        if index:
            q = attempt.predefined_question_ids[0]
            service._save(attempt.id, q.id, q.suggested_answer_ids.filtered("is_correct").ids, False)
        service._submit(attempt.id)
        attempts.append(attempt.id)
    failed = service._start(enrollments[1], activities[1])
    service._submit(failed.id)
    attempts.append(failed.id)
    spec = {"enrollments": enrollments, "activities": activities, "optional": optional.id, "attempts": attempts}
    spec["snapshot"] = snapshot(spec)
    params.set_str(key, json.dumps(spec, default=str))
    env.cr.commit()
    print("J2_SHARED_OFFERS_FROZEN_OBLIGATIONS_AND_NATIVE_EVIDENCE_PREPARED")
else:
    spec = json.loads(saved)
    actual = json.loads(json.dumps(snapshot(spec), default=str))
    assert actual == spec["snapshot"], "The update changed obligations, context evidence or completion"
    assert actual["completion"] == [True, True] and actual["optional"] is False
    print("J2_SHARED_OFFERS_OBLIGATIONS_NATIVE_CONTEXTS_AND_COMPLETION_PRESERVED")
