from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .training_controlled import TERMINAL


class TrainingEnrollment(models.Model):
    _name = "training.enrollment"
    _inherit = "training.controlled"
    _description = "Training Enrollment"
    _check_company_auto = True
    _rec_name = "participant_id"
    _order = "requested_at, id"

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True, index=True)
    # Keep a company on an empty native form: a related value would be False
    # until delivery selection, making its check_company domain circular.
    # create() derives the stored company from the checked delivery; identity
    # cannot be rewritten afterwards. Existing stored company values are kept.
    company_id = fields.Many2one("res.company", required=True, readonly=True,
                                 default=lambda self: self.env.company, index=True)
    program_id = fields.Many2one(related="delivery_id.program_id", store=True)
    participant_id = fields.Many2one("res.partner", required=True, ondelete="restrict", check_company=True, index=True)
    user_id = fields.Many2one("res.users", ondelete="restrict", check_company=True)
    allocation_id = fields.Many2one("training.seat.allocation", ondelete="restrict", check_company=True)
    free_reason = fields.Text(string="Free Invitation Reason")
    requested_at = fields.Datetime(default=fields.Datetime.now, readonly=True, required=True, copy=False)
    state = fields.Selection([(v, label) for v, label in [
        ("requested", "Requested"), ("reserved", "Reserved"), ("waiting", "Waiting"),
        ("confirmed", "Confirmed"), ("closed", "Closed"), ("cancelled", "Cancelled"),
        ("replaced", "Replaced"), ("abandoned", "Abandoned")]], default="requested", required=True, readonly=True, copy=False)
    reservation_end = fields.Datetime(readonly=True, copy=False)
    prerequisites = fields.Selection([("pending", "Pending"), ("validated", "Validated"), ("waived", "Waived")], default="pending", required=True, readonly=True, copy=False)
    commercially_authorized = fields.Boolean(readonly=True, copy=False)
    access_state = fields.Selection([("unopened", "Unopened"), ("active", "Active"), ("suspended", "Suspended"), ("revoked", "Revoked")], default="unopened", required=True, readonly=True, copy=False)
    access_start = fields.Datetime(readonly=True, copy=False)
    access_end = fields.Datetime(readonly=True, copy=False)
    effective_access = fields.Selection([("unopened", "Unopened"), ("active", "Active"), ("scheduled", "Scheduled"), ("expired", "Expired"), ("suspended", "Suspended"), ("revoked", "Revoked"), ("blocked", "Blocked")], compute="_compute_effective_access")
    successor_id = fields.Many2one("training.enrollment", readonly=True, copy=False, ondelete="restrict", check_company=True)

    _reason_actions = (
        "action_validate_prerequisites", "action_waive_prerequisites", "action_authorize",
        "action_revoke_authorization", "action_open_access", "action_suspend_access",
        "action_revoke_access", "action_cancel", "action_abandon", "action_close", "action_confirm",
    )

    @api.private
    def _reason_labels(self):
        return {
            "action_validate_prerequisites": self.env._("Validate Prerequisites"),
            "action_waive_prerequisites": self.env._("Waive Prerequisites"),
            "action_authorize": self.env._("Authorize Commercially"),
            "action_revoke_authorization": self.env._("Withdraw Authorization"),
            "action_open_access": self.env._("Open / Resume Access"),
            "action_suspend_access": self.env._("Suspend Access"),
            "action_revoke_access": self.env._("Revoke Access"),
            "action_cancel": self.env._("Cancel Enrollment"),
            "action_abandon": self.env._("Abandon"),
            "action_close": self.env._("Close"),
            "action_confirm": self.env._("Confirm Enrollment"),
        }

    @api.depends("participant_id.display_name", "delivery_id.display_name")
    @api.depends_context("lang")
    def _compute_display_name(self):
        for enrollment in self:
            if not enrollment.id:
                enrollment.display_name = self.env._("New Enrollment")
                continue
            enrollment.display_name = self.env._(
                "%(participant)s — %(delivery)s (Enrollment %(reference)s)",
                participant=enrollment.participant_id.display_name or "—",
                delivery=enrollment.delivery_id.display_name or "—",
                reference=enrollment.id if isinstance(enrollment.id, int) else "—",
            )

    @api.private
    def _occupies(self, now=None):
        return self.state == "confirmed" or (self.state == "reserved" and self.reservation_end and self.reservation_end > (now or fields.Datetime.now()) and (not self.allocation_id or self.allocation_id._available(now)))

    @api.private
    def _validate_seat(self):
        self.ensure_one()
        if self.allocation_id:
            lot = self.allocation_id
            if lot.delivery_id != self.delivery_id or not lot._available():
                raise ValidationError(self.env._("Choose an available allocation for this delivery."))
            count = len(lot.enrollment_ids.filtered(lambda e: e._occupies()))
            if count > lot.quantity:
                raise ValidationError(self.env._("All places in this allocation have already been assigned."))
        elif not (self.free_reason or "").strip():
            raise ValidationError(self.env._("An enrollment without a commercial allocation needs a free invitation reason."))
        self.delivery_id._check_capacity()

    @api.private
    def _check_identity(self):
        self.ensure_one()
        if self.user_id and self.user_id.partner_id != self.participant_id:
            raise ValidationError(self.env._("The account must belong to the named participant."))
        duplicate = self.search_count([("id", "!=", self.id), ("delivery_id", "=", self.delivery_id.id), ("participant_id", "=", self.participant_id.id), ("state", "not in", list(TERMINAL))])
        if self.state not in TERMINAL and duplicate:
            raise ValidationError(self.env._("This participant already has an active enrollment for this delivery."))
        if self.allocation_id and self.allocation_id.delivery_id != self.delivery_id:
            raise ValidationError(self.env._("The allocation belongs to another delivery."))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_coordinator()
        with self.env.cr.savepoint():
            prepared = []
            for values in vals_list:
                values = dict(values)
                if set(values) - {"delivery_id", "participant_id", "user_id", "allocation_id", "free_reason"}:
                    raise ValidationError(self.env._("Create a requested enrollment without admission metadata."))
                values.update(state="requested", requested_at=fields.Datetime.now(), prerequisites="pending", commercially_authorized=False, access_state="unopened", access_start=False, access_end=False, reservation_end=False, successor_id=False)
                prepared.append(values)
            deliveries = self.env["training.delivery"].browse([v.get("delivery_id") or self.env.context.get("default_delivery_id") for v in prepared])
            deliveries._serialize()
            if any(d.state in ("delivered", "closed", "cancelled") for d in deliveries):
                raise ValidationError(self.env._("This delivery no longer accepts enrollments."))
            for values in prepared:
                delivery = self.env["training.delivery"].browse(values.get("delivery_id") or self.env.context.get("default_delivery_id"))
                values.update(company_id=delivery.company_id.id, program_id=delivery.program_id.id)
            records = super().create(prepared)
            for record in records:
                record._check_identity()
                if not record.allocation_id and not (record.free_reason or "").strip():
                    raise ValidationError(self.env._("Enter a commercial allocation or a free invitation reason."))
                self.env["training.operation"]._record(record, {}, {"state": record.state, "participant_id": record.participant_id.id}, record.free_reason)
            return records

    def write(self, vals):
        self._require_coordinator()
        if set(vals) - {"user_id"}:
            raise ValidationError(self.env._("Use admission and access actions; enrollment identity and origin are fixed."))
        with self.env.cr.savepoint():
            self.delivery_id._serialize()
            for enrollment in self:
                if "user_id" in vals and enrollment.access_state != "unopened":
                    raise ValidationError(self.env._("The account of an activated enrollment is fixed."))
                enrollment._store(vals)
                enrollment._check_identity()
        return True

    @api.private
    def _action(self, callback):
        with self.env.cr.savepoint():
            self._require_coordinator()
            self.delivery_id._serialize()
            self.invalidate_recordset()
            for enrollment in self:
                callback(enrollment)
        return True

    def action_wait(self):
        def change(e):
            if e.state not in ("requested", "waiting"):
                raise ValidationError(self.env._("Only a request may join the waiting list."))
            if e.state != "waiting":
                e._store({"state": "waiting"})
        return self._action(change)

    def action_reserve(self, expires_at=None, reason=None):
        def change(e):
            if e.state == "reserved" and e._occupies():
                return
            if e.state not in ("requested", "waiting", "reserved") or e.delivery_id.state in ("closed", "cancelled", "delivered"):
                raise ValidationError(self.env._("This enrollment cannot reserve a place."))
            deadline = fields.Datetime.to_datetime(expires_at or (e.allocation_id.expires_at if e.allocation_id else False))
            if not deadline or deadline <= fields.Datetime.now():
                raise ValidationError(self.env._("Set a future reservation deadline."))
            e._store({"state": "reserved", "reservation_end": deadline}, reason)
            e._validate_seat()
        return self._action(change)

    @api.private
    def _review_prerequisites(self, target, reason):
        def change(e):
            if e.state in TERMINAL:
                raise ValidationError(self.env._("A terminal enrollment keeps its admission history."))
            e._store({"prerequisites": target}, e._require_reason(reason))
        return self._action(change)

    def action_validate_prerequisites(self, reason=None):
        return self._review_prerequisites("validated", reason)

    def action_waive_prerequisites(self, reason=None):
        return self._review_prerequisites("waived", reason)

    @api.private
    def _check_admission(self):
        self.ensure_one()
        self._check_identity()
        if self.prerequisites == "pending":
            raise ValidationError(self.env._("Validate prerequisites or record a waiver before confirmation."))
        if self.delivery_id.state in ("closed", "cancelled", "delivered"):
            raise ValidationError(self.env._("The delivery no longer accepts admissions."))
        if self.allocation_id:
            if self.allocation_id.state != "confirmed":
                raise ValidationError(self.env._("Confirm the commercial allocation first."))
            self.allocation_id._check_source()
        self._validate_seat()

    def action_confirm(self, reason=None):
        def change(e):
            if e.state == "confirmed":
                return
            if e.state not in ("requested", "reserved") or (e.state == "reserved" and not e._occupies()):
                raise ValidationError(self.env._("Confirm a request or a non-expired reservation. Propose waiting places manually first."))
            e._store({"state": "confirmed"}, reason)
            e._check_admission()
        return self._action(change)

    def action_authorize(self, reason=None):
        def change(e):
            if e.state != "confirmed":
                raise ValidationError(self.env._("Confirm the enrollment before commercial authorization."))
            e._check_admission()
            if not e.commercially_authorized:
                e._store({"commercially_authorized": True}, e._require_reason(reason))
        return self._action(change)

    def action_revoke_authorization(self, reason=None):
        return self._action(lambda e: e._store({"commercially_authorized": False}, e._require_reason(reason)))

    def action_open_access(self, reason=None):
        def change(e):
            if e.access_state == "active":
                return
            if e.access_state == "revoked":
                raise ValidationError(self.env._("Revoked access cannot be reopened; review a new enrollment."))
            e._check_admission()
            if e.state != "confirmed" or not e.commercially_authorized or not e.user_id or not e.user_id.active:
                raise ValidationError(self.env._("Access requires a confirmed, authorized enrollment and an active personal account."))
            values = {"access_state": "active"}
            if not e.access_start:
                delivery = e.delivery_id
                start = fields.Datetime.now() if delivery.access_policy == "duration" else delivery.access_start
                end = start + timedelta(days=delivery.access_days) if delivery.access_policy == "duration" else delivery.access_end
                values.update(access_start=start, access_end=end)
            if (values.get("access_end") or e.access_end) <= fields.Datetime.now():
                raise ValidationError(self.env._("Extend an expired period before opening access."))
            e._store(values, e._require_reason(reason))
        return self._action(change)

    def action_suspend_access(self, reason=None):
        def change(e):
            if e.state != "confirmed" or e.access_state != "active":
                raise ValidationError(self.env._("Only active access on a confirmed enrollment can be suspended."))
            e._store({"access_state": "suspended"}, e._require_reason(reason))
        return self._action(change)

    def action_revoke_access(self, reason=None):
        return self._action(lambda e: e._store({"access_state": "revoked"}, e._require_reason(reason)))

    def action_extend_access(self, end_at=None, reason=None):
        def change(e):
            end = fields.Datetime.to_datetime(end_at)
            if not e.access_end or not end or end <= max(e.access_end, fields.Datetime.now()) or e.state != "confirmed":
                raise ValidationError(self.env._("An extension requires a confirmed enrollment and a later access end."))
            e._store({"access_end": end}, e._require_reason(reason))
        return self._action(change)

    @api.private
    def _effective_state(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        if self.access_state != "active":
            return self.access_state
        if (self.state != "confirmed" or not self.commercially_authorized or self.prerequisites == "pending"
                or not self.user_id or not self.user_id.active or self.user_id.partner_id != self.participant_id
                or self.delivery_id.state == "cancelled"):
            return "blocked"
        if not self.access_start or not self.access_end:
            return "blocked"
        if now < self.access_start:
            return "scheduled"
        return "expired" if now >= self.access_end else "active"

    @api.depends("state", "access_state", "commercially_authorized", "prerequisites", "user_id.active", "user_id.partner_id", "participant_id", "access_start", "access_end", "delivery_id.state")
    def _compute_effective_access(self):
        for enrollment in self:
            enrollment.effective_access = enrollment._effective_state()

    @api.private
    def _finish(self, target, reason):
        def change(e):
            if e.state == target:
                return
            if e.state in TERMINAL:
                raise ValidationError(self.env._("A terminal enrollment cannot change its history."))
            if target in ("closed", "abandoned") and e.state != "confirmed":
                raise ValidationError(self.env._("Only a confirmed enrollment may be closed or abandoned."))
            e._store({"state": target, "access_state": "revoked"}, e._require_reason(reason))
        return self._action(change)

    def action_cancel(self, reason=None):
        return self._finish("cancelled", reason)

    def action_abandon(self, reason=None):
        return self._finish("abandoned", reason)

    def action_close(self, reason=None):
        return self._finish("closed", reason)

    def action_transfer(self, target_id, replacement=False, reason=None):
        self.ensure_one()
        target = self.browse(target_id)
        target.ensure_one()
        target._require_coordinator()
        if type(replacement) is not bool:
            raise ValidationError(self.env._("Choose report or replacement explicitly."))
        with self.env.cr.savepoint():
            self._require_coordinator()
            (self.delivery_id | target.delivery_id)._serialize()
            self.invalidate_recordset()
            target.invalidate_recordset()
            if self.successor_id:
                if self.successor_id == target:
                    return True
                raise ValidationError(self.env._("This enrollment already has a successor."))
            if self.state in TERMINAL or target.state != "requested" or target == self or self.company_id != target.company_id:
                raise ValidationError(self.env._("Transfer to a new requested enrollment in the same operating company."))
            if replacement:
                if self.delivery_id != target.delivery_id or self.participant_id == target.participant_id or self.allocation_id != target.allocation_id:
                    raise ValidationError(self.env._("A replacement uses the same delivery and allocation with a different person."))
            elif self.participant_id != target.participant_id or self.delivery_id == target.delivery_id:
                raise ValidationError(self.env._("A report keeps the participant and selects another delivery."))
            self._store({"state": "replaced" if replacement else "cancelled", "access_state": "revoked", "successor_id": target.id}, self._require_reason(reason))
            self.env["training.operation"]._record(target, {}, {}, self.env._("Linked from enrollment %s", self.id))
        return True


    def action_open_operation(self):
        self.ensure_one()
        self._require_coordinator()
        return {"type": "ir.actions.act_window", "name": self.env._("Enrollment Operation"),
                "res_model": "training.enrollment.operation", "view_mode": "form", "target": "new",
                "context": {"default_enrollment_id": self.id}}
