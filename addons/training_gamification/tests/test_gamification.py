"""Points from training evidence: opt-in rules, idempotence, withdrawal, deletion, rights."""

from datetime import datetime
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from odoo.addons.training_management.tests.test_attendance import AttendanceCase


class GamificationCase(AttendanceCase):
    def setUp(self):
        super().setUp()
        self.admin = self.env.ref("base.user_admin")
        self.Rule = self.env["training.gamification.rule"].with_user(self.admin)
        self.Point = self.env["training.gamification.point"].sudo()

    def rule(self, **values):
        return self.Rule.create(
            {
                "name": "Fictional attendance",
                "event_type": "attendance",
                "points": 5,
                "date_from": "2027-01-01",
                "active": True,
                **values,
            }
        )

    def reconcile(self):
        self.env["training.gamification.service"].with_user(self.admin)._reconcile()
        self.portal.invalidate_recordset(["karma"])

    def invalidate(self, presence):
        return self.service(self.portal_b)._invalidate(
            presence.session_id.id,
            presence.enrollment_id.id,
            reason="Fictional wrong interval",
            revision=presence.revision,
            definition=self.service()._definition(presence.session_id),
        )

    def validated_presence(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.review(presence)
        self.assertEqual(presence.state, "validated")
        return presence


@tagged("post_install", "-at_install")
class TestTrainingGamification(GamificationCase):
    def test_nothing_is_granted_without_an_active_rule(self):
        self.validated_presence()
        self.rule(active=False)
        self.reconcile()
        self.assertFalse(self.Point.search([]))
        self.assertEqual(self.portal.karma, 0)

    def test_grant_is_idempotent_and_withdrawn_when_evidence_is_invalidated(self):
        rule = self.rule()
        presence = self.validated_presence()
        self.reconcile()
        grant = self.Point.search([("rule_id", "=", rule.id)])
        self.assertEqual((grant.kind, grant.points, grant.user_id), ("grant", 5, self.portal))
        self.assertEqual(self.portal.karma, 5)
        tracking = (
            self.env["gamification.karma.tracking"].sudo().search([("origin_ref", "=", f"{grant._name},{grant.id}")])
        )
        self.assertEqual(tracking.reason, "Fictional attendance")

        self.reconcile()
        self.assertEqual(len(self.Point.search([])), 1)
        self.assertEqual(self.portal.karma, 5)

        self.invalidate(presence)
        self.reconcile()
        withdrawal = self.Point.search([("kind", "=", "withdrawal")])
        self.assertEqual((withdrawal.points, withdrawal.grant_id), (-5, grant))
        self.assertTrue(grant.withdrawn)
        self.assertEqual(self.portal.karma, 0)

    def test_events_before_the_rule_start_or_without_account_earn_nothing(self):
        self.rule(date_from="2027-02-01")
        presence = self.validated_presence()
        self.reconcile()
        self.assertFalse(self.Point.search([]))

        service = self.env["training.gamification.service"]
        self.assertEqual(service._participant_user(presence.enrollment_id), self.portal)
        stranger = self.env["res.partner"].create({"name": "Fictional participant without account"})
        without_account = self.enrollment(self.delivery(), participant_id=stranger.id, user_id=False)
        self.assertFalse(service._participant_user(without_account))

    def test_limit_per_enrollment(self):
        self.rule(max_per_enrollment=1)
        delivery, session, enrollment = self.scheduled()
        self.review(self.declare(session, enrollment))
        second = (
            self.env["training.session"]
            .with_user(self.coordinator)
            ._create_scheduled(
                [
                    {
                        "name": "Fictional second session",
                        "delivery_id": delivery.id,
                        "instructor_id": self.portal_b.partner_id.id,
                        "mode": "remote",
                        "meeting_url": "https://example.invalid/room",
                        "start_date": "2027-01-04",
                        "end_date": "2027-01-04",
                        "start_hour": 13,
                        "end_hour": 15,
                        "attendance_mode": "mixed",
                    }
                ],
                reason="Fictional added session",
                conflict_reason="Fictional overlapping fixture",
            )
        )
        with patch("odoo.fields.Datetime.now", return_value=second.end_at):
            self.review(self.declare(second, enrollment))
        self.reconcile()
        self.assertEqual(len(self.Point.search([])), 1)

    def test_deleting_the_dossier_deletes_points_and_their_karma(self):
        rule = self.rule()
        presence = self.validated_presence()
        self.reconcile()
        grant = self.Point.search([("rule_id", "=", rule.id)])
        self.assertEqual(self.portal.karma, 5)
        enrollment = presence.enrollment_id
        enrollment.action_cancel(reason="Fictional cancellation")
        enrollment.with_user(self.admin).action_training_delete_dossier()
        self.assertFalse(grant.exists())
        self.portal.invalidate_recordset(["karma"])
        self.assertEqual(self.portal.karma, 0)
        self.assertFalse(
            self.env["gamification.karma.tracking"].sudo().search([("origin_ref", "=", f"{grant._name},{grant.id}")])
        )
        # The rule keeps no trace of the deleted dossier and can be deleted again.
        rule.unlink()

    def test_only_administrators_configure_and_points_are_server_written(self):
        with self.assertRaises(AccessError):
            self.env["training.gamification.rule"].with_user(self.coordinator).create(
                {"name": "Forbidden", "event_type": "attendance", "points": 1}
            )
        with self.assertRaises(AccessError):
            self.env["training.gamification.service"].with_user(self.coordinator)._reconcile()
        with self.assertRaises(AccessError):
            self.env["training.gamification.point"].with_user(self.admin).create({})
        # A participant reads only their own points.

        rule = self.rule()
        self.validated_presence()
        self.reconcile()
        Point = self.env["training.gamification.point"]
        self.assertEqual(Point.with_user(self.portal).search([]).user_id, self.portal)
        self.assertFalse(Point.with_user(self.portal_b).search([]))
        with self.assertRaises(ValidationError):
            rule.write({"event_type": "enrollment_closed"})
        with self.assertRaises(ValidationError):
            rule.write({"course_ids": [(6, 0, [])]})
        with self.assertRaises(ValidationError):
            rule.unlink()
        rule.write({"points": 8, "active": False})

    def test_event_types_cover_the_training_flows(self):
        keys = set(dict(self.env["training.gamification.service"]._event_selection()))
        self.assertTrue(
            {
                "attendance",
                "activity_completed",
                "activity_submitted",
                "activity_validated",
                "practice_done",
                "feedback_received",
                "tutoring_attended",
                "enrollment_closed",
            }
            <= keys
        )
        # Every candidate reader runs on an empty and a real enrollment set.
        enrollment = self.validated_presence().enrollment_id
        service = self.env["training.gamification.service"]
        for _label, method in service._event_types().values():
            list(method(self.env["training.enrollment"]))
            list(method(enrollment))

    def test_completed_training_and_company_isolation(self):
        other = self.env["res.company"].create({"name": "Fictional other company"})
        self.admin.company_ids |= other
        self.rule(event_type="enrollment_closed", name="Fictional other company", company_id=other.id)
        self.rule(event_type="enrollment_closed", name="Fictional completion", points=10)
        enrollment = self.validated_presence().enrollment_id
        self.reconcile()
        self.assertFalse(self.Point.search([]))
        with patch("odoo.fields.Datetime.now", return_value=datetime(2027, 2, 2)):
            enrollment.action_close(reason="Fictional completion")
            self.reconcile()
        self.assertEqual(enrollment.state, "closed")
        grant = self.Point.search([])
        self.assertEqual((grant.rule_id.name, grant.points), ("Fictional completion", 10))
        self.assertEqual(self.portal.karma, 10)

    def test_native_challenge_counts_the_journal(self):
        self.rule()
        self.validated_presence()
        self.reconcile()
        badge = self.env["gamification.badge"].create({"name": "Fictional assiduous"})
        definition = self.env["gamification.goal.definition"].create(
            {
                "name": "Fictional attendance points",
                "computation_mode": "count",
                "model_id": self.env["ir.model"]._get_id("training.gamification.point"),
                "domain": "[('user_id', '=', user.id), ('kind', '=', 'grant'), ('withdrawn', '=', False)]",
            }
        )
        challenge = self.env["gamification.challenge"].create(
            {
                "name": "Fictional session challenge",
                "user_domain": False,
                "user_ids": [(6, 0, self.portal.ids)],
                "reward_id": badge.id,
                "reward_realtime": True,
                "line_ids": [(0, 0, {"definition_id": definition.id, "target_goal": 1})],
            }
        )
        challenge.action_start()
        challenge._generate_goals_from_challenge()
        goal = self.env["gamification.goal"].search(
            [("challenge_id", "=", challenge.id), ("user_id", "=", self.portal.id)]
        )
        goal.update_goal()
        self.assertEqual((goal.current, goal.state), (1, "reached"))
