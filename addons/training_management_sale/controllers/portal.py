from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.addons.account.controllers.portal import PortalAccount
from odoo.addons.account_payment.controllers.payment import PaymentPortal as InvoicePaymentPortal
from odoo.addons.sale.controllers.portal import CustomerPortal, PaymentPortal


class TrainingPortalDocumentAccess:
    def _document_check_access(self, model_name, document_id, access_token=None):
        document = super()._document_check_access(model_name, document_id, access_token)
        if not request.env.user.share:
            return document
        if model_name == "sale.order" and document.training_request_kind:
            authorized = document.training_portal_partner_ids
        elif model_name == "account.move" and document.training_is_sale_invoice:
            authorized = document.training_portal_partner_ids
        else:
            return document
        if request.env.user._is_public() or request.env.user.partner_id not in authorized:
            raise AccessError(request.env._("This training document requires an authorized portal contact."))
        return document


class TrainingCustomerPortal(TrainingPortalDocumentAccess, CustomerPortal):
    def _get_payment_values(self, order_sudo, **kwargs):
        if order_sudo.training_request_kind:
            return {"payment_amount": None}
        return super()._get_payment_values(order_sudo, **kwargs)


class TrainingAccountPortal(TrainingPortalDocumentAccess, PortalAccount):
    pass


class TrainingInvoicePaymentPortal(TrainingPortalDocumentAccess, InvoicePaymentPortal):
    @http.route()
    def invoice_transaction(self, invoice_id, access_token, **kwargs):
        invoice_sudo = self._document_check_access("account.move", invoice_id, access_token)
        if invoice_sudo._training_sale_invoices():
            raise ValidationError(
                request.env._("Online payment transactions are disabled for training orders and invoices.")
            )
        return super().invoice_transaction(invoice_id, access_token, **kwargs)


class TrainingPaymentPortal(TrainingPortalDocumentAccess, PaymentPortal):
    @http.route()
    def portal_order_transaction(self, order_id, access_token, **kwargs):
        try:
            order_sudo = self._document_check_access("sale.order", order_id, access_token)
        except AccessError:
            raise ValidationError(request.env._("The access token is invalid.")) from None
        if order_sudo.training_request_kind:
            raise ValidationError(
                request.env._("Online payment transactions are disabled for training orders and invoices.")
            )
        return super().portal_order_transaction(order_id, access_token, **kwargs)
