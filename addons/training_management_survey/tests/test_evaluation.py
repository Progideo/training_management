"""S09.1 native Surveys are distinct from mocks, including HTTP and revocation."""

from datetime import timedelta
from unittest.mock import patch

from lxml import html
from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.addons.training_management.tests.test_evaluation import EvaluationCase


class NativeEvaluationCase(EvaluationCase):
    def native_evaluation(self, scored=True, extra_required=False, **survey_values):
        row, grant = self.assigned_evaluation(scored=scored)
        action = row.evaluation_id.action_new_version()
        evaluation = self.env["training.evaluation"].with_user(self.coordinator).browse(action["res_id"])
        survey = (
            self.env["survey.survey"].with_user(self.coordinator).browse(evaluation.action_questionnaire()["res_id"])
        )
        question = (
            self.env["survey.question"]
            .with_user(self.coordinator)
            .create(
                {
                    "survey_id": survey.id,
                    "title": "Fictional pedagogical question",
                    "question_type": "simple_choice" if scored else "text_box",
                    "answer_score": 1 if scored else 0,
                    "suggested_answer_ids": [
                        Command.create({"value": "Expected response", "is_correct": True}),
                        Command.create({"value": "Other response"}),
                    ]
                    if scored
                    else [],
                }
            )
        )
        if extra_required:
            self.env["survey.question"].with_user(self.coordinator).create(
                {
                    "survey_id": survey.id,
                    "title": "Second required observation",
                    "question_type": "text_box",
                    "constr_mandatory": True,
                }
            )
        if survey_values:
            survey.write(survey_values)
        evaluation.action_publish()
        assignment = (
            self.env["training.evaluation.assignment"]
            .with_user(self.coordinator)
            .create(
                {
                    "evaluation_id": evaluation.id,
                    "enrollment_id": row.enrollment_id.id,
                    "opens_at": row.opens_at,
                    "due_at": row.due_at,
                }
            )
        )
        return assignment, grant, survey, question


@tagged("post_install", "-at_install")
class TestNativeEvaluation(NativeEvaluationCase):
    def test_native_completion_validation_and_mock_boundary(self):
        row, grant, survey, question = self.native_evaluation()
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        with self.assertRaises(ValidationError):
            self.decision(row)
        service._save_answers(row.id, {question.id: question.suggested_answer_ids[:1].ids}, submit=True)
        self.assertEqual(row.state, "submitted")
        self.assertFalse(row.result_available)
        attempt = self.env["survey.user_input"].search([("training_evaluation_assignment_id", "=", row.id)])
        self.assertEqual(attempt.scoring_percentage, 100)
        self.assertEqual(
            self.env["training.evaluation.service"].with_user(self.portal_b)._portal_values(row)["proposed_score"], 100
        )
        supervisor_values = self.env["training.evaluation.service"].with_user(self.supervisor)._portal_values(row)
        self.assertEqual(supervisor_values["review_answers"], [])
        with self.assertRaises(AccessError):
            self.env["training.exam.service"].with_user(self.portal)._attempt(attempt.id)
        self.decision(row, score=100)
        self.assertEqual(row.score, 100)
        with self.assertRaises(ValidationError):
            survey.write({"title": "Changed question set"})
        grant.write({"active": False})
        with self.assertRaises(AccessError):
            self.decision(row, score=90)

    def test_coordinator_cannot_bypass_evaluator_scope_through_native_answers(self):
        row, _grant, _survey, question = self.native_evaluation()
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        service._save_answers(row.id, {question.id: question.suggested_answer_ids[:1].ids}, submit=True)
        attempt = self.env["survey.user_input"].search([("training_evaluation_assignment_id", "=", row.id)])
        with self.assertRaises(AccessError):
            attempt.with_user(self.coordinator).read(["scoring_percentage"])
        with self.assertRaises(AccessError):
            attempt.user_input_line_ids.with_user(self.coordinator).read(["suggested_answer_id"])
        self.assertFalse(attempt.with_user(self.coordinator).search([("id", "=", attempt.id)]))
        self.assertFalse(
            attempt.user_input_line_ids.with_user(self.coordinator).search([("user_input_id", "=", attempt.id)])
        )
        # Authorized evaluators use the scoped projection, not native Survey ACLs.
        self.assertTrue(
            self.env["training.evaluation.service"].with_user(self.portal_b)._portal_values(row)["review_answers"]
        )

    def test_qualitative_text_and_new_attempt_preserve_native_answers(self):
        row, _grant, _survey, question = self.native_evaluation(scored=False)
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        service._save_answers(row.id, {question.id: "Fictional qualitative response"}, submit=True)
        first = self.env["survey.user_input"].search([("training_evaluation_assignment_id", "=", row.id)])
        self.assertEqual(first.user_input_line_ids.value_text_box, "Fictional qualitative response")
        self.decision(row)
        self.assertFalse(row.result_available)
        self.env["training.evaluation.service"].with_user(self.coordinator)._reopen(
            row.id,
            revision=row.revision,
            reason="Fictional second attempt",
            due_at=fields.Datetime.now() + timedelta(days=2),
        )
        service._start(row.id)
        self.assertEqual(row.attempt_number, 2)
        self.assertEqual(row.state, "in_progress")
        self.assertEqual(first.state, "done")
        self.assertEqual(first.user_input_line_ids.value_text_box, "Fictional qualitative response")
        action = row.evaluation_id.action_new_version()
        newer = self.env["training.evaluation"].browse(action["res_id"])
        self.assertNotEqual(newer.survey_id, first.survey_id)
        self.assertEqual(newer.survey_id.training_evaluation_id, newer)

    def test_deadline_revocation_and_forged_question(self):
        row, _grant, _survey, question = self.native_evaluation()
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        with self.assertRaises(ValidationError):
            service._save_answers(row.id, {question.id + 10000: [1]})
        with self.assertRaises(ValidationError):
            service._save_answers(row.id, {question.id: [999999]})
        row.enrollment_id.action_suspend_access(reason="Fictional revocation")
        with self.assertRaises(AccessError):
            service._save_answers(row.id, {question.id: []}, submit=True)

    def test_server_deadline_excludes_late_answers(self):
        row, _grant, _survey, question = self.native_evaluation()
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        attempt = self.env["survey.user_input"].search([("training_evaluation_assignment_id", "=", row.id)])
        with patch("odoo.fields.Datetime.now", return_value=attempt.deadline + timedelta(seconds=1)):
            service._save_answers(row.id, {question.id: question.suggested_answer_ids[:1].ids}, submit=True)
        self.assertEqual(attempt.state, "done")
        self.assertFalse(attempt.user_input_line_ids)
        self.assertEqual(row.state, "submitted")
        self.assertFalse(row.result_available)

    def test_portal_displays_effective_timed_deadline(self):
        row, _grant, _survey, _question = self.native_evaluation(is_time_limited=True, time_limit=5)
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        attempt = self.env["survey.user_input"].search([("training_evaluation_assignment_id", "=", row.id)])
        self.assertLess(attempt.deadline, row.due_at)
        self.assertEqual(service._portal_values(row)["due"], attempt.deadline)

    def test_archived_questionnaire_refuses_new_attempt_without_partial_state(self):
        row, _grant, survey, _question = self.native_evaluation()
        survey.write({"active": False})
        service = self.env["training.evaluation.service"].with_user(self.portal)
        with self.assertRaises(ValidationError):
            service._start(row.id)
        self.assertFalse(row.started_at)
        self.assertFalse(self.env["survey.user_input"].search([("training_evaluation_assignment_id", "=", row.id)]))


@tagged("post_install", "-at_install")
class TestEvaluationHTTP(NativeEvaluationCase, HttpCase):
    def test_http_answers_and_foreign_assignment_refused(self):
        row, _grant, _survey, question = self.native_evaluation()
        self.authenticate(self.portal.login, self.portal.login)
        url = "/my/training-evaluations/%s" % row.id
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        response = self.url_open(url, data={"csrf_token": token, "operation": "start", "attempt_number": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Fictional pedagogical question", response.text)
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "submit",
                "attempt_number": "1",
                "q_%s" % question.id: str(question.suggested_answer_ids[:1].id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Completed / Awaiting Validation", response.text)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        tree = html.fromstring(response.content)
        self.assertEqual(len(tree.xpath('//textarea[@name="conclusion" or @name="source" or @name="reason"]')), 3)
        self.assertTrue(tree.xpath('//form[contains(@action, "#evaluation-feedback")]'))
        row.delivery_id.write({"evaluation_instructor_ids": [Command.clear()]})
        self.assertEqual(self.url_open(url).status_code, 404)
        self.assertNotIn(row.name, self.url_open("/my/training-evaluations").text)

    def test_old_http_form_cannot_submit_reopened_attempt(self):
        row, _grant, _survey, question = self.native_evaluation()
        self.authenticate(self.portal.login, self.portal.login)
        url = "/my/training-evaluations/%s" % row.id
        response = self.url_open(url)
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        response = self.url_open(url, data={"csrf_token": token, "operation": "start", "attempt_number": "1"})
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._save_answers(row.id, {question.id: question.suggested_answer_ids[:1].ids}, submit=True)
        self.env["training.evaluation.service"].with_user(self.coordinator)._reopen(
            row.id, revision=row.revision, reason="Fictional retry", due_at=fields.Datetime.now() + timedelta(days=2)
        )
        service._start(row.id)
        self.env.flush_all()
        # A second browser tab still holds the first attempt's form.
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "submit",
                "attempt_number": "1",
                "q_%s" % question.id: str(question.suggested_answer_ids[:1].id),
            },
        )
        self.assertEqual(response.status_code, 200)
        row.invalidate_recordset()
        self.assertEqual(row.state, "in_progress")
        attempt = self.env["survey.user_input"].search(
            [("training_evaluation_assignment_id", "=", row.id), ("training_evaluation_number", "=", 2)]
        )
        self.assertFalse(attempt.user_input_line_ids)
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "submit",
                "attempt_number": "2",
                "q_%s" % question.id: str(question.suggested_answer_ids[:1].id),
            },
        )
        self.assertEqual(response.status_code, 200)
        row.invalidate_recordset()
        self.assertEqual(row.state, "submitted")
        attempt.invalidate_recordset()
        self.assertEqual(attempt.user_input_line_ids.suggested_answer_id, question.suggested_answer_ids[:1])

    def test_incomplete_submission_retains_draft_and_focuses_feedback(self):
        row, _grant, survey, question = self.native_evaluation(scored=False, extra_required=True)
        self.authenticate(self.portal.login, self.portal.login)
        url = "/my/training-evaluations/%s" % row.id
        response = self.url_open(url)
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        self.url_open(url, data={"csrf_token": token, "operation": "start", "attempt_number": "1"})
        draft = "Fictional draft <b>kept as text</b>"
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "submit",
                "attempt_number": "1",
                "q_%s" % question.id: draft,
            },
        )
        tree = html.fromstring(response.content)
        self.assertEqual(tree.xpath('//textarea[@name="q_%s"]' % question.id)[0].text, draft)
        self.assertFalse(tree.xpath("//textarea/b"))
        self.assertTrue(tree.xpath('//*[@id="evaluation-feedback"][@tabindex="-1"][@role="alert"]'))
        row.invalidate_recordset()
        self.assertEqual(row.state, "in_progress")
        attempt = self.env["survey.user_input"].search([("training_evaluation_assignment_id", "=", row.id)])
        self.assertFalse(attempt.user_input_line_ids)
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "save",
                "attempt_number": "1",
                "q_%s" % question.id: draft,
            },
        )
        self.assertTrue(html.fromstring(response.content).xpath('//*[@id="evaluation-feedback"][@role="status"]'))
        second = survey.question_ids - question
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "submit",
                "attempt_number": "1",
                "q_%s" % question.id: draft,
                "q_%s" % second.id: "Completed fictional observation",
            },
        )
        self.assertEqual(response.status_code, 200)
        row.invalidate_recordset()
        self.assertEqual(row.state, "submitted")
