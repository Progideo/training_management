"""Server-authored training emails rendered from native, editable mail templates."""

import hashlib

from odoo import api, fields, models
from odoo.fields import Command
from odoo.tools.misc import clean_context


def mail_fingerprint(mail):
    """Digest of what was queued: transport refuses a mail altered after queueing."""
    return hashlib.sha256(("%s\n%s" % (mail.subject or "", mail.body_html or "")).encode()).hexdigest()


class TrainingMailJournal(models.AbstractModel):
    _name = "training.mail.journal"
    _description = "Training Mail Journal"

    # Native template used by the journal; overridable per variant.
    _training_mail_template_xmlid = None

    mail_fingerprint = fields.Char(readonly=True, copy=False)

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
        mail_id = template.send_mail(self.id, force_send=False, email_values=values)
        return self.env["mail.mail"].sudo().browse(mail_id)

    @api.private
    def _training_mail_matches(self, mail):
        self.ensure_one()
        return bool(self.mail_fingerprint) and self.mail_fingerprint == mail_fingerprint(mail)
