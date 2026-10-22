from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .training_controlled import TERMINAL, TrainingControlled


class TrainingDelivery(models.Model):
    _name = "training.delivery"
    _inherit = "training.controlled"
    _description = "Training Delivery"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    program_id = fields.Many2one("training.program.version", required=True, ondelete="restrict", check_company=True)
    kind = fields.Selection([("session", "Dated Session"), ("autonomous", "Autonomous Offer")], required=True, default="session")
    delivery_mode = fields.Selection(related="program_id.delivery_mode")
    responsible_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="restrict", check_company=True)
    start_at = fields.Datetime()
    end_at = fields.Datetime()
    timezone = fields.Selection(selection=lambda self: self.env["res.partner"].fields_get(["tz"])["tz"]["selection"], required=True, default=lambda self: self.env.user.tz or "UTC")
    capacity = fields.Integer(help="Zero means unlimited.")
    opening_threshold = fields.Integer()
    state = fields.Selection([(v, label) for v, label in [
        ("preparation", "Preparation"), ("confirmed", "Confirmed"), ("ongoing", "Ongoing"),
        ("delivered", "Delivered"), ("closed", "Closed"), ("cancelled", "Cancelled")]], default="preparation", required=True, readonly=True, copy=False)
    access_policy = fields.Selection([("fixed", "Fixed Period"), ("duration", "Duration from Explicit Activation")], default="fixed", required=True)
    access_start = fields.Datetime()
    access_end = fields.Datetime()
    access_days = fields.Integer()
    allocation_ids = fields.One2many("training.seat.allocation", "delivery_id")
    enrollment_ids = fields.One2many("training.enrollment", "delivery_id")
    operation_ids = fields.One2many("training.operation", "delivery_id", readonly=True)
    occupied_seats = fields.Integer(compute="_compute_seats")
    below_threshold = fields.Boolean(compute="_compute_seats")
    revision = fields.Integer(default=0, readonly=True, copy=False)

    _valid_capacity = models.Constraint("CHECK(capacity >= 0 AND opening_threshold >= 0 AND access_days >= 0)", "Capacity, threshold and duration cannot be negative.")

    _reason_actions = ("action_confirm", "action_cancel", "action_close")

    @api.private
    def _reason_labels(self):
        return {
            "action_confirm": self.env._("Confirm below Threshold"),
            "action_cancel": self.env._("Cancel Delivery"),
            "action_close": self.env._("Close"),
        }

    @api.private
    def _serialize(self):
        self._require_coordinator()
        self.sorted("id").lock_for_update()
        self.invalidate_recordset()
        for delivery in self.sorted("id"):
            # Write fence: a stale REPEATABLE READ snapshot must fail, even after
            # a competing transaction released its lock. A lock alone is not enough.
            super(TrainingControlled, delivery).write({"revision": delivery.revision + 1})

    @api.private
    def _occupancy(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        lots = self.allocation_ids.filtered(lambda lot: lot.state == "confirmed" or (
            lot.state == "reserved" and lot.expires_at and lot.expires_at > now))
        free = self.enrollment_ids.filtered(lambda item: not item.allocation_id and item._occupies(now))
        return sum(lots.mapped("quantity")) + len(free)

    @api.depends("capacity", "opening_threshold", "allocation_ids.state", "allocation_ids.quantity", "allocation_ids.expires_at", "enrollment_ids.state", "enrollment_ids.reservation_end")
    def _compute_seats(self):
        for delivery in self:
            delivery.occupied_seats = delivery._occupancy()
            delivery.below_threshold = delivery.occupied_seats < delivery.opening_threshold

    @api.private
    def _check_capacity(self):
        for delivery in self:
            if delivery.capacity and delivery._occupancy() > delivery.capacity:
                raise ValidationError(self.env._("The delivery capacity would be exceeded."))

    @api.constrains("program_id", "kind", "start_at", "end_at", "access_policy", "access_start", "access_end", "access_days", "capacity", "opening_threshold")
    def _check_definition(self):
        for delivery in self:
            if delivery.program_id.state == "draft":
                raise ValidationError(self.env._("Choose a validated programme version."))
            if delivery.kind == "session" and (not delivery.start_at or not delivery.end_at or delivery.end_at <= delivery.start_at):
                raise ValidationError(self.env._("A dated session requires an increasing start and end period."))
            if delivery.kind == "autonomous" and (delivery.start_at or delivery.end_at):
                raise ValidationError(self.env._("An autonomous offer does not require fictitious session dates."))
            if delivery.access_policy == "fixed" and (not delivery.access_start or not delivery.access_end or delivery.access_end <= delivery.access_start):
                raise ValidationError(self.env._("Set an increasing access period."))
            if delivery.access_policy == "duration" and delivery.access_days <= 0:
                raise ValidationError(self.env._("Set a positive access duration."))
            if delivery.capacity and delivery.opening_threshold > delivery.capacity:
                raise ValidationError(self.env._("The opening threshold cannot exceed capacity."))
            delivery._check_capacity()

    @api.model_create_multi
    def create(self, vals_list):
        self._require_coordinator()
        prepared = []
        for values in vals_list:
            values = dict(values)
            if set(values) & {"revision", "allocation_ids", "enrollment_ids", "operation_ids"} or values.get("state", "preparation") != "preparation":
                raise ValidationError(self.env._("Create a delivery in preparation without generated records."))
            values.update(state="preparation", revision=0, allocation_ids=[], enrollment_ids=[], operation_ids=[])
            prepared.append(values)
        records = super().create(prepared)
        for record in records:
            self.env["training.operation"]._record(record, {}, {"state": record.state, "program_id": record.program_id.id}, False)
        return records

    def write(self, vals):
        self._require_coordinator()
        if set(vals) & {"state", "revision", "allocation_ids", "enrollment_ids", "operation_ids"}:
            raise ValidationError(self.env._("Use the delivery workflow to change its state."))
        with self.env.cr.savepoint():
            self._serialize()
            for delivery in self:
                if set(vals) & {"company_id", "program_id", "kind", "access_policy", "access_start", "access_end", "access_days", "start_at", "end_at"} and (delivery.enrollment_ids or delivery.allocation_ids):
                    raise ValidationError(self.env._("A delivery with inscriptions keeps its programme, dates and access policy. Change the dates with the dedicated action."))
                if "company_id" in vals and delivery.allocation_ids:
                    raise ValidationError(self.env._("A delivery with allocated places keeps its company."))
                delivery._store(vals)
            self._check_definition()
        return True

    @api.private
    def _transition(self, target, reason=None):
        with self.env.cr.savepoint():
            self._serialize()
            transitions = {"preparation": "confirmed", "confirmed": "ongoing", "ongoing": "delivered", "delivered": "closed"}
            for delivery in self:
                if delivery.state == target:
                    continue
                if target == "cancelled":
                    if delivery.state in ("closed", "cancelled"):
                        raise ValidationError(self.env._("A closed delivery cannot be cancelled."))
                    reason = delivery._require_reason(reason)
                    for enrollment in delivery.enrollment_ids.filtered(lambda e: e.state not in TERMINAL):
                        enrollment._store({"state": "cancelled", "access_state": "revoked"}, reason)
                    for lot in delivery.allocation_ids.filtered(lambda lot: lot.state in ("reserved", "confirmed")):
                        lot._store({"state": "cancelled"}, reason)
                else:
                    if transitions.get(delivery.state) != target:
                        raise ValidationError(self.env._("This delivery transition is not allowed."))
                    if target == "confirmed" and delivery._occupancy() < delivery.opening_threshold:
                        reason = delivery._require_reason(reason)
                    elif target == "closed":
                        reason = delivery._require_reason(reason)
                        if delivery.enrollment_ids.filtered(lambda e: e.state in ("requested", "reserved", "waiting")):
                            raise ValidationError(self.env._("Settle requested, reserved and waiting enrollments before closing the delivery."))
                        for enrollment in delivery.enrollment_ids.filtered(lambda e: e.state == "confirmed"):
                            enrollment._store({"state": "closed", "access_state": "revoked"}, reason)
                delivery._store({"state": target}, reason)
        return True

    def action_change_dates(self, start_at=None, end_at=None, access_start=None, access_end=None, reason=None):
        """Move the session or the fixed access period of a delivery that is still to come.

        ``None`` keeps the current value. Programme, company, nature and access
        policy stay fixed; access periods already computed on enrollments are
        never rewritten.
        """
        self.ensure_one()
        with self.env.cr.savepoint():
            self._require_coordinator()
            self._serialize()
            self.invalidate_recordset()
            if self.state not in ("preparation", "confirmed"):
                raise ValidationError(self.env._("Dates can only change while the delivery is in preparation or confirmed."))
            requested = {"start_at": start_at, "end_at": end_at, "access_start": access_start, "access_end": access_end}
            changes = {}
            for key, value in requested.items():
                value = fields.Datetime.to_datetime(value) if value is not None else None
                if value is not None and value != self[key]:
                    changes[key] = value
            if not changes:
                return True
            if self.kind == "autonomous" and {"start_at", "end_at"} & set(changes):
                raise ValidationError(self.env._("An autonomous offer does not require fictitious session dates."))
            if self.access_policy != "fixed" and {"access_start", "access_end"} & set(changes):
                raise ValidationError(self.env._("Access dates only apply to a fixed access period."))
            reason = self._require_reason(reason)
            if {"access_start", "access_end"} & set(changes):
                new_start = changes.get("access_start", self.access_start)
                new_end = changes.get("access_end", self.access_end)
                if (new_start > self.access_start or new_end < self.access_end) and self.enrollment_ids.filtered(lambda e: e.access_state == "active"):
                    raise ValidationError(self.env._("A fixed access period cannot be shortened while an access is active."))
            self._store(changes, reason)
        return True

    def action_open_dates(self):
        self.ensure_one()
        self._require_coordinator()
        return {"type": "ir.actions.act_window", "name": self.env._("Change Dates"),
                "res_model": "training.delivery.dates", "view_mode": "form", "target": "new",
                "context": {"default_delivery_id": self.id}}

    def action_confirm(self, reason=None):
        return self._transition("confirmed", reason)

    def action_start(self):
        return self._transition("ongoing")

    def action_deliver(self):
        return self._transition("delivered")

    def action_close(self, reason=None):
        return self._transition("closed", reason)

    def action_cancel(self, reason=None):
        return self._transition("cancelled", reason)
