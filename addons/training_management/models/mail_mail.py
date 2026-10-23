from odoo import models


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        # Called inside native _send's error handling, immediately before build
        # and transport, including queue retries and synchronous sends.
        policy = self.env["training.document.policy"]
        # Native mail may carry a file belonging to a different document. Check
        # its source as well as the envelope before native sudo reads its bytes
        # or turns a large attachment into a download link.
        for source in [self.mail_message_id, *self.attachment_ids]:
            policy._check_send(
                policy._document(source),
                self.recipient_ids | self.recipient_cc_ids,
                email_to=self.email_to,
                email_cc=self.email_cc,
                required=False,
                allow_internal=True,
            )
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
