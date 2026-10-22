from odoo import models, _
from odoo.exceptions import ValidationError


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        # Called inside native _send's error handling, immediately before build
        # and transport, including queue retries and synchronous sends.
        document = (
            self.env[self.model].sudo().browse(self.res_id).exists()
            if (self.model in ("sale.order", "account.move", "account.payment") and self.res_id)
            else False
        )
        if document:
            restricted = (
                document.training_request_kind
                if self.model == "sale.order"
                else document.training_is_sale_invoice
                if self.model == "account.move"
                else document._training_receipt_is_restricted()
            )
            if restricted:
                allowed = (
                    document._training_receipt_allowed_partners()
                    if self.model == "account.payment"
                    else document.training_portal_partner_ids.filtered("email")
                )
                recipients = self.recipient_ids | self.recipient_cc_ids
                external = recipients.filtered(
                    lambda partner: not partner.user_ids or all(user.share for user in partner.user_ids)
                )
                if self.email_to or self.email_cc or external - allowed:
                    raise ValidationError(_("A training mail recipient is no longer authorized on the document."))
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
