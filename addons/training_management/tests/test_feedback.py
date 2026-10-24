"""Feedback administration also works before optional Surveys is installed."""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .test_closure import ClosureCase


@tagged("post_install", "-at_install")
class TestFeedbackAdministration(ClosureCase):
    def test_nominative_draft_population_states(self):
        enrollment = self.opened()
        definition = (
            self.env["training.feedback"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional nominative draft",
                    "program_id": enrollment.delivery_id.program_id.id,
                    "purpose": "immediate",
                    "anonymous": False,
                    "criteria": "Fictional draft completion criteria",
                }
            )
        )
        campaign = (
            self.env["training.feedback.campaign"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional draft population",
                    "feedback_id": definition.id,
                    "delivery_id": enrollment.delivery_id.id,
                    "retention_id": self.retention.id,
                    "population": "Confirmed fictional participants",
                    "due_at": fields.Datetime.now() + timedelta(days=7),
                }
            )
        )
        recipient = (
            self.env["training.feedback.recipient"]
            .with_user(self.coordinator)
            .create(
                {
                    "campaign_id": campaign.id,
                    "user_id": enrollment.user_id.id,
                    "enrollment_id": enrollment.id,
                    "role": "participant",
                }
            )
        )
        self.assertEqual(recipient.read(["response_state"])[0]["response_state"], "not_invited")
        recipient.write({"active": False, "exclusion_reason": "Fictional withdrawal"})
        self.assertEqual(recipient.read(["response_state"])[0]["response_state"], "not_applicable")
