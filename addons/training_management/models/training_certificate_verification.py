"""P20: frozen public projection with one audited terminal status change."""

import json
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_closure import QUALITY


class CertificateVerification(models.Model):
    _name = "training.certificate.verification"
    _description = "Training Certificate Verification"
    _rec_name = "reference"
    _check_company_auto = True

    document_id = fields.Many2one("training.document", required=True, ondelete="restrict", check_company=True)
    dossier_id = fields.Many2one(related="document_id.dossier_id", store=True)
    company_id = fields.Many2one(related="document_id.company_id", store=True)
    token = fields.Char(required=True, copy=False, groups=QUALITY)
    url = fields.Char(string="Verification Link", required=True)
    reference = fields.Char(required=True)
    issuer = fields.Char(required=True)
    beneficiary = fields.Char(required=True)
    programme = fields.Char(required=True)
    programme_version = fields.Char(required=True)
    kind = fields.Selection(
        [
            ("participation", "Participation Certificate"),
            ("completion", "Completion Certificate"),
            ("achievement", "Achievement Certificate"),
        ],
        required=True,
    )
    issued_at = fields.Datetime(string="Certificate Issued At", required=True)
    sha256 = fields.Char(required=True)
    state = fields.Selection(
        [("valid", "Valid"), ("revoked", "Revoked"), ("replaced", "Replaced")], required=True, default="valid"
    )
    reason = fields.Text()
    changed_at = fields.Datetime()
    changed_by_id = fields.Many2one("res.users", ondelete="restrict")
    replacement_id = fields.Many2one("training.certificate.verification", ondelete="restrict", check_company=True)

    _unique_document = models.Constraint("UNIQUE(document_id)", "This document already has verification.")
    _unique_token = models.Constraint("UNIQUE(token)", "This verification identifier already exists.")

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # only the private issued-PDF factory
        raise AccessError(self.env._("Verification is created only when issuing a new certificate."))

    def write(self, vals):  # pylint: disable=method-required-super  # audited actions below
        raise AccessError(self.env._("Use the certificate revocation or replacement action."))

    def copy_data(self, default=None):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Certificate verification cannot be copied."))

    @api.ondelete(at_uninstall=False)
    def _keep_verification(self):
        raise ValidationError(self.env._("Keep certificate verification and its history."))

    @api.private
    def _issue(self, document, token, url):
        document.dossier_id._authorize(quality=True)
        snapshot = json.loads(document.snapshot)
        # Narrow elevation for the immutable factory; no public create permission.
        # pylint: disable-next=super-method-mismatch,context-overridden  # controlled immutable factory
        return super(CertificateVerification, self.sudo().with_context({})).create(
            {
                "document_id": document.id,
                "token": token,
                "url": url,
                "reference": snapshot["reference"],
                "issuer": snapshot["issuer"],
                "beneficiary": snapshot["beneficiary"],
                "programme": snapshot["programme"],
                "programme_version": snapshot["programme_version"],
                "kind": document.kind,
                "issued_at": document.created_at,
                "sha256": document.sha256,
            }
        )

    @api.private
    def _authorize(self):
        self.ensure_one()
        # Re-evaluate actual user rights even if a caller supplied a sudo record.
        record = self.with_env(self.env(su=False))
        record.check_access("read")
        if record.company_id not in record.env.companies:
            raise AccessError(self.env._("This certificate is outside the allowed companies."))
        record.dossier_id._authorize(quality=True)
        return record

    def action_revoke(self, reason=None):
        return self._change("revoked", reason=reason)

    def action_replace(self, replacement_id=None, reason=None):
        return self._change("replaced", reason=reason, replacement_id=replacement_id)

    @api.private
    def _change(self, state, reason=None, replacement_id=None):
        record = self._authorize()
        if reason is None:
            return {
                "type": "ir.actions.act_window",
                "name": self.env._("Change Certificate Status"),
                "res_model": "training.certificate.change",
                "view_mode": "form",
                "target": "new",
                "context": {"default_verification_id": record.id, "default_state": state},
            }
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError(self.env._("Enter a reason for this action."))
        record.dossier_id._serialize()
        if record.state == state and record.replacement_id.id == (replacement_id or False):
            return True
        if record.state != "valid":
            raise ValidationError(self.env._("This certificate has already been revoked or replaced."))
        replacement = record.browse(replacement_id).exists() if replacement_id else record.browse()
        if state == "replaced":
            if not replacement or replacement == record:
                raise ValidationError(self.env._("Choose a different valid certificate for the same dossier and type."))
            replacement = replacement._authorize()
            if (
                replacement.dossier_id != record.dossier_id
                or replacement.kind != record.kind
                or replacement.state != "valid"
            ):
                raise ValidationError(self.env._("Choose a different valid certificate for the same dossier and type."))
        # Public write stays forbidden; only this authorized, serialized terminal transition mutates audit fields.
        # pylint: disable-next=super-method-mismatch  # checked terminal transition
        return super(CertificateVerification, record.sudo()).write(
            {
                "state": state,
                "reason": reason.strip(),
                "changed_at": fields.Datetime.now(),
                "changed_by_id": record.env.uid,
                "replacement_id": replacement.id,
            }
        )

    def _can_return_content(self, field_name=None, access_token=None):
        # The public controller is the only projection; even a field-scoped native
        # token must not expose audit reasons or other fields through /web/content.
        return False

    @api.private
    def _public_values(self, token):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return False
        # Capability lookup only: no numeric IDs, public ACL, PDF or related record returned.
        record = self.sudo().search([("token", "=", token)], limit=1)
        if not record:
            return False
        return {
            "issuer": record.issuer,
            "beneficiary": record.beneficiary,
            "reference": record.reference,
            "kind": record.kind,
            "programme": record.programme,
            "programme_version": record.programme_version,
            "issued_at": record.issued_at,
            "state": record.state,
            "sha256": record.sha256,
        }
