"""Retain native P10 definitions and all earlier histories across a repeated update."""

import hashlib
import json
import os

from odoo import Command
from odoo.tools import SQL

if env.cr.dbname != "tm_s01_test_p09":
    raise RuntimeError("Disposable P09/P10 history database only")
params = env["ir.config_parameter"]
key = "training_management_test.p10"


def snapshot():
    env.flush_all()
    result = {}
    for table in (
        "survey_survey",
        "survey_question",
        "survey_question_answer",
        "survey_user_input",
        "survey_user_input_line",
        "training_orientation_rule",
        "training_enrollment",
        "training_path_assignment",
        "sale_order",
        "sale_order_line",
    ):
        env.cr.execute(SQL("SELECT to_jsonb(t)::text FROM %s t ORDER BY id", SQL.identifier(table)))
        result[table] = hashlib.sha256(json.dumps(env.cr.fetchall()).encode()).hexdigest()
    return result


if os.environ["P09_PHASE"] == "orientation_prepare":
    previous = json.loads(params.get_str("training_management_test.p09"))
    actor = env(user=env["res.users"].browse(previous["coord"]))
    diagnostic = actor["survey.survey"].create(
        {
            "title": "Fictional pre-purchase diagnostic",
            "orientation_company_id": actor.company.id,
            "orientation_contact": "Fictional advisor : conseil@example.invalid",
        }
    )
    question = actor["survey.question"].create(
        {
            "survey_id": diagnostic.id,
            "title": "Fictional experience?",
            "question_type": "simple_choice",
            "suggested_answer_ids": [Command.create({"value": "Beginner"}), Command.create({"value": "Experienced"})],
        }
    )
    actor["training.orientation.rule"].create(
        {
            "survey_id": diagnostic.id,
            "answer_ids": [Command.set(question.suggested_answer_ids[:1].ids)],
            "level": "Discovery",
            "explanation": "Start with the fundamentals.",
        }
    )
    diagnostic.action_orientation_publish()
    params.set_str(key, json.dumps({"survey": diagnostic.id, "snapshot": snapshot()}))
    env.cr.commit()  # explicit disposable shell transaction only
    print("P10 orientation definitions baseline OK")
else:
    saved = json.loads(params.get_str(key))
    assert snapshot() == saved["snapshot"], "P10 or earlier history changed during update"
    diagnostic = env["survey.survey"].browse(saved["survey"])
    question = diagnostic.question_ids
    result = diagnostic._orientation_result({str(question.id): str(question.suggested_answer_ids[0].id)})
    assert result and result["name"] == "Discovery"
    assert snapshot() == saved["snapshot"], "Reading a diagnostic persisted answers"
    print("P10 orientation and prior histories preserved; result read without writes OK")
