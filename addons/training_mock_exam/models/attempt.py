"""Native Survey evidence, exact scoring and strict server-owned deadlines."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class Attempt(models.Model):
    _inherit = "survey.user_input"  # pylint: disable=consider-merging-classes-inherited  # boundary and engine transitions are separate concerns

    mock_reader_group_id = fields.Many2one("res.groups", readonly=True, copy=False, ondelete="restrict")
    # Capture at the authorized factory. A new stored related field would
    # recompute old native answers and change their audit timestamps on upgrade.
    mock_company_id = fields.Many2one("res.company", readonly=True, copy=False, index=True)
    mock_context_key = fields.Char(readonly=True, copy=False, index=True)
    training_family_id = fields.Many2one("survey.survey", readonly=True, ondelete="restrict", index=True, copy=False)
    training_review_ids = fields.Many2many(
        "survey.question",
        "training_exam_review_rel",
        "attempt_id",
        "question_id",
        string="Marked for Review",
        readonly=True,
        copy=False,
    )
    training_adjustment_ids = fields.One2many("training.exam.revision", "attempt_id", readonly=True)
    mock_revision_serial = fields.Integer(readonly=True, copy=False, default=0)

    @api.private
    def _mock_revision_scope(self, *, lock=False):
        raise AccessError(self.env._("This exam context does not authorize result revisions."))

    @api.private
    def _mock_revision_project(self):
        return True

    _mock_context_active = models.UniqueIndex(
        "(partner_id, training_family_id, mock_context_key) WHERE mock_context_key IS NOT NULL AND state != 'done'",
        "Resume the active attempt in this context before starting another one.",
    )

    @api.private
    def _mock_exam_records(self):
        return self.filtered("mock_context_key")

    @api.ondelete(at_uninstall=False)
    def _mock_keep_attempts(self):
        if self._mock_exam_records():
            raise ValidationError(self.env._("Keep the exam history."))

    @api.private
    def _mock_close_if_expired(self):
        self.ensure_one()
        self.lock_for_update()
        self.invalidate_recordset()
        if self.state != "done" and self.deadline <= fields.Datetime.now():
            self._training_finish()
        return self

    @api.depends(
        "user_input_line_ids.answer_score",
        "user_input_line_ids.suggested_answer_id",
        "predefined_question_ids",
        "survey_id",
        "mock_context_key",
    )
    def _compute_scoring_values(self):
        result = super()._compute_scoring_values()
        for attempt in self._mock_exam_records():
            rows = attempt._training_scores()
            total = sum(row["maximum"] for row in rows)
            obtained = sum(row["points"] for row in rows)
            attempt.scoring_total = obtained
            # No rounding before the inclusive threshold comparison.
            attempt.scoring_percentage = 100 * obtained / total if total else 0

        return result

    @api.private
    def _training_scores(self):
        self.ensure_one()
        rows = []
        for question in self.predefined_question_ids.sorted(lambda q: (q.sequence, q.id)):
            selected = self.user_input_line_ids.filtered(lambda line: line.question_id == question).suggested_answer_id
            correct = question.suggested_answer_ids.filtered("is_correct")
            rows.append(
                {
                    "question": question,
                    "selected": selected,
                    "correct": correct,
                    "points": question.answer_score if selected and set(selected.ids) == set(correct.ids) else 0,
                    "maximum": question.answer_score,
                }
            )
        return rows

    @api.private
    def _training_finish(self):
        for attempt in self:
            if attempt.state != "done":
                attempt._training_store(
                    {
                        "state": "done",
                        "end_datetime": min(fields.Datetime.now(), attempt.deadline),
                    }
                )

    @api.model
    def _mock_expire_domain(self, domain):
        candidates = self.sudo().search(
            domain + [("state", "!=", "done"), ("deadline", "<=", fields.Datetime.now())], limit=100
        )
        for candidate in candidates:
            with self.env.cr.savepoint():
                locked = candidate.try_lock_for_update()
                if locked:
                    locked.invalidate_recordset()
                    if locked.state != "done" and locked.deadline <= fields.Datetime.now():
                        locked._training_finish()

    @api.model
    def _cron_mock_expire(self):
        self._mock_expire_domain([("mock_context_key", "!=", False)])


class AnswerLine(models.Model):
    _inherit = "survey.user_input.line"  # pylint: disable=consider-merging-classes-inherited  # boundary and engine transitions are separate concerns

    @api.depends("suggested_answer_id", "user_input_id", "question_id.answer_score")
    def _compute_answer_score(self):
        result = super()._compute_answer_score()
        for line in self.filtered(lambda line: line.user_input_id._mock_exam_records()):
            question = line.question_id
            lines = line.user_input_id.user_input_line_ids.filtered(lambda item: item.question_id == question)
            selected = lines.suggested_answer_id
            correct = question.suggested_answer_ids.filtered("is_correct")
            exact = bool(selected) and set(selected.ids) == set(correct.ids)
            line.answer_is_correct = exact
            # Allocate question points once, retaining native answer lines.
            line.answer_score = question.answer_score if exact and line == lines[:1] else 0
        return result

    @api.private
    def _training_mutable(self, attempts):
        if attempts._mock_exam_records().filtered(lambda a: not self.env.su or a.state == "done"):
            raise AccessError(self.env._("Use the checked exam operations; completed answers are immutable."))

    @api.model_create_multi
    def create(self, vals_list):
        self._training_mutable(
            self.env["survey.user_input"].browse(
                list(
                    filter(
                        None,
                        [v.get("user_input_id") or self.env.context.get("default_user_input_id") for v in vals_list],
                    )
                )
            )
        )
        return super().create(vals_list)

    def write(self, vals):
        self._training_mutable(self.user_input_id)
        if vals.get("user_input_id"):
            self._training_mutable(self.env["survey.user_input"].browse(vals["user_input_id"]))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _training_keep_answers(self):
        self._training_mutable(self.user_input_id)
