"""A mock exam earns points once, whatever the score and the retakes."""

from odoo.tests import tagged

from odoo.addons.training_management_survey.tests.test_exam import ExamCase


@tagged("post_install", "-at_install")
class TestMockExamPoints(ExamCase):
    def test_completed_exam_earns_once_whatever_the_score(self):
        admin = self.env.ref("base.user_admin")
        rule = (
            self.env["training.gamification.rule"]
            .with_user(admin)
            .create(
                {
                    "name": "Fictional mock exam",
                    "event_type": "mock_exam_completed",
                    "points": 10,
                    "date_from": "2020-01-01",
                    "active": True,
                }
            )
        )
        exam, q1, q2, activity, enrollment, service = self.published()
        reconcile = self.env["training.gamification.service"].with_user(admin)._reconcile
        attempt = service._start(enrollment.id, activity.id)
        reconcile()
        self.assertFalse(rule.point_ids, "An unfinished attempt earns nothing.")
        service._save(attempt.id, q2.id, [], False)
        service._submit(attempt.id)
        self.assertEqual(attempt.scoring_total, 0)
        for _ in range(2):
            reconcile()
            retake = service._start(enrollment.id, activity.id)
            service._submit(retake.id)
        reconcile()
        self.assertEqual(rule.point_ids.mapped("points"), [10])
        self.assertEqual(rule.point_ids.user_id, self.portal)
