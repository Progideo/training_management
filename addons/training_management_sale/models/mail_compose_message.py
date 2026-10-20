from odoo import _, models
from odoo.exceptions import ValidationError


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _compute_recipient_partners(self):
        super()._compute_recipient_partners()
        for composer in self.filtered(
            lambda wizard: wizard.model == "sale.order" and not wizard.composition_batch
        ):
            res_ids = composer._evaluate_res_ids()
            if len(res_ids) == 1:
                order = self.env["sale.order"].browse(res_ids[0])
                if order.training_request_kind:
                    composer.partner_ids = order.training_portal_partner_ids.filtered("email")
                    composer.partner_cc_ids = False

    def _prepare_mail_values(self, res_ids):
        values = super()._prepare_mail_values(res_ids)
        if self.model != "sale.order":
            return values
        for order in self.env["sale.order"].browse(res_ids).filtered("training_request_kind"):
            mail_values = values.get(order.id, {})
            allowed = order.training_portal_partner_ids.filtered("email")
            selected = self.env["res.partner"].browse(
                mail_values.get("partner_ids", []) + mail_values.get("partner_cc_ids", [])
            )
            if (not selected or selected - allowed or mail_values.get("email_to")
                    or mail_values.get("email_cc")):
                raise ValidationError(_(
                    "Send training quotation PDFs only to named contacts authorized on this order."
                ))
            mail_values["notify_skip_followers"] = True
        return values

    def _action_schedule_message(self):
        for composer in self.filtered(lambda wizard: wizard.model == "sale.order"):
            composer._prepare_mail_values(composer._evaluate_res_ids())
        return super()._action_schedule_message()
