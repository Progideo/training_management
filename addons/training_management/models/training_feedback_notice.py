"""Idempotent feedback mail, with eligibility checked at transport."""

from odoo import api, fields, models

from .training_mail_journal import mail_fingerprint


class FeedbackNotice(models.Model):
    _name = "training.feedback.notice"
    _inherit = ["training.learning.evidence", "training.mail.journal"]
    _description = "Feedback Invitation Journal"
    _training_mail_template_xmlid = "training_management.mail_template_feedback_notice"

    recipient_id = fields.Many2one("training.feedback.recipient", required=True, ondelete="restrict")
    campaign_id = fields.Many2one(related="recipient_id.campaign_id", store=True)
    company_id = fields.Many2one(related="recipient_id.company_id", store=True)
    occurrence = fields.Char(required=True)
    email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="set null")
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
            and (
                self.occurrence == "invitation"
                or campaign.anonymous
                or self.recipient_id._nominative_state() != "received"
            )
        )

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
        mail = journal._training_render_mail(
            journal.email,
            recipient.company_id,
            email_from=recipient.company_id.partner_id.email_formatted or self.env.user.email_formatted,
        )
        journal._store_evidence({"mail_id": mail.id, "mail_fingerprint": mail_fingerprint(mail)})
        return journal
