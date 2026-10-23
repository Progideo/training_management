"""Additional document grants; native ORM permissions always remain necessary.

All entry points use the same document/recipient calculation. Metadata is read
under sudo only to decide a grant, never to return document content. This service
has no public RPC method and does not grant access to pedagogical records.
"""

from odoo import api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain


class TrainingDocumentPolicy(models.AbstractModel):
    _name = "training.document.policy"
    _description = "Training Document Authorization"

    @api.private
    def _document(self, record):
        """Resolve a native file/message to its commercial source, if relevant."""
        record.ensure_one()
        target = record.sudo()
        for model, model_field, id_field in (
            ("ir.attachment", "res_model", "res_id"),
            ("mail.message", "model", "res_id"),
        ):
            if target._name == model:
                source_model, source_id = target[model_field], target[id_field]
                if (
                    source_model not in ("mail.message", "sale.order", "account.move", "account.payment")
                    or not source_id
                ):
                    return self.env["sale.order"]
                target = self.env[source_model].sudo().browse(source_id).exists()
                if not target:
                    raise AccessError(self.env._("This training attachment is unavailable."))
        if target._name not in ("sale.order", "account.move", "account.payment"):
            return self.env["sale.order"]
        return target

    @api.private
    def _restricted(self, document):
        if not document:
            return False
        document.ensure_one()
        if document._name == "sale.order":
            return bool(document.sudo().training_request_kind)
        if document._name == "account.move":
            return document.sudo().training_is_sale_invoice
        if document._name == "account.payment":
            return document.sudo()._training_receipt_is_restricted()
        return False

    @api.private
    def _partners(self, document, *, email_only=False):
        """Current named grants; receipts keep their invoice intersection rule."""
        if not self._restricted(document):
            return self.env["res.partner"]
        target = document.sudo()
        partners = (
            target._training_receipt_allowed_partners()
            if target._name == "account.payment"
            else target.training_portal_partner_ids
        )
        return partners.filtered("email") if email_only else partners

    @api.private
    def _can_read(self, record):
        # This is an additional veto, not an alternative to native permissions.
        if not self.env.user.share:
            return True
        document = self._document(record)
        return not self._restricted(document) or (
            not self.env.user._is_public() and self.env.user.partner_id in self._partners(document)
        )

    @api.private
    def _check_read(self, record):
        if not self._can_read(record):
            raise AccessError(self.env._("This training document requires a currently authorized portal contact."))

    @api.private
    def _check_send(self, document, partners, *, email_to=False, email_cc=False, required=True, allow_internal=False):
        if not self._restricted(document):
            return
        # At transport, native internal notifications keep their existing rights.
        # Explicit document sends still require every selected named recipient.
        selected = partners.sudo()
        if allow_internal:
            selected = selected.filtered(lambda p: not p.user_ids or all(u.share for u in p.user_ids))
        if (required and not partners) or email_to or email_cc or selected - self._partners(document, email_only=True):
            raise ValidationError(self.env._("Send training documents only to currently authorized named contacts."))

    @api.private
    def _filter_notifications(self, document, recipients):
        if not self._restricted(document):
            return recipients
        allowed = set(self._partners(document).ids)
        return [recipient for recipient in recipients if not recipient["share"] or recipient["id"] in allowed]

    @api.private
    def _message_domain(self):
        """Uncached grant domain, intersected with native message permissions."""
        if not self.env.user.share:
            return Domain.TRUE
        result = Domain.TRUE
        for model, flag in (("sale.order", "training_request_kind"), ("account.move", "training_is_sale_invoice")):
            allowed = Domain(flag, "=", False)
            if not self.env.user._is_public():
                allowed |= Domain("training_portal_partner_ids", "in", self.env.user.partner_id.ids)
            query = self.env[model].sudo()._search(allowed)
            result &= Domain("model", "!=", model) | Domain("res_id", "any!", query)
        # In the pinned image reconciled_invoice_ids is non-stored and cannot
        # express the receipt intersection as a relational search domain.
        messages = self.env["mail.message"].sudo().search_fetch([("model", "=", "account.payment")], ["res_id"])
        payments = self.env["account.payment"].sudo().browse(messages.mapped("res_id")).exists()
        forbidden = payments.filtered(lambda payment: not self._can_read(payment))
        return result & (Domain("model", "!=", "account.payment") | ~Domain("res_id", "in", forbidden.ids))
