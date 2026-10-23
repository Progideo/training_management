from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..models.training_attendance import MODES, SETTINGS


class AttendanceEdit(models.TransientModel):
    _name = "training.attendance.edit"
    _description = "Record Paper or Correct Attendance"

    session_id = fields.Many2one("training.session", required=True)
    delivery_id = fields.Many2one(related="session_id.delivery_id")
    enrollment_id = fields.Many2one("training.enrollment", required=True)
    operation = fields.Selection(
        [("paper", "Import Signed Paper"), ("correction", "Correct Validated Attendance")],
        required=True,
        default="paper",
    )
    start_minutes = fields.Float(string="Arrival (Minutes After Scheduled Start)")
    end_minutes = fields.Float(string="Departure (Minutes After Scheduled Start)")
    absent = fields.Boolean()
    reason = fields.Text(required=True)
    data = fields.Binary(attachment=False, required=True)
    filename = fields.Char(required=True)
    revision = fields.Integer(readonly=True)

    @api.onchange("enrollment_id", "session_id")
    def _onchange_presence(self):
        self.revision = 0
        if self.session_id and self.enrollment_id:
            presence = self.env["training.attendance"].search(
                [("session_id", "=", self.session_id.id), ("enrollment_id", "=", self.enrollment_id.id)], limit=1
            )
            self.revision = presence.revision
            self.end_minutes = (self.session_id.end_at - self.session_id.start_at).total_seconds() / 60
            decisions = presence.event_ids.filtered(lambda e: e.kind in ("validation", "correction"))
            latest = (decisions or presence.event_ids).sorted("id")[-1:]
            self.absent = bool(latest.absent)
            self.start_minutes = 0
            if latest and latest.start_at:
                self.start_minutes = (latest.start_at - self.session_id.start_at).total_seconds() / 60
                self.end_minutes = (latest.end_at - self.session_id.start_at).total_seconds() / 60

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("training_management.group_training_coordinator"):
            raise AccessError(self.env._("Only a training coordinator may import or correct attendance."))
        self.env["training.attendance.service"]._review(
            self.session_id.id,
            self.enrollment_id.id,
            self.start_minutes,
            self.end_minutes,
            correction=self.operation == "correction",
            paper=self.operation == "paper",
            absent=self.absent,
            revision=self.revision,
            reason=self.reason,
            data=self.data.content if self.data else b"",
            filename=self.filename,
        )
        return {"type": "ir.actions.act_window_close"}


class AttendanceSessionEdit(models.TransientModel):
    _inherit = "training.session.edit"

    attendance_mode = fields.Selection(MODES, required=True, default="electronic")
    attendance_before = fields.Integer(string="Declaration Opens Before Session (Minutes)")
    attendance_after = fields.Integer(string="Declaration Closes After Session (Minutes)")
    attendance_wording = fields.Text(
        required=True,
        default=lambda self: self.env._("I confirm that I attended the interval indicated for this session."),
    )

    @api.model
    def _schedule_fields(self):
        return (*super()._schedule_fields(), *SETTINGS)
