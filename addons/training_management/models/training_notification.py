"""Missing lifecycle notices; existing S04/S05/S09 journals remain their sources."""

from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models


class TrainingNotification(models.Model):
    _name = "training.notification"
    _inherit = "training.learning.evidence"
    _description = "Training Lifecycle Notification Journal"
    _order = "id desc"

    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="restrict")
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    event_key = fields.Char(required=True)
    kind = fields.Selection(
        [
            ("request", "Enrollment Request Received"),
            ("confirmation", "Enrollment Confirmed"),
            ("evaluation", "Evaluation Invitation"),
            ("deadline", "Evaluation Deadline"),
            ("document", "Certificate Available"),
            ("access", "Learning Access Changed"),
            ("change", "Enrollment Changed"),
        ],
        required=True,
    )
    assignment_id = fields.Many2one("training.evaluation.assignment", ondelete="restrict")
    document_id = fields.Many2one("training.document", ondelete="restrict")
    recipient_id = fields.Many2one("res.users", ondelete="restrict")
    email = fields.Char()
    recipient_language = fields.Char(required=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict")
    distribution_state = fields.Selection(related="mail_id.state")
    failure = fields.Char()
    template_version = fields.Char(default="S10-LIFECYCLE-1", required=True)
    _one_event = models.Constraint("UNIQUE(enrollment_id,event_key)", "This lifecycle event is already journaled.")

    @api.private
    def _authorized(self):
        self.ensure_one()
        user = self.recipient_id
        enrollment = self.enrollment_id
        if (
            not user.active
            or user._is_public()
            or enrollment.user_id != user
            or user.partner_id != enrollment.participant_id
            or enrollment.company_id not in user.company_ids
            or user.partner_id.email != self.email
        ):
            return False
        if self.kind == "document":
            return bool(
                self.document_id and self.env["training.document.policy"].with_user(user)._can_read(self.document_id)
            )
        if self.kind in ("access", "change"):
            return True
        if enrollment.state not in ("requested", "reserved", "waiting", "confirmed", "closed"):
            return False
        if self.assignment_id:
            return (
                enrollment.state == "confirmed"
                and self.assignment_id.enrollment_id == enrollment
                and self.assignment_id.state != "validated"
                and self.event_key.endswith(fields.Datetime.to_string(self.assignment_id.due_at))
            )
        return True

    @api.private
    def _content(self):
        self.ensure_one()
        env = self.with_context(lang=self.recipient_language).env
        subject = env._("Your training space has been updated")
        body = Markup('<p>%s</p><p><a href="%s/my/home">%s</a></p>') % (
            env._("Sign in to view your enrollment, evaluation deadlines or available documents."),
            self.enrollment_id.get_base_url(),
            env._("Open my training space"),
        )
        return subject, body

    @api.private
    def _queue(self, enrollment, kind, key, *, assignment=None, document=None):
        # Trusted lifecycle callers hold the delivery fence. A replay reuses the
        # existing journal and queued mail; it never recreates a sent message.
        # The lifecycle hook already authorized its source (including assigned quality).
        # Elevation is limited to the common write fence, never to recipient eligibility.
        enrollment.delivery_id.sudo()._serialize()
        existing = self.sudo().search([("enrollment_id", "=", enrollment.id), ("event_key", "=", key)], limit=1)
        if existing:
            if existing.mail_id.state == "exception" and existing._authorized():
                existing.mail_id.sudo().write({"state": "outgoing"})
            return existing
        user = enrollment.user_id
        notice = self._create_evidence(
            {
                "enrollment_id": enrollment.id,
                "event_key": key,
                "kind": kind,
                "assignment_id": assignment.id if assignment else False,
                "document_id": document.id if document else False,
                "recipient_id": user.id,
                "email": user.partner_id.email,
                "recipient_language": user.lang or "en_US",
            }
        )
        if not notice.email or not notice._authorized():
            notice._store_evidence({"failure": self.env._("No authorized recipient with an email address.")})
            return notice
        subject, body = notice._content()
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        mail = (
            self.env["mail.mail"]  # pylint: disable=context-overridden  # replace caller context before elevated mail
            .sudo()
            .with_context(clean)  # pylint: disable=context-overridden  # discard caller defaults before elevated mail
            .create(
                {  # pylint: disable=context-overridden
                    "subject": subject,
                    "body_html": body,
                    "email_to": notice.email,
                    "email_cc": False,
                    "recipient_ids": [],
                    "recipient_cc_ids": [],
                    "attachment_ids": [],
                    "email_from": enrollment.company_id.partner_id.email_formatted or self.env.user.email_formatted,
                    **self.env["mail.mail"]._training_identity(enrollment.company_id),
                    "model": self._name,
                    "res_id": notice.id,
                    "auto_delete": False,
                }
            )
        )
        notice._store_evidence({"mail_id": mail.id})
        return notice

    @api.model
    def _cron_deadlines(self):
        now = fields.Datetime.now()
        assignments = self.env["training.evaluation.assignment"].search(
            [("due_at", "<=", now + timedelta(days=1)), ("enrollment_id.state", "=", "confirmed")]
        )
        for assignment in assignments.filtered(lambda a: a.state != "validated"):
            self._queue(
                assignment.enrollment_id,
                "deadline",
                "deadline:%s:%s" % (assignment.id, fields.Datetime.to_string(assignment.due_at)),
                assignment=assignment,
            )


class NotificationEnrollment(models.Model):
    # Keep lifecycle hooks separate from learning access policies.
    _inherit = "training.enrollment"  # pylint: disable=consider-merging-classes-inherited

    @api.model_create_multi
    def create(self, vals_list):
        rows = super().create(vals_list)
        for row in rows:
            self.env["training.notification"]._queue(row, "request", "request")
        return rows

    @api.private
    def _store(self, values, reason=False):
        previous = self.state
        changed = any(
            self[name] != values[name]
            for name in ("access_state", "access_start", "access_end", "state")
            if name in values
        )
        result = super()._store(values, reason)
        if values.get("state") == "confirmed" and previous != "confirmed":
            self.env["training.notification"]._queue(self, "confirmation", "confirmation")
        if changed and self.company_id.sudo().training_notification_address:
            kind = "change" if values.get("state") and values["state"] != previous else "access"
            if kind == "access" or values.get("state") != "confirmed":
                operation = (
                    self.env["training.operation"]
                    .sudo()
                    .search(
                        [
                            ("model_name", "=", self._name),
                            ("record_id", "=", self.id),
                            ("delivery_id", "=", self.delivery_id.id),
                        ],
                        order="id desc",
                        limit=1,
                    )
                )
                self.env["training.notification"]._queue(self, kind, "%s:%s" % (kind, operation.id))
        return result


class NotificationEvaluation(models.Model):
    _inherit = "training.evaluation.assignment"

    @api.model_create_multi
    def create(self, vals_list):
        assignments = super().create(vals_list)
        for assignment in assignments:
            self.env["training.notification"]._queue(
                assignment.enrollment_id,
                "evaluation",
                "evaluation:%s:%s" % (assignment.id, fields.Datetime.to_string(assignment.due_at)),
                assignment=assignment,
            )
        return assignments


class NotificationDocument(models.Model):
    _inherit = "training.document"

    @api.private
    def _append(self, values):
        document = super()._append(values)
        if document.kind in ("participation", "completion", "achievement"):
            self.env["training.notification"]._queue(
                document.dossier_id.enrollment_id, "document", "document:%s" % document.id, document=document
            )
        return document
