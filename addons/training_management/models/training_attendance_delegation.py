"""An unavailable trainer: audited control reassignment, schedule evidence unchanged."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AttendanceDelegation(models.Model):
    _name = "training.attendance.delegation"
    _inherit = "training.attendance.evidence"
    _description = "Attendance Control Reassignment"
    _order = "id desc"
    _rec_name = "partner_id"
    _check_company_auto = True

    session_id = fields.Many2one("training.session", required=True, ondelete="restrict", check_company=True, index=True)
    company_id = fields.Many2one(related="session_id.company_id", store=True)
    previous_partner_id = fields.Many2one("res.partner", string="Previous Controller", ondelete="restrict")
    partner_id = fields.Many2one(
        "res.partner", string="Replacement Trainer", required=True, ondelete="restrict", index=True
    )
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    occurred_at = fields.Datetime(required=True)
    reason = fields.Text(required=True)


class AttendanceControlSession(models.Model):
    _inherit = "training.session"

    attendance_delegation_ids = fields.One2many(
        "training.attendance.delegation",
        "session_id",
        readonly=True,
        groups="training_management.group_training_coordinator",
    )
    attendance_control_partner_id = fields.Many2one(
        "res.partner", string="Attendance Control", compute="_compute_attendance_control", compute_sudo=True
    )

    @api.depends("instructor_id", "attendance_delegation_ids")
    def _compute_attendance_control(self):
        for session in self:
            session.attendance_control_partner_id = session._control_partner()

    @api.private
    def _control_partner(self):
        self.ensure_one()
        latest = self.env["training.attendance.delegation"].sudo().search([("session_id", "=", self.id)], limit=1)
        return latest.partner_id or self.sudo().instructor_id

    @api.model
    def _delegated_session_ids(self, partner):
        rows = self.env["training.attendance.delegation"].sudo().search([("partner_id", "=", partner.id)])
        return rows.session_id.filtered(lambda session: session._control_partner() == partner).ids

    def action_delegate_control(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reassign Attendance Control"),
            "res_model": "training.attendance.delegate",
            "view_mode": "form",
            "target": "new",
            "context": {"default_session_id": self.id},
        }


class AttendanceDelegationService(models.AbstractModel):
    _inherit = "training.attendance.service"

    @api.private
    def _delegate(self, session_id, partner_id, reason):
        with self.env.cr.savepoint():
            session = self._session(session_id, coordinator=True, lock=True)
            if not (reason or "").strip():
                raise ValidationError(self.env._("Explain why the attendance control is reassigned."))
            partner = self.env["res.partner"].sudo().browse(partner_id).exists()
            if not partner or not partner.user_ids.filtered(
                lambda user: user.active and session.company_id in user.company_ids
            ):
                raise ValidationError(self.env._("Choose a replacement with an active account in this company."))
            confirmed = session.delivery_id.enrollment_ids.filtered(lambda row: row.state == "confirmed")
            if partner in confirmed.participant_id:
                raise ValidationError(self.env._("A participant of this training cannot control its attendance."))
            current = session._control_partner()
            if partner == current:
                return (
                    self.env["training.attendance.delegation"].sudo().search([("session_id", "=", session.id)], limit=1)
                )
            return self.env["training.attendance.delegation"]._append(
                {
                    "session_id": session.id,
                    "previous_partner_id": current.id,
                    "partner_id": partner.id,
                    "actor_id": self.env.uid,
                    "occurred_at": fields.Datetime.now(),
                    "reason": reason.strip(),
                }
            )
