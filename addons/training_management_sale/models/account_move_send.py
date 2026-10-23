"""The native invoice pipeline has its own defaults, parameters and followers; all must use the document grant."""

from odoo import models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    def _get_default_mail_partner_ids(self, move, mail_template, mail_lang):
        if move.training_is_sale_invoice:
            return self.env["training.document.policy"]._partners(move, email_only=True)
        return super()._get_default_mail_partner_ids(move, mail_template, mail_lang)

    def _get_mail_params(self, move, move_data):
        if move.training_is_sale_invoice:
            self.env["training.document.policy"]._check_send(
                move, self.env["res.partner"].browse(move_data.get("mail_partner_ids", []))
            )
        return super()._get_mail_params(move, move_data)

    def _send_mail(self, move, mail_template, **kwargs):
        if move.training_is_sale_invoice:
            kwargs["notify_skip_followers"] = True
        return super()._send_mail(move, mail_template, **kwargs)
