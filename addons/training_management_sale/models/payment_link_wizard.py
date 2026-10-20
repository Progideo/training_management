from odoo import api, models, _
from odoo.exceptions import ValidationError


class PaymentLinkWizard(models.TransientModel):
    _inherit = "payment.link.wizard"

    @api.model
    def _check_training_document_link(self, model_name, record_id):
        if not record_id:
            return
        if model_name == "sale.order":
            document = self.env["sale.order"].browse(record_id)
            is_training = bool(document.training_request_kind)
        elif model_name == "account.move":
            document = self.env["account.move"].browse(record_id)
            is_training = bool(document._training_sale_invoices())
        else:
            return
        if is_training:
            raise ValidationError(_(
                "Online payment links are disabled for training orders and invoices."
            ))

    @api.model
    def default_get(self, fields_list):
        self._check_training_document_link(
            self.env.context.get("active_model"), self.env.context.get("active_id"),
        )
        return super().default_get(fields_list)

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard._check_training_document_link(wizard.res_model, wizard.res_id)
        return wizards

    def write(self, vals):
        result = super().write(vals)
        for wizard in self:
            wizard._check_training_document_link(wizard.res_model, wizard.res_id)
        return result

    def _compute_link(self):
        for wizard in self:
            wizard._check_training_document_link(wizard.res_model, wizard.res_id)
        return super()._compute_link()
