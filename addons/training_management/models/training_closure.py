"""DOC01–02: versioned evidence, explicit decisions and preserved outputs."""

import hashlib
import io
import json
import math
import zipfile

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.binary import BinaryBytes

COORDINATOR = "training_management.group_training_coordinator"
QUALITY = "training_management.group_training_quality"
CATEGORIES = [
    ("need", "Needs and Accepted Programme"),
    ("commercial", "Commercial Documents"),
    ("roster", "Enrollment List"),
    ("positioning", "Initial Assessment"),
    ("invitation", "Invitations"),
    ("resources", "Assignments and Resources"),
    ("materials", "Applicable Materials"),
    ("attendance", "Attendance or Activity Traces"),
    ("assessment", "Dedicated Learning Assessment"),
    ("feedback", "Feedback"),
    ("certificate", "Certificates"),
    ("incidents", "Incidents and Improvements"),
    ("completion", "Controlled Completion Evidence"),
]
# Even a mistaken sharing checkbox cannot expose individual assessments or notes.
CLIENT_CATEGORIES = {
    "need",
    "commercial",
    "roster",
    "invitation",
    "resources",
    "materials",
    "attendance",
    "certificate",
}
KINDS = [("participation", "Participation"), ("completion", "Completion"), ("achievement", "Achievement")]


class RetentionCategory(models.Model):
    _name = "training.retention.category"
    _description = "Training Retention Policy"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    purpose = fields.Text(required=True)
    responsible_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    duration_days = fields.Integer(required=True)
    archive_policy = fields.Text(required=True)
    deletion_policy = fields.Text(required=True, help="Requests are reviewed manually; no automatic purge.")
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    approved_at = fields.Datetime(readonly=True, copy=False)

    @api.private
    def _quality(self):
        if not self.env.user.has_group(QUALITY):
            raise AccessError(self.env._("An explicitly assigned quality role is required."))
        self.check_access("write")

    @api.model_create_multi
    def create(self, vals_list):
        self._quality()
        if any(set(v) & {"approved_by_id", "approved_at"} for v in vals_list):
            raise AccessError(self.env._("Use Approve Policy."))
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        return super(RetentionCategory, self.with_context(clean)).create(vals_list)  # pylint: disable=context-overridden

    def write(self, vals):
        self._quality()
        self.lock_for_update()
        self.invalidate_recordset()
        if self.filtered("approved_at") or set(vals) & {"approved_by_id", "approved_at"}:
            raise ValidationError(self.env._("Keep approved policies; create a new policy version."))
        return super().write(vals)

    def action_approve(self):
        self._quality()
        self.lock_for_update()
        self.invalidate_recordset()
        for policy in self.filtered(lambda p: not p.approved_at):
            if policy.duration_days <= 0 or policy.company_id not in policy.responsible_id.company_ids:
                raise ValidationError(
                    self.env._("Set a positive approved duration and an authorized responsible user.")
                )
            # pylint: disable-next=super-method-mismatch  # checked approval bypasses the public immutable write guard
            super(RetentionCategory, policy).write(
                {"approved_at": fields.Datetime.now(), "approved_by_id": self.env.uid}
            )
        return True

    @api.ondelete(at_uninstall=False)
    def _keep_approved(self):
        if self.filtered("approved_at"):
            raise ValidationError(self.env._("Keep approved retention policies."))


class ClosureDossier(models.Model):
    _name = "training.closure"
    _description = "Training Closure Dossier"
    _rec_name = "enrollment_id"
    _check_company_auto = True

    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="restrict", check_company=True)
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    quality_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    retention_id = fields.Many2one(
        "training.retention.category", required=True, ondelete="restrict", check_company=True
    )
    share_certificates = fields.Boolean(string="Share Issued Certificates with Explicit Client Recipients")
    customer_id = fields.Many2one("res.partner", readonly=True, ondelete="restrict")
    client_contact_ids = fields.Many2many("res.partner", string="Explicit Client Recipients")
    evidence_ids = fields.One2many("training.proof", "dossier_id", readonly=True)
    output_ids = fields.One2many("training.document", "dossier_id", readonly=True)
    missing = fields.Text(compute="_compute_missing")
    state = fields.Selection([("open", "Open"), ("closed", "Closed")], default="open", required=True, readonly=True)
    closed_at = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    frozen = fields.Boolean(
        string="Legal Hold", default=True, help="No automatic deletion, even after retention expires."
    )

    _unique_enrollment = models.Constraint("UNIQUE(enrollment_id)", "One closure dossier per enrollment.")

    @api.private
    def _authorize(self, quality=False):
        self.check_access("read")
        user = self.env.user
        if not user.active or user._is_public():
            raise AccessError(self.env._("This dossier is unavailable."))
        if quality:
            if not user.has_group(QUALITY) or any(d.quality_id != user for d in self):
                raise AccessError(self.env._("Only the quality reviewer assigned to this dossier may approve it."))
        elif not user.has_group(COORDINATOR) and not (
            user.has_group(QUALITY) and all(d.quality_id == user for d in self)
        ):
            raise AccessError(self.env._("This dossier is unavailable."))

    @api.private
    def _serialize(self):
        # Checked dossier authority precedes narrow elevation for the existing
        # delivery write fence. No business mutation or returned data uses sudo.
        # Same lock order as S03/S05/S07: delivery first, then enrollment/dossier.
        self.delivery_id.sudo()._serialize()
        self.enrollment_id.lock_for_update()
        self.lock_for_update()
        self.env.invalidate_all()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group(COORDINATOR):
            raise AccessError(self.env._("Only coordinators create closure dossiers."))
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if set(vals) - {
                "enrollment_id",
                "quality_id",
                "retention_id",
                "client_contact_ids",
                "share_certificates",
                "frozen",
            }:
                raise AccessError(self.env._("Dossier identity and audit fields are controlled by the server."))
            enrollment = self.env["training.enrollment"].browse(
                vals.get("enrollment_id") or self.env.context.get("default_enrollment_id")
            )
            enrollment.check_access("read")
            vals["enrollment_id"] = enrollment.id
            vals["customer_id"] = (enrollment.allocation_id.customer_id or enrollment.participant_id).id
            prepared.append(vals)
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        return super(ClosureDossier, self.with_context(clean)).create(prepared)  # pylint: disable=context-overridden

    def write(self, vals):
        self._authorize()
        self._serialize()
        if (self.filtered(lambda d: d.state == "closed") and set(vals) - {"client_contact_ids"}) or set(vals) - {
            "quality_id",
            "retention_id",
            "client_contact_ids",
            "share_certificates",
            "frozen",
        }:
            raise ValidationError(self.env._("Keep dossier identity and closed dossiers unchanged."))
        if set(vals) & {"quality_id", "retention_id"} and (self.sudo().evidence_ids or self.sudo().output_ids):
            raise ValidationError(self.env._("Keep the reviewer and retention policy once evidence exists."))
        return super().write(vals)

    @api.constrains("quality_id", "retention_id", "client_contact_ids", "customer_id")
    def _check_definition(self):
        for dossier in self:
            reviewer = dossier.quality_id
            if not reviewer.active or not reviewer.has_group(QUALITY) or dossier.company_id not in reviewer.company_ids:
                raise ValidationError(
                    self.env._("Assign an active quality reviewer authorized for this operating company.")
                )
            if not dossier.retention_id.approved_at:
                raise ValidationError(self.env._("Choose an approved retention policy."))
            if any(
                p.commercial_partner_id != dossier.customer_id.commercial_partner_id for p in dossier.client_contact_ids
            ):
                raise ValidationError(self.env._("Explicit recipients must belong to this dossier's customer."))

    @api.private
    def _latest(self):
        self.ensure_one()
        rows = self.env["training.proof"].sudo().search([("dossier_id", "=", self.id)], order="version desc, id desc")
        result = {}
        for row in rows:
            result.setdefault(row.category, row)
        return result

    @api.private
    def _missing_keys(self):
        latest = self._latest()
        missing = [key for key, _label in CATEGORIES if key not in latest or not latest[key].validated_at]
        if "certificate" not in latest and self.sudo().output_ids.filtered(lambda d: d.kind in dict(KINDS)):
            missing.remove("certificate")
        return missing

    def _compute_missing(self):
        for dossier in self:
            labels = dict(self.env["training.proof"].fields_get(["category"])["category"]["selection"])
            dossier.missing = "\n".join(labels[key] for key in dossier._missing_keys())

    def action_close(self):
        self._authorize(quality=True)
        self._serialize()
        for dossier in self:
            if dossier.state == "closed":
                continue
            if dossier._missing_keys():
                raise ValidationError(
                    self.env._("Review missing evidence; approve a reasoned exemption where applicable.")
                )
            # pylint: disable-next=super-method-mismatch  # checked closure stores server audit fields
            super(ClosureDossier, dossier).write(
                {"state": "closed", "closed_at": fields.Datetime.now(), "closed_by_id": self.env.uid}
            )
        return True

    def action_certificate_participation(self):
        self.ensure_one()
        self._authorize(quality=True)
        return self.enrollment_id._issue_certificate("participation")

    def action_certificate_completion(self):
        self.ensure_one()
        self._authorize(quality=True)
        return self.enrollment_id._issue_certificate("completion")

    def action_certificate_achievement(self):
        self.ensure_one()
        self._authorize(quality=True)
        return self.enrollment_id._issue_certificate("achievement")

    def action_export_internal(self):
        return self._export_dossier(client=False)

    def action_export_client(self):
        return self._export_dossier(client=True)

    @api.private
    def _export_dossier(self, client):
        self.ensure_one()
        self._authorize(quality=True)
        self._serialize()
        scope = "client" if client else "internal"
        if client and not self.client_contact_ids:
            raise ValidationError(self.env._("Select explicit authorized client recipients before exporting."))
        rows = self.env["training.proof"].search([("dossier_id", "=", self.id), ("validated_at", "!=", False)])
        if client:
            rows = rows.filtered(
                lambda p: p.client_shared and p.category in CLIENT_CATEGORIES and p.disposition == "file"
            )
        manifest = {
            "dossier": self.id,
            "scope": scope,
            "recipient_partner_ids": self.client_contact_ids.ids if client else [],
            "reviewer_id": self.quality_id.id,
            "actor": self.env.uid,
            "date": str(fields.Datetime.now()),
            "closed": self.state == "closed",
            "certification": False,
            "missing": [k for k in self._missing_keys() if not client or k in CLIENT_CATEGORIES],
            "pieces": [],
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for proof in rows:
                name = f"proof-{proof.id}-v{proof.version}.pdf"
                item = {
                    "id": proof.id,
                    "category": proof.category,
                    "version": proof.version,
                    "source": proof.source if not client else "Approved client document",
                    "author": proof.author,
                    "produced_at": str(proof.produced_at),
                    "validated_by": proof.validated_by_id.id,
                    "validated_at": str(proof.validated_at),
                    "sha256": proof.sha256,
                    "confidentiality": proof.confidentiality,
                    "disposition": proof.disposition,
                    "reason": proof.reason if not client else False,
                    "retention": self.retention_id.id,
                    "filename": name if proof.data else False,
                }
                if not client and proof.category == "assessment" and proof.disposition == "file":
                    item.update(score=proof.score, threshold=proof.threshold)
                manifest["pieces"].append(item)
                if proof.data:
                    archive.writestr(name, proof.data.content)
            # Certificates are individually generated and never carry scores.
            docs = self.output_ids.filtered(lambda d: d.kind in dict(KINDS) and (not client or d.client_shared))
            for doc in docs:
                name = f"certificate-{doc.id}.pdf"
                archive.writestr(name, doc.data.content)
                item = {
                    "id": doc.id,
                    "kind": doc.kind,
                    "version": doc.template_version,
                    "sha256": doc.sha256,
                    "filename": name,
                    "issued_at": str(doc.created_at),
                    "issued_by": doc.actor_id.id,
                }
                if not client:
                    item["criteria"] = json.loads(doc.snapshot)
                manifest["pieces"].append(item)
            archive.writestr("index.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        output = self.env["training.document"]._append(
            {
                "dossier_id": self.id,
                "kind": scope,
                "data": BinaryBytes(stream.getvalue()),
                "filename": f"dossier-{self.id}-{scope}.zip",
                "snapshot": json.dumps(manifest),
                "client_shared": client,
                "recipient_ids": [(6, 0, self.client_contact_ids.ids)] if client else [],
            }
        )
        return output.with_user(self.env.user).action_download()

    @api.ondelete(at_uninstall=False)
    def _keep_dossier(self):
        raise ValidationError(self.env._("Keep closure dossiers and their evidence."))


class ClosureProof(models.Model):
    _name = "training.proof"
    _description = "Versioned Training Proof"
    _rec_name = "category"
    _check_company_auto = True

    dossier_id = fields.Many2one("training.closure", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="dossier_id.company_id", store=True)
    category = fields.Selection(CATEGORIES, required=True)
    previous_id = fields.Many2one("training.proof", readonly=True, copy=False, ondelete="restrict", check_company=True)
    version = fields.Integer(readonly=True, default=1)
    confidentiality = fields.Selection(
        [("internal", "Internal"), ("sensitive", "Sensitive / Assigned Quality Only")],
        required=True,
        default="internal",
    )
    source = fields.Text(required=True, help="Origin, original document/event identifier and extraction method.")
    author = fields.Char(required=True, help="Author of the original evidence; uploader is separately recorded.")
    produced_at = fields.Datetime(required=True)
    data = fields.Binary(attachment=False, copy=False)
    filename = fields.Char(default="proof.pdf")
    disposition = fields.Selection(
        [("file", "Evidence"), ("not_applicable", "Not Applicable"), ("waiver", "Exemption")],
        required=True,
        default="file",
    )
    reason = fields.Text()
    client_shared = fields.Boolean(help="Only client-safe categories can be included in the client export.")
    score = fields.Float(help="Dedicated learning assessment only, never imported automatically from a mock exam.")
    threshold = fields.Float(default=70)
    validated_at = fields.Datetime(readonly=True, copy=False)
    validated_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    sha256 = fields.Char(readonly=True, copy=False)

    _unique_version = models.Constraint("UNIQUE(dossier_id, category, version)", "This proof version already exists.")

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if set(vals) & {"version", "previous_id", "validated_at", "validated_by_id", "sha256"}:
                raise AccessError(self.env._("Evidence versions and validation are server controlled."))
            dossier = self.env["training.closure"].browse(
                vals.get("dossier_id") or self.env.context.get("default_dossier_id")
            )
            dossier._authorize(quality=vals.get("confidentiality") == "sensitive")
            dossier._serialize()
            if dossier.state == "closed":
                raise ValidationError(self.env._("The dossier is closed; keep its evidence unchanged."))
            previous = dossier._latest().get(vals.get("category"))
            vals.update(
                dossier_id=dossier.id,
                previous_id=previous.id if previous else False,
                version=previous.version + 1 if previous else 1,
            )
            # Ignore untrusted default_* audit values on all controlled factories.
            prepared.append(vals)
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        return super(ClosureProof, self.with_context(clean)).create(prepared)  # pylint: disable=context-overridden

    def write(self, vals):
        self.check_access("write")
        self.dossier_id._authorize(quality=vals.get("confidentiality") == "sensitive")
        self.dossier_id._serialize()
        if (
            self.filtered("validated_at")
            or any(d.state == "closed" for d in self.dossier_id)
            or set(vals)
            & {
                "dossier_id",
                "company_id",
                "category",
                "previous_id",
                "version",
                "validated_at",
                "validated_by_id",
                "sha256",
            }
        ):
            raise ValidationError(self.env._("Keep validated evidence; create a new version."))
        return super().write(vals)

    @api.constrains("score", "threshold", "client_shared", "confidentiality", "category", "produced_at")
    def _check_proof(self):
        for proof in self:
            if not all(math.isfinite(v) and 0 <= v <= 100 for v in (proof.score, proof.threshold)):
                raise ValidationError(self.env._("Assessment score and threshold must be between 0 and 100."))
            if proof.client_shared and (
                proof.category not in CLIENT_CATEGORIES or proof.confidentiality == "sensitive"
            ):
                raise ValidationError(self.env._("Individual results and confidential notes cannot be client shared."))
            if proof.produced_at > fields.Datetime.now():
                raise ValidationError(self.env._("Evidence cannot have a future production date."))

    def _can_return_content(self, field_name=None, access_token=None):
        self.env["training.document.policy"]._check_read(self)
        return field_name == "data"

    def action_validate(self):
        self.dossier_id._authorize(quality=True)
        self.dossier_id._serialize()
        for proof in self.filtered(lambda p: not p.validated_at):
            if proof.dossier_id.state == "closed":
                raise ValidationError(self.env._("The dossier is closed."))
            raw = proof.data.content if proof.data else b""
            if proof.disposition == "file":
                if not raw.startswith(b"%PDF-"):
                    raise ValidationError(self.env._("Attach the PDF evidence before validation."))
            elif not (proof.reason or "").strip() or raw:
                raise ValidationError(
                    self.env._("A non-applicable piece or exemption requires a reason and no empty substitute file.")
                )
            if not (proof.source or "").strip() or not (proof.author or "").strip():
                raise ValidationError(self.env._("Record evidence provenance and author."))
            # pylint: disable-next=super-method-mismatch  # checked validation freezes the proof and its audit fields
            super(ClosureProof, proof).write(
                {
                    "validated_at": fields.Datetime.now(),
                    "validated_by_id": self.env.uid,
                    "sha256": hashlib.sha256(raw).hexdigest() if raw else False,
                }
            )
        return True

    @api.ondelete(at_uninstall=False)
    def _keep_proof(self):
        raise ValidationError(self.env._("Keep every proof version, including drafts and exemptions."))

    def copy_data(self, default=None):  # pylint: disable=method-required-super
        raise ValidationError(self.env._("Create a new version with its own provenance."))

    def _export_rows(self, fields, *, _is_toplevel_call=True):  # pylint: disable=method-required-super
        raise UserError(self.env._("Use the controlled dossier export to retain its manifest."))


class ClosureDocument(models.Model):
    _name = "training.document"
    _inherit = "training.attendance.evidence"
    _description = "Preserved Training Document"
    _rec_name = "filename"
    _check_company_auto = True

    dossier_id = fields.Many2one("training.closure", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="dossier_id.company_id", store=True)
    kind = fields.Selection(KINDS + [("internal", "Internal Export"), ("client", "Client Export")], required=True)
    data = fields.Binary(attachment=False, required=True)
    filename = fields.Char(required=True)
    snapshot = fields.Text(required=True, groups=QUALITY)
    template_version = fields.Char(default="S08-QWEB-1", required=True)
    created_at = fields.Datetime(required=True)
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    sha256 = fields.Char(required=True)
    client_shared = fields.Boolean()
    recipient_ids = fields.Many2many("res.partner", readonly=True)

    @api.private
    def _append(self, values):
        values = dict(
            values,
            created_at=fields.Datetime.now(),
            actor_id=self.env.uid,
            sha256=hashlib.sha256(values["data"].content).hexdigest(),
        )
        return super()._append(values)

    def _can_return_content(self, field_name=None, access_token=None):
        self.env["training.document.policy"]._check_read(self)
        return field_name == "data"

    def action_download(self):
        self.ensure_one()
        self.env["training.document.policy"]._check_read(self)
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/training.document/{self.id}/data/{self.filename}?download=true",
            "target": "self",
        }

    def _export_rows(self, fields, *, _is_toplevel_call=True):  # pylint: disable=method-required-super
        raise UserError(self.env._("Download an authorized preserved document."))


class ClosureEnrollment(models.Model):
    _inherit = "training.enrollment"  # pylint: disable=consider-merging-classes-inherited  # S08 issuance is independent of S05 progress

    closure_ids = fields.One2many("training.closure", "enrollment_id", readonly=True)

    def action_closure(self):
        if not (self.env.user.has_group(COORDINATOR) or self.env.user.has_group(QUALITY)):
            raise AccessError(self.env._("A coordinator or assigned quality role is required."))
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.closure",
            "view_mode": "list,form",
            "domain": [("enrollment_id", "=", self.id)],
            "context": {"default_enrollment_id": self.id},
        }

    def action_certificate_participation(self):
        return self._issue_certificate("participation")

    def action_certificate_completion(self):
        return self._issue_certificate("completion")

    def action_certificate_achievement(self):
        return self._issue_certificate("achievement")

    @api.private
    def _issue_certificate(self, kind):
        self.ensure_one()
        self.check_access("read")
        dossier = self.env["training.closure"].search([("enrollment_id", "=", self.id)], limit=1)
        if not dossier:
            raise ValidationError(self.env._("Create the closure dossier and assign its quality reviewer first."))
        dossier._authorize(quality=True)
        dossier._serialize()
        if dossier.state == "closed":
            raise ValidationError(self.env._("The dossier is closed."))
        if kind != "participation" and self.state not in ("confirmed", "closed"):
            raise ValidationError(
                self.env._("Issue documents for a confirmed or completed enrollment before dossier closure.")
            )
        latest = dossier._latest()
        minutes, origins = 0, []
        if kind == "participation":
            attendances = self.env["training.attendance"].sudo().search([("enrollment_id", "=", self.id)])
            for attendance in attendances:
                if attendance.state == "validated":
                    minutes += attendance.minutes
                    origins.append(
                        {"attendance": attendance.id, "revision": attendance.revision, "minutes": attendance.minutes}
                    )
            if minutes <= 0:
                raise ValidationError(self.env._("Participation requires a positive validated attendance duration."))
        else:
            category = "completion" if kind == "completion" else "assessment"
            proof = latest.get(category)
            if not proof or not proof.validated_at or proof.disposition != "file":
                raise ValidationError(self.env._("Validate the dedicated evidence required for this certificate."))
            origins = [{"proof": proof.id, "version": proof.version, "sha256": proof.sha256}]
            if kind == "completion":
                activities = self.env["training.learning.activity"].search(
                    [("delivery_id", "=", self.delivery_id.id), ("optional", "=", False)]
                )
                service = self.env["training.learning.service"]
                if any(not service._complete(self, a) for a in activities):
                    raise ValidationError(
                        self.env._("Complete every required activity and review its supporting evidence.")
                    )
                origins += [service._certificate_origin(self, a) for a in activities]
            elif proof.score < proof.threshold:
                raise ValidationError(self.env._("The dedicated learning assessment threshold has not been reached."))
            else:
                origins[0].update(score=proof.score, threshold=proof.threshold)
        snapshot = {
            "kind": kind,
            "reference": f"TM-{dossier.id}-{kind}",
            "beneficiary": self.participant_id.name,
            "enrollment": self.id,
            "programme": self.delivery_id.program_id.title,
            "programme_version": self.delivery_id.program_id.version,
            "delivery": self.delivery_id.name,
            "minutes": minutes,
            "origins": origins,
            "template": "S08-QWEB-1",
            "retention": dossier.retention_id.id,
            "start": str(self.delivery_id.start_at or ""),
            "end": str(self.delivery_id.end_at or ""),
        }
        snapshot["client_recipients"] = dossier.client_contact_ids.ids if dossier.share_certificates else []
        snapshot["reference"] += "-" + hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:12]
        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        previous = dossier.output_ids.filtered(lambda d: d.kind == kind and d.sudo().snapshot == serialized)
        if previous:
            return previous[:1].action_download()
        report = self.env.ref("training_management.action_training_certificate")
        engine = self.env["ir.actions.report"]
        html = engine._render_template(
            "training_management.certificate_document",
            {
                "values": snapshot,
                "title": dict(KINDS)[kind],
                "issuer": self.company_id.name,
                "issued_at": fields.Datetime.now(),
                "issued_by": self.env.user.name,
            },
        ).decode()
        raw = engine._run_pdf_engine_without_processing(engine._get_pdf_engine(report), [html], report_ref=report)
        if not raw.startswith(b"%PDF-"):
            raise ValidationError(self.env._("Certificate PDF generation failed."))
        doc = self.env["training.document"]._append(
            {
                "dossier_id": dossier.id,
                "kind": kind,
                "filename": f"certificate-{self.id}-{kind}.pdf",
                "data": BinaryBytes(raw),
                "snapshot": serialized,
                "client_shared": dossier.share_certificates,
                "recipient_ids": [(6, 0, dossier.client_contact_ids.ids)] if dossier.share_certificates else [],
            }
        )
        return doc.with_user(self.env.user).action_download()


class ClosureLearningService(models.AbstractModel):
    _inherit = "training.learning.service"

    @api.private
    def _certificate_origin(self, enrollment, activity):
        # Called only after assigned-quality authorization, the common delivery
        # lock and the completion check. The existing S05 private lookup limits
        # elevation to this enrollment/activity; no private message is copied.
        progress = self._progress(enrollment, activity)
        origin = {
            "activity": activity.id,
            "name": activity.name,
            "criterion": activity.criterion,
            "dependencies": activity.dependency_ids.ids,
            "material_assignment": activity.material_assignment_id.id,
            "progress": progress.id,
            "revision": progress.revision if progress else 0,
            "state": progress.state if progress else False,
            "declared_at": str(progress.declared_at) if progress.declared_at else False,
            "submission": progress.latest_submission_id.id,
            "submission_fingerprint": progress.latest_submission_id.fingerprint,
        }
        if activity.criterion == "validation":
            origin["correction"] = (
                self.env["training.learning.entry"]
                .sudo()
                .search(
                    [
                        ("enrollment_id", "=", enrollment.id),
                        ("activity_id", "=", activity.id),
                        ("kind", "=", "correction"),
                    ],
                    order="id desc",
                    limit=1,
                )
                .id
            )
        if activity.criterion == "evaluation":
            origin.update(
                threshold=activity.evaluation_threshold, evaluation=self._evaluation_snapshot(enrollment, activity)
            )
        return origin

    @api.private
    def _evaluation_snapshot(self, enrollment, activity):
        return {"score": self._evaluation_result(enrollment, activity)}


class ClosureDocumentPolicy(models.AbstractModel):
    _inherit = "training.document.policy"

    @api.private
    def _document(self, record):
        target = record.sudo()
        if target._name == "ir.attachment" and target.res_model in ("training.proof", "training.document"):
            target = self.env[target.res_model].sudo().browse(target.res_id).exists()
        if target and target._name in ("training.proof", "training.document"):
            return target
        return super()._document(record)

    @api.private
    def _is_pedagogical(self, document):
        return (
            bool(document)
            and document._name in ("training.proof", "training.document")
            or super()._is_pedagogical(document)
        )

    @api.private
    def _restricted(self, document):
        return document._name in ("training.proof", "training.document") or super()._restricted(document)

    @api.private
    def _can_read(self, record):
        target = self._document(record)
        if target._name not in ("training.proof", "training.document"):
            return super()._can_read(record)
        user = self.env.user
        if not user.active or user._is_public() or target.company_id not in user.company_ids:
            return False
        dossier = target.dossier_id
        if user.has_group(QUALITY) and dossier.quality_id == user:
            return True
        if target._name == "training.proof":
            return user.has_group(COORDINATOR) and target.with_env(self.env(su=False)).has_access("read")
        if target.kind == "internal":
            return False
        if (
            target.kind in dict(KINDS)
            and dossier.enrollment_id.user_id == user
            and dossier.enrollment_id.participant_id == user.partner_id
        ):
            return True
        return bool(
            target.client_shared
            and user.partner_id in target.recipient_ids
            and user.partner_id in dossier.client_contact_ids
            and user.partner_id.commercial_partner_id == dossier.customer_id.commercial_partner_id
        )

    @api.private
    def _check_send(self, document, partners, **kwargs):
        if document and document._name in ("training.proof", "training.document"):
            raise ValidationError(self.env._("Download S08 documents through authenticated access only."))
        return super()._check_send(document, partners, **kwargs)


class ClosureReport(models.AbstractModel):
    _name = "report.training_management.certificate_document"
    _description = "Training Certificate Access"

    @api.model
    def _get_report_values(self, docids, data=None):
        # Report URLs must never create a new, unsnapshotted certificate.
        raise AccessError(self.env._("Use the preserved certificate download action."))
