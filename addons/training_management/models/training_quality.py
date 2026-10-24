"""QUA01–02: dossier grants, immutable private history and separate effectiveness."""

import hashlib
import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain

from .training_evaluation import COORDINATOR, QUALITY, clean_context

QUALITY_MODELS = ("training.complaint", "training.improvement", "training.quality.event", "training.quality.file")


def required_text(value):
    return bool(value and value.strip())


class QualityDelivery(models.Model):
    _inherit = "training.delivery"

    complaint_quality_id = fields.Many2one("res.users", string="Complaint Intake Reviewer", groups=COORDINATOR)
    complaint_retention_id = fields.Many2one(
        "training.retention.category",
        string="Complaint Retention Policy",
        groups=COORDINATOR,
        check_company=True,
        ondelete="restrict",
    )
    complaint_response_days = fields.Integer(default=0, string="Complaint Response Target (Days)", groups=COORDINATOR)
    complaint_ids = fields.One2many("training.complaint", "delivery_id", groups=COORDINATOR + "," + QUALITY)

    @api.constrains("complaint_quality_id", "complaint_response_days")
    def _check_complaint_intake(self):
        for row in self:
            user = row.complaint_quality_id
            if row.complaint_response_days < 0 or (
                user and (not user.active or not user.has_group(QUALITY) or row.company_id not in user.company_ids)
            ):
                raise ValidationError(self.env._("Choose an active quality reviewer and a positive response target."))


class QualityRecord(models.AbstractModel):
    _name = "training.quality.record"
    _description = "Private Quality Dossier Rules"
    _check_company_auto = True

    name = fields.Char(required=True, string="Subject")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, ondelete="restrict"
    )
    delivery_id = fields.Many2one("training.delivery", ondelete="restrict", check_company=True)
    quality_id = fields.Many2one(
        "res.users",
        required=True,
        string="Assigned Quality Reviewer",
        default=lambda self: self.env.user if self.env.user.has_group(QUALITY) else False,
        ondelete="restrict",
    )
    member_ids = fields.Many2many(
        "res.users",
        string="Explicitly Authorized Staff",
        default=lambda self: self.env.user if not self.env.user.has_group(QUALITY) else self.env["res.users"],
    )
    responsible_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, ondelete="restrict"
    )
    retention_id = fields.Many2one(
        "training.retention.category", required=True, ondelete="restrict", check_company=True
    )
    confidentiality = fields.Selection(
        [("internal", "Internal / Assigned Staff"), ("sensitive", "Sensitive / Assigned Staff")],
        required=True,
        default="sensitive",
    )
    due_date = fields.Date(required=True)
    overdue = fields.Boolean(compute="_compute_overdue", search="_search_overdue")
    frozen = fields.Boolean(
        default=False, string="Legal Hold", help="Prevents content and workflow changes; no automatic purge."
    )

    def _compute_overdue(self):
        for row in self:
            row.overdue = row.state not in row._terminal_states() and row.due_date < fields.Date.context_today(row)

    @api.model
    def _search_overdue(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise ValidationError(self.env._("Use a boolean overdue filter."))
        domain = Domain.AND(
            [[("state", "not in", self._terminal_states())], [("due_date", "<", fields.Date.context_today(self))]]
        )
        return domain if value == (operator == "=") else ~domain

    @api.private
    def _terminal_states(self):
        return ("closed",) if self._name == "training.complaint" else ("effective", "ineffective")

    @api.private
    def _is_quality(self):
        self.ensure_one()
        user = self.env.user
        return user.has_group(QUALITY) and (
            self.quality_id == user or (self._name == "training.improvement" and self.complaint_id.quality_id == user)
        )

    @api.private
    def _authorize(self, quality=False, lock=True, mutating=True):
        self.ensure_one()
        self.with_env(self.env(su=False)).check_access("write")
        if lock:
            if self._name == "training.improvement" and self.complaint_id:
                self.complaint_id.lock_for_update()
            self.lock_for_update()
            self.env.invalidate_all()
            self.with_env(self.env(su=False)).check_access("write")
        if not self.env.user.active or (quality and not self._is_quality()):
            raise AccessError(self.env._("The quality reviewer explicitly assigned to this dossier is required."))
        if self.frozen and mutating:
            raise ValidationError(self.env._("This quality dossier is on legal hold."))

    @api.private
    def _event(self, operation, before=None, reason=None):
        # The operation was authorized before mutation; reassignment may remove
        # the actor's access. Elevate only this immutable post-operation snapshot.
        self.env["training.quality.event"]._append(self.sudo(), operation, before or {}, reason)

    @api.private
    def _snapshot(self):
        keys = self._editable_fields() | {
            "state",
            "name",
            "quality_id",
            "responsible_id",
            "member_ids",
            "due_date",
            "frozen",
        }
        keys |= (
            {"description", "complainant_id", "received_at", "resolved_at", "closed_at", "portal_revoked"}
            if self._name == "training.complaint"
            else {"implemented_at", "verified_at", "verifier_id", "verification", "follow_up"}
        )
        result = {}
        for key in sorted(keys):
            value = self[key]
            result[key] = value.ids if isinstance(value, models.BaseModel) else value
        return result

    @api.private
    def _editable_fields(self):
        return (
            {"treatment", "reply", "resolution_reason"}
            if self._name == "training.complaint"
            else {"decision", "implementation", "output_reference", "effectiveness_criterion", "verification_plan"}
        )

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.user.has_group(COORDINATOR) or self.env.user.has_group(QUALITY)):
            raise AccessError(self.env._("Only explicitly authorized staff may register quality dossiers."))
        common = {
            "name",
            "company_id",
            "delivery_id",
            "quality_id",
            "responsible_id",
            "member_ids",
            "retention_id",
            "due_date",
            "confidentiality",
        }
        specific = (
            {"enrollment_id", "complainant_id", "description", "channel", "portal_visible"}
            if self._name == "training.complaint"
            else {"complaint_id", "campaign_id", "origin", "origin_reference"}
        )
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if set(vals) - common - specific - self._editable_fields():
                raise AccessError(self.env._("Quality identities, workflow and audit fields are server controlled."))
            if vals.get("delivery_id"):
                delivery = self.env["training.delivery"].browse(vals["delivery_id"])
                delivery.check_access("read")
                if vals.get("company_id") and vals["company_id"] != delivery.company_id.id:
                    raise ValidationError(self.env._("Keep the delivery operating company."))
                vals["company_id"] = delivery.company_id.id
            if vals.get("enrollment_id"):
                self.env["training.enrollment"].browse(vals["enrollment_id"]).check_access("read")
            for model, key in (("training.complaint", "complaint_id"), ("training.feedback.campaign", "campaign_id")):
                if vals.get(key):
                    source = self.env[model].browse(vals[key])
                    if key == "complaint_id":
                        # Creation must serialize with removal of the source dossier grant.
                        source._authorize()
                    else:
                        source.check_access("read")
            prepared.append(vals)
        records = super(QualityRecord, clean_context(self)).create(prepared)
        for row in records:
            row.with_env(self.env(su=False)).check_access("read")
            row._event("registered")
        return records

    def write(self, vals):
        assignment = {"quality_id", "responsible_id", "member_ids", "due_date", "frozen"}
        if set(vals) - self._editable_fields() - assignment - {"file_ids"}:
            raise AccessError(self.env._("Keep original quality identities and use workflow actions."))
        for row in self.sorted("id"):
            # Legal holds may only be lifted by the assigned quality reviewer.
            if set(vals) == {"frozen"} and row.frozen:
                row.with_env(self.env(su=False)).check_access("write")
                row.lock_for_update()
                row.env.invalidate_all()
                row.with_env(self.env(su=False)).check_access("write")
                if not row._is_quality():
                    raise AccessError(self.env._("The assigned quality reviewer must release the legal hold."))
            else:
                row._authorize(quality=bool(set(vals) & assignment))
            if row.state in row._terminal_states() or (row._name == "training.complaint" and row.state == "resolved"):
                if set(vals) - assignment:
                    raise ValidationError(self.env._("Reopen the dossier with a reason before changing its treatment."))
            before = row._snapshot()
            super(QualityRecord, row).write(vals)
            row._event("updated", before)
            self.env.transaction.invalidate_access_cache()
        return True

    @api.constrains("quality_id", "member_ids", "responsible_id", "retention_id", "company_id", "due_date")
    def _check_quality_definition(self):
        for row in self:
            if row.company_id not in self.env.user.company_ids:
                raise AccessError(self.env._("This operating company is not authorized."))
            reviewer = row.quality_id
            if not reviewer.active or not reviewer.has_group(QUALITY) or row.company_id not in reviewer.company_ids:
                raise ValidationError(self.env._("Assign an active quality reviewer authorized for this company."))
            users = row.member_ids | reviewer
            if row.responsible_id not in users:
                raise ValidationError(self.env._("The responsible user must be explicitly authorized for the dossier."))
            for user in users:
                if (
                    not user.active
                    or user.share
                    or row.company_id not in user.company_ids
                    or not (user.has_group(QUALITY) or user.has_group(COORDINATOR))
                ):
                    raise ValidationError(
                        self.env._("Authorize only active quality or coordination staff in this company.")
                    )
            if not row.retention_id.approved_at:
                raise ValidationError(self.env._("Choose an approved retention policy."))

    @api.private
    def _transition(self, state, reason=None, **values):  # pylint: disable=super-method-mismatch  # Controlled state factory.
        before = self._snapshot()
        super(QualityRecord, self).write(dict(values, state=state))  # pylint: disable=super-method-mismatch
        self._event(state, before, reason)
        return True

    @api.ondelete(at_uninstall=False)
    def _keep_quality_history(self):
        raise ValidationError(self.env._("Keep quality dossiers and their history; no automatic purge."))

    def action_export_proof(self):
        self._authorize(quality=True, mutating=False)
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.quality.export",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_" + ("complaint_id" if self._name == "training.complaint" else "improvement_id"): self.id
            },
        }


class Complaint(models.Model):
    _name = "training.complaint"
    _inherit = "training.quality.record"
    _description = "Confidential Training Complaint"
    _order = "id desc"

    submission_key = fields.Char(readonly=True, copy=False, groups=COORDINATOR + "," + QUALITY)
    _unique_submission = models.Constraint(
        "UNIQUE(enrollment_id, submission_key)", "This complaint was already received."
    )

    enrollment_id = fields.Many2one("training.enrollment", ondelete="restrict", check_company=True)
    complainant_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    description = fields.Text(required=True, string="Original Complaint")
    channel = fields.Selection(
        [
            ("portal", "Authenticated Portal"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("paper", "Paper"),
            ("other", "Other"),
        ],
        required=True,
        default="email",
    )
    portal_visible = fields.Boolean(string="Share Own Complaint and Reply with Participant")
    portal_revoked = fields.Boolean(readonly=True)
    treatment = fields.Text()
    reply = fields.Text(string="Reply Communicable to Complainant")
    resolution_reason = fields.Text(string="Action or Justification")
    state = fields.Selection(
        [
            ("received", "Received"),
            ("processing", "In Treatment"),
            ("resolved", "Resolved with Reply"),
            ("closed", "Closed"),
        ],
        default="received",
        required=True,
        readonly=True,
    )
    received_at = fields.Datetime(default=fields.Datetime.now, readonly=True, copy=False)
    resolved_at = fields.Datetime(readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)
    improvement_ids = fields.One2many("training.improvement", "complaint_id")
    event_ids = fields.One2many("training.quality.event", "complaint_id")
    file_ids = fields.One2many("training.quality.file", "complaint_id")

    @api.constrains("enrollment_id", "delivery_id", "complainant_id", "portal_visible")
    def _check_complaint_links(self):
        for row in self:
            if not required_text(row.name) or not required_text(row.description):
                raise ValidationError(self.env._("Enter a subject and the original complaint."))
            if row.enrollment_id and (
                row.enrollment_id.delivery_id != row.delivery_id
                or row.enrollment_id.participant_id != row.complainant_id
            ):
                raise ValidationError(self.env._("The complaint must match the participant and delivery."))
            if row.portal_visible and not row.enrollment_id:
                raise ValidationError(self.env._("Participant sharing requires the corresponding enrollment."))

    def action_new_improvement(self):
        self._authorize()
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.improvement",
            "view_mode": "form",
            "context": {
                "default_complaint_id": self.id,
                "default_delivery_id": self.delivery_id.id,
                "default_quality_id": self.quality_id.id,
                "default_retention_id": self.retention_id.id,
                "default_origin": "complaint",
                "default_origin_reference": "Complaint %s" % self.id,
            },
        }

    def action_decision(self):
        self._authorize(quality=True)
        operation = "reopen" if self.state in ("resolved", "closed") else "revoke"
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.quality.operation",
            "view_mode": "form",
            "target": "new",
            "context": {"default_complaint_id": self.id, "default_operation": operation},
        }

    def action_start(self):
        self._authorize()
        if self.state == "processing":
            return True
        if self.state != "received":
            raise ValidationError(self.env._("Start treatment from a received complaint."))
        self._transition("processing")
        return True

    def action_resolve(self):
        self._authorize(quality=True)
        if self.state == "resolved":
            return True
        if (
            self.state != "processing"
            or not required_text(self.reply)
            or not (required_text(self.treatment) or required_text(self.resolution_reason) or self.improvement_ids)
        ):
            raise ValidationError(
                self.env._("Treatment or a justified action and a reply are required before resolution.")
            )
        self._transition("resolved", resolved_at=fields.Datetime.now())
        return True

    def action_close(self):
        self._authorize(quality=True)
        if self.state == "closed":
            return True
        if self.state != "resolved":
            raise ValidationError(self.env._("Resolve the complaint with a reply before closure."))
        self._transition("closed", closed_at=fields.Datetime.now())
        return True

    def action_reopen(self, reason=None):
        self._authorize(quality=True)
        if self.state not in ("resolved", "closed") or not required_text(reason):
            raise ValidationError(self.env._("Reopening a resolved complaint requires a reason."))
        # Previous dates/reply remain in immutable history; the old reply is not exposed as a new resolution.
        self._transition("processing", reason, resolved_at=False, closed_at=False)
        return True

    def action_revoke_portal(self, reason=None):  # pylint: disable=super-method-mismatch  # Controlled audit update.
        self._authorize(quality=True)
        if not required_text(reason):
            raise ValidationError(self.env._("Explain the participant access withdrawal."))
        if not self.portal_revoked:
            before = self._snapshot()
            super(QualityRecord, self).write({"portal_revoked": True})  # pylint: disable=super-method-mismatch
            self._event("portal_revoked", before, reason)
        return True


class Improvement(models.Model):
    _name = "training.improvement"
    _inherit = "training.quality.record"
    _description = "Training Improvement and Effectiveness"
    _order = "id desc"

    complaint_id = fields.Many2one("training.complaint", ondelete="restrict", check_company=True)
    campaign_id = fields.Many2one("training.feedback.campaign", ondelete="restrict", check_company=True)
    origin = fields.Selection(
        [("complaint", "Complaint"), ("feedback", "Feedback Campaign"), ("review", "Review"), ("other", "Other")],
        required=True,
        default="review",
    )
    origin_reference = fields.Text(required=True)
    decision = fields.Text()
    implementation = fields.Text()
    output_reference = fields.Text(string="Corrected Support / Output Reference")
    effectiveness_criterion = fields.Text()
    verification_plan = fields.Text()
    state = fields.Selection(
        [
            ("decision", "To Decide"),
            ("planned", "Planned"),
            ("done", "Implemented"),
            ("checking", "Effectiveness to Verify"),
            ("effective", "Effective"),
            ("ineffective", "Not Effective"),
        ],
        required=True,
        default="decision",
        readonly=True,
    )
    implemented_at = fields.Datetime(readonly=True, copy=False)
    verified_at = fields.Datetime(readonly=True, copy=False)
    verifier_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    verification = fields.Text(readonly=True, copy=False)
    follow_up = fields.Text(readonly=True, copy=False)
    event_ids = fields.One2many("training.quality.event", "improvement_id")
    file_ids = fields.One2many("training.quality.file", "improvement_id")

    @api.constrains(
        "complaint_id", "campaign_id", "delivery_id", "origin", "origin_reference", "member_ids", "quality_id"
    )
    def _check_improvement_links(self):
        for row in self:
            if not required_text(row.name) or not required_text(row.origin_reference):
                raise ValidationError(self.env._("Document the subject and origin of the action."))
            if (row.origin == "complaint") != bool(row.complaint_id) or (row.origin == "feedback") != bool(
                row.campaign_id
            ):
                raise ValidationError(self.env._("Link the explicit complaint or campaign for the selected origin."))
            for source in row.complaint_id:
                if source.company_id != row.company_id or source.delivery_id != row.delivery_id:
                    raise ValidationError(self.env._("Keep the same operating company and delivery as the complaint."))
                if (row.member_ids | row.quality_id) - (source.member_ids | source.quality_id):
                    raise ValidationError(self.env._("Action staff must also be authorized for the source complaint."))
            if row.campaign_id and (
                row.campaign_id.company_id != row.company_id or row.campaign_id.delivery_id != row.delivery_id
            ):
                raise ValidationError(self.env._("Keep the same company and delivery as the feedback campaign."))

    def action_decision(self):
        self._authorize(quality=True)
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.quality.operation",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_improvement_id": self.id,
                "default_operation": "replan" if self.state == "ineffective" else "verify",
            },
        }

    def action_plan(self):
        self._authorize(quality=True)
        if self.state == "planned":
            return True
        if self.state != "decision" or not all(
            required_text(x) for x in (self.decision, self.effectiveness_criterion, self.verification_plan)
        ):
            raise ValidationError(self.env._("Document the decision, effectiveness criterion and verification plan."))
        self._transition("planned")
        return True

    def action_implement(self):
        self._authorize()
        if self.state == "done":
            return True
        if (
            self.state != "planned"
            or not required_text(self.implementation)
            or not required_text(self.output_reference)
        ):
            raise ValidationError(self.env._("Document the implementation and corrected output."))
        self._transition("done", implemented_at=fields.Datetime.now())
        return True

    def action_check_effectiveness(self):
        self._authorize()
        if self.state == "checking":
            return True
        if self.state != "done":
            raise ValidationError(self.env._("Verify effectiveness only after implementation."))
        self._transition("checking")
        return True

    def action_verify(self, effective=None, verification=None, follow_up=None):
        self._authorize(quality=True)
        if not isinstance(effective, bool) or not required_text(verification):
            raise ValidationError(self.env._("Record an effectiveness decision and its verification evidence."))
        if (
            self.state == ("effective" if effective else "ineffective")
            and self.verifier_id == self.env.user
            and self.verification == verification
            and (self.follow_up or False) == (follow_up or False)
        ):
            return True
        if self.state != "checking" or (not effective and not required_text(follow_up)):
            raise ValidationError(self.env._("An ineffective action needs a documented follow-up."))
        self._transition(
            "effective" if effective else "ineffective",
            verification,
            verified_at=fields.Datetime.now(),
            verifier_id=self.env.uid,
            verification=verification,
            follow_up=follow_up or False,
        )
        return True

    def action_replan(self, reason=None):
        self._authorize(quality=True)
        if self.state != "ineffective" or not required_text(reason):
            raise ValidationError(
                self.env._("Replan an ineffective action with a reason; keep its earlier verification.")
            )
        self._transition("decision", reason)
        return True


class QualityEvent(models.Model):
    _name = "training.quality.event"
    _description = "Immutable Private Quality History"
    _order = "id"

    complaint_id = fields.Many2one("training.complaint", ondelete="restrict", readonly=True)
    improvement_id = fields.Many2one("training.improvement", ondelete="restrict", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    operation = fields.Char(readonly=True)
    author_id = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    occurred_at = fields.Datetime(readonly=True)
    details = fields.Text(readonly=True)
    reason = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # Public insertion is deliberately forbidden.
        raise AccessError(self.env._("Quality history is created only by controlled operations."))

    @api.private
    def _append(self, parent, operation, before, reason):  # pylint: disable=super-method-mismatch  # Private append-only factory.
        values = {
            "complaint_id" if parent._name == "training.complaint" else "improvement_id": parent.id,
            "company_id": parent.company_id.id,
            "operation": operation,
            "author_id": self.env.uid,
            "occurred_at": fields.Datetime.now(),
            "reason": reason,
            "details": json.dumps({"before": before, "after": parent._snapshot()}, default=str, sort_keys=True),
        }
        return super(QualityEvent, clean_context(self).sudo()).create(values)  # pylint: disable=super-method-mismatch

    def write(self, vals):  # pylint: disable=method-required-super  # Immutable evidence and history.
        raise AccessError(self.env._("Keep immutable quality history."))

    @api.ondelete(at_uninstall=False)
    def _keep_event(self):
        raise ValidationError(self.env._("Keep immutable quality history."))


class QualityFile(models.Model):
    _name = "training.quality.file"
    _description = "Immutable Private Quality File"
    _check_company_auto = True

    name = fields.Char(required=True, string="Filename")
    complaint_id = fields.Many2one("training.complaint", ondelete="restrict", check_company=True)
    improvement_id = fields.Many2one("training.improvement", ondelete="restrict", check_company=True)
    company_id = fields.Many2one("res.company", readonly=True)
    source = fields.Text(required=True)
    produced_at = fields.Datetime(required=True, default=fields.Datetime.now)
    data = fields.Binary(required=True, attachment=False, copy=False)
    sha256 = fields.Char(readonly=True)
    previous_id = fields.Many2one("training.quality.file", ondelete="restrict", check_company=True)

    @api.private
    def _parent(self):
        self.ensure_one()
        return self.complaint_id or self.improvement_id

    @api.model_create_multi
    def create(self, vals_list):
        rows = self.browse()
        for original in vals_list:
            vals = dict(original)
            if set(vals) - {"name", "complaint_id", "improvement_id", "source", "produced_at", "data", "previous_id"}:
                raise AccessError(self.env._("Quality file audit fields are server controlled."))
            if bool(vals.get("complaint_id")) == bool(vals.get("improvement_id")):
                raise ValidationError(self.env._("Choose exactly one quality dossier."))
            parent = self.env["training.complaint" if vals.get("complaint_id") else "training.improvement"].browse(
                vals.get("complaint_id") or vals.get("improvement_id")
            )
            parent._authorize()
            if parent.state in parent._terminal_states() or parent.state == "resolved":
                raise ValidationError(self.env._("Reopen the quality dossier before adding evidence."))
            previous = self.browse(vals.get("previous_id"))
            if previous:
                previous.check_access("read")
                if previous._parent() != parent:
                    raise ValidationError(self.env._("A corrected file must retain its dossier."))
            vals["company_id"] = parent.company_id.id
            row = super(QualityFile, clean_context(self)).create(vals)
            if not row.data or row.produced_at > fields.Datetime.now():
                raise ValidationError(self.env._("Provide a nonempty file and a valid production date."))
            super(QualityFile, row.sudo()).write(  # pylint: disable=super-method-mismatch  # Server-derived hash, once.
                {"sha256": hashlib.sha256(row.data.content).hexdigest()}
            )
            parent._event("file_added", reason=str(row.id))
            rows |= row
        return rows

    def write(self, vals):  # pylint: disable=method-required-super  # Immutable evidence and history.
        raise AccessError(self.env._("Keep original quality files; add a corrected version."))

    def _can_return_content(self, field_name=None, access_token=None):
        self.env["training.document.policy"]._check_read(self)
        return field_name == "data"

    @api.ondelete(at_uninstall=False)
    def _keep_file(self):
        raise ValidationError(self.env._("Retain quality files and their provenance."))


class QualityEnrollment(models.Model):
    _inherit = "training.enrollment"

    complaint_ids = fields.One2many("training.complaint", "enrollment_id", groups=COORDINATOR + "," + QUALITY)
