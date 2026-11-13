"""Same-generation adapter extraction: keep native evidence from the reader tranche."""

import json
import os

from odoo import Command

if env.cr.dbname != "tm_s01_test_p09":
    raise RuntimeError("Use the isolated runtime upgrade database")
params = env["ir.config_parameter"]
phase = os.environ["J1_RUNTIME_PHASE"]
key = "training_mock_exam.tm_runtime_upgrade"


def snapshot(attempts):
    env.flush_all()
    return {
        "attempts": attempts.read(
            [
                "id",
                "survey_id",
                "training_enrollment_id",
                "training_activity_id",
                "training_family_id",
                "training_review_ids",
                "predefined_question_ids",
                "state",
                "deadline",
                "start_datetime",
                "end_datetime",
                "scoring_percentage",
                "scoring_total",
            ]
        ),
        "lines": attempts.user_input_line_ids.sorted("id").read(
            ["id", "user_input_id", "question_id", "suggested_answer_id", "answer_score", "answer_is_correct"]
        ),
        "revisions": attempts.training_adjustment_ids.sorted("id").read(
            ["id", "attempt_id", "reason", "points_by_question", "previous_id"]
        ),
    }


if phase == "prepare":
    previous = json.loads(params.get_str("training_management_test.p09"))
    enrollment = env["training.enrollment"].browse(previous["enrollment"])
    coord = previous["coord"]
    exam = (
        env["survey.survey"]
        .with_user(coord)
        .create(
            {"title": "Fictional preserved runtime exam", "training_program_id": previous["program"], "time_limit": 30}
        )
    )
    question = (
        env["survey.question"]
        .with_user(coord)
        .create(
            {
                "title": "Fictional preserved question",
                "survey_id": exam.id,
                "question_type": "simple_choice",
                "answer_score": 2,
                "suggested_answer_ids": [
                    Command.create({"value": "Expected", "is_correct": True}),
                    Command.create({"value": "Other"}),
                ],
            }
        )
    )
    exam.action_training_publish()
    activity = (
        env["training.learning.activity"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional preserved exam activity",
                "delivery_id": enrollment.delivery_id.id,
                "criterion": "evaluation",
                "evaluation_threshold": 80,
                "training_exam_id": exam.id,
            }
        )
    )
    service = env["training.exam.service"].with_user(enrollment.user_id)
    done = service._start(enrollment.id, activity.id)
    service._save(done.id, question.id, question.suggested_answer_ids.filtered("is_correct").ids, True)
    service._submit(done.id)
    revisions = env["training.exam.revision"].with_user(coord)
    revisions._record(done, {str(question.id): 0}, "Fictional first revision")
    revisions._record(done, {str(question.id): 1}, "Fictional second revision")
    active = service._start(enrollment.id, activity.id)
    service._save(active.id, question.id, question.suggested_answer_ids.filtered("is_correct").ids, True)
    attempts = (done | active).with_env(env).sorted("id")
    params.set_str(
        key,
        json.dumps(
            {
                "ids": attempts.ids,
                "active": active.id,
                "done": done.id,
                "enrollment": enrollment.id,
                "activity": activity.id,
                "actor": enrollment.user_id.id,
                "snapshot": snapshot(attempts),
            },
            default=str,
        ),
    )
    env.cr.commit()
    print("J1_TM_NATIVE_ATTEMPTS_REVIEWS_AND_REVISIONS_PREPARED_BEFORE_EXTRACTION")
else:
    saved = json.loads(params.get_str(key))
    attempts = env["survey.user_input"].browse(saved["ids"])
    actual = json.loads(json.dumps(snapshot(attempts), default=str))
    assert actual == saved["snapshot"], "The extraction changed existing native exam evidence"
    assert not any(attempts.mapped("mock_context_key")), "No context identity should be invented on old evidence"
    service = env["training.exam.service"].with_user(saved["actor"])
    assert service._result(env["survey.user_input"].browse(saved["done"]))["percentage"] == 50
    resumed = service._start(saved["enrollment"], saved["activity"])
    assert resumed.id == saved["active"] and resumed.training_review_ids
    service._submit(resumed.id)
    fresh = service._start(saved["enrollment"], saved["activity"])
    assert fresh.id not in saved["ids"] and fresh.mock_context_key == "training.enrollment:%s" % saved["enrollment"]
    assert not fresh.user_input_line_ids and not fresh.training_review_ids
    env.cr.commit()
    print("J1_TM_NATIVE_ATTEMPTS_REVIEWS_DEADLINES_SCORES_REVISIONS_AND_RESUME_PRESERVED")
