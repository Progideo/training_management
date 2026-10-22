"""Keep dossier authorization even when native binary routes receive a token.

The exact Community image accepts a valid attachment token without checking the
parent. These two narrow hooks cover token validation and streaming (including
the PDF preview); ordinary Odoo attachments retain their native behavior.
"""

from odoo import api, models
from odoo.exceptions import ValidationError


CONFIDENTIAL_MODELS = ("training.adaptation", "training.adaptation.history")


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.private
    def _check_adaptation_access(self):
        for attachment in self.sudo():
            if attachment.res_model in CONFIDENTIAL_MODELS and attachment.res_id:
                # Reset sudo inherited from native binary/token processing. The
                # authenticated user must independently read the parent dossier.
                self.env[attachment.res_model].with_user(self.env.user).browse(attachment.res_id).check_access("read")

    @api.constrains("public", "res_model", "res_id")
    def _check_adaptation_private(self):
        if any(item.public and item.res_model in CONFIDENTIAL_MODELS for item in self):
            raise ValidationError(self.env._("Confidential adaptation attachments cannot be public."))

    def _can_return_content(self, field_name=None, access_token=None):
        self._check_adaptation_access()
        return super()._can_return_content(field_name, access_token)

    def _to_http_stream(self):
        self._check_adaptation_access()
        return super()._to_http_stream()
