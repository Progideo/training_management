"""Immutable client programme variants; standard catalogue versions stay untouched."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, LockError, ValidationError


class TrainingIntraVersion(models.Model):
    _name = "training.intra.version"
    _description = "Client Intra Programme Version"
    _check_company_auto = True
    _rec_name = "version"
    _order = "id desc"

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    customer_id = fields.Many2one("res.partner", required=True, ondelete="restrict", check_company=True)
    program_id = fields.Many2one(
        "training.program.version", required=True, readonly=True, ondelete="restrict", check_company=True
    )
    previous_id = fields.Many2one("training.intra.version", ondelete="restrict", check_company=True)
    version = fields.Char(required=True)
    objectives = fields.Text(required=True)
    business_cases = fields.Text(required=True)
    instructions = fields.Text(required=True)
    data = fields.Binary(attachment=False, copy=False, string="Confidential Client PDF")
    filename = fields.Char()
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("confirmed", "Confirmed")],
        default="draft",
        readonly=True,
        required=True,
        copy=False,
    )
    submitted_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    submitted_at = fields.Datetime(readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    approved_at = fields.Datetime(readonly=True, copy=False)
    approved_contact_id = fields.Many2one("res.partner", readonly=True, copy=False, ondelete="restrict")
    approval_reference = fields.Char(copy=False, help="Reference to the client agreement recorded by the coordinator.")
    agreement_contact_id = fields.Many2one("res.partner", copy=False, check_company=True, ondelete="restrict")
    confirmed_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    confirmed_at = fields.Datetime(readonly=True, copy=False)

    _unique_version = models.Constraint(
        "UNIQUE(delivery_id, version)", "This intra version already exists for the delivery."
    )
    _one_successor = models.Constraint("UNIQUE(previous_id)", "A successor already exists for this intra version.")

    @api.private
    def _require_coordinator(self):
        self.check_access("write" if self else "create")
        if not self.env.su and not self.env.user.has_group("training_management.group_training_coordinator"):
            raise AccessError(self.env._("Only a training coordinator may manage client programme versions."))

    @api.private
    def _content_fields(self):
        return {
            "version",
            "objectives",
            "business_cases",
            "instructions",
            "data",
            "filename",
            "approval_reference",
            "agreement_contact_id",
        }

    @api.model_create_multi
    def create(self, vals_list):
        self._require_coordinator()
        prepared = []
        seen = set()
        for vals in vals_list:
            vals = self._add_missing_default_values(dict(vals))
            if (
                set(vals)
                - self._content_fields()
                - {"delivery_id", "customer_id", "previous_id", "program_id", "state"}
                or vals.get("state", "draft") != "draft"
            ):
                raise ValidationError(self.env._("Create a draft client version without approval metadata."))
            delivery = self.env["training.delivery"].browse(vals["delivery_id"])
            if delivery.id in seen:
                raise ValidationError(self.env._("Create one client successor per delivery at a time."))
            seen.add(delivery.id)
            delivery._serialize()
            existing = self.search([("delivery_id", "=", delivery.id)])
            customer = self.env["res.partner"].browse(vals["customer_id"])
            if customer.commercial_partner_id != customer or any(v.customer_id != customer for v in existing):
                raise ValidationError(
                    self.env._("An intra delivery and all its variants belong to one client company.")
                )
            if any(a.customer_id.commercial_partner_id != customer for a in delivery.allocation_ids):
                raise ValidationError(self.env._("An intra variant cannot cover another client's allocation."))
            if vals.get("previous_id"):
                previous = self.browse(vals["previous_id"])
                previous.check_access("read")
                if previous.delivery_id != delivery or previous.customer_id != customer or previous.state == "draft":
                    raise ValidationError(self.env._("Choose a frozen predecessor from the same client delivery."))
            elif existing:
                raise ValidationError(self.env._("Link the new intra version to its predecessor."))
            if vals.get("program_id") and vals["program_id"] != delivery.program_id.id:
                raise ValidationError(self.env._("The client version must use the delivery standard programme."))
            vals["program_id"] = delivery.program_id.id
            prepared.append(vals)
        return super().create(prepared)

    @api.onchange("delivery_id")
    def _onchange_delivery_id(self):
        self.program_id = self.delivery_id.program_id

    @api.constrains("objectives", "business_cases", "instructions", "version", "data", "filename")
    def _check_content(self):
        for row in self:
            if any(not (row[f] or "").strip() for f in ("objectives", "business_cases", "instructions", "version")):
                raise ValidationError(
                    self.env._("Complete the client objectives, business cases, instructions and version.")
                )
            if row.data and (
                not row.data.content.startswith(b"%PDF-") or not (row.filename or "").lower().endswith(".pdf")
            ):
                raise ValidationError(self.env._("The confidential client document must be a PDF."))

    def write(self, vals):
        self._require_coordinator()
        self.delivery_id._serialize()
        self.lock_for_update()
        self.invalidate_recordset()
        # Agreement evidence can be recorded after submission, without changing
        # the exact programme content the client is asked to approve.
        agreement_only = set(vals) <= {"approval_reference", "agreement_contact_id"}
        if set(vals) - self._content_fields() or any(
            r.state != "draft" and not (r.state == "submitted" and agreement_only) for r in self
        ):
            raise ValidationError(
                self.env._("Keep the frozen intra version. Create a successor and obtain a new client agreement.")
            )
        return super().write(vals)

    def action_submit(self):
        # pylint: disable=super-method-mismatch  # controlled state and server-authored evidence
        self._require_coordinator()
        self.delivery_id._serialize()
        self.lock_for_update()
        self.invalidate_recordset()
        if any(r.state not in ("draft", "submitted") for r in self):
            raise ValidationError(self.env._("This client version is already approved."))
        self._check_content()
        return super(TrainingIntraVersion, self.filtered(lambda r: r.state == "draft")).write(
            {"state": "submitted", "submitted_by_id": self.env.uid, "submitted_at": fields.Datetime.now()}
        )

    @api.private
    def _approve(self, actor, contact):
        # pylint: disable=super-method-mismatch  # controlled state and server-authored evidence
        self.ensure_one()
        try:
            self.lock_for_update()
        except LockError as error:
            raise ConcurrencyError("Concurrent client agreement; retry with a fresh snapshot") from error
        self.invalidate_recordset()
        if self.state in ("approved", "confirmed"):
            return True
        if self.state != "submitted":
            raise ValidationError(self.env._("Submit this exact client version before recording the agreement."))
        return super().write(
            {
                "state": "approved",
                "approved_by_id": actor.id,
                "approved_contact_id": contact.id,
                "approved_at": fields.Datetime.now(),
            }
        )

    def action_record_agreement(self):
        self._require_coordinator()
        for row in self:
            if (
                not row.approval_reference
                or not row.agreement_contact_id
                or row.agreement_contact_id.commercial_partner_id != row.customer_id
            ):
                raise ValidationError(
                    self.env._("Record the client contact and the reference of their agreement on this version.")
                )
            row._approve(self.env.user, row.agreement_contact_id)
        return True

    def action_confirm(self):
        # pylint: disable=super-method-mismatch  # controlled state and server-authored evidence
        self._require_coordinator()
        self.delivery_id._serialize()
        self.lock_for_update()
        self.invalidate_recordset()
        for row in self:
            if row.state == "confirmed" and row.delivery_id.intra_version_id == row:
                continue
            if row.state != "approved" or self.search_count([("previous_id", "=", row.id)]):
                raise ValidationError(self.env._("Confirm the latest client version only after its agreement."))
            super(TrainingIntraVersion, row).write(
                {"state": "confirmed", "confirmed_by_id": self.env.uid, "confirmed_at": fields.Datetime.now()}
            )
            row.delivery_id._store({"intra_version_id": row.id})
        return True

    def action_new_version(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_delivery_id": self.delivery_id.id,
                "default_customer_id": self.customer_id.id,
                "default_previous_id": self.id,
                "default_objectives": self.objectives,
                "default_business_cases": self.business_cases,
                "default_instructions": self.instructions,
            },
        }

    def unlink(self):  # pylint: disable=method-required-super  # preserve client agreement history
        raise AccessError(self.env._("Client programme version history must be preserved."))  # pylint: disable=no-raise-unlink  # immutable history


class TrainingIntraDelivery(models.Model):
    _inherit = "training.delivery"  # pylint: disable=consider-merging-classes-inherited  # intra content lifecycle is separate from attendance and scheduling

    intra_version_id = fields.Many2one(
        "training.intra.version",
        readonly=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
        groups="training_management.group_training_coordinator",
    )
    intra_version_ids = fields.One2many(
        "training.intra.version", "delivery_id", groups="training_management.group_training_coordinator"
    )

    @api.model_create_multi
    def create(self, vals_list):
        if (
            any(v.get("intra_version_id") or v.get("intra_version_ids") for v in vals_list)
            or self.env.context.get("default_intra_version_id")
            or self.env.context.get("default_intra_version_ids")
        ):
            raise AccessError(self.env._("Create the delivery first, then obtain agreement on its client version."))
        return super().create([dict(v, intra_version_id=False, intra_version_ids=[]) for v in vals_list])

    def write(self, vals):
        if "intra_version_id" in vals:
            raise AccessError(self.env._("Use Confirm on the approved client programme version."))
        if set(vals) & {"company_id", "program_id"} and self.intra_version_ids:
            raise ValidationError(
                self.env._("A delivery with client versions keeps its operator and standard programme.")
            )
        return super().write(vals)

    @api.private
    def _transition(self, target, reason=None, conflict_reason=None):
        if target == "confirmed" and any(r.intra_version_ids and not r.intra_version_id for r in self):
            raise ValidationError(
                self.env._("Confirm the approved client programme before confirming the intra delivery.")
            )
        return super()._transition(target, reason, conflict_reason)


class TrainingIntraAllocation(models.Model):
    _inherit = "training.seat.allocation"  # pylint: disable=consider-merging-classes-inherited  # intra client scope is independent of commercial commitment

    @api.constrains("delivery_id", "customer_id")
    def _check_intra_customer(self):
        for allocation in self:
            if any(
                v.customer_id != allocation.customer_id.commercial_partner_id
                for v in allocation.delivery_id.intra_version_ids
            ):
                raise ValidationError(self.env._("An intra variant cannot cover another client's allocation."))
