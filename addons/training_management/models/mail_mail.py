from odoo import models
from odoo.exceptions import ValidationError


class MailMail(models.Model):
    # Keep per-workflow transport policies in their own inherited classes.
    _inherit = "mail.mail"  # pylint: disable=consider-merging-classes-inherited

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        if self.model in ("training.learning.notice", "training.practice.notice", "training.tutoring.notice"):
            notice = self.env[self.model].sudo().search([("mail_id", "=", self.id)], limit=1)
            if not notice or not notice._authorized():
                raise ValidationError(self.env._("This learning notification no longer has an authorized recipient."))
            subject, body = notice._content()
            if (
                self.email_to != notice.recipient_email
                or self.email_cc
                or self.recipient_ids
                or self.recipient_cc_ids
                or self.attachment_ids
                or self.subject != subject
                or self.body_html != body
            ):
                raise ValidationError(self.env._("Learning notifications contain only the authorized sign-in link."))
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
        if self.model == "training.notification":
            notice = self.env["training.notification"].sudo().search([("mail_id", "=", self.id)], limit=1)
            if not notice or not notice._authorized():
                raise ValidationError(self.env._("This lifecycle notification is no longer authorized."))
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
                raise ValidationError(self.env._("Lifecycle notifications contain only the authorized sign-in link."))
        if self.model == "training.operator.notice":
            notice = self.env["training.operator.notice"].sudo().search([("mail_id", "=", self.id)], limit=1)
            if not notice or not notice._authorized():
                raise ValidationError(self.env._("This staff alert no longer has an authorized recipient."))
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
                raise ValidationError(self.env._("Staff alerts contain only the authorized sign-in link."))
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
