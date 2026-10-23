"""Native Survey questions and answers for distinct S09 pedagogical evaluations."""

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class Evaluation(models.Model):
    _inherit = "training.evaluation"

    survey_id = fields.Many2one("survey.survey", ondelete="restrict", copy=False)

    def action_questionnaire(self):
        self.ensure_one()
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        self.lock_for_update()
        if not self.survey_id:
            if self.state != "draft":
                raise ValidationError(self.env._("Create a new version to add a questionnaire."))
            self.survey_id = self.env["survey.survey"].create(
                {
                    "title": self.name,
                    "training_program_id": self.program_id.id,
                    "training_evaluation_id": self.id,
                    "training_version": self.version,
                    "survey_type": "custom",
                    "scoring_type": "scoring_with_answers" if self.scored else "no_scoring",
                    "scoring_success_min": self.threshold,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "survey.survey",
            "res_id": self.survey_id.id,
            "view_mode": "form",
        }

    @api.private
    def _publish_questionnaire(self):
        if self.survey_id:
            survey = self.survey_id
            if survey.training_evaluation_id != self or survey.training_program_id != self.program_id:
                raise ValidationError(self.env._("Use the questionnaire belonging to this evaluation version."))
            survey.write({"title": self.name, "training_version": self.version, "scoring_success_min": self.threshold})
            survey.action_training_publish()
        return super()._publish_questionnaire()

    def copy(self, default=None):
        new = super().copy(default)
        if self.survey_id:
            new.survey_id = self.survey_id.copy(
                {
                    "training_evaluation_id": new.id,
                    "training_version": new.version,
                    "training_origin_id": (self.survey_id.training_origin_id or self.survey_id).id,
                    "training_revision_reason": "New evaluation version",
                }
            ).id
        return new


class SurveyEvaluation(models.Model):
    _inherit = "survey.survey"

    training_evaluation_id = fields.Many2one("training.evaluation", ondelete="restrict", copy=False)

    @api.constrains("training_evaluation_id", "training_program_id")
    def _check_evaluation_programme(self):
        for survey in self.filtered("training_evaluation_id"):
            if survey.training_evaluation_id.program_id != survey.training_program_id:
                raise ValidationError(self.env._("Use the programme of this evaluation version."))


class EvaluationAttempt(models.Model):
    _inherit = "survey.user_input"

    training_evaluation_assignment_id = fields.Many2one(
        "training.evaluation.assignment", ondelete="restrict", copy=False, readonly=True
    )
    training_evaluation_number = fields.Integer(readonly=True, copy=False)

    @api.private
    def _training_finish(self):
        result = super()._training_finish()
        for attempt in self.filtered("training_evaluation_assignment_id"):
            row = attempt.training_evaluation_assignment_id
            if row.attempt_number == attempt.training_evaluation_number and not row.submitted_at:
                row._store({"submitted_at": attempt.end_datetime, "revision": row.revision + 1})
        return result


class EvaluationService(models.AbstractModel):
    _inherit = "training.evaluation.service"

    @api.private
    def _native_attempt(self, attempt_id, *, mutate=False):
        attempt = self.env["survey.user_input"].sudo().browse(attempt_id).exists()
        if not attempt or not attempt.training_evaluation_assignment_id:
            raise AccessError(self.env._("This evaluation attempt is unavailable."))
        row = self._assignment(attempt.training_evaluation_assignment_id.id, participant=True, lock=mutate)
        if attempt.training_evaluation_number != row.attempt_number and mutate:
            raise AccessError(self.env._("This attempt is no longer current."))
        if mutate:
            attempt.lock_for_update()
            attempt.invalidate_recordset()
        if attempt.state != "done" and attempt.deadline <= fields.Datetime.now():
            if not mutate:
                return self._native_attempt(attempt_id, mutate=True)
            attempt._training_finish()
        return attempt

    @api.private
    def _start(self, assignment_id):
        with self.env.cr.savepoint():
            return self._start_checked(assignment_id)

    @api.private
    def _start_checked(self, assignment_id):
        row = super()._start(assignment_id)
        survey = row.evaluation_id.survey_id
        if not survey:
            return row
        current = (
            self.env["survey.user_input"]
            .sudo()
            .search(
                [
                    ("training_evaluation_assignment_id", "=", row.id),
                    ("training_evaluation_number", "=", row.attempt_number),
                ],
                limit=1,
            )
        )
        if not current:
            survey.lock_for_update()
            survey.invalidate_recordset(["active"])
            if not survey.active:
                raise ValidationError(self.env._("This evaluation questionnaire is archived."))
            self.env["survey.user_input"].flush_model(["state"])
            active = (
                self.env["survey.user_input"]
                .sudo()
                .search_count(
                    [
                        ("partner_id", "=", row.enrollment_id.participant_id.id),
                        ("training_family_id", "=", survey.id),
                        ("state", "!=", "done"),
                    ],
                    limit=1,
                )
            )
            if active:
                raise ValidationError(self.env._("Resume the active evaluation attempt first."))
            deadline = row.due_at
            now = fields.Datetime.now()
            if survey.is_time_limited:
                deadline = min(deadline, now + timedelta(minutes=survey.time_limit))
            self.env["survey.user_input"].sudo()._training_create(
                {
                    "survey_id": survey.id,
                    "partner_id": row.enrollment_id.participant_id.id,
                    "training_enrollment_id": row.enrollment_id.id,
                    "training_family_id": survey.id,
                    "training_evaluation_assignment_id": row.id,
                    "training_evaluation_number": row.attempt_number,
                    "start_datetime": now,
                    "state": "in_progress",
                    "deadline": deadline,
                    "predefined_question_ids": [(6, 0, survey.question_ids.ids)],
                }
            )
        return row

    @api.private
    def _save_answers(self, assignment_id, answers, *, submit=False):
        row = self._assignment(assignment_id, participant=True, lock=True)
        attempt = (
            self.env["survey.user_input"]
            .sudo()
            .search(
                [
                    ("training_evaluation_assignment_id", "=", row.id),
                    ("training_evaluation_number", "=", row.attempt_number),
                ],
                limit=1,
            )
        )
        attempt = self._native_attempt(attempt.id, mutate=True)
        if attempt.state == "done":
            return row
        if set(answers) - set(attempt.predefined_question_ids.ids):
            raise ValidationError(self.env._("Use questions from this evaluation."))
        for question in attempt.predefined_question_ids:
            value = answers.get(question.id)
            if question.question_type in ("simple_choice", "multiple_choice"):
                values = [int(v) for v in (value or [])]
                if (
                    len(values) != len(set(values))
                    or not set(values) <= set(question.suggested_answer_ids.ids)
                    or (question.question_type == "simple_choice" and len(values) > 1)
                ):
                    raise ValidationError(self.env._("Choose answers from this question."))
                native = str(values[0]) if question.question_type == "simple_choice" and values else values
            else:
                native = str(value or "")[:20000]
            if submit:
                errors = question.validate_question(native)
                if errors or (
                    question.constr_mandatory and (not native or (isinstance(native, str) and not native.strip()))
                ):
                    raise ValidationError(self.env._("Complete the required answers before submitting."))
            attempt._save_lines(question, native)
        attempt.user_input_line_ids._compute_answer_score()
        if submit:
            attempt._training_finish()
        return row

    @api.private
    def _validate(self, assignment_id, **values):
        row = self._assignment(assignment_id, evaluate=True, lock=True)
        if row.evaluation_id.survey_id:
            attempt = (
                self.env["survey.user_input"]
                .sudo()
                .search(
                    [
                        ("training_evaluation_assignment_id", "=", row.id),
                        ("training_evaluation_number", "=", row.attempt_number),
                    ],
                    limit=1,
                )
            )
            if not attempt or attempt.state != "done":
                raise ValidationError(self.env._("Complete the native questionnaire before validating its result."))
            values["source"] = "survey.user_input:%s; %s" % (attempt.id, values.get("source") or "")
        return super()._validate(assignment_id, **values)

    @api.private
    def _portal_answers(self, assignment_id, post, *, submit=False):
        row = self._assignment(assignment_id, participant=True)
        if not row.evaluation_id.survey_id:
            return super()._portal_answers(assignment_id, post, submit=submit)
        answers = {}
        for key, value in post.items():
            if key.startswith("q_") and key[2:].isdigit():
                question_id = int(key[2:])
                question = row.evaluation_id.survey_id.question_ids.filtered(lambda q: q.id == question_id)
                answers[question_id] = (
                    value
                    if question.question_type in ("simple_choice", "multiple_choice")
                    else (value[0] if value else "")
                )
        return self._save_answers(assignment_id, answers, submit=submit)

    @api.private
    def _portal_values(self, row):
        values = super()._portal_values(row)
        survey = row.evaluation_id.survey_id
        if not survey:
            return values
        values["online"] = True
        attempt = (
            self.env["survey.user_input"]
            .sudo()
            .search(
                [
                    ("training_evaluation_assignment_id", "=", row.id),
                    ("training_evaluation_number", "=", row.attempt_number),
                ],
                limit=1,
            )
        )
        if attempt and values["own"]:
            attempt = self._native_attempt(attempt.id)
            values.update(submitted=attempt.state == "done", state=self._state_label(row), revision=row.revision)
        if not attempt:
            return values
        if values["own"] and attempt.state != "done":
            questions = []
            for question in attempt.predefined_question_ids.sorted(lambda q: (q.sequence, q.id)):
                lines = attempt.user_input_line_ids.filtered(lambda line: line.question_id == question)
                questions.append(
                    {
                        "id": question.id,
                        "title": question.title,
                        "type": question.question_type,
                        "choices": [
                            {
                                "id": choice.id,
                                "label": choice.value_label,
                                "selected": choice in lines.suggested_answer_id,
                            }
                            for choice in question.suggested_answer_ids
                        ],
                        "text": lines[:1].value_text_box or lines[:1].value_char_box or "",
                    }
                )
            values["questions"] = questions
        if values["can_evaluate"] and attempt.state == "done":
            values["proposed_score"] = attempt.scoring_percentage if row.evaluation_id.scored else None
            values["review_answers"] = [
                {
                    "question": q.title,
                    "answer": ", ".join(
                        attempt.user_input_line_ids.filtered(lambda line: line.question_id == q).mapped(
                            "suggested_answer_id.value_label"
                        )
                    )
                    or "\n".join(
                        (line.value_text_box or line.value_char_box or "")
                        for line in attempt.user_input_line_ids.filtered(lambda line: line.question_id == q)
                    ),
                }
                for q in attempt.predefined_question_ids
            ]
        return values
