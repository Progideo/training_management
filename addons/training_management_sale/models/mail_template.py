from odoo import _, models
from odoo.exceptions import ValidationError


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def send_mail_batch(
        self, res_ids, force_send=False, raise_exception=False, email_values=None, email_layout_xmlid=False
    ):
        self.ensure_one()
        if self.model in ("sale.order", "account.move", "account.payment"):
            records = self.env[self.model].browse([res_id for res_id in res_ids if res_id])
            restricted = records.filtered(
                lambda record: (
                    record.training_request_kind
                    if self.model == "sale.order"
                    else record.training_is_sale_invoice
                    if self.model == "account.move"
                    else record._training_receipt_is_restricted()
                )
            )
            if restricted:
                if email_values and set(email_values) & {
                    "email_to",
                    "email_cc",
                    "partner_ids",
                    "partner_cc_ids",
                    "recipient_ids",
                    "recipient_cc_ids",
                }:
                    raise ValidationError(
                        _("Recipients of training documents cannot be overridden on direct email sends.")
                    )
                rendered = self._generate_template(
                    restricted.ids,
                    ["email_to", "email_cc", "partner_to", "partner_cc"],
                )
                for record in restricted:
                    if self.model == "account.payment":
                        allowed = record._training_receipt_allowed_partners()
                    else:
                        allowed = record.training_portal_partner_ids.filtered("email")
                    values = rendered[record.id]
                    selected = set(values.get("partner_ids", []) + values.get("partner_cc_ids", []))
                    if not selected or values.get("email_to") or values.get("email_cc") or selected - set(allowed.ids):
                        raise ValidationError(
                            _("Send training documents only to named contacts authorized on the document.")
                        )
        return super().send_mail_batch(
            res_ids,
            force_send=force_send,
            raise_exception=raise_exception,
            email_values=email_values,
            email_layout_xmlid=email_layout_xmlid,
        )
