"""Append-only result corrections, authorized by the actual business context."""

import math
from uuid import UUID

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class Revision(models.Model):
    _name = "training.exam.revision"
    _description = "Motivated Exam Result Revision"
    _order = "id desc"

    attempt_id = fields.Many2one("survey.user_input", required=True, ondelete="restrict", readonly=True, index=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True, ondelete="restrict", index=True)
    reason = fields.Text(required=True, readonly=True)
    revised_at = fields.Datetime(readonly=True, copy=False)
    points_by_question = fields.Json(required=True, readonly=True)
    author_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    previous_id = fields.Many2one("training.exam.revision", readonly=True, ondelete="restrict")
    request_key = fields.Char(readonly=True, copy=False)
    _one_request = models.Constraint("UNIQUE(request_key)", "A result revision request is unique.")

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Use the motivated result revision action."))

    def write(self, vals):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Result revisions are immutable."))

    @api.ondelete(at_uninstall=False)
    def _keep_revisions(self):
        raise AccessError(self.env._("Result revisions are immutable."))

    @api.private
    def _record(self, attempt, points, reason, *, request_key=None, expected_previous=None):
        if not self.env.user.active or self.env.user._is_public():
            raise AccessError(self.env._("An active exam coordinator is required."))
        # Never inherit sudo or a different actor from a caller's recordset.
        attempt = self.env["survey.user_input"].with_env(self.env(su=False)).browse(attempt.id).exists()
        if not attempt:
            raise AccessError(self.env._("This exam attempt is unavailable."))
        with self.env.cr.savepoint():
            policy = attempt._mock_revision_scope(lock=True)
            attempt = attempt.sudo()
            attempt.lock_for_update()
            attempt.invalidate_recordset()
            expected = {str(question.id): question.answer_score for question in attempt.predefined_question_ids}
            if (
                attempt.state != "done"
                or not isinstance(reason, str)
                or not reason.strip()
                or type(points) is not dict
                or set(points) != set(expected)
            ):
                raise ValidationError(self.env._("Provide a reason and points for every completed question."))
            if any(
                type(value) not in (int, float) or not 0 <= value <= expected[key] or not math.isfinite(value)
                for key, value in points.items()
            ):
                raise ValidationError(self.env._("Revised points must be between zero and the question maximum."))
            if request_key is not None:
                try:
                    if str(UUID(request_key)) != request_key:
                        raise ValueError("Noncanonical request")
                except (ValueError, TypeError, AttributeError) as error:
                    raise ValidationError(self.env._("Use a valid result revision request.")) from error
            # A real write fence rejects an old Repeatable Read snapshot before
            # looking up the preceding event. Original answers/scores stay intact.
            attempt._training_store({"mock_revision_serial": attempt.mock_revision_serial + 1})
            revisions = self.sudo().with_context({})  # pylint: disable=context-overridden
            if request_key:
                existing = revisions.search([("request_key", "=", request_key)], limit=1)
                if existing:
                    if (
                        existing.attempt_id != attempt
                        or existing.points_by_question != points
                        or existing.reason != reason.strip()
                    ):
                        raise ValidationError(self.env._("This revision request has different contents."))
                    return existing
            previous = revisions.search([("attempt_id", "=", attempt.id)], limit=1)
            if expected_previous is not None and expected_previous != (previous.id or 0):
                raise ValidationError(
                    self.env._("The result has been revised. Reload before applying another correction.")
                )
            # Private append-only factory after actual context authorization.
            # pylint: disable-next=super-method-mismatch
            revision = super(Revision, revisions).create(
                {
                    "attempt_id": attempt.id,
                    "company_id": policy["company"].id,
                    "points_by_question": points,
                    "reason": reason.strip(),
                    "revised_at": fields.Datetime.now(),
                    "author_id": self.env.uid,
                    "previous_id": previous.id,
                    "request_key": request_key,
                }
            )
            attempt.with_env(self.env(su=False))._mock_revision_project()
            return revision
