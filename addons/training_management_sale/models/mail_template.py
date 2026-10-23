"""The native template API permits forced recipients without a composer; validate them against the same document grant."""

from odoo import models
from odoo.exceptions import ValidationError


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def send_mail_batch(
        self, res_ids, force_send=False, raise_exception=False, email_values=None, email_layout_xmlid=False
    ):
        self.ensure_one()
        if self.model in ("sale.order", "account.move", "account.payment"):
            records = self.env[self.model].browse([res_id for res_id in res_ids if res_id])
            policy = self.env["training.document.policy"]
            restricted = records.filtered(policy._restricted)
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
                        self.env._("Recipients of training documents cannot be overridden on direct email sends.")
                    )
                rendered = self._generate_template(
                    restricted.ids,
                    ["email_to", "email_cc", "partner_to", "partner_cc"],
                )
                for record in restricted:
                    values = rendered[record.id]
                    selected = self.env["res.partner"].browse(
                        values.get("partner_ids", []) + values.get("partner_cc_ids", [])
                    )
                    policy._check_send(
                        record, selected, email_to=values.get("email_to"), email_cc=values.get("email_cc")
                    )
        return super().send_mail_batch(
            res_ids,
            force_send=force_send,
            raise_exception=raise_exception,
            email_values=email_values,
            email_layout_xmlid=email_layout_xmlid,
        )
