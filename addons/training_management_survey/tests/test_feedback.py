"""EVA02: separation proof and functional/security regression tests."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged
from lxml import html
from odoo.addons.training_management.tests.test_evaluation import EvaluationCase


class FeedbackCase(EvaluationCase):
    def campaign(self, anonymous=True, purpose="immediate", recipients=3):
        delivery = self.delivery()
        definition = (
            self.env["training.feedback"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional feedback",
                    "program_id": self.program.id,
                    "purpose": purpose,
                    "anonymous": anonymous,
                    "criteria": "One mandatory choice",
                    "version": "1",
                }
            )
        )
        survey = (
            self.env["survey.survey"].with_user(self.coordinator).browse(definition.action_questionnaire()["res_id"])
        )
        question = (
            self.env["survey.question"]
            .with_user(self.coordinator)
            .create(
                {
                    "survey_id": survey.id,
                    "title": "Useful?",
                    "question_type": "simple_choice",
                    "constr_mandatory": True,
                    "suggested_answer_ids": [Command.create({"value": "Yes"}), Command.create({"value": "No"})],
                }
            )
        )
        definition.write(
            {
                "indicator_question_id": question.id,
                "favorable_answer_ids": [Command.set(question.suggested_answer_ids[:1].ids)],
            }
        )
        definition.action_publish()
        campaign = (
            self.env["training.feedback.campaign"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional feedback campaign",
                    "delivery_id": delivery.id,
                    "feedback_id": definition.id,
                    "population": "Confirmed fictional participants",
                    "retention_id": self.retention.id,
                    "opens_at": fields.Datetime.now() - timedelta(hours=1),
                    "due_at": fields.Datetime.now() + timedelta(days=2),
                }
            )
        )
        users = self.env["res.users"]
        for index in range(recipients):
            user = new_test_user(
                self.env,
                login=f"feedback_{campaign.id}_{index}",
                groups="base.group_portal",
                email=f"fictional{index}@example.invalid",
            )
            users |= user
            enrollment = self.enrollment(delivery, participant_id=user.partner_id.id, user_id=user.id)
            enrollment.action_validate_prerequisites(reason="Fictional eligibility")
            enrollment.action_confirm()
            self.env["training.feedback.recipient"].with_user(self.coordinator).create(
                {
                    "campaign_id": campaign.id,
                    "user_id": user.id,
                    "role": "participant",
                    "enrollment_id": enrollment.id,
                }
            )
        campaign.action_open()
        return campaign, users, question

    def submit(self, campaign, user, question, choice=0):
        return (
            self.env["training.feedback.service"]
            .with_user(user)
            ._submit(campaign.id, "participant", {question.id: question.suggested_answer_ids[choice].ids})
        )


@tagged("post_install", "-at_install")
class TestFeedback(FeedbackCase):
    def test_anonymous_separation_proof_and_three_threshold(self):
        campaign, users, question = self.campaign()
        invitation_before = campaign.recipient_ids.read(["user_id", "write_date", "response_state"])
        self.submit(campaign, users[0], question)
        self.submit(campaign, users[0], question)  # double POST: no second response
        self.assertEqual(
            self.env["survey.user_input"].search_count([("training_feedback_campaign_id", "=", campaign.id)]), 1
        )
        self.assertEqual(campaign.recipient_ids.read(["user_id", "write_date", "response_state"]), invitation_before)
        attempts = self.env["survey.user_input"].search([("training_feedback_campaign_id", "=", campaign.id)])
        for field in (
            "partner_id",
            "email",
            "nickname",
            "invite_token",
            "training_feedback_recipient_id",
            "training_enrollment_id",
            "start_datetime",
            "end_datetime",
        ):
            self.assertFalse(attempts[field], field)
        self.assertEqual(attempts.create_uid.id, 1)
        self.assertEqual(attempts.create_date, campaign.opens_at)
        self.assertEqual(attempts.write_date, campaign.opens_at)
        self.assertEqual(attempts.user_input_line_ids.create_uid.id, 1)
        self.assertEqual(attempts.user_input_line_ids.create_date, campaign.opens_at)
        self.assertEqual(attempts.user_input_line_ids.write_date, campaign.opens_at)
        self.assertFalse(
            self.env["mail.message"].search([("model", "=", "survey.user_input"), ("res_id", "=", attempts.id)])
        )
        for user in (self.coordinator, self.quality, self.supervisor, users[0]):
            for model in ("survey.user_input", "survey.user_input.line"):
                record = attempts if model == "survey.user_input" else attempts.user_input_line_ids
                try:
                    visible = self.env[model].with_user(user).search([("id", "in", record.ids)])
                    self.assertFalse(visible)
                except AccessError:
                    self.assertFalse(record.with_user(user).has_access("read"))
                with self.assertRaises(AccessError):
                    record.with_user(user).read()
            with self.assertRaises(AccessError):
                self.env["training.feedback.spent"].with_user(user).search([])
        self.submit(campaign, users[1], question)
        self.assertEqual(self.env["training.feedback.service"]._build_snapshot(campaign), {"insufficient": True})
        self.submit(campaign, users[2], question)
        campaign.action_close()
        self.assertEqual(campaign.snapshot["received"], 3)
        self.assertEqual(campaign.snapshot["rate"], 100)  # homogeneous responses: no extra control
        self.assertFalse(campaign.snapshot.get("insufficient"))

    def test_two_closed_no_restitution_and_deadline(self):
        campaign, users, question = self.campaign()
        for user in users[:2]:
            self.submit(campaign, user, question)
        campaign.action_close()
        self.assertEqual(campaign.snapshot, {"insufficient": True})
        with self.assertRaises(ValidationError):
            self.submit(campaign, users[2], question)
        self.assertIn("Insufficient", campaign.summary)

    def test_nominative_states_and_version_freeze(self):
        campaign, users, question = self.campaign(anonymous=False)
        self.assertEqual(campaign.recipient_ids[0].response_state, "not_invited")
        campaign.action_invite()
        campaign.recipient_ids.invalidate_recordset()
        self.assertEqual(campaign.recipient_ids[0].response_state, "queued")
        self.submit(campaign, users[0], question, choice=1)
        campaign.recipient_ids.invalidate_recordset()
        self.assertEqual(campaign.recipient_ids[0].response_state, "received")
        campaign.action_close()
        self.assertEqual(campaign.snapshot["received"], 1)
        self.assertEqual(campaign.snapshot["rate"], 0)
        with self.assertRaises(ValidationError):
            campaign.feedback_id.write({"anonymous": True})
        with self.assertRaises(ValidationError):
            question.write({"title": "Changed"})

    def test_collective_reminders_idempotence_and_transport_revocation(self):
        campaign, users, question = self.campaign()
        campaign.action_invite()
        campaign.action_invite()
        self.assertEqual(len(campaign.notice_ids), 3)
        self.submit(campaign, users[0], question)
        campaign.action_remind()
        campaign.action_remind()
        self.assertEqual(len(campaign.notice_ids), 6)  # includes the respondent
        notice = campaign.notice_ids.filtered(lambda n: n.recipient_id.user_id == users[0])[:1]
        outgoing = notice.mail_id
        self.assertTrue(notice._authorized())
        notice.recipient_id.write({"active": False, "exclusion_reason": "Fictional withdrawal"})
        with self.assertRaises(ValidationError):
            outgoing._prepare_outgoing_list()
        with self.assertRaises(AccessError):
            self.submit(campaign, users[0], question)
        campaign.action_remind()
        self.assertEqual(len(campaign.notice_ids), 6)

    def test_partial_nominative_and_invalid_submission_atomicity(self):
        campaign, users, question = self.campaign(anonymous=False)
        service = self.env["training.feedback.service"].with_user(users[0])
        service._submit(campaign.id, "participant", {}, submit=False)
        campaign.recipient_ids.invalidate_recordset()
        self.assertEqual(campaign.recipient_ids[0].response_state, "in_progress")
        self.assertEqual(self.env["training.feedback.service"]._build_snapshot(campaign)["received"], 0)
        with self.assertRaises(ValidationError):
            service._submit(campaign.id, "participant", {})
        self.submit(campaign, users[0], question)
        values, done = service._own_answers(campaign)
        self.assertTrue(done)
        self.assertEqual(values["q_%s" % question.id], [str(question.suggested_answer_ids[0].id)])
        self.assertEqual(
            len(self.env["survey.user_input"].search([("training_feedback_campaign_id", "=", campaign.id)])), 1
        )
        anonymous, anonymous_users, anonymous_question = self.campaign()
        with self.assertRaises(ValidationError):
            self.env["training.feedback.service"].with_user(anonymous_users[0])._submit(anonymous.id, "participant", {})
        self.assertFalse(self.env["training.feedback.spent"].search([("campaign_id", "=", anonymous.id)]))
        self.assertFalse(self.env["survey.user_input"].search([("training_feedback_campaign_id", "=", anonymous.id)]))
        self.submit(anonymous, anonymous_users[0], anonymous_question)

    def test_scoped_summary_revocation_foreign_company_and_forgery(self):
        campaign, users, question = self.campaign()
        campaign.delivery_id.write({"evaluation_supervisor_ids": [Command.set(self.supervisor.ids)]})
        service = self.env["training.feedback.service"].with_user(self.supervisor)
        self.assertEqual(service._campaign(campaign.id, staff=True).id, campaign.id)
        self.assertIn("after closure", service._summary_text(campaign))
        for user in (self.internal, self.portal, users[0]):
            with self.assertRaises(AccessError):
                self.env["training.feedback.service"].with_user(user)._campaign(campaign.id, staff=True)
        with self.assertRaises(AccessError):
            self.env["training.feedback.service"].with_user(self.portal)._submit(campaign.id, "participant", {})
        with self.assertRaises(ValidationError):
            self.env["training.feedback.service"].with_user(users[0])._submit(
                campaign.id, "participant", {question.id: [999999]}
            )
        campaign.delivery_id.write({"evaluation_supervisor_ids": [Command.clear()]})
        with self.assertRaises(AccessError):
            service._campaign(campaign.id, staff=True)
        foreign = new_test_user(
            self.env,
            login="feedback_foreign",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        with self.assertRaises(AccessError):
            self.env["training.feedback.service"].with_user(foreign)._campaign(campaign.id, staff=True)
        self.assertFalse(self.env["training.feedback.campaign"].with_user(foreign).search([("id", "=", campaign.id)]))

    def test_reopening_preserves_snapshot_and_versions(self):
        campaign, users, question = self.campaign()
        for user in users:
            self.submit(campaign, user, question)
        campaign.action_close()
        snapshot = dict(campaign.snapshot)
        original_due = campaign.due_at
        with self.assertRaises(ValidationError):
            campaign.write({"due_at": fields.Datetime.now() + timedelta(days=4)})
        action = campaign.action_new_collection()
        new = self.env["training.feedback.campaign"].with_user(self.coordinator).browse(action["res_id"])
        self.assertEqual(new.state, "draft")
        self.assertEqual(new.previous_id, campaign)
        self.assertFalse(new.snapshot)
        self.assertEqual(campaign.snapshot, snapshot)
        self.assertEqual(campaign.due_at, original_due)
        version = campaign.feedback_id.action_new_version()
        definition = self.env["training.feedback"].browse(version["res_id"])
        self.assertNotEqual(definition.survey_id, campaign.feedback_id.survey_id)
        self.assertEqual(definition.previous_id, campaign.feedback_id)

    def test_anonymous_ledger_unordered_and_no_native_metadata_counts(self):
        campaign, users, question = self.campaign()
        for user in reversed(users):
            self.submit(campaign, user, question)
        pool = self.env["training.feedback.spent"].search([("campaign_id", "=", campaign.id)])
        self.assertEqual(len(pool), 1)
        self.assertEqual(pool.digests, sorted(pool.digests))
        self.assertFalse(pool._log_access)
        self.assertNotIn("recipient_id", pool._fields)
        self.assertNotIn("answer_id", pool._fields)
        survey = campaign.feedback_id.survey_id.with_user(self.coordinator)
        self.assertEqual(survey.answer_count, 0)
        self.assertEqual(survey.answer_done_count, 0)
        self.assertFalse(survey.user_input_ids)
        self.assertFalse(
            self.env["survey.user_input"]
            .with_user(self.coordinator)
            ._read_group([("survey_id", "=", survey.id)], [], ["__count"])[0][0]
        )

    def test_instructor_and_sponsor_own_population_and_revocation(self):
        campaign, _users, question = self.campaign(anonymous=False)
        for purpose in ("instructor", "sponsor"):
            definition = (
                self.env["training.feedback"]
                .with_user(self.coordinator)
                .browse(campaign.feedback_id.action_new_version()["res_id"])
            )
            definition.write({"purpose": purpose})
            definition.action_publish()
            campaign.delivery_id.write({"evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)]})
            staff_campaign = (
                self.env["training.feedback.campaign"]
                .with_user(self.coordinator)
                .create(
                    {
                        "name": purpose,
                        "feedback_id": definition.id,
                        "delivery_id": campaign.delivery_id.id,
                        "population": "Explicit fictional role",
                        "retention_id": self.retention.id,
                        "opens_at": campaign.opens_at,
                        "due_at": campaign.due_at,
                        "recipient_ids": [Command.create({"user_id": self.portal_b.id, "role": purpose})],
                    }
                )
            )
            staff_campaign.action_open()
            q = definition.survey_id.question_ids[0]
            self.env["training.feedback.service"].with_user(self.portal_b)._submit(
                staff_campaign.id, purpose, {q.id: q.suggested_answer_ids[:1].ids}
            )
            staff_campaign.action_close()
            self.assertEqual(staff_campaign.snapshot["received"], 1)
            self.assertEqual(staff_campaign.snapshot["expected"], 1)
            self.assertFalse(staff_campaign.recipient_ids.enrollment_id)

    def test_anonymous_identifying_questions_and_deadline(self):
        campaign, users, question = self.campaign()
        definition = (
            self.env["training.feedback"]
            .with_user(self.coordinator)
            .browse(campaign.feedback_id.action_new_version()["res_id"])
        )
        q = definition.survey_id.question_ids[0]
        q.write({"question_type": "char_box", "save_as_email": True})
        with self.assertRaises(ValidationError):
            definition.action_publish()
        from unittest.mock import patch

        with patch("odoo.fields.Datetime.now", return_value=campaign.due_at + timedelta(seconds=1)):
            with self.assertRaises(ValidationError):
                self.submit(campaign, users[0], question)

    def test_s08_real_pdf_idempotence_and_client_exclusion(self):
        campaign, users, question = self.campaign()
        for user in users:
            self.submit(campaign, user, question)
        campaign.action_close()
        dossier = self.dossier(campaign.recipient_ids[0].enrollment_id)
        wizard = (
            self.env["training.feedback.export"]
            .with_user(self.coordinator)
            .create({"campaign_id": campaign.id, "dossier_id": dossier.id})
        )
        action = wizard.action_export()
        proof = self.env["training.proof"].browse(action["res_id"])
        self.assertTrue(proof.data.content.startswith(b"%PDF-"))
        self.assertEqual(proof.category, "feedback")
        self.assertFalse(proof.client_shared)
        rendered = self.env["ir.actions.report"]._render_template(
            "training_management.feedback_document",
            self.env["report.training_management.feedback_document"]
            .with_user(self.coordinator)
            ._get_report_values(campaign.ids),
        )
        self.assertIn(question.title, rendered.decode())
        self.assertEqual(wizard.action_export()["res_id"], proof.id)
        self.validate(proof)
        pdf_before = proof.data.content
        campaign.action_new_collection()
        self.assertEqual(proof.data.content, pdf_before)
        with self.assertRaises(ValidationError):
            self.env["training.feedback.export"].with_user(self.coordinator).create(
                {"campaign_id": campaign.id, "dossier_id": self.dossier().id}
            ).action_export()

    def test_scheduled_invitation_zero_reminders_and_transport_retry(self):
        campaign, users, question = self.campaign(anonymous=False)
        # Include campaigns with reminders disabled in scheduled invitations.
        campaign._store({"reminder_days": 0})
        self.env["training.feedback.campaign"]._cron_remind()
        self.assertEqual(len(campaign.notice_ids), 3)
        self.env["training.feedback.campaign"]._cron_remind()
        self.assertEqual(len(campaign.notice_ids), 3)
        notice = campaign.notice_ids[0]
        notice.mail_id.sudo().write({"state": "exception"})
        campaign.action_invite()
        self.assertEqual(notice.mail_id.sudo().state, "outgoing")
        self.assertEqual(len(campaign.notice_ids), 3)
        notice.mail_id.sudo().write({"state": "sent"})
        campaign.recipient_ids.invalidate_recordset()
        self.assertEqual(notice.recipient_id.response_state, "invited")

    def test_feedback_answer_exports_and_binary_are_blocked(self):
        campaign, users, question = self.campaign()
        self.submit(campaign, users[0], question)
        attempt = self.env["survey.user_input"].search([("training_feedback_campaign_id", "=", campaign.id)])
        for record in (attempt, attempt.user_input_line_ids):
            with self.assertRaises(AccessError):
                record.with_user(self.coordinator).export_data(["id"])
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(self.coordinator)._check_training_binary_access(record)


@tagged("post_install", "-at_install")
class TestFeedbackHTTP(FeedbackCase, HttpCase):
    def test_anonymous_http_form_csrf_and_native_token_boundary(self):
        campaign, users, question = self.campaign()
        user = users[0]
        self.authenticate(user.login, user.login)
        url = "/my/training-feedback/%s" % campaign.id
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Anonymous collection", response.text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        tree = html.fromstring(response.content)
        token = tree.xpath('//input[@name="csrf_token"]/@value')[0]
        self.assertFalse(tree.xpath('//button[@value="save"]'))
        self.assertEqual(self.url_open(url, data={"q_%s" % question.id: "1"}).status_code, 400)
        response = self.url_open(url, data={"csrf_token": token})
        self.assertIn("Complete the required answers", response.text)
        self.assertTrue(html.fromstring(response.content).xpath('//*[@id="feedback-message"][@tabindex="-1"]'))
        response = self.url_open(
            url, data={"csrf_token": token, "q_%s" % question.id: str(question.suggested_answer_ids[0].id)}
        )
        self.assertIn("Thank you", response.text)
        attempt = self.env["survey.user_input"].search([("training_feedback_campaign_id", "=", campaign.id)])
        survey = campaign.feedback_id.survey_id
        for path in (
            "/survey/start/%s/%s" % (survey.access_token, attempt.access_token),
            "/survey/print/%s" % survey.access_token,
        ):
            self.assertEqual(self.url_open(path).status_code, 404)
        # Reload never reveals whether this invitation has submitted a response.
        self.assertIn("Submit feedback", self.url_open(url).text)
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(url).status_code, 404)

    def test_nominative_draft_resume_escape_and_scoped_summary(self):
        campaign, users, question = self.campaign(anonymous=False)
        self.authenticate(users[0].login, users[0].login)
        url = "/my/training-feedback/%s" % campaign.id
        response = self.url_open(url)
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "save",
                "q_%s" % question.id: str(question.suggested_answer_ids[1].id),
            },
        )
        self.assertIn("draft has been saved", response.text)
        response = self.url_open(url)
        self.assertTrue(
            html.fromstring(response.content).xpath(
                '//input[@value="%s"][@checked]' % question.suggested_answer_ids[1].id
            )
        )
        self.assertEqual(self.url_open(url + "/summary").status_code, 404)
        campaign.delivery_id.write({"evaluation_supervisor_ids": [Command.set(self.supervisor.ids)]})
        self.authenticate(self.supervisor.login, self.supervisor.login)
        self.assertIn("after closure", self.url_open(url + "/summary").text)
        campaign.action_close()
        response = self.url_open(url + "/summary")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Received: 0", response.text)
        campaign.delivery_id.write({"evaluation_supervisor_ids": [Command.clear()]})
        self.assertEqual(self.url_open(url + "/summary").status_code, 404)
