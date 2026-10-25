"""SEC01: native previews must not bypass exam or response confidentiality."""

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged

from .test_exam import ExamCase
from .test_feedback import FeedbackCase


@tagged("post_install", "-at_install")
class TestExamSecurity(ExamCase, HttpCase):
    def test_native_exam_export_keeps_scope_and_ordinary_survey_unchanged(self):
        _exam, question, _other_question = self.exam()
        audit = self.env["training.export.audit"].with_user(self.coordinator)
        prior = audit.search([])
        question.export_data(["id", "title"])
        created = audit.search([]) - prior
        self.assertEqual(len(created), 1)
        self.assertEqual(created.model_name, question._name)
        self.assertEqual(created.manifest["ids"], question.ids)
        ordinary = self.env["survey.survey"].with_user(self.coordinator).create({"title": "Ordinary survey"})
        ordinary.export_data(["title"])
        self.assertEqual(audit.search_count([]), len(prior) + 1)
        self.coordinator.sudo().active = False
        with self.assertRaises(AccessError):
            question.export_data(["id"])

    def test_exam_pdf_preview_current_coordinator_and_private_cache(self):
        exam, question, _choice = self.exam()
        attachment = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "private-exam.pdf",
                    "raw": self.program.pdf_attachment_id.raw.content,
                    "res_model": question._name,
                    "res_id": question.id,
                }
            )
        )
        url = f"/mail/attachment/pdf_first_page/{attachment.id}?access_token={attachment._get_ownership_token()}"
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(self.coordinator.login, self.coordinator.login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        mail = self.env["mail.mail"].create(
            {
                "subject": "Fictional",
                "body_html": "<p>Fictional</p>",
                "email_to": "fictional@example.invalid",
                "attachment_ids": [Command.link(attachment.id)],
            }
        )
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()
        self.coordinator.sudo().active = False
        policy = self.env["training.document.policy"].with_user(self.coordinator)
        self.assertFalse(policy._can_read(attachment.sudo()))
        self.authenticate(None, None)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.assertTrue(exam.exists())


@tagged("post_install", "-at_install")
class TestFeedbackSecurity(FeedbackCase, HttpCase):
    def test_response_pdf_ownership_token_is_never_a_grant(self):
        campaign, users, question = self.campaign()
        self.submit(campaign, users[0], question)
        answer = self.env["survey.user_input"].search([("training_feedback_campaign_id", "=", campaign.id)])
        # A legacy response attachment must remain private, even under native
        # ownership tokens and even for a coordinator who manages its campaign.
        attachment = self.env["ir.attachment"].create(
            {
                "name": "private-response.pdf",
                "raw": self.program.pdf_attachment_id.raw.content,
            }
        )
        # Current ORM guards forbid new response attachments. Reproduce a
        # pre-existing row without weakening those guards, in this rolled-back
        # fictional fixture only.
        self.env.cr.execute(
            "UPDATE ir_attachment SET res_model=%s, res_id=%s WHERE id=%s",
            (answer._name, answer.id, attachment.id),
        )
        attachment.invalidate_recordset(["res_model", "res_id"])
        url = f"/mail/attachment/pdf_first_page/{attachment.id}?access_token={attachment._get_ownership_token()}"
        for user in (self.coordinator, users[0]):
            self.authenticate(user.login, user.login)
            self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(None, None)
        self.assertEqual(self.url_open(url).status_code, 404)
