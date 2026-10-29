"""Explicit per-course opt-in, private evidence and single native date notices."""

import hashlib

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SessionAlertCompany(models.Model):
    _inherit = "res.company"  # pylint: disable=consider-merging-classes-inherited

    training_session_alert_retention_id = fields.Many2one(
        "training.retention.category",
        string="Date Alert Retention Policy",
        groups="base.group_system",
        ondelete="restrict",
        copy=False,
    )

    @api.constrains("training_session_alert_retention_id")
    def _check_session_alert_policy(self):
        for company in self:
            policy = company.training_session_alert_retention_id
            if policy and (policy.company_id != company or not policy.approved_at):
                raise ValidationError(self.env._("Choose an approved retention policy of this operator company."))


class SessionAlertSubscription(models.Model):
    _name = "training.session.alert.subscription"
    _inherit = "training.learning.evidence"
    _description = "Voluntary New Session Date Subscription"
    _check_company_auto = True
    _rec_name = "course_id"

    course_id = fields.Many2one("training.course", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    owner_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    owner_partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    retention_id = fields.Many2one(
        "training.retention.category", required=True, ondelete="restrict", check_company=True
    )
    public_title = fields.Char(required=True)
    active_consent = fields.Boolean()
    subscribed_at = fields.Datetime(required=True)
    consent_wording = fields.Text(required=True)
    revision = fields.Integer(default=1)
    _unique_owner_course = models.Constraint(
        "UNIQUE(course_id, owner_id, company_id)", "A date subscription already exists for this account and course."
    )

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
    def _definition(self, program):
        policy = program.company_id.sudo().training_session_alert_retention_id
        return hashlib.sha256((str(program.id) + ":" + str(policy.id) + ":" + self._wording()).encode()).hexdigest()

    @api.private
    def _subscribe(self, program, accepted=False, definition=None):
        user = self.env.user
        if not user.active or user._is_public() or program.company_id not in user.company_ids:
            raise AccessError(self.env._("Sign in with an account authorized for this operator."))
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
            policy = program.company_id.sudo().training_session_alert_retention_id
            if not policy or not policy.approved_at or policy.company_id != program.company_id:
                raise ValidationError(self.env._("Date alerts require an approved retention policy."))
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
                "retention_id": policy.id,
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
    retention_id = fields.Many2one("training.retention.category", required=True, ondelete="restrict")
    revision = fields.Integer(required=True)
    _once = models.Constraint("UNIQUE(subscription_id, revision)", "This consent transition is already recorded.")


class SessionAlertNotice(models.Model):
    _name = "training.session.alert.notice"
    _inherit = "training.learning.evidence"
    _description = "New Session Date Notification Journal"

    subscription_id = fields.Many2one("training.session.alert.subscription", required=True, ondelete="restrict")
    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    subscription_revision = fields.Integer(required=True)
    recipient_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    recipient_email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict")
    distribution_state = fields.Selection(related="mail_id.state")
    not_queued_reason = fields.Char()
    _once = models.Constraint("UNIQUE(subscription_id, delivery_id)", "This date alert is already journaled.")

    @api.private
    def _authorized(self):
        self.ensure_one()
        sub, delivery, user = self.subscription_id, self.delivery_id, self.recipient_id
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
            and sub.company_id == delivery.company_id
            and sub.course_id == delivery.program_id.course_id
            and sub.subscribed_at <= delivery.session_first_published_at
            and delivery._session_public_row()
        )

    @api.private
    def _content(self):
        env = self.with_context(lang=self.recipient_language).env
        return env._("New training session dates are available"), Markup(
            '<p>%s</p><p><a href="%s">%s</a></p><p><a href="%s">%s</a></p>'
        ) % (
            env._(
                "New session dates have been published for a training you follow. Consult the current public information before requesting a place."
            ),
            self.delivery_id.get_base_url() + "/formations/%s/sessions" % self.delivery_id.program_id.id,
            env._("View session dates"),
            self.delivery_id.get_base_url() + "/my/training-date-alerts",
            env._("Manage or unsubscribe from date alerts"),
        )

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
                    "recipient_email": user.partner_id.email,
                    "recipient_language": user.partner_id.lang or "en_US",
                }
            )
            if not row._authorized():
                row._store_evidence(
                    {"not_queued_reason": self.env._("No currently authorized recipient with an email address.")}
                )
                continue
            subject, body = row._content()
            clean = {key: value for key, value in self.env.context.items() if not key.startswith("default_")}
            mail = (
                self.env["mail.mail"]
                .sudo()
                .with_context(**clean)
                .create(
                    {
                        "subject": subject,
                        "body_html": body,
                        "email_to": row.recipient_email,
                        "email_from": delivery.company_id.partner_id.email_formatted or self.env.user.email_formatted,
                        **self.env["mail.mail"]._training_identity(delivery.company_id),
                        "email_cc": False,
                        "recipient_ids": [],
                        "recipient_cc_ids": [],
                        "attachment_ids": [],
                        "model": self._name,
                        "res_id": row.id,
                        "auto_delete": False,
                    }
                )
            )  # pylint: disable=context-overridden  # discard untrusted mail defaults
            row._store_evidence({"mail_id": mail.id})
