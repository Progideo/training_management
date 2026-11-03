"""Native ORM proof only, on a fresh J1 base with website_slides_survey and no TM.

No target access rule or target obligation is claimed by these native contracts.
The shell rolls back all fictional records on exit.
"""

from psycopg2 import IntegrityError

from odoo import Command
from odoo.tools import mute_logger

if not env.cr.dbname.startswith("tm_j1_") or "training.enrollment" in env:
    raise RuntimeError("Use an isolated J1 native-only database")
partner = env["res.partner"].create({"name": "Fictional native learner", "email": "native@example.invalid"})
courses = env["slide.channel"].create([{"name": "Fictional edition A"}, {"name": "Fictional edition B"}])
first = env["slide.channel.partner"].create({"channel_id": courses[0].id, "partner_id": partner.id})
second = env["slide.channel.partner"].create({"channel_id": courses[1].id, "partner_id": partner.id})
try:
    with mute_logger("odoo.sql_db"), env.cr.savepoint():
        env["slide.channel.partner"].create({"channel_id": courses[0].id, "partner_id": partner.id})
        env.flush_all()
except IntegrityError:
    print("J1_NATIVE_UNIQUE_MEMBERSHIP_CONFIRMED")
else:
    raise AssertionError("Duplicate membership accepted")

exams = env["survey.survey"].create(
    [
        {"title": "Fictional exam A", "scoring_type": "scoring_with_answers", "is_attempts_limited": False},
        {"title": "Fictional exam B", "scoring_type": "scoring_with_answers", "is_attempts_limited": False},
    ]
)
question = env["survey.question"].create(
    {
        "survey_id": exams[0].id,
        "title": "Fictional question",
        "question_type": "simple_choice",
        "suggested_answer_ids": [
            Command.create({"value": "Correct", "is_correct": True, "answer_score": 1}),
            Command.create({"value": "Incorrect", "is_correct": False, "answer_score": 0}),
        ],
    }
)
slides = env["slide.slide"].create(
    [
        {"name": "Exam A", "channel_id": courses[0].id, "survey_id": exams[0].id, "is_published": True},
        {"name": "Exam B", "channel_id": courses[0].id, "survey_id": exams[1].id, "is_published": True},
        {"name": "Shared exam A", "channel_id": courses[1].id, "survey_id": exams[0].id, "is_published": True},
    ]
)
assert len(courses[0].slide_ids) == 2 and slides[0].survey_id == slides[2].survey_id
print("J1_NATIVE_MULTIPLE_AND_SHARED_EXAMS_CONFIRMED")
bindings = env["slide.slide.partner"].create(
    [
        {"slide_id": slides[0].id, "partner_id": partner.id},
        {"slide_id": slides[2].id, "partner_id": partner.id},
    ]
)
answer = exams[0]._create_answer(partner=partner, slide_partner_id=bindings[0].id)
answer._save_lines(question, question.suggested_answer_ids.filtered("is_correct").id)
answer._mark_done()
assert answer.scoring_success
env.flush_all()
assert bindings[0].completed and not bindings[1].completed
first._recompute_completion()
assert first.completion == 50, first.completion
assert not second.completion
print("J1_NATIVE_SECOND_EXAM_BLOCKS_100_PERCENT_CONTEXTS_SEPARATE")
# Native ORM permits a fresh empty answer even after success. The native slide URL
# generator reuses the last answer, so this does not prove target UI retry behavior.
retry = exams[0]._create_answer(partner=partner, slide_partner_id=bindings[0].id)
assert retry != answer and not retry.user_input_line_ids
retry._save_lines(question, question.suggested_answer_ids.filtered(lambda row: not row.is_correct).id)
retry._mark_done()
env.flush_all()
assert not retry.scoring_success and bindings[0].completed
assert exams[0]._has_attempts_left(partner, partner.email, False)
print("J1_NATIVE_RETRY_AFTER_SUCCESS_AND_FIRST_ACQUISITION_PRESERVED")
assert not slides[0].can_self_mark_completed
print("J1_NATIVE_EXAM_SELF_COMPLETION_DISABLED")
print("J1_NATIVE_CONTRACTS_OK_NOT_TARGET_ACCESS_OR_OPTIONALITY_PROOF")
