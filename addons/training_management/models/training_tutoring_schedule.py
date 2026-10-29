"""Reciprocal S04/P13 integrity: one resource fence, no duplicated calendars."""

from odoo import api, models
from odoo.exceptions import ValidationError


class TutoringSession(models.Model):
    _inherit = "training.session"

    @api.private
    def _reserve(self, reason=None):
        result = super()._reserve(reason)
        for session in self.filtered(lambda s: not s.cancelled):
            slots = (
                self.env["training.tutoring.slot"]
                .sudo()
                .search(
                    [
                        ("company_id", "=", session.company_id.id),
                        ("state", "=", "published"),
                        ("start_at", "<", session.end_at),
                        ("end_at", ">", session.start_at),
                    ]
                )
            )
            if slots.filtered(
                lambda s: (
                    s.tutor_id.partner_id == session.instructor_id or (session.room_id and s.room_id == session.room_id)
                )
            ):
                raise ValidationError(self.env._("Cancel the conflicting tutoring slot before reserving this session."))
        return result


class TutoringUnavailability(models.Model):
    _inherit = "training.unavailability"

    @api.private
    def _record_change(self, before, after):
        result = super()._record_change(before, after)
        for item in self.filtered("active"):
            slots = (
                self.env["training.tutoring.slot"]
                .sudo()
                .search(
                    [
                        ("company_id", "=", item.company_id.id),
                        ("state", "=", "published"),
                        ("start_at", "<", item.end_at),
                        ("end_at", ">", item.start_at),
                    ]
                )
            )
            if slots.filtered(
                lambda s: s.tutor_id.partner_id == item.instructor_id or (item.room_id and s.room_id == item.room_id)
            ):
                raise ValidationError(
                    self.env._("Cancel the conflicting tutoring slot before recording this unavailability.")
                )
        return result


class TutoringRoom(models.Model):
    _inherit = "resource.resource"

    def write(self, vals):
        slots = (
            self.env["training.tutoring.slot"].sudo().search([("room_id", "in", self.ids), ("state", "=", "published")])
        )
        if slots and set(vals) & {"training_capacity", "company_id", "training_room", "resource_type", "active"}:
            self.check_access("write")
            slots._lock()
        result = super().write(vals)
        if slots:
            slots._check_definition()
        return result


class TutoringDelivery(models.Model):
    _inherit = "training.delivery"

    def write(self, vals):
        if set(vals) & {"timezone", "company_id", "program_id", "kind"}:
            slots = self.env["training.tutoring.slot"].sudo().search([("delivery_id", "in", self.ids)])
            if "timezone" in vals and any(s.timezone != vals["timezone"] for s in slots):
                raise ValidationError(self.env._("The reference timezone is preserved once tutoring slots exist."))
            for delivery in slots.delivery_id:
                if any(
                    k in vals and (delivery[k].id if delivery._fields[k].type == "many2one" else delivery[k]) != vals[k]
                    for k in ("company_id", "program_id", "kind")
                ):
                    raise ValidationError(self.env._("A delivery with sessions keeps its company, programme and kind."))
        return super().write(vals)
