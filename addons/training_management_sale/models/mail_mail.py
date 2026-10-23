from odoo import models


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        # Called inside native _send's error handling, immediately before build
        # and transport, including queue retries and synchronous sends.
        policy = self.env["training.document.policy"]
        document = policy._document(self.mail_message_id)
        policy._check_send(
            document,
            self.recipient_ids | self.recipient_cc_ids,
            email_to=self.email_to,
            email_cc=self.email_cc,
            required=False,
            allow_internal=True,
        )
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
