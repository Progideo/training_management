"""All portal operations recheck the exact S03 identity and current grant."""

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ExamService(models.AbstractModel):
    _name = "training.exam.service"
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
        if finish and enrollment._effective_state() not in ("active", "expired"):
            raise AccessError(self.env._("This private exam is unavailable."))
        if lock:
            enrollment.delivery_id._serialize()
            enrollment.invalidate_recordset()
            return self._enrollment(enrollment_id, history=history, finish=finish)
        return enrollment

    @api.private
    def _start(self, enrollment_id, activity_id):
        learning = self.env["training.learning.service"]
        enrollment = self._enrollment(enrollment_id, lock=True)
        activity = learning._activity(enrollment, activity_id)
        exam = activity.training_exam_id
        if not exam or exam.training_state != "published" or not exam.active:
            raise ValidationError(self.env._("No published mock exam is assigned."))
        family = exam.training_origin_id or exam
        family.lock_for_update()
        attempts = self.env["survey.user_input"].sudo()
        active = attempts.search(
            [
                ("training_family_id", "=", family.id),
                ("partner_id", "=", enrollment.participant_id.id),
                ("state", "!=", "done"),
            ],
            limit=1,
        )
        if active and active.deadline <= fields.Datetime.now():
            active.lock_for_update()
            active._training_finish()
            active = attempts
        if active:
            if active.training_enrollment_id != enrollment:
                raise ValidationError(self.env._("Resume the active attempt in your other training space first."))
            return active
        now = fields.Datetime.now()
        return attempts._training_create(
            {
                "survey_id": exam.id,
                "partner_id": enrollment.participant_id.id,
                "training_enrollment_id": enrollment.id,
                "training_activity_id": activity.id,
                "training_family_id": family.id,
                "start_datetime": now,
                "state": "in_progress",
                "deadline": now + timedelta(minutes=exam.time_limit),
                "predefined_question_ids": [(6, 0, exam.question_ids.ids)],
            }
        )

    @api.private
    def _attempt(self, attempt_id, *, mutate=False):
        attempt = self.env["survey.user_input"].sudo().browse(attempt_id).exists()
        if not attempt or not attempt.training_enrollment_id or attempt.training_evaluation_assignment_id:
            raise AccessError(self.env._("This private exam is unavailable."))
        self._enrollment(attempt.training_enrollment_id.id, history=not mutate, finish=mutate, lock=mutate)
        if mutate or attempt.state != "done":
            attempt.lock_for_update()
            attempt.invalidate_recordset()
            if attempt.state != "done" and attempt.deadline <= fields.Datetime.now():
                attempt._training_finish()
        return attempt

    @api.private
    def _save(self, attempt_id, question_id, choices, marked):
        attempt = self._attempt(attempt_id, mutate=True)
        # Expiration is persisted in this successful response, never rolled back
        # by throwing a late-answer exception after closing the attempt.
        if attempt.state == "done":
            return {"done": True}
        question = attempt.predefined_question_ids.filtered(lambda q: q.id == question_id)
        if (
            not question
            or len(choices) != len(set(choices))
            or not set(choices) <= set(question.suggested_answer_ids.ids)
        ):
            raise ValidationError(self.env._("Choose answers from this question."))
        if question.question_type == "simple_choice" and len(choices) > 1:
            raise ValidationError(self.env._("Choose one answer for a QCU question."))
        attempt._save_lines(question, choices)
        attempt.user_input_line_ids.filtered(lambda line: line.question_id == question)._compute_answer_score()
        review = attempt.training_review_ids | question if marked else attempt.training_review_ids - question
        attempt._training_store({"training_review_ids": [(6, 0, review.ids)]})
        return {"saved": True}

    @api.private
    def _submit(self, attempt_id):
        attempt = self._attempt(attempt_id, mutate=True)
        if attempt.state != "done":
            attempt._training_finish()
        return {"done": True}

    @api.private
    def _result(self, attempt):
        if attempt.state != "done":
            raise AccessError(self.env._("Correction is available only after submission."))
        rows = attempt._training_scores()
        latest = attempt.training_adjustment_ids[:1]
        themes = {p.title: {"points": 0, "maximum": 0} for p in attempt.survey_id.page_ids}
        result = []
        policy = self.env["training.document.policy"]
        for row in rows:
            question = row["question"]
            points = latest.points_by_question[str(question.id)] if latest else row["points"]
            theme = question.training_theme or question.page_id.title or self.env._("Unclassified")
            material = question.training_material_id
            # Reuse S05 policy, including revocation, version and assignment.
            url = (
                f"/web/content/training.material/{material.id}/data?download=true&filename_field=filename"
                if (material and policy._can_read(material))
                else False
            )
            result.append(
                {
                    "title": question.title,
                    "selected": row["selected"].mapped("value_label"),
                    "correct": row["correct"].mapped("value_label"),
                    "images": [
                        {
                            "label": choice.value_label,
                            "url": f"/survey/get_question_image/{attempt.survey_id.access_token}/{attempt.access_token}/{question.id}/{choice.id}",
                        }
                        for choice in question.suggested_answer_ids
                        if choice.value_image
                    ],
                    "explanation": question.training_explanation,
                    "points": points,
                    "original_points": row["points"],
                    "maximum": row["maximum"],
                    "url": url,
                }
            )
            totals = themes.setdefault(theme, {"points": 0, "maximum": 0})
            totals["points"] += points
            totals["maximum"] += row["maximum"]
        maximum = sum(r["maximum"] for r in result)
        obtained = sum(r["points"] for r in result)
        percentage = 100 * obtained / maximum if maximum else None
        return {
            "questions": result,
            "themes": themes,
            "points": obtained,
            "maximum": maximum,
            "percentage": percentage,
            "success": percentage is not None and percentage >= attempt.survey_id.scoring_success_min,
            "original_percentage": attempt.scoring_percentage,
            "revisions": [{"reason": r.reason, "date": r.create_date} for r in attempt.training_adjustment_ids],
        }


class LearningActivity(models.Model):
    _inherit = "training.learning.activity"

    criterion = fields.Selection(selection_add=[("evaluation", "Mock Exam Threshold")])
    training_exam_id = fields.Many2one("survey.survey", ondelete="restrict", string="Mock Exam Version")

    @api.constrains("training_exam_id", "delivery_id", "criterion")
    def _check_training_exam(self):
        for activity in self:
            exam = activity.training_exam_id
            if exam and (
                activity.criterion != "evaluation"
                or exam.training_state != "published"
                or exam.training_program_id != activity.delivery_id.program_id
            ):
                raise ValidationError(
                    self.env._("Assign a published exam from this programme to an evaluation activity.")
                )

    def write(self, vals):
        if self.env["survey.user_input"].sudo().search_count([("training_activity_id", "in", self.ids)], limit=1):
            raise ValidationError(self.env._("Keep activities with exam attempts unchanged; add a new activity."))
        return super().write(vals)


class LearningService(models.AbstractModel):
    _inherit = "training.learning.service"

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
        scores = [self.env["training.exam.service"]._result(a)["percentage"] for a in attempts]
        return max(scores) if scores else None

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
