from datetime import UTC, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from odoo.addons.mail.tests.common import MockEmail
from odoo.exceptions import AccessError, ValidationError

from .test_crm_session_confirmation import TestCrmSessionConfirmation


class TestSessionConfirmationEmail(MockEmail, TestCrmSessionConfirmation):
    def notices(self, lead):
        return self.env["training.session.confirmation.notice"].sudo().search([("lead_id", "=", lead.id)])

    def planning(self, lead):
        delivery = lead.training_requested_delivery_id
        start = (delivery.start_at + timedelta(minutes=1)).replace(second=0, microsecond=0)
        end = start + timedelta(minutes=30)
        start = start.replace(tzinfo=UTC).astimezone(ZoneInfo(delivery.timezone))
        end = end.replace(tzinfo=UTC).astimezone(ZoneInfo(delivery.timezone))
        return (
            self.env["training.session"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional meeting",
                    "delivery_id": delivery.id,
                    "mode": "remote",
                    "start_date": start.date(),
                    "end_date": end.date(),
                    "start_hour": start.hour + start.minute / 60,
                    "end_hour": end.hour + end.minute / 60,
                    "meeting_url": "https://meeting.example.invalid/session",
                    "location": "Fictional practical instructions",
                }
            )
        )

    def test_individual_requester_participant_same_address_gets_one_native_email(self):
        lead = self.request()
        wizard = self.assistant(lead)
        person = wizard.line_ids.participant_id
        person.email = "Fictional Requester <FICTIONAL-REQUESTER@example.invalid>"
        wizard.action_confirm()
        notice = self.notices(lead).ensure_one()
        self.assertEqual(notice.email, "fictional-requester@example.invalid")
        self.assertTrue(notice.is_requester)
        self.assertEqual(notice.participant_ids, person)
        mail = notice.mail_id
        self.assertEqual(mail.state, "outgoing")
        self.assertFalse(mail.auto_delete)
        self.assertEqual(mail.model, notice._name)
        self.assertFalse(mail.email_cc or mail.recipient_ids or mail.attachment_ids)
        self.assertIn(lead.training_requested_course_id.name, mail.subject)
        self.assertIn(lead.training_requested_delivery_id.timezone, mail.body_html)
        original = mail.id
        for _ in range(2):
            wizard.action_confirm()
            self.env[notice._name].with_user(self.coordinator)._queue(lead)
        self.assertEqual(self.notices(lead).mail_id.ids, [original])
        mail.write({"state": "sent"})
        self.env[notice._name].with_user(self.coordinator)._queue(lead)
        self.assertEqual(self.notices(lead).mail_id.ids, [original])

    def test_group_messages_include_schedule_and_practical_details_privately(self):
        lead = self.request(count=3)
        self.planning(lead)
        wizard = self.assistant(lead)
        wizard.action_confirm()
        notices = self.notices(lead)
        self.assertEqual(len(notices), 4)
        self.assertEqual(len(notices.mail_id), 4)
        self.assertEqual(len(set(notices.mapped("email"))), 4)
        for notice in notices:
            mail = notice.mail_id
            self.assertEqual(mail.email_to, notice.email)
            self.assertIn("https://meeting.example.invalid/session", mail.body_html)
            self.assertIn("Fictional practical instructions", mail.body_html)
            self.assertIn(str(lead.training_requested_delivery_id.start_at.year), mail.body_html)
            self.assertFalse(mail.email_cc or mail.recipient_ids or mail.recipient_cc_ids or mail.attachment_ids)
            if not notice.is_requester:
                others = lead.training_session_enrollment_ids.participant_id - notice.participant_ids
                for person in others:
                    self.assertNotIn(person.name, mail.body_html)
        wizard.action_confirm()
        self.assertEqual(self.notices(lead).mail_id, notices.mail_id)

    def test_missing_address_or_template_failure_rolls_back_the_whole_confirmation(self):
        lead = self.request(count=2)
        wizard = self.assistant(lead)
        wizard.line_ids[1].participant_id.email = False
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        self.assertFalse(lead.training_session_enrollment_ids)
        self.assertFalse(lead.training_requested_delivery_id.enrollment_ids)
        self.assertFalse(self.notices(lead))
        wizard.line_ids[1].participant_id.email = "second@example.invalid"
        with patch.object(
            type(self.env["mail.template"]), "send_mail", side_effect=ValidationError("Fictional failure")
        ):
            with self.assertRaises(ValidationError):
                wizard.action_confirm()
        self.assertFalse(self.notices(lead))
        self.assertFalse(lead.training_session_enrollment_ids)
        wizard.action_confirm()
        self.assertEqual(len(self.notices(lead)), 3)

    def test_transport_rechecks_recipient_schedule_and_envelope(self):
        lead = self.request()
        wizard = self.assistant(lead)
        wizard.action_confirm()
        notices = self.notices(lead)
        participant = notices.filtered(lambda notice: not notice.is_requester).ensure_one()
        self.assertTrue(participant._authorized())
        self.assertTrue(participant.mail_id._prepare_outgoing_list())
        person = participant.participant_ids
        original_email = person.email
        person.email = "changed@example.invalid"
        with self.assertRaises(ValidationError):
            participant.mail_id._prepare_outgoing_list()
        person.email = original_email
        participant.mail_id.email_cc = "intruder@example.invalid"
        with self.assertRaises(ValidationError):
            participant.mail_id._prepare_outgoing_list()
        participant.mail_id.email_cc = False
        delivery = lead.training_requested_delivery_id
        delivery.action_change_dates(
            start_at=delivery.start_at + timedelta(days=1),
            end_at=delivery.end_at + timedelta(days=1),
            reason="Fictional rescheduling",
        )
        for notice in notices:
            with self.assertRaises(ValidationError):
                notice.mail_id._prepare_outgoing_list()

    def test_native_transport_sends_once_with_captured_smtp(self):
        lead = self.request(count=3)
        wizard = self.assistant(lead)
        with self.mock_mail_gateway():
            wizard.action_confirm()
            mails = self.notices(lead).mail_id
            mails.send(auto_commit=False, raise_exception=True)
            self.assertEqual(len(self._mails), 4)
            self.assertEqual(mails.mapped("state"), ["sent"] * 4)
            expected = set(self.notices(lead).mapped("email"))
            actual = {email for mail in self._mails for email in mail["email_to"]}
            self.assertEqual(actual, expected)
            wizard.action_confirm()
            self.env["training.session.confirmation.notice"].with_user(self.coordinator)._queue(lead)
            self.assertEqual(self.notices(lead).mail_id, mails)
            self.assertFalse(mails.filtered(lambda mail: mail.state == "outgoing"))
            self.assertEqual(len(self._mails), 4)

    def test_only_authorized_staff_can_read_confirmation_details(self):
        lead = self.request()
        wizard = self.assistant(lead)
        wizard.action_confirm()
        notice = self.notices(lead)[0]
        self.assertEqual(notice.with_user(self.coordinator).email, notice.email)
        for user in (self.portal, self.seller):
            with self.assertRaises(AccessError):
                notice.with_user(user).read(["email", "details_html"])
        with self.assertRaises(AccessError):
            notice.with_user(self.coordinator).write({"email": "changed@example.invalid"})
        action = lead.action_view_session_confirmation_emails()
        self.assertEqual(action["res_model"], notice._name)
        self.assertEqual(action["domain"], [("lead_id", "=", lead.id)])
