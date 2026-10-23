"""EVA02: versioned feedback, administrative populations and immutable closures."""

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_evaluation import COORDINATOR, clean_context


class Feedback(models.Model):
    _name = "training.feedback"
    _description = "Feedback Questionnaire Version"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    program_id = fields.Many2one("training.program.version", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="program_id.company_id", store=True)
    purpose = fields.Selection(
        [
            ("immediate", "Immediate Satisfaction"),
            ("delayed", "Delayed Satisfaction"),
            ("instructor", "Instructor Feedback"),
            ("sponsor", "Sponsor Feedback"),
        ],
        required=True,
    )
    anonymous = fields.Boolean(default=True)
    version = fields.Char(required=True, default="1")
    criteria = fields.Text(required=True, translate=True)
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")], default="draft", readonly=True, copy=False
    )
    previous_id = fields.Many2one("training.feedback", readonly=True, copy=False, ondelete="restrict")

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.delivery"]._require_coordinator()
        if any(set(v) & {"state", "previous_id"} for v in vals_list):
            raise AccessError(self.env._("Use the feedback publication actions."))
        return super(Feedback, clean_context(self)).create(vals_list)

    def write(self, vals):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()
        if self.filtered(lambda x: x.state != "draft") or set(vals) & {"state", "previous_id"}:
            raise ValidationError(self.env._("Published feedback is immutable; create a new version."))
        return super().write(vals)

    def action_publish(self):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        self.lock_for_update()
        for row in self.filtered(lambda x: x.state == "draft"):
            if not (row.criteria or "").strip():
                raise ValidationError(self.env._("Describe the completion criteria."))
            row._publish_questionnaire()
            super(Feedback, row).write({"state": "published"})  # pylint: disable=super-method-mismatch
        return True

    @api.private
    def _publish_questionnaire(self):
        raise ValidationError(self.env._("Install the native Surveys integration to collect feedback."))

    def action_new_version(self):
        self.ensure_one()
        self.env["training.delivery"]._require_coordinator()
        self.check_access("read")
        if self.state != "published":
            raise ValidationError(self.env._("Publish the source first."))
        new = self.copy({"version": self.version + "+"})
        super(Feedback, new).write({"previous_id": self.id})  # pylint: disable=super-method-mismatch
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": new.id, "view_mode": "form"}

    @api.ondelete(at_uninstall=False)
    def _keep_versions(self):
        if self.filtered(lambda x: x.state == "published"):
            raise ValidationError(self.env._("Retain published feedback versions."))


class Campaign(models.Model):
    _name = "training.feedback.campaign"
    _description = "Training Feedback Campaign"
    _check_company_auto = True

    name = fields.Char(required=True)
    feedback_id = fields.Many2one("training.feedback", required=True, ondelete="restrict", check_company=True)
    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    anonymous = fields.Boolean(related="feedback_id.anonymous")
    purpose = fields.Selection(related="feedback_id.purpose")
    population = fields.Text(required=True, help="Inclusion criteria retained with the campaign.")
    retention_id = fields.Many2one(
        "training.retention.category", required=True, ondelete="restrict", check_company=True
    )
    opens_at = fields.Datetime(required=True, default=fields.Datetime.now)
    due_at = fields.Datetime(required=True)
    reminder_days = fields.Integer(default=7, help="Zero disables scheduled collective reminders.")
    recipient_ids = fields.One2many("training.feedback.recipient", "campaign_id", copy=False)
    notice_ids = fields.One2many("training.feedback.notice", "campaign_id", readonly=True, copy=False)
    state = fields.Selection(
        [("draft", "Draft"), ("open", "Open"), ("closed", "Closed")], default="draft", readonly=True, copy=False
    )
    closed_at = fields.Datetime(readonly=True, copy=False)
    snapshot = fields.Json(readonly=True, copy=False, groups=COORDINATOR)
    summary = fields.Text(compute="_compute_summary")
    previous_id = fields.Many2one("training.feedback.campaign", readonly=True, copy=False, ondelete="restrict")

    @api.depends("state", "snapshot")
    def _compute_summary(self):
        for campaign in self:
            campaign.summary = self.env["training.feedback.service"]._summary_text(campaign)

    @api.private
    def _store(self, vals):
        return super().write(vals)  # pylint: disable=super-method-mismatch  # checked private campaign transition

    @api.private
    def _lock(self):
        self.ensure_one()
        self.delivery_id._serialize()
        self.lock_for_update()
        self.invalidate_recordset()

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.delivery"]._require_coordinator()
        if any(set(v) & {"state", "closed_at", "snapshot", "previous_id"} for v in vals_list):
            raise AccessError(self.env._("Use the campaign actions."))
        return super(Campaign, clean_context(self)).create(vals_list)

    def write(self, vals):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        for campaign in self:
            campaign._lock()
            if campaign.state != "draft" or set(vals) & {"state", "snapshot", "closed_at", "previous_id"}:
                raise ValidationError(self.env._("Keep opened campaign settings and closed snapshots unchanged."))
        return super().write(vals)

    @api.constrains("due_at", "opens_at", "reminder_days", "feedback_id", "delivery_id", "retention_id")
    def _check_campaign(self):
        for row in self:
            if row.retention_id and not row.retention_id.approved_at:
                raise ValidationError(self.env._("Choose an approved retention policy."))
            if (
                row.due_at <= row.opens_at
                or row.reminder_days < 0
                or row.feedback_id.program_id != row.delivery_id.program_id
            ):
                raise ValidationError(
                    self.env._("Use the delivery programme, a valid period and nonnegative reminders.")
                )

    def action_export_proof(self):
        self.ensure_one()
        self.env["training.feedback.service"]._campaign(self.id, staff=True)
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.feedback.export",
            "view_mode": "form",
            "target": "new",
            "context": {"default_campaign_id": self.id},
        }

    def action_summary(self):
        self.ensure_one()
        self.env["training.feedback.service"]._campaign(self.id, staff=True)
        return {"type": "ir.actions.act_url", "url": "/my/training-feedback/%s/summary" % self.id, "target": "self"}

    def action_open(self):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        for row in self:
            row._lock()
            if row.state != "draft":
                continue
            if row.feedback_id.state != "published" or not row.recipient_ids or row.due_at <= fields.Datetime.now():
                raise ValidationError(self.env._("Choose a published version, recipients and a future deadline."))
            row._store({"state": "open"})
        return True

    def action_invite(self):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        for row in self:
            row._lock()
            row._queue("invitation")
        return True

    def action_remind(self):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        for row in self:
            row._lock()
            occurrence = fields.Date.to_string(fields.Date.today())
            row._queue("reminder:" + occurrence)
        return True

    @api.private
    def _queue(self, occurrence):
        now = fields.Datetime.now()
        if self.state != "open" or not self.opens_at <= now <= self.due_at:
            raise ValidationError(self.env._("This feedback campaign is not open."))
        for recipient in self.recipient_ids:
            if recipient._eligible() and not recipient.exclusion_reason:
                # Anonymous reminders never inspect the spent ledger or answers.
                if not self.anonymous and recipient._nominative_state() == "received":
                    continue
                self.env["training.feedback.notice"]._queue(recipient, occurrence)

    def action_close(self):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        for row in self:
            row._lock()
            if row.state != "open":
                continue
            summary = self.env["training.feedback.service"]._build_snapshot(row)
            row._store({"snapshot": summary, "state": "closed", "closed_at": fields.Datetime.now()})
        return True

    def action_new_collection(self):
        """A new editable collection preserves the old deadline and nonresponses."""
        self.ensure_one()
        self.env["training.delivery"]._require_coordinator()
        self.check_access("read")
        if self.state != "closed":
            raise ValidationError(self.env._("Close this collection first."))
        new = self.copy(
            {
                "opens_at": fields.Datetime.now(),
                "due_at": fields.Datetime.now() + timedelta(days=7),
                "recipient_ids": [
                    (0, 0, {"user_id": r.user_id.id, "role": r.role, "enrollment_id": r.enrollment_id.id})
                    for r in self.recipient_ids
                    if r._eligible()
                ],
            }
        )
        new._store({"previous_id": self.id})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": new.id, "view_mode": "form"}

    @api.model
    def _cron_remind(self):
        # Privileged scheduler, same checked transport as manual queueing.
        for row in self.sudo().search([("state", "=", "open"), ("due_at", ">=", fields.Datetime.now())]):
            with self.env.cr.savepoint():
                row._lock()
                if row.state != "open" or row.opens_at > fields.Datetime.now():
                    continue
                row._queue("invitation")
                if not row.reminder_days or row.opens_at + timedelta(days=row.reminder_days) > fields.Datetime.now():
                    continue
                window = int((fields.Datetime.now() - row.opens_at).total_seconds() // (86400 * row.reminder_days))
                row._queue("scheduled:%s" % window)

    @api.ondelete(at_uninstall=False)
    def _keep_campaigns(self):
        if self.filtered(lambda x: x.state != "draft"):
            raise ValidationError(self.env._("Retain opened feedback campaigns."))


class Recipient(models.Model):
    _name = "training.feedback.recipient"
    _description = "Administrative Feedback Invitation"
    _check_company_auto = True

    campaign_id = fields.Many2one("training.feedback.campaign", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="campaign_id.company_id", store=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    role = fields.Selection(
        [("participant", "Participant"), ("instructor", "Instructor"), ("sponsor", "Sponsor")], required=True
    )
    enrollment_id = fields.Many2one("training.enrollment", ondelete="restrict", check_company=True)
    active = fields.Boolean(default=True)
    exclusion_reason = fields.Text(help="Reason for withdrawal or non-applicability.")
    response_state = fields.Selection(
        [
            ("anonymous", "Anonymous collection; individual response tracking unavailable"),
            ("not_invited", "Not Invited"),
            ("queued", "Invitation Queued"),
            ("invitation_error", "Invitation Error"),
            ("invited", "Invited"),
            ("in_progress", "In Progress"),
            ("received", "Response Received"),
            ("no_response", "No Response at Deadline"),
            ("not_applicable", "Not Applicable / Withdrawn"),
        ],
        compute="_compute_response_state",
    )
    _one_role = models.Constraint("UNIQUE(campaign_id, user_id, role)", "This recipient role is already invited.")

    @api.depends("campaign_id.state", "campaign_id.due_at", "campaign_id.anonymous", "active", "exclusion_reason")
    def _compute_response_state(self):
        for row in self:
            row.response_state = "anonymous" if row.campaign_id.anonymous else row._nominative_state()

    @api.private
    def _nominative_state(self):
        if self.campaign_id.anonymous:
            return self.env._("Anonymous collection; individual response tracking unavailable")
        return self.env["training.feedback.service"]._nominative_state(self)

    @api.private
    def _eligible(self):
        self.ensure_one()
        user = self.user_id
        campaign = self.campaign_id
        if (
            not self.active
            or self.exclusion_reason
            or not user.active
            or user._is_public()
            or campaign.company_id not in user.company_ids
        ):
            return False
        if self.role == "participant":
            enrollment = self.enrollment_id
            return bool(
                enrollment
                and enrollment.delivery_id == campaign.delivery_id
                and enrollment.user_id == user
                and enrollment.participant_id == user.partner_id
                and enrollment.state == "confirmed"
                and enrollment.access_state not in ("suspended", "revoked")
            )
        if self.role == "instructor":
            return self.env["training.evaluation.service"].with_user(user)._teaching_mission(campaign.delivery_id)
        # Explicit sponsor authorization is the active invitation, never client membership alone.
        return self.role == "sponsor"

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.delivery"]._require_coordinator()
        records = super(Recipient, clean_context(self)).create(vals_list)
        for row in records:
            row.campaign_id.check_access("write")
            row.campaign_id._lock()
            if row.campaign_id.state == "closed":
                raise ValidationError(self.env._("Retain the closed campaign population."))
            expected = "participant" if row.campaign_id.purpose in ("immediate", "delayed") else row.campaign_id.purpose
            if row.role != expected or not row._eligible():
                raise ValidationError(self.env._("Choose a currently eligible recipient in the campaign population."))
        return records

    def write(self, vals):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        for row in self:
            row.campaign_id._lock()
            if row.campaign_id.state == "closed" or set(vals) - {"active", "exclusion_reason"}:
                raise ValidationError(self.env._("Retain recipient identity; withdraw with a reason."))
            if not (vals.get("exclusion_reason") or row.exclusion_reason or "").strip():
                raise ValidationError(self.env._("Explain the population change."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _keep_recipients(self):
        if self.campaign_id.filtered(lambda x: x.state != "draft"):
            raise ValidationError(self.env._("Withdraw recipients instead of deleting invitations."))


class FeedbackService(models.AbstractModel):
    _name = "training.feedback.service"
    _description = "Scoped Feedback Operations"

    @api.private
    def _campaign(self, campaign_id, *, staff=False, lock=False):
        row = self.env["training.feedback.campaign"].sudo().browse(campaign_id).exists()
        user = self.env.user
        if not row or not user.active or user._is_public() or row.company_id not in user.company_ids:
            raise AccessError(self.env._("This feedback campaign is unavailable."))
        if staff:
            if not self.env["training.evaluation.service"]._staff(row.delivery_id):
                raise AccessError(self.env._("This feedback campaign is unavailable."))
        else:
            recipients = row.recipient_ids.filtered(lambda x: x.user_id == user and x._eligible())
            if not recipients:
                raise AccessError(self.env._("This feedback campaign is unavailable."))
        if lock:
            row._lock()
            return self._campaign(campaign_id, staff=staff)
        return row

    @api.private
    def _summary_text(self, campaign):
        # Called by an ORM compute under the caller; recheck scope before sudo snapshot.
        row = self._campaign(campaign.id, staff=True)
        if row.state != "closed":
            return self.env._("Summary available after closure")
        snapshot = row.snapshot or {}
        if snapshot.get("insufficient"):
            return self.env._("Insufficient responses (minimum 3)")
        return self.env._(
            "Received: %(received)s; expected: %(expected)s; applicable: %(applicable)s; formula: %(formula)s",
            **snapshot,
        )

    @api.private
    def _build_snapshot(self, campaign):
        raise ValidationError(self.env._("Install the native Surveys integration to collect feedback."))

    @api.private
    def _nominative_state(self, recipient):
        return self.env._("Not invited")


class FeedbackReport(models.AbstractModel):
    _name = "report.training_management.feedback_document"
    _description = "Frozen Feedback Campaign Summary"

    @api.model
    def _get_report_values(self, docids, data=None):
        service = self.env["training.feedback.service"]
        rows = []
        for campaign_id in docids:
            campaign = service._campaign(campaign_id, staff=True)
            if campaign.state != "closed":
                raise ValidationError(self.env._("Close the campaign before exporting its summary."))
            rows.append(
                {
                    "name": campaign.name,
                    "summary": service._summary_text(campaign),
                    "snapshot": None if campaign.snapshot.get("insufficient") else campaign.snapshot,
                }
            )
        return {"rows": rows}
