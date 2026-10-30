"""EXA01–06 / P07–08: native models, real grants and retained originals."""

from datetime import timedelta
from io import BytesIO
from PIL import Image
from odoo.tools.binary import BinaryBytes
from unittest.mock import patch
import json
import re

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tests import tagged, HttpCase, new_test_user, Form
from odoo.tools.misc import limited_field_access_token
from odoo.tools.translate import load_language
from odoo.addons.training_management.tests.test_material import MaterialCase


class ExamCase(MaterialCase):
    def exam(self, with_image=False, **values):
        exam = (
            self.env["survey.survey"]
            .with_user(self.coordinator)
            .create(
                {
                    "title": "Fictional mock exam",
                    "training_program_id": self.program.id,
                    "survey_type": "custom",
                    "scoring_type": "scoring_with_answers",
                    "time_limit": 60,
                    "scoring_success_min": 75,
                    **values,
                }
            )
        )
        q1 = (
            self.env["survey.question"]
            .with_user(self.coordinator)
            .create(
                {
                    "survey_id": exam.id,
                    "title": "Fixed QCU",
                    "question_type": "simple_choice",
                    "sequence": 10,
                    "answer_score": 18,
                    "training_theme": "Basics",
                    "training_explanation": "PRIVATE FINAL EXPLANATION",
                    "suggested_answer_ids": [
                        Command.create({"value": "Expected A", "is_correct": True, "answer_score": 18}),
                        Command.create({"value": "Wrong B", "is_correct": False}),
                    ],
                }
            )
        )
        q2 = (
            self.env["survey.question"]
            .with_user(self.coordinator)
            .create(
                {
                    "survey_id": exam.id,
                    "title": "Fixed QCM",
                    "question_type": "multiple_choice",
                    "sequence": 20,
                    "answer_score": 6,
                    "training_theme": "Advanced",
                    "suggested_answer_ids": [
                        Command.create({"value": "Expected C", "is_correct": True, "answer_score": 3}),
                        Command.create({"value": "Expected D", "is_correct": True, "answer_score": 3}),
                        Command.create({"value": "Wrong E", "is_correct": False}),
                    ],
                }
            )
        )
        if with_image:
            image = BytesIO()
            Image.new("RGB", (8, 8), "blue").save(image, "PNG")
            q2.suggested_answer_ids[:1].write(
                {"value_image": BinaryBytes(image.getvalue()), "value_image_filename": "fictional.png"}
            )
        return exam, q1, q2

    def published(self, **values):
        exam, q1, q2 = self.exam(**values)
        exam.action_training_publish()
        delivery = self.delivery()
        activity = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Exam",
                    "delivery_id": delivery.id,
                    "criterion": "evaluation",
                    "evaluation_threshold": 75,
                    "training_exam_id": exam.id,
                }
            )
        )
        enrollment = self.opened(delivery)
        service = self.env["training.exam.service"].with_user(self.portal)
        return exam, q1, q2, activity, enrollment, service


@tagged("post_install", "-at_install")
class TestMockExam(ExamCase):
    def test_legacy_public_exam_attachment_cannot_bypass_parent_access(self):
        exam, q1, q2 = self.exam()
        attachment = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create({"name": "Private exam file", "raw": b"PRIVATE EXAM FILE", "res_model": q1._name, "res_id": q1.id})
        )
        # Simulate an existing pre-review file. Public create/write now rejects
        # these flags; the test must still exercise native legacy token paths.
        attachment.flush_recordset()
        self.env.cr.execute(
            "UPDATE ir_attachment SET public = TRUE, access_token = %s WHERE id = %s",
            ["fictional-legacy-token", attachment.id],
        )
        attachment.invalidate_recordset()
        other_coord = new_test_user(
            self.env,
            login="s06_file_other_company",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        for user in (self.portal, self.portal_b, self.reader, other_coord):
            private_file = attachment.with_user(user)
            self.assertFalse(private_file.search([("id", "=", attachment.id)]))
            with self.assertRaises(AccessError):
                private_file.read(["raw"])
            with self.assertRaises((AccessError, UserError)):
                private_file.export_data(["name", "raw"])
            with self.assertRaises(AccessError):
                private_file.sudo()._can_return_content(access_token="fictional-legacy-token")
        self.assertTrue(attachment.read(["raw"]))
        self.assertEqual(attachment.raw.content, b"PRIVATE EXAM FILE")

    def test_generic_certification_report_rejects_mock_exam_attempts(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._submit(attempt.id)
        reports = self.env["ir.actions.report"].with_user(self.coordinator)
        with self.assertRaises(AccessError):
            reports._render_qweb_html("survey.certification_report", [attempt.id])
        ordinary = self.env["survey.survey"].with_user(self.coordinator).create({"title": "Ordinary certification"})
        answer = ordinary._create_answer(partner=self.portal.partner_id)
        html, _ = reports._render_qweb_html("survey.certification_report", [answer.id])
        self.assertIn(b"Ordinary certification", html)

    def test_native_exam_attachments_cannot_be_published_or_detached(self):
        exam, q1, q2 = self.exam(with_image=True)
        choice = q2.suggested_answer_ids[:1]
        files = self.env["ir.attachment"].with_user(self.coordinator)
        attachment = files.create(
            {
                "name": "Private question image",
                "raw": choice.value_image.content,
                "res_model": q2._name,
                "res_id": q2.id,
            }
        )
        self.assertTrue(attachment)
        for values in ({"public": True}, {"access_token": "fictional-token"}, {"res_model": False, "res_id": False}):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                attachment.write(values)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            files.create(
                {
                    "name": "Private exam image",
                    "raw": b"private",
                    "res_model": exam._name,
                    "res_id": exam.id,
                    "public": True,
                }
            )
        with self.assertRaises(AccessError):
            attachment.with_user(self.portal_b).read(["raw"])
        with self.assertRaises(AccessError):
            attachment.with_user(self.portal_b).sudo()._to_http_stream()
        for user in (self.portal, self.reader):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                files.with_user(user).create(
                    {"name": "Forged exam file", "raw": b"private", "res_model": q2._name, "res_id": q2.id}
                )
        with self.assertRaises(ValidationError):
            attachment.copy({"res_model": False, "res_id": False, "public": True})
        attachment.write({"raw": b"New draft content"})
        ordinary = self.env["survey.survey"].with_user(self.coordinator).create({"title": "Ordinary attachment"})
        ordinary_file = files.create(
            {
                "name": "Ordinary file",
                "raw": b"ordinary",
                "public": True,
                "res_model": ordinary._name,
                "res_id": ordinary.id,
            }
        )
        ordinary_file.write({"raw": b"changed"})
        self.assertTrue(ordinary_file.copy())
        ordinary_file.unlink()

    def test_published_images_are_immutable_through_native_attachments(self):
        exam, q1, q2 = self.exam(with_image=True)
        choice = q2.suggested_answer_ids[:1]
        attachment = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Private question image",
                    "raw": choice.value_image.content,
                    "res_model": q2._name,
                    "res_id": q2.id,
                }
            )
        )
        self.assertTrue(attachment)
        original = choice.value_image.content
        exam.action_training_publish()
        for values in ({"raw": b"changed"}, {"res_id": q1.suggested_answer_ids[:1].id}):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                attachment.write(values)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            attachment.unlink()
        self.assertEqual(choice.value_image.content, original)

    def test_native_editor_models_and_publish_validation(self):
        exam, q1, q2 = self.exam(time_limit=0)
        with self.assertRaises(ValidationError):
            exam.action_training_publish()
        exam.time_limit = 60
        q2.answer_score = 0
        with self.assertRaises(ValidationError):
            exam.action_training_publish()
        q2.answer_score = 6
        q2.suggested_answer_ids.is_correct = False
        with self.assertRaises(ValidationError):
            exam.action_training_publish()
        q2.suggested_answer_ids[:2].is_correct = True
        exam.action_training_publish()
        self.assertFalse(exam.certification)
        self.assertFalse(exam.is_attempts_limited)
        self.assertEqual(exam.questions_selection, "all")
        self.assertEqual(exam._name, "survey.survey")
        for record, vals in [
            (exam, {"time_limit": 120}),
            (q1, {"title": "Changed"}),
            (q2.suggested_answer_ids[:1], {"is_correct": False}),
        ]:
            with self.assertRaises(ValidationError):
                record.write(vals)
            with self.assertRaises(ValidationError):
                record.unlink()

    def test_18_of_24_inclusive_threshold_exact_qcm_and_native_storage(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, False)
        service._save(attempt.id, q2.id, q2.suggested_answer_ids.ids, False)
        self.assertEqual(attempt._name, "survey.user_input")
        self.assertEqual(attempt.scoring_total, 18)
        self.assertEqual(attempt.scoring_percentage, 75)
        with self.assertRaises(AccessError):
            service._result(attempt)
        service._submit(attempt.id)
        result = service._result(attempt)
        self.assertTrue(result["success"])
        self.assertEqual(result["points"], 18)
        self.assertEqual(sum(t["points"] for t in result["themes"].values()), 18)
        self.assertTrue(self.env["training.learning.service"].with_user(self.portal)._complete(enrollment, activity))
        self.assertEqual(result["questions"][0]["explanation"], "PRIVATE FINAL EXPLANATION")

    def test_qcm_partial_empty_and_exact_are_zero_zero_full(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        for choices, expected in [(q2.suggested_answer_ids[:1].ids, 0), ([], 0), (q2.suggested_answer_ids[:2].ids, 6)]:
            attempt = service._start(enrollment.id, activity.id)
            service._save(attempt.id, q2.id, choices, False)
            service._submit(attempt.id)
            self.assertEqual(attempt.scoring_total, expected)

    def test_retake_twice_after_100_percent_preserves_every_result(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempts = []
        for _ in range(2):
            attempt = service._start(enrollment.id, activity.id)
            self.assertEqual(service._start(enrollment.id, activity.id), attempt)
            for q in (q1, q2):
                service._save(attempt.id, q.id, q.suggested_answer_ids.filtered("is_correct").ids, False)
            self.assertEqual(service._submit(attempt.id), {"done": True})
            self.assertEqual(service._submit(attempt.id), {"done": True})
            self.assertEqual(attempt.scoring_percentage, 100)
            attempts.append(attempt)
        self.assertNotEqual(attempts[0], attempts[1])
        self.assertEqual(attempts[0].scoring_percentage, 100)
        self.assertEqual(len(attempts[0].user_input_line_ids), 3)
        self.assertFalse(
            self.env["mail.mail"]
            .sudo()
            .search([("model", "=", "survey.user_input"), ("res_id", "in", [a.id for a in attempts])])
        )

    def test_native_timer_ten_minutes_reload_expiry_late_save_and_cron(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        start = fields.Datetime.now()
        with patch("odoo.fields.Datetime.now", return_value=start):
            attempt = service._start(enrollment.id, activity.id)
            service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, True)
        with patch("odoo.fields.Datetime.now", return_value=start + timedelta(minutes=10)):
            self.assertEqual(service._start(enrollment.id, activity.id), attempt)
            self.assertEqual(attempt.deadline - fields.Datetime.now(), timedelta(minutes=50))
            self.assertFalse(attempt.survey_time_limit_reached)
        with patch("odoo.fields.Datetime.now", return_value=start + timedelta(minutes=60)):
            self.assertEqual(service._save(attempt.id, q2.id, q2.suggested_answer_ids[:2].ids, False), {"done": True})
        self.assertEqual(attempt.state, "done")
        self.assertEqual(attempt.scoring_total, 18)
        self.assertEqual(attempt.end_datetime, attempt.deadline)
        second = service._start(enrollment.id, activity.id)
        with patch("odoo.fields.Datetime.now", return_value=second.deadline):
            self.env["survey.user_input"]._cron_training_expire()
        self.assertEqual(second.state, "done")

    def test_revision_version_history_and_theme_totals(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, True)
        service._submit(attempt.id)
        action = exam.action_training_new_version()
        v2 = self.env["survey.survey"].with_user(self.coordinator).browse(action["res_id"])
        v2.write({"training_version": "2", "training_revision_reason": "Corrected wording", "time_limit": 30})
        v2.question_ids[:1].write({"title": "New wording", "answer_score": 2, "training_theme": "New theme"})
        v2.action_training_publish()
        self.assertEqual(attempt.predefined_question_ids[:1].title, "Fixed QCU")
        self.assertEqual(attempt.scoring_percentage, 75)
        revision = (
            self.env["training.exam.revision"]
            .with_user(self.coordinator)
            ._record(
                attempt.with_user(self.coordinator),
                {str(q1.id): 18, str(q2.id): 6},
                "Accepted ambiguous option",
            )
        )
        self.assertEqual(service._result(attempt)["percentage"], 100)
        self.assertEqual(attempt.scoring_percentage, 75)
        self.assertEqual(sum(t["points"] for t in service._result(attempt)["themes"].values()), 24)
        with self.assertRaises(AccessError):
            revision.write({"reason": "Replaced"})
        with self.assertRaises(ValidationError):
            self.env["training.exam.revision"].with_user(self.coordinator)._record(
                attempt.with_user(self.coordinator),
                {str(q1.id): 25, str(q2.id): 6},
                "Invalid points",
            )

    def test_restricted_identity_native_rpc_exports_and_suspension(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, False)
        for user in (self.portal, self.portal_b, self.reader, self.internal):
            for record in (exam, q1, q2.suggested_answer_ids[:1], attempt, attempt.user_input_line_ids):
                with self.assertRaises(AccessError):
                    record.with_user(user).read()
                with self.assertRaises((AccessError, UserError)):
                    record.with_user(user).export_data(["id"])
        with self.assertRaises(AccessError):
            self.env["training.exam.service"].with_user(self.portal_b)._attempt(attempt.id)
        enrollment.action_suspend_access(reason="Fictional suspension")
        with self.assertRaises(AccessError):
            service._save(attempt.id, q1.id, [], False)
        with self.assertRaises(AccessError):
            service._attempt(attempt.id)

    def test_wrong_question_forged_choices_native_creation_and_finished_edits(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        with self.assertRaises(ValidationError):
            service._save(attempt.id, q1.id, q2.suggested_answer_ids[:1].ids, False)
        with self.assertRaises(ValidationError):
            service._save(attempt.id, q1.id, q1.suggested_answer_ids.ids, False)
        with self.assertRaises(AccessError):
            exam._create_answer(partner=self.portal.partner_id)
        service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, True)
        service._submit(attempt.id)
        for record, vals in [(attempt, {"state": "in_progress"}), (attempt.user_input_line_ids, {"skipped": True})]:
            with self.assertRaises(AccessError):
                record.with_user(self.coordinator).write(vals)
        with self.assertRaises(AccessError):
            self.env["survey.user_input"].with_user(self.coordinator).create({"survey_id": exam.id})

    def test_expired_access_retains_results_but_forbids_retake(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._submit(attempt.id)
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_end + timedelta(seconds=1)):
            self.assertEqual(service._attempt(attempt.id), attempt)
            with self.assertRaises(AccessError):
                service._start(enrollment.id, activity.id)

    def test_native_survey_role_and_other_company_cannot_read_private_exams(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, False)
        officer = new_test_user(
            self.env, login="s06_native_manager", groups="survey.group_survey_manager,base.group_user"
        )
        other_coord = new_test_user(
            self.env,
            login="s06_other_company",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        for user in (officer, other_coord):
            for record in (exam, q1, q2.suggested_answer_ids[:1], attempt, attempt.user_input_line_ids):
                self.assertFalse(record.with_user(user).search([("id", "in", record.ids)]))
                with self.assertRaises(AccessError):
                    record.with_user(user).read()
        # Ordinary surveys still use native Survey roles, not training grants.
        ordinary = self.env["survey.survey"].with_user(officer).create({"title": "Ordinary officer survey"})
        self.assertTrue(ordinary.exists())
        with self.assertRaises(AccessError):
            ordinary.write({"training_origin_id": exam.id})
        with self.assertRaises(AccessError):
            self.env["survey.user_input"].with_user(officer).with_context(
                default_training_family_id=exam.id,
            ).create({"survey_id": ordinary.id})
        self.assertFalse(ordinary.copy().training_program_id)

    def test_native_revision_wizard_preserves_original_and_rejects_forgery(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._submit(attempt.id)
        with Form(
            self.env["training.exam.revise"]
            .with_user(self.coordinator)
            .with_context(
                active_model="survey.user_input",
                active_id=attempt.id,
            )
        ) as form:
            form.reason = "Fictional administrative review"
            with form.line_ids.edit(0) as line:
                line.points = 18
        form.record.action_apply()
        self.assertEqual(attempt.scoring_total, 0)
        self.assertEqual(service._result(attempt)["points"], 18)
        with self.assertRaises(AccessError):
            self.env["training.exam.revision"].with_user(self.coordinator).create(
                {
                    "attempt_id": attempt.id,
                    "reason": "Forged",
                    "author_id": self.coordinator.id,
                    "points_by_question": {str(q1.id): 24},
                }
            )

    def test_empty_section_unclassified_and_hidden_revision_resource(self):
        exam, q1, q2 = self.exam()
        self.env["survey.question"].with_user(self.coordinator).create(
            {
                "survey_id": exam.id,
                "title": "Empty theme",
                "is_page": True,
                "sequence": 100,
            }
        )
        q1.training_theme = False
        private_material = self.material(delivery_id=self.delivery().id)
        q1.training_material_id = private_material
        exam.action_training_publish()
        delivery = self.delivery()
        activity = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Exam",
                    "delivery_id": delivery.id,
                    "criterion": "evaluation",
                    "training_exam_id": exam.id,
                }
            )
        )
        enrollment = self.opened(delivery)
        service = self.env["training.exam.service"].with_user(self.portal)
        attempt = service._start(enrollment.id, activity.id)
        service._submit(attempt.id)
        result = service._result(attempt)
        self.assertEqual(result["themes"]["Empty theme"]["maximum"], 0)
        self.assertIn("Unclassified", result["themes"])
        self.assertFalse(result["questions"][0]["url"])
        self.assertEqual(sum(t["maximum"] for t in result["themes"].values()), 24)
        exam.action_archive()
        with self.assertRaises(ValidationError):
            service._start(enrollment.id, activity.id)
        self.assertEqual(service._attempt(attempt.id), attempt)

    def test_access_expiry_allows_finishing_only_the_authorized_active_attempt(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        start = enrollment.access_end - timedelta(minutes=10)
        with patch("odoo.fields.Datetime.now", return_value=start):
            attempt = service._start(enrollment.id, activity.id)
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_end + timedelta(minutes=1)):
            self.assertEqual(enrollment._effective_state(), "expired")
            self.assertTrue(service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, False)["saved"])
            with self.assertRaises(AccessError):
                service._start(enrollment.id, activity.id)
            service._submit(attempt.id)
            self.assertEqual(service._result(attempt)["percentage"], 75)
            self.assertEqual(attempt.deadline, start + timedelta(minutes=60))
            enrollment.action_suspend_access(reason="Fictional suspension after expiry")
            with self.assertRaises(AccessError):
                service._attempt(attempt.id)
            with self.assertRaises(AccessError):
                service._submit(attempt.id)
        exam2, q3, q4, activity2, enrollment2, service2 = self.published()
        with patch("odoo.fields.Datetime.now", return_value=enrollment2.access_end - timedelta(minutes=10)):
            second = service2._start(enrollment2.id, activity2.id)
        with patch("odoo.fields.Datetime.now", return_value=enrollment2.access_end + timedelta(minutes=1)):
            enrollment2.action_revoke_access(reason="Fictional revocation after expiry")
            with self.assertRaises(AccessError):
                service2._save(second.id, q3.id, q3.suggested_answer_ids[:1].ids, False)

    def test_unrelated_native_survey_is_unaffected(self):
        survey = self.env["survey.survey"].create({"title": "Ordinary survey"})
        question = self.env["survey.question"].create(
            {"survey_id": survey.id, "title": "Ordinary free text", "question_type": "text_box"}
        )
        answer = survey._create_answer(partner=self.portal.partner_id)
        answer._mark_in_progress()
        answer._save_lines(question, "Ordinary response")
        answer._mark_done()
        question.title = "Standard remains editable"
        self.assertEqual(answer.state, "done")


@tagged("post_install", "-at_install")
class TestMockExamHttp(ExamCase, HttpCase):
    def test_image_only_native_choices_have_a_readable_private_correction(self):
        exam, q1, q2 = self.exam(with_image=True)
        choice = q2.suggested_answer_ids[:1]
        choice.value = False
        exam.action_training_publish()
        delivery = self.delivery()
        activity = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Image exam",
                    "delivery_id": delivery.id,
                    "criterion": "evaluation",
                    "training_exam_id": exam.id,
                }
            )
        )
        enrollment = self.opened(delivery)
        service = self.env["training.exam.service"].with_user(self.portal)
        attempt = service._start(enrollment.id, activity.id)
        service._save(attempt.id, q2.id, q2.suggested_answer_ids.filtered("is_correct").ids, False)
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(f"/my/training-exams/{attempt.id}").status_code, 200)
        service._submit(attempt.id)
        result = self.url_open(f"/my/training-exams/{attempt.id}")
        self.assertEqual(result.status_code, 200)
        self.assertIn(choice.value_label, result.text)
        image_url = f"/survey/get_question_image/{exam.access_token}/{attempt.access_token}/{q2.id}/{choice.id}"
        self.assertIn(image_url, result.text)
        self.assertEqual(self.url_open(image_url).content, choice.value_image.content)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(image_url).status_code, 404)

    def test_native_token_routes_cannot_bypass_enrollment_and_no_early_correction(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open(f"/my/training-exams/{attempt.id}")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("PRIVATE FINAL EXPLANATION", page.text)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        saved = self.url_open(
            f"/my/training-exams/{attempt.id}/save",
            data={
                "csrf_token": csrf,
                "question": q2.id,
                "choices": json.dumps(q2.suggested_answer_ids[:1].ids),
            },
        )
        self.assertTrue(saved.json()["saved"])
        again = self.url_open(f"/my/training-exams/{attempt.id}")
        self.assertNotIn("text-success-emphasis", again.text)
        self.assertNotIn("PRIVATE FINAL EXPLANATION", again.text)
        for path in [
            f"/survey/start/{exam.access_token}?answer_token={attempt.access_token}",
            f"/survey/print/{exam.access_token}?answer_token={attempt.access_token}",
            f"/survey/get_question_image/{exam.access_token}/{attempt.access_token}/{q1.id}/0",
        ]:
            self.assertEqual(self.url_open(path).status_code, 404)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(f"/my/training-exams/{attempt.id}").status_code, 404)
        self.assertEqual(self.url_open(f"/my/trainings/{enrollment.id}/exams/{activity.id}").status_code, 404)

    def test_http_retake_after_success_csrf_binary_token_and_french(self):
        load_language(self.env.cr, "fr_FR")
        self.env["ir.module.module"]._load_module_terms(["training_management_survey"], ["fr_FR"], overwrite=True)
        self.portal.lang = "fr_FR"
        if "website" in self.env and "language_ids" in self.env["website"]._fields:
            french = self.env.ref("base.lang_fr")
            self.env["website"].search([]).write(
                {"language_ids": [Command.set(french.ids)], "default_lang_id": french.id}
            )
        exam, q1, q2, activity, enrollment, service = self.published()
        self.authenticate(self.portal.login, self.portal.login)
        start_url = f"/my/trainings/{enrollment.id}/exams/{activity.id}"
        page = self.url_open(start_url)
        self.assertEqual(page.status_code, 200)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        first = self.url_open(start_url, data={"csrf_token": csrf})
        attempt = self.env["survey.user_input"].sudo().search([("training_enrollment_id", "=", enrollment.id)])
        for q in (q1, q2):
            response = self.url_open(
                f"/my/training-exams/{attempt.id}/save",
                data={
                    "csrf_token": csrf,
                    "question": q.id,
                    "choices": json.dumps(q.suggested_answer_ids.filtered("is_correct").ids),
                },
            )
            self.assertTrue(response.json()["saved"])
        self.url_open(f"/my/training-exams/{attempt.id}/save", data={"csrf_token": csrf, "kind": "submit"})
        result = self.url_open(f"/my/training-exams/{attempt.id}")
        self.assertIn("Confirmer et repasser", result.text)
        self.assertIn("PRIVATE FINAL EXPLANATION", result.text)
        self.assertIn("100", result.text)
        second = self.url_open(start_url, data={"csrf_token": csrf})
        self.assertNotEqual(first.url, second.url)
        self.assertEqual(
            self.env["survey.user_input"].sudo().search_count([("training_enrollment_id", "=", enrollment.id)]), 2
        )
        current = (
            self.env["survey.user_input"]
            .sudo()
            .search([("training_enrollment_id", "=", enrollment.id), ("state", "!=", "done")])
        )
        deadline = current.deadline
        resumed = self.url_open(start_url, data={"csrf_token": csrf})
        self.assertEqual(resumed.url, second.url)
        current.invalidate_recordset()
        self.assertEqual(current.deadline, deadline)
        self.url_open(
            f"/my/training-exams/{current.id}/save",
            data={
                "csrf_token": csrf,
                "question": q1.id,
                "choices": json.dumps(q1.suggested_answer_ids.filtered("is_correct").ids),
            },
        )
        # No GET/status/cron closes this expired attempt before the new-start POST.
        with patch("odoo.fields.Datetime.now", return_value=deadline):
            restarted = self.url_open(start_url, data={"csrf_token": csrf}, allow_redirects=False)
        self.assertEqual(restarted.status_code, 303)
        current.invalidate_recordset()
        self.assertEqual(current.state, "done")
        self.assertEqual(current.end_datetime, deadline)
        self.assertEqual(current.scoring_total, q1.answer_score)
        self.assertTrue(current.user_input_line_ids)
        self.assertEqual(attempt.scoring_percentage, 100)
        all_attempts = self.env["survey.user_input"].sudo().search([("training_enrollment_id", "=", enrollment.id)])
        self.assertEqual(len(all_attempts), 3)
        self.assertEqual(len(all_attempts.filtered(lambda a: a.state != "done")), 1)
        self.assertNotEqual(restarted.headers["Location"], f"/my/training-exams/{current.id}")
        token = limited_field_access_token(q1, "training_explanation", scope="binary")
        self.assertEqual(
            self.url_open(
                f"/web/content/survey.question/{q1.id}/training_explanation?access_token={token}"
            ).status_code,
            404,
        )
        denied = self.url_open(f"/my/training-exams/{attempt.id}/save", data={"kind": "submit"})
        self.assertEqual(denied.status_code, 400)

    def test_private_native_choice_image_needs_owner_even_with_shared_tokens(self):
        exam, q1, q2, activity, enrollment, service = self.published(with_image=True)
        attempt = service._start(enrollment.id, activity.id)
        choice = q2.suggested_answer_ids[:1]
        path = f"/survey/get_question_image/{exam.access_token}/{attempt.access_token}/{q2.id}/{choice.id}"
        self.assertEqual(self.url_open(path).status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, choice.value_image.content)
        self.assertIn("no-store", response.headers["Cache-Control"])
        token = limited_field_access_token(choice, "value_image", scope="binary")
        generic = self.url_open(f"/web/image/survey.question.answer/{choice.id}/value_image?access_token={token}")
        # Native /web/image returns a public placeholder on access denial.
        self.assertNotEqual(generic.content, choice.value_image.content)
        self.assertEqual(
            self.url_open(
                f"/web/content/survey.question.answer/{choice.id}/value_image?access_token={token}"
            ).status_code,
            404,
        )
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(path).status_code, 404)
