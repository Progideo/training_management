"""Commercial requests alert only the configured authorized internal manager."""

from email.utils import parseaddr

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from odoo.addons.training_management.tests.test_enrollment import EnrollmentCase


@tagged("post_install", "-at_install")
class TestRequestAlerts(EnrollmentCase):
    def test_acknowledgement_manager_alert_and_revoked_request(self):
        self.env.ref("sales_team.group_sale_salesman_all_leads").write(
            {"user_ids": [Command.link(self.coordinator.id)]}
        )
        self.coordinator.partner_id.email = "manager@example.invalid"
        self.company.write(
            {
                "training_notification_address": "contact@example.invalid",
                "training_notification_manager_id": self.coordinator.id,
            }
        )
        lead = self.env["crm.lead"].create(
            {
                "name": "PRIVATE-REQUEST",
                "company_id": self.company.id,
                "training_request_kind": "group",
                "email_from": "requester@example.invalid",
            }
        )
        ack = self.env["training.request.notice"].search([("lead_id", "=", lead.id)])
        alert = self.env["training.operator.notice"].search(
            [("source_model", "=", "crm.lead"), ("source_id", "=", lead.id)]
        )
        self.assertEqual(len(ack), 1)
        self.assertEqual(len(alert), 1)
        for mail in ack.mail_id | alert.mail_id:
            self.assertEqual(parseaddr(mail.email_from), (self.company.name, "contact@example.invalid"))
            self.assertEqual(mail.reply_to, "contact@example.invalid")
            self.assertNotIn("PRIVATE-REQUEST", mail.body_html)
            self.assertFalse(mail.email_cc or mail.recipient_ids or mail.recipient_cc_ids or mail.attachment_ids)
            self.assertTrue(mail._prepare_outgoing_list())
        self.assertEqual(alert.recipient_id, self.coordinator)
        self.assertEqual(self.env["training.operator.notice"]._queue(lead, "request"), alert)
        with self.assertRaises(AccessError):
            alert.with_user(self.portal).read(["source_id"])
        lead.active = False
        for mail in ack.mail_id | alert.mail_id:
            with self.assertRaises(ValidationError):
                mail._prepare_outgoing_list()

    def test_manager_needs_actual_crm_read_rights(self):
        self.coordinator.partner_id.email = "manager@example.invalid"
        self.company.write(
            {
                "training_notification_address": "contact@example.invalid",
                "training_notification_manager_id": self.coordinator.id,
            }
        )
        lead = self.env["crm.lead"].create(
            {
                "name": "Private CRM request",
                "company_id": self.company.id,
                "training_request_kind": "group",
                "email_from": "requester@example.invalid",
            }
        )
        alert = self.env["training.operator.notice"].search(
            [("source_model", "=", "crm.lead"), ("source_id", "=", lead.id)]
        )
        self.assertEqual(len(alert), 1)
        self.assertFalse(alert.mail_id)
        self.assertTrue(alert.failure)
