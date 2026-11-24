"""Explicit per-course opt-in, private evidence and single native date notices."""

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import SQL, consteq, email_normalize, email_split
from odoo.addons.training_catalog.models.training_deletion import require_evidence_deletion

from .training_mail_journal import mail_fingerprint

# A confirmation link received by email stays valid this long.
CONFIRMATION_DELAY = timedelta(days=7)
# Technical cleanup: a visitor request never confirmed is not a consent (22 November 2026).
UNCONFIRMED_LIFETIME = timedelta(days=60)
GC_LIMIT = 1000
# Confirmation emails: one per subscription within this delay, and a daily limit per address.
CONFIRMATION_THROTTLE = timedelta(minutes=15)
CONFIRMATIONS_PER_DAY = 5


class SessionAlertSubscription(models.Model):
    _name = "training.session.alert.subscription"
    _inherit = ["training.learning.evidence", "training.mail.journal"]
    _training_mail_template_xmlid = "training_management.mail_template_date_alert_confirmation"
    _description = "Voluntary New Session Date Subscription"
    _check_company_auto = True
    _rec_name = "course_id"

    course_id = fields.Many2one("training.course", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    # An account owns its subscription; a visitor subscribes with a confirmed email address.
    owner_id = fields.Many2one("res.users", ondelete="restrict")
    owner_partner_id = fields.Many2one("res.partner", ondelete="restrict")
    email = fields.Char(string="Email Address", help="Normalized address of a subscription without account.")
    language = fields.Char()
    access_token = fields.Char(groups="base.group_system", copy=False)
    confirmation_requested_at = fields.Datetime(readonly=True)
    confirmation_mail_id = fields.Many2one("mail.mail", ondelete="set null", readonly=True)
    # Historical only: retention is the operator's matter, outside the generic module (21 November 2026).
    retention_id = fields.Many2one("training.retention.category", ondelete="restrict", check_company=True)
    public_title = fields.Char(required=True)
    active_consent = fields.Boolean()
    subscribed_at = fields.Datetime(required=True)
    consent_wording = fields.Text(required=True)
    revision = fields.Integer(default=1)
    _unique_owner_course = models.Constraint(
        "UNIQUE(course_id, owner_id, company_id)", "A date subscription already exists for this account and course."
    )
    _unique_email_course = models.UniqueIndex(
        "(course_id, email, company_id) WHERE owner_id IS NULL",
        "A date subscription already exists for this address and course.",
    )
    _one_recipient = models.Constraint(
        "CHECK((owner_id IS NOT NULL AND owner_partner_id IS NOT NULL AND email IS NULL)"
        " OR (owner_id IS NULL AND owner_partner_id IS NULL AND email IS NOT NULL))",
        "A date subscription belongs either to an account or to an email address.",
    )

    @api.ondelete(at_uninstall=False)
    def _unlink_keep_evidence(self):
        # A visitor request never confirmed is technical data; every consent stays evidence,
        # deletable by an administrator only (conservation configurée).
        require_evidence_deletion(
            self - self._never_confirmed(), self.env._("Keep learning evidence and its history unchanged.")
        )

    @api.private
    def _never_confirmed(self):
        events = self.env["training.session.alert.event"].sudo().search([("subscription_id", "in", self.ids)])
        return self.filtered(lambda row: not row.owner_id and not row.active_consent) - events.subscription_id

    @api.autovacuum
    def _gc_unconfirmed_requests(self):
        self.env.flush_all()
        self.env.cr.execute(
            SQL(
                """SELECT s.id FROM training_session_alert_subscription s
                    WHERE s.owner_id IS NULL AND NOT COALESCE(s.active_consent, FALSE)
                      AND s.confirmation_requested_at < %s
                      AND NOT EXISTS (SELECT 1 FROM training_session_alert_event e WHERE e.subscription_id = s.id)
                    ORDER BY s.id LIMIT %s""",
                fields.Datetime.now() - UNCONFIRMED_LIFETIME,
                GC_LIMIT,
            )
        )
        stale = self.sudo().browse([row[0] for row in self.env.cr.fetchall()])
        stale.unlink()
        return len(stale), len(stale) == GC_LIMIT

    @api.private
    def _owner(self):
        self.ensure_one()
        user = self.env.user
        if not user.active or user._is_public() or self.owner_id != user or self.owner_partner_id != user.partner_id:
            raise AccessError(self.env._("This date subscription is unavailable."))

    @api.private
    def _wording(self):
        return self.env._(
            "I wish to receive an email when new dates are published for this training by this operator. I can unsubscribe from my account at any time. This does not enroll me in a session."
        )

    @api.private
    def _email_wording(self):
        return self.env._(
            "I wish to receive an email at this address when new dates are published for this training by this operator. I can unsubscribe from each email at any time. This does not enroll me in a session."
        )

    @api.private
    def _definition(self, program):
        wording = self._wording() if not self.env.user._is_public() else self._email_wording()
        return hashlib.sha256((str(program.id) + ":" + wording).encode()).hexdigest()

    @api.private
    def _subscribe(self, program, accepted=False, definition=None):
        user = self.env.user
        if not user.active or user._is_public() or program.company_id not in user.company_ids:
            raise AccessError(self.env._("Sign in with an account authorized for this operator."))
        address = user.partner_id.email or ""
        if len(email_split(address)) != 1 or not email_normalize(address):
            raise ValidationError(self.env._("Your account needs a single valid email address for date alerts."))
        if accepted is not True:
            raise ValidationError(self.env._("Explicitly accept the new date alerts."))
        with self.env.cr.savepoint():
            # Exact published programme selected by the route; never a caller domain.
            program.company_id.sudo()._lock_training_schedule()
            program.invalidate_recordset()
            if program.state != "published" or not program.public_catalogue or not program.course_id.active:
                raise ValidationError(self.env._("This programme is no longer public."))
            if definition != self._definition(program):
                raise ValidationError(self.env._("The date alert terms changed. Review and accept them again."))
            row = self.sudo().search(
                [
                    ("owner_id", "=", user.id),
                    ("company_id", "=", program.company_id.id),
                    ("course_id", "=", program.course_id.id),
                ],
                limit=1,
            )
            values = {
                "public_title": program.title,
                "active_consent": True,
                "subscribed_at": fields.Datetime.now(),
                "consent_wording": self._wording(),
            }
            if row:
                row._owner()
                if row.active_consent:
                    return row
                values["revision"] = row.revision + 1
                row._store_evidence(values)
            else:
                row = self._create_evidence(
                    {
                        **values,
                        "owner_id": user.id,
                        "owner_partner_id": user.partner_id.id,
                        "company_id": program.company_id.id,
                        "course_id": program.course_id.id,
                    }
                )
            row._event("subscribe")
            return row

    @api.private
    def _check_public_program(self, program, accepted, definition):
        """Common checks of an opt-in; the caller holds the company schedule fence."""
        if accepted is not True:
            raise ValidationError(self.env._("Explicitly accept the new date alerts."))
        program.invalidate_recordset()
        if program.state != "published" or not program.public_catalogue or not program.course_id.active:
            raise ValidationError(self.env._("This programme is no longer public."))
        if definition != self._definition(program):
            raise ValidationError(self.env._("The date alert terms changed. Review and accept them again."))
        return True

    @api.private
    def _request_by_email(self, program, email, accepted=False, definition=None):
        """Visitor opt-in: record the request and send a confirmation link (double opt-in).

        The answer never tells whether the address is already subscribed.
        """
        address = email_normalize(email or "")
        if not address or len(email_split(email or "")) != 1 or len(address) > 254:
            raise ValidationError(self.env._("Enter a valid email address."))
        with self.env.cr.savepoint():
            program.company_id.sudo()._lock_training_schedule()
            self._check_public_program(program, accepted, definition)
            now = fields.Datetime.now()
            model = self.sudo()
            row = model.search(
                [
                    ("owner_id", "=", False),
                    ("email", "=", address),
                    ("company_id", "=", program.company_id.id),
                    ("course_id", "=", program.course_id.id),
                ],
                limit=1,
            )
            if row.active_consent:
                return True
            if row.confirmation_requested_at and row.confirmation_requested_at > now - CONFIRMATION_THROTTLE:
                return True
            recent = model.search_count(
                [
                    ("owner_id", "=", False),
                    ("email", "=", address),
                    ("confirmation_requested_at", ">", now - timedelta(days=1)),
                ]
            )
            if recent >= CONFIRMATIONS_PER_DAY:
                return True
            values = {
                "public_title": program.title,
                "active_consent": False,
                "subscribed_at": now,
                "consent_wording": self._email_wording(),
                "access_token": secrets.token_urlsafe(32),
                "confirmation_requested_at": now,
                "language": self.env.lang or "en_US",
            }
            if row:
                row._store_evidence({**values, "revision": row.revision + 1})
            else:
                row = model._create_evidence(
                    {
                        **values,
                        "email": address,
                        "company_id": program.company_id.id,
                        "course_id": program.course_id.id,
                    }
                )
            row._queue_confirmation()
        return True

    @api.private
    def _queue_confirmation(self):
        self.ensure_one()
        mail = self._training_render_mail(self.email, self.company_id)
        self._store_evidence({"confirmation_mail_id": mail.id, "mail_fingerprint": mail_fingerprint(mail)})

    @api.private
    def _confirmation_authorized(self, mail):
        """Transport check: only the latest confirmation of a pending visitor request leaves."""
        self.ensure_one()
        return bool(
            not self.owner_id
            and not self.active_consent
            and self.confirmation_mail_id == mail
            and self.confirmation_requested_at
            and self.confirmation_requested_at > fields.Datetime.now() - CONFIRMATION_DELAY
            and mail.email_to == self.email
        )

    @api.model
    @api.private
    def _from_token(self, token):
        """The visitor subscription matching an emailed link, else an empty recordset."""
        if not token or not token.isascii() or len(token) > 64:
            return self.browse()
        row = self.sudo().search([("owner_id", "=", False), ("access_token", "=", token)], limit=1)
        return row if row and consteq(row.access_token or "", token) else self.browse()

    @api.private
    def _confirm_by_token(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            self.company_id.sudo()._lock_training_schedule()
            self.invalidate_recordset()
            if self.active_consent:
                return True
            if (
                not self.confirmation_requested_at
                or self.confirmation_requested_at <= fields.Datetime.now() - CONFIRMATION_DELAY
            ):
                raise ValidationError(self.env._("This confirmation link has expired. Ask for the alert again."))
            # Alerts follow the sessions first published after the confirmation.
            self._store_evidence(
                {"active_consent": True, "subscribed_at": fields.Datetime.now(), "revision": self.revision + 1}
            )
            self._event("subscribe")
        return True

    @api.private
    def _unsubscribe_by_token(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            self.company_id.sudo()._lock_training_schedule()
            self.invalidate_recordset()
            if self.active_consent:
                self._store_evidence({"active_consent": False, "revision": self.revision + 1})
                self._event("unsubscribe")
        return True

    @api.private
    def _unsubscribe(self):
        self._owner()
        with self.env.cr.savepoint():
            self.company_id.sudo()._lock_training_schedule()
            self.invalidate_recordset()
            self._owner()
            if self.active_consent:
                self._store_evidence({"active_consent": False, "revision": self.revision + 1})
                self._event("unsubscribe")
        return True

    @api.private
    def _event(self, operation):
        self.env["training.session.alert.event"]._create_evidence(
            {
                "subscription_id": self.id,
                "company_id": self.company_id.id,
                "actor_id": self.env.uid,
                "operation": operation,
                "occurred_at": fields.Datetime.now(),
                "wording": self.consent_wording,
                "retention_id": self.retention_id.id,
                "revision": self.revision,
            }
        )


class SessionAlertEvent(models.Model):
    _name = "training.session.alert.event"
    _inherit = "training.learning.evidence"
    _description = "Date Alert Consent Evidence"

    subscription_id = fields.Many2one("training.session.alert.subscription", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    operation = fields.Selection([("subscribe", "Subscribe"), ("unsubscribe", "Unsubscribe")], required=True)
    occurred_at = fields.Datetime(required=True)
    wording = fields.Text(required=True)
    retention_id = fields.Many2one("training.retention.category", ondelete="restrict")  # historical only
    revision = fields.Integer(required=True)
    _once = models.Constraint("UNIQUE(subscription_id, revision)", "This consent transition is already recorded.")


class SessionAlertNotice(models.Model):
    _name = "training.session.alert.notice"
    _inherit = ["training.learning.evidence", "training.mail.journal"]
    _training_mail_template_xmlid = "training_management.mail_template_date_alert_notice"
    _description = "New Session Date Notification Journal"

    subscription_id = fields.Many2one("training.session.alert.subscription", required=True, ondelete="restrict")
    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    subscription_revision = fields.Integer(required=True)
    recipient_id = fields.Many2one("res.users", ondelete="restrict")
    recipient_email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="set null")
    distribution_state = fields.Selection(related="mail_id.state")
    not_queued_reason = fields.Char()
    _once = models.Constraint("UNIQUE(subscription_id, delivery_id)", "This date alert is already journaled.")

    @api.private
    def _authorized(self):
        self.ensure_one()
        sub, delivery, user = self.subscription_id, self.delivery_id, self.recipient_id
        if not sub.owner_id:
            # Subscription without account: the confirmed address of the request only.
            return bool(
                sub.active_consent
                and sub.revision == self.subscription_revision
                and not user
                and self.recipient_email
                and self.recipient_email == sub.email
                and email_normalize(self.recipient_email) == self.recipient_email
                and sub.company_id == delivery.company_id
                and sub.course_id == delivery.program_id.course_id
                and sub.subscribed_at <= delivery.session_first_published_at
                and delivery._session_public_row()
            )
        return bool(
            sub.active_consent
            and sub.revision == self.subscription_revision
            and user.active
            and not user._is_public()
            and sub.owner_id == user
            and sub.owner_partner_id == user.partner_id
            and self.company_id in user.company_ids
            and user.partner_id.email == self.recipient_email
            and self.recipient_email
            and len(email_split(self.recipient_email)) == 1
            and email_normalize(self.recipient_email)
            and sub.company_id == delivery.company_id
            and sub.course_id == delivery.program_id.course_id
            and sub.subscribed_at <= delivery.session_first_published_at
            and delivery._session_public_row()
        )

    @api.private
    def training_mail_manage_url(self):
        """Link of the alert email to manage or stop date alerts."""
        return self._manage_url()

    @api.private
    def _manage_url(self):
        self.ensure_one()
        base = self.delivery_id.get_base_url()
        sub = self.subscription_id.sudo()
        if sub.owner_id:
            return base + "/my/training-date-alerts"
        return base + "/formations/date-alert/unsubscribe/%s" % sub.access_token

    @api.private
    def _queue_session(self, delivery):
        # Caller holds company then delivery fences; this first-publication event
        # never sweeps historical dates during a subscription or resubscription.
        subscriptions = (
            self.env["training.session.alert.subscription"]
            .sudo()
            .search(
                [
                    ("company_id", "=", delivery.company_id.id),
                    ("course_id", "=", delivery.program_id.course_id.id),
                    ("active_consent", "=", True),
                    ("subscribed_at", "<=", delivery.session_first_published_at),
                ]
            )
        )
        for sub in subscriptions:
            if self.sudo().search_count([("subscription_id", "=", sub.id), ("delivery_id", "=", delivery.id)]):
                continue
            user = sub.owner_id
            row = self._create_evidence(
                {
                    "subscription_id": sub.id,
                    "subscription_revision": sub.revision,
                    "delivery_id": delivery.id,
                    "recipient_id": user.id,
                    "recipient_email": user.partner_id.email if user else sub.email,
                    "recipient_language": (user.partner_id.lang if user else sub.language) or "en_US",
                }
            )
            if not row._authorized():
                row._store_evidence(
                    {"not_queued_reason": self.env._("No currently authorized recipient with an email address.")}
                )
                continue
            mail = row._training_render_mail(
                row.recipient_email,
                delivery.company_id,
                email_from=delivery.company_id.partner_id.email_formatted or self.env.user.email_formatted,
            )
            row._store_evidence({"mail_id": mail.id, "mail_fingerprint": mail_fingerprint(mail)})
