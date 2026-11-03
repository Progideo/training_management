"""Keep TM-only author permissions strict when common and native records are mixed."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestSharedLibraryBoundary(TransactionCase):
    def test_common_author_cannot_batch_edit_tm_metadata_on_native_records(self):
        author = new_test_user(self.env, login="mock_mixed_author", groups="training_mock_exam.group_mock_exam_author")
        course = self.env["training.course"].create({"name": "Fictional shared course"})
        model = self.env["survey.survey"].with_user(author)
        common = model.create({"title": "Fictional common exam", "training_course_id": course.id})
        native = model.create({"title": "Fictional ordinary survey"})
        common.write({"training_version": "A"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            (common | native).write({"training_version": "B"})
        questions = self.env["survey.question"].with_user(author)
        shared_question = questions.create({"survey_id": common.id, "title": "Fictional shared question"})
        native_question = questions.create({"survey_id": native.id, "title": "Fictional native question"})
        shared_question.write({"training_theme": "Fictional shared theme"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            (shared_question | native_question).write({"training_theme": "Denied mixed edit"})
