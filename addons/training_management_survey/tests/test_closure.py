import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.addons.training_management.tests.test_closure import ClosureCase

from .test_exam import ExamCase


@tagged("post_install", "-at_install")
class TestMockClosure(ClosureCase, ExamCase):
    def test_successful_mock_does_not_issue_achievement_certificate(self):
        _exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        service._save(attempt.id, q1.id, q1.suggested_answer_ids.filtered("is_correct").ids, False)
        service._save(attempt.id, q2.id, q2.suggested_answer_ids.filtered("is_correct").ids, False)
        service._submit(attempt.id)
        self.assertTrue(service._result(attempt)["success"])
        dossier = self.dossier(enrollment)
        with self.assertRaises(ValidationError):
            enrollment.with_user(self.quality).action_certificate_achievement()
        self.assertFalse(dossier.output_ids)

        self.validate(self.proof(dossier, "completion"))
        enrollment.with_user(self.quality).action_certificate_completion()
        snapshot = json.loads(self.document(dossier, "completion").snapshot)
        origin = snapshot["origins"][1]
        self.assertEqual(origin["threshold"], activity.evaluation_threshold)
        self.assertEqual(origin["evaluation"]["exam"], activity.training_exam_id.id)
        self.assertEqual(origin["evaluation"]["attempts"], attempt.ids)
        self.assertEqual(origin["evaluation"]["score"], service._result(attempt)["percentage"])
