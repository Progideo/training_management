from odoo import http
from odoo.http import request
from odoo.addons.payment.controllers.payment_status import PaymentStatus
from odoo.addons.account.controllers.portal import PortalAccount
from odoo.addons.account_payment.controllers.payment import PaymentPortal as InvoicePaymentPortal
from odoo.addons.sale.controllers.portal import CustomerPortal, PaymentPortal


class TrainingPortalDocumentAccess:
    def _document_check_access(self, model_name, document_id, access_token=None):
        document = super()._document_check_access(model_name, document_id, access_token)
        request.env["training.document.policy"]._check_read(document)
        return document


class TrainingCustomerPortal(TrainingPortalDocumentAccess, CustomerPortal):
    pass


class TrainingAccountPortal(TrainingPortalDocumentAccess, PortalAccount):
    pass


class TrainingInvoicePaymentPortal(TrainingPortalDocumentAccess, InvoicePaymentPortal):
    @http.route()
    def payment_pay(self, *args, amount=None, invoice_id=None, access_token=None, **kwargs):
        # Native payment tokens can bypass _document_check_access on this route.
        # Keep the named grant before rendering invoice details or a payment form.
        target = self._cast_as_int(invoice_id)
        if target:
            invoice = request.env["account.move"].sudo().browse(target).exists()
            request.env["training.document.policy"]._check_read(invoice)
        return super().payment_pay(*args, amount=amount, invoice_id=invoice_id, access_token=access_token, **kwargs)

    @http.route()
    def payment_confirm(self, tx_id, access_token, **kwargs):
        target = self._cast_as_int(tx_id)
        if target:
            request.env["payment.transaction"].sudo().browse(target).exists()._check_training_document_access()
        return super().payment_confirm(tx_id, access_token, **kwargs)

    def _process_transaction(self, partner_id, currency_id, invoice_ids, payment_reference, **kwargs):
        # Includes the native batch route for overdue invoices.
        for invoice in request.env["account.move"].sudo().browse(invoice_ids):
            request.env["training.document.policy"]._check_read(invoice)
        return super()._process_transaction(partner_id, currency_id, invoice_ids, payment_reference, **kwargs)


class TrainingPaymentPortal(TrainingPortalDocumentAccess, PaymentPortal):
    pass


class TrainingPaymentStatus(PaymentStatus):
    def _get_monitored_transaction(self):
        transaction = super()._get_monitored_transaction()
        transaction._check_training_document_access()
        return transaction
