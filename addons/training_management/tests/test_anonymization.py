from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .test_attendance import AttendanceCase


@tagged("post_install", "-at_install")
class TestAnonymization(AttendanceCase):
    """Conservation configurée (22 November 2026): the module provides the anonymization,
    without default deadline; the evidence stays, its personal copies are cleared."""

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref("base.user_admin")
        self.company.write(
            {
                "training_notification_template_id": self.env["mail.template"]
                .create(
                    {
                        "name": "Fictional notification identity",
                        "model_id": self.env["ir.model"]._get_id("res.company"),
                        "email_from": "{{ object.name }} <contact@example.invalid>",
                    }
                )
                .id,
                "training_notification_manager_id": self.coordinator.id,
            }
        )
        self.coordinator.partner_id.email = "manager@example.invalid"
        self.portal.partner_id.email = "participant@example.invalid"

    def test_anonymized_dossier_keeps_evidence_without_personal_copies(self):
        enrollment = self.opened(self.delivery())
        journals = self.env["training.notification"].search([("enrollment_id", "=", enrollment.id)])
        self.assertIn("participant@example.invalid", journals.mapped("email"))
        mails = journals.mail_id
        self.assertTrue(mails)
        with self.assertRaises(AccessError):
            enrollment.with_user(self.coordinator).action_training_anonymize_dossier()
        with self.assertRaisesRegex(ValidationError, "finished or cancelled"):
            enrollment.with_user(self.admin).action_training_anonymize_dossier()
        enrollment.action_cancel(reason="Fictional cancellation")
        enrollment.with_user(self.admin).action_training_anonymize_dossier()
        self.assertTrue(enrollment.anonymized_at)
        self.assertTrue(journals.exists() == journals and enrollment.exists())
        self.assertFalse(any(journals.mapped("email")))
        self.assertFalse(mails.exists())
        self.assertFalse(journals.mail_id)

    def test_participant_with_a_user_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "Delete the user"):
            self.portal.partner_id.with_user(self.admin).action_training_anonymize_participant()
        with self.assertRaises(AccessError):
            self.portal.partner_id.with_user(self.coordinator).action_training_anonymize_participant()

    def test_participant_without_user_is_anonymized(self):
        partner = self.env["res.partner"].create(
            {"name": "Fictional Visitor", "email": "visitor@example.invalid", "phone": "+212 600 000 000"}
        )
        subscription = (
            self.env["training.session.alert.subscription"]
            .sudo()
            ._create_evidence(
                {
                    "course_id": self.course.id,
                    "company_id": self.company.id,
                    "public_title": "Fictional public title",
                    "subscribed_at": fields.Datetime.now(),
                    "consent_wording": "Fictional consent",
                    "email": "visitor@example.invalid",
                }
            )
        )
        partner.with_user(self.admin).action_training_anonymize_participant()
        self.assertFalse(partner.active)
        self.assertFalse(partner.email or partner.phone)
        self.assertNotIn("Fictional Visitor", partner.name)
        # The consent stays as evidence, without the address.
        self.assertTrue(subscription.exists())
        self.assertEqual(subscription.email, "anonymized-%s@anonymized.invalid" % subscription.id)
