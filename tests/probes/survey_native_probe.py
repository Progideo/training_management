"""Run with Odoo shell on a disposable tm_s01_test_* database only.

This probes the native models, not the browser or HTTP routes.
Fixtures are fictional, no certification is sent, and all changes roll back.
"""

import json
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError


def run_probe(env):
    if not env.cr.dbname.startswith("tm_s01_test_"):
        raise RuntimeError("This probe requires a disposable tm_s01_test_* database.")
    results = {}
    try:
        user = (
            env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Fictional survey participant",
                    "login": "fictional-survey-participant",
                    "group_ids": [Command.set([env.ref("base.group_portal").id])],
                }
            )
        )
        survey = env["survey.survey"].create(
            {
                "title": "Fictional native coverage probe",
                "questions_layout": "one_page",
                "questions_selection": "all",
                "scoring_type": "scoring_with_answers",
                "is_attempts_limited": False,
                "is_time_limited": True,
                "time_limit": 10,
                "certification": False,
                "users_login_required": True,
            }
        )
        question = env["survey.question"].create(
            {
                "survey_id": survey.id,
                "title": "Select exactly A and B",
                "question_type": "multiple_choice",
                "suggested_answer_ids": [
                    Command.create({"value": "A", "answer_score": 1, "is_correct": True}),
                    Command.create({"value": "B", "answer_score": 1, "is_correct": True}),
                    Command.create({"value": "C", "answer_score": 0, "is_correct": False}),
                ],
            }
        )
        first = survey._create_answer(user=user)
        first._save_lines(question, question.suggested_answer_ids.ids)
        results["all_choices_including_wrong_score"] = first.scoring_percentage
        assert first.scoring_percentage == 100, "Native scoring changed; reassess EXA02."
        # Avoid _mark_done and its notification side effects: only model scoring
        # and creation eligibility are probed, not the final submission workflow.
        first.write({"state": "done"})
        second = survey._create_answer(user=user)
        second._save_lines(question, question.suggested_answer_ids[:1].ids)
        results["partial_answer_score"] = second.scoring_percentage
        assert second.scoring_percentage == 50
        third = survey._create_answer(user=user)
        results["new_attempt_after_success"] = bool(second and first.scoring_success)
        results["simultaneous_unfinished_attempts"] = len(
            (second | third).filtered(lambda record: record.state != "done")
        )
        assert results["simultaneous_unfinished_attempts"] == 2

        second.write(
            {
                "state": "in_progress",
                "start_datetime": fields.Datetime.now() - timedelta(minutes=11),
            }
        )
        results["expired_at_ten_minutes"] = second.survey_time_limit_reached
        survey.time_limit = 20
        results["expired_after_source_duration_change"] = second.survey_time_limit_reached
        assert results["expired_at_ten_minutes"]
        assert not results["expired_after_source_duration_change"]

        question.title = "Changed after completion"
        results["completed_attempt_question_title"] = first.user_input_line_ids[0].question_id.title
        assert results["completed_attempt_question_title"] == "Changed after completion"
        try:
            first.with_user(user).read(["state"])
        except AccessError:
            results["portal_direct_orm_read"] = "denied"
        else:
            results["portal_direct_orm_read"] = "allowed"
        results["lines_before_question_deletion"] = len(first.user_input_line_ids)
        question.unlink()
        env.invalidate_all()
        results["lines_after_question_deletion"] = len(first.user_input_line_ids)
        assert results["lines_after_question_deletion"] == 0
        print("SURVEY_NATIVE_PROBE=" + json.dumps(results, sort_keys=True))
    finally:
        env.cr.rollback()


run_probe(env)  # noqa: F821 - provided by `odoo shell`
