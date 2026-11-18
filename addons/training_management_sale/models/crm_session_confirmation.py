"""CRM entry point for the native session enrollment assistant."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

CONFIRMATION_FIELDS = {"training_session_enrollment_ids", "training_session_confirmation_revision"}


class CrmLead(models.Model):
    _inherit = "crm.lead"  # pylint: disable=consider-merging-classes-inherited

    training_session_enrollment_ids = fields.Many2many(
        "training.enrollment",
        "training_crm_session_enrollment_rel",
        "lead_id",
        "enrollment_id",
        string="Confirmed Session Participants",
        readonly=True,
        copy=False,
        groups="training_management.group_training_coordinator",
    )
    training_session_confirmation_revision = fields.Integer(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(CONFIRMATION_FIELDS & values.keys() for values in vals_list) or any(
            "default_" + key in self.env.context for key in CONFIRMATION_FIELDS
        ):
            raise AccessError(self.env._("Use the session confirmation assistant."))
        return super().create(vals_list)

    def write(self, vals):
        if CONFIRMATION_FIELDS & vals.keys():
            raise AccessError(self.env._("Use the session confirmation assistant."))
        if {
            "training_requested_delivery_id",
            "training_requested_course_id",
            "training_program_id",
            "training_attendee_count",
            "company_id",
        } & vals.keys():
            # Do not expose participant records to ordinary CRM callers.
            self.check_access("write")
            confirmed = self.sudo().filtered("training_session_enrollment_ids")
            for lead in confirmed:
                for key in vals.keys() & {
                    "training_requested_delivery_id",
                    "training_requested_course_id",
                    "training_program_id",
                    "training_attendee_count",
                    "company_id",
                }:
                    current = lead[key].id if lead._fields[key].type == "many2one" else lead[key]
                    if current != (vals[key] or False):
                        raise ValidationError(
                            self.env._("A confirmed session request keeps its session and participant count.")
                        )
        return super().write(vals)

    @api.private
    def _check_session_confirmation_access(self):
        self.ensure_one()
        self.check_access("write")
        if not self.env.user.active or not self.env.user.has_group("training_management.group_training_coordinator"):
            raise AccessError(self.env._("Only a training coordinator may confirm session participants."))
        if not self.company_id or self.company_id not in self.env.companies:
            raise AccessError(self.env._("Use a request in your active operating companies."))
        delivery = self.training_requested_delivery_id
        delivery.check_access("write")
        if (
            not self.active
            or not delivery
            or delivery.company_id != self.company_id
            or delivery.kind != "session"
            or delivery.program_id != self.training_program_id
            or delivery.program_id.course_id != self.training_requested_course_id
            or not 1 <= self.training_attendee_count <= 5
        ):
            raise ValidationError(self.env._("Choose a session registration request for one to five participants."))
        return delivery

    @api.private
    def _store_session_confirmation(self, values):
        self._check_session_confirmation_access()
        return super().write(values)  # pylint: disable=super-method-mismatch  # private checked enrollment decision

    def action_confirm_session_participants(self):
        self._check_session_confirmation_access()
        if self.training_session_enrollment_ids:
            return self.action_view_session_participants()
        wizard = self.env["training.crm.session.confirmation"].with_context(default_lead_id=self.id).create({})
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Confirm Session Participants"),
            "res_model": wizard._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_session_participants(self):
        self._check_session_confirmation_access()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Session Participants"),
            "res_model": "training.enrollment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.training_session_enrollment_ids.ids)],
        }

    def action_view_session_confirmation_emails(self):
        self._check_session_confirmation_access()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Confirmation Emails"),
            "res_model": "training.session.confirmation.notice",
            "view_mode": "list,form",
            "domain": [("lead_id", "=", self.id)],
        }
