from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .training_controlled import TERMINAL


class TrainingSeatAllocation(models.Model):
    _name = "training.seat.allocation"
    _inherit = ["training.controlled", "mail.thread", "mail.activity.mixin"]
    _description = "Training Seat Allocation"
    _check_company_auto = True
    _rec_name = "customer_id"

    delivery_id = fields.Many2one(
        "training.delivery", required=True, ondelete="restrict", check_company=True, index=True
    )
    # Keep a company on an empty native form: a related value would be False
    # until delivery selection, making its check_company domain circular.
    # create() derives the stored company from the checked delivery; identity
    # cannot be rewritten afterwards. Existing stored company values are kept.
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, default=lambda self: self.env.company, index=True
    )
    customer_id = fields.Many2one("res.partner", required=True, ondelete="restrict", check_company=True)
    quantity = fields.Integer(required=True, default=1)
    source_reference = fields.Char(string="Reservation Reference", required=True)
    expires_at = fields.Datetime(required=True)
    state = fields.Selection(
        [("reserved", "Reserved"), ("confirmed", "Confirmed"), ("expired", "Expired"), ("cancelled", "Cancelled")],
        default="reserved",
        required=True,
        readonly=True,
        copy=False,
    )
    enrollment_ids = fields.One2many("training.enrollment", "allocation_id")
    unnamed_seats = fields.Integer(compute="_compute_unnamed")

    _positive_quantity = models.Constraint("CHECK(quantity > 0)", "Allocate a positive number of places.")
    _unique_source = models.Constraint(
        "UNIQUE(delivery_id, source_reference)", "This reservation reference already exists for the delivery."
    )

    _reason_actions = ("action_confirm", "action_cancel")

    @api.private
    def _reason_labels(self):
        return {
            "action_confirm": self.env._("Confirm Allocation"),
            "action_cancel": self.env._("Cancel Allocation"),
        }

    @api.depends("quantity", "state", "expires_at", "enrollment_ids.state", "enrollment_ids.reservation_end")
    def _compute_unnamed(self):
        now = fields.Datetime.now()
        for lot in self:
            lot.unnamed_seats = (
                lot.quantity - len(lot.enrollment_ids.filtered(lambda e: e._occupies(now)))
                if lot._available(now)
                else 0
            )

    @api.private
    def _available(self, now=None):
        self.ensure_one()
        return self.state == "confirmed" or (
            self.state == "reserved" and self.expires_at and self.expires_at > (now or fields.Datetime.now())
        )

    @api.private
    def _holds_source(self, now=None):
        """A lot binds its commercial source while it is alive or still carries an open enrollment."""
        self.ensure_one()
        return self._available(now) or any(e.state not in TERMINAL for e in self.enrollment_ids)

    @api.private
    def _check_source(self):
        # Integration override validates the commercial line before commitment.
        raise ValidationError(self.env._("A confirmed allocation requires a confirmed commercial line."))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_coordinator()
        with self.env.cr.savepoint():
            prepared = []
            for values in vals_list:
                values = dict(values)
                if values.get("state", "reserved") != "reserved" or "enrollment_ids" in values:
                    raise ValidationError(self.env._("Create a reservation before confirming its places."))
                values.update(state="reserved", enrollment_ids=[])
                values["source_reference"] = (values.get("source_reference") or "").strip()
                prepared.append(values)
            deliveries = self.env["training.delivery"].browse(
                [v.get("delivery_id") or self.env.context.get("default_delivery_id") for v in prepared]
            )
            deliveries._serialize()
            if any(d.state in ("delivered", "closed", "cancelled") for d in deliveries):
                raise ValidationError(self.env._("This delivery no longer accepts reservations."))
            for values in prepared:
                delivery = self.env["training.delivery"].browse(
                    values.get("delivery_id") or self.env.context.get("default_delivery_id")
                )
                values["company_id"] = delivery.company_id.id
            records = super(
                TrainingSeatAllocation, self.with_context(mail_create_nolog=True, mail_create_nosubscribe=True)
            ).create(prepared)
            for record in records:
                if record.expires_at <= fields.Datetime.now() or not record.source_reference:
                    raise ValidationError(self.env._("A reservation needs a reference and a future expiry."))
                self.env["training.operation"]._record(
                    record, {}, {"quantity": record.quantity, "state": record.state}, False
                )
            deliveries._check_capacity()
            return records

    def write(self, vals):  # pylint: disable=method-required-super  # training records are changed only through their controlled actions
        self._require_coordinator()
        vals = self._write_technical(vals)
        if vals:
            raise ValidationError(self.env._("An allocation is fixed; cancel it and create a new reservation."))
        return True

    def action_confirm(self, reason=None):
        self._require_coordinator()
        with self.env.cr.savepoint():
            self.delivery_id._serialize()
            self.invalidate_recordset()
            for lot in self:
                if lot.state == "confirmed":
                    continue
                if not lot._available() or lot.delivery_id.state in ("closed", "cancelled", "delivered"):
                    raise ValidationError(self.env._("Only a live reservation can be confirmed."))
                lot._check_source()
                lot._store({"state": "confirmed"}, reason)
            self.delivery_id._check_capacity()
        return True

    def action_cancel(self, reason=None):
        self._require_coordinator()
        with self.env.cr.savepoint():
            self.delivery_id._serialize()
            self.invalidate_recordset()
            for lot in self:
                if lot.state == "cancelled":
                    continue
                reason = lot._require_reason(reason)
                for enrollment in lot.enrollment_ids.filtered(lambda e: e.state not in TERMINAL):
                    enrollment._store({"state": "cancelled", "access_state": "revoked"}, reason)
                lot._store({"state": "cancelled"}, reason)
        return True

    def action_release_places(self, quantity, reason=None):
        self.ensure_one()
        with self.env.cr.savepoint():
            self._require_coordinator()
            self.delivery_id._serialize()
            self.invalidate_recordset()
            if (
                type(quantity) is not int
                or quantity <= 0
                or quantity >= self.quantity
                or self.state not in ("reserved", "confirmed")
            ):
                raise ValidationError(
                    self.env._(
                        "Release a positive number below the allocation quantity, or cancel the whole allocation."
                    )
                )
            remaining = self.quantity - quantity
            if len(self.enrollment_ids.filtered(lambda e: e._occupies())) > remaining:
                raise ValidationError(
                    self.env._("Cancel or transfer the affected enrollments before releasing their places.")
                )
            self._store({"quantity": remaining}, self._require_reason(reason))
        return True

    def action_extend_deadline(self, expires_at=None, reason=None):
        self.ensure_one()
        with self.env.cr.savepoint():
            self._require_coordinator()
            self.delivery_id._serialize()
            self.invalidate_recordset()
            now = fields.Datetime.now()
            deadline = fields.Datetime.to_datetime(expires_at)
            if (
                self.state != "reserved"
                or not self._available(now)
                or self.delivery_id.state in ("delivered", "closed", "cancelled")
            ):
                raise ValidationError(self.env._("Only a live reservation can be extended."))
            if not deadline or deadline <= max(self.expires_at, now):
                raise ValidationError(self.env._("An extension needs a future deadline later than the current one."))
            self._store({"expires_at": deadline}, self._require_reason(reason))
        return True

    def action_expire(self):
        self._require_coordinator()
        with self.env.cr.savepoint():
            self.delivery_id._serialize()
            self.invalidate_recordset()
            for lot in self:
                if lot.state == "reserved" and lot.expires_at <= fields.Datetime.now():
                    for enrollment in lot.enrollment_ids.filtered(lambda e: e.state == "reserved"):
                        enrollment._store({"state": "requested"}, self.env._("Reservation expired"))
                    lot._store({"state": "expired"}, self.env._("Reservation expired"))
        return True

    def action_open_extend(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Extend Deadline"),
            "res_model": "training.allocation.extend",
            "view_mode": "form",
            "target": "new",
            "context": {"default_allocation_id": self.id},
        }

    def action_open_release(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Release Places"),
            "res_model": "training.allocation.release",
            "view_mode": "form",
            "target": "new",
            "context": {"default_allocation_id": self.id},
        }
