from odoo import models
from odoo.exceptions import AccessError


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"

    def _check_training_binary_access(self, record):
        if not self.env.user.share:
            return

        target = record.sudo()
        if target._name == "ir.attachment":
            model_name, document_id = target.res_model, target.res_id
            if model_name == "mail.message":
                message = self.env["mail.message"].sudo().browse(document_id).exists()
                model_name, document_id = (message.model, message.res_id) if message else (None, None)
            if model_name not in ("sale.order", "account.move", "account.payment") or not document_id:
                return
            target = self.env[model_name].sudo().browse(document_id).exists()
            if not target:
                raise AccessError(self.env._("This training attachment is unavailable."))

        if target._name == "sale.order" and target.training_request_kind:
            authorized = target.training_portal_partner_ids
        elif target._name == "account.move" and target.training_is_sale_invoice:
            authorized = target.training_portal_partner_ids
        elif target._name == "account.payment" and target._training_receipt_is_restricted():
            authorized = target._training_receipt_allowed_partners()
        else:
            return
        if self.env.user._is_public() or self.env.user.partner_id not in authorized:
            raise AccessError(self.env._("This training attachment requires an authorized portal contact."))

    def _find_record(self, xmlid=None, res_model="ir.attachment", res_id=None, access_token=None, field=None):
        record = super()._find_record(xmlid, res_model, res_id, access_token, field)
        self._check_training_binary_access(record)
        return record

    def _get_stream_from(
        self,
        record,
        field_name="raw",
        filename=None,
        filename_field="name",
        mimetype=None,
        default_mimetype="application/octet-stream",
    ):
        self._check_training_binary_access(record)
        return super()._get_stream_from(
            record,
            field_name,
            filename,
            filename_field,
            mimetype,
            default_mimetype,
        )
