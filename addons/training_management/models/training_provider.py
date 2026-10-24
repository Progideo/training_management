"""QUA03: partner dossiers, immutable evidence, obligations and analyzed watch."""

import hashlib
import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_evaluation import COORDINATOR, QUALITY, clean_context

PROVIDER_MODELS = (
    "training.provider.dossier",
    "training.provider.evidence",
    "training.provider.obligation",
    "training.provider.event",
)


def text(value):
    return bool(value and value.strip())


class ProviderDossier(models.Model):
    _name = "training.provider.dossier"
    _description = "Private Instructor, Subcontracting or Watch Dossier"
    _check_company_auto = True
    _order = "id desc"

    name = fields.Char(required=True, string="Subject")
    kind = fields.Selection(
        [("instructor", "Instructor"), ("subcontract", "Subcontracting"), ("watch", "Watch")], required=True
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, ondelete="restrict"
    )
    partner_id = fields.Many2one("res.partner", ondelete="restrict", check_company=True, string="Intervening Partner")
    quality_id = fields.Many2one("res.users", required=True, ondelete="restrict", string="Assigned Quality Reviewer")
    member_ids = fields.Many2many("res.users", string="Explicitly Authorized Staff", default=lambda self: self.env.user)
    retention_id = fields.Many2one(
        "training.retention.category", required=True, check_company=True, ondelete="restrict"
    )
    frozen = fields.Boolean(string="Legal Hold", default=False)
    competencies = fields.Text(string="Competencies and Scope")
    source = fields.Char(string="Watch Source")
    observed_on = fields.Date(string="Source Date")
    analysis = fields.Text()
    decision = fields.Text()
    impact = fields.Text(string="Impact / Actions")
    no_impact_reason = fields.Text(string="Reasoned Absence of Impact")
    program_id = fields.Many2one(
        "training.program.version", check_company=True, ondelete="restrict", string="Impacted Programme Version"
    )
    improvement_id = fields.Many2one(
        "training.improvement", check_company=True, ondelete="restrict", string="Improvement Action"
    )
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Reviewed"), ("closed", "Archived")], default="draft", readonly=True, copy=False
    )
    can_review = fields.Boolean(compute="_compute_can_review")
    revision = fields.Integer(default=0, readonly=True, copy=False)

    evidence_ids = fields.One2many("training.provider.evidence", "dossier_id")
    obligation_ids = fields.One2many("training.provider.obligation", "dossier_id")
    event_ids = fields.One2many("training.provider.event", "dossier_id", readonly=True)

    @api.depends("quality_id")
    @api.depends_context("uid")
    def _compute_can_review(self):
        for row in self:
            row.can_review = (
                row.quality_id == self.env.user and self.env.user.active and self.env.user.has_group(QUALITY)
            )

    @api.private
    def _editable(self):
        return {
            "name",
            "quality_id",
            "member_ids",
            "retention_id",
            "competencies",
            "source",
            "observed_on",
            "analysis",
            "decision",
            "impact",
            "no_impact_reason",
            "program_id",
            "improvement_id",
        }

    @api.private
    def _authorize(self, quality=False, mutable=True):  # pylint: disable=missing-return  # Authorization and write fence only.
        self.ensure_one()
        self.with_env(self.env(su=False)).check_access("write")
        self.lock_for_update()
        self.env.invalidate_all()
        self.with_env(self.env(su=False)).check_access("write")
        if not self.env.user.active or (
            quality and (self.quality_id != self.env.user or not self.env.user.has_group(QUALITY))
        ):
            raise AccessError(self.env._("The assigned quality reviewer is required."))
        if mutable and (self.frozen or self.state == "closed"):
            raise ValidationError(self.env._("This dossier is archived or on legal hold."))
        # A write fence also rejects stale repeatable-read snapshots after a
        # concurrent grant withdrawal, evidence replacement or decision.
        # pylint: disable-next=super-method-mismatch  # Authorized server-controlled audit/workflow mutation.
        super(ProviderDossier, self).write({"revision": self.revision + 1})

    @api.private
    def _snapshot(self):
        return {
            key: self[key].ids if isinstance(self[key], models.BaseModel) else self[key]
            for key in sorted(self._editable() | {"state", "frozen"})
        }

    @api.private
    def _event(self, operation, before=None):
        # Authorization precedes mutation; reassignment can remove the actor.
        self.env["training.provider.event"]._append(self.sudo(), operation, before or {})

    @api.private
    def _record_content_change(self, operation, details):
        # The child factory/mutation already locked and authorized this dossier.
        # Keep the same review semantics for native nested forms and direct ORM.
        before = self._snapshot()
        if self.state == "active":
            # pylint: disable-next=super-method-mismatch  # Authorized review invalidation.
            super(ProviderDossier, self).write({"state": "draft"})
        self._event(operation, {"dossier": before, "change": details})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.active or not (self.env.user.has_group(COORDINATOR) or self.env.user.has_group(QUALITY)):
            raise AccessError(self.env._("Authorized training staff are required."))
        for vals in vals_list:
            if set(vals) - self._editable() - {"kind", "company_id", "partner_id"}:
                raise AccessError(self.env._("Dossier workflow and audit fields are server controlled."))
        rows = super(ProviderDossier, clean_context(self)).create(vals_list)
        rows.with_env(self.env(su=False)).check_access("write")
        for row in rows:
            row._event("created")
        return rows

    def write(self, vals):
        if set(vals) - self._editable() - {"frozen", "evidence_ids", "obligation_ids"}:
            raise AccessError(self.env._("Retain dossier identity and use the workflow actions."))
        for row in self.sorted("id"):
            row._authorize(
                quality=bool(set(vals) & {"quality_id", "member_ids", "frozen"}),
                mutable=bool(set(vals) - {"frozen", "quality_id", "member_ids"}),
            )
            before = row._snapshot()
            prepared = dict(vals)
            if set(vals) - {"frozen", "quality_id", "member_ids"} and row.state == "active":
                prepared["state"] = "draft"
            super(ProviderDossier, row).write(prepared)
            row._event("updated", before)
            self.env.transaction.invalidate_access_cache()
        return True

    @api.constrains(
        "quality_id", "member_ids", "company_id", "partner_id", "kind", "retention_id", "program_id", "improvement_id"
    )
    def _check_scope(self):
        for row in self:
            if row.kind != "watch" and not row.partner_id:
                raise ValidationError(self.env._("Select the intervening partner."))
            if not row.retention_id.approved_at:
                raise ValidationError(self.env._("Choose an approved retention policy."))
            if not row.quality_id.active or not row.quality_id.has_group(QUALITY):
                raise ValidationError(self.env._("Assign an active quality reviewer."))
            for user in row.quality_id | row.member_ids:
                if (
                    not user.active
                    or row.company_id not in user.company_ids
                    or not (user.has_group(QUALITY) or user.has_group(COORDINATOR))
                ):
                    raise ValidationError(
                        self.env._("Dossier access requires active authorized staff in the operating company.")
                    )
            for linked in (row.program_id, row.improvement_id):
                if linked:
                    linked.with_env(self.env(su=False)).check_access("read")

    def action_add_evidence(self):
        self.ensure_one()
        self.check_access("write")
        if self.frozen or self.state == "closed":
            raise ValidationError(self.env._("This dossier is archived or on legal hold."))
        # A native standalone form avoids the Odoo 20 nested-list cache failure
        # when a new evidence record refers to another row in that same list.
        # Creation still checks the dossier again, including grants and holds.
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Add Evidence"),
            "res_model": "training.provider.evidence",
            "views": [(self.env.ref("training_management.view_provider_evidence_form").id, "form")],
            "target": "new",
            "context": {**clean_context(self).env.context, "default_dossier_id": self.id},
        }

    def action_review(self):
        for row in self.sorted("id"):
            row._authorize(quality=True)
            if row.state == "active":
                continue
            if row.kind == "instructor" and not (text(row.competencies) and row.evidence_ids):
                raise ValidationError(self.env._("Describe the competencies and their scope."))
            if row.kind == "watch" and not (
                text(row.source)
                and row.observed_on
                and text(row.analysis)
                and text(row.decision)
                and (text(row.impact) != text(row.no_impact_reason))
            ):
                raise ValidationError(
                    self.env._(
                        "Analyze the dated source, record a decision and either its impact or a reasoned absence of impact."
                    )
                )
            if row.kind == "subcontract" and not row.obligation_ids:
                raise ValidationError(self.env._("Record the contractual obligations before review."))
            before = row._snapshot()
            # pylint: disable-next=super-method-mismatch  # Authorized server-controlled audit/workflow mutation.
            super(ProviderDossier, row).write({"state": "active"})
            row._event("reviewed", before)
        return True

    def action_archive(self):
        for row in self.sorted("id"):
            row._authorize(quality=True, mutable=False)
            if row.frozen:
                raise ValidationError(self.env._("This dossier is on legal hold."))
            if row.state != "closed":
                before = row._snapshot()
                # pylint: disable-next=super-method-mismatch  # Authorized server-controlled audit/workflow mutation.
                super(ProviderDossier, row).write({"state": "closed"})
                row._event("archived", before)
        return True

    @api.ondelete(at_uninstall=False)
    def _keep_history(self):
        raise ValidationError(self.env._("Archive dossiers and retain their evidence and history."))


class ProviderEvidence(models.Model):
    _name = "training.provider.evidence"
    _description = "Immutable Private Provider Evidence"
    _check_company_auto = True
    _order = "id desc"

    dossier_id = fields.Many2one("training.provider.dossier", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="dossier_id.company_id", store=True)
    name = fields.Char(required=True, string="Filename")
    competence = fields.Char(required=True, string="Competence / Evidence Scope")
    source = fields.Text(required=True)
    produced_on = fields.Date(required=True, default=fields.Date.today)
    valid_from = fields.Date(required=True, default=fields.Date.today)
    valid_until = fields.Date(string="Valid Until (If Applicable)")
    data = fields.Binary(required=True, attachment=False)
    checksum = fields.Char(readonly=True, copy=False)
    previous_id = fields.Many2one(
        "training.provider.evidence", ondelete="restrict", check_company=True, string="Replaced Evidence"
    )
    replacement_ids = fields.One2many("training.provider.evidence", "previous_id")

    _one_replacement = models.Constraint("UNIQUE(previous_id)", "An evidence version may have only one replacement.")

    @api.model_create_multi
    def create(self, vals_list):
        if any(
            set(v)
            - {
                "dossier_id",
                "name",
                "competence",
                "source",
                "produced_on",
                "valid_from",
                "valid_until",
                "data",
                "previous_id",
            }
            for v in vals_list
        ):
            raise AccessError(self.env._("Evidence audit fields are server controlled."))
        for vals in vals_list:
            parent = self.env["training.provider.dossier"].browse(vals.get("dossier_id"))
            parent._authorize()
            if vals.get("previous_id"):
                previous = self.browse(vals["previous_id"])
                previous.check_access("read")
                if previous.dossier_id != parent or previous.replacement_ids:
                    raise ValidationError(self.env._("Replace the latest evidence in the same dossier."))
        rows = super(ProviderEvidence, clean_context(self)).create(vals_list)
        for row in rows:
            if not (
                text(row.source)
                and text(row.competence)
                and row.data
                and (not row.valid_until or row.valid_until >= row.valid_from)
            ):
                raise ValidationError(self.env._("Provide evidence, its source, scope and a valid period."))
            # pylint: disable-next=super-method-mismatch  # Authorized server-controlled audit/workflow mutation.
            super(ProviderEvidence, row.sudo()).write({"checksum": hashlib.sha256(row.data.content).hexdigest()})
            row.dossier_id._record_content_change(
                "evidence", {"evidence_id": row.id, "checksum": row.checksum, "previous_id": row.previous_id.id}
            )
        return rows

    def write(self, vals):  # pylint: disable=method-required-super  # Immutable evidence/history.
        raise AccessError(self.env._("Evidence is immutable; add a replacement version."))

    def _can_return_content(self, field_name=None, access_token=None):
        self.env["training.document.policy"]._check_read(self)
        return field_name == "data"

    @api.ondelete(at_uninstall=False)
    def _keep_history(self):
        raise ValidationError(self.env._("Retain every evidence version."))


class ProviderObligation(models.Model):
    _name = "training.provider.obligation"
    _description = "Subcontractor Contractual Obligation"
    _check_company_auto = True

    dossier_id = fields.Many2one("training.provider.dossier", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="dossier_id.company_id", store=True)
    name = fields.Char(required=True, string="Contractual Obligation")
    responsible_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, ondelete="restrict"
    )
    due_date = fields.Date(required=True)
    evidence_id = fields.Many2one("training.provider.evidence", ondelete="restrict", check_company=True)
    control = fields.Text(string="Control Findings")
    checked_at = fields.Datetime(readonly=True, copy=False)
    checked_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    state = fields.Selection(
        [("pending", "Pending"), ("conform", "Conform"), ("nonconform", "Nonconform")],
        default="pending",
        readonly=True,
        copy=False,
    )

    @api.private
    def _snapshot(self):
        return {
            "id": self.id,
            "name": self.name,
            "responsible_id": self.responsible_id.id,
            "due_date": self.due_date,
            "evidence_id": self.evidence_id.id,
            "control": self.control,
            "state": self.state,
            "checked_at": self.checked_at,
            "checked_by_id": self.checked_by_id.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        allowed = {"dossier_id", "name", "responsible_id", "due_date", "evidence_id", "control"}
        if any(set(v) - allowed for v in vals_list):
            raise AccessError(self.env._("Use the obligation control actions."))
        for vals in vals_list:
            self.env["training.provider.dossier"].browse(vals.get("dossier_id"))._authorize()
        rows = super(ProviderObligation, clean_context(self)).create(vals_list)
        for row in rows:
            row.dossier_id._record_content_change("obligation", row._snapshot())
        return rows

    def write(self, vals):
        if set(vals) - {"name", "responsible_id", "due_date", "evidence_id", "control"}:
            raise AccessError(self.env._("Keep the obligation identity and use the control actions."))
        for row in self.sorted("id"):
            row.check_access("write")
            row.dossier_id._authorize()
            row.invalidate_recordset()
            if row.state != "pending":
                raise ValidationError(self.env._("Retain controlled obligations; add a follow-up obligation."))
            before = row._snapshot()
            super(ProviderObligation, row).write(vals)
            row.dossier_id._record_content_change(
                "obligation_updated", {"obligation_before": before, "obligation_after": row._snapshot()}
            )
        return True

    @api.constrains("dossier_id", "responsible_id", "evidence_id")
    def _check_definition(self):
        for row in self:
            if row.dossier_id.kind != "subcontract":
                raise ValidationError(self.env._("Contractual obligations belong to a subcontracting dossier."))
            if row.responsible_id not in row.dossier_id.member_ids | row.dossier_id.quality_id:
                raise ValidationError(self.env._("Assign responsibility to authorized dossier staff."))
            if row.evidence_id and row.evidence_id.dossier_id != row.dossier_id:
                raise ValidationError(self.env._("Keep evidence in the same dossier."))

    @api.private
    def _control(self, conform):
        for row in self.sorted("id"):
            row.check_access("write")
            row.dossier_id._authorize(quality=True)
            row.invalidate_recordset()
            if row.state != "pending":
                if row.state != ("conform" if conform else "nonconform"):
                    raise ValidationError(self.env._("Retain controlled obligations; add a follow-up obligation."))
                continue
            if not text(row.control) or not row.evidence_id:
                raise ValidationError(self.env._("Record control findings and supporting evidence."))
            before = row._snapshot()
            # pylint: disable-next=super-method-mismatch  # Authorized server-controlled audit/workflow mutation.
            super(ProviderObligation, row).write(
                {
                    "state": "conform" if conform else "nonconform",
                    "checked_at": fields.Datetime.now(),
                    "checked_by_id": self.env.uid,
                }
            )
            row.dossier_id._event("controlled", {"obligation_before": before, "obligation_after": row._snapshot()})
        return True

    def action_conform(self):
        return self._control(True)

    def action_nonconform(self):
        return self._control(False)

    @api.ondelete(at_uninstall=False)
    def _keep_history(self):
        raise ValidationError(self.env._("Retain contractual obligations and controls."))


class ProviderEvent(models.Model):
    _name = "training.provider.event"
    _description = "Immutable Private Provider History"
    _order = "id"

    dossier_id = fields.Many2one("training.provider.dossier", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="dossier_id.company_id", store=True)
    actor_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    occurred_at = fields.Datetime(required=True, readonly=True)
    operation = fields.Selection(
        [
            ("created", "Created"),
            ("updated", "Updated"),
            ("reviewed", "Reviewed"),
            ("archived", "Archived"),
            ("evidence", "Evidence Added"),
            ("obligation", "Obligation Added"),
            ("obligation_updated", "Obligation Updated"),
            ("controlled", "Control Recorded"),
        ],
        required=True,
        readonly=True,
    )
    details = fields.Text(required=True, readonly=True)

    @api.private
    def _append(self, dossier, operation, before):
        # pylint: disable-next=super-method-mismatch  # Authorized server-controlled audit/workflow mutation.
        return super(ProviderEvent, clean_context(self).sudo()).create(
            {
                "dossier_id": dossier.id,
                "actor_id": self.env.uid,
                "occurred_at": fields.Datetime.now(),
                "operation": operation,
                "details": json.dumps({"before": before, "after": dossier._snapshot()}, sort_keys=True, default=str),
            }
        )

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # Immutable evidence/history.
        raise AccessError(self.env._("History is appended by authorized dossier operations."))

    def write(self, vals):  # pylint: disable=method-required-super  # Immutable evidence/history.
        raise AccessError(self.env._("Private history is immutable."))

    @api.ondelete(at_uninstall=False)
    def _keep_history(self):
        raise ValidationError(self.env._("Retain private dossier history."))


class ProviderService(models.AbstractModel):
    _name = "training.provider.service"
    _description = "Provider Quality Projections"

    @api.private
    def _assignment_warning(self, partners, company, on_date, until=None):
        user = self.env.user
        if not (
            user.active
            and user.has_group(COORDINATOR)
            and company in user.company_ids
            and company in self.env.companies
        ):
            return False
        # Planning needs a warning, never private filenames, analyses or counts.
        # The explicit coordinator/company check precedes this narrow projection.
        dossiers = (
            self.env["training.provider.dossier"]
            .sudo()
            .search(
                [
                    ("kind", "=", "instructor"),
                    ("partner_id", "in", partners.ids),
                    ("company_id", "=", company.id),
                    ("state", "!=", "closed"),
                ]
            )
        )
        if partners and set(partners.ids) - set(dossiers.partner_id.ids):
            return self.env._(
                "Instructor evidence is missing or outside its validity period. Ask the quality reviewer before assignment. Scheduling remains available."
            )
        for dossier in dossiers:
            latest = dossier.evidence_ids.filtered(lambda e: not e.replacement_ids)
            if not latest or any(
                e.valid_from > on_date or (e.valid_until and e.valid_until < (until or on_date)) for e in latest
            ):
                return self.env._(
                    "Instructor evidence is missing or outside its validity period. Ask the quality reviewer before assignment. Scheduling remains available."
                )
        return False

    @api.private
    def _states(self, offset=0, limit=80):
        # S10 contract: apply native grants/company filters BEFORE count/page.
        model = self.env["training.provider.dossier"].with_env(self.env(su=False))
        domain = []
        rows = model.search(domain, offset=max(0, offset), limit=min(200, max(1, limit)))
        return {
            "total": model.search_count(domain),
            "rows": [{"id": r.id, "kind": r.kind, "state": r.state, "frozen": r.frozen} for r in rows],
        }


class ProviderSession(models.Model):
    _inherit = "training.session"  # pylint: disable=consider-merging-classes-inherited  # Keep QUA03 warning projections separate from scheduling and attendance.

    instructor_warning = fields.Char(
        string="Instructor Evidence", compute="_compute_provider_warning", groups=COORDINATOR
    )

    @api.depends("instructor_id", "company_id", "start_date", "end_date")
    def _compute_provider_warning(self):
        for row in self:
            row.instructor_warning = self.env["training.provider.service"]._assignment_warning(
                row.instructor_id, row.company_id, row.start_date or fields.Date.today(), row.end_date
            )

    @api.onchange("instructor_id", "start_date", "end_date")
    def _onchange_provider_warning(self):
        if self.instructor_warning:
            return {"warning": {"title": self.env._("Instructor Evidence"), "message": self.instructor_warning}}
        return None


class ProviderDelivery(models.Model):
    _inherit = "training.delivery"  # pylint: disable=consider-merging-classes-inherited  # Keep QUA03 warning projections separate from evaluation authorization rules.

    instructor_warning = fields.Char(
        string="Instructor Evidence", compute="_compute_provider_warning", groups=COORDINATOR
    )

    @api.depends("evaluation_instructor_ids", "company_id", "start_at", "end_at")
    def _compute_provider_warning(self):
        for row in self:
            row.instructor_warning = self.env["training.provider.service"]._assignment_warning(
                row.evaluation_instructor_ids,
                row.company_id,
                fields.Date.to_date(row.start_at) or fields.Date.today(),
                fields.Date.to_date(row.end_at),
            )

    @api.onchange("evaluation_instructor_ids", "start_at", "end_at")
    def _onchange_provider_warning(self):
        if self.instructor_warning:
            return {"warning": {"title": self.env._("Instructor Evidence"), "message": self.instructor_warning}}
        return None
