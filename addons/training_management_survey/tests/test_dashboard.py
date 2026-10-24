"""S10 consumes frozen feedback aggregates and versioned mock-exam scores."""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_exam import ExamCase
from .test_feedback import FeedbackCase


@tagged("post_install", "-at_install")
class TestDashboardFeedback(FeedbackCase):
    def test_anonymous_two_hidden_three_visible_without_extra_control(self):
        for count in (2, 3):
            campaign, users, question = self.campaign(recipients=count)
            for user in users:
                self.submit(campaign, user, question)
            campaign.action_close()
            service = self.env["training.dashboard.service"].with_user(self.coordinator)
            data = service._dashboard(campaign.delivery_id.id)
            summary = data["campaigns"][0]
            if count == 2:
                self.assertIsNone(summary["snapshot"])
                self.assertIn("Insufficient", summary["summary"])
            else:
                self.assertEqual(summary["snapshot"]["received"], 3)
                self.assertEqual(summary["snapshot"]["rate"], 100)
            self.assertTrue(all(row["feedback"][0]["code"] == "anonymous" for row in data["rows"]))
            self.assertFalse(any(row["feedback_pending"] or row["overdue"] for row in data["rows"]))
            self.assertNotIn("user_input_line", str(data))
            self.assertNotIn("training_feedback_recipient_id", str(data))

    def test_named_received_and_overdue_are_not_inferred_for_anonymous(self):
        campaign, users, question = self.campaign(anonymous=False)
        self.submit(campaign, users[0], question)
        data = self.env["training.dashboard.service"].with_user(self.coordinator)._dashboard(campaign.delivery_id.id)
        states = [row["feedback"][0]["code"] for row in data["rows"]]
        self.assertEqual(states.count("received"), 1)
        self.assertEqual(len(data["rows"]), 3)

    def test_instructor_campaign_is_delivery_level_only(self):
        campaign, _users, _question = self.campaign(purpose="instructor", recipients=0, opened=False)
        campaign.delivery_id.write({"evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)]})
        self.opened(campaign.delivery_id)
        self.env["training.feedback.recipient"].with_user(self.coordinator).create(
            {"campaign_id": campaign.id, "user_id": self.portal_b.id, "role": "instructor"}
        )
        campaign.action_open()
        data = self.env["training.dashboard.service"].with_user(self.portal_b)._dashboard(campaign.delivery_id.id)
        self.assertEqual(len(data["campaigns"]), 1)
        self.assertEqual(data["rows"][0]["feedback"], [])


@tagged("post_install", "-at_install")
class TestDashboardExam(ExamCase):
    def test_first_last_best_per_version_without_raw_answers_or_certification(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        for correct in (False, True):
            attempt = service._start(enrollment.id, activity.id)
            if not correct:
                projected = (
                    self.env["training.dashboard.service"]
                    .with_user(self.coordinator)
                    ._participant(enrollment.id)["exams"][0]
                )
                self.assertIsNone(projected["first"])
                self.assertEqual(projected["ongoing"], 1)
            service._save(
                attempt.id,
                q1.id,
                q1.suggested_answer_ids[:1].ids if correct else q1.suggested_answer_ids[1:].ids,
                False,
            )
            service._save(
                attempt.id,
                q2.id,
                q2.suggested_answer_ids[:2].ids if correct else q2.suggested_answer_ids[2:].ids,
                False,
            )
            service._submit(attempt.id)
        dashboard = self.env["training.dashboard.service"].with_user(self.coordinator)
        data = dashboard._dashboard(enrollment.delivery_id.id)
        result = data["rows"][0]["exams"][0]
        self.assertEqual((result["count"], result["first"], result["last"], result["best"]), (2, 0, 100, 100))
        self.assertNotIn("PRIVATE FINAL EXPLANATION", str(data))
        self.assertFalse(any(metric["name"] == exam.title for metric in data["metrics"]))
        enrollment.delivery_id.write({"evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)]})
        self.assertEqual(dashboard.with_user(self.portal_b)._participant(enrollment.id)["exams"][0]["count"], 2)
        with self.assertRaises(AccessError):
            self.env["survey.user_input"].with_user(self.portal_b).search(
                [("training_enrollment_id", "=", enrollment.id)]
            )
