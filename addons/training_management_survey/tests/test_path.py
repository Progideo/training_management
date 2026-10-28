"""P09 / S06: progression reads scores without evaluating correction links."""

from odoo import Command
from odoo.tests import Form, tagged

from .test_exam import ExamCase


@tagged("post_install", "-at_install")
class TestPathExam(ExamCase):
    def test_acquired_exam_step_with_private_correction_resource(self):
        material = self.material()
        exam, first, second = self.exam()
        first.training_material_id = material
        exam.action_training_publish()
        delivery = self.delivery()
        activity = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional path assessment",
                    "delivery_id": delivery.id,
                    "criterion": "evaluation",
                    "evaluation_threshold": 75,
                    "training_exam_id": exam.id,
                }
            )
        )
        enrollment = self.opened(delivery)
        service = self.env["training.exam.service"].with_user(self.portal)
        attempt = service._start(enrollment.id, activity.id)
        for question in (first, second):
            service._save(attempt.id, question.id, question.suggested_answer_ids.filtered("is_correct").ids, False)
        service._submit(attempt.id)
        path = (
            self.env["training.path"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional acquired exam path",
                    "step_ids": [Command.create({"program_id": self.program.id})],
                }
            )
        )
        path.action_validate()
        reference = (
            self.env["training.path.assignment"]
            .with_user(self.coordinator)
            .create(
                {
                    "step_id": path.step_ids.id,
                    "enrollment_id": enrollment.id,
                }
            )
        )
        self.assertTrue(reference.completed)
        self.assertEqual(enrollment.with_user(self.portal).sudo()._effective_state(), "active")
        self.assertTrue(self.env["training.document.policy"].with_user(self.portal)._can_read(material))
        self.assertEqual(service._result(attempt)["percentage"], 100)
        self.assertTrue(service._result(attempt)["questions"][0]["url"])
        self.assertEqual(
            self.env["survey.user_input"].search_count(
                [
                    ("training_enrollment_id", "=", enrollment.id),
                ]
            ),
            1,
        )

        with Form(
            self.env["training.exam.revise"]
            .with_user(self.coordinator)
            .with_context(
                active_model="survey.user_input",
                active_id=attempt.id,
            )
        ) as form:
            form.reason = "Fictional path score review"
            with form.line_ids.edit(0) as line:
                line.points = 0
        form.record.action_apply()
        learning = self.env["training.learning.service"].with_user(self.portal)
        self.assertEqual(learning._evaluation_result(enrollment.sudo(), activity.sudo()), 25)
        self.assertEqual(service._result(attempt)["percentage"], 25)
        self.assertEqual(attempt.scoring_percentage, 100)
        self.assertFalse(reference._is_completed())
