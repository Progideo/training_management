"""P14 explicit versioned consent, moderation and revocable public projections."""

import hashlib
import json
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

COORDINATOR = "training_management.group_training_coordinator"
MODERATOR = "training_management.group_training_publication_moderator"
CONTENT = {"name", "body", "public_context", "participation_month", "identify_client", "confidential"}
TARGET = {
    "kind",
    "delivery_id",
    "enrollment_id",
    "allocation_id",
    "representative_id",
    "authority_reference",
    "retention_id",
}
STATES = [
    ("draft", "Draft"),
    ("invited", "Invited"),
    ("submitted", "Awaiting Moderation or Authorization"),
    ("authorized", "Client Authorized"),
    ("published", "Published"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
]


class Testimonial(models.Model):
    _name = "training.publication"
    _description = "Verified Review or Customer Case"
    _check_company_auto = True
    _order = "id desc"

    name = fields.Char(required=True)
    kind = fields.Selection(
        [("review", "Participant Review"), ("case", "Customer Case")], required=True, default="review"
    )
    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    program_id = fields.Many2one(related="delivery_id.program_id", store=True)
    enrollment_id = fields.Many2one("training.enrollment", ondelete="restrict", check_company=True)
    allocation_id = fields.Many2one("training.seat.allocation", ondelete="restrict", check_company=True)
    customer_id = fields.Many2one(related="allocation_id.customer_id")
    representative_id = fields.Many2one("res.users", ondelete="restrict")
    authority_reference = fields.Text(help="Private reference establishing authority to authorize this customer case.")
    retention_id = fields.Many2one(
        "training.retention.category", required=True, ondelete="restrict", check_company=True
    )
    confidential = fields.Boolean(default=True)
    body = fields.Text()
    public_context = fields.Char()
    participation_month = fields.Char(help="Public month in YYYY-MM format; no private session name.")
    identify_client = fields.Boolean(string="Request Publication of Customer Name")
    identity_mode = fields.Selection([("anonymous", "Verified Participant"), ("name", "Consented Name")], readonly=True)
    public_identity = fields.Char(readonly=True, copy=False)
    owner_id = fields.Many2one("res.users", readonly=True, ondelete="restrict", copy=False)
    owner_partner_id = fields.Many2one("res.partner", readonly=True, ondelete="restrict", copy=False)
    state = fields.Selection(STATES, default="draft", required=True, readonly=True, copy=False)
    participation_snapshot = fields.Json(readonly=True, copy=False)
    consent_wording = fields.Text(readonly=True, copy=False)
    consented_at = fields.Datetime(readonly=True, copy=False)
    consented_by_id = fields.Many2one("res.users", readonly=True, ondelete="restrict", copy=False)
    identity_consented = fields.Boolean(readonly=True, copy=False)
    request_digest = fields.Char(readonly=True, copy=False)
    published_at = fields.Datetime(readonly=True, copy=False)
    moderated_by_id = fields.Many2one("res.users", readonly=True, ondelete="restrict", copy=False)
    moderation_reason = fields.Text(string="Moderation Decision Reason")
    event_ids = fields.One2many("training.publication.event", "publication_id", readonly=True)

    @api.private
    def _staff(self, *, moderator=False):
        user = self.env.user
        group = MODERATOR if moderator else COORDINATOR
        if not user.active or user._is_public() or not user.has_group(group):
            raise AccessError(self.env._("This publication action requires an explicitly authorized staff role."))
        self.with_env(self.env(su=False)).check_access("write" if self else "create")
        if self and self.company_id - self.env.companies:
            raise AccessError(self.env._("This publication is outside the allowed companies."))

    @api.private
    def _lock(self):
        # Caller has checked the exact staff/owner grant. Same company/delivery
        # lock order as S04/S07; shared fences serialize attendance corrections,
        # invitations, consent, moderation and withdrawal under REPEATABLE READ.
        self.ensure_one()
        self.company_id.sudo()._lock_training_schedule()
        self.delivery_id.sudo()._serialize()
        self.sudo().lock_for_update()
        self.invalidate_recordset()

    @api.private
    def _owner(self, *, grant=False, lock_grant=False):
        self.ensure_one()
        user = self.env.user
        if (
            not user.active
            or user._is_public()
            or self.company_id not in user.company_ids
            or self.owner_id != user
            or self.owner_partner_id != user.partner_id
        ):
            raise AccessError(self.env._("This private publication request is unavailable."))
        if grant:
            if self.kind == "review":
                if not self.env["training.learning.service"]._is_participant(self.enrollment_id.sudo()):
                    raise AccessError(self.env._("The participant training access is no longer active."))
            else:
                self._client_scope(user, lock=lock_grant)
        return True

    @api.private
    def _client_scope(self, user, *, lock=False):
        if lock:
            # P05 revocation locks its grant row. Lock the matching immutable
            # scope too so a stale snapshot cannot authorize a new case after
            # revocation. These locks follow the company/delivery/publication
            # locks and never grant access by themselves.
            grants = (
                self.env["training.company.authorization"]
                .sudo()
                .search(
                    [
                        ("user_id", "=", user.id),
                        ("company_id", "=", self.company_id.id),
                        ("customer_id", "=", self.customer_id.commercial_partner_id.id),
                        ("allocation_ids", "in", self.allocation_id.ids),
                    ]
                )
            )
            grants.sorted("id").lock_for_update()
            grants.invalidate_recordset()
        return self.env["training.company.service"].with_user(user)._allocation(self.allocation_id.id)

    @api.private
    def _attendance(self):
        attendance = self.env["training.attendance"].sudo().search([("enrollment_id", "=", self.enrollment_id.id)])
        retained = attendance.filtered(lambda a: a.state == "validated" and a.minutes > 0)
        return {
            "minutes": sum(retained.mapped("minutes")),
            "month": str(max(retained.mapped("session_id.start_date")))[:7] if retained else False,
            "evidence": [{"id": a.id, "revision": a.revision, "minutes": a.minutes} for a in retained.sorted("id")],
        }

    @api.private
    def _public_program(self):
        p = self.program_id.sudo()
        return p.state == "published" and p.public_catalogue and p.course_id.active

    @api.private
    def _valid_participation(self):
        facts = self._attendance()
        return facts["minutes"] > 0 and facts["month"] == self.participation_month

    @api.private
    def _terms(self):
        return self.env._(
            "I authorize public display of this exact text, training context and month on the training catalogue. "
            "Participation may be partial. This is separate from private satisfaction surveys. "
            "I may withdraw this authorization from this page. Copies made by third parties cannot be recalled."
        )

    @api.private
    def _definition(self):
        # Optimistic form binding, never an authorization token.
        data = {
            "id": self.id,
            "body": self.body,
            "context": self.public_context,
            "month": self.participation_month,
            "terms": self.consent_wording,
            "name": self.owner_partner_id.name if self.kind == "review" else self.public_identity,
            "identify_client": self.identify_client,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @api.private
    def _store(self, values, reason=""):
        # No caller controlled context defaults, mail thread or followers.
        super(Testimonial, self.sudo()).write(values)  # pylint: disable=super-method-mismatch
        self.env["training.publication.event"]._create_evidence(
            {
                "publication_id": self.id,
                "actor_id": self.env.uid,
                "occurred_at": fields.Datetime.now(),
                "state": self.state,
                "reason": reason,
                "snapshot": {
                    key: self[key]
                    for key in (
                        "body",
                        "public_context",
                        "participation_month",
                        "public_identity",
                        "identity_mode",
                        "consent_wording",
                        "identity_consented",
                        "request_digest",
                    )
                },
            }
        )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        self._staff()
        values = [self._add_missing_default_values(dict(v)) for v in vals_list]
        # A native form includes its empty editable moderation field when the
        # coordinator also holds the moderator role. Empty is not a decision;
        # a nonempty pre-seeded decision still fails the whitelist below.
        for value in values:
            if not value.get("moderation_reason"):
                value.pop("moderation_reason", None)
        if any(set(v) - (CONTENT | TARGET | {"state"}) or v.get("state") != "draft" for v in values):
            raise ValidationError(
                self.env._("Create a draft; consent and publication evidence are generated by the server.")
            )
        deliveries = self.env["training.delivery"].browse([v["delivery_id"] for v in values])
        deliveries.check_access("read")
        deliveries.company_id._lock_training_schedule()
        deliveries._serialize()
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        return super(Testimonial, self.with_context(clean)).create(values)  # pylint: disable=context-overridden

    @api.constrains("enrollment_id", "allocation_id", "representative_id", "delivery_id", "kind", "retention_id")
    def _check_target(self):
        for row in self:
            if row.kind == "review":
                valid = (
                    row.enrollment_id
                    and row.enrollment_id.delivery_id == row.delivery_id
                    and not row.allocation_id
                    and not row.representative_id
                )
            else:
                valid = (
                    row.allocation_id
                    and row.allocation_id.delivery_id == row.delivery_id
                    and row.representative_id
                    and not row.enrollment_id
                )
            if not valid or row.retention_id.company_id != row.company_id:
                raise ValidationError(
                    self.env._(
                        "Select an enrollment or a customer allocation from this delivery and its operator policy."
                    )
                )

    def write(self, vals):
        if set(vals) == {"moderation_reason"}:
            self._staff(moderator=True)
            self._lock()
            return super().write(vals)
        self._staff()
        self._lock()
        if any(r.state != "draft" for r in self) or set(vals) - CONTENT:
            raise ValidationError(
                self.env._("Keep invited or submitted versions unchanged; create a new draft for a new authorization.")
            )
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _keep_publication(self):
        raise ValidationError(self.env._("Keep publication requests and their authorization history."))

    def copy_data(self, default=None):  # pylint: disable=method-required-super
        raise ValidationError(self.env._("Create a new draft without copying consent or publication evidence."))

    def _export_rows(self, fields, *, _is_toplevel_call=True):  # pylint: disable=method-required-super
        self.with_env(self.env(su=False)).check_access("read")
        raise UserError(self.env._("Publication consent evidence is private and cannot be exported in bulk."))

    def _can_return_content(self, field_name=None, access_token=None):
        return False

    def action_request_authorization(self):
        self._staff()
        self._lock()
        if self.state in ("invited", "submitted", "authorized", "published"):
            return True
        if self.state != "draft" or not self.retention_id.approved_at or not self._public_program():
            raise ValidationError(
                self.env._("Use a draft, an approved retention policy and a currently public programme.")
            )
        if self.kind == "review":
            enrollment = self.enrollment_id.sudo()
            facts = self._attendance()
            owner = enrollment.user_id
            if (
                not facts["minutes"]
                or not owner
                or not self.env["training.learning.service"].with_user(owner)._is_participant(enrollment)
            ):
                raise ValidationError(
                    self.env._("An invitation requires positive validated attendance and active participant access.")
                )
            # One outstanding request per enrollment; explicit new intention is
            # possible after rejection/withdrawal, not after a repeated click.
            if self.sudo().search_count(
                [
                    ("enrollment_id", "=", enrollment.id),
                    ("state", "not in", ("draft", "rejected", "withdrawn")),
                    ("id", "!=", self.id),
                ]
            ):
                raise ValidationError(self.env._("This participant already has an outstanding publication request."))
            values = {
                "state": "invited",
                "owner_id": owner.id,
                "owner_partner_id": owner.partner_id.id,
                "public_context": self.program_id.title,
                "participation_month": facts["month"],
                "participation_snapshot": facts,
                "body": False,
                "confidential": False,
            }
        else:
            owner = self.representative_id
            self._client_scope(owner, lock=True)
            if (
                self.confidential
                or not (self.authority_reference or "").strip()
                or not (self.body or "").strip()
                or not (self.public_context or "").strip()
                or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", self.participation_month or "")
            ):
                raise ValidationError(
                    self.env._(
                        "Approve a non-confidential case with exact text, public context, month and representative authority."
                    )
                )
            values = {
                "state": "submitted",
                "owner_id": owner.id,
                "owner_partner_id": owner.partner_id.id,
                "public_identity": self.customer_id.commercial_partner_id.name if self.identify_client else False,
            }
        wording = self.with_context(lang=owner.partner_id.lang or self.env.lang)._terms()
        self._store(dict(values, consent_wording=wording), self.env._("Authorization requested"))
        self.env["training.publication.notice"]._queue_publication(self)
        return True

    @api.private
    def _consent(self, *, definition, body="", identity="anonymous", accepted=False, identity_accepted=False):
        self._owner(grant=True)
        self._lock()
        self._owner(grant=True, lock_grant=True)
        body = (body or "").strip()
        request_digest = hashlib.sha256(
            json.dumps([definition, body, identity, bool(accepted), bool(identity_accepted)]).encode()
        ).hexdigest()
        if self.state in ("submitted", "authorized", "published") and self.request_digest == request_digest:
            return self
        expected = "invited" if self.kind == "review" else "submitted"
        if self.state != expected or definition != self._definition() or not accepted:
            raise ValidationError(
                self.env._("Reload the exact publication preview and explicitly confirm its authorization.")
            )
        if identity not in ("anonymous", "name") or (identity == "name" and not identity_accepted):
            raise ValidationError(self.env._("Publication of a name requires its separate explicit consent."))
        values = {
            "consented_at": fields.Datetime.now(),
            "consented_by_id": self.env.uid,
            "request_digest": request_digest,
            "identity_consented": bool(identity_accepted),
        }
        if self.kind == "review":
            if not body or len(body) > 5000 or not self._valid_participation():
                raise ValidationError(
                    self.env._("Provide an opinion of at most 5000 characters with currently verified participation.")
                )
            values.update(
                state="submitted",
                body=body,
                identity_mode=identity,
                public_identity=self.owner_partner_id.name if identity == "name" else False,
                participation_snapshot=self._attendance(),
            )
        else:
            if body or (self.identify_client and (identity != "name" or not identity_accepted)):
                raise ValidationError(
                    self.env._("Authorize the exact customer case and separately authorize its requested company name.")
                )
            values.update(state="authorized", identity_mode="name" if self.identify_client else "anonymous")
        self._store(values, self.env._("Exact version authorized by its owner"))
        return self

    def action_publish(self):
        self._staff(moderator=True)
        self._lock()
        self._staff(moderator=True)
        if self.state == "published":
            return True
        expected = "submitted" if self.kind == "review" else "authorized"
        if (
            self.state != expected
            or not self.consented_at
            or not (self.moderation_reason or "").strip()
            or not self._public_program()
            or (self.public_identity and not self.identity_consented)
        ):
            raise ValidationError(
                self.env._("Publish only an authorized exact version with a recorded moderation decision.")
            )
        if self.kind == "review" and not self._valid_participation():
            raise ValidationError(self.env._("Participation must still be verified before publication."))
        if self.kind == "case":
            self._client_scope(self.owner_id, lock=True)
            if self.confidential:
                raise ValidationError(self.env._("A confidential customer case must remain private."))
        self._store(
            {"state": "published", "published_at": fields.Datetime.now(), "moderated_by_id": self.env.uid},
            self.moderation_reason,
        )
        return True

    def action_reject(self):
        self._staff(moderator=True)
        self._lock()
        if self.state == "rejected":
            return True
        if self.state not in ("submitted", "authorized") or not (self.moderation_reason or "").strip():
            raise ValidationError(self.env._("Record a reason to reject a submitted publication."))
        return self._store({"state": "rejected", "moderated_by_id": self.env.uid}, self.moderation_reason)

    @api.private
    def _withdraw(self):
        # Original consenting identity retains withdrawal after learning access
        # expires. This grants no new access to learning or company dossiers.
        self._owner()
        self._lock()
        self._owner()
        if self.state == "withdrawn":
            return self
        self._store({"state": "withdrawn"}, self.env._("Authorization withdrawn by its owner"))
        return self

    def action_withdraw(self):
        self._staff(moderator=True)
        self._lock()
        if self.state == "withdrawn":
            return True
        if not (self.moderation_reason or "").strip():
            raise ValidationError(self.env._("Record the reason for the publication withdrawal."))
        return self._store({"state": "withdrawn"}, self.moderation_reason)

    @api.private
    def _public_row(self):
        self.ensure_one()
        if (
            self.state != "published"
            or not self.consented_at
            or not self._public_program()
            or (self.public_identity and not self.identity_consented)
        ):
            return False
        if self.kind == "review" and not self._valid_participation():
            return False
        if self.kind == "case":
            if self.confidential:
                return False
            try:
                self.with_user(self.owner_id).sudo()._owner(grant=True)
            except AccessError:
                return False
        return {
            "kind": self.kind,
            "body": self.body,
            "context": self.public_context,
            "month": self.participation_month,
            "date": fields.Date.to_string(self.consented_at.date()),
            "identity": self.public_identity
            or (
                self.env._("Verified participant") if self.kind == "review" else self.env._("Authorized customer case")
            ),
        }


class PublicationEvent(models.Model):
    _name = "training.publication.event"
    _inherit = "training.learning.evidence"
    _description = "Private Publication Authorization History"
    _order = "id desc"

    publication_id = fields.Many2one("training.publication", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="publication_id.company_id", store=True)
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    occurred_at = fields.Datetime(required=True)
    state = fields.Selection(STATES, required=True)
    reason = fields.Text()
    snapshot = fields.Json(required=True)

    def _can_return_content(self, field_name=None, access_token=None):
        return False
