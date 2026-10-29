"""Optional company identity; never configure or activate a mail transport."""

from email.utils import formataddr

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize


class Company(models.Model):
    _inherit = "res.company"

    training_notification_address = fields.Char(groups="base.group_system")
    training_alert_address = fields.Char(string="Training Manager Alert Address", groups="base.group_system")
    training_notification_manager_id = fields.Many2one(
        "res.users", string="Training Alert Manager", groups="base.group_system", ondelete="restrict"
    )

    @api.constrains("training_notification_address", "training_alert_address", "training_notification_manager_id")
    def _check_training_notifications(self):
        for company in self:
            manager = company.training_notification_manager_id
            for address in (company.training_notification_address, company.training_alert_address):
                if address and email_normalize(address) != address:
                    raise ValidationError(self.env._("Enter one normalized notification email address."))
            if manager and (
                not manager.active
                or manager.share
                or company not in manager.company_ids
                or not manager.has_group("training_management.group_training_coordinator")
            ):
                raise ValidationError(self.env._("Choose an active internal training coordinator of this company."))


class Mail(models.Model):
    _inherit = "mail.mail"  # pylint: disable=consider-merging-classes-inherited

    @api.private
    def _training_identity(self, company):
        # Narrow read of administrator-only configuration, no recipient elevation.
        address = company.sudo().training_notification_address
        return {"email_from": formataddr((company.name, address)), "reply_to": address} if address else {}

    def write(self, vals):
        result = super().write(vals)
        if vals.get("state") == "exception":
            for mail in self.filtered(
                lambda item: (
                    item.model
                    in (
                        "training.notification",
                        "training.session",
                        "training.feedback.notice",
                        "training.request.notice",
                        "training.learning.notice",
                        "training.practice.notice",
                    )
                )
            ):
                model = "training.invitation" if mail.model == "training.session" else mail.model
                source = (
                    self.env[model].sudo().search([("mail_id", "=", mail.id)], limit=1) if model in self.env else False
                )
                if source and not (source._name == "training.learning.notice" and source.entry_id):
                    self.env["training.operator.notice"]._queue(source, "mail-failure")
        return result

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        if (
            self.model
            in (
                "training.notification",
                "training.learning.notice",
                "training.practice.notice",
                "training.feedback.notice",
                "training.session",
                "training.request.notice",
                "training.operator.notice",
            )
            and self.model in self.env
        ):
            record = self.env[self.model].sudo().browse(self.res_id).exists()
            if record:
                expected = self._training_identity(record.company_id)
                if any(self[key] != value for key, value in expected.items()):
                    raise ValidationError(
                        self.env._("Review this queued notification after the sender identity changed.")
                    )
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
