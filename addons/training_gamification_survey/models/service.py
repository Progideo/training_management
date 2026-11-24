"""Mock exams earn points once per exam and enrollment, whatever the score or the retakes."""

from odoo import api, models


class GamificationService(models.AbstractModel):
    _inherit = "training.gamification.service"

    @api.model
    def _event_types(self):
        return {
            **super()._event_types(),
            "mock_exam_completed": (self.env._("Mock exam completed"), self._events_mock_exam_completed),
        }

    @api.model
    def _events_mock_exam_completed(self, enrollments):
        attempts = (
            self.env["survey.user_input"]
            .sudo()
            .search(
                [("training_enrollment_id", "in", enrollments.ids), ("training_activity_id", "!=", False)],
                order="end_datetime, id",
            )
        )
        first_done = {}
        for attempt in attempts:
            key = (attempt.training_enrollment_id, attempt.training_activity_id)
            first_done.setdefault(key, None)
            if attempt.state == "done" and not first_done[key]:
                first_done[key] = attempt.end_datetime or attempt.write_date
        for (enrollment, activity), date in first_done.items():
            # Unlimited retakes cannot multiply points: the exam itself is the event.
            yield enrollment, f"{activity._name},{activity.id}", bool(date), date
