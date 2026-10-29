"""Generic, append-only staff alerts with fresh source and recipient grants."""

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class OperatorNotice(models.Model):
    _name = "training.operator.notice"
    _inherit = "training.learning.evidence"
    _description = "Training Staff Alert Journal"
    _order = "id desc"

    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    source_model = fields.Char(required=True)
    source_id = fields.Integer(required=True)
    event_key = fields.Char(required=True)
    role = fields.Selection([("manager", "Manager"), ("trainer", "Assigned Trainer")], required=True)
    recipient_id = fields.Many2one("res.users", ondelete="restrict")
    email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict")
    distribution_state = fields.Selection(related="mail_id.state")
    failure = fields.Char()
    _one_alert = models.Constraint(
        "UNIQUE(company_id,source_model,source_id,event_key,role)", "This staff alert is already journaled."
    )

    @api.model
    def _source_models(self):
        return (
            "training.attendance.event",
            "training.complaint",
            "training.improvement",
            "training.notification",
            "training.invitation",
            "training.feedback.notice",
            "training.learning.notice",
            "training.practice.notice",
        )

    @api.private
    def _source(self):
        self.ensure_one()
        return (
            self.env[self.source_model].sudo().browse(self.source_id).exists()
            if self.source_model in self._source_models()
            else False
        )

    @api.private
    def _recipient(self, source, role):
        if role == "trainer" and source._name == "training.attendance.event":
            return source.attendance_id.session_id.instructor_id.user_ids.filtered(
                lambda user: user.active and not user._is_public() and source.company_id in user.company_ids
            )[:1]
        return source.company_id.sudo().training_notification_manager_id if role == "manager" else self.env["res.users"]

    @api.private
    def _authorized(self):
        self.ensure_one()
        source, user = self._source(), self.recipient_id
        if source and source._name == "training.learning.notice" and source.entry_id:
            return False
        if (
            not source
            or not user
            or not user.active
            or source.company_id != self.company_id
            or self.company_id not in user.company_ids
        ):
            return False
        if self._recipient(source, self.role) != user or self._recipient_email(source, self.role) != self.email:
            return False
        if (
            source._name
            in (
                "training.notification",
                "training.invitation",
                "training.feedback.notice",
                "training.learning.notice",
                "training.practice.notice",
            )
            and source.mail_id.state != "exception"
        ):
            return False
        if source._name in ("training.complaint", "training.improvement") and (
            source.state in source._terminal_states() or source.state == "resolved"
        ):
            return False
        if source._name == "training.attendance.event":
            presence = source.attendance_id
            if presence.revision != source.id or presence.session_id.delivery_id.state in ("closed", "cancelled"):
                return False
            if self.role == "trainer":
                if source.kind != "declaration":
                    return False
                try:
                    self.env["training.attendance.service"].with_user(user)._session(presence.session_id.id)
                except (AccessError, ValidationError):
                    return False
                return True
        return bool(
            self.role == "manager"
            and not user.share
            and user.has_group("training_management.group_training_coordinator")
            and source.with_user(user).has_access("read")
        )

    @api.private
    def _recipient_email(self, source, role):
        user = self._recipient(source, role)
        return (
            (source.company_id.sudo().training_alert_address or user.partner_id.email)
            if role == "manager"
            else user.partner_id.email
        )

    @api.private
    def _content(self):
        self.ensure_one()
        env = self.with_context(lang=self.recipient_language).env
        source = self._source()
        path = "/odoo"
        if self.role == "trainer" and source and source._name == "training.attendance.event":
            path = "/my/training-sessions/%s/attendance" % source.attendance_id.session_id.id
        return env._("A training action needs your attention"), Markup('<p>%s</p><p><a href="%s">%s</a></p>') % (
            env._("Sign in to review the information you are authorized to access."),
            self.company_id.get_base_url() + path,
            env._("Open training space"),
        )

    @api.private
    def _queue(self, source, key, role="manager"):
        source.ensure_one()
        if source._name not in self._source_models():
            raise ValidationError(self.env._("Unsupported staff alert source."))
        company = source.company_id
        if not company.sudo().training_notification_address:
            return self.browse()
        # Serialize only this trusted source; prevents duplicate concurrent queueing.
        source.sudo().lock_for_update()
        journal = self.sudo().search(
            [
                ("company_id", "=", company.id),
                ("source_model", "=", source._name),
                ("source_id", "=", source.id),
                ("event_key", "=", key),
                ("role", "=", role),
            ],
            limit=1,
        )
        if journal:
            if journal.mail_id.state == "exception" and journal._authorized():
                journal.mail_id.sudo().write({"state": "outgoing"})
            return journal
        user = self._recipient(source.sudo(), role)
        journal = self._create_evidence(
            {
                "company_id": company.id,
                "source_model": source._name,
                "source_id": source.id,
                "event_key": key,
                "role": role,
                "recipient_id": user.id,
                "email": self._recipient_email(source.sudo(), role),
                "recipient_language": user.lang or "en_US",
            }
        )
        if not journal.email or not journal._authorized():
            journal._store_evidence({"failure": self.env._("No authorized recipient with an email address.")})
            return journal
        subject, body = journal._content()
        mail = self.env["mail.mail"].sudo().with_context({})  # pylint: disable=context-overridden  # discard untrusted caller defaults
        queued = mail.create(
            {
                "subject": subject,
                "body_html": body,
                "email_to": journal.email,
                "email_cc": False,
                "recipient_ids": [],
                "recipient_cc_ids": [],
                "attachment_ids": [],
                "auto_delete": False,
                "model": self._name,
                "res_id": journal.id,
                **mail._training_identity(company),
            }
        )
        journal._store_evidence({"mail_id": queued.id})
        return journal


class AttendanceAlert(models.Model):
    _inherit = "training.attendance.event"

    @api.private
    def _append(self, values):
        event = super()._append(values)
        if event.kind == "declaration":
            self.env["training.operator.notice"]._queue(event, "review", "trainer")
        if event.anomaly or event.kind == "invalidation":
            self.env["training.operator.notice"]._queue(event, "attention")
        return event


class ComplaintAlert(models.Model):
    _inherit = "training.complaint"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            self.env["training.operator.notice"]._queue(record, "registered")
        return records


class ImprovementAlert(models.Model):
    _inherit = "training.improvement"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            self.env["training.operator.notice"]._queue(record, "registered")
        return records
