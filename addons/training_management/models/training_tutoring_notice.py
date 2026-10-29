"""Private P13 notices reuse the native queue and its transport-time checks."""

from markupsafe import Markup

from odoo import api, fields, models


class TutoringNotice(models.Model):
    _name = "training.tutoring.notice"
    _inherit = "training.learning.notice"
    _description = "Tutoring Reservation Notification Journal"

    booking_id = fields.Many2one("training.tutoring.booking", required=True, ondelete="restrict")
    notice_state = fields.Selection([("confirmed", "Confirmed"), ("cancelled", "Cancelled")], required=True)
    event_kind = fields.Selection(selection_add=[("booking", "Tutoring Reservation")])

    @api.depends("booking_id")
    def _compute_event_kind(self):
        for notice in self:
            notice.event_kind = "booking"

    @api.private
    def _authorized(self):
        self.ensure_one()
        booking = self.booking_id
        enrollment = booking.enrollment_id
        recipient = self.recipient_id
        if (
            not recipient
            or not recipient.active
            or recipient.partner_id.email != self.recipient_email
            or booking.state != self.notice_state
        ):
            return False
        service = self.env["training.learning.service"].with_user(recipient)
        if recipient == enrollment.user_id:
            return service._is_participant(enrollment)
        return recipient == booking.slot_id.tutor_id and service._is_tutor(enrollment)

    @api.private
    def _content(self):
        self.ensure_one()
        env = self.with_context(lang=self.recipient_language).env
        return env._("Your tutoring reservation has changed"), Markup('<p>%s</p><p><a href="%s">%s</a></p>') % (
            env._("Sign in to view the current reservation information."),
            self.enrollment_id.get_base_url() + "/my/training-bookings",
            env._("Open tutoring reservations"),
        )

    @api.private
    def _queue_booking(self, booking):
        enrollment = booking.enrollment_id
        for user in enrollment.user_id | booking.slot_id.tutor_id:
            self._queue(
                enrollment,
                "tutoring:%s:%s:%s" % (booking.id, booking.state, user.id),
                user,
                extra_values={"booking_id": booking.id, "notice_state": booking.state},
            )
