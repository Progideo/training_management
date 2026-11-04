"""Real native answers/timers; a test-only grant stub replaces the absent business adapter."""

from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged, new_test_user

from .test_library import MockCase


@tagged("post_install", "-at_install")
class TestSharedRuntime(MockCase):
    def setUp(self):
        super().setUp()
        self.learner = new_test_user(self.env, login="mock_engine_learner", groups="base.group_portal")
        self.exam_record, self.question = self.exam()
        self.exam_record.action_mock_publish()
        self.engine = self.env["training.mock.exam.service"].with_user(self.learner)
        self.allowed = set()

    def start(self, context="test.grant:1"):
        attempt = self.engine._start_native(self.exam_record.sudo(), context, {})
        self.allowed.add(attempt.id)
        return attempt

    @contextmanager
    def grant(self):
        allowed = self.allowed

        def authorized(service, attempt_id, *, mutate=False):
            attempt = service.env["survey.user_input"].sudo().browse(attempt_id).exists()
            if not attempt or attempt.id not in allowed or attempt.partner_id != service.env.user.partner_id:
                raise AccessError(service.env._("Test grant denied"))
            if mutate or attempt.state != "done":
                attempt._mock_close_if_expired()
            return attempt

        with patch.object(type(self.engine), "_attempt", authorized):
            yield

    def test_context_resume_two_exams_and_unlimited_retake_after_success(self):
        first = self.start()
        self.assertEqual(self.start(), first)
        other_context = self.start("test.grant:2")
        self.assertNotEqual(first, other_context)
        second_exam, _ = self.exam()
        second_exam.action_mock_publish()
        second = self.engine._start_native(second_exam.sudo(), "test.grant:1", {})
        self.assertNotEqual(first, second)
        with self.grant():
            self.engine._save(
                first.id, self.question.id, self.question.suggested_answer_ids.filtered("is_correct").ids, True
            )
            with self.assertRaises(AccessError):
                self.engine._result(first)
            self.engine._submit(first.id)
            result = self.engine._result(first)
        self.assertEqual(result["percentage"], 100)
        self.assertTrue(result["success"])
        fresh = self.start()
        self.assertNotEqual(fresh, first)
        self.assertFalse(fresh.user_input_line_ids)
        self.assertFalse(fresh.training_review_ids)
        self.assertEqual(other_context.state, "in_progress")
        self.assertEqual(first.scoring_percentage, 100)

    def test_adapter_evidence_filter_excludes_without_widening_context_or_erasing_answers(self):
        passed = self.start()
        with self.grant():
            self.engine._save(
                passed.id, self.question.id, self.question.suggested_answer_ids.filtered("is_correct").ids, False
            )
            self.engine._submit(passed.id)
        failed = self.start()
        with self.grant():
            self.engine._submit(failed.id)
        partner = self.learner.partner_id.id
        status = self.engine._obligation_status(self.exam_record, "test.grant:1", partner, "pass")
        self.assertTrue(status["satisfied"])
        excluded = self.engine._obligation_status(
            self.exam_record, "test.grant:1", partner, "pass", attempt_domain=[("id", "!=", passed.id)]
        )
        self.assertFalse(excluded["satisfied"])
        self.assertEqual(excluded["score"], 0)
        other = self.start("test.grant:2")
        with self.grant():
            self.engine._save(
                other.id, self.question.id, self.question.suggested_answer_ids.filtered("is_correct").ids, False
            )
            self.engine._submit(other.id)
        outside = self.engine._obligation_status(
            self.exam_record, "test.grant:1", partner, "pass", attempt_domain=[("id", "=", other.id)]
        )
        self.assertFalse(outside["complete"])
        empty = self.engine._obligation_status(
            self.exam_record,
            "test.grant:1",
            partner,
            "complete",
            attempt_domain=[("id", "not in", (passed | failed).ids)],
        )
        self.assertFalse(empty["satisfied"])
        self.assertTrue(passed.user_input_line_ids)
        self.assertTrue(self.engine._obligation_status(self.exam_record, "test.grant:1", partner, "pass")["satisfied"])

    def test_exact_deadline_closes_without_saving_late_answers_or_restarting(self):
        attempt = self.start()
        deadline = attempt.deadline
        with self.grant(), patch.object(fields.Datetime, "now", return_value=deadline):
            self.assertEqual(self.engine._save(attempt.id, self.question.id, [], False), {"done": True})
            self.assertEqual(self.engine._submit(attempt.id), {"done": True})
            self.assertEqual(self.engine._submit(attempt.id), {"done": True})
        self.assertFalse(attempt.user_input_line_ids)
        self.assertEqual(attempt.end_datetime, deadline)
        self.assertEqual(attempt.deadline, deadline)
        self.assertEqual(attempt.state, "done")

    def test_cron_persists_last_confirmed_answer_and_is_idempotent(self):
        attempt = self.start()
        with self.grant():
            self.engine._save(
                attempt.id, self.question.id, self.question.suggested_answer_ids.filtered("is_correct").ids, False
            )
        with patch.object(fields.Datetime, "now", return_value=attempt.deadline + timedelta(seconds=1)):
            self.env["survey.user_input"]._cron_mock_expire()
            self.env["survey.user_input"]._cron_mock_expire()
        self.assertEqual(attempt.state, "done")
        self.assertEqual(attempt.end_datetime, attempt.deadline)
        self.assertEqual(attempt.scoring_percentage, 100)
        with self.assertRaises(AccessError):
            attempt.user_input_line_ids.write({"skipped": True})
        with self.assertRaises(ValidationError):
            attempt.unlink()

    def test_fail_closed_authorization_and_direct_native_mutation(self):
        attempt = self.start()
        with self.assertRaises(AccessError):
            self.engine._submit(attempt.id)
        with self.assertRaises(AccessError):
            self.engine._result(attempt)
        self.allowed.clear()
        with self.grant(), self.assertRaises(AccessError):
            self.engine._save(attempt.id, self.question.id, [], False)
        with self.assertRaises(AccessError):
            attempt.with_user(self.author).write({"deadline": fields.Datetime.now()})
        with self.assertRaises(AccessError):
            self.env["survey.user_input"].with_context(default_mock_context_key="forged:1").create(
                {"survey_id": self.exam_record.id}
            )

        ordinary = (
            self.env["survey.survey"].with_user(self.author).create({"title": "Fictional ordinary native survey"})
        )
        for value in (0, False, ""):
            with self.assertRaises(AccessError):
                self.env["survey.user_input"].create({"survey_id": ordinary.id, "mock_context_key": value})
            with self.assertRaises(AccessError):
                self.env["survey.user_input"].with_context(default_mock_context_key=value).create(
                    {"survey_id": ordinary.id}
                )

    def test_definition_author_cannot_read_learner_evidence_via_public_attachment(self):
        attempt = self.start()
        attachment = self.env["ir.attachment"].create(
            {"name": "Fictional learner evidence", "raw": b"PRIVATE LEARNER EVIDENCE"}
        )
        # Model a pre-existing accidental public pointer, without weakening the factory.
        attachment.flush_recordset()
        self.cr.execute(
            "UPDATE ir_attachment SET res_model='survey.user_input', res_id=%s, public=TRUE WHERE id=%s",
            [attempt.id, attachment.id],
        )
        attachment.invalidate_recordset()
        self.assertFalse(attachment.with_user(self.author).search([("id", "=", attachment.id)]))
        with self.assertRaises(AccessError):
            self.env["ir.binary"].with_user(self.author)._get_stream_from(attachment.with_user(self.author))

    def test_enriched_answers_have_no_partial_credit_or_duplicate_items(self):
        exam, question = self.exam()
        question._configure_interaction("ordering", "One\nTwo")
        exam.action_mock_publish()
        attempt = self.engine._start_native(exam.sudo(), "test.grant:1", {})
        self.allowed.add(attempt.id)
        with self.grant():
            same_option = question.suggested_answer_ids.filtered(lambda a: a.training_option_label == "One")
            with self.assertRaises(ValidationError):
                self.engine._save(attempt.id, question.id, same_option.ids, False)
            self.engine._save(
                attempt.id, question.id, question.suggested_answer_ids.filtered("is_correct")[:1].ids, False
            )
            self.engine._submit(attempt.id)
            self.assertEqual(self.engine._result(attempt)["percentage"], 0)
