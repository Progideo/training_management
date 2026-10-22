"""ORG02: native resources, local-time sessions and serialized reservations."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


COORDINATOR = "training_management.group_training_coordinator"
BOOKED = ("confirmed", "ongoing", "delivered", "closed")


def local_instant(day, hour, zone, occurrence=None):
    """Reject gaps; require an explicit occurrence for an ambiguous wall time."""
    if not day or not 0 <= hour < 24:
        raise ValueError("Invalid local date or time")
    minutes = round(hour * 60)
    if minutes >= 1440:
        raise ValueError("Invalid local date or time")
    wall = datetime.combine(fields.Date.to_date(day), time()) + timedelta(minutes=minutes)
    tz = ZoneInfo(zone)
    candidates = []
    for fold in (0, 1):
        instant = wall.replace(tzinfo=tz, fold=fold).astimezone(timezone.utc)
        if instant.astimezone(tz).replace(tzinfo=None) == wall and instant not in candidates:
            candidates.append(instant)
    if not candidates:
        raise ValueError("This local time does not exist; choose another time")
    if len(candidates) > 1 and occurrence not in ("first", "second"):
        raise ValueError("This local time occurs twice; choose the first or second occurrence")
    return candidates[1 if len(candidates) > 1 and occurrence == "second" else 0].replace(tzinfo=None)


class ResCompany(models.Model):
    _inherit = "res.company"

    training_schedule_revision = fields.Integer(default=0, readonly=True, copy=False, groups=COORDINATOR)

    @api.private
    def _lock_training_schedule(self):
        if not self.env.su and not self.env.user.has_group(COORDINATOR):
            raise AccessError(self.env._("Only a training coordinator may reserve resources."))
        if not self.env.su and self - self.env.companies:
            raise AccessError(self.env._("The company is outside your allowed companies."))
        # Narrow elevation: only the revision fence, after explicit company/role
        # checks. A write forces stale REPEATABLE READ snapshots to fail/retry.
        for company in self.sorted("id").sudo():
            company.lock_for_update()
            company.invalidate_recordset(["training_schedule_revision"])
            super(ResCompany, company).write({"training_schedule_revision": company.training_schedule_revision + 1})  # pylint: disable=super-method-mismatch  # private revision fence
        return True

    def write(self, vals):
        if "training_schedule_revision" in vals:
            raise AccessError(self.env._("The reservation revision is server-managed."))
        return super().write(vals)


class ResourceResource(models.Model):
    _inherit = "resource.resource"

    training_room = fields.Boolean()
    training_capacity = fields.Integer(string="Room Capacity", help="Zero means not specified.")

    def write(self, vals):
        rooms = self.filtered("training_room")
        if rooms and set(vals) & {"training_capacity", "company_id", "training_room", "resource_type", "active"}:
            self.check_access("write")
            rooms.company_id._lock_training_schedule()
            # Integrity locks only: prevent a capacity edit racing a new lot or
            # admission. No dossier content is exposed through this elevation.
            deliveries = self.env["training.session"].sudo().search([("room_id", "in", rooms.ids)]).delivery_id
            deliveries._serialize()
        return super().write(vals)

    @api.constrains("training_capacity", "company_id", "resource_type", "training_room", "active")
    def _check_training_room(self):
        for room in self:
            if room.training_capacity < 0 or (
                room.training_room and (not room.company_id or room.resource_type != "material")
            ):
                raise ValidationError(
                    self.env._("A training room is a material resource of one company with a non-negative capacity.")
                )
            # Check every affected booking, even when a room administrator edits
            # it. This is a narrow integrity read, never returned to the caller.
            sessions = self.env["training.session"].sudo().search([("room_id", "=", room.id)])
            for session in sessions:
                session._check_room()


class TrainingSession(models.Model):
    _name = "training.session"
    _description = "Training Session"
    _order = "start_at, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    instructor_id = fields.Many2one("res.partner", ondelete="restrict", check_company=True)
    room_id = fields.Many2one("resource.resource", ondelete="restrict", check_company=True)
    mode = fields.Selection(
        [("onsite", "On site"), ("remote", "Remote"), ("blended", "Blended")], required=True, default="onsite"
    )
    location = fields.Char()
    meeting_url = fields.Char(string="Meeting Link")
    equipment = fields.Text()
    timezone = fields.Selection(related="delivery_id.timezone", store=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    start_hour = fields.Float(required=True, default=9)
    end_hour = fields.Float(required=True, default=17)
    start_occurrence = fields.Selection([("first", "First occurrence"), ("second", "Second occurrence")])
    end_occurrence = fields.Selection([("first", "First occurrence"), ("second", "Second occurrence")])
    start_at = fields.Datetime(compute="_compute_instants", store=True)
    end_at = fields.Datetime(compute="_compute_instants", store=True)
    cancelled = fields.Boolean(readonly=True, copy=False)

    @api.onchange("start_date")
    def _onchange_start_date(self):
        self.end_date = self.start_date

    @api.depends("start_date", "end_date", "start_hour", "end_hour", "timezone", "start_occurrence", "end_occurrence")
    def _compute_instants(self):
        for session in self:
            session.start_at = session.end_at = False
            if session.start_date and session.end_date and session.timezone:
                try:
                    session.start_at = local_instant(
                        session.start_date, session.start_hour, session.timezone, session.start_occurrence
                    )
                    session.end_at = local_instant(
                        session.end_date, session.end_hour, session.timezone, session.end_occurrence
                    )
                except ValueError as error:
                    messages = {
                        "Invalid local date or time": self.env._("Invalid local date or time"),
                        "This local time does not exist; choose another time": self.env._(
                            "This local time does not exist; choose another time"
                        ),
                        "This local time occurs twice; choose the first or second occurrence": self.env._(
                            "This local time occurs twice; choose the first or second occurrence"
                        ),
                    }
                    raise ValidationError(self.env._("Invalid local schedule: %s", messages[str(error)])) from error

    @api.private
    def _require_coordinator(self):
        self.check_access("write" if self else "create")
        if not self.env.su and not self.env.user.has_group(COORDINATOR):
            raise AccessError(self.env._("Only a training coordinator may change sessions."))

    @api.private
    def _check_room(self):
        for session in self.filtered(lambda item: not item.cancelled):
            room = session.room_id
            if room and (not room.training_room or not room.active or room.company_id != session.company_id):
                raise ValidationError(self.env._("Choose an active training room of the delivery company."))
            if room.training_capacity and session.delivery_id._occupancy() > room.training_capacity:
                raise ValidationError(self.env._("The room is smaller than the committed participant count."))

    @api.constrains("start_at", "end_at", "delivery_id", "room_id", "meeting_url")
    def _check_definition(self):
        for session in self:
            delivery = session.delivery_id
            if delivery.kind == "autonomous":
                raise ValidationError(self.env._("An autonomous offer does not need fictitious sessions."))
            if not session.start_at or not session.end_at or session.end_at <= session.start_at:
                raise ValidationError(self.env._("Set an increasing session period."))
            if session.start_at < delivery.start_at or session.end_at > delivery.end_at:
                raise ValidationError(
                    self.env._("Sessions must remain inside the delivery dates. Change those dates explicitly first.")
                )
            if session.meeting_url and not session.meeting_url.startswith("https://"):
                raise ValidationError(self.env._("Use an HTTPS meeting link."))
            session._check_room()

    @api.private
    def _conflicts(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("id", "!=", self.id),
            ("cancelled", "=", False),
            "|",
            ("delivery_id.state", "in", BOOKED),
            ("delivery_id", "=", self.delivery_id.id),
            ("start_at", "<", self.end_at),
            ("end_at", ">", self.start_at),
        ]
        # Same partner/room only; no cross-company resource sharing in S04.
        resources = []
        if self.instructor_id:
            resources.append(("instructor_id", "=", self.instructor_id.id))
        if self.room_id:
            resources.append(("room_id", "=", self.room_id.id))
        if len(resources) > 1:
            resources.insert(0, "|")
        sessions = self.search(domain + resources) if resources else self.browse()
        unavailable = (
            self.env["training.unavailability"]
            .search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("active", "=", True),
                    ("start_at", "<", self.end_at),
                    ("end_at", ">", self.start_at),
                ]
            )
            .filtered(
                lambda item: (
                    (item.instructor_id and item.instructor_id == self.instructor_id)
                    or (item.room_id and item.room_id == self.room_id)
                )
            )
        )
        return ["session:%s" % item.id for item in sessions] + ["unavailability:%s" % item.id for item in unavailable]

    @api.private
    def _reserve(self, reason=None):
        for session in self.filtered(lambda item: not item.cancelled):
            if (
                not session.instructor_id
                or (session.mode in ("onsite", "blended") and not (session.location or session.room_id))
                or (session.mode in ("remote", "blended") and not session.meeting_url)
            ):
                raise ValidationError(
                    self.env._("Complete the instructor, place and/or remote link before confirming.")
                )
            session._check_definition()
            conflicts = session._conflicts()
            if conflicts:
                if not reason or not reason.strip():
                    raise ValidationError(
                        self.env._("Instructor or room conflict. Change the schedule or confirm with a reason.")
                    )
                self.env["training.operation"]._record(session, {}, {"conflicts": conflicts}, reason.strip())

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # shared checked helper also used by wizard
        return self._create_scheduled(vals_list)

    @api.private
    def _create_scheduled(self, vals_list, reason=None):
        self._require_coordinator()
        if any(
            set(values) - (set(self.env["training.session.edit"]._schedule_fields()) | {"delivery_id"})
            for values in vals_list
        ):
            raise ValidationError(self.env._("Session instants and state are server-managed."))
        deliveries = self.env["training.delivery"].browse([values["delivery_id"] for values in vals_list])
        deliveries._require_coordinator()
        deliveries.company_id._lock_training_schedule()
        deliveries._serialize()
        if any(delivery.state not in ("preparation", "confirmed") for delivery in deliveries):
            raise ValidationError(self.env._("Sessions can only change before the delivery starts."))
        if any(delivery.state == "confirmed" for delivery in deliveries) and not (reason or "").strip():
            raise ValidationError(self.env._("Enter a reason for adding sessions after confirmation."))
        # Public RPC contexts may contain arbitrary default_* values. Only the
        # validated input above may define a session; generated values are not
        # allowed to enter through defaults (UTC instants, company, cancellation).
        clean_context = {key: value for key, value in self.env.context.items() if not key.startswith("default_")}
        records = super(TrainingSession, self.with_context(clean_context)).create(vals_list)  # pylint: disable=super-method-mismatch  # shared checked creation helper
        for record in records:
            self.env["training.operation"]._record(
                record, {}, {"name": record.name, "start_at": record.start_at, "end_at": record.end_at}, reason
            )
            if record.delivery_id.state == "confirmed":
                record._reserve(reason)
        return records

    @api.private
    def _apply_schedule(self, vals, reason=None, cancel=False):
        self.ensure_one()
        self._require_coordinator()
        if set(vals) - set(self.env["training.session.edit"]._schedule_fields()):
            raise ValidationError(self.env._("Only schedule fields may change."))
        self.company_id._lock_training_schedule()
        self.delivery_id._serialize()
        self.invalidate_recordset()
        if self.cancelled or self.delivery_id.state not in ("preparation", "confirmed"):
            raise ValidationError(self.env._("Only a future, non-cancelled session may change."))
        values = dict(vals, cancelled=bool(cancel))
        before = {key: self[key].id if self._fields[key].type == "many2one" else self[key] for key in values}
        changed = {key: value for key, value in values.items() if value != before[key]}
        if not changed:
            return
        if self.delivery_id.state == "confirmed" or cancel:
            reason = self.delivery_id._require_reason(reason)
        super().write(changed)  # pylint: disable=super-method-mismatch  # controlled schedule action
        if self.delivery_id.state == "confirmed":
            self._reserve(reason)
        after = {key: self[key].id if self._fields[key].type == "many2one" else self[key] for key in changed}
        self.env["training.operation"]._record(self, {key: before[key] for key in changed}, after, reason)

    def write(self, vals):
        self._require_coordinator()
        if set(vals) - set(self.env["training.session.edit"]._schedule_fields()):
            raise ValidationError(self.env._("Use the controlled session actions."))
        if any(item.delivery_id.state != "preparation" for item in self):
            raise ValidationError(self.env._("Use Change Session with a reason after confirmation."))
        self.company_id._lock_training_schedule()
        self.delivery_id._serialize()
        before = {
            item.id: {key: item[key].id if item._fields[key].type == "many2one" else item[key] for key in vals}
            for item in self
        }
        result = super().write(vals)
        for item in self:
            after = {key: item[key].id if item._fields[key].type == "many2one" else item[key] for key in vals}
            self.env["training.operation"]._record(item, before[item.id], after, False)
        return result

    def unlink(self):  # pylint: disable=method-required-super  # immutable history: cancellation replaces deletion
        raise AccessError(self.env._("Cancel a session to preserve its history."))  # pylint: disable=no-raise-unlink  # preserve audit

    def action_change(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.session.edit",
            "view_mode": "form",
            "target": "new",
            "context": {"default_session_id": self.id, "default_delivery_id": self.delivery_id.id},
        }

    def action_duplicate_session(self):
        self.ensure_one()
        self._require_coordinator()
        context = {"default_delivery_id": self.delivery_id.id}
        for key in self.env["training.session.edit"]._schedule_fields():
            context["default_" + key] = self[key].id if self._fields[key].type == "many2one" else self[key]
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.session.edit",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }


class TrainingUnavailability(models.Model):
    _name = "training.unavailability"
    _description = "Training Resource Unavailability"
    _check_company_auto = True

    name = fields.Char(default="Unavailable", required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    instructor_id = fields.Many2one("res.partner", ondelete="restrict", check_company=True)
    room_id = fields.Many2one("resource.resource", ondelete="restrict", check_company=True)
    start_at = fields.Datetime(required=True)
    end_at = fields.Datetime(required=True)
    active = fields.Boolean(default=True)

    @api.constrains("instructor_id", "room_id", "start_at", "end_at")
    def _check_definition(self):
        for item in self:
            if bool(item.instructor_id) == bool(item.room_id) or item.end_at <= item.start_at:
                raise ValidationError(self.env._("Choose one instructor or room and an increasing period."))
            if item.room_id and (not item.room_id.training_room or item.room_id.company_id != item.company_id):
                raise ValidationError(self.env._("Choose a training room of this company."))

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.session"]._require_coordinator()
        companies = self.env["res.company"].browse([vals.get("company_id", self.env.company.id) for vals in vals_list])
        companies._lock_training_schedule()
        records = super().create(vals_list)
        records._record_change({}, {"active": True})
        return records

    @api.private
    def _record_change(self, before, after):
        # No sensitive appointment description is required or copied.
        for item in self:
            sessions = self.env["training.session"].search(
                [
                    ("company_id", "=", item.company_id.id),
                    ("delivery_id.state", "in", BOOKED),
                    ("cancelled", "=", False),
                    ("start_at", "<", item.end_at),
                    ("end_at", ">", item.start_at),
                ]
            )
            sessions = sessions.filtered(
                lambda session: (
                    (item.instructor_id and session.instructor_id == item.instructor_id)
                    or (item.room_id and session.room_id == item.room_id)
                )
            )
            if item.active and sessions:
                raise ValidationError(
                    self.env._("This unavailability overlaps a confirmed session. Change that session first.")
                )

    def write(self, vals):
        self.check_access("write")
        self.company_id._lock_training_schedule()
        if "company_id" in vals:
            raise ValidationError(self.env._("An unavailability keeps its company."))
        result = super().write(vals)
        self._record_change({}, vals)
        return result
