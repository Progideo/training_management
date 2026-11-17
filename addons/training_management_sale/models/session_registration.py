"""Public intake for future inter-company sessions."""

import hashlib
import json

from datetime import UTC
from zoneinfo import ZoneInfo

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize

MAX_PUBLIC_GROUP_SIZE = 5


class TrainingDelivery(models.Model):
    _inherit = "training.delivery"

    @api.private
    def _public_registration_sessions(self, company, course_id, delivery_id=None):
        # Search with sudo only inside the website operator's published scope.
        domain = [
            ("company_id", "=", company.id),
            ("program_id.company_id", "=", company.id),
            ("program_id.course_id", "=", course_id),
            ("program_id.course_id.active", "=", True),
            ("program_id.public_catalogue", "=", True),
            ("program_id.state", "=", "published"),
            ("program_id.delivery_mode", "in", ("onsite", "remote", "blended")),
            ("kind", "=", "session"),
            ("session_public", "=", True),
            ("session_sales_open", "=", True),
            ("state", "in", ("preparation", "confirmed")),
            ("start_at", ">", fields.Datetime.now()),
        ]
        if delivery_id is not None:
            domain.append(("id", "=", delivery_id))
        return self.sudo().search(domain, order="start_at, id")

    @api.private
    def _public_registration_limit(self):
        self.ensure_one()
        if not self.capacity:
            return MAX_PUBLIC_GROUP_SIZE
        return max(0, min(MAX_PUBLIC_GROUP_SIZE, self.capacity - self._occupancy()))


class CrmLead(models.Model):
    _inherit = "crm.lead"  # pylint: disable=consider-merging-classes-inherited

    training_requested_delivery_id = fields.Many2one(
        "training.delivery",
        string="Requested Session",
        check_company=True,
        ondelete="restrict",
        readonly=True,
        copy=False,
    )

    @api.private
    def _submit_public_session_request(self, delivery, values, key):
        company = delivery.company_id
        self = (
            self.with_user(SUPERUSER_ID)
            .sudo()
            .with_company(company)
            .with_context(mail_create_nosubscribe=True, mail_create_nolog=True, lang=self.env.lang)
        )
        if not values["contact"]:
            raise ValidationError(self.env._("Enter your name."))
        if any(len(value) > 254 for value in values.values()):
            raise ValidationError(self.env._("A field exceeds 254 characters."))
        email = email_normalize(values["email"])
        if not email:
            raise ValidationError(self.env._("Enter a valid email address."))
        count = values["count"]
        # Native schedule and allocation changes update the delivery row.
        # A concurrent change must be retried before the CRM request is recorded.
        delivery.lock_for_update()
        limit = delivery._public_registration_limit() if delivery._session_public_row() else 0
        if count not in {str(number) for number in range(1, limit + 1)}:
            raise ValidationError(self.env._("Choose a participant count within the current availability."))
        count = int(count)
        program = delivery.program_id
        local_zone = ZoneInfo(delivery.timezone)
        fingerprint = hashlib.sha256(json.dumps([delivery.id, values], sort_keys=True).encode()).hexdigest()
        return self._record_public_request(
            {
                "name": self.env._("Inter-company registration request — %s", program.course_id.name),
                "type": "lead",
                "user_id": False,
                "team_id": False,
                "company_id": company.id,
                "contact_name": values["contact"],
                "email_from": email,
                "partner_name": values["organisation"],
                "phone": values["phone"],
                "training_request_kind": "group" if count > 1 else "individual",
                "training_request_type": "catalogue",
                "training_requested_course_id": program.course_id.id,
                "training_program_id": program.id,
                "training_requested_delivery_id": delivery.id,
                "training_attendee_count": count,
                "training_requested_currency_id": company.currency_id.id,
                "training_delivery_mode": program.delivery_mode,
                "training_date_from": delivery.start_at.replace(tzinfo=UTC).astimezone(local_zone).date(),
                "training_date_to": delivery.end_at.replace(tzinfo=UTC).astimezone(local_zone).date(),
                "training_submission_key": key,
                "training_submission_hash": fingerprint,
            },
            email,
        )
