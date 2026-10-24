"""No native attachment/token/mail side channel for confidential quality dossiers."""

import logging

from odoo import api, models
from odoo.exceptions import AccessError, ValidationError

from .training_quality import QUALITY_MODELS

_logger = logging.getLogger(__name__)


class QualityAccessError(models.Model):
    _inherit = "ir.access"

    def _make_record_access_error(self, records, operation):
        if records._name in QUALITY_MODELS:
            # Odoo's debug diagnostic reads display names with sudo. A refusal
            # must not disclose private subjects or filenames, even in debug.
            _logger.info(
                "Private quality access denied: model=%s operation=%s uid=%s records=%s",
                records._name,
                operation,
                self.env.uid,
                records.ids[:6],
            )
            return AccessError(self.env._("This private quality record is unavailable."))
        return super()._make_record_access_error(records, operation)


class QualityPolicy(models.AbstractModel):
    _inherit = "training.document.policy"  # pylint: disable=consider-merging-classes-inherited  # Keep confidential quality rules separate from other training workflows.

    @api.private
    def _document(self, record):
        target = record.sudo()
        if target._name == "ir.attachment" and target.res_model in QUALITY_MODELS and target.res_id:
            return self.env[target.res_model].sudo().browse(target.res_id).exists()
        if target._name in QUALITY_MODELS:
            return target
        return super()._document(record)

    @api.private
    def _is_pedagogical(self, document):
        # The Sales integration delegates non-commercial training records through
        # this existing policy hook, including private S08 and quality evidence.
        return bool(document and document._name in QUALITY_MODELS) or super()._is_pedagogical(document)

    @api.private
    def _restricted(self, document):
        return bool(document and document._name in QUALITY_MODELS) or super()._restricted(document)

    @api.private
    def _can_read(self, record):
        target = self._document(record)
        if target._name not in QUALITY_MODELS:
            return super()._can_read(record)
        return bool(
            target
            and self.env.user.active
            and not self.env.user._is_public()
            and target.with_env(self.env(su=False)).has_access("read")
        )

    @api.private
    def _check_send(self, document, partners, **kwargs):
        if document and self._document(document)._name in QUALITY_MODELS:
            raise ValidationError(self.env._("Do not distribute private quality content through email."))
        return super()._check_send(document, partners, **kwargs)


class QualityAttachment(models.Model):
    _inherit = "ir.attachment"  # pylint: disable=consider-merging-classes-inherited  # Keep confidential quality rules separate from other training workflows.

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("res_model", self.env.context.get("default_res_model")) in QUALITY_MODELS for v in vals_list):
            raise AccessError(self.env._("Use immutable private quality files, not native attachments."))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("res_model") in QUALITY_MODELS or any(r.res_model in QUALITY_MODELS for r in self.sudo()):
            raise AccessError(self.env._("Keep quality files in their controlled private dossier."))
        return super().write(vals)


class QualityBinary(models.AbstractModel):
    _inherit = "ir.binary"  # pylint: disable=consider-merging-classes-inherited  # Keep confidential quality rules separate from other training workflows.

    def _find_record(self, xmlid=None, res_model="ir.attachment", res_id=None, access_token=None, field=None):
        record = super()._find_record(xmlid, res_model, res_id, access_token, field)
        if record._name in QUALITY_MODELS and (record._name != "training.quality.file" or field != "data"):
            raise AccessError(self.env._("Only the authorized quality file may be downloaded."))
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
        if record._name in QUALITY_MODELS:
            self.env["training.document.policy"]._check_read(record)
            if record._name != "training.quality.file" or field_name != "data":
                raise AccessError(self.env._("Only the authorized quality file may be downloaded."))
            filename_field = "name"
        return super()._get_stream_from(record, field_name, filename, filename_field, mimetype, default_mimetype)


class QualityMailMessage(models.Model):
    _inherit = "mail.message"  # pylint: disable=consider-merging-classes-inherited  # Keep confidential quality rules separate from other training workflows.

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("model", self.env.context.get("default_model")) in QUALITY_MODELS for v in vals_list):
            raise AccessError(self.env._("Record quality treatment in the private dossier history."))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("model") in QUALITY_MODELS:
            raise AccessError(self.env._("Do not attach shared chatter to a private quality dossier."))
        return super().write(vals)


class QualityMailActivity(models.Model):
    _inherit = "mail.activity"  # pylint: disable=consider-merging-classes-inherited  # Keep confidential quality rules separate from other training workflows.

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            model_id = vals.get("res_model_id") or self.env.context.get("default_res_model_id")
            if vals.get("res_model", self.env.context.get("default_res_model")) in QUALITY_MODELS or (
                model_id and self.env["ir.model"].browse(model_id).model in QUALITY_MODELS
            ):
                raise AccessError(self.env._("Use the private quality deadline list; no shared activity content."))
        return super().create(vals_list)

    def write(self, vals):
        model_id = vals.get("res_model_id")
        if vals.get("res_model") in QUALITY_MODELS or (
            model_id and self.env["ir.model"].browse(model_id).model in QUALITY_MODELS
        ):
            raise AccessError(self.env._("Use the private quality deadline list; no shared activity content."))
        return super().write(vals)
