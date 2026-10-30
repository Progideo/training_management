"""Document confidentiality around native transactions; no payment policy."""

from odoo import models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _training_documents(self):
        self.ensure_one()
        return [*self.sale_order_ids, *self.invoice_ids]

    def _check_training_document_access(self):
        policy = self.env["training.document.policy"]
        for transaction in self:
            for document in transaction._training_documents():
                policy.with_user(self.env.user)._check_read(document)

    def _bus_channels(self):
        self.ensure_one()
        documents = self._training_documents()
        policy = self.env["training.document.policy"]
        if not any(policy._restricted(document) for document in documents):
            return super()._bus_channels()
        # The native status page already listens on its authenticated partner's
        # private bus. Never broadcast training status through a reusable public
        # transaction token: revoking a grant must also revoke future updates.
        partners = policy._partners(documents[0])
        for document in documents[1:]:
            partners &= policy._partners(document)
        for user in self.partner_id.user_ids.filtered(lambda user: not user.share):
            if all(policy.with_user(user)._can_read(document) for document in documents):
                partners |= user.partner_id
        return partners
