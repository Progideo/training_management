"""Native token resolution and streaming of an already-resolved record both need the current document grant."""

from odoo import models


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"

    def _check_training_binary_access(self, record):
        self.env["training.document.policy"]._check_read(record)

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
