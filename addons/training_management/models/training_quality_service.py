"""Authenticated participant projection: own original complaint and published reply only."""

from datetime import timedelta
from uuid import UUID

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_evaluation import clean_context
from .training_quality import QualityRecord, required_text


class QualityService(models.AbstractModel):
    _name = "training.quality.service"
    _description = "Private Participant Complaint Projection"

    @api.private
    def _enrollment_domain(self):
        user = self.env.user
        if not user.active or user._is_public():
            return [("id", "=", 0)]
        return [
            ("company_id", "in", user.company_ids.ids),
            ("user_id", "=", user.id),
            ("participant_id", "=", user.partner_id.id),
            ("state", "in", ["confirmed", "closed"]),
            ("commercially_authorized", "=", True),
            ("access_state", "not in", ["revoked", "suspended"]),
        ]

    @api.private
    def _visible_domain(self):
        enrollments = self.env["training.enrollment"].sudo().search(self._enrollment_domain())
        return [
            ("enrollment_id", "in", enrollments.ids),
            ("portal_visible", "=", True),
            ("portal_revoked", "=", False),
            ("company_id", "in", self.env.user.company_ids.ids),
        ]

    @api.private
    def _complaint(self, complaint_id):
        row = (
            self.env["training.complaint"].sudo().search(self._visible_domain() + [("id", "=", complaint_id)], limit=1)
        )
        if not row:
            raise AccessError(self.env._("This complaint is unavailable."))
        return row

    @api.private
    def _values(self, row):
        row = self._complaint(row.id)
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "state": row.state,
            "reply": row.reply if row.state in ("resolved", "closed") else False,
            "received_at": row.received_at,
        }

    @api.private
    def _receive(self, enrollment_id, key, subject, description):  # pylint: disable=super-method-mismatch  # Checked portal factory.
        try:
            key = str(UUID(key))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError(self.env._("Reload the complaint form before submitting.")) from None
        enrollment = (
            self.env["training.enrollment"]
            .sudo()
            .search(self._enrollment_domain() + [("id", "=", enrollment_id)], limit=1)
        )
        if not enrollment:
            raise AccessError(self.env._("This enrollment is unavailable."))
        enrollment.lock_for_update()
        self.env.invalidate_all()
        if not enrollment.filtered_domain(self._enrollment_domain()):
            raise AccessError(self.env._("This enrollment is unavailable."))
        existing = (
            self.env["training.complaint"]
            .sudo()
            .search([("enrollment_id", "=", enrollment.id), ("submission_key", "=", key)], limit=1)
        )
        if existing:
            return self._complaint(existing.id)
        if not required_text(subject) or not required_text(description):
            raise ValidationError(self.env._("Enter a subject and your complaint."))
        delivery = enrollment.delivery_id
        reviewer = delivery.complaint_quality_id
        retention = delivery.complaint_retention_id
        if not reviewer or not reviewer.active or not retention.approved_at or delivery.complaint_response_days < 1:
            raise ValidationError(self.env._("Complaint intake is not configured; contact the training organizer."))
        model = clean_context(self.env["training.complaint"]).sudo()
        # Narrow factory after current ownership, eligibility and serialized anti-replay checks.
        row = super(QualityRecord, model).create(  # pylint: disable=super-method-mismatch
            {
                "name": subject,
                "description": description,
                "company_id": delivery.company_id.id,
                "delivery_id": delivery.id,
                "enrollment_id": enrollment.id,
                "complainant_id": self.env.user.partner_id.id,
                "quality_id": reviewer.id,
                "responsible_id": reviewer.id,
                "member_ids": [Command.clear()],
                "retention_id": retention.id,
                "channel": "portal",
                "portal_visible": True,
                "submission_key": key,
                "due_date": fields.Date.context_today(self) + timedelta(days=delivery.complaint_response_days),
            }
        )
        row._event("registered_from_portal")
        return row
