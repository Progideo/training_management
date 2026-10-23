"""Native Survey storage with a separate, inaccessible one-use ledger.

Anonymous inputs contain no invitation, identity, personal author or submission
clock. The ledger has no answer pointer or technical timestamps. Only privileged
technical support can inspect it; business users cannot query completion.
"""

import hashlib
import hmac

from odoo import api, fields, models, SUPERUSER_ID
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.training_management.models.training_evaluation import clean_context


class Feedback(models.Model):
    _inherit = "training.feedback"

    survey_id = fields.Many2one("survey.survey", ondelete="restrict", copy=False)
    indicator_question_id = fields.Many2one("survey.question", string="Satisfaction Indicator")
    favorable_answer_ids = fields.Many2many("survey.question.answer", string="Favorable Choices")

    def action_questionnaire(self):
        self.ensure_one()
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        self.lock_for_update()
        if not self.survey_id:
            if self.state != "draft":
                raise ValidationError(self.env._("Create a new feedback version first."))
            self.survey_id = self.env["survey.survey"].create(
                {
                    "title": self.name,
                    "training_program_id": self.program_id.id,
                    "training_feedback_id": self.id,
                    "training_version": self.version,
                    "survey_type": "custom",
                    "scoring_type": "no_scoring",
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
        survey = self.survey_id
        if not survey or survey.training_feedback_id != self or survey.training_program_id != self.program_id:
            raise ValidationError(self.env._("Choose the questionnaire belonging to this feedback version."))
        if self.indicator_question_id:
            question = self.indicator_question_id
            if (
                question not in survey.question_ids
                or question.question_type != "simple_choice"
                or not self.favorable_answer_ids
                or self.favorable_answer_ids - question.suggested_answer_ids
            ):
                raise ValidationError(self.env._("Choose a single-choice indicator and its favorable choices."))
        elif self.favorable_answer_ids:
            raise ValidationError(self.env._("Choose the satisfaction indicator question."))
        survey.action_training_publish()
        return True

    def copy(self, default=None):
        new = super().copy({"indicator_question_id": False, "favorable_answer_ids": [], **(default or {})})
        if self.survey_id:
            new.survey_id = self.survey_id.copy(
                {
                    "training_feedback_id": new.id,
                    "training_version": new.version,
                    "training_origin_id": (self.survey_id.training_origin_id or self.survey_id).id,
                    "training_revision_reason": "New feedback version",
                }
            )
        return new


class FeedbackSurvey(models.Model):
    _inherit = "survey.survey"

    training_feedback_id = fields.Many2one("training.feedback", ondelete="restrict", copy=False)

    @api.constrains("training_feedback_id", "training_program_id", "training_evaluation_id")
    def _check_feedback_program(self):
        for survey in self.filtered("training_feedback_id"):
            if survey.training_feedback_id.program_id != survey.training_program_id or survey.training_evaluation_id:
                raise ValidationError(self.env._("Use a distinct feedback questionnaire in its programme."))


class FeedbackSpent(models.Model):
    _name = "training.feedback.spent"
    _description = "Private Anonymous Anti-Replay Ledger"
    _log_access = False

    campaign_id = fields.Many2one("training.feedback.campaign", required=True, ondelete="restrict")
    digests = fields.Json(default=list, required=True)
    _one_use = models.Constraint("UNIQUE(campaign_id)", "One unordered anti-replay pool per campaign.")

    # No ACL: not even a business administrator can inspect this technical ledger.
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(self.env._("Private technical ledger."))
        return super().create(vals_list)


class FeedbackInput(models.Model):
    _inherit = "survey.user_input"

    training_feedback_campaign_id = fields.Many2one(
        "training.feedback.campaign", ondelete="restrict", readonly=True, copy=False
    )
    training_feedback_recipient_id = fields.Many2one(
        "training.feedback.recipient", ondelete="restrict", readonly=True, copy=False
    )

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        # Native ID-only export otherwise skips field reads and record rules.
        self.check_access("read")
        return super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)

    def write(self, vals):
        if self.filtered("training_feedback_campaign_id"):
            raise AccessError(self.env._("Feedback responses are immutable."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _keep_feedback(self):
        if self.filtered("training_feedback_campaign_id"):
            raise AccessError(self.env._("Retain collected feedback."))


class FeedbackLine(models.Model):
    _inherit = "survey.user_input.line"

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        self.check_access("read")
        return super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)

    @api.private
    def _training_mutable(self, attempts):
        if attempts.filtered(lambda x: x.training_feedback_campaign_id and (not self.env.su or x.state == "done")):
            raise AccessError(self.env._("Feedback responses are immutable."))
        return super()._training_mutable(attempts)


class FeedbackService(models.AbstractModel):
    _inherit = "training.feedback.service"

    @api.private
    def _spent_digest(self, campaign, recipient):
        # database.secret is the existing native per-database secret, never exported.
        secret = self.env["ir.config_parameter"].sudo().get_str("database.secret")
        if not secret:
            raise ValidationError(self.env._("The native database secret is unavailable."))
        return hmac.new(
            secret.encode(), f"feedback:{campaign.id}:{recipient.user_id.id}:{recipient.role}".encode(), hashlib.sha256
        ).hexdigest()

    @api.private
    def _submit(self, campaign_id, role, answers, *, submit=True):
        with self.env.cr.savepoint():
            return self._submit_checked(campaign_id, role, answers, submit=submit)

    @api.private
    def _submit_checked(self, campaign_id, role, answers, *, submit=True):
        campaign = self._campaign(campaign_id, lock=True)
        now = fields.Datetime.now()
        if (
            campaign.state != "open"
            or not campaign.opens_at <= now <= campaign.due_at
            or not campaign.feedback_id.survey_id.active
        ):
            raise ValidationError(self.env._("This feedback campaign is not open."))
        recipient = campaign.recipient_ids.filtered(
            lambda x: x.user_id == self.env.user and x.role == role and x._eligible()
        )
        if len(recipient) != 1:
            raise AccessError(self.env._("This feedback invitation is unavailable."))
        attempts = (
            clean_context(self.env["survey.user_input"])
            .with_user(SUPERUSER_ID)
            .with_context(mail_create_nolog=True, mail_create_nosubscribe=True, tracking_disable=True)
        )
        spent = self.env["training.feedback.spent"].sudo()
        pool = spent.search([("campaign_id", "=", campaign.id)], limit=1)
        attempt = attempts.browse()
        if campaign.anonymous:
            if not submit:
                raise ValidationError(self.env._("Anonymous answers are submitted together, without a named draft."))
            digest = self._spent_digest(campaign, recipient)
            if pool and digest in pool.digests:
                return True  # same generic acknowledgment, no response/status/id returned
        else:
            attempt = attempts.search([("training_feedback_recipient_id", "=", recipient.id)], limit=1)
            if attempt and attempt.state == "done":
                return True
        survey = campaign.feedback_id.survey_id
        survey.lock_for_update()
        survey.invalidate_recordset(["active"])
        if not survey.active:
            raise ValidationError(self.env._("This questionnaire is archived."))
        questions = survey.question_ids
        if set(answers) - set(questions.ids):
            raise ValidationError(self.env._("Use questions from this questionnaire."))
        normalized = {}
        for question in questions:
            value = answers.get(question.id)
            if question.question_type in ("simple_choice", "multiple_choice"):
                values = [int(x) for x in (value or [])]
                if (
                    len(values) != len(set(values))
                    or not set(values) <= set(question.suggested_answer_ids.ids)
                    or (question.question_type == "simple_choice" and len(values) > 1)
                ):
                    raise ValidationError(self.env._("Choose answers from this question."))
                value = str(values[0]) if question.question_type == "simple_choice" and values else values
            else:
                value = str(value or "")[:20000]
            if submit and (
                question.validate_question(value)
                or (question.constr_mandatory and (not value or (isinstance(value, str) and not value.strip())))
            ):
                raise ValidationError(self.env._("Complete the required answers before submitting."))
            normalized[question.id] = value
        clock = campaign.opens_at if campaign.anonymous else now
        if submit and not any(normalized.values()):
            raise ValidationError(self.env._("Provide at least one answer before submitting."))
        attempt = attempt or attempts._training_create(
            {
                "survey_id": survey.id,
                "training_feedback_campaign_id": campaign.id,
                "training_feedback_recipient_id": False if campaign.anonymous else recipient.id,
                "partner_id": False if campaign.anonymous else recipient.user_id.partner_id.id,
                "email": False,
                "nickname": False,
                "invite_token": False,
                "start_datetime": False if campaign.anonymous else now,
                "deadline": campaign.due_at,
                "state": "in_progress",
                "create_date": clock,
                "write_date": clock,
                "predefined_question_ids": [(6, 0, questions.ids)],
            }
        )
        for question in questions:
            attempt._save_lines(question, normalized[question.id])
        if campaign.anonymous:
            # A single sorted set, not one sequential row per respondent: no
            # submission order or response pointer is persisted in the ledger.
            if pool:
                pool.write({"digests": sorted([*pool.digests, digest])})
            else:
                spent.create({"campaign_id": campaign.id, "digests": [digest]})
        attempt._training_store(
            {
                "state": "done" if submit else "in_progress",
                "end_datetime": now if submit and not campaign.anonymous else False,
                "write_date": clock,
            }
        )
        if campaign.anonymous:
            # The ORM forces log-access clocks even for a neutral technical author.
            # Normalize only these completed private rows, inside the same transaction.
            # Necessary to remove submission timing from persistent answer metadata.
            attempt.flush_recordset()
            attempt.user_input_line_ids.flush_recordset()
            self.env.cr.execute(
                "UPDATE survey_user_input SET create_date=%s, write_date=%s WHERE id=%s",
                (clock, clock, attempt.id),
            )
            self.env.cr.execute(
                "UPDATE survey_user_input_line SET create_date=%s, write_date=%s WHERE user_input_id=%s",
                (clock, clock, attempt.id),
            )
            attempt.invalidate_recordset(["create_date", "write_date"])
            attempt.user_input_line_ids.invalidate_recordset(["create_date", "write_date"])
        return True

    @api.private
    def _nominative_state(self, recipient):
        if recipient.exclusion_reason:
            return "not_applicable"
        answers = (
            self.env["survey.user_input"]
            .sudo()
            .search([("training_feedback_recipient_id", "=", recipient.id)], limit=1)
        )
        if answers and answers.state == "done":
            return "received"
        if answers:
            return "no_response" if fields.Datetime.now() > recipient.campaign_id.due_at else "in_progress"
        notices = recipient.campaign_id.notice_ids.filtered(lambda x: x.recipient_id == recipient and x.mail_id)
        if not notices:
            return "not_invited"
        states = notices.mail_id.mapped("state")
        if "sent" in states:
            return "no_response" if fields.Datetime.now() > recipient.campaign_id.due_at else "invited"
        return "queued" if "outgoing" in states else "invitation_error"

    @api.private
    def _build_snapshot(self, campaign):
        attempts = (
            self.env["survey.user_input"]
            .sudo()
            .search([("training_feedback_campaign_id", "=", campaign.id), ("state", "=", "done")])
        )
        if campaign.anonymous and len(attempts) < 3:
            return {"insufficient": True}  # no small counts or per-person subtraction
        feedback = campaign.feedback_id
        applicable = len(
            campaign.with_context(active_test=False).recipient_ids.filtered(lambda x: not x.exclusion_reason)
        )
        snapshot = {
            "received": len(attempts),
            "expected": len(campaign.with_context(active_test=False).recipient_ids),
            "applicable": applicable,
            "formula": "S092-1",
            "version": feedback.version,
            "population": campaign.population,
            "opens_at": str(campaign.opens_at),
            "due_at": str(campaign.due_at),
            "questions": [],
        }
        lines = attempts.user_input_line_ids
        for question in feedback.survey_id.question_ids:
            answered = lines.filtered(lambda x: x.question_id == question and not x.skipped)
            snapshot["questions"].append(
                {
                    "title": question.title,
                    "valid": len(answered.user_input_id),
                    "choices": [
                        {
                            "label": choice.value_label,
                            "count": len(answered.filtered(lambda x: x.suggested_answer_id == choice)),
                        }
                        for choice in question.suggested_answer_ids
                    ],
                }
            )
        indicator = feedback.indicator_question_id
        if indicator:
            valid = lines.filtered(lambda x: x.question_id == indicator and not x.skipped)
            favorable = valid.filtered(lambda x: x.suggested_answer_id in feedback.favorable_answer_ids)
            snapshot.update(
                valid=len(valid), favorable=len(favorable), rate=100 * len(favorable) / len(valid) if valid else None
            )
        return snapshot

    @api.private
    def _own_answers(self, campaign):
        # Anonymous GET never queries the ledger or response table.
        if campaign.anonymous:
            return {}, False
        recipients = campaign.recipient_ids.filtered(lambda x: x.user_id == self.env.user and x._eligible())
        attempt = (
            self.env["survey.user_input"]
            .sudo()
            .search(
                [
                    ("training_feedback_campaign_id", "=", campaign.id),
                    ("training_feedback_recipient_id", "in", recipients.ids),
                ],
                limit=1,
            )
        )
        values = {}
        for q in campaign.feedback_id.survey_id.question_ids:
            lines = attempt.user_input_line_ids.filtered(lambda x: x.question_id == q and not x.skipped)
            values["q_%s" % q.id] = (
                [str(x) for x in lines.suggested_answer_id.ids]
                if q.question_type in ("simple_choice", "multiple_choice")
                else [lines[:1].value_text_box or lines[:1].value_char_box or ""]
            )
        return values, bool(attempt and attempt.state == "done")

    @api.private
    def _named_details(self, campaign):
        # Business readers see collective results. Only coordination or the
        # assigned quality reviewer can inspect submitted nominative feedback.
        user = self.env.user
        if campaign.anonymous or not (
            user.has_group("training_management.group_training_coordinator")
            or (
                user.has_group("training_management.group_training_quality")
                and campaign.delivery_id.evaluation_quality_id == user
            )
        ):
            return []
        attempts = (
            self.env["survey.user_input"]
            .sudo()
            .search([("training_feedback_campaign_id", "=", campaign.id), ("state", "=", "done")])
        )
        return [
            {
                "name": a.partner_id.name,
                "answers": [
                    {
                        "question": q.title,
                        "value": ", ".join(
                            a.user_input_line_ids.filtered(lambda x: x.question_id == q).suggested_answer_id.mapped(
                                "value_label"
                            )
                        )
                        or "\n".join(
                            (x.value_text_box or x.value_char_box or "")
                            for x in a.user_input_line_ids.filtered(lambda x: x.question_id == q)
                        ),
                    }
                    for q in campaign.feedback_id.survey_id.question_ids
                ],
            }
            for a in attempts
        ]
