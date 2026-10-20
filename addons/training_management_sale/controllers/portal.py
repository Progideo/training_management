from odoo import http, _
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.sale.controllers.portal import CustomerPortal, PaymentPortal


class TrainingCustomerPortal(CustomerPortal):
    def _get_payment_values(self, order_sudo, **kwargs):
        if order_sudo.training_request_kind:
            return {"payment_amount": None}
        return super()._get_payment_values(order_sudo, **kwargs)


class TrainingPaymentPortal(PaymentPortal):
    @http.route()
    def portal_order_transaction(self, order_id, access_token, **kwargs):
        try:
            order_sudo = self._document_check_access("sale.order", order_id, access_token)
        except AccessError:
            raise ValidationError(self.env._("The access token is invalid.")) from None
        if order_sudo.training_request_kind:
            raise ValidationError(_(
                "Online payment transactions are disabled for training orders and invoices."
            ))
        return super().portal_order_transaction(order_id, access_token, **kwargs)
