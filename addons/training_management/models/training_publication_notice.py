"""One private sign-in notice per request, checked again at native transport."""

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError


class PublicationNotice(models.Model):
    _name = "training.publication.notice"
    _inherit = "training.learning.evidence"
    _description = "Publication Invitation Journal"

    publication_id = fields.Many2one("training.publication", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="publication_id.company_id", store=True)
    recipient_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    recipient_email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict")
    not_queued_reason = fields.Char()
    _once = models.Constraint("UNIQUE(publication_id)", "This publication invitation is already journaled.")

    @api.private
    def _authorized(self):
        self.ensure_one()
        row = self.publication_id
        if (
            row.state != ("invited" if row.kind == "review" else "submitted")
            or self.recipient_id != row.owner_id
            or self.recipient_email != row.owner_id.partner_id.email
        ):
            return False
        try:
            row.with_user(self.recipient_id).sudo()._owner(grant=True)
        except AccessError:
            return False
        return row._valid_participation() if row.kind == "review" else not row.confidential

    @api.private
    def _content(self):
        env = self.with_context(lang=self.recipient_language).env
        return env._("A publication authorization awaits your decision"), Markup(
            '<p>%s</p><p><a href="%s">%s</a></p>'
        ) % (
            env._(
                "Sign in to review the proposed publication. Giving an opinion or authorizing publication is optional."
            ),
            self.publication_id.get_base_url() + "/my/training-publications",
            env._("Review publication requests"),
        )

    @api.private
    def _queue_publication(self, publication):  # pylint: disable=context-overridden  # discard untrusted mail defaults
        previous = self.sudo().search([("publication_id", "=", publication.id)])
        if previous:
            return previous
        user = publication.owner_id
        row = self._create_evidence(
            {
                "publication_id": publication.id,
                "recipient_id": user.id,
                "recipient_email": user.partner_id.email,
                "recipient_language": user.partner_id.lang or "en_US",
            }
        )
        if not row.recipient_email or not row._authorized():
            row._store_evidence(
                {"not_queued_reason": self.env._("No currently authorized recipient with an email address.")}
            )
            return row
        subject, body = row._content()
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        mail_model = self.env["mail.mail"].sudo().with_context(clean)  # pylint: disable=context-overridden  # remove untrusted mail defaults
        mail = mail_model.create(
            {  # pylint: disable=context-overridden
                "subject": subject,
                "body_html": body,
                "email_to": row.recipient_email,
                "email_from": publication.company_id.partner_id.email_formatted or self.env.user.email_formatted,
                **self.env["mail.mail"]._training_identity(publication.company_id),
                "email_cc": False,
                "recipient_ids": [],
                "recipient_cc_ids": [],
                "attachment_ids": [],
                "model": self._name,
                "res_id": row.id,
                "auto_delete": False,
            }
        )
        row._store_evidence({"mail_id": mail.id})
        return row
