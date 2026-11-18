"""One native queued confirmation per CRM request and normalized address."""

import hashlib
import json

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import clean_context, email_normalize, format_datetime


class SessionConfirmationNotice(models.Model):
    _name = "training.session.confirmation.notice"
    _inherit = "training.learning.evidence"
    _description = "Session Registration Confirmation Email"
    _order = "id desc"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    email = fields.Char(required=True)
    participant_ids = fields.Many2many("res.partner", string="Participants", readonly=True)
    is_requester = fields.Boolean(string="Requester", readonly=True)
    recipient_language = fields.Char(required=True)
    session_fingerprint = fields.Char(required=True)
    details_html = fields.Html(string="Session Information", readonly=True, sanitize=True)
    mail_id = fields.Many2one("mail.mail", ondelete="restrict", readonly=True)
    distribution_state = fields.Selection(related="mail_id.state")

    _one_address = models.Constraint(
        "UNIQUE(lead_id, email)", "This session confirmation is already prepared for this address."
    )

    @api.private
    def _schedule(self, lead):
        delivery = lead.training_requested_delivery_id
        sessions = delivery.session_ids.filtered(lambda session: not session.cancelled).sorted("start_at")
        return {
            "course": lead.training_requested_course_id.name,
            "course_id": lead.training_requested_course_id.id,
            "start": delivery.start_at,
            "end": delivery.end_at,
            "timezone": delivery.timezone,
            "mode": delivery.delivery_mode,
            "sessions": [
                {
                    "start": session.start_at,
                    "end": session.end_at,
                    "mode": session.mode,
                    "location": session.location or session.room_id.name or "",
                    "meeting_url": session.meeting_url or "",
                }
                for session in sessions
            ],
        }

    @api.private
    def _fingerprint(self, schedule):
        stable = {key: value for key, value in schedule.items() if key != "course"}
        return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()

    @api.private
    def _details(self, schedule, lang):
        env = self.with_context(lang=lang).env
        zone = schedule["timezone"]
        modes = dict(self.env["training.program.version"]._fields["delivery_mode"]._description_selection(env))

        def dates(instant):
            return format_datetime(env, instant, tz=zone, dt_format="d MMMM y HH:mm XXX")

        body = Markup("<p><strong>%s</strong></p><p>%s — %s (%s)</p><p>%s</p>") % (
            schedule["course"],
            dates(schedule["start"]),
            dates(schedule["end"]),
            zone,
            modes.get(schedule["mode"], schedule["mode"]),
        )
        for session in schedule["sessions"]:
            body += Markup("<p>%s — %s</p>") % (dates(session["start"]), dates(session["end"]))
            if session["location"]:
                body += Markup("<p>%s</p>") % session["location"]
            if session["meeting_url"]:
                body += Markup('<p><a href="%s">%s</a></p>') % (
                    session["meeting_url"],
                    env._("Join the remote session"),
                )
        if not schedule["sessions"] or not any(
            session["location"] or session["meeting_url"] for session in schedule["sessions"]
        ):
            body += Markup("<p>%s</p>") % env._("Practical access information will be provided before the session.")
        return body

    @api.private
    def _recipients(self, lead):
        enrollments = lead.training_session_enrollment_ids
        recipients = {}
        requester = email_normalize(lead.email_from)
        if not requester:
            raise ValidationError(self.env._("Enter a valid email address for the requester."))
        recipients[requester] = {
            "is_requester": True,
            "participants": self.env["res.partner"],
            "lang": lead.partner_id.lang or self.env.lang or "en_US",
        }
        for person in enrollments.participant_id:
            email = email_normalize(person.email)
            if not email:
                raise ValidationError(self.env._("Enter a valid email address for every participant."))
            row = recipients.setdefault(
                email,
                {
                    "is_requester": False,
                    "participants": self.env["res.partner"],
                    "lang": person.lang or self.env.lang or "en_US",
                },
            )
            row["participants"] |= person
        return recipients

    @api.private
    def _queue(self, lead):
        delivery = lead._check_session_confirmation_access()
        lead.lock_for_update()
        if not lead.training_session_enrollment_ids or any(
            enrollment.state != "confirmed" for enrollment in lead.training_session_enrollment_ids
        ):
            raise ValidationError(self.env._("Confirm the participants before preparing the confirmation emails."))
        delivery.check_access("read")
        schedule = self._schedule(lead)
        recipients = self._recipients(lead)
        template = self.env.ref("training_management_sale.mail_template_session_confirmation")
        for email, values in recipients.items():
            if self.sudo().search_count([("lead_id", "=", lead.id), ("email", "=", email)]):
                continue
            notice = self._create_evidence(
                {
                    "lead_id": lead.id,
                    "company_id": lead.company_id.id,
                    "email": email,
                    "is_requester": values["is_requester"],
                    "participant_ids": [Command.set(values["participants"].ids)],
                    "recipient_language": values["lang"],
                    "session_fingerprint": self._fingerprint(schedule),
                    "details_html": self._details(schedule, values["lang"]),
                }
            )
            # Native template and queue only. No template-selected recipients,
            # followers, reports or caller-supplied defaults reach the envelope.
            outgoing_template = template.sudo().with_context(clean_context(self.env.context))
            mail_id = outgoing_template.send_mail(
                notice.id,
                force_send=False,
                email_values={
                    "email_to": email,
                    "email_cc": False,
                    "recipient_ids": [Command.clear()],
                    "attachment_ids": [Command.clear()],
                    "auto_delete": False,
                    **self.env["mail.mail"]._training_identity(lead.company_id),
                },
            )
            notice._store_evidence({"mail_id": mail_id})
        return True

    @api.private
    def _authorized(self):
        self.ensure_one()
        lead = self.lead_id
        enrollments = lead.training_session_enrollment_ids
        if (
            not lead.active
            or lead.company_id != self.company_id
            or not enrollments
            or any(item.state != "confirmed" for item in enrollments)
            or lead.training_requested_delivery_id.state in ("cancelled", "closed", "delivered")
            or self.session_fingerprint != self._fingerprint(self._schedule(lead))
        ):
            return False
        if self.is_requester and email_normalize(lead.email_from) != self.email:
            return False
        return all(
            person in enrollments.participant_id and person.active and email_normalize(person.email) == self.email
            for person in self.participant_ids
        ) and bool(self.is_requester or self.participant_ids)


class Mail(models.Model):
    _inherit = "mail.mail"  # pylint: disable=consider-merging-classes-inherited

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        if self.model == "training.session.confirmation.notice":
            notice = self.env[self.model].sudo().search([("mail_id", "=", self.id)], limit=1)
            if (
                not notice
                or not notice._authorized()
                or self.email_to != notice.email
                or self.email_cc
                or self.recipient_ids
                or self.recipient_cc_ids
                or self.attachment_ids
            ):
                raise ValidationError(
                    self.env._("This session confirmation is no longer authorized for this recipient.")
                )
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
