"""Generic acknowledgement of a training CRM request, through native mail.mail."""

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingRequestNotice(models.Model):
    _name = "training.request.notice"
    _inherit = "training.learning.evidence"
    _description = "Training Request Acknowledgement Journal"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True)
    email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict")
    distribution_state = fields.Selection(related="mail_id.state")
    failure = fields.Char()
    template_version = fields.Char(default="S10-REQUEST-1", required=True)
    _one_request = models.Constraint("UNIQUE(lead_id)", "This request has already been acknowledged.")

    @api.private
    def _authorized(self):
        self.ensure_one()
        return bool(
            self.lead_id.exists()
            and self.lead_id.active
            and self.lead_id.training_request_kind
            and self.lead_id.email_normalized
            and self.lead_id.email_normalized == self.email
            and (not self.lead_id.company_id or self.lead_id.company_id == self.company_id)
        )

    @api.private
    def _content(self):
        env = self.with_context(lang=self.recipient_language).env
        return env._("Your training request has been received"), Markup("<p>%s</p>") % env._(
            "Your training request has been recorded. The team will contact you. This acknowledgement does not confirm an enrollment."
        )

    @api.private
    def _queue(self, lead):
        lead.check_access("read")
        lead.lock_for_update()
        existing = self.sudo().search([("lead_id", "=", lead.id)], limit=1)
        if existing:
            if existing.mail_id.state == "exception" and existing._authorized():
                existing.mail_id.sudo().write({"state": "outgoing"})
            return existing
        notice = self._create_evidence(
            {
                "lead_id": lead.id,
                "company_id": (lead.company_id or self.env.company).id,
                "email": lead.email_normalized,
                "recipient_language": lead.partner_id.lang or self.env.lang or "en_US",
            }
        )
        if not notice._authorized():
            notice._store_evidence({"failure": self.env._("No current request recipient with a valid email address.")})
            return notice
        subject, body = notice._content()
        clean = {key: value for key, value in self.env.context.items() if not key.startswith("default_")}
        mail = (
            self.env["mail.mail"]  # pylint: disable=context-overridden  # replace caller context before elevated mail
            .sudo()
            .with_context(clean)  # pylint: disable=context-overridden  # discard caller defaults before elevated mail
            .create(
                {  # pylint: disable=context-overridden
                    "subject": subject,
                    "body_html": body,
                    "email_to": notice.email,
                    "email_cc": False,
                    "recipient_ids": [],
                    "recipient_cc_ids": [],
                    "attachment_ids": [],
                    "auto_delete": False,
                    "email_from": notice.company_id.partner_id.email_formatted or self.env.user.email_formatted,
                    "model": self._name,
                    "res_id": notice.id,
                }
            )
        )
        notice._store_evidence({"mail_id": mail.id})
        return notice


class RequestLead(models.Model):
    _inherit = "crm.lead"  # pylint: disable=consider-merging-classes-inherited  # Request acknowledgements have a separate lifecycle.

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        for lead in leads.filtered("training_request_kind"):
            self.env["training.request.notice"]._queue(lead)
        return leads


class RequestMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        if self.model == "training.request.notice":
            notice = self.env["training.request.notice"].sudo().search([("mail_id", "=", self.id)], limit=1)
            if not notice or not notice._authorized():
                raise ValidationError(self.env._("This request acknowledgement is no longer authorized."))
            subject, body = notice._content()
            if (
                self.subject != subject
                or self.body_html != body
                or self.email_to != notice.email
                or self.email_cc
                or self.recipient_ids
                or self.recipient_cc_ids
                or self.attachment_ids
            ):
                raise ValidationError(self.env._("Request acknowledgements contain only their generic confirmation."))
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
