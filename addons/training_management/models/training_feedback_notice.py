"""Idempotent feedback mail, with eligibility checked at transport."""

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FeedbackNotice(models.Model):
    _name = "training.feedback.notice"
    _inherit = "training.learning.evidence"
    _description = "Feedback Invitation Journal"

    recipient_id = fields.Many2one("training.feedback.recipient", required=True, ondelete="restrict")
    campaign_id = fields.Many2one(related="recipient_id.campaign_id", store=True)
    company_id = fields.Many2one(related="recipient_id.company_id", store=True)
    occurrence = fields.Char(required=True)
    email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict")
    distribution_state = fields.Selection(related="mail_id.state")
    failure = fields.Char()
    _one_notice = models.Constraint("UNIQUE(recipient_id, occurrence)", "This invitation is already journaled.")

    @api.private
    def _authorized(self):
        self.ensure_one()
        campaign = self.campaign_id
        now = fields.Datetime.now()
        return (
            self.recipient_id._eligible()
            and self.recipient_id.user_id.partner_id.email == self.email
            and campaign.state == "open"
            and campaign.opens_at <= now <= campaign.due_at
        )

    @api.private
    def _content(self):
        self.ensure_one()
        env = self.with_context(lang=self.recipient_language).env
        body = Markup('<p>%s</p><p><a href="%s/my/training-feedback">%s</a></p>') % (
            env._("Sign in to your training feedback space. If you have already replied, please ignore this reminder."),
            self.campaign_id.get_base_url(),
            env._("Open feedback space"),
        )
        return env._("Your training feedback"), body

    @api.private
    def _queue(self, recipient, occurrence):
        journal = self.sudo().search([("recipient_id", "=", recipient.id), ("occurrence", "=", occurrence)], limit=1)
        if journal:
            if journal.mail_id.state == "exception" and journal._authorized():
                journal.mail_id.sudo().write({"state": "outgoing"})
            return journal
        journal = self._create_evidence(
            {
                "recipient_id": recipient.id,
                "occurrence": occurrence,
                "email": recipient.user_id.partner_id.email,
                "recipient_language": recipient.user_id.lang or "en_US",
            }
        )
        if not journal.email or not journal._authorized():
            journal._store_evidence({"failure": self.env._("No authorized recipient with an email address.")})
            return journal
        subject, body = journal._content()
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        # pylint: disable=context-overridden  # discard caller defaults before the mail factory
        mail = (
            self.env["mail.mail"]
            .sudo()
            .with_context(clean)  # pylint: disable=context-overridden  # discard caller defaults
            .create(
                {  # pylint: disable=context-overridden
                    "subject": subject,
                    "body_html": body,
                    "email_to": journal.email,
                    "email_from": recipient.company_id.partner_id.email_formatted or self.env.user.email_formatted,
                    "email_cc": False,
                    "recipient_ids": [],
                    "recipient_cc_ids": [],
                    "attachment_ids": [],
                    "model": self._name,
                    "res_id": journal.id,
                    "auto_delete": False,
                }
            )
        )
        journal._store_evidence({"mail_id": mail.id})
        return journal


class FeedbackMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        if self.model == "training.feedback.notice":
            notice = self.env["training.feedback.notice"].sudo().search([("mail_id", "=", self.id)], limit=1)
            if not notice or not notice._authorized():
                raise ValidationError(self.env._("This feedback invitation is no longer authorized."))
            subject, body = notice._content()
            if (
                self.email_to != notice.email
                or self.email_cc
                or self.recipient_ids
                or self.recipient_cc_ids
                or self.attachment_ids
                or self.subject != subject
                or self.body_html != body
            ):
                raise ValidationError(self.env._("Feedback notifications contain only the sign-in link."))
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
