"""Keep TM-only author permissions strict when common and native records are mixed."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_exam import ExamCase


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


@tagged("post_install", "-at_install")
class TestSharedRuntimeAdapter(ExamCase):
    def test_two_enrollments_keep_active_attempts_answers_and_grants_separate(self):
        exam, question, _, activity, enrollment, service = self.published()
        other_delivery = self.delivery()
        other_activity = activity.copy({"delivery_id": other_delivery.id})
        other_enrollment = self.opened(other_delivery)
        first = service._start(enrollment.id, activity.id)
        second = service._start(other_enrollment.id, other_activity.id)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first.mock_context_key, second.mock_context_key)
        self.assertEqual(service._start(enrollment.id, activity.id), first)
        self.assertEqual(service._start(other_enrollment.id, other_activity.id), second)
        service._save(first.id, question.id, question.suggested_answer_ids.filtered("is_correct").ids, True)
        self.assertFalse(second.user_input_line_ids)
        self.assertFalse(second.training_review_ids)
        service._submit(first.id)
        self.assertEqual(second.state, "in_progress")
        foreign_service = service.with_user(self.portal_b)
        with self.assertRaises(AccessError):
            foreign_service._result(first)
        with self.assertRaises(AccessError):
            foreign_service._save(second.id, question.id, [], False)
        fresh = service._start(enrollment.id, activity.id)
        self.assertNotEqual(fresh, first)
        self.assertFalse(fresh.user_input_line_ids)
        self.assertEqual(first.state, "done")
        revision = self.env["training.exam.revision"].with_user(self.coordinator)
        initial = revision._record(
            first, {str(q.id): 0 for q in first.predefined_question_ids}, "Fictional initial revision"
        )
        second_revision = revision._record(
            first, {str(q.id): q.answer_score for q in first.predefined_question_ids}, "Fictional second revision"
        )
        result = service._result(first)
        self.assertEqual(result["percentage"], 100)
        self.assertEqual(len(result["revisions"]), 2)
        self.assertEqual(first.scoring_percentage, 75)
        third = revision._record(
            first, {str(q.id): q.answer_score / 2 for q in first.predefined_question_ids}, "Fictional third revision"
        )
        self.assertEqual(third.previous_id, second_revision)
        self.assertEqual(second_revision.previous_id, initial)
        self.assertEqual(service._result(first)["percentage"], 50)
