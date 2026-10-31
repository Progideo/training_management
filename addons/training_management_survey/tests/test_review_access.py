"""History expiry exception must not bypass withdrawals; exams need a provider."""

from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged

from .test_exam import ExamCase


@tagged("post_install", "-at_install")
class TestExamAccessContinuity(ExamCase, HttpCase):
    def test_history_and_correction_follow_effective_access_with_expiry_exception(self):
        exam, q1, q2, activity, enrollment, service = self.published(with_image=True)
        attempt = service._start(enrollment.id, activity.id)
        service._save(attempt.id, q1.id, q1.suggested_answer_ids[:1].ids, False)
        service._submit(attempt.id)
        self.authenticate(self.portal.login, self.portal.login)
        path = "/my/training-exams/%s" % attempt.id
        self.assertIn("PRIVATE FINAL EXPLANATION", self.url_open(path).text)
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_end + timedelta(seconds=1)):
            self.assertEqual(service._attempt(attempt.id), attempt)
            self.assertIn(enrollment, service._history_enrollments())
            self.assertEqual(self.url_open(path).status_code, 200)
            with self.assertRaises(AccessError):
                service._start(enrollment.id, activity.id)
        image_path = "/survey/get_question_image/%s/%s/%s/%s" % (
            exam.access_token,
            attempt.access_token,
            q2.id,
            q2.suggested_answer_ids[:1].id,
        )
        self.assertEqual(self.url_open(image_path).content, q2.suggested_answer_ids[:1].value_image.content)
        enrollment.action_revoke_authorization(reason="Fictional commercial withdrawal")
        self.assertEqual(enrollment._effective_state(), "blocked")
        self.assertNotIn(enrollment, service._history_enrollments())
        with self.assertRaises(AccessError):
            service._attempt(attempt.id)
        self.assertEqual(self.url_open(path).status_code, 404)
        self.assertNotIn(path, self.url_open("/my/training-exams").text)
        self.assertEqual(self.url_open("/my/trainings/%s/exams/%s" % (enrollment.id, activity.id)).status_code, 404)
        # The route is also covered by native-choice image tests; no alternate
        # token route may restore an enrollment whose commercial grant was withdrawn.
        self.assertEqual(self.url_open(image_path).status_code, 404)
        enrollment.action_authorize(reason="Fictional authorization restored")
        self.assertEqual(service._attempt(attempt.id), attempt)
        enrollment.action_suspend_access(reason="Fictional suspension")
        self.assertNotIn(enrollment, service._history_enrollments())
        self.assertEqual(self.url_open(path).status_code, 404)

    def test_exam_is_required_and_cannot_be_removed_from_an_activity(self):
        _exam, _q1, _q2, activity, _enrollment, _service = self.published()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            activity.write({"training_exam_id": False})
        self.assertTrue(activity.training_exam_id)
