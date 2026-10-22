from odoo import models
from odoo.exceptions import ValidationError


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    def _get_default_mail_partner_ids(self, move, mail_template, mail_lang):
        if move.training_is_sale_invoice:
            return move.training_portal_partner_ids.filtered("email")
        return super()._get_default_mail_partner_ids(move, mail_template, mail_lang)

    def _get_mail_params(self, move, move_data):
        if move.training_is_sale_invoice:
            allowed = move.training_portal_partner_ids.filtered("email")
            recipients = self.env["res.partner"].browse(move_data.get("mail_partner_ids", []))
            if not recipients or recipients - allowed:
                raise ValidationError(
                    self.env._("Send training invoice PDFs only to named contacts authorized on this invoice.")
                )
        return super()._get_mail_params(move, move_data)

    def _send_mail(self, move, mail_template, **kwargs):
        if move.training_is_sale_invoice:
            kwargs["notify_skip_followers"] = True
        return super()._send_mail(move, mail_template, **kwargs)
