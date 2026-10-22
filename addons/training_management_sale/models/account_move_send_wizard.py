from odoo import models


class AccountMoveSendWizard(models.TransientModel):
    _inherit = "account.move.send.wizard"

    def _compute_mail_partners(self):  # pylint: disable=missing-return  # compute method, nothing to return
        super()._compute_mail_partners()
        for wizard in self.filtered(lambda item: item.move_id.training_is_sale_invoice):
            wizard.mail_partner_ids = wizard.move_id.training_portal_partner_ids.filtered("email")
