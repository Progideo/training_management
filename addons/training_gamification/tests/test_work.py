"""Work submitted then validated: two events, the deposit kept when changes are asked."""

from odoo.tests import tagged

from odoo.addons.training_management.tests.test_learning import PDF, LearningCase


@tagged("post_install", "-at_install")
class TestWorkPoints(LearningCase):
    def test_submission_then_validation(self):
        admin = self.env.ref("base.user_admin")
        Rule = self.env["training.gamification.rule"].with_user(admin)
        for event, points in (("activity_submitted", 5), ("activity_validated", 10)):
            Rule.create(
                {"name": event, "event_type": event, "points": points, "date_from": "2020-01-01", "active": True}
            )
        reconcile = self.env["training.gamification.service"].with_user(admin)._reconcile
        Point = self.env["training.gamification.point"].sudo()
        _delivery, activity, enrollment = self.setup_learning()
        entry = self.post(enrollment, activity_id=activity.id, data=PDF, filename="work.pdf")
        progress = self.service()._progress(enrollment, activity)
        reconcile()
        self.assertEqual(Point.search([]).mapped("points"), [5])

        self.post(
            enrollment,
            "correction",
            activity_id=activity.id,
            parent_id=entry.id,
            revision=progress.revision,
            decision="changes",
        )
        self.assertEqual(progress.state, "changes")
        reconcile()
        self.assertEqual(Point.search([]).mapped("points"), [5], "Asking for changes keeps the deposit.")

        newer = self.post(enrollment, activity_id=activity.id, parent_id=entry.id, revision=progress.revision)
        self.post(
            enrollment,
            "correction",
            activity_id=activity.id,
            parent_id=newer.id,
            revision=progress.revision,
            decision="accepted",
        )
        self.assertEqual(progress.state, "validated")
        reconcile()
        self.assertEqual(sorted(Point.search([]).mapped("points")), [5, 10])
