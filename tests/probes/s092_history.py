"""Retain closed summaries, anonymous native inputs and the unordered replay pool."""

import hashlib
import json
import os
from datetime import timedelta

from odoo import Command, fields

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S09.2 fixture database only")
key = "training_management_test.s092_snapshot"


def reference(name, record):
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": name, "model": record._name, "res_id": record.id}
    )


def snapshot():
    env.flush_all()
    result = {}
    for table in (
        "training_feedback",
        "training_feedback_campaign",
        "training_feedback_recipient",
        "training_feedback_spent",
        "training_feedback_notice",
        "survey_user_input",
        "survey_user_input_line",
        "training_proof",
        "training_document",
    ):
        env.cr.execute(f"SELECT to_jsonb(t) FROM {table} t ORDER BY id")
        result[table] = [r[0] for r in env.cr.fetchall()]
    dossier = env.ref("training_management_test.s08_dossier")
    result["pdf"] = [hashlib.sha256(p.data.content).hexdigest() for p in dossier.evidence_ids if p.data]
    return json.dumps(result, default=str, sort_keys=True)


if os.environ["S092_PHASE"] == "prepare":
    actor = env.ref("training_management_test.s052_coordinator")
    program = env.ref("training_management_test.s08_dossier").delivery_id.program_id
    delivery = (
        env["training.delivery"]
        .with_user(actor)
        .create(
            {
                "name": "Fictional retained S092 delivery",
                "company_id": program.company_id.id,
                "program_id": program.id,
                "kind": "autonomous",
                "capacity": 10,
                "access_policy": "duration",
                "access_days": 30,
            }
        )
    )
    definition = (
        env["training.feedback"]
        .with_user(actor)
        .create(
            {
                "name": "Fictional retained feedback",
                "program_id": program.id,
                "purpose": "immediate",
                "anonymous": True,
                "criteria": "One choice",
                "version": "retained-1",
            }
        )
    )
    survey = env["survey.survey"].with_user(actor).browse(definition.action_questionnaire()["res_id"])
    question = (
        env["survey.question"]
        .with_user(actor)
        .create(
            {
                "survey_id": survey.id,
                "title": "Fictional useful feedback?",
                "question_type": "simple_choice",
                "constr_mandatory": True,
                "suggested_answer_ids": [Command.create({"value": "Yes"}), Command.create({"value": "No"})],
            }
        )
    )
    definition.write(
        {
            "indicator_question_id": question.id,
            "favorable_answer_ids": [Command.set(question.suggested_answer_ids[:1].ids)],
        }
    )
    definition.action_publish()
    campaign = (
        env["training.feedback.campaign"]
        .with_user(actor)
        .create(
            {
                "name": "Fictional retained anonymous collection",
                "delivery_id": delivery.id,
                "feedback_id": definition.id,
                "population": "Three fictional active participants",
                "retention_id": env.ref("training_management_test.s08_dossier").retention_id.id,
                "opens_at": fields.Datetime.now() - timedelta(days=1),
                "due_at": fields.Datetime.now() + timedelta(days=7),
            }
        )
    )
    users = []
    for i in range(3):
        user = (
            env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Fictional S092 %s" % i,
                    "login": "s092_probe_%s" % i,
                    "company_id": program.company_id.id,
                    "company_ids": [Command.set(program.company_id.ids)],
                    "group_ids": [Command.set(env.ref("base.group_portal").ids)],
                }
            )
        )
        users.append(user)
        enrollment = (
            env["training.enrollment"]
            .with_user(actor)
            .create(
                {
                    "delivery_id": delivery.id,
                    "participant_id": user.partner_id.id,
                    "user_id": user.id,
                    "free_reason": "Fictional feedback fixture",
                }
            )
        )
        enrollment.action_validate_prerequisites(reason="Fictional review")
        enrollment.action_confirm()
        env["training.feedback.recipient"].with_user(actor).create(
            {"campaign_id": campaign.id, "user_id": user.id, "role": "participant", "enrollment_id": enrollment.id}
        )
        reference("s092_user_%s" % i, user)
    campaign.action_open()
    for user in users:
        env["training.feedback.service"].with_user(user)._submit(
            campaign.id, "participant", {question.id: question.suggested_answer_ids[:1].ids}
        )
    campaign.action_close()
    assert campaign.snapshot["received"] == 3 and campaign.snapshot["rate"] == 100
    opened = env["training.feedback.campaign"].with_user(actor).browse(campaign.action_new_collection()["res_id"])
    opened.action_open()
    reference("s092_campaign", campaign)
    reference("s092_concurrent_campaign", opened)
    reference("s092_question", question)
    env["ir.config_parameter"].sudo().set_str(key, snapshot())
    env.cr.commit()  # Disposable synthetic fixture only.
    print("S092_HISTORY_PREPARED")
else:
    assert snapshot() == env["ir.config_parameter"].sudo().get_str(key)
    print("S092_HISTORY_OK: closed aggregates, inputs, replay pools, notices and old S08 PDF bytes preserved")
