"""Keep native composition and scheduling; only named defaults and final values need the additional document grant."""

from odoo import models


class MailComposeMessage(models.TransientModel):  # pylint: disable=no-wizard-in-models  # extends a native wizard; moving the file is out of scope
    _inherit = "mail.compose.message"

    def _compute_recipient_partners(self):  # pylint: disable=missing-return  # compute method, nothing to return
        super()._compute_recipient_partners()
        for composer in self.filtered(
            lambda wizard: wizard.model in ("sale.order", "account.payment") and not wizard.composition_batch
        ):
            res_ids = composer._evaluate_res_ids()
            if len(res_ids) == 1 and composer.model == "sale.order":
                order = self.env["sale.order"].browse(res_ids[0])
                if order.training_request_kind:
                    composer.partner_ids = self.env["training.document.policy"]._partners(order, email_only=True)
                    composer.partner_cc_ids = False
            elif len(res_ids) == 1 and composer.model == "account.payment":
                payment = self.env["account.payment"].browse(res_ids[0])
                if payment._training_receipt_is_restricted():
                    composer.partner_ids = self.env["training.document.policy"]._partners(payment, email_only=True)
                    composer.partner_cc_ids = False

    def _prepare_mail_values(self, res_ids):
        values = super()._prepare_mail_values(res_ids)
        if self.model not in ("sale.order", "account.move", "account.payment"):
            return values
        policy = self.env["training.document.policy"]
        for document in self.env[self.model].browse(res_ids):
            if not policy._restricted(document):
                continue
            mail_values = values.get(document.id, {})
            selected = self.env["res.partner"].browse(
                mail_values.get("partner_ids", []) + mail_values.get("partner_cc_ids", [])
            )
            policy._check_send(
                document,
                selected,
                email_to=mail_values.get("email_to"),
                email_cc=mail_values.get("email_cc"),
                required=bool(self.template_id or mail_values.get("attachment_ids")),
            )
            mail_values["notify_skip_followers"] = True
        return values
