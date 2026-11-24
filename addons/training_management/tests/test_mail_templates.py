"""Training emails come from native, editable and translatable mail templates."""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_attendance import AttendanceCase

TEMPLATES = {
    "training_management.mail_template_training_notification": "training.notification",
    "training_management.mail_template_learning_notice": "training.learning.notice",
    "training_management.mail_template_practice_notice": "training.practice.notice",
    "training_management.mail_template_tutoring_notice": "training.tutoring.notice",
    "training_management.mail_template_feedback_notice": "training.feedback.notice",
    "training_management.mail_template_publication_notice": "training.publication.notice",
    "training_management.mail_template_operator_notice": "training.operator.notice",
    "training_management.mail_template_date_alert_confirmation": "training.session.alert.subscription",
    "training_management.mail_template_date_alert_notice": "training.session.alert.notice",
    "training_management.mail_template_session_invitation": "training.invitation",
}


@tagged("post_install", "-at_install")
class TestMailTemplates(AttendanceCase):
    def setUp(self):
        super().setUp()
        self.portal.partner_id.email = "participant@example.invalid"

    def lifecycle_mail(self):
        enrollment = self.opened(self.delivery())
        journal = self.env["training.notification"].search([("enrollment_id", "=", enrollment.id)], limit=1)
        self.assertTrue(journal.mail_id)
        return journal

    def test_every_training_email_has_a_native_template(self):
        for xmlid, model in TEMPLATES.items():
            template = self.env.ref(xmlid)
            self.assertEqual(template.model, model, xmlid)
            self.assertFalse(template.email_to or template.partner_to or template.email_cc, xmlid)
            self.assertFalse(template.attachment_ids or template.report_template_ids, xmlid)

    def test_template_text_is_used_and_checked_at_transport(self):
        # Written in the participant's language, as an organization edits its template.
        self.env.ref("training_management.mail_template_training_notification").with_context(
            lang=self.portal.lang or "en_US"
        ).write({"subject": "Fictional organization: your training space"})
        journal = self.lifecycle_mail()
        mail = journal.mail_id
        self.assertEqual(mail.subject, "Fictional organization: your training space")
        self.assertIn("/my/home", mail.body_html)
        self.assertTrue(mail._prepare_outgoing_list())
        mail.sudo().body_html = mail.body_html + "<p>Private detail</p>"
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()

    def test_french_recipient_receives_the_french_text(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(["training_management"], ["fr_FR"], overwrite=True)
        self.portal.lang = "fr_FR"
        mail = self.lifecycle_mail().mail_id
        self.assertEqual(mail.subject, "Votre espace de formation a été mis à jour")
        self.assertIn("Bonjour,", mail.body_html)
        self.assertTrue(mail._prepare_outgoing_list())
