"""P11: real identities, post-training lifecycle and private evidence boundaries."""

from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, tagged
from odoo.tools.translate import load_language
from odoo.tools.misc import limited_field_access_token

from .test_closure import ClosureCase
from .test_material import PDF


class PracticeCase(ClosureCase):
    def plan(self, **values):
        delivery = self.delivery(learning_tutor_id=self.portal_b.id, timezone=values.pop("timezone", "UTC"))
        self.lot(delivery, quantity=1)
        enrollment = self.opened(delivery)
        delivery.action_confirm()
        delivery.action_start()
        delivery.action_deliver()
        return (
            self.env["training.practice.action"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "PRIVATE fictional practice action",
                    "enrollment_id": enrollment.id,
                    "completed_on": fields.Date.today() - timedelta(days=30),
                    "horizon": "30",
                    "service_reference": "Fictional service agreement",
                    "trainer_feedback": True,
                    "retention_id": self.retention.id,
                    **values,
                }
            )
        )

    def as_user(self, action, user=None):
        # Same narrowly elevated record as the controller, with original actor.
        return action.with_user(user or self.portal).sudo()


@tagged("post_install", "-at_install")
class TestPractice(PracticeCase):
    def test_empty_native_form_and_30_60_day_deadlines(self):
        action = self.plan()
        with Form(self.env["training.practice.action"].with_user(self.coordinator)) as form:
            form.name = "Fictional sixty-day action"
            form.enrollment_id = action.enrollment_id
            form.completed_on = action.completed_on
            form.horizon = "60"
            form.service_reference = "Fictional agreement"
            form.retention_id = self.retention
        self.assertEqual(form.record.due_date, action.completed_on + timedelta(days=60))
        self.assertEqual(action.due_date, action.completed_on + timedelta(days=30))
        self.assertFalse(action.entry_ids)
        with self.assertRaises(ValidationError):
            action.write({"horizon": "60"})
        with self.assertRaises(ValidationError):
            self.plan(completed_on=fields.Date.today() + timedelta(days=1))
        with self.assertRaises(AccessError):
            self.env["training.practice.action"].with_user(self.internal).create({"name": "forged"})
        with self.assertRaises(ValidationError):
            self.plan(state="done")

    def test_completion_optional_proof_feedback_and_double_submit(self):
        action = self.plan()
        participant, trainer = self.as_user(action), self.as_user(action, self.portal_b)
        with self.assertRaises(ValidationError):
            trainer._submit("trainer", "too early")
        participant._submit("participant", "PRIVATE completion note", PDF, "../proof.pdf")
        participant._submit("participant", "PRIVATE completion note", PDF, "proof.pdf")
        self.assertEqual(action.state, "done")
        self.assertEqual(len(action.entry_ids), 1)
        proof = action.entry_ids
        self.assertEqual(proof.create_uid, self.portal)
        self.assertEqual(proof.data.content, PDF)
        self.assertEqual(proof.filename, "proof.pdf")
        trainer._submit("trainer", "PRIVATE trainer comment", PDF, "feedback.pdf")
        trainer._submit("trainer", "PRIVATE trainer comment", PDF, "feedback.pdf")
        self.assertEqual(len(action.entry_ids), 2)
        self.assertEqual(action.entry_ids[-1].create_uid, self.portal_b)
        action.action_close()
        action.action_close()
        self.assertEqual(len(action.entry_ids), 3)
        with self.assertRaises(ValidationError):
            trainer._submit("trainer", "late comment")
        with self.assertRaises(AccessError):
            proof.write({"body": "forged"})
        with self.assertRaises(UserError):
            proof.export_data(["body"])
        optional = self.plan(trainer_feedback=False)
        self.as_user(optional)._submit("participant")
        self.assertFalse(optional.entry_ids.data)
        with self.assertRaises(AccessError):
            self.as_user(optional, self.portal_b)._submit("trainer", "forged")
        self.assertFalse(
            self.env["training.learning.progress"].sudo().search([("enrollment_id", "=", action.enrollment_id.id)])
        )

    def test_expiration_closure_and_explicit_revocation(self):
        action = self.plan()
        # Ordinary expiry of S05 never blocks an agreed post-training action.
        action.enrollment_id._store({"access_end": fields.Datetime.now() - timedelta(days=1)}, "Fictional expiry")
        action.delivery_id.action_close(reason="Fictional normal closure")
        self.assertEqual(action.enrollment_id.state, "closed")
        self.assertTrue(self.as_user(action)._eligible("participant"))
        self.as_user(action)._submit("participant")
        action.action_withdraw_access()
        action.action_withdraw_access()
        self.assertEqual(len(action.entry_ids), 2)
        self.assertFalse(self.as_user(action)._eligible("participant"))
        withdrawn = self.plan()
        withdrawn.enrollment_id.action_revoke_authorization(reason="Fictional commercial withdrawal")
        self.assertFalse(self.as_user(withdrawn)._eligible("participant"))
        denied = self.plan()
        denied.enrollment_id.action_revoke_access(reason="Fictional explicit revocation")
        denied.delivery_id.action_close(reason="Fictional normal closure")
        self.assertTrue(denied.access_withdrawn)
        self.assertFalse(self.as_user(denied)._eligible("participant"))

    def test_current_roles_company_isolation_and_binary_tokens(self):
        action = self.plan()
        self.as_user(action)._submit("participant", "PRIVATE", PDF, "private.pdf")
        entry = action.entry_ids
        policy = self.env["training.document.policy"]
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .search([("res_model", "=", entry._name), ("res_id", "=", entry.id), ("res_field", "=", "data")])
        )
        self.assertEqual(attachment.company_id, action.company_id)
        for user in (self.portal, self.portal_b, self.coordinator):
            self.assertTrue(policy.with_user(user)._can_read(entry))
        for user in (self.internal, self.reader, self.other_quality, self.env.ref("base.public_user")):
            self.assertFalse(policy.with_user(user)._can_read(entry))
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._get_stream_from(entry.sudo(), "data")
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._find_record(
                    res_model=entry._name,
                    res_id=entry.id,
                    field="data",
                    access_token=limited_field_access_token(entry, "data", scope="binary"),
                )
        with self.assertRaises(ValidationError):
            attachment.write({"public": True})
        with self.assertRaises(ValidationError):
            attachment.unlink()
        with self.assertRaises(ValidationError):
            policy._check_send(entry, self.portal.partner_id, required=False)
        action.enrollment_id.write({"learning_tutor_id": self.internal.id})
        self.assertFalse(policy.with_user(self.portal_b)._can_read(entry))
        self.portal.write({"company_ids": [Command.set(self.other_company.ids)], "company_id": self.other_company.id})
        self.assertFalse(policy.with_user(self.portal)._can_read(entry))
        self.assertEqual(self.env["training.practice.action"].with_user(self.portal)._portal_rows(), [])

    def test_reminder_occurrences_transport_and_stop(self):
        action = self.plan()
        model = self.env["training.practice.action"]
        model._cron_reminders()
        model._cron_reminders()
        notices = self.env["training.practice.notice"].search([("action_id", "=", action.id)])
        self.assertEqual(len(notices), 1)
        notice = notices.sudo()
        self.assertTrue(notice._authorized())
        self.assertFalse(notice.mail_id.attachment_ids or notice.mail_id.email_cc or notice.mail_id.recipient_ids)
        self.assertNotIn("PRIVATE", notice.mail_id.body_html)
        notice.mail_id._prepare_outgoing_list()
        self.as_user(action)._submit("participant")
        self.assertFalse(notice._authorized())
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()
        model._cron_reminders()
        self.assertEqual(self.env["training.practice.notice"].search_count([("action_id", "=", action.id)]), 1)
        closed = self.plan()
        closed.action_close()
        model._cron_reminders()
        self.assertFalse(self.env["training.practice.notice"].search([("action_id", "=", closed.id)]))
        no_reminder = self.plan(reminder_days=0)
        model._cron_reminders()
        self.assertFalse(self.env["training.practice.notice"].search([("action_id", "=", no_reminder.id)]))

    def test_intervals_timezone_and_suspended_closure(self):
        action = self.plan(timezone="Pacific/Auckland")
        instant = datetime(2026, 10, 28, 12, 30)
        self.assertEqual(
            fields.Date.context_today(
                action.with_context(tz=action.delivery_id.timezone), timestamp=instant
            ).isoformat(),
            "2026-10-29",
        )
        self.assertEqual(
            fields.Date.context_today(action.with_context(tz="UTC"), timestamp=instant).isoformat(), "2026-10-28"
        )
        model = self.env["training.practice.action"]
        with patch.object(fields.Date, "context_today", return_value=action.due_date - timedelta(days=1)):
            model._cron_reminders()
        self.assertFalse(self.env["training.practice.notice"].search([("action_id", "=", action.id)]))
        with patch.object(fields.Date, "context_today", return_value=action.due_date):
            model._cron_reminders()
        with patch.object(fields.Date, "context_today", return_value=action.due_date + timedelta(days=15)):
            model._cron_reminders()
            model._cron_reminders()
        notices = self.env["training.practice.notice"].search([("action_id", "=", action.id)])
        self.assertEqual(len(notices), 2)
        self.assertEqual(set(notices.mapped("event_key")), {f"practice:{action.id}:0", f"practice:{action.id}:2"})
        suspended = self.plan()
        suspended.enrollment_id.action_suspend_access(reason="Fictional suspension")
        suspended.delivery_id.action_close(reason="Fictional closure")
        self.assertTrue(suspended.access_withdrawn)
        self.assertFalse(self.as_user(suspended)._eligible("participant"))

    def test_native_sender_identity_and_failure_alert(self):
        self.company.write(
            {
                "training_notification_template_id": self.env["mail.template"]
                .create(
                    {
                        "name": "Fictional notification identity",
                        "model_id": self.env["ir.model"]._get_id("res.company"),
                        "email_from": "{{ object.name }} <notify@example.invalid>",
                        "reply_to": "notify@example.invalid",
                    }
                )
                .id,
                "training_notification_manager_id": self.coordinator.id,
            }
        )
        action = self.plan()
        self.env["training.practice.action"]._cron_reminders()
        notice = self.env["training.practice.notice"].sudo().search([("action_id", "=", action.id)])
        notice.mail_id._prepare_outgoing_list()
        notice.mail_id.write({"email_from": "forged@example.invalid"})
        self.assertTrue(notice.mail_id._prepare_outgoing_list())
        notice.mail_id.write(self.env["mail.mail"]._training_identity(self.company))
        notice.mail_id.write({"state": "exception"})
        notices = (
            self.env["training.operator.notice"]
            .sudo()
            .search([("source_model", "=", notice._name), ("source_id", "=", notice.id)])
        )
        self.assertEqual(len(notices), 1)
        self.assertTrue(notices._authorized())
        self.assertNotIn("PRIVATE", notices.mail_id.body_html)
        self.assertFalse(notices.mail_id.attachment_ids)

    def test_summary_is_explicit_and_never_projects_private_content(self):
        action = self.plan()
        self.as_user(action)._submit("participant", "PRIVATE evidence", PDF, "private.pdf")
        lot = action.delivery_id.allocation_ids
        grant = (
            self.env["training.company.authorization"]
            .with_user(self.coordinator)
            .create(
                {
                    "customer_id": self.customer.id,
                    "user_id": self.portal_b.id,
                    "allocation_ids": [Command.set(lot.ids)],
                }
            )
        )
        grant.action_confirm()
        summaries = self.env["training.practice.summary"].with_user(self.coordinator)
        self.assertFalse(summaries.with_user(self.portal_b)._client_rows(lot))
        summary = summaries.create(
            {
                "allocation_id": lot.id,
                "authorization_id": grant.id,
                "body": "Agreed collective summary",
                "authorization_reference": "Fictional signed agreement",
                "retention_id": self.retention.id,
            }
        )
        self.assertFalse(summaries.with_user(self.portal_b)._client_rows(lot))
        summary.action_publish()
        self.assertEqual(summaries.with_user(self.portal_b)._client_rows(lot)[0]["body"], "Agreed collective summary")
        with self.assertRaises(ValidationError):
            summary.write({"body": "forged"})
        with self.assertRaises(AccessError):
            summaries.with_user(self.portal)._client_rows(lot)
        grant.action_revoke()
        with self.assertRaises(AccessError):
            summaries.with_user(self.portal_b)._client_rows(lot)
        self.assertEqual(action.entry_ids.body, "PRIVATE evidence")


@tagged("post_install", "-at_install")
class TestPracticeHTTP(PracticeCase, HttpCase):
    def test_forms_roles_direct_files_and_private_headers(self):
        action = self.plan()
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open("/my/training-practice")
        self.assertEqual(page.status_code, 200)
        self.assertIn(action.name, page.text)
        self.assertIn("no-store", page.headers["Cache-Control"])
        path = f"/my/training-practice/{action.id}"
        submitted = self.url_open(
            path,
            data={"csrf_token": self.csrf_token(), "role": "participant", "body": "PRIVATE portal note"},
            files={"file": ("proof.pdf", PDF, "application/pdf")},
            allow_redirects=False,
        )
        self.assertEqual(submitted.status_code, 303)
        entry = action.sudo().entry_ids
        self.assertEqual(len(entry), 1)
        url = f"{path}/files/{entry.id}"
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.authenticate(self.portal_b.login, self.portal_b.login)
        error = self.url_open(path, data={"csrf_token": self.csrf_token(), "role": "trainer", "body": ""})
        self.assertEqual(error.status_code, 400)
        reply = self.url_open(
            path,
            data={"csrf_token": self.csrf_token(), "role": "trainer", "body": "PRIVATE trainer reply"},
            allow_redirects=False,
        )
        self.assertEqual(reply.status_code, 303)
        self.assertEqual(len(action.sudo().entry_ids), 2)
        self.authenticate(self.internal.login, self.internal.login)
        self.assertNotIn(action.name, self.url_open("/my/training-practice").text)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.assertEqual(
            self.url_open(path, data={"csrf_token": self.csrf_token(), "role": "participant"}).status_code, 404
        )
        self.authenticate(self.portal.login, self.portal.login)
        action.enrollment_id.action_revoke_access(reason="Fictional revocation")
        self.assertEqual(self.url_open(url).status_code, 404)

    def test_french_form_and_escaped_private_content(self):
        load_language(self.cr, "fr_FR")
        self.env["ir.module.module"].search([("name", "=", "training_management")])._update_translations(["fr_FR"])
        self.portal.lang = "fr_FR"
        if "website" in self.env and "language_ids" in self.env["website"]._fields:
            french = self.env.ref("base.lang_fr")
            self.env["website"].search([]).write(
                {"language_ids": [Command.set(french.ids)], "default_lang_id": french.id}
            )
        action = self.plan(name="<script>PRIVATE action</script>")
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open("/my/training-practice")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Mes plans de mise en pratique", page.text)
        self.assertIn("Marquer comme réalisée", page.text)
        self.assertNotIn("<script>PRIVATE action</script>", page.text)
        self.assertIn("&lt;script&gt;PRIVATE action&lt;/script&gt;", page.text)
        self.assertIn(f'for="practice_body_{action.id}"', page.text)
        self.assertIn(f'id="practice_body_{action.id}"', page.text)
