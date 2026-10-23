"""Keep dossier authorization even when native binary routes receive a token.

The exact Community image accepts a valid attachment token without checking the
parent. These two narrow hooks cover token validation and streaming (including
the PDF preview); ordinary Odoo attachments retain their native behavior.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


CONFIDENTIAL_MODELS = ("training.adaptation", "training.adaptation.history")
S08_MODELS = ("training.proof", "training.document")


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
        if any(v.get("res_model", self.env.context.get("default_res_model")) in S08_MODELS for v in vals_list):
            raise ValidationError(self.env._("Use the controlled evidence or document field."))
        if any(
            vals.get("res_model", self.env.context.get("default_res_model"))
            in ("training.attendance.event", "training.attendance.edit")
            for vals in vals_list
        ):
            raise ValidationError(
                self.env._("Attendance evidence is stored only through the controlled attendance action.")
            )
        if any(vals.get("training_program_id") for vals in vals_list):
            raise ValidationError(self.env._("Reference programme PDFs are created only during controlled generation."))
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            source_model = vals.get("res_model") or self.env.context.get("default_res_model")
            if source_model == "training.learning.entry":
                vals.update(self._add_missing_default_values(vals))
                entry = self.env["training.learning.entry"].sudo().browse(vals.get("res_id")).exists()
                if not entry:
                    raise ValidationError(self.env._("Use the private learning form to upload a file."))
                self.env["training.document.policy"]._check_read(entry)
                if (
                    entry.sealed_at
                    or entry.create_uid != self.env.user
                    or vals.get("res_field") != "data"
                    or vals.get("public")
                    or vals.get("access_token")
                    or vals.get("url")
                    or vals.get("type", "binary") != "binary"
                    or self.sudo().search_count(
                        [("res_model", "=", entry._name), ("res_id", "=", entry.id), ("res_field", "=", "data")]
                    )
                ):
                    raise ValidationError(self.env._("Use the private learning form to upload a file."))
                vals["company_id"] = entry.company_id.id
            if source_model == "training.material":
                vals.update(self._add_missing_default_values(vals))
                material = self.env["training.material"].browse(
                    vals.get("res_id") or self.env.context.get("default_res_id")
                )
                material._require_coordinator()
                material._serialize()
                # Native Binary.create uses the environment company by default.
                # Derive this metadata from the authorized parent in a multi-company batch.
                vals["company_id"] = material.company_id.id if material else False
                if (
                    not material
                    or material.frozen_at
                    or material.withdrawn
                    or vals.get("res_field") != "data"
                    or vals.get("public")
                    or vals.get("access_token")
                    or vals.get("type", "binary") != "binary"
                    or vals.get("url")
                    or self.sudo().search_count(
                        [
                            ("res_model", "=", "training.material"),
                            ("res_id", "=", material.id),
                            ("res_field", "=", "data"),
                        ]
                    )
                ):
                    raise ValidationError(self.env._("Use the PDF field of a new private support version."))
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
        if vals.get("res_model") in S08_MODELS or any(a.res_model in S08_MODELS for a in self.sudo()):
            raise ValidationError(self.env._("Keep preserved S08 documents unchanged."))
        if vals.get("res_model") in ("training.attendance.event", "training.attendance.edit") or any(
            a.res_model in ("training.attendance.event", "training.attendance.edit") for a in self.sudo()
        ):
            raise ValidationError(
                self.env._("Attendance evidence is stored only through the controlled attendance action.")
            )
        if vals.get("res_model") == "training.learning.entry" or any(
            a.res_model == "training.learning.entry" for a in self.sudo()
        ):
            raise ValidationError(self.env._("Private learning files cannot be changed, shared or reassigned."))
        protected = self.sudo().filtered(lambda item: item.res_model == "training.material")
        if protected or vals.get("res_model") == "training.material":
            if not protected or set(vals) & {
                "res_model",
                "res_id",
                "res_field",
                "public",
                "access_token",
                "type",
                "url",
                "company_id",
            }:
                raise ValidationError(self.env._("A private support cannot be detached, shared or reassigned."))
            materials = self.env["training.material"].browse(protected.mapped("res_id"))
            materials._require_coordinator()
            materials._serialize()
            if any(item.frozen_at or item.withdrawn for item in materials):
                raise ValidationError(self.env._("The distributed PDF file is immutable."))
        if any(self.sudo().mapped("training_program_id")) or vals.get("training_program_id"):
            raise ValidationError(self.env._("A reference programme PDF cannot be changed or shared by token."))
        return super().write(vals)

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        if any(item.res_model in ("training.material", "training.learning.entry") for item in self.sudo()):
            self.check_access("read")
            raise UserError(
                self.env._("Bulk export of private support records is unavailable. Download an authorized PDF instead.")
            )
        return super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)

    def copy_data(self, default=None):
        if any(item.res_model in ("training.material", "training.learning.entry") for item in self.sudo()):
            raise ValidationError(self.env._("Private support files cannot be copied."))
        return super().copy_data(default)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_material(self):
        if any(item.res_model in ("training.material", "training.learning.entry") for item in self.sudo()):
            raise ValidationError(self.env._("Keep private support files and their history."))

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
        policy = self.env["training.document.policy"]
        document = policy._document(self)
        if policy._is_pedagogical(document):
            policy._check_read(self)
            return True
        return super()._can_return_content(field_name, access_token)

    def _to_http_stream(self):
        self._check_programme_pdf_access()
        self._check_adaptation_access()
        self.env["training.document.policy"]._check_read(self)
        return super()._to_http_stream()
