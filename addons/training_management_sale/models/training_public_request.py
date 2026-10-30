"""Qualified requests on native CRM; public writes use a fixed private service."""

import hashlib
import json
from datetime import date

from psycopg2 import IntegrityError

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, ValidationError
from odoo.tools import email_normalize
from odoo.tools.binary import BinaryBytes


class TrainingPublicRequest(models.Model):
    _inherit = "crm.lead"  # pylint: disable=consider-merging-classes-inherited  # guided intake is separate from commercial qualification

    training_request_type = fields.Selection(
        [("catalogue", "Catalogue"), ("adaptation", "Adaptation"), ("custom", "Custom")]
    )
    training_objectives = fields.Text()
    training_level = fields.Char()
    training_tools = fields.Text()
    training_country_id = fields.Many2one("res.country", ondelete="restrict")
    training_advice_requested = fields.Boolean()
    training_submission_key = fields.Char(copy=False, readonly=True, index=True, groups="base.group_user")
    training_submission_hash = fields.Char(copy=False, readonly=True, groups="base.group_user")

    _unique_training_submission = models.Constraint(
        "UNIQUE(training_submission_key)", "This request was already recorded."
    )

    @api.private
    def _submit_public_request(self, company, values, key, file=None):
        # Only called after the controller verifies the session-bound nonce and
        # CSRF. No caller-selected model, company, partner, fields or recipients.
        self = (
            self.with_user(SUPERUSER_ID)
            .sudo()
            .with_company(company)
            .with_context(mail_create_nosubscribe=True, mail_create_nolog=True, lang=self.env.lang)
        )
        required = (
            "contact",
            "email",
            "kind",
            "request_type",
            "objectives",
            "level",
            "count",
            "country",
            "mode",
            "currency",
        )
        if any(not (values.get(k) or "").strip() for k in required):
            raise ValidationError(
                self.env._(
                    "Complete the contact, request type, objectives, level, participants, country, modality and currency."
                )
            )
        if any(len(str(v)) > 5000 for v in values.values()):
            raise ValidationError(self.env._("A request field exceeds 5000 characters."))
        email = email_normalize(values["email"])
        if not email:
            raise ValidationError(self.env._("Enter a valid email address."))
        kind, request_type = values["kind"], values["request_type"]
        if kind not in ("group", "individual") or request_type not in ("catalogue", "adaptation", "custom"):
            raise ValidationError(self.env._("Choose a valid training request type."))
        if kind == "group" and not values.get("organisation", "").strip():
            raise ValidationError(self.env._("Enter the organisation for an intra-company request."))
        try:
            count, country_id, program_id = (
                int(values["count"]),
                int(values["country"]),
                int(values.get("program") or 0),
            )
            start, end = (date.fromisoformat(values[k]) if values.get(k) else False for k in ("date_from", "date_to"))
        except (ValueError, TypeError):
            raise ValidationError(self.env._("Check the participant count, country, programme and dates.")) from None
        if count <= 0 or (kind == "individual" and count != 1) or (start and end and end < start):
            raise ValidationError(
                self.env._("Use a positive participant count (one for an individual) and ordered dates.")
            )
        if not start and not values.get("dates_flexible"):
            raise ValidationError(self.env._("Choose preferred dates or indicate that dates are to be discussed."))
        country = self.env["res.country"].browse(country_id).exists()
        currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", values["currency"]), ("active", "=", True)], limit=1)
        )
        if not country or not currency:
            raise ValidationError(self.env._("Choose a country and an active currency independently of the language."))
        if values["mode"] not in ("onsite", "remote", "blended", "elearning"):
            raise ValidationError(self.env._("Choose a valid delivery mode."))
        program = self.env["training.program.version"].browse(program_id).exists()
        if (
            program
            and (
                program.company_id != company
                or program.state != "published"
                or not program.public_catalogue
                or not program.course_id.active
            )
        ) or (not program and (program_id or request_type != "custom")):
            raise ValidationError(self.env._("Choose a published programme, or request custom training."))
        raw, filename = b"", ""
        if file and file.filename:
            raw, filename = file.read(10 * 1024 * 1024 + 1), file.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if not filename.lower().endswith(".pdf") or not raw.startswith(b"%PDF-") or len(raw) > 10 * 1024 * 1024:
                raise ValidationError(self.env._("The private specification must be a PDF of at most 10 MB."))
        fingerprint = hashlib.sha256(json.dumps(values, sort_keys=True).encode() + raw + filename.encode()).hexdigest()
        existing = self.search([("training_submission_key", "=", key)], limit=1)
        if existing:
            if existing.training_submission_hash != fingerprint:
                raise ValidationError(
                    self.env._("This form was already submitted with different content. Start a new request.")
                )
            return existing
        data = {
            "name": self.env._("Training request — %s", values["contact"]),
            "type": "lead",
            "user_id": False,
            "team_id": False,
            "company_id": company.id,
            "contact_name": values["contact"],
            "email_from": email,
            "partner_name": values.get("organisation"),
            "phone": values.get("phone"),
            "training_request_kind": kind,
            "training_program_id": program.id,
            "training_attendee_count": count,
            "training_requested_currency_id": currency.id,
            "training_delivery_mode": values["mode"],
            "training_date_from": start,
            "training_date_to": end,
            "training_request_type": request_type,
            "training_objectives": values["objectives"],
            "training_level": values["level"],
            "training_tools": values.get("tools"),
            "training_country_id": country.id,
            "training_advice_requested": bool(values.get("advice")),
            "training_submission_key": key,
            "training_submission_hash": fingerprint,
            "description": self.env._("Dates to discuss") if values.get("dates_flexible") else False,
        }
        try:
            with self.env.cr.savepoint():
                lead = self.create(data)
                if raw:
                    self.env["ir.attachment"].create(
                        {
                            "name": filename,
                            "raw": BinaryBytes(raw),
                            "mimetype": "application/pdf",
                            "res_model": "crm.lead",
                            "res_id": lead.id,
                            "company_id": company.id,
                            "public": False,
                            "access_token": False,
                        }
                    )
                return lead
        except IntegrityError as error:
            if error.diag.constraint_name == "crm_lead_unique_training_submission":
                # Native Odoo retry starts a fresh REPEATABLE READ transaction,
                # where the winning request is visible. Never return a stale read.
                raise ConcurrencyError("Concurrent training request; retry with a fresh snapshot") from error
            raise


class TrainingRequestPolicy(models.AbstractModel):
    _inherit = "training.document.policy"  # pylint: disable=consider-merging-classes-inherited  # intake files have no portal grant

    @api.private
    def _document(self, record):
        target = record.sudo()
        if target._name == "ir.attachment" and target.res_model == "crm.lead" and target.res_id:
            lead = self.env["crm.lead"].sudo().browse(target.res_id).exists()
            if lead.training_request_kind:
                return lead
        if target._name == "crm.lead" and target.training_request_kind:
            return target
        return super()._document(record)

    @api.private
    def _restricted(self, document):
        return bool(document) and document._name == "crm.lead" or super()._restricted(document)

    @api.private
    def _can_read(self, record):
        document = self._document(record)
        if document and document._name == "crm.lead":
            return not self.env.user.share and document.with_env(self.env(su=False)).has_access("read")
        return super()._can_read(record)

    @api.private
    def _partners(self, document, *, email_only=False):
        if document and document._name == "crm.lead":
            return self.env["res.partner"]
        return super()._partners(document, email_only=email_only)


class TrainingRequestAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.constrains("res_model", "res_id", "public", "access_token", "type", "url")
    def _check_training_request_private(self):
        for attachment in self:
            if attachment.res_model == "crm.lead" and attachment.res_id:
                lead = self.env["crm.lead"].sudo().browse(attachment.res_id).exists()
                if lead.training_request_kind and (
                    attachment.public or attachment.access_token or attachment.type != "binary"
                ):
                    raise ValidationError(
                        self.env._("Training request attachments must remain private without sharing tokens.")
                    )

    def write(self, vals):
        protected = self.sudo().filtered(
            lambda a: (
                a.res_model == "crm.lead"
                and a.res_id
                and self.env["crm.lead"].sudo().browse(a.res_id).exists().training_request_kind
            )
        )
        if protected and set(vals) & {
            "res_model",
            "res_id",
            "res_field",
            "company_id",
            "public",
            "access_token",
            "type",
            "url",
        }:
            raise AccessError(self.env._("A training specification cannot be shared or reassigned."))
        return super().write(vals)

    def _can_return_content(self, field_name=None, access_token=None):
        document = self.env["training.document.policy"]._document(self)
        if document and document._name == "crm.lead":
            self.env["training.document.policy"]._check_read(self)
        return super()._can_return_content(field_name, access_token)

    def copy_data(self, default=None):
        for attachment in self:
            document = self.env["training.document.policy"]._document(attachment)
            if document and document._name == "crm.lead":
                raise AccessError(self.env._("Private training specifications cannot be copied to another envelope."))
        return super().copy_data(default)
