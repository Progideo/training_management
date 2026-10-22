"""Keep dossier authorization even when native binary routes receive a token.

The exact Community image accepts a valid attachment token without checking the
parent. These two narrow hooks cover token validation and streaming (including
the PDF preview); ordinary Odoo attachments retain their native behavior.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


CONFIDENTIAL_MODELS = ("training.adaptation", "training.adaptation.history")


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    training_program_id = fields.Many2one(
        "training.program.version",
        string="Reference Programme",
        readonly=True,
        copy=False,
        index=True,
        ondelete="restrict",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("training_program_id") for vals in vals_list):
            raise ValidationError(self.env._("Reference programme PDFs are created only during controlled generation."))
        # An untrusted default_* context cannot forge the protected marker.
        return super().create([dict(vals, training_program_id=False) for vals in vals_list])

    @api.private
    def _create_programme_pdf(self, program, raw):
        program.ensure_one()
        program._require_pdf_coordinator()
        # Narrow elevation: the coordinator may validate a programme without
        # generic attachment creation rights. No elevation is used for rendering.
        return super(IrAttachment, self.sudo()).create(  # pylint: disable=super-method-mismatch  # private controlled factory
            {
                "name": f"Programme-{program.id}-{program.version}.pdf",
                "raw": raw,
                "type": "binary",
                "mimetype": "application/pdf",
                "res_model": program._name,
                "res_id": program.id,
                "res_field": False,
                "training_program_id": program.id,
                "company_id": program.company_id.id,
                "public": False,
                "access_token": False,
                "url": False,
            }
        )

    def write(self, vals):
        if any(self.sudo().mapped("training_program_id")) or vals.get("training_program_id"):
            raise ValidationError(self.env._("A reference programme PDF cannot be changed or shared by token."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_programme_pdf(self):
        if any(self.sudo().mapped("training_program_id")):
            raise ValidationError(self.env._("A reference programme PDF cannot be deleted."))

    @api.private
    def _check_programme_pdf_access(self):
        for attachment in self.sudo():
            if attachment.training_program_id:
                program = attachment.training_program_id.with_user(self.env.user)
                if program._reference_pdf().id != attachment.id:
                    raise ValidationError(self.env._("The reference PDF link is invalid."))

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
        self._check_programme_pdf_access()
        self._check_adaptation_access()
        return super()._can_return_content(field_name, access_token)

    def _to_http_stream(self):
        self._check_programme_pdf_access()
        self._check_adaptation_access()
        return super()._to_http_stream()
