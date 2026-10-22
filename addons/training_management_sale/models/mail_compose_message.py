from odoo import models
from odoo.exceptions import ValidationError


class MailComposeMessage(models.TransientModel):
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
                    composer.partner_ids = order.training_portal_partner_ids.filtered("email")
                    composer.partner_cc_ids = False
            elif len(res_ids) == 1 and composer.model == "account.payment":
                payment = self.env["account.payment"].browse(res_ids[0])
                if payment._training_receipt_is_restricted():
                    composer.partner_ids = payment._training_receipt_allowed_partners()
                    composer.partner_cc_ids = False

    def _prepare_mail_values(self, res_ids):
        values = super()._prepare_mail_values(res_ids)
        if self.model not in ("sale.order", "account.move", "account.payment"):
            return values
        documents = self.env[self.model].browse(res_ids)
        if self.model == "sale.order":
            documents = documents.filtered("training_request_kind")
        elif self.model == "account.move":
            documents = documents.filtered("training_is_sale_invoice")
        else:
            documents = documents.filtered(lambda payment: payment._training_receipt_is_restricted())
        for document in documents:
            mail_values = values.get(document.id, {})
            allowed = (
                document._training_receipt_allowed_partners()
                if self.model == "account.payment"
                else document.training_portal_partner_ids.filtered("email")
            )
            selected = self.env["res.partner"].browse(
                mail_values.get("partner_ids", []) + mail_values.get("partner_cc_ids", [])
            )
            preparing_document = bool(self.template_id or mail_values.get("attachment_ids"))
            if (
                (preparing_document and not selected)
                or selected - allowed
                or mail_values.get("email_to")
                or mail_values.get("email_cc")
            ):
                raise ValidationError(
                    self.env._("Send training document PDFs only to named contacts authorized on this document.")
                )
            mail_values["notify_skip_followers"] = True
        return values

    def _action_schedule_message(self):
        for composer in self.filtered(lambda wizard: wizard.model in ("sale.order", "account.move", "account.payment")):
            composer._prepare_mail_values(composer._evaluate_res_ids())
        return super()._action_schedule_message()
