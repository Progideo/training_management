from odoo.addons.sale.controllers.portal import CustomerPortal


class TrainingCustomerPortal(CustomerPortal):
    def _get_payment_values(self, order_sudo, **kwargs):
        if order_sudo.training_request_kind:
            return {"payment_amount": None}
        return super()._get_payment_values(order_sudo, **kwargs)
