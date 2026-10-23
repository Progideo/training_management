"""Native author/recipient shortcuts outlive a grant; recheck reads and controller paths against current grants."""

from odoo import models
from odoo.exceptions import AccessError


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
        return self.env["training.document.policy"]._message_domain()

    def _get_with_access(self, mode="read", **kwargs):
        # Controllers may pass a sudoed message. Reapply the current user's
        # restriction before native author/recipient/token shortcuts.
        if self and self.env.user.share:
            permitted = self.sudo().filtered_domain(self._training_message_access_domain())
            if permitted != self:
                return self.browse()
        return super()._get_with_access(mode=mode, **kwargs)
