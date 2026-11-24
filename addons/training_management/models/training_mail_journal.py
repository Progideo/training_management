"""Server-authored training emails rendered from native, editable mail templates."""

import hashlib

from odoo import api, fields, models
from odoo.fields import Command
from odoo.tools.misc import clean_context


def mail_fingerprint(mail):
    """Digest of what was queued: transport refuses a mail altered after queueing."""
    return hashlib.sha256(("%s\n%s" % (mail.subject or "", mail.body_html or "")).encode()).hexdigest()


class TrainingMailDigest(models.Model):
    """Digest of a queued training email, kept apart so that journals stay unchanged."""

    _name = "training.mail.digest"
    _description = "Training Mail Digest"

    mail_id = fields.Many2one("mail.mail", required=True, ondelete="cascade", index=True)
    digest = fields.Char(required=True)
    _one_mail = models.Constraint("UNIQUE(mail_id)", "This email already has a digest.")


class TrainingMailJournal(models.AbstractModel):
    _name = "training.mail.journal"
    _description = "Training Mail Journal"

    # Native template used by the journal; overridable per variant.
    _training_mail_template_xmlid = None

    @api.private
    def _training_mail_template(self):
        self.ensure_one()
        return self.env.ref(self._training_mail_template_xmlid)

    @api.private
    def _training_render_mail(self, email_to, company, *, email_from=False, model=False, res_id=False):
        """Queue the journal's template for one recipient and return the queued mail.

        Only the template's subject and body are used: recipients, copies, followers,
        attachments and reports come from the journal, never from the template or the
        caller's context. Sender and reply-to follow the company's training identity.
        """
        self.ensure_one()
        # Replace the caller context: no default_* value reaches the elevated mail factory.
        template = self._training_mail_template().sudo().with_context(clean_context(self.env.context))  # pylint: disable=context-overridden
        values = {
            "email_to": email_to,
            "email_cc": False,
            "recipient_ids": [Command.clear()],
            "recipient_cc_ids": [Command.clear()],
            "attachment_ids": [Command.clear()],
            "auto_delete": False,
            "scheduled_date": False,
            "mail_server_id": False,
        }
        if email_from:
            values["email_from"] = email_from
        values.update(self.env["mail.mail"]._training_identity(company))
        if model:
            values.update(model=model, res_id=res_id)
        mail = self.env["mail.mail"].sudo().browse(template.send_mail(self.id, force_send=False, email_values=values))
        self.env["training.mail.digest"].sudo().create({"mail_id": mail.id, "digest": mail_fingerprint(mail)})
        return mail

    @api.private
    def _training_mail_matches(self, mail):
        """Queued content unchanged. Mails queued before the templates (no digest) keep the
        content written by the former code: only their recipient is checked again."""
        self.ensure_one()
        row = self.env["training.mail.digest"].sudo().search([("mail_id", "=", mail.id)], limit=1)
        return not row or row.digest == mail_fingerprint(mail)
