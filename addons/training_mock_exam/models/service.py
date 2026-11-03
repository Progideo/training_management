"""Shared passation; adapters authorize context before any privileged native operation."""

from datetime import timedelta
import math
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain


class ExamService(models.AbstractModel):
    _name = "training.mock.exam.service"
    _description = "Shared Private Native Exam Engine"

    @api.private
    def _attempt(self, attempt_id, *, mutate=False):
        raise AccessError(self.env._("An authorized learner context is required."))

    @api.private
    def _start_native(self, exam, context_key, values, *, legacy_domain=None):
        # Private extension point: the adapter has checked and locked its grant.
        user = self.env.user
        if (
            not user.active
            or user._is_public()
            or not isinstance(context_key, str)
            or not context_key.strip()
            or len(context_key) > 200
        ):
            raise AccessError(self.env._("An authorized learner context is required."))
        if not exam:
            raise ValidationError(self.env._("No published mock exam is assigned."))
        exam.ensure_one()
        if exam.training_course_id and exam.mock_company_id not in user.company_ids:
            raise AccessError(self.env._("This exam belongs to another company."))
        if (
            not exam.active
            or exam.training_state != "published"
            or not exam._mock_definition_allowed()
            or not math.isfinite(exam.time_limit)
            or exam.time_limit <= 0
        ):
            raise ValidationError(self.env._("No published mock exam is assigned."))
        family = exam.training_origin_id or exam
        family.lock_for_update()
        scope = Domain("mock_context_key", "=", context_key)
        if legacy_domain is not None:
            scope |= Domain(legacy_domain)
        attempts = self.env["survey.user_input"].sudo().with_context({})  # pylint: disable=context-overridden  # strip all RPC defaults at the factory boundary
        active = attempts.search(
            list(
                scope
                & Domain("training_family_id", "=", family.id)
                & Domain("partner_id", "=", user.partner_id.id)
                & Domain("state", "!=", "done")
            ),
            limit=1,
        )
        if active:
            active._mock_close_if_expired()
            if active.state != "done":
                return active
            active.flush_recordset(["state"])
        now = fields.Datetime.now()
        return attempts._training_create(
            {
                **values,
                "survey_id": exam.id,
                "partner_id": user.partner_id.id,
                "mock_context_key": context_key,
                "mock_company_id": exam.mock_company_id.id,
                "training_family_id": family.id,
                "start_datetime": now,
                "state": "in_progress",
                "deadline": now + timedelta(minutes=exam.time_limit),
                "predefined_question_ids": [(6, 0, exam.question_ids.ids)],
            }
        )

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
            or type(question_id) is not int
            or not isinstance(choices, list)
            or any(type(choice) is not int for choice in choices)
            or type(marked) is not bool
            or len(choices) != len(set(choices))
            or not set(choices) <= set(question.suggested_answer_ids.ids)
        ):
            raise ValidationError(self.env._("Choose answers from this question."))
        if question.question_type == "simple_choice" and len(choices) > 1:
            raise ValidationError(self.env._("Choose one answer for a QCU question."))
        if question.training_interaction:
            selected = question.suggested_answer_ids.filtered(lambda answer: answer.id in choices)
            if len(set(selected.mapped("training_row_key"))) != len(selected) or len(
                set(selected.mapped("training_option_key"))
            ) != len(selected):
                raise ValidationError(self.env._("Assign each item at most once; leave unanswered rows empty."))
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
        attempt = self._attempt(attempt.id)
        if attempt.state != "done":
            raise AccessError(self.env._("Correction is available only after submission."))
        rows = attempt._training_scores()
        latest = self._result_adjustments(attempt)[:1]
        themes = {p.title: {"points": 0, "maximum": 0} for p in attempt.survey_id.page_ids}
        result = []
        for row in rows:
            question = row["question"]
            points = latest.points_by_question[str(question.id)] if latest else row["points"]
            theme = question.training_theme or question.page_id.title or self.env._("Unclassified")
            url = self._result_material(question)
            result.append(
                {
                    "title": question.title,
                    "selected": row["selected"].mapped("value_label"),
                    "correct": row["correct"].mapped("value_label"),
                    "images": self._result_images(attempt, question),
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
            "revisions": [{"reason": r.reason, "date": r.create_date} for r in self._result_adjustments(attempt)],
        }

    @api.private
    def _result_adjustments(self, attempt):
        return []

    @api.private
    def _result_material(self, question):
        return False

    @api.private
    def _result_images(self, attempt, question):
        return []

    @api.private
    def _obligation_status(self, exam, context_key, partner_id, obligation, *, legacy_domain=None):
        """Scalar evidence only; the adapter resolves and authorizes its frozen grant."""
        if obligation not in ("optional", "complete", "pass"):
            raise ValidationError(self.env._("Choose a valid exam obligation."))
        scope = Domain("mock_context_key", "=", context_key)
        if legacy_domain is not None:
            scope |= Domain(legacy_domain)
        attempts = (
            self.env["survey.user_input"]
            .sudo()
            .search(
                list(
                    scope
                    & Domain("survey_id", "=", exam.id)
                    & Domain("partner_id", "=", partner_id)
                    & Domain("state", "=", "done")
                )
            )
        )
        scores = []
        for attempt in attempts:
            rows = attempt._training_scores()
            latest = self._result_adjustments(attempt)[:1]
            maximum = sum(row["maximum"] for row in rows)
            if maximum:
                points = sum(
                    latest.points_by_question[str(row["question"].id)] if latest else row["points"] for row in rows
                )
                scores.append(100 * points / maximum)
        best = max(scores, default=None)
        succeeded = best is not None and best >= exam.scoring_success_min
        return {
            "required": obligation != "optional",
            "complete": bool(attempts),
            "success": succeeded,
            "satisfied": succeeded if obligation == "pass" else bool(attempts),
            "score": best,
        }
