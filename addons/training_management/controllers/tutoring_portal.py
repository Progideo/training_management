"""Authenticated native QWeb forms; no portal ORM grants or shared attendees."""

from datetime import timedelta
from uuid import uuid4

from odoo import fields, http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools.misc import format_datetime

from .material_portal import TrainingParticipantPortal


class TutoringPortal(http.Controller):
    @http.route("/my/training-bookings", type="http", auth="user", website=True, methods=["GET"])
    def bookings(self, **kwargs):
        service = request.env["training.learning.service"]
        enrollments = request.env["training.document.policy"]._enrollments().filtered(service._is_participant)
        tutor_enrollments = service._tutored_enrollments()
        bookings = (
            request.env["training.tutoring.booking"]
            .sudo()
            .search(
                [
                    ("enrollment_id", "in", tutor_enrollments.ids),
                    ("slot_id.tutor_id", "=", request.env.uid),
                ],
                order="confirmed_at desc",
                limit=200,
            )
        )
        tz = request.env.user.tz or "UTC"
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.tutoring_home",
                {
                    "enrollments": [{"id": e.id, "name": e.delivery_id.name} for e in enrollments],
                    "appointments": [
                        {
                            "participant": b.enrollment_id.participant_id.name,
                            "name": b.slot_id.name,
                            "start": format_datetime(request.env, b.slot_id.start_at, tz=tz),
                            "state": b.state,
                            "meeting_url": b.slot_id.meeting_url if b.state == "confirmed" else False,
                        }
                        for b in bookings
                    ],
                    "timezone": tz,
                },
            )
        )

    @http.route("/my/trainings/<int:enrollment_id>/tutoring", type="http", auth="user", website=True, methods=["GET"])
    def slots(self, enrollment_id, error=False, **kwargs):
        try:
            enrollment = request.env["training.learning.service"]._enrollment(enrollment_id)
        except (AccessError, MissingError):
            raise request.not_found() from None
        entitlement = (
            request.env["training.tutoring.entitlement"].sudo().search([("enrollment_id", "=", enrollment.id)], limit=1)
        )
        booking_model = request.env["training.tutoring.booking"].sudo()
        bookings = booking_model.search([("enrollment_id", "=", enrollment.id)], order="confirmed_at desc")
        used = len(bookings.filtered(lambda b: not b.refunded))
        now = fields.Datetime.now()
        tz = request.env.user.tz or enrollment.delivery_id.timezone
        slots = (
            request.env["training.tutoring.slot"]
            .sudo()
            .search(
                [
                    ("delivery_id", "=", enrollment.delivery_id.id),
                    ("state", "=", "published"),
                    ("tutor_id.active", "=", True),
                    ("tutor_id.company_ids", "in", enrollment.company_id.ids),
                    ("tutor_id", "=", (enrollment.learning_tutor_id or enrollment.delivery_id.learning_tutor_id).id),
                    ("start_at", ">", now),
                ],
                limit=200,
            )
        )
        rows = []
        occupied = {
            s.id: count
            for s, count in booking_model._read_group(
                [("slot_id", "in", slots.ids), ("state", "=", "confirmed")], ["slot_id"], ["__count"]
            )
        }
        for slot in slots:
            if (
                not enrollment.access_start
                or not enrollment.access_end
                or slot.start_at < enrollment.access_start
                or slot.end_at > enrollment.access_end
            ):
                continue
            current = bookings.filtered(lambda b: b.slot_id == slot and b.state == "confirmed")
            full = occupied.get(slot.id, 0) >= slot.capacity
            rows.append(
                {
                    "id": slot.id,
                    "name": slot.name,
                    "start": format_datetime(request.env, slot.start_at, tz=tz),
                    "end": format_datetime(request.env, slot.end_at, tz=tz),
                    "duration": slot.duration_hours,
                    "capacity": slot.capacity,
                    "kind": slot.kind,
                    "terms": slot.cancellation_terms,
                    "refund": slot.refund_policy == "before",
                    "deadline": format_datetime(
                        request.env, slot.start_at - timedelta(hours=slot.cancellation_hours), tz=tz
                    )
                    if slot.refund_policy == "before"
                    else False,
                    "can_book": bool(entitlement and used < entitlement.included_count and not full and not current),
                    "full": full,
                    "booked": bool(current),
                    "key": str(uuid4()),
                }
            )
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.tutoring_slots",
                {
                    "enrollment_id": enrollment.id,
                    "name": enrollment.delivery_id.name,
                    "timezone": tz,
                    "included": entitlement.included_count if entitlement else 0,
                    "used": used,
                    "rows": rows,
                    "bookings": [
                        {
                            "id": b.id,
                            "name": b.slot_id.name,
                            "start": format_datetime(request.env, b.slot_id.start_at, tz=tz),
                            "state": b.state,
                            "terms": b.cancellation_terms,
                            "refunded": b.refunded,
                            "can_cancel": b.state == "confirmed" and b.slot_id.start_at > now,
                            "location": b.slot_id.location or b.slot_id.room_id.name
                            if b.state == "confirmed"
                            else False,
                            "meeting_url": b.slot_id.meeting_url if b.state == "confirmed" else False,
                            "refund": b.refund_policy == "before",
                            "deadline": format_datetime(request.env, b.refund_deadline, tz=tz)
                            if b.refund_deadline
                            else False,
                        }
                        for b in bookings
                    ],
                    "error": error,
                },
            )
        )

    @http.route("/my/trainings/<int:enrollment_id>/tutoring", type="http", auth="user", website=True, methods=["POST"])
    def operate(self, enrollment_id, **values):
        try:
            with request.env.cr.savepoint():
                service = request.env["training.tutoring.service"]
                if values.get("action") == "cancel":
                    service._cancel(enrollment_id, int(values.get("booking_id", 0)))
                elif values.get("action") == "reserve":
                    service._reserve(enrollment_id, int(values.get("slot_id", 0)), values.get("request_key"))
                else:
                    raise request.not_found()
        except (AccessError, MissingError):
            raise request.not_found() from None
        except (ValidationError, ValueError) as exc:
            response = self.slots(
                enrollment_id,
                error=str(exc) if isinstance(exc, ValidationError) else request.env._("Invalid reservation request."),
            )
            response.status_code = 400
            return response
        return request.redirect("/my/trainings/%s/tutoring" % enrollment_id, code=303)
