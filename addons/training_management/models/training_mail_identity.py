"""Optional company identity; never configure or activate a mail transport."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize


class Company(models.Model):
    _inherit = "res.company"

    training_notification_address = fields.Char(
        string="Legacy Notification Address",
        groups="base.group_system",
        readonly=True,
        help="Preserved migration history; new notifications use the native email template.",
    )
    training_notification_template_id = fields.Many2one(
        "mail.template",
        string="Notification Identity Template",
        groups="base.group_system",
        domain="[('model', '=', 'res.company')]",
        ondelete="restrict",
        help="Only sender and reply-to are rendered. Recipients, content and attachments remain controlled by the notification.",
    )
    training_alert_address = fields.Char(string="Training Manager Alert Address", groups="base.group_system")
    training_notification_manager_id = fields.Many2one(
        "res.users", string="Training Alert Manager", groups="base.group_system", ondelete="restrict"
    )

    @api.constrains("training_notification_template_id", "training_alert_address", "training_notification_manager_id")
    def _check_training_notifications(self):
        for company in self:
            manager = company.training_notification_manager_id
            template = company.training_notification_template_id
            if template and template.model != "res.company":
                raise ValidationError(self.env._("Choose an email template for companies."))
            for address in (company.training_alert_address,):
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
        # Only the administrator-selected template and two identity fields are read
        # with elevation. Never render recipients, body, reports or attachments here.
        company = company.sudo()
        template = company.training_notification_template_id
        if template:
            if template.model != "res.company":
                raise ValidationError(self.env._("Choose an email template for companies."))
            values = template.with_company(company)._generate_template(company.ids, ("email_from", "reply_to"))[
                company.id
            ]
            return {key: value for key, value in values.items() if key in ("email_from", "reply_to") and value}
        return {
            key: value
            for key, value in {
                "email_from": company.default_from_email or company.partner_id.email_formatted,
                "reply_to": company.catchall_email,
            }.items()
            if value
        }

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
                        "training.tutoring.notice",
                        "training.publication.notice",
                        "training.session.alert.notice",
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
