"""Persisted fictional native Survey definitions; never a learner passation."""

import json

from odoo import Command
from odoo.tests import new_test_user

if not env.cr.dbname.startswith("tm_j1m_"):
    raise RuntimeError("Use an isolated tm_j1m_* database")
params = env["ir.config_parameter"]
key = "training_mock_exam.j1_snapshot"
expected = params.get_str(key)


def snapshot(exams):
    return {
        "surveys": exams.read(
            [
                "id",
                "training_course_id",
                "training_state",
                "training_origin_id",
                "training_version",
                "training_revision_reason",
                "title",
                "time_limit",
            ]
        ),
        "questions": exams.question_ids.read(
            [
                "id",
                "survey_id",
                "title",
                "answer_score",
                "training_theme",
                "training_explanation",
                "training_interaction",
            ]
        ),
        "choices": exams.question_ids.suggested_answer_ids.read(
            [
                "id",
                "question_id",
                "value",
                "is_correct",
                "training_row_key",
                "training_row_label",
                "training_option_key",
                "training_option_label",
            ]
        ),
    }


if not expected:
    author = new_test_user(env, login="j1m_fixture_author", groups="training_mock_exam.group_mock_exam_author")
    course = env["training.course"].create({"name": "Fictional common mock course"})
    exam = (
        env["survey.survey"]
        .with_user(author)
        .create({"title": "Fictional common mock", "training_course_id": course.id, "time_limit": 15})
    )
    question = (
        env["survey.question"]
        .with_user(author)
        .create(
            {
                "survey_id": exam.id,
                "title": "Fictional question",
                "question_type": "multiple_choice",
                "answer_score": 2,
                "training_theme": "Fictional theme",
                "training_explanation": "Fictional correction",
                "suggested_answer_ids": [
                    Command.create({"value": "Yes", "is_correct": True}),
                    Command.create({"value": "No"}),
                ],
            }
        )
    )
    question._configure_interaction("ordering", "Alpha\nBeta")
    exam.action_mock_publish()
    version = env["survey.survey"].browse(exam.action_mock_new_version()["res_id"]).with_user(author)
    version.write({"training_version": "2", "training_revision_reason": "Fictional revision"})
    version.action_mock_publish()
    exams = (exam | version).with_env(env).sorted("id")
    params.set_str(key, json.dumps({"ids": exams.ids, "snapshot": snapshot(exams)}, default=str))
    env.cr.commit()  # Deliberate fictional fixture persisted across module update processes.
    print("J1_MOCK_HISTORY_PREPARED")
else:
    saved = json.loads(expected)
    actual = json.loads(json.dumps(snapshot(env["survey.survey"].browse(saved["ids"])), default=str))
    assert actual == saved["snapshot"], "Native definitions, versions or corrections changed"
    print("J1_MOCK_NATIVE_DEFINITIONS_AND_CORRECTIONS_PRESERVED")
installed = set(env["ir.module.module"].search([("state", "=", "installed")]).mapped("name"))
assert (
    not {
        "training_management",
        "training_management_survey",
        "training_management_elearning",
        "training_elearning",
        "website_slides",
        "sale_management",
    }
    & installed
)
print("J1_MOCK_WITHOUT_BUSINESS_APPS_CONFIRMED")
