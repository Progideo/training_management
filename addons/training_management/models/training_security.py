"""Shared confidentiality boundaries; business grants remain in their workflows."""

import hashlib
import json
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_attachment import CONFIDENTIAL_MODELS

_logger = logging.getLogger(__name__)


class TrainingAccessDiagnostic(models.Model):
    _inherit = "ir.access"

    def _make_record_access_error(self, records, operation):
        if records._name.startswith("training."):
            # Native debug diagnostics resolve display names with sudo. Even
            # an identifier guessed by an unauthorized user must reveal no name.
            _logger.info(
                "Training access denied: uid=%s model=%s operation=%s records=%s",
                self.env.uid,
                records._name,
                operation,
                records.ids[:6],
            )
            return AccessError(self.env._("This private training record is unavailable."))
        return super()._make_record_access_error(records, operation)


class TrainingSecurityPolicy(models.AbstractModel):
    _inherit = "training.document.policy"

    @api.private
    def _document(self, record):
        # Classification may read only the parent pointer with sudo; it never
        # authorizes a token, former referent, follower or message recipient.
        target = record.sudo()
        if target._name == "ir.attachment" and target.res_model in CONFIDENTIAL_MODELS:
            target = self.env[target.res_model].sudo().browse(target.res_id).exists()
        elif target._name == "mail.message" and target.model in CONFIDENTIAL_MODELS:
            target = self.env[target.model].sudo().browse(target.res_id).exists()
        if target._name in CONFIDENTIAL_MODELS:
            if not target:
                raise AccessError(self.env._("This private training record is unavailable."))
            return target
        return super()._document(record)

    @api.private
    def _is_pedagogical(self, document):
        return bool(document and document._name in CONFIDENTIAL_MODELS) or super()._is_pedagogical(document)

    @api.private
    def _restricted(self, document):
        return bool(document and document._name in CONFIDENTIAL_MODELS) or super()._restricted(document)

    @api.private
    def _can_read(self, record):
        document = self._document(record)
        if document._name in CONFIDENTIAL_MODELS:
            delivery = (
                document.delivery_id if document._name == "training.adaptation" else document.adaptation_id.delivery_id
            )
            return bool(
                document
                and self.env.user.active
                and not self.env.user._is_public()
                and self.env.user in delivery.adaptation_referent_id | delivery.adaptation_deputy_id
                and document.with_env(self.env(su=False)).has_access("read")
            )
        return super()._can_read(record)

    @api.private
    def _check_send(self, document, partners, **kwargs):
        if document and self._document(document)._name in CONFIDENTIAL_MODELS:
            raise ValidationError(self.env._("Do not distribute confidential adaptations through email."))
        return super()._check_send(document, partners, **kwargs)

    @api.private
    def _audit_file_read(self, record):
        """Server log survives read-only HTTP transactions; never store file content.

        This records authorized stream/preview preparation, not proof that a
        browser received all bytes. Existing exports retain their DB manifests.
        """
        document = self._document(record)
        if self._restricted(document):
            _logger.info(
                "Training file prepared: uid=%s company=%s model=%s record=%s privileged=%s",
                self.env.uid,
                (document.company_id if "company_id" in document._fields else document.training_company_id).id,
                document._name,
                document.id,
                self.env.su or self.env.user.has_group("base.group_system"),
            )


class TrainingSecurityBinary(models.AbstractModel):
    _inherit = "ir.binary"  # pylint: disable=consider-merging-classes-inherited  # Keep access auditing separate from binary authorization.

    def _get_stream_from(
        self,
        record,
        field_name="raw",
        filename=None,
        filename_field="name",
        mimetype=None,
        default_mimetype="application/octet-stream",
    ):
        stream = super()._get_stream_from(record, field_name, filename, filename_field, mimetype, default_mimetype)
        self.env["training.document.policy"]._audit_file_read(record)
        return stream


class TrainingExportAudit(models.Model):
    _name = "training.export.audit"
    _inherit = "training.learning.evidence"
    _description = "Training Export Scope Manifest"
    _order = "id desc"

    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    exported_at = fields.Datetime(required=True)
    model_name = fields.Char(required=True)
    manifest = fields.Json(required=True)
    sha256 = fields.Char(required=True)

    @api.private
    def _record_export(self, records, columns):
        # The caller checked the entire source recordset and successfully built
        # its export. Retain scope, not values, names, emails or private answers.
        records.check_access("read")
        if "company_id" not in records._fields:
            return
        for company in records.company_id:
            rows = records.filtered(lambda row: row.company_id == company)
            manifest = {"model": records._name, "ids": sorted(rows.ids), "fields": columns, "population": len(rows)}
            self._create_evidence(
                {
                    "company_id": company.id,
                    "actor_id": self.env.uid,
                    "exported_at": fields.Datetime.now(),
                    "model_name": records._name,
                    "manifest": manifest,
                    "sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                }
            )


class TrainingExportScope(models.AbstractModel):
    _inherit = "base"

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        training = self._name.startswith("training.")
        if training:
            # Native export of the external identifier can avoid any field read.
            # Enforce the record rules even for that path and nested traversal.
            self.check_access("read")
        result = super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
        if (
            training
            and self
            and self._name
            not in (
                "training.adaptation",
                "training.adaptation.history",
                "training.dashboard.line",
            )
        ):
            # These three sources already retain their own immutable manifest.
            self.env["training.export.audit"]._record_export(self, fields)
        return result
