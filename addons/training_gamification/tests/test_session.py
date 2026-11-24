"""Session challenges, coordination follow-up and the client's collective indicator."""

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged

from .test_gamification import GamificationCase


@tagged("post_install", "-at_install")
class TestSessionEngagement(GamificationCase, HttpCase):
    def template(self, **values):
        definition = self.env["gamification.goal.definition"].create(
            {
                "name": "Fictional training points",
                "computation_mode": "count",
                "model_id": self.env["ir.model"]._get_id("training.gamification.point"),
                "field_date_id": self.env["ir.model.fields"]._get("training.gamification.point", "date").id,
                "domain": "[('user_id', '=', user.id), ('kind', '=', 'grant'), ('withdrawn', '=', False)]",
            }
        )
        return self.env["gamification.challenge"].create(
            {
                "name": "Fictional session challenge",
                "training_template": True,
                "user_domain": False,
                "line_ids": [(0, 0, {"definition_id": definition.id, "target_goal": 1})],
                **values,
            }
        )

    def test_coordinator_launches_a_personal_challenge_for_participants(self):
        delivery, _session, enrollment = self.scheduled()
        template = self.template()
        challenge = delivery.with_user(self.coordinator)._launch_training_challenge(template)
        self.assertEqual(challenge.user_ids, self.portal)
        self.assertEqual(challenge.training_delivery_id, delivery)
        self.assertEqual((challenge.state, challenge.visibility_mode), ("inprogress", "personal"))
        self.assertEqual(challenge.start_date, delivery.start_at.date())
        self.assertEqual(template.state, "draft", "The template is never started itself.")
        self.assertEqual(delivery.training_challenge_count, 1)

        with self.assertRaises(ValidationError):
            delivery.with_user(self.coordinator)._launch_training_challenge(challenge)
        with self.assertRaises(ValidationError):
            self.template(visibility_mode="ranking")
        with self.assertRaises(AccessError):
            delivery.with_user(self.portal)._launch_training_challenge(template)

        action = delivery.with_user(self.coordinator).action_open_training_engagement()
        self.assertEqual(action["domain"], [("delivery_id", "=", delivery.id)])
        self.rule()
        self.review(self.declare(*self.session_and(enrollment)))
        self.reconcile()
        rows = self.env["training.gamification.point"].with_user(self.coordinator).search(action["domain"])
        self.assertEqual(rows.enrollment_id, enrollment)

    def session_and(self, enrollment):
        return enrollment.delivery_id.session_ids[:1], enrollment

    def test_client_sees_a_collective_figure_from_three_participants(self):
        delivery, _session, _own = self.scheduled()
        lot = self.lot(delivery, quantity=5)
        # Without the sales integration, simulate the confirmed commercial line.
        source = patch.object(type(lot), "_check_source", lambda allocation: None)
        source.start()
        self.addCleanup(source.stop)
        lot.action_confirm(reason="Fictional order")
        grant = (
            self.env["training.company.authorization"]
            .with_user(self.coordinator)
            .create(
                {
                    "company_id": self.company.id,
                    "customer_id": lot.customer_id.commercial_partner_id.id,
                    "user_id": self.portal.id,
                    "allocation_ids": [Command.set(lot.ids)],
                }
            )
        )
        grant.action_confirm()
        service = self.env["training.gamification.service"].with_user(self.portal)

        def add(partner, user=False):
            enrollment = self.enrollment(
                delivery, allocation_id=lot.id, free_reason=False, participant_id=partner.id, user_id=user
            )
            enrollment.action_validate_prerequisites(reason="Fictional review")
            enrollment.action_confirm()
            return enrollment

        first = add(self.portal_b.partner_id, self.portal_b.id)
        add(self.env["res.partner"].create({"name": "Fictional second participant"}))
        self.assertFalse(service._client_indicator(lot.id), "Two participants: no figure at all.")
        add(self.env["res.partner"].create({"name": "Fictional third participant"}))
        self.assertEqual(service._client_indicator(lot.id), {"participants": 3, "active": 0, "challenges": False})

        rule = self.rule()
        self.Point.create(
            {
                "rule_id": rule.id,
                "enrollment_id": first.id,
                "user_id": self.portal_b.id,
                "kind": "grant",
                "points": 5,
                "date": "2027-01-04 10:00:00",
                "source_key": "fictional,1",
            }
        )
        self.assertEqual(service._client_indicator(lot.id)["active"], 33)
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open(f"/my/company-trainings/{lot.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="company-engagement"', page.text)
        self.assertIn("33 %", page.text)
        self.assertNotIn(self.portal_b.name, page.text.split('id="company-engagement"')[1].split("</section>")[0])

        with self.assertRaises(AccessError):
            self.env["training.gamification.service"].with_user(self.portal_b)._client_indicator(lot.id)
