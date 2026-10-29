"""Individual generic notices through native mail.mail, checked again at transport."""

from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models


class LearningNotice(models.Model):
    _name = "training.learning.notice"
    _inherit = "training.learning.evidence"
    _description = "Learning Notification Journal"
    _order = "id desc"
    _rec_name = "event_kind"

    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="restrict", index=True)
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    entry_id = fields.Many2one("training.learning.entry", ondelete="restrict")
    event_key = fields.Char(required=True)
    event_kind = fields.Selection(
        [("entry", "Private Learning Update"), ("reminder", "Inactivity Reminder")],
        compute="_compute_event_kind",
        string="Notification",
    )

    @api.depends("entry_id")
    def _compute_event_kind(self):
        for notice in self:
            notice.event_kind = "entry" if notice.entry_id else "reminder"

    recipient_id = fields.Many2one("res.users", ondelete="restrict")
    recipient_email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict")
    distribution_state = fields.Selection(related="mail_id.state")
    not_queued_reason = fields.Char()
    _one_event = models.Constraint(
        "UNIQUE(enrollment_id, event_key)", "This learning notification is already journaled."
    )

    @api.private
    def _current_recipient(self):
        self.ensure_one()
        enrollment = self.enrollment_id
        if self.entry_id and self.entry_id.kind in ("submission", "question"):
            return enrollment.learning_tutor_id or enrollment.delivery_id.learning_tutor_id
        return enrollment.user_id

    @api.private
    def _authorized(self):
        self.ensure_one()
        recipient = self._current_recipient()
        if (
            not recipient
            or recipient != self.recipient_id
            or not recipient.active
            or recipient.partner_id.email != self.recipient_email
        ):
            return False
        service = self.env["training.learning.service"].with_user(recipient)
        if self.entry_id and self.entry_id.kind in ("submission", "question"):
            return (
                service._project_evaluator(self.enrollment_id)
                if self.entry_id.activity_id.project_rubric_id
                else service._is_tutor(self.enrollment_id)
            )
        if not service._is_participant(self.enrollment_id):
            return False
        if not self.entry_id:
            if not service._reminder_due(self.enrollment_id):
                return False
            last = service._last_activity(self.enrollment_id)
            delivery = self.enrollment_id.delivery_id
            first_due = last + timedelta(days=delivery.learning_inactivity_days)
            window = int(
                (fields.Datetime.now() - first_due).total_seconds() // (delivery.learning_reminder_days * 86400)
            )
            return self.event_key == "reminder:%s:%s" % (fields.Datetime.to_string(last), window)
        return True

    @api.private
    def _content(self):
        self.ensure_one()
        env = self.with_context(lang=self.recipient_language).env
        # No name, private title, correction, score or file in email or subject.
        subject = env._("Your training space needs attention")
        tutor = self.entry_id and self.entry_id.kind in ("submission", "question")
        path = "/my/training-tutoring/%s" if tutor else "/my/trainings/%s"
        url = self.enrollment_id.get_base_url() + path % self.enrollment_id.id
        body = Markup('<p>%s</p><p><a href="%s">%s</a></p>') % (
            env._("Sign in to your training space to view the current information."),
            url,
            env._("Open training space"),
        )
        return subject, body

    @api.private
    def _queue(self, enrollment, event_key, recipient, *, entry=None):
        # Caller holds the learning enrollment fence or the S03 delivery fence. No request context can
        # add attachments, CC, followers or different recipients to elevated mail.
        existing = self.sudo().search([("enrollment_id", "=", enrollment.id), ("event_key", "=", event_key)], limit=1)
        if existing:
            if existing.mail_id and existing.mail_id.state == "exception" and existing._authorized():
                existing.mail_id.sudo().write({"state": "outgoing"})
            return existing
        record = self._create_evidence(
            {
                "enrollment_id": enrollment.id,
                "event_key": event_key,
                "entry_id": entry.id if entry else False,
                "recipient_id": recipient.id,
                "recipient_language": (recipient.partner_id.lang if recipient else False)
                or self.env.lang
                or self.env.ref("base.lang_en").code,
                "recipient_email": recipient.partner_id.email if recipient else False,
            }
        )
        if not recipient or not record.recipient_email or not record._authorized():
            record._store_evidence(
                {"not_queued_reason": self.env._("No currently authorized recipient with an email address.")}
            )
            return record
        subject, body = record._content()
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        mail_model = self.env["mail.mail"].sudo().with_context(clean)  # pylint: disable=context-overridden  # discard caller defaults before whitelisted mail
        mail = mail_model.create(
            {
                "subject": subject,
                "body_html": body,
                "email_to": record.recipient_email,
                "email_from": enrollment.company_id.partner_id.email_formatted or self.env.user.email_formatted,
                **self.env["mail.mail"]._training_identity(enrollment.company_id),
                "email_cc": False,
                "recipient_ids": [],
                "recipient_cc_ids": [],
                "attachment_ids": [],
                "model": self._name,
                "res_id": record.id,
                "auto_delete": False,
            }
        )
        record._store_evidence({"mail_id": mail.id})
        return record
