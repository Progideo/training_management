"""Generic acknowledgement of a training CRM request, through native mail.mail."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingRequestNotice(models.Model):
    _name = "training.request.notice"
    _inherit = ["training.learning.evidence", "training.mail.journal"]
    _description = "Training Request Acknowledgement Journal"
    _training_mail_template_xmlid = "training_management_sale.mail_template_request_notice"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True)
    email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="set null")
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
        mail = notice._training_render_mail(
            notice.email,
            notice.company_id,
            email_from=notice.company_id.partner_id.email_formatted or self.env.user.email_formatted,
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
            self.env["training.operator.notice"]._queue(lead, "request")
        return leads


class RequestMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        if self.model == "training.request.notice":
            notice = self.env["training.request.notice"].sudo().search([("mail_id", "=", self.id)], limit=1)
            if not notice or not notice._authorized():
                raise ValidationError(self.env._("This request acknowledgement is no longer authorized."))
            if (
                not notice._training_mail_matches(self)
                or self.email_to != notice.email
                or self.email_cc
                or self.recipient_ids
                or self.recipient_cc_ids
                or self.attachment_ids
            ):
                raise ValidationError(self.env._("Request acknowledgements contain only their generic confirmation."))
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)


class RequestOperatorNotice(models.Model):
    _inherit = "training.operator.notice"

    @api.model
    def _source_models(self):
        return (*super()._source_models(), "crm.lead", "training.request.notice")

    @api.private
    def _authorized(self):
        source = self._source()
        if source and source._name == "crm.lead" and (not source.active or not source.training_request_kind):
            return False
        if (
            source
            and source._name == "training.request.notice"
            and (source.mail_id.state != "exception" or not source._authorized())
        ):
            return False
        return super()._authorized()
