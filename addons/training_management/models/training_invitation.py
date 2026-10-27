"""Explicit, individual, idempotent invitations through Odoo's mail queue."""

import hashlib
import json

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import format_datetime


class TrainingInvitation(models.Model):
    _name = "training.invitation"
    _description = "Training Invitation Distribution"
    _order = "id desc"

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    session_id = fields.Many2one("training.session", required=True, ondelete="restrict")
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    fingerprint = fields.Char(required=True)
    dispatch_number = fields.Integer(required=True, default=1)
    mail_id = fields.Many2one("mail.mail", required=True, ondelete="restrict")
    distribution_state = fields.Selection(related="mail_id.state")
    requested_by_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    requested_at = fields.Datetime(required=True)
    recipient_timezone = fields.Char(required=True)

    _unique_dispatch = models.Constraint(
        "UNIQUE(session_id, partner_id, dispatch_number)", "This invitation is already queued."
    )

    @api.private
    def _fingerprint(self, session, partner):
        data = {
            key: session[key]
            for key in ("name", "start_at", "end_at", "location", "meeting_url", "cancelled", "timezone", "mode")
        }
        data.update(
            instructor=session.instructor_id.name,
            room=session.room_id.name,
            recipient_email=partner.email,
            recipient_timezone=partner.tz or session.timezone,
            recipient_language=partner.lang,
        )
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    @api.private
    def _recipients(self, delivery):
        delivery._require_coordinator()
        participants = delivery.enrollment_ids.filtered(lambda item: item.state == "confirmed").participant_id
        return participants | delivery.session_ids.instructor_id

    @api.private
    def _queue(self, delivery, recipients):
        delivery.ensure_one()
        delivery._require_coordinator()
        delivery.company_id._lock_training_schedule()
        delivery._serialize()
        if delivery.state != "confirmed":
            raise ValidationError(
                self.env._("Confirm the delivery and its complete schedule before sending invitations.")
            )
        sessions = delivery.session_ids.filtered(lambda item: not item.cancelled)
        sessions._reserve() if not any(session._conflicts() for session in sessions) else sessions._check_definition()
        if not recipients or recipients - self._recipients(delivery):
            raise AccessError(self.env._("Select only confirmed participants and assigned instructors."))
        if any(not partner.email for partner in recipients):
            raise ValidationError(self.env._("Every selected recipient needs an email address."))
        all_sessions = delivery.session_ids
        if not all_sessions:
            raise ValidationError(self.env._("There are no sessions to invite recipients to."))
        count = 0
        # Never carry RPC default_* values into elevated mail creation: in
        # particular no default_attachment_ids, CC, followers or mail server.
        clean_context = {key: value for key, value in self.env.context.items() if not key.startswith("default_")}
        outgoing = self.env["mail.mail"].sudo().with_context(clean_context)  # pylint: disable=context-overridden  # deliberately discard untrusted defaults
        for session in all_sessions:
            participants = delivery.enrollment_ids.filtered(lambda item: item.state == "confirmed").participant_id
            for partner in recipients & (participants | session.instructor_id):
                previous = self.search([("session_id", "=", session.id), ("partner_id", "=", partner.id)])
                if session.cancelled and not previous:
                    continue
                tz = partner.tz or session.timezone
                fingerprint = self._fingerprint(session, partner)
                # Idempotence applies to the latest dispatch, not every past
                # schedule: A -> B -> A is a new change that must be notified.
                existing = previous[:1].filtered(lambda item: item.fingerprint == fingerprint)
                if existing:
                    # Retry the same queued item rather than create a duplicate.
                    if existing.mail_id.state == "exception":
                        existing.mail_id.sudo().write({"state": "outgoing"})
                    continue
                localized = session.with_context(lang=partner.lang or self.env.lang)
                title = (
                    localized.env._("Session cancelled")
                    if session.cancelled
                    else localized.env._("Training invitation / schedule update")
                )
                start = format_datetime(localized.env, session.start_at, tz=tz)
                end = format_datetime(localized.env, session.end_at, tz=tz)
                body = Markup("<p>%s — %s</p><p>%s → %s (%s)</p><p>%s</p><p>%s</p><p>%s</p>") % (
                    delivery.name,
                    session.name,
                    start,
                    end,
                    tz,
                    session.instructor_id.name or "",
                    session.location or session.room_id.name or "",
                    session.meeting_url or "",
                )
                # Narrow elevation: whitelist recipients above, one message per
                # person, no followers, attachments, CC or confidential content.
                mail = outgoing.create(
                    {
                        "subject": "%s — %s" % (title, session.name),
                        "body_html": body,
                        "email_to": partner.email,
                        "email_from": self.env.user.email_formatted or delivery.company_id.partner_id.email_formatted,
                        **self.env["mail.mail"]._training_identity(delivery.company_id),
                        "auto_delete": False,
                        "model": "training.session",
                        "res_id": session.id,
                    }
                )
                super(TrainingInvitation, self.sudo().with_context(clean_context)).create(  # pylint: disable=context-overridden  # deliberately discard untrusted defaults
                    {
                        "delivery_id": delivery.id,
                        "session_id": session.id,
                        "partner_id": partner.id,
                        "fingerprint": fingerprint,
                        "dispatch_number": previous[0].dispatch_number + 1 if previous else 1,
                        "mail_id": mail.id,
                        "requested_by_id": self.env.uid,
                        "requested_at": fields.Datetime.now(),
                        "recipient_timezone": tz,
                    }
                )
                count += 1
        return count

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # server-authored immutable records
        raise AccessError(self.env._("Invitations are generated by the coordinator's send action."))

    def write(self, vals):  # pylint: disable=method-required-super  # immutable records
        raise AccessError(self.env._("Distribution history is immutable."))  # pylint: disable=no-raise-unlink  # preserve audit

    def unlink(self):  # pylint: disable=method-required-super  # immutable history: cancellation replaces deletion
        raise AccessError(self.env._("Distribution history is immutable."))  # pylint: disable=no-raise-unlink  # preserve audit


class MailMail(models.Model):
    # Keep S04 transport validation separate from subsequent notification policies.
    _inherit = "mail.mail"  # pylint: disable=consider-merging-classes-inherited

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        self.ensure_one()
        if self.model == "training.session":
            # Native transport boundary, inside mail.mail's error handling.
            # Recheck the snapshot and recipient when the queue actually sends,
            # including retries after reassignment, cancellation or schedule edits.
            invitation = self.env["training.invitation"].sudo().search([("mail_id", "=", self.id)], limit=1)
            if not invitation:
                raise ValidationError(self.env._("This session email has no authorized invitation."))
            session, partner = invitation.session_id, invitation.partner_id
            latest = invitation.search([("session_id", "=", session.id), ("partner_id", "=", partner.id)], limit=1)
            allowed = (
                session.delivery_id.enrollment_ids.filtered(lambda item: item.state == "confirmed").participant_id
                | session.instructor_id
            )
            if (
                session.delivery_id.state not in ("confirmed", "ongoing")
                or partner not in allowed
                or self.email_to != partner.email
                or self.email_cc
                or self.recipient_ids
                or self.recipient_cc_ids
                or invitation != latest
                or invitation.fingerprint != invitation._fingerprint(session, partner)
            ):
                raise ValidationError(
                    self.env._("The schedule or recipient changed. Review and send the updated invitation.")
                )
        return super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
