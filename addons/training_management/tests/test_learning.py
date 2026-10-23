"""S05 completion: real identities, native evidence, transport and portal boundaries."""

from datetime import timedelta
import hashlib
import json
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tools.misc import limited_field_access_token

from .test_material import PDF, MaterialCase


class LearningCase(MaterialCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.partner_id.email = "sender@example.invalid"
        cls.peer = new_test_user(cls.env, login="s052_peer", groups="base.group_portal")

    def activity(self, delivery, **values):
        return (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create({"name": "Fictional required activity", "delivery_id": delivery.id, **values})
        )

    def setup_learning(self, **delivery_values):
        delivery = self.delivery(learning_tutor_id=self.portal_b.id, **delivery_values)
        activity = self.activity(delivery, criterion="validation")
        enrollment = self.opened(delivery)
        return delivery, activity, enrollment

    def service(self, user=None):
        return self.env["training.learning.service"].with_user(user or self.portal)

    def post(self, enrollment, kind="submission", **values):
        return self.service(self.portal_b if kind in ("correction", "answer") else self.portal)._post(
            enrollment.id, kind, request_key=str(uuid4()), body="Fictional private work", **values
        )

    def file(self, entry):
        return (
            self.env["ir.attachment"]
            .sudo()
            .search([("res_model", "=", entry._name), ("res_id", "=", entry.id), ("res_field", "=", "data")])
        )


@tagged("post_install", "-at_install")
class TestLearning(LearningCase):
    def test_native_activity_form_criteria_optional_and_cycles(self):
        delivery = self.delivery()
        with Form(
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .with_context(default_delivery_id=delivery.id)
        ) as form:
            form.name = "Fictional declared consultation"
        first = form.record
        optional = self.activity(delivery, optional=True)
        final = self.activity(delivery, dependency_ids=[Command.set(first.ids)])
        with self.assertRaises(ValidationError):
            first.write({"dependency_ids": [Command.set(final.ids)]})
        with self.assertRaises(ValidationError):
            final.write({"dependency_ids": [Command.set(optional.ids)]})
        foreign = self.activity(self.delivery())
        with self.assertRaises(ValidationError):
            final.write({"dependency_ids": [Command.set(foreign.ids)]})
        enrollment = self.opened(delivery)
        self.assertFalse(self.service()._complete(enrollment, first))
        with self.assertRaises(ValidationError):
            self.service()._declare(enrollment.id, final.id)
        self.service()._declare(enrollment.id, first.id)
        self.service()._declare(enrollment.id, first.id)
        self.service()._declare(enrollment.id, final.id)
        rows = self.service()._rows(enrollment)
        self.assertEqual(sum(not r["optional"] for r in rows), 2)
        self.assertEqual(sum(r["complete"] and not r["optional"] for r in rows), 2)
        self.assertFalse(self.service()._complete(enrollment, optional))
        self.assertEqual(len(first.progress_ids), 1)
        with self.assertRaises(ValidationError):
            first.write({"criterion": "validation"})
        with self.assertRaises(ValidationError):
            first.update_field_translations("name", {"en_US": "Fictional forbidden change"})

    def test_submission_review_and_new_versions_keep_native_messages_and_files(self):
        delivery, activity, enrollment = self.setup_learning()
        entry = self.post(enrollment, activity_id=activity.id, data=PDF, filename="work.pdf")
        progress = self.service()._progress(enrollment, activity)
        self.assertFalse(progress.completed)
        self.assertEqual(entry.message_id._name, "mail.message")
        self.assertEqual(entry.message_id.author_id, self.portal.partner_id)
        self.assertEqual(entry.create_uid, self.portal)
        self.assertEqual(self.file(entry).raw.content, PDF)
        self.assertEqual(self.file(entry).company_id, enrollment.company_id)
        self.assertFalse(self.file(entry).public or self.file(entry).access_token)
        correction = self.post(
            enrollment,
            "correction",
            activity_id=activity.id,
            parent_id=entry.id,
            revision=progress.revision,
            decision="changes",
            data=PDF + b"feedback",
            filename="feedback.pdf",
        )
        self.assertEqual(progress.state, "changes")
        self.assertFalse(progress.completed)
        newer = self.post(
            enrollment,
            activity_id=activity.id,
            parent_id=entry.id,
            revision=progress.revision,
            data=PDF + b"new version",
            filename="new.pdf",
        )
        with self.assertRaises(ValidationError):
            self.post(
                enrollment,
                "correction",
                activity_id=activity.id,
                parent_id=entry.id,
                revision=progress.revision,
                decision="accepted",
            )
        self.post(
            enrollment,
            "correction",
            activity_id=activity.id,
            parent_id=newer.id,
            revision=progress.revision,
            decision="accepted",
        )
        self.assertTrue(progress.completed)
        self.assertEqual(entry.data.content, PDF)
        self.assertEqual(correction.data.content, PDF + b"feedback")
        self.assertEqual(newer.parent_id, entry)
        for operation in (
            lambda: entry.write({"filename": "altered"}),
            lambda: entry.copy(),
            lambda: entry.unlink(),
            lambda: entry.message_id.write({"body": "altered"}),
            lambda: entry.message_id.copy(),
            lambda: entry.message_id.unlink(),
        ):
            with self.assertRaises((AccessError, ValidationError)):
                operation()
        self.assertFalse(delivery.message_ids.filtered(lambda m: "Fictional private work" in m.body))
        self.assertFalse(enrollment.message_ids.filtered(lambda m: "Fictional private work" in m.body))

    def test_uploaded_image_keeps_original_bytes_and_hash(self):
        _, activity, enrollment = self.setup_learning()
        self.env["ir.config_parameter"].set_str("base.image_autoresize_max_px", "1920x1920")
        output = BytesIO()
        Image.new("RGB", (2001, 2), color="blue").save(output, format="PNG")
        payload = output.getvalue()
        entry = self.post(enrollment, activity_id=activity.id, data=payload, filename="original-work.png")
        self.assertEqual(self.file(entry).raw.content, payload)
        self.assertEqual(entry.data.content, payload)
        self.assertEqual(entry.sha256, hashlib.sha256(payload).hexdigest())

    def test_submission_criterion_and_authoritative_evaluation_hook(self):
        _, activity, enrollment = self.setup_learning()
        submitted = self.activity(enrollment.delivery_id, criterion="submission")
        self.post(enrollment, activity_id=submitted.id)
        self.assertTrue(self.service()._complete(enrollment, submitted))
        evaluated = self.activity(enrollment.delivery_id, criterion="evaluation", evaluation_threshold=75)
        self.assertFalse(self.service()._complete(enrollment, evaluated))
        with self.assertRaises(ValidationError):
            self.service()._declare(enrollment.id, evaluated.id)
        with self.assertRaises(ValidationError):
            self.post(enrollment, activity_id=evaluated.id)
        # The only provider is the future S06 authoritative result, never RPC data.
        with patch.object(type(self.service()), "_evaluation_result", return_value=74):
            self.assertFalse(self.service()._complete(enrollment, evaluated))
        with patch.object(type(self.service()), "_evaluation_result", return_value=75):
            self.assertTrue(self.service()._complete(enrollment, evaluated))
        self.assertFalse(self.service()._complete(enrollment, activity))

    def test_idempotency_and_stale_submission_rejected(self):
        _, activity, enrollment = self.setup_learning()
        key = str(uuid4())
        values = {"activity_id": activity.id, "body": "Fictional unique submission", "request_key": key}
        entry = self.service()._post(enrollment.id, "submission", **values)
        self.assertEqual(self.service()._post(enrollment.id, "submission", **values), entry)
        self.assertEqual(self.env["training.learning.notice"].search_count([("entry_id", "=", entry.id)]), 1)
        with self.assertRaises(ValidationError):
            self.service()._post(enrollment.id, "submission", **dict(values, body="different work"))
        with self.assertRaises(ValidationError):
            self.post(enrollment, activity_id=activity.id, revision=0)
        self.assertEqual(len(activity.progress_ids), 1)

    def test_exact_mission_and_private_help_including_internal_coordinator(self):
        delivery, activity, enrollment = self.setup_learning()
        question = self.post(enrollment, "question")
        answer = self.post(enrollment, "answer", parent_id=question.id)
        policy = self.env["training.document.policy"]
        for user in (self.portal, self.portal_b):
            self.assertTrue(policy.with_user(user)._can_read(question))
        for user in (self.peer, self.coordinator, self.reader, self.internal, self.env.ref("base.public_user")):
            self.assertFalse(policy.with_user(user)._can_read(question))
            with self.assertRaises(AccessError):
                self.service(user)._enrollment(enrollment.id, tutor=True)
            with self.assertRaises(AccessError):
                question.with_user(user).read(["message_id"])
            with self.assertRaises(AccessError):
                question.message_id.with_user(user).read(["body"])
        # A classroom instructor without an explicit tutoring mission has no grant.
        delivery.write({"learning_tutor_id": self.internal.id})
        self.assertFalse(policy.with_user(self.portal_b)._can_read(question))
        self.assertFalse(question.message_id.with_user(self.portal_b).sudo()._get_with_access())
        self.assertTrue(policy.with_user(self.internal)._can_read(answer))
        self.assertEqual(question.with_user(self.internal).read(["kind"])[0]["kind"], "question")
        enrollment.write({"learning_tutor_id": self.portal_b.id})
        self.assertFalse(policy.with_user(self.internal)._can_read(question))
        self.assertTrue(policy.with_user(self.portal_b)._can_read(question))
        enrollment.action_suspend_access(reason="Fictional suspension")
        self.assertFalse(policy.with_user(self.portal)._can_read(question))
        self.assertTrue(policy.with_user(self.portal_b)._can_read(question))
        with self.assertRaises(AccessError):
            self.post(enrollment, "question")
        self.assertEqual(answer.parent_id, question)
        self.assertFalse(self.env["mail.mail"].search([("model", "=", question._name)]))
        self.assertFalse(activity.progress_ids)

    def test_internal_author_loses_native_message_and_file_access_on_suspension(self):
        delivery = self.delivery()
        enrollment = self.enrollment(delivery, participant_id=self.internal.partner_id.id, user_id=self.internal.id)
        enrollment.action_validate_prerequisites(reason="Fictional review")
        enrollment.action_confirm()
        enrollment.action_authorize(reason="Fictional authorization")
        enrollment.action_open_access(reason="Fictional opening")
        entry = self.service(self.internal)._post(
            enrollment.id,
            "question",
            request_key=str(uuid4()),
            body="Fictional internal author's private work",
            data=PDF,
            filename="private.pdf",
        )
        message = entry.message_id.with_user(self.internal)
        attachment = self.file(entry).with_user(self.internal)
        self.assertIn("Fictional internal author's private work", message.read(["body"])[0]["body"])
        self.assertTrue(attachment.read(["raw"])[0]["raw"])
        self.assertEqual(attachment.raw.content, PDF)
        enrollment.action_suspend_access(reason="Fictional suspension")
        for record, fields in ((message, ["body"]), (attachment, ["raw"]), (entry.with_user(self.internal), ["kind"])):
            with self.assertRaises(AccessError):
                record.read(fields)
        self.assertFalse(self.env["mail.message"].with_user(self.internal).search([("id", "=", message.id)], limit=1))
        self.assertFalse(message.sudo()._get_with_access())

    def test_cross_enrollment_company_account_and_message_forgery(self):
        _, activity, enrollment = self.setup_learning()
        other = self.opened()
        question = self.post(enrollment, "question")
        for operation in (
            lambda: self.service()._declare(other.id, activity.id),
            lambda: self.post(other, "answer", parent_id=question.id),
            lambda: (
                self.env["mail.message"]
                .with_user(self.coordinator)
                .create({"model": question._name, "res_id": question.id, "body": "forged"})
            ),
            lambda: self.env[question._name].with_user(self.portal).create({"kind": "question"}),
        ):
            with self.assertRaises(AccessError):
                operation()
        self.portal.write({"company_ids": [Command.set(self.other_company.ids)], "company_id": self.other_company.id})
        self.assertFalse(self.env["training.document.policy"].with_user(self.portal)._can_read(question))
        self.portal_b.active = False
        self.assertFalse(self.env["training.document.policy"].with_user(self.portal_b)._can_read(question))

    def test_file_tokens_mutation_relational_export_and_private_mail(self):
        _, activity, enrollment = self.setup_learning()
        entry = self.post(enrollment, activity_id=activity.id, data=PDF, filename="work.pdf")
        attachment = self.file(entry)
        token = limited_field_access_token(attachment, "raw", scope="binary")
        self.assertTrue(
            self.env["ir.binary"]
            .with_user(self.portal_b)
            ._find_record(res_id=attachment.id, field="raw", access_token=token)
        )
        for user in (self.coordinator, self.internal, self.env.ref("base.public_user")):
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._find_record(
                    res_id=attachment.id, field="raw", access_token=token
                )
        for vals in (
            {"public": True},
            {"access_token": "forged"},
            {"res_id": 0},
            {"res_model": "res.partner"},
            {"raw": b"replaced"},
        ):
            with self.assertRaises(ValidationError):
                attachment.write(vals)
        for operation in (
            lambda: attachment.copy(),
            lambda: attachment.unlink(),
            lambda: (
                self.env["ir.attachment"]
                .with_user(self.portal)
                .create(
                    {"name": "extra", "raw": PDF, "res_model": entry._name, "res_id": entry.id, "res_field": "data"}
                )
            ),
        ):
            with self.assertRaises(ValidationError):
                operation()
        for record, paths in (
            (entry, ["message_id/body"]),
            (attachment, ["raw"]),
            (entry.message_id, ["body"]),
            (enrollment.with_user(self.coordinator), ["learning_progress_ids/latest_submission_id/data"]),
        ):
            with self.assertRaises((UserError, AccessError)):
                record.export_data(paths)
        mail = self.env["mail.mail"].create(
            {
                "subject": "Fictional unrelated",
                "body_html": "Fictional",
                "email_from": "sender@example.invalid",
                "recipient_ids": [Command.set(self.portal.partner_id.ids)],
                "attachment_ids": [Command.set(attachment.ids)],
            }
        )
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()
        enrollment.action_revoke_access(reason="Fictional revoke")
        with self.assertRaises(AccessError):
            self.env["ir.binary"].with_user(self.portal)._find_record(
                res_id=attachment.id, field="raw", access_token=token
            )

    def test_generic_notice_queue_checks_recipient_at_transport_and_retry(self):
        delivery, activity, enrollment = self.setup_learning()
        entry = self.post(enrollment, activity_id=activity.id, data=PDF, filename="private-name.pdf")
        notice = self.env["training.learning.notice"].search([("entry_id", "=", entry.id)])
        self.assertEqual(notice.recipient_id, self.portal_b)
        self.assertTrue(notice.mail_id._prepare_outgoing_list())
        self.assertNotIn("Fictional private work", notice.mail_id.body_html)
        self.assertNotIn("private-name.pdf", notice.mail_id.body_html)
        self.assertNotIn(activity.name, notice.mail_id.body_html)
        self.assertFalse(notice.mail_id.attachment_ids or notice.mail_id.recipient_ids or notice.mail_id.email_cc)
        notice.mail_id.email_cc = "forged@example.invalid"
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()
        notice.mail_id.email_cc = False
        delivery.write({"learning_tutor_id": self.internal.id})
        notice.mail_id.write({"state": "exception"})
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()
        self.portal_b.partner_id.email = "changed@example.invalid"
        delivery.write({"learning_tutor_id": self.portal_b.id})
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()

    def test_reminders_offer_deadline_optional_suspension_completion_and_repeat(self):
        delivery, _, enrollment = self.setup_learning(
            learning_due_days=5, learning_inactivity_days=2, learning_reminder_days=3
        )
        self.assertEqual(
            self.service()._deadline(enrollment, delivery.learning_activity_ids),
            enrollment.access_start + timedelta(days=5),
        )
        start = enrollment.access_start
        with patch("odoo.fields.Datetime.now", return_value=start + timedelta(days=2, seconds=1)):
            self.env["training.learning.service"]._cron_reminders()
            self.env["training.learning.service"]._cron_reminders()
            notices = self.env["training.learning.notice"].search(
                [("enrollment_id", "=", enrollment.id), ("entry_id", "=", False)]
            )
            self.assertEqual(len(notices), 1)
            self.assertTrue(notices.mail_id._prepare_outgoing_list())
            enrollment.action_suspend_access(reason="Fictional justified suspension")
            self.env["training.learning.service"]._cron_reminders()
            self.assertEqual(
                self.env["training.learning.notice"].search_count([("enrollment_id", "=", enrollment.id)]), 1
            )
            with self.assertRaises(ValidationError):
                notices.mail_id._prepare_outgoing_list()
        enrollment.action_open_access(reason="Fictional resumption")
        optional_delivery = self.delivery(learning_inactivity_days=1, learning_reminder_days=1)
        self.activity(optional_delivery, optional=True)
        optional_enrollment = self.opened(optional_delivery)
        with patch("odoo.fields.Datetime.now", return_value=start + timedelta(days=3)):
            self.assertFalse(self.service()._reminder_due(optional_enrollment))
        with self.assertRaises(ValidationError):
            delivery.write({"learning_reminder_days": 0})

    def test_postponement_keeps_work_without_transferring_private_evidence(self):
        _, activity, enrollment = self.setup_learning()
        entry = self.post(enrollment, activity_id=activity.id, data=PDF, filename="old.pdf")
        target_delivery = self.delivery(learning_tutor_id=self.portal_b.id)
        target = self.enrollment(target_delivery)
        enrollment.action_postpone(target.id, reason="Fictional postponement")
        self.assertEqual(entry.data.content, PDF)
        self.assertFalse(self.env["training.document.policy"].with_user(self.portal)._can_read(entry))
        self.assertFalse(self.env["training.document.policy"].with_user(self.portal_b)._can_read(entry))
        target.action_validate_prerequisites(reason="Fictional review")
        target.action_confirm()
        target.action_authorize(reason="Fictional authorization")
        target.action_open_access(reason="Fictional opening")
        self.assertEqual(self.service()._entries(target), [])
        self.assertEqual(entry.enrollment_id, enrollment)

    def test_no_recipient_is_journaled_and_old_reminders_cannot_burst_on_retry(self):
        delivery = self.delivery(learning_inactivity_days=1, learning_reminder_days=1)
        self.activity(delivery)
        enrollment = self.opened(delivery)
        question = self.post(enrollment, "question")
        journal = self.env["training.learning.notice"].search([("entry_id", "=", question.id)])
        self.assertTrue(journal.not_queued_reason)
        self.assertFalse(journal.mail_id)
        # Backdate only a fictional fixture; evidence timestamps cannot be set by RPC.
        self.env.cr.execute(
            "UPDATE training_learning_entry SET create_date=%s WHERE id=%s", [enrollment.access_start, question.id]
        )
        question.invalidate_recordset(["create_date"])
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_start + timedelta(days=1, seconds=1)):
            self.env["training.learning.service"]._cron_reminders()
            first = self.env["training.learning.notice"].search(
                [("enrollment_id", "=", enrollment.id), ("entry_id", "=", False)]
            )
            self.assertTrue(first.mail_id._prepare_outgoing_list())
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_start + timedelta(days=2, seconds=1)):
            self.env["training.learning.service"]._cron_reminders()
            with self.assertRaises(ValidationError):
                first.mail_id._prepare_outgoing_list()
            all_reminders = self.env["training.learning.notice"].search(
                [("enrollment_id", "=", enrollment.id), ("entry_id", "=", False)]
            )
            self.assertEqual(len(all_reminders), 2)
            self.assertTrue((all_reminders - first).mail_id._prepare_outgoing_list())

    def test_tutor_common_supports_and_ordinary_native_messages(self):
        material = self.material()
        delivery, _, enrollment = self.setup_learning()
        policy = self.env["training.document.policy"].with_user(self.portal_b)
        self.assertTrue(policy._can_read(material))
        self.assertTrue(policy._can_read(self.program.pdf_attachment_id))
        delivery.write({"learning_tutor_id": False})
        self.assertFalse(policy._can_read(material))
        ordinary = self.env["mail.message"].create(
            {
                "model": "res.partner",
                "res_id": self.customer.id,
                "body": "Fictional ordinary message",
                "message_type": "comment",
            }
        )
        self.assertIn("Fictional ordinary message", ordinary.with_user(self.internal).read(["body"])[0]["body"])
        self.assertTrue(ordinary.with_user(self.internal)._get_with_access())
        self.assertTrue(enrollment.exists())

    def test_only_optional_or_completed_work_does_not_trigger_reminder(self):
        delivery = self.delivery(learning_inactivity_days=1, learning_reminder_days=1)
        required = self.activity(delivery)
        self.activity(delivery, optional=True)
        enrollment = self.opened(delivery)
        self.service()._declare(enrollment.id, required.id)
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_start + timedelta(days=3)):
            self.assertFalse(self.service()._reminder_due(enrollment))


@tagged("post_install", "-at_install")
class TestLearningHttp(LearningCase, HttpCase):
    def form_post(self, enrollment, *, tutor=False, kind="question", **values):
        path = "/my/training-tutoring/%s/learning" if tutor else "/my/trainings/%s/learning"
        return self.url_open(
            path % enrollment.id,
            data={
                "csrf_token": self.csrf_token(),
                "kind": kind,
                "body": "Fictional private HTTP message",
                "request_key": str(uuid4()),
                **values,
            },
            allow_redirects=False,
        )

    def test_participant_tutor_submission_review_and_nonmatching_routes(self):
        _, activity, enrollment = self.setup_learning()
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(f"/my/trainings/{enrollment.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(activity.name, response.text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.form_post(enrollment, kind="submission", activity_id=activity.id).status_code, 303)
        entry = self.env["training.learning.entry"].search([("enrollment_id", "=", enrollment.id)])
        progress = self.service()._progress(enrollment, activity)
        self.assertEqual(self.url_open(f"/my/training-tutoring/{enrollment.id}").status_code, 404)
        self.assertEqual(
            self.form_post(enrollment, tutor=True, kind="correction", activity_id=activity.id).status_code, 404
        )
        self.authenticate(self.portal_b.login, self.portal_b.login)
        response = self.url_open(f"/my/training-tutoring/{enrollment.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Fictional private HTTP message", response.text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(
            self.form_post(
                enrollment,
                tutor=True,
                kind="correction",
                activity_id=activity.id,
                parent_id=entry.id,
                revision=progress.revision,
                decision="accepted",
            ).status_code,
            303,
        )
        self.assertTrue(progress.completed)
        self.assertEqual(self.url_open(f"/my/trainings/{enrollment.id}").status_code, 404)
        self.authenticate(self.coordinator.login, self.coordinator.login)
        self.assertEqual(self.url_open(f"/my/training-tutoring/{enrollment.id}").status_code, 404)

    def test_native_file_preview_tokens_no_cache_and_reassignment(self):
        delivery, activity, enrollment = self.setup_learning()
        entry = self.post(
            enrollment, activity_id=activity.id, data=self.program.pdf_attachment_id.raw.content, filename="work.pdf"
        )
        file = self.file(entry)
        urls = [
            f"/web/content/{file.id}",
            f"/web/content/{entry._name}/{entry.id}/data?unique=forever",
            f"/web/content/{file.id}?access_token={limited_field_access_token(file, 'raw', scope='binary')}",
            f"/mail/attachment/pdf_first_page/{file.id}?access_token={file._get_ownership_token()}",
        ]
        self.authenticate(self.portal_b.login, self.portal_b.login)
        for url in urls:
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("attachment", self.url_open(urls[0]).headers["Content-Disposition"])
        self.authenticate(self.peer.login, self.peer.login)
        for url in urls + [f"/my/trainings/{enrollment.id}", f"/my/training-tutoring/{enrollment.id}"]:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        self.authenticate(self.portal.login, self.portal.login)
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_end):
            for url in urls:
                self.assertEqual(self.url_open(url).status_code, 404, url)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        delivery.write({"learning_tutor_id": self.internal.id})
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(urls[0]).status_code, 200)
        enrollment.action_revoke_access(reason="Fictional revoke")
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        self.authenticate(None, None)
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)

    def test_active_file_content_is_downloaded_and_text_preview_is_private(self):
        _, activity, enrollment = self.setup_learning()
        payload = b'<html><script>alert("fictional")</script></html>'
        entry = self.post(enrollment, activity_id=activity.id, data=payload, filename="exercise.html")
        attachment = self.file(entry)
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(f"/web/content/{attachment.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("nosniff", response.headers["X-Content-Type-Options"])
        response = self.url_open(f"/mail/attachment/render_text/{attachment.id}?unique={attachment.checksum}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("sandbox", response.headers["Content-Security-Policy"])
        self.authenticate(self.peer.login, self.peer.login)
        response = self.url_open(f"/mail/attachment/render_text/{attachment.id}")
        self.assertEqual(response.status_code, 404)

    def test_native_message_rpc_rechecks_private_mission(self):
        delivery, activity, enrollment = self.setup_learning()
        entry = self.service()._post(
            enrollment.id,
            "submission",
            activity_id=activity.id,
            request_key=str(uuid4()),
            body="Fictional private RPC work",
        )
        delivery.write({"learning_tutor_id": self.internal.id})

        def rpc(method, args, limit=None):
            kwargs = {"fields": ["body"]}
            if method == "search_read":
                kwargs["limit"] = limit
            response = self.url_open(
                "/web/dataset/call_kw/mail.message/" + method,
                data=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "model": "mail.message",
                            "method": method,
                            "args": args,
                            "kwargs": kwargs,
                        },
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            return response.json()

        self.authenticate(self.internal.login, self.internal.login)
        domain = [("id", "=", entry.message_id.id)]
        for limit in (None, 1):
            result = rpc("search_read", [domain], limit=limit)
            self.assertIn("Fictional private RPC work", result["result"][0]["body"])
        delivery.write({"learning_tutor_id": self.portal_b.id})
        for limit in (None, 1):
            self.assertEqual(rpc("search_read", [domain], limit=limit)["result"], [])
        result = rpc("read", [entry.message_id.ids])
        self.assertIn("error", result)
        self.assertNotIn("Fictional private RPC work", json.dumps(result))
        for user in (self.coordinator, self.peer):
            self.authenticate(user.login, user.login)
            result = rpc("search_read", [domain])
            self.assertNotIn("Fictional private RPC work", json.dumps(result))

    def test_csrf_idempotent_upload_and_plain_text_escaping(self):
        _, activity, enrollment = self.setup_learning()
        self.authenticate(self.portal.login, self.portal.login)
        path = f"/my/trainings/{enrollment.id}/learning"
        response = self.url_open(path, data={"kind": "question", "body": "forged"})
        self.assertEqual(response.status_code, 400)
        key = str(uuid4())
        values = {
            "csrf_token": self.csrf_token(),
            "kind": "submission",
            "activity_id": activity.id,
            "request_key": key,
            "body": '<script>alert("private")</script>',
            "create_uid": self.portal_b.id,
        }
        for _ in range(2):
            response = self.url_open(
                path, data=values, files={"file": ("work.pdf", BytesIO(PDF), "application/pdf")}, allow_redirects=False
            )
            self.assertEqual(response.status_code, 303)
        entries = self.env["training.learning.entry"].search([("enrollment_id", "=", enrollment.id)])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries.create_uid, self.portal)
        response = self.url_open(f"/my/trainings/{enrollment.id}")
        self.assertNotIn('<script>alert("private")</script>', response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertEqual(entries.data.content, PDF)
