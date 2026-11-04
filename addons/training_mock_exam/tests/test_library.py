import io
from PIL import Image
from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools.binary import BinaryBytes


class MockCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = new_test_user(
            cls.env, login="shared_exam_author", groups="training_mock_exam.group_mock_exam_author"
        )
        cls.other_company = cls.env["res.company"].create({"name": "Fictional Exam B"})
        cls.portal = new_test_user(cls.env, login="shared_exam_portal", groups="base.group_portal")
        cls.native_author = new_test_user(cls.env, login="native_survey_author", groups="survey.group_survey_user")
        cls.course = cls.env["training.course"].create({"name": "Fictional common course"})
        cls.foreign = cls.env["training.course"].create(
            {"name": "Fictional foreign course", "company_id": cls.other_company.id}
        )

    def exam(self):
        exam = (
            self.env["survey.survey"]
            .with_user(self.author)
            .create(
                {
                    "title": "Fictional shared exam",
                    "training_course_id": self.course.id,
                    "time_limit": 20,
                    "scoring_success_min": 70,
                }
            )
        )
        question = (
            self.env["survey.question"]
            .with_user(self.author)
            .create(
                {
                    "survey_id": exam.id,
                    "title": "Fictional fixed question",
                    "question_type": "simple_choice",
                    "answer_score": 2,
                    "training_theme": "Fictional theme",
                    "training_explanation": "Fictional correction",
                    "suggested_answer_ids": [
                        Command.create({"value": "Correct", "is_correct": True}),
                        Command.create({"value": "Incorrect", "is_correct": False}),
                    ],
                }
            )
        )
        return exam, question


@tagged("post_install", "-at_install")
class TestMockLibrary(MockCase):
    def test_native_author_form_and_default_context(self):
        model = self.env["survey.survey"].with_user(self.author).with_context(mock_exam_editor=True)
        with Form(model, view="survey.survey_survey_view_form") as form:
            form.title = "Native shared definition form"
            form.training_course_id = self.course
        self.assertEqual(form.record.training_course_id, self.course)
        self.env["survey.survey"].with_user(self.author).with_context(default_training_course_id=self.course.id).create(
            {
                "title": "Shared context with native questions",
                "question_and_page_ids": [
                    Command.create(
                        {
                            "title": "Question created with the native parent",
                            "question_type": "simple_choice",
                            "training_theme": "Context theme",
                            "suggested_answer_ids": [
                                Command.create({"value": "Yes", "is_correct": True}),
                                Command.create({"value": "No"}),
                            ],
                        }
                    )
                ],
            }
        )

    def test_batch_publication_does_not_publish_a_partial_set(self):
        first, question = self.exam()
        invalid, other_question = self.exam()
        invalid.time_limit = 0
        with self.assertRaises(ValidationError):
            (first | invalid).action_mock_publish()
        self.assertEqual(first.training_state, "draft")
        self.assertEqual(invalid.training_state, "draft")

    def test_multiple_exams_and_native_version_history(self):
        first, question = self.exam()
        second, _ = self.exam()
        first.action_mock_publish()
        second.action_mock_publish()
        self.assertEqual(first.training_course_id, second.training_course_id)
        result = first.action_mock_new_version()
        revision = self.env["survey.survey"].browse(result["res_id"]).with_user(self.author)
        self.assertEqual(revision.training_origin_id, first)
        self.assertNotEqual(revision.question_ids, question)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            revision.write({"training_version": first.training_version})
        revision.write({"training_version": "2", "training_revision_reason": "Fictional question revision"})
        revision.action_mock_publish()
        self.assertEqual(first.training_state, "published")
        self.assertFalse(first.certification)
        self.assertFalse(revision.is_attempts_limited)
        self.assertTrue(revision.is_time_limited)

    def test_published_questions_choices_and_files_are_frozen(self):
        exam, question = self.exam()
        image = io.BytesIO()
        Image.new("RGB", (2, 2), "blue").save(image, "PNG")
        choice = question.suggested_answer_ids[0]
        choice.write({"value_image": BinaryBytes(image.getvalue())})
        attachment = self.env["ir.attachment"].create(
            {
                "name": "Fictional question file",
                "res_model": question._name,
                "res_id": question.id,
                "raw": BinaryBytes(b"private file"),
            }
        )
        exam.action_mock_publish()
        for record, values in (
            (exam, {"time_limit": 99}),
            (question, {"title": "Changed"}),
            (choice, {"is_correct": False}),
            (attachment, {"raw": BinaryBytes(b"changed")}),
        ):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                record.write(values)
        with self.assertRaises(ValidationError):
            question.unlink()
        with self.assertRaises(ValidationError):
            exam.unlink()

    def test_author_and_company_boundaries(self):
        exam, question = self.exam()
        for actor in (self.portal, self.native_author, self.env.ref("base.public_user")):
            with self.assertRaises(AccessError):
                exam.with_user(actor).read(["title"])
            with self.assertRaises(AccessError):
                question.with_user(actor).read(["training_explanation"])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["survey.survey"].with_user(self.author).create(
                {"title": "Denied", "training_course_id": self.foreign.id}
            )
        if "training.enrollment" in self.env:
            with self.assertRaises(AccessError):
                self.env["training.enrollment"].with_user(self.author).search([])

    def test_enriched_definitions_publish_without_tm(self):
        for kind, items in [("matching", "One | First\nTwo | Second"), ("ordering", "First\nSecond")]:
            exam, question = self.exam()
            question._configure_interaction(kind, items)
            question._validate_interaction()
            exam.action_mock_publish()
            self.assertEqual(question.training_interaction, kind)
            self.assertEqual(len(question.suggested_answer_ids), 4)
            with self.assertRaises(ValidationError):
                question._configure_interaction(kind, items)

    def test_publication_and_native_answer_bypasses_refused(self):
        exam, question = self.exam()
        with self.assertRaises(ValidationError):
            exam.write({"training_state": "published"})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["survey.survey"].with_user(self.author).with_context(default_training_state="published").create(
                {"title": "Denied state", "training_course_id": self.course.id}
            )
        exam.action_mock_publish()
        with self.assertRaises(AccessError):
            exam._create_answer(partner=self.portal.partner_id)
        with self.assertRaises(AccessError):
            self.env["survey.user_input"].create({"survey_id": exam.id, "partner_id": self.portal.partner_id.id})


@tagged("post_install", "-at_install")
class TestMockBoundaryHttp(MockCase, HttpCase):
    def test_native_tokens_and_public_attachment_do_not_expose_definitions(self):
        exam, question = self.exam()
        attachment = self.env["ir.attachment"].create(
            {
                "name": "Private mock fixture",
                "res_model": question._name,
                "res_id": question.id,
                "raw": BinaryBytes(b"PRIVATE_EXAM_FIXTURE"),
            }
        )
        self.env.cr.execute("UPDATE ir_attachment SET public = TRUE WHERE id = %s", [attachment.id])
        attachment.invalidate_recordset()
        self.env.flush_all()
        for url in (f"/survey/start/{exam.access_token}", f"/web/content/{attachment.id}"):
            # Website may first canonicalize the language prefix. The final
            # resource must still refuse access, rather than accepting a redirect.
            response = self.url_open(url)
            self.assertIn(response.status_code, (403, 404))
            self.assertNotIn(b"PRIVATE_EXAM_FIXTURE", response.content)
        with self.assertRaises(AccessError):
            attachment.with_user(self.native_author).read(["raw"])
