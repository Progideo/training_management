"""Keep the native scheduler and retain the training composer's recipient scope."""

from odoo import api, models


class MailScheduledMessage(models.Model):
    _inherit = "mail.scheduled.message"

    @api.model
    def _notification_parameters_whitelist(self):
        allowed = super()._notification_parameters_whitelist()
        if len(self) == 1 and self.model in ("sale.order", "account.move", "account.payment"):
            document = self.env[self.model].browse(self.res_id)
            if self.env["training.document.policy"]._restricted(document):
                # The composer already set this native parameter. Without this
                # whitelist entry the deferred path silently notifies followers.
                return allowed | {"notify_skip_followers"}
        return allowed
