"""All portal operations recheck the exact S03 identity and current grant."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ExamService(models.AbstractModel):
    _name = "training.exam.service"
    _inherit = "training.mock.exam.service"
    _description = "Private Native Survey Exam Operations"

    @api.private
    def _enrollment(self, enrollment_id, *, history=False, finish=False, lock=False):
        if not history and not finish:
            return self.env["training.learning.service"]._enrollment(enrollment_id, lock=lock)
        enrollment = self.env["training.enrollment"].sudo().browse(enrollment_id).exists()
        user = self.env.user
        if not enrollment or not (
            user.active
            and not user._is_public()
            and enrollment.user_id == user
            and enrollment.participant_id == user.partner_id
            and enrollment.company_id in user.company_ids
            and enrollment.state == "confirmed"
            and enrollment.access_state == "active"
        ):
            raise AccessError(self.env._("This private exam is unavailable."))
        if enrollment._effective_state() not in ("active", "expired"):
            raise AccessError(self.env._("This private exam is unavailable."))
        if lock:
            self.env["training.learning.service"]._lock_enrollment(enrollment)
            return self._enrollment(enrollment_id, history=history, finish=finish)
        return enrollment

    @api.private
    def _history_enrollments(self):
        user = self.env.user
        enrollments = self.env["training.enrollment"].sudo()
        if not user.active or user._is_public():
            return enrollments.browse()
        candidates = enrollments.search(
            [
                ("user_id", "=", user.id),
                ("participant_id", "=", user.partner_id.id),
                ("company_id", "in", user.company_ids.ids),
                ("state", "=", "confirmed"),
                ("access_state", "=", "active"),
            ]
        )
        # Expiry keeps history; every other withdrawal uses the same effective
        # policy as direct result/image reads, including inherited path gates.
        return candidates.filtered(lambda e: e._effective_state() in ("active", "expired"))

    @api.private
    def _start(self, enrollment_id, activity_id):
        enrollment = self._enrollment(enrollment_id, lock=True)
        activity = self.env["training.learning.service"]._activity(enrollment, activity_id)
        exam = self.env["training.exam.requirement"]._assigned_exam(enrollment, activity)
        attempt = self._start_native(
            exam,
            "training.enrollment:%s" % enrollment.id,
            {
                "training_enrollment_id": enrollment.id,
                "training_activity_id": activity.id,
                "mock_reader_group_id": self.env.ref("training_management.group_training_coordinator").id,
            },
            legacy_domain=[("mock_context_key", "=", False), ("training_enrollment_id", "=", enrollment.id)],
        )

        if attempt.survey_id != exam:
            raise ValidationError(self.env._("Finish the active attempt of this exam family before changing versions."))
        return attempt

    @api.private
    def _attempt(self, attempt_id, *, mutate=False):
        attempt = self.env["survey.user_input"].sudo().browse(attempt_id).exists()
        if not attempt or not attempt.training_enrollment_id or attempt.training_evaluation_assignment_id:
            raise AccessError(self.env._("This private exam is unavailable."))
        self._enrollment(attempt.training_enrollment_id.id, history=not mutate, finish=mutate, lock=mutate)
        if attempt.survey_id.training_course_id:
            assigned = self.env["training.exam.requirement"]._assigned_exam(
                attempt.training_enrollment_id, attempt.training_activity_id
            )
            if assigned != attempt.survey_id:
                raise AccessError(self.env._("This private exam is unavailable."))
            if attempt.training_enrollment_id._effective_state() == "expired":
                if not mutate:
                    raise AccessError(self.env._("Detailed exam content is closed after access expiry."))
                attempt.lock_for_update()
                attempt.invalidate_recordset()
                if attempt.state != "done":
                    attempt._training_finish()
        if (
            attempt.mock_context_key
            and attempt.mock_context_key != "training.enrollment:%s" % attempt.training_enrollment_id.id
        ):
            raise AccessError(self.env._("This private exam is unavailable."))
        if mutate or attempt.state != "done":
            attempt._mock_close_if_expired()
        return attempt

    @api.private
    def _result_material(self, question):
        material = question.training_material_id
        return (
            f"/web/content/training.material/{material.id}/data?download=true&filename_field=filename"
            if material and self.env["training.document.policy"]._can_read(material)
            else False
        )

    @api.private
    def _result_images(self, attempt, question):
        return [
            {
                "label": choice.value_label,
                "url": f"/survey/get_question_image/{attempt.survey_id.access_token}/{attempt.access_token}/{question.id}/{choice.id}",
            }
            for choice in question.suggested_answer_ids
            if choice.value_image
        ]


class LearningActivity(models.Model):
    _inherit = "training.learning.activity"  # pylint: disable=consider-merging-classes-inherited  # legacy exam integration is separate from frozen requirements

    criterion = fields.Selection(selection_add=[("evaluation", "Mock Exam Threshold")])
    training_exam_id = fields.Many2one("survey.survey", ondelete="restrict", string="Mock Exam Version")

    @api.model
    def _supports_mock_exams(self):
        return True

    @api.constrains("training_exam_id", "delivery_id", "criterion")
    def _check_evaluation_configuration(self):
        for activity in self:
            exam = activity.training_exam_id
            if (activity.criterion == "evaluation" and not exam) or (
                exam
                and (
                    activity.criterion != "evaluation"
                    or exam.training_state != "published"
                    or (
                        exam.training_course_id != activity.delivery_id.program_id.course_id
                        if exam.training_course_id
                        else exam.training_program_id != activity.delivery_id.program_id
                    )
                    or (exam.training_course_id and exam.mock_company_id != activity.company_id)
                )
            ):
                raise ValidationError(
                    self.env._("Assign a published exam from this programme to an evaluation activity.")
                )

    def write(self, vals):
        if self.env["survey.user_input"].sudo().search_count([("training_activity_id", "in", self.ids)], limit=1):
            raise ValidationError(self.env._("Keep activities with exam attempts unchanged; add a new activity."))
        return super().write(vals)


class LearningService(models.AbstractModel):
    _inherit = "training.learning.service"  # pylint: disable=consider-merging-classes-inherited  # legacy integration and contextual obligations are separate

    @api.private
    def _evaluation_snapshot(self, enrollment, activity):
        snapshot = super()._evaluation_snapshot(enrollment, activity)
        if activity.training_exam_id:
            attempts = (
                self.env["survey.user_input"]
                .sudo()
                .search(
                    [
                        ("training_enrollment_id", "=", enrollment.id),
                        ("survey_id", "=", activity.training_exam_id.id),
                        ("state", "=", "done"),
                    ],
                    order="id",
                )
            )
            snapshot.update(exam=activity.training_exam_id.id, attempts=attempts.ids)
        return snapshot

    @api.private
    def _evaluation_result(self, enrollment, activity):
        exam = activity.training_exam_id
        if not exam:
            return super()._evaluation_result(enrollment, activity)
        attempts = (
            self.env["survey.user_input"]
            .sudo()
            .search(
                [
                    ("training_enrollment_id", "=", enrollment.id),
                    ("survey_id", "=", exam.id),
                    ("state", "=", "done"),
                ]
            )
        )
        # Progression needs a scalar score, not the correction and its resource
        # links. Building those links calls the access policy, which itself
        # evaluates path progression. Keep this read independent of access.
        scores = []
        for attempt in attempts:
            rows = attempt._training_scores()
            latest = attempt.training_adjustment_ids.sorted("id", reverse=True)[:1]
            maximum = sum(row["maximum"] for row in rows)
            if maximum:
                obtained = sum(
                    latest.points_by_question[str(row["question"].id)] if latest else row["points"] for row in rows
                )
                scores.append(100 * obtained / maximum)
        return max(scores, default=None)

    @api.private
    def _rows(self, enrollment):
        rows = super()._rows(enrollment)
        for row in rows:
            activity = self.env["training.learning.activity"].sudo().browse(row["id"])
            row["exam_url"] = (
                f"/my/trainings/{enrollment.id}/exams/{activity.id}" if activity.training_exam_id else False
            )
        return rows


class Program(models.Model):
    _inherit = "training.program.version"

    def action_training_exam(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("training_management.group_training_coordinator"):
            raise AccessError(self.env._("Training coordination is required."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "survey.survey",
            "view_mode": "form",
            "context": {
                "default_training_program_id": self.id,
                "default_title": self.title,
                "default_survey_type": "custom",
                "default_scoring_type": "scoring_with_answers",
            },
        }
