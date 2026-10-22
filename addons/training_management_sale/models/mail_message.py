from odoo import models
from odoo.exceptions import AccessError
from odoo.fields import Domain


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _access_domain(self, operation):
        # Keep the native permissions cached; the additional document grant is
        # deliberately recomputed, so a revoke cannot leave cached ids/queries.
        domain = super()._access_domain(operation)
        if operation == "read" and self.env.user.share:
            domain &= self._training_message_access_domain()
        return domain

    def _check_training_message_access(self):
        if self and not self.env.su and self.env.user.share:
            if self.sudo().filtered_domain(self._training_message_access_domain()) != self:
                raise AccessError(self.env._("This training message requires a currently authorized contact."))

    def read(self, fields=None, load="_classic_read"):
        self._check_training_message_access()
        return super().read(fields=fields, load=load)

    def _training_message_access_domain(self):
        if not self.env.user.share:
            return Domain.TRUE
        partner_id = self.env.user.partner_id.id
        result = Domain.TRUE
        for model, flag in (("sale.order", "training_request_kind"), ("account.move", "training_is_sale_invoice")):
            allowed = Domain(flag, "=", False)
            if not self.env.user._is_public():
                allowed |= Domain("training_portal_partner_ids", "in", [partner_id])
            # Only ids are used here; native message access remains necessary.
            query = self.env[model].sudo()._search(allowed)
            result &= Domain("model", "!=", model) | Domain("res_id", "any!", query)
        # Native reconciled_invoice_ids is non-stored and does not support
        # relational/negative search operators in this exact Community version.
        # Inspect only payments referenced by messages, under sudo for metadata;
        # no body or recipient data is returned by this permission calculation.
        messages = self.sudo().search_fetch([("model", "=", "account.payment")], ["res_id"])
        payments = self.env["account.payment"].sudo().browse(messages.mapped("res_id")).exists()
        forbidden = payments.filtered(
            lambda payment: (
                payment._training_receipt_is_restricted()
                and (
                    self.env.user._is_public()
                    or self.env.user.partner_id not in payment._training_receipt_allowed_partners()
                )
            )
        )
        return result & (Domain("model", "!=", "account.payment") | ~Domain("res_id", "in", forbidden.ids))

    def _get_with_access(self, mode="read", **kwargs):
        # Controllers may pass a sudoed message. Reapply the current user's
        # restriction before native author/recipient/token shortcuts.
        if self and self.env.user.share:
            permitted = self.sudo().filtered_domain(self._training_message_access_domain())
            if permitted != self:
                return self.browse()
        return super()._get_with_access(mode=mode, **kwargs)

    def export_data(self, fields_to_export):
        self._check_training_message_access()
        self.check_access("read")
        return super().export_data(fields_to_export)
