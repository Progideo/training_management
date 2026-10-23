"""Native invoices without a template fall back to the commercial partner; keep named grants in that path too."""

from odoo import models


class AccountMoveSendWizard(models.TransientModel):  # pylint: disable=no-wizard-in-models  # extends a native wizard; moving the file is out of scope
    _inherit = "account.move.send.wizard"

    def _compute_mail_partners(self):  # pylint: disable=missing-return  # compute method, nothing to return
        super()._compute_mail_partners()
        # Native code falls back to the commercial partner when no template is selected.
        for wizard in self.filtered(lambda item: item.move_id.training_is_sale_invoice):
            wizard.mail_partner_ids = self.env["training.document.policy"]._partners(wizard.move_id, email_only=True)
