"""The TM adapter owns notifications for its own active enrollments."""

from markupsafe import Markup
from odoo import api, fields, models


class Version(models.Model):
    _inherit = "training.elearning.version"

    @api.private
    def _withdraw_consumers(self, reason):
        result = super()._withdraw_consumers(reason)
        for version in self:
            # The checked library lifecycle serializes this single withdrawal.
            # No learner evidence or definition is modified by the adapter.
            usages = self.env["training.elearning.usage"].sudo().search([("version_id", "=", version.id)])
            enrollments = (
                self.env["training.enrollment"]
                .sudo()
                .search([("delivery_id", "in", usages.delivery_id.ids), ("company_id", "=", version.company_id.id)])
            )
            affected = enrollments.filtered(
                lambda enrollment: (
                    self.env["training.learning.service"].with_user(enrollment.user_id)._is_participant(enrollment)
                    if enrollment.user_id
                    else False
                )
            )
            for enrollment in affected:
                self.env["training.learning.notice"]._queue(
                    enrollment,
                    "resource_withdrawal:%s" % version.id,
                    enrollment.user_id,
                    extra_values={"interactive_version_id": version.id},
                )
            for delivery in affected.delivery_id:
                if delivery.responsible_id.active:
                    delivery.activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=delivery.responsible_id.id,
                        summary=self.env._("Review withdrawn resource and affected training dates"),
                    )
        return result


class Notice(models.Model):
    _inherit = "training.learning.notice"
    event_kind = fields.Selection(selection_add=[("resource_withdrawal", "Resource Withdrawal")])
    interactive_version_id = fields.Many2one("training.elearning.version", readonly=True, ondelete="restrict")

    @api.depends("entry_id", "interactive_version_id")
    def _compute_event_kind(self):
        result = super()._compute_event_kind()
        for notice in self.filtered("interactive_version_id"):
            notice.event_kind = "resource_withdrawal"
        return result

    @api.private
    def _authorized(self):
        self.ensure_one()
        if not self.interactive_version_id:
            return super()._authorized()
        enrollment = self.enrollment_id
        recipient = enrollment.user_id
        version = self.interactive_version_id
        return bool(
            recipient
            and recipient == self.recipient_id
            and recipient.active
            and recipient.partner_id.email == self.recipient_email
            and version.state == "withdrawn"
            and version.company_id == enrollment.company_id
            and self.event_key == "resource_withdrawal:%s" % version.id
            and self.env["training.learning.service"].with_user(recipient)._is_participant(enrollment)
            and self.env["training.elearning.usage"]
            .sudo()
            .search_count([("delivery_id", "=", enrollment.delivery_id.id), ("version_id", "=", version.id)], limit=1)
        )

    @api.private
    def _content(self):
        subject, body = super()._content()
        if self.interactive_version_id:
            language = self.with_context(lang=self.recipient_language).env
            body = (
                Markup("<p>%s</p>")
                % language._("A learning resource is unavailable. Contact your training coordination.")
                + body
            )
        return subject, body
