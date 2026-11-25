"""Generic reminders in the native queue, with a durable occurrence journal."""

# pylint: disable=context-overridden  # replace caller defaults before whitelisted elevated mail

from odoo import api, fields, models


class PracticeNotice(models.Model):
    _name = "training.practice.notice"
    _inherit = "training.learning.notice"
    _description = "Practice Reminder Journal"
    _training_mail_template_xmlid = "training_management.mail_template_practice_notice"

    action_id = fields.Many2one("training.practice.action", required=True, ondelete="restrict")

    @api.private
    def _authorized(self):
        self.ensure_one()
        action = self.action_id
        user = action.enrollment_id.user_id
        today = fields.Date.context_today(action.with_context(tz=action.delivery_id.timezone))
        return bool(
            user
            and action.state == "planned"
            and action.reminder_days > 0
            and today >= action.due_date
            and user == self.recipient_id
            and user.partner_id.email == self.recipient_email
            and action.with_user(user)._eligible("participant")
        )

    @api.private
    def _queue_action(self, action, window):  # pylint: disable=context-overridden  # discard untrusted mail defaults
        # Caller holds delivery and action fences. No retrospective occurrence
        # replay: a delayed scheduler queues only the current reminder window.
        key = "practice:%s:%s" % (action.id, window)
        previous = self.sudo().search([("enrollment_id", "=", action.enrollment_id.id), ("event_key", "=", key)])
        if previous:
            if previous.mail_id.state == "exception" and previous._authorized():
                previous.mail_id.sudo().write({"state": "outgoing"})
            return previous
        user = action.enrollment_id.user_id
        row = self._create_evidence(
            {
                "action_id": action.id,
                "enrollment_id": action.enrollment_id.id,
                "event_key": key,
                "recipient_id": user.id,
                "recipient_email": user.partner_id.email,
                "recipient_language": user.partner_id.lang or "en_US",
            }
        )
        if not row.recipient_email or not row._authorized():
            row._store_evidence(
                {"not_queued_reason": self.env._("No currently authorized recipient with an email address.")}
            )
            return row
        mail = row._training_render_mail(
            row.recipient_email,
            action.company_id,
            email_from=action.company_id.partner_id.email_formatted or self.env.user.email_formatted,
        )
        row._store_evidence({"mail_id": mail.id})
        return row
