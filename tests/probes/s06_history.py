"""S05 work and ordinary Survey histories survive installing the exam bridge."""

import json
import os
from uuid import uuid4

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable CI history database only")
phase = os.environ["S06_PHASE"]
key = "training_management_test.s06_history"


def remember(name, record):
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": name, "model": record._name, "res_id": record.id}
    )


def snapshot():
    entry = env.ref("training_management_test.s06_entry")
    attempt = env.ref("training_management_test.s06_native_attempt")
    return json.dumps(
        {
            "entry": entry.read(["enrollment_id", "activity_id", "sealed_at", "message_id"]),
            "message": entry.message_id.read(["body", "author_id", "model", "res_id"]),
            "native_attempt": attempt.read(
                ["state", "start_datetime", "end_datetime", "scoring_total", "scoring_percentage"]
            ),
            "native_lines": attempt.user_input_line_ids.read(["question_id", "suggested_answer_id", "answer_score"]),
        },
        sort_keys=True,
        default=str,
    )


if phase == "prepare":
    enrollment = env.ref("training_management_test.s052_enrollment")
    coordinator = env["res.users"].search([("login", "=", "s052_history_coord")], limit=1)
    activity = (
        env["training.learning.activity"]
        .with_user(coordinator)
        .create(
            {
                "name": "Fictional preserved exercise",
                "delivery_id": enrollment.delivery_id.id,
                "criterion": "submission",
            }
        )
    )
    entry = (
        env["training.learning.service"]
        .with_user(enrollment.user_id)
        ._post(
            enrollment.id,
            "submission",
            activity_id=activity.id,
            request_key=str(uuid4()),
            body="Fictional preserved private work",
        )
    )
    # The native service returns an entry record; its message remains canonical.
    remember("s06_entry", entry)
    survey = env["survey.survey"].create({"title": "Ordinary preserved Survey", "scoring_type": "scoring_with_answers"})
    from odoo import Command

    question = env["survey.question"].create(
        {
            "survey_id": survey.id,
            "title": "Ordinary preserved question",
            "question_type": "simple_choice",
            "suggested_answer_ids": [
                Command.create({"value": "Yes", "is_correct": True, "answer_score": 1}),
                Command.create({"value": "No"}),
            ],
        }
    )
    attempt = survey._create_answer(partner=enrollment.participant_id)
    attempt._mark_in_progress()
    attempt._save_lines(question, question.suggested_answer_ids[:1].ids)
    attempt._mark_done()
    remember("s06_native_attempt", attempt)
    env["ir.config_parameter"].set_str(key, snapshot())
    env.cr.commit()  # Isolated fictional CI fixture, before the upgrade process.
    print("S06_HISTORY_PREPARED")
elif phase == "verify":
    assert snapshot() == env["ir.config_parameter"].get_str(key)
    print("S06_PRIVATE_WORK_AND_NATIVE_SURVEY_HISTORY_OK")
    env.cr.rollback()
else:
    raise RuntimeError("Unknown history phase")
