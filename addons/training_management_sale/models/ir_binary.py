from odoo import models, _
from odoo.exceptions import AccessError


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"

    def _find_record(self, xmlid=None, res_model="ir.attachment", res_id=None,
                     access_token=None, field=None):
        record = super()._find_record(xmlid, res_model, res_id, access_token, field)
        if not self.env.user.share:
            return record

        target = record.sudo()
        if target._name == "ir.attachment":
            model_name, document_id = target.res_model, target.res_id
            if model_name == "mail.message":
                message = self.env["mail.message"].sudo().browse(document_id).exists()
                model_name, document_id = (message.model, message.res_id) if message else (None, None)
            if model_name not in ("sale.order", "account.move") or not document_id:
                return record
            target = self.env[model_name].sudo().browse(document_id).exists()
            if not target:
                raise AccessError(_("This training attachment is unavailable."))

        if target._name == "sale.order" and target.training_request_kind:
            authorized = target.training_portal_partner_ids
        elif target._name == "account.move" and target.training_is_sale_invoice:
            authorized = target.training_portal_partner_ids
        else:
            return record
        if self.env.user._is_public() or self.env.user.partner_id not in authorized:
            raise AccessError(_("This training attachment requires an authorized portal contact."))
        return record
