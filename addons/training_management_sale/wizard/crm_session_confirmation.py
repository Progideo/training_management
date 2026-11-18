"""Confirm a complete CRM request through the existing enrollment decisions."""

from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SessionConfirmation(models.TransientModel):
    _name = "training.crm.session.confirmation"
    _description = "Confirm CRM Session Participants"
    _check_company_auto = True

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade", readonly=True)
    company_id = fields.Many2one(related="lead_id.company_id", compute_sudo=False)
    delivery_id = fields.Many2one(related="lead_id.training_requested_delivery_id", compute_sudo=False)
    program_id = fields.Many2one(related="lead_id.training_program_id", compute_sudo=False)
    expected_count = fields.Integer(
        related="lead_id.training_attendee_count", string="Expected Participants", compute_sudo=False
    )
    start_at = fields.Datetime(string="Session Start", readonly=True, required=True)
    end_at = fields.Datetime(string="Session End", readonly=True, required=True)
    source = fields.Selection(
        [("order", "Confirmed Order"), ("allocation", "Existing Confirmed Allocation"), ("free", "Free Invitation")],
        required=True,
        default="order",
        string="Seat Origin",
    )
    sale_line_id = fields.Many2one("sale.order.line", string="Confirmed Order Line", check_company=True)
    allocation_id = fields.Many2one("training.seat.allocation", string="Confirmed Allocation", check_company=True)
    free_reason = fields.Text(string="Free Invitation Reason")
    prerequisites_checked = fields.Boolean(string="I have checked the prerequisites for all participants")
    reason = fields.Char(string="Admission Reason")
    line_ids = fields.One2many("training.crm.session.confirmation.line", "wizard_id", string="Named Participants")

    @api.model
    def default_get(self, names):
        values = super().default_get(names)
        lead = self.env["crm.lead"].browse(values.get("lead_id"))
        if lead:
            delivery = lead._check_session_confirmation_access()
            values.update(start_at=delivery.start_at, end_at=delivery.end_at)
            values["line_ids"] = [
                Command.create({"participant_id": lead.partner_id.id if lead.training_attendee_count == 1 else False})
                for _ in range(lead.training_attendee_count)
            ]
        return {key: value for key, value in values.items() if key in names}

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            lead_id = values.get("lead_id", self.env.context.get("default_lead_id"))
            self.env["crm.lead"].browse(lead_id)._check_session_confirmation_access()
        return super().create(vals_list)

    def write(self, vals):
        if "lead_id" in vals:
            raise AccessError(self.env._("Open a new assistant for another request."))
        return super().write(vals)

    @api.private
    def _allocation(self, delivery):
        if self.source == "free":
            if not (self.free_reason or "").strip():
                raise ValidationError(self.env._("Enter the reason for the free invitation."))
            return self.env["training.seat.allocation"]
        if self.source == "allocation":
            allocation = self.allocation_id
            allocation.check_access("write")
            if not allocation or allocation.delivery_id != delivery or allocation.state != "confirmed":
                raise ValidationError(self.env._("Choose a confirmed allocation for this session."))
            return allocation
        line = self.sale_line_id
        line.check_access("read")
        if (
            self.source != "order"
            or not line
            or line.state != "sale"
            or line.company_id != delivery.company_id
            or line.training_program_id != delivery.program_id
        ):
            raise ValidationError(self.env._("Choose a confirmed order line for this session programme and company."))
        allocation = self.env["training.seat.allocation"].create(
            {
                "delivery_id": delivery.id,
                "customer_id": line.order_id.partner_id.id,
                "sale_line_id": line.id,
                "quantity": self.expected_count,
                "source_reference": f"CRM-{self.lead_id.id}",
                "expires_at": fields.Datetime.now() + timedelta(days=1),
            }
        )
        allocation.action_confirm()
        return allocation

    def action_confirm(self):
        self.ensure_one()
        self.check_access("write")
        with self.env.cr.savepoint():
            lead = self.lead_id
            delivery = lead._check_session_confirmation_access()
            lead.lock_for_update()
            lead.invalidate_recordset()
            lead._store_session_confirmation(
                {"training_session_confirmation_revision": lead.training_session_confirmation_revision + 1}
            )
            participants = self.line_ids.participant_id
            participants.check_access("read")
            if len(self.line_ids) != lead.training_attendee_count or len(participants) != len(self.line_ids):
                raise ValidationError(self.env._("Enter exactly one distinct contact for each requested participant."))
            if any(
                not person.active or person.is_company or (person.company_id and person.company_id != lead.company_id)
                for person in participants
            ):
                raise ValidationError(
                    self.env._("Choose individual contacts shared or belonging to the operating company.")
                )
            existing = lead.training_session_enrollment_ids
            if existing:
                if set(existing.participant_id.ids) != set(participants.ids):
                    raise ValidationError(self.env._("This request already has participants. Open their enrollments."))
                return lead.action_view_session_participants()
            if (
                delivery.state not in ("preparation", "confirmed")
                or delivery.start_at <= fields.Datetime.now()
                or delivery.start_at != self.start_at
                or delivery.end_at != self.end_at
            ):
                raise ValidationError(
                    self.env._("The session has changed or no longer accepts participants. Reopen the assistant.")
                )
            if not self.prerequisites_checked or not (self.reason or "").strip():
                raise ValidationError(
                    self.env._("Check all participants' prerequisites and enter the admission reason.")
                )
            allocation = self._allocation(delivery)
            enrollments = self.env["training.enrollment"].create(
                [
                    {
                        "delivery_id": delivery.id,
                        "participant_id": person.id,
                        "allocation_id": allocation.id,
                        "free_reason": self.free_reason if self.source == "free" else False,
                    }
                    for person in participants
                ]
            )
            enrollments.action_validate_prerequisites(reason=self.reason)
            enrollments.action_confirm(reason=self.reason)
            lead._store_session_confirmation({"training_session_enrollment_ids": [Command.set(enrollments.ids)]})
            lead.message_post(body=self.env._("Session places confirmed for %s participant(s).", len(enrollments)))
            return lead.action_view_session_participants()


class SessionConfirmationLine(models.TransientModel):
    _name = "training.crm.session.confirmation.line"
    _description = "CRM Session Participant"
    _check_company_auto = True

    wizard_id = fields.Many2one("training.crm.session.confirmation", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="wizard_id.company_id", compute_sudo=False)
    participant_id = fields.Many2one(
        "res.partner",
        check_company=True,
        domain="[('is_company', '=', False), ('company_id', 'in', [False, company_id])]",
    )
