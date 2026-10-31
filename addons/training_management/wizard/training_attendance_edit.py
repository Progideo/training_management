from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..models.training_attendance import MODES, SETTINGS


class AttendanceEdit(models.TransientModel):
    _name = "training.attendance.edit"
    _description = "Record Paper or Correct Attendance"
    _check_company_auto = True

    session_id = fields.Many2one("training.session", required=True, check_company=True)
    delivery_id = fields.Many2one(related="session_id.delivery_id")
    company_id = fields.Many2one(related="session_id.company_id")
    enrollment_id = fields.Many2one("training.enrollment", required=True, check_company=True)
    operation = fields.Selection(
        [
            ("paper", "Import Signed Paper"),
            ("correction", "Correct Validated Attendance"),
            ("invalidation", "Invalidate Attendance"),
        ],
        required=True,
        default="paper",
    )
    start_minutes = fields.Float(string="Arrival (Minutes After Scheduled Start)")
    end_minutes = fields.Float(string="Departure (Minutes After Scheduled Start)")
    period_date = fields.Date(string="Date")
    halfday = fields.Selection(
        [("am", "Morning"), ("pm", "Afternoon"), ("legacy", "Historical attendance")], required=True, default="am"
    )
    period_key = fields.Char(compute="_compute_period_key")
    absent = fields.Boolean()
    reason = fields.Text(required=True)
    data = fields.Binary(attachment=False)
    filename = fields.Char()
    revision = fields.Integer(readonly=True)
    definition = fields.Char(readonly=True)

    @api.depends("period_date", "halfday")
    def _compute_period_key(self):
        for wizard in self:
            wizard.period_key = (
                "legacy" if wizard.halfday == "legacy" else "%s-%s" % (wizard.period_date, wizard.halfday)
            )

    @api.onchange("enrollment_id", "session_id")
    def _onchange_presence(self):
        if self.session_id:
            periods = self.env["training.attendance.service"]._visible_periods(self.session_id, self.enrollment_id.id)
            first = periods[0]
            self.halfday = "legacy" if first["key"] == "legacy" else first["key"][-2:]
            self.period_date = first["key"][:10] if first["key"] != "legacy" else False
        self._onchange_period()

    @api.onchange("period_date", "halfday")
    def _onchange_period(self):
        self.revision = 0
        self.definition = (
            self.env["training.attendance.service"]._definition(self.session_id) if self.session_id else False
        )
        if self.session_id and self.enrollment_id:
            presence = self.env["training.attendance"].search(
                [
                    ("session_id", "=", self.session_id.id),
                    ("enrollment_id", "=", self.enrollment_id.id),
                    ("period_key", "=", self.period_key),
                ],
                limit=1,
            )
            self.revision = presence.revision
            latest = presence.event_ids.sorted("id")[-1:]
            self.absent = bool(latest.absent)
            self.start_minutes = 0
            self.end_minutes = (self.session_id.end_at - self.session_id.start_at).total_seconds() / 60
            if self.halfday == "legacy" and latest.start_at:
                self.start_minutes = (latest.start_at - self.session_id.start_at).total_seconds() / 60
                self.end_minutes = (latest.end_at - self.session_id.start_at).total_seconds() / 60

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("training_management.group_training_coordinator"):
            raise AccessError(self.env._("Only a training coordinator may import or correct attendance."))
        if self.halfday == "legacy" and not self.env["training.attendance"].search_count(
            [
                ("session_id", "=", self.session_id.id),
                ("enrollment_id", "=", self.enrollment_id.id),
                ("period_key", "=", "legacy"),
            ],
            limit=1,
        ):
            raise ValidationError(self.env._("Choose a half-day from the current schedule."))
        if self.operation == "invalidation":
            self.env["training.attendance.service"]._invalidate(
                self.session_id.id,
                self.enrollment_id.id,
                revision=self.revision,
                reason=self.reason,
                definition=self.definition,
                period_key=self.period_key,
            )
            return {"type": "ir.actions.act_window_close"}
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
            definition=self.definition,
            period_key=self.period_key,
        )
        return {"type": "ir.actions.act_window_close"}


class AttendanceSessionEdit(models.TransientModel):
    _inherit = "training.session.edit"

    attendance_mode = fields.Selection(MODES, required=True, default="electronic")
    attendance_before = fields.Integer(string="Declaration Opens Before Session (Minutes)")
    attendance_after = fields.Integer(string="Declaration Closes After Session (Minutes)", default=30)
    attendance_wording = fields.Text(
        required=True,
        default=lambda self: self.env._("I confirm that I attended the interval indicated for this session."),
    )

    @api.model
    def _schedule_fields(self):
        return (*super()._schedule_fields(), *SETTINGS)
