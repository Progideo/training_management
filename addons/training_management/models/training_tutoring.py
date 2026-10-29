"""P13 booking: explicit entitlements, immutable published slots and server fences."""

from datetime import timedelta
from uuid import UUID

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_schedule import BOOKED, local_instant

COORDINATOR = "training_management.group_training_coordinator"


class TutoringEntitlement(models.Model):
    _name = "training.tutoring.entitlement"
    _description = "Included Tutoring Reservations"
    _check_company_auto = True
    _rec_name = "enrollment_id"

    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="restrict", check_company=True)
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    included_count = fields.Integer(required=True)
    service_reference = fields.Char(required=True)
    retention_id = fields.Many2one(
        "training.retention.category", required=True, ondelete="restrict", check_company=True
    )
    used_count = fields.Integer(compute="_compute_used")
    booking_ids = fields.One2many("training.tutoring.booking", "entitlement_id", readonly=True)
    _one_entitlement = models.Constraint("UNIQUE(enrollment_id)", "This enrollment already has a tutoring entitlement.")

    @api.depends("booking_ids.refunded")
    def _compute_used(self):
        for row in self:
            row.used_count = (
                self.env["training.tutoring.booking"]
                .sudo()
                .search_count([("entitlement_id", "=", row.id), ("refunded", "=", False)])
            )

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.tutoring.service"]._coordinator()
        allowed = {"enrollment_id", "included_count", "service_reference", "retention_id"}
        if any(set(v) - allowed or not allowed <= set(v) for v in vals_list):
            raise ValidationError(self.env._("Explicitly set the included count, service and retention policy."))
        enrollments = self.env["training.enrollment"].browse([v["enrollment_id"] for v in vals_list])
        enrollments.check_access("read")
        enrollments.delivery_id.company_id._lock_training_schedule()
        enrollments.delivery_id._serialize()
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        return super(TutoringEntitlement, self.with_context(clean)).create(vals_list)  # pylint: disable=context-overridden

    @api.constrains("enrollment_id", "included_count", "service_reference", "retention_id")
    def _check_entitlement(self):
        for row in self:
            if (
                row.included_count <= 0
                or not row.service_reference.strip()
                or not row.retention_id.approved_at
                or row.enrollment_id.state != "confirmed"
            ):
                raise ValidationError(
                    self.env._("Use a confirmed enrollment, a positive quota and an approved retention policy.")
                )

    def write(self, vals):  # pylint: disable=method-required-super
        raise ValidationError(self.env._("Keep the agreed tutoring entitlement unchanged."))

    @api.ondelete(at_uninstall=False)
    def _keep_entitlement(self):
        raise ValidationError(self.env._("Keep tutoring entitlements and their history."))


class TutoringSlot(models.Model):
    _name = "training.tutoring.slot"
    _description = "Tutoring Availability"
    _check_company_auto = True
    _order = "start_at, id"

    name = fields.Char(required=True)
    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    tutor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    room_id = fields.Many2one("resource.resource", ondelete="restrict", check_company=True)
    kind = fields.Selection([("individual", "Individual"), ("collective", "Collective")], required=True)
    capacity = fields.Integer(required=True)
    mode = fields.Selection([("onsite", "On site"), ("remote", "Remote")], required=True)
    location = fields.Char()
    meeting_url = fields.Char()
    timezone = fields.Selection(related="delivery_id.timezone", store=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    start_hour = fields.Float(required=True)
    end_hour = fields.Float(required=True)
    start_occurrence = fields.Selection([("first", "First occurrence"), ("second", "Second occurrence")])
    end_occurrence = fields.Selection([("first", "First occurrence"), ("second", "Second occurrence")])
    start_at = fields.Datetime(compute="_compute_instants", store=True)
    end_at = fields.Datetime(compute="_compute_instants", store=True)
    duration_hours = fields.Float(compute="_compute_instants", store=True)
    refund_policy = fields.Selection([("never", "No refund"), ("before", "Refund before deadline")], required=True)
    cancellation_hours = fields.Float(help="Hours before the start. Zero allows cancellation until the start.")
    cancellation_terms = fields.Text(required=True)
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published"), ("cancelled", "Cancelled")],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
    )
    booking_ids = fields.One2many("training.tutoring.booking", "slot_id", readonly=True)
    occupied_count = fields.Integer(compute="_compute_occupied")
    published_at = fields.Datetime(readonly=True, copy=False)
    published_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    cancelled_at = fields.Datetime(readonly=True, copy=False)
    cancelled_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")

    @api.depends("booking_ids.state")
    def _compute_occupied(self):
        for slot in self:
            slot.occupied_count = len(slot.booking_ids.filtered(lambda b: b.state == "confirmed"))

    @api.depends("start_date", "end_date", "start_hour", "end_hour", "timezone", "start_occurrence", "end_occurrence")
    def _compute_instants(self):
        for slot in self:
            slot.start_at = slot.end_at = False
            slot.duration_hours = 0
            if slot.start_date and slot.end_date and slot.timezone:
                try:
                    slot.start_at = local_instant(
                        slot.start_date, slot.start_hour, slot.timezone, slot.start_occurrence
                    )
                    slot.end_at = local_instant(slot.end_date, slot.end_hour, slot.timezone, slot.end_occurrence)
                except ValueError as exc:
                    raise ValidationError(
                        self.env._(
                            "Invalid local schedule: choose an existing time and specify its occurrence if ambiguous."
                        )
                    ) from exc
                slot.duration_hours = (slot.end_at - slot.start_at).total_seconds() / 3600

    @api.private
    def _lock(self):
        # Called only after exact actor/company checks. Same order as S04.
        self.company_id.sudo()._lock_training_schedule()
        self.delivery_id.sudo()._serialize()
        self.sorted("id").lock_for_update()
        self.invalidate_recordset()

    @api.constrains(
        "capacity",
        "kind",
        "start_at",
        "end_at",
        "tutor_id",
        "room_id",
        "refund_policy",
        "cancellation_hours",
        "cancellation_terms",
        "mode",
        "meeting_url",
        "location",
    )
    def _check_definition(self):
        for slot in self:
            if (
                slot.capacity <= 0
                or (slot.kind == "individual" and slot.capacity != 1)
                or not slot.start_at
                or not slot.end_at
                or slot.end_at <= slot.start_at
                or not slot.tutor_id.active
                or slot.company_id not in slot.tutor_id.company_ids
                or slot.tutor_id._is_public()
                or slot.cancellation_hours < 0
                or not slot.cancellation_terms.strip()
                or (slot.mode == "remote" and not (slot.meeting_url or "").startswith("https://"))
                or (slot.mode == "onsite" and not (slot.location or slot.room_id))
                or (
                    slot.room_id
                    and (
                        not slot.room_id.training_room
                        or not slot.room_id.active
                        or slot.room_id.company_id != slot.company_id
                    )
                )
                or (slot.room_id.training_capacity and slot.capacity > slot.room_id.training_capacity)
            ):
                raise ValidationError(
                    self.env._(
                        "Complete a valid tutoring period, tutor, capacity, location and cancellation conditions."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.tutoring.service"]._coordinator()
        allowed = self._definition_fields()
        values = [self._add_missing_default_values(dict(v)) for v in vals_list]
        if any(set(v) - allowed - {"state"} or v.get("state") != "draft" for v in values):
            raise ValidationError(self.env._("Create a draft slot; booking state and UTC instants are server-managed."))
        self.env["training.delivery"].browse([v["delivery_id"] for v in values]).check_access("read")
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        return super(TutoringSlot, self.with_context(clean)).create(values)  # pylint: disable=context-overridden

    @api.private
    def _definition_fields(self):
        return {
            "name",
            "delivery_id",
            "tutor_id",
            "room_id",
            "kind",
            "capacity",
            "mode",
            "location",
            "meeting_url",
            "start_date",
            "end_date",
            "start_hour",
            "end_hour",
            "start_occurrence",
            "end_occurrence",
            "refund_policy",
            "cancellation_hours",
            "cancellation_terms",
        }

    def write(self, vals):
        self.env["training.tutoring.service"]._coordinator()
        self.check_access("write")
        if set(vals) - self._definition_fields() or "delivery_id" in vals:
            raise ValidationError(self.env._("Use the controlled slot actions."))
        self._lock()
        if any(s.state != "draft" for s in self):
            raise ValidationError(self.env._("Keep published slots unchanged; cancel and replace them."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _keep_slot(self):
        self.env["training.tutoring.service"]._coordinator()
        self._lock()
        if any(s.state != "draft" for s in self):
            raise ValidationError(self.env._("Keep published slots and their history."))

    @api.private
    def _check_conflicts(self):
        for slot in self:
            tutor = slot.tutor_id.partner_id
            period = [
                ("company_id", "=", slot.company_id.id),
                ("start_at", "<", slot.end_at),
                ("end_at", ">", slot.start_at),
            ]
            sessions = (
                self.env["training.session"]
                .sudo()
                .search(period + [("cancelled", "=", False), ("delivery_id.state", "in", BOOKED)])
            )
            unavailable = self.env["training.unavailability"].sudo().search(period + [("active", "=", True)])
            others = self.sudo().search(period + [("id", "!=", slot.id), ("state", "=", "published")])
            if (
                sessions.filtered(lambda s: s.instructor_id == tutor or (slot.room_id and s.room_id == slot.room_id))
                or unavailable.filtered(
                    lambda u: u.instructor_id == tutor or (slot.room_id and u.room_id == slot.room_id)
                )
                or others.filtered(
                    lambda s: s.tutor_id == slot.tutor_id or (slot.room_id and s.room_id == slot.room_id)
                )
            ):
                raise ValidationError(self.env._("This tutor or room is unavailable during the proposed period."))

    def action_publish(self):
        self.env["training.tutoring.service"]._coordinator()
        self.check_access("write")
        self._lock()
        for slot in self:
            if slot.state == "published":
                continue
            if (
                slot.state != "draft"
                or slot.start_at <= fields.Datetime.now()
                or slot.delivery_id.state in ("cancelled", "closed")
            ):
                raise ValidationError(self.env._("Publish a future draft slot for an open delivery."))
            slot._check_definition()
            slot._check_conflicts()
            super(TutoringSlot, slot).write(
                {"state": "published", "published_at": fields.Datetime.now(), "published_by_id": self.env.uid}
            )  # pylint: disable=super-method-mismatch
        return True

    def action_cancel(self):
        self.env["training.tutoring.service"]._coordinator()
        self.check_access("write")
        self._lock()
        for slot in self:
            if slot.state == "cancelled":
                continue
            super(TutoringSlot, slot).write(
                {"state": "cancelled", "cancelled_at": fields.Datetime.now(), "cancelled_by_id": self.env.uid}
            )  # pylint: disable=super-method-mismatch
            for booking in slot.sudo().booking_ids.filtered(lambda b: b.state == "confirmed"):
                booking._cancel(refund=True)
        return True


class TutoringBooking(models.Model):
    _name = "training.tutoring.booking"
    _inherit = "training.learning.evidence"
    _description = "Private Tutoring Reservation"
    _check_company_auto = True
    _rec_name = "slot_id"

    entitlement_id = fields.Many2one(
        "training.tutoring.entitlement", required=True, ondelete="restrict", check_company=True
    )
    enrollment_id = fields.Many2one(related="entitlement_id.enrollment_id", store=True)
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    slot_id = fields.Many2one("training.tutoring.slot", required=True, ondelete="restrict", check_company=True)
    request_key = fields.Char(required=True)
    confirmed_at = fields.Datetime(required=True)
    state = fields.Selection(
        [("confirmed", "Confirmed"), ("cancelled", "Cancelled")], required=True, default="confirmed"
    )
    refund_policy = fields.Selection([("never", "No refund"), ("before", "Refund before deadline")], required=True)
    refund_deadline = fields.Datetime()
    cancellation_terms = fields.Text(required=True)
    cancelled_at = fields.Datetime()
    retention_id = fields.Many2one(related="entitlement_id.retention_id", store=True)
    cancelled_by_id = fields.Many2one("res.users", ondelete="restrict")
    refunded = fields.Boolean()
    _request_unique = models.Constraint(
        "UNIQUE(enrollment_id, request_key)", "This reservation request was already processed."
    )
    _one_active = models.UniqueIndex(
        "(slot_id, enrollment_id) WHERE state = 'confirmed'", "This participant already booked the slot."
    )

    @api.private
    def _cancel(self, refund):
        if self.state != "cancelled":
            self._store_evidence(
                {
                    "state": "cancelled",
                    "refunded": refund,
                    "cancelled_at": fields.Datetime.now(),
                    "cancelled_by_id": self.env.uid,
                }
            )
            self.env["training.tutoring.notice"]._queue_booking(self)


class TutoringService(models.AbstractModel):
    _name = "training.tutoring.service"
    _description = "Checked Tutoring Reservation Operations"

    @api.private
    def _coordinator(self):
        if not self.env.user.active or (not self.env.su and not self.env.user.has_group(COORDINATOR)):
            raise AccessError(self.env._("Only a training coordinator may configure tutoring."))

    @api.private
    def _reserve(self, enrollment_id, slot_id, request_key):
        enrollment = self.env["training.learning.service"]._enrollment(enrollment_id)
        slot = self.env["training.tutoring.slot"].sudo().browse(slot_id).exists()
        if (
            not slot
            or slot.delivery_id != enrollment.delivery_id
            or slot.tutor_id != (enrollment.learning_tutor_id or enrollment.delivery_id.learning_tutor_id)
        ):
            raise AccessError(self.env._("This tutoring slot is unavailable."))
        try:
            request_key = str(UUID(request_key))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError(self.env._("Reload the reservation form and try again.")) from exc
        slot._lock()
        enrollment = self.env["training.learning.service"]._enrollment(enrollment_id)
        if slot.tutor_id != (enrollment.learning_tutor_id or enrollment.delivery_id.learning_tutor_id):
            raise AccessError(self.env._("This tutoring slot is unavailable."))
        bookings = self.env["training.tutoring.booking"].sudo()
        previous = bookings.search([("enrollment_id", "=", enrollment.id), ("request_key", "=", request_key)], limit=1)
        if previous:
            if previous.slot_id != slot:
                raise ValidationError(self.env._("This request already refers to another slot."))
            return previous
        existing = bookings.search(
            [("enrollment_id", "=", enrollment.id), ("slot_id", "=", slot.id), ("state", "=", "confirmed")], limit=1
        )
        if existing:
            return existing
        entitlement = (
            self.env["training.tutoring.entitlement"].sudo().search([("enrollment_id", "=", enrollment.id)], limit=1)
        )
        used = (
            bookings.search_count([("entitlement_id", "=", entitlement.id), ("refunded", "=", False)])
            if entitlement
            else 0
        )
        if not entitlement or used >= entitlement.included_count:
            raise ValidationError(self.env._("No included tutoring reservation remains."))
        if slot.state != "published" or slot.start_at <= fields.Datetime.now():
            raise ValidationError(self.env._("This slot is no longer available."))
        if (
            not enrollment.access_start
            or not enrollment.access_end
            or slot.start_at < enrollment.access_start
            or slot.end_at > enrollment.access_end
        ):
            raise ValidationError(self.env._("Choose a tutoring slot within your authorized access period."))
        if bookings.search_count([("slot_id", "=", slot.id), ("state", "=", "confirmed")]) >= slot.capacity:
            raise ValidationError(self.env._("This tutoring slot is full."))
        slot._check_conflicts()
        booking = bookings._create_evidence(
            {
                "entitlement_id": entitlement.id,
                "slot_id": slot.id,
                "request_key": request_key,
                "confirmed_at": fields.Datetime.now(),
                "refund_policy": slot.refund_policy,
                "refund_deadline": slot.start_at - timedelta(hours=slot.cancellation_hours)
                if slot.refund_policy == "before"
                else False,
                "cancellation_terms": slot.cancellation_terms,
            }
        )
        self.env["training.tutoring.notice"]._queue_booking(booking)
        return booking

    @api.private
    def _cancel(self, enrollment_id, booking_id):
        enrollment = self.env["training.learning.service"]._enrollment(enrollment_id)
        booking = self.env["training.tutoring.booking"].sudo().browse(booking_id).exists()
        if not booking or booking.enrollment_id != enrollment:
            raise AccessError(self.env._("This private reservation is unavailable."))
        booking.slot_id._lock()
        self.env["training.learning.service"]._enrollment(enrollment_id)
        booking.invalidate_recordset()
        if booking.state == "cancelled":
            return booking
        now = fields.Datetime.now()
        if now >= booking.slot_id.start_at:
            raise ValidationError(self.env._("This tutoring slot has already started."))
        booking._cancel(refund=bool(booking.refund_policy == "before" and now <= booking.refund_deadline))
        return booking
