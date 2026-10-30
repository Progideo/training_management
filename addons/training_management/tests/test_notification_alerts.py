"""C06: configured identities and alerts never widen the recipient's grants."""

from datetime import timedelta
from email.utils import parseaddr
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .test_attendance import AttendanceCase
from .test_quality import QualityCase


@tagged("post_install", "-at_install")
class TestNotificationAlerts(AttendanceCase):
    def setUp(self):
        super().setUp()
        self.company.write(
            {
                "training_notification_template_id": self.env["mail.template"]
                .create(
                    {
                        "name": "Fictional notification identity",
                        "model_id": self.env["ir.model"]._get_id("res.company"),
                        "email_from": "{{ object.name }} <contact@example.invalid>",
                        "reply_to": "contact@example.invalid",
                    }
                )
                .id,
                "training_notification_manager_id": self.coordinator.id,
            }
        )
        self.coordinator.partner_id.email = "manager@example.invalid"
        self.portal.partner_id.email = "participant@example.invalid"
        self.portal_b.partner_id.email = "trainer@example.invalid"

    def assert_identity(self, mails):
        self.assertTrue(mails)
        for mail in mails:
            self.assertEqual(parseaddr(mail.email_from), (self.company.name, "contact@example.invalid"))
            self.assertEqual(mail.reply_to, "contact@example.invalid")
            self.assertFalse(mail.email_cc or mail.recipient_ids or mail.recipient_cc_ids or mail.attachment_ids)
            self.assertTrue(mail._prepare_outgoing_list())

    def test_access_open_extend_suspend_revoke_and_replay(self):
        delivery = self.delivery()
        enrollment = self.opened(delivery)
        journal = self.env["training.notification"]
        access = journal.search([("enrollment_id", "=", enrollment.id), ("kind", "=", "access")])
        self.assertEqual(len(access), 1)
        enrollment.action_open_access(reason="Replay")
        self.assertEqual(journal.search([("enrollment_id", "=", enrollment.id), ("kind", "=", "access")]), access)
        enrollment.action_extend_access(enrollment.access_end + timedelta(days=2), reason="Fictional extension")
        enrollment.action_suspend_access(reason="Fictional suspension")
        enrollment.action_revoke_access(reason="Fictional revocation")
        access = journal.search([("enrollment_id", "=", enrollment.id), ("kind", "=", "access")])
        self.assertEqual(len(access), 4)
        self.assert_identity(access.mail_id)
        enrollment.action_cancel(reason="Fictional cancellation")
        change = journal.search([("enrollment_id", "=", enrollment.id), ("kind", "=", "change")])
        self.assertEqual(len(change), 1)
        self.assert_identity(change.mail_id)
        with self.assertRaises(AccessError):
            enrollment.with_user(self.portal).action_open_access(reason="Forbidden")

    def test_invitations_and_private_learning_use_configured_identity(self):
        delivery, session, enrollment = self.scheduled()
        inv = self.env["training.invitation"].with_user(self.coordinator)
        recipients = self.portal.partner_id | self.portal_b.partner_id
        self.assertEqual(inv._queue(delivery, recipients), 2)
        self.assert_identity(delivery.invitation_ids.mail_id)
        delivery.learning_tutor_id = self.portal_b
        entry = (
            self.env["training.learning.service"]
            .with_user(self.portal)
            ._post(
                enrollment.id, "question", request_key="12345678-1234-4234-8234-123456789abc", body="PRIVATE-CONTENT"
            )
        )
        notice = self.env["training.learning.notice"].search([("entry_id", "=", entry.id)])
        self.assert_identity(notice.mail_id)
        self.assertNotIn("PRIVATE-CONTENT", notice.mail_id.body_html)
        notice.mail_id.write({"state": "exception"})
        self.assertFalse(
            self.env["training.operator.notice"].search([]), "Private learning failures must stay with the tutor"
        )
        self.assertEqual(notice.mail_id.email_to, self.portal_b.partner_id.email)

    def test_attendance_alert_replay_and_assignment_change(self):
        delivery, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        alerts = self.env["training.operator.notice"]
        first = alerts.search([("source_model", "=", "training.attendance.event"), ("role", "=", "trainer")])
        self.assertEqual(len(first), 1)
        self.assert_identity(first.mail_id)
        self.assertEqual(first.recipient_id, self.portal_b)
        self.assertEqual(self.declare(session, enrollment), presence)
        self.assertEqual(alerts.search([("role", "=", "trainer")]), first)
        self.assertEqual(alerts._queue(presence.event_ids[-1], "review", "trainer"), first)
        with self.assertRaises(ValidationError):
            session._apply_schedule({"instructor_id": self.portal.partner_id.id}, "Fictional reassignment")
        self.portal_b.active = False
        with self.assertRaises(ValidationError):
            first.mail_id._prepare_outgoing_list()
        with self.assertRaises(AccessError):
            first.with_user(self.portal_b).read(["email"])
        self.assertFalse(delivery.state == "closed")

    def test_invalidation_manager_alert_and_redeclaration(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.review(presence)
        self.service(self.coordinator)._invalidate(
            session.id,
            enrollment.id,
            reason="Fictional invalidation",
            revision=presence.revision,
            definition=self.service()._definition(session),
        )
        alert = self.env["training.operator.notice"].search([("role", "=", "manager")])
        self.assertEqual(len(alert), 1)
        self.assert_identity(alert.mail_id)
        self.declare(session, enrollment)
        newest = self.env["training.operator.notice"].search([("role", "=", "trainer")], order="id desc", limit=1)
        self.assert_identity(newest.mail_id)
        with self.assertRaises(ValidationError):
            alert.mail_id._prepare_outgoing_list()

    def test_review_removes_stale_pending_alert(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        notice = self.env["training.operator.notice"].search([("role", "=", "trainer")])
        self.review(presence)
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()

    def test_failure_alert_manager_revocation_and_no_recursive_alert(self):
        delivery = self.delivery()
        enrollment = self.opened(delivery)
        notice = self.env["training.notification"].search([("enrollment_id", "=", enrollment.id)], limit=1)
        notice.mail_id.write({"state": "exception"})
        alert = self.env["training.operator.notice"].search([("source_model", "=", notice._name)])
        self.assertEqual(len(alert), 1)
        self.assert_identity(alert.mail_id)
        self.assertEqual(alert.recipient_id, self.coordinator)
        notice.mail_id.write({"state": "exception"})
        self.assertEqual(self.env["training.operator.notice"].search([("source_model", "=", notice._name)]), alert)
        alert.mail_id.write({"state": "exception"})
        self.assertEqual(len(self.env["training.operator.notice"].search([])), 1)
        self.company.training_alert_address = "central@example.invalid"
        with self.assertRaises(ValidationError):
            alert.mail_id._prepare_outgoing_list()
        self.company.training_notification_manager_id = False
        with self.assertRaises(ValidationError):
            alert.mail_id._prepare_outgoing_list()

    def test_configuration_rights_cross_company_and_stale_identity(self):
        with self.assertRaises(AccessError):
            self.company.with_user(self.coordinator).write({"training_notification_template_id": False})
        with self.assertRaises(ValidationError):
            self.company.write({"training_notification_manager_id": self.portal.id})
        with self.assertRaises(ValidationError):
            self.company.write({"training_alert_address": "a@example.invalid,b@example.invalid"})
        enrollment = self.opened(self.delivery())
        notice = self.env["training.notification"].search([("enrollment_id", "=", enrollment.id)], limit=1)
        before = (notice.mail_id.email_from, notice.mail_id.reply_to)
        self.company.training_notification_template_id.write({"email_from": "changed@example.invalid"})
        self.assertTrue(notice.mail_id._prepare_outgoing_list())
        self.assertEqual((notice.mail_id.email_from, notice.mail_id.reply_to), before)
        self.assertFalse(self.other_company.training_notification_template_id)

    def test_native_template_cannot_add_recipients_or_private_attachments(self):
        template = self.company.training_notification_template_id
        attachment = self.env["ir.attachment"].create({"name": "Fictional unwanted", "raw": b"private"})
        template.write(
            {
                "email_to": "unwanted@example.invalid",
                "email_cc": "unwanted@example.invalid",
                "attachment_ids": [(6, 0, attachment.ids)],
                "body_html": "UNWANTED TEMPLATE CONTENT",
                "reply_to": "reply@example.invalid",
            }
        )
        enrollment = self.opened(self.delivery())
        notice = self.env["training.notification"].search([("enrollment_id", "=", enrollment.id)], limit=1)
        self.assertEqual(notice.mail_id.email_to, self.portal.partner_id.email)
        self.assertEqual(notice.mail_id.reply_to, "reply@example.invalid")
        self.assertFalse(notice.mail_id.email_cc or notice.mail_id.attachment_ids)
        self.assertNotIn("UNWANTED", notice.mail_id.body_html)
        self.assertTrue(notice.mail_id._prepare_outgoing_list())
        self.portal.active = False
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()

    def test_no_transport_called_when_generating_alerts(self):
        with patch.object(
            type(self.env["ir.mail_server"]), "send_email", side_effect=AssertionError("No transport")
        ) as transport:
            _, session, enrollment = self.scheduled()
            self.declare(session, enrollment)
            self.assertEqual(transport.call_count, 0)


@tagged("post_install", "-at_install")
class TestQualityAlerts(QualityCase):
    def test_private_quality_alert_requires_the_actual_dossier_grant(self):
        from odoo import Command

        self.env.ref("training_management.group_training_coordinator").write(
            {"user_ids": [Command.link(self.quality.id)]}
        )
        self.quality.partner_id.email = "reviewer@example.invalid"
        self.company.write(
            {
                "training_notification_template_id": self.env["mail.template"]
                .create(
                    {
                        "name": "Fictional notification identity",
                        "model_id": self.env["ir.model"]._get_id("res.company"),
                        "email_from": "{{ object.name }} <contact@example.invalid>",
                        "reply_to": "contact@example.invalid",
                    }
                )
                .id,
                "training_notification_manager_id": self.quality.id,
            }
        )
        complaint = self.complaint()
        notice = self.env["training.operator.notice"].search(
            [("source_model", "=", "training.complaint"), ("source_id", "=", complaint.id)]
        )
        self.assertEqual(len(notice), 1)
        self.assertTrue(notice.mail_id._prepare_outgoing_list())
        self.assertNotIn("CONFIDENTIAL", notice.mail_id.body_html)
        self.assertNotIn(complaint.name, notice.mail_id.subject)
        complaint.write({"quality_id": self.other_quality.id})
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()
