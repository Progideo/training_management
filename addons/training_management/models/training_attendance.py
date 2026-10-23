"""PRE01–03: one retained interval, append-only declarations and decisions."""

import json
import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.binary import BinaryBytes

COORDINATOR = "training_management.group_training_coordinator"
MODES = [("electronic", "Electronic"), ("paper", "Paper"), ("mixed", "Mixed")]
SETTINGS = ("attendance_mode", "attendance_before", "attendance_after", "attendance_wording")


class AttendanceSession(models.Model):
    _inherit = "training.session"

    attendance_mode = fields.Selection(MODES, required=True, default="electronic")
    attendance_before = fields.Integer(string="Declaration Opens Before Session (Minutes)", default=0)
    attendance_after = fields.Integer(string="Declaration Closes After Session (Minutes)", default=30)
    attendance_wording = fields.Text(
        required=True,
        default=lambda self: self.env._("I confirm that I attended the interval indicated for this session."),
    )
    attendance_ids = fields.One2many("training.attendance", "session_id", readonly=True, groups=COORDINATOR)

    @api.constrains(*SETTINGS)
    def _check_attendance_settings(self):
        for session in self:
            if (
                min(session.attendance_before, session.attendance_after) < 0
                or not (session.attendance_wording or "").strip()
            ):
                raise ValidationError(self.env._("Use non-negative declaration windows and a confirmation text."))

    @api.private
    def _apply_schedule(self, vals, reason=None, cancel=False, conflict_reason=None):
        if self.attendance_ids:
            raise ValidationError(self.env._("Keep the schedule and declaration settings once attendance is recorded."))
        return super()._apply_schedule(vals, reason, cancel, conflict_reason)

    def write(self, vals):
        if self.filtered("attendance_ids"):
            raise ValidationError(self.env._("Keep the schedule and declaration settings once attendance is recorded."))
        return super().write(vals)

    def action_attendance(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Session Attendance"),
            "res_model": "training.attendance",
            "view_mode": "list,form",
            "domain": [("session_id", "=", self.id)],
        }

    def action_record_attendance(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Record Paper / Correct Attendance"),
            "res_model": "training.attendance.edit",
            "view_mode": "form",
            "target": "new",
            "context": {"default_session_id": self.id},
        }


class AttendanceEvidence(models.AbstractModel):
    _name = "training.attendance.evidence"
    _description = "Server-authored Attendance Evidence"

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # controlled server factory
        raise AccessError(self.env._("Use the attendance declaration or review action."))

    def write(self, vals):  # pylint: disable=method-required-super  # append-only public API
        raise AccessError(self.env._("Attendance evidence cannot be rewritten."))

    @api.ondelete(at_uninstall=False)
    def _keep_evidence(self):
        raise ValidationError(self.env._("Keep attendance evidence and its history."))

    def copy_data(self, default=None):  # pylint: disable=method-required-super  # preserve provenance
        raise AccessError(self.env._("Attendance evidence cannot be copied."))

    @api.private
    def _append(self, values):
        # Authority and serialization are checked by the service, not by sudo.
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        return super(AttendanceEvidence, self.sudo().with_context(clean)).create(values)  # pylint: disable=super-method-mismatch,context-overridden  # private checked factory


class Attendance(models.Model):
    _name = "training.attendance"
    _inherit = "training.attendance.evidence"
    _description = "Session Attendance"
    _rec_name = "enrollment_id"
    _check_company_auto = True

    session_id = fields.Many2one("training.session", required=True, ondelete="restrict", check_company=True, index=True)
    enrollment_id = fields.Many2one(
        "training.enrollment", required=True, ondelete="restrict", check_company=True, index=True
    )
    company_id = fields.Many2one(related="session_id.company_id", store=True)
    event_ids = fields.One2many("training.attendance.event", "attendance_id", readonly=True)
    state = fields.Selection(
        [("pending", "Pending Review"), ("anomaly", "Anomaly"), ("validated", "Validated")], compute="_compute_result"
    )
    minutes = fields.Float(string="Validated Minutes", compute="_compute_result")
    late_minutes = fields.Float(compute="_compute_result")
    absent = fields.Boolean(compute="_compute_result")
    revision = fields.Integer(compute="_compute_result")
    _one_presence = models.Constraint(
        "UNIQUE(session_id, enrollment_id)", "One attendance record per participant and session."
    )

    @api.depends("event_ids")
    def _compute_result(self):
        for record in self:
            events = record.event_ids.sorted("id")
            decisions = events.filtered(lambda e: e.kind in ("validation", "correction"))
            last = decisions[-1:] or events[-1:]
            record.revision = events[-1:].id or 0
            record.state = "validated" if decisions else "anomaly" if events.filtered("anomaly") else "pending"
            record.minutes = (
                max(0, (last.end_at - last.start_at).total_seconds() / 60) if decisions and not last.absent else 0
            )
            record.absent = bool(decisions and last.absent)
            record.late_minutes = (
                max(0, (last.start_at - record.session_id.start_at).total_seconds() / 60)
                if decisions and not last.absent
                else 0
            )


class AttendanceEvent(models.Model):
    _name = "training.attendance.event"
    _inherit = "training.attendance.evidence"
    _description = "Attendance Declaration and Review History"
    _order = "id"
    _rec_name = "kind"

    attendance_id = fields.Many2one("training.attendance", required=True, ondelete="restrict", index=True)
    company_id = fields.Many2one(related="attendance_id.company_id", store=True)
    kind = fields.Selection(
        [
            ("declaration", "Participant Declaration"),
            ("paper", "Signed Paper"),
            ("validation", "Trainer Validation"),
            ("correction", "Coordinator Correction"),
        ],
        required=True,
    )
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    occurred_at = fields.Datetime(required=True)
    start_at = fields.Datetime()
    end_at = fields.Datetime()
    absent = fields.Boolean()
    anomaly = fields.Boolean()
    wording = fields.Text()
    reason = fields.Text()
    before = fields.Text()
    after = fields.Text(required=True)
    # Native binary field without an attachment: collective signed sheets remain
    # coordinator-only evidence; no public attachment flag or bearer token exists.
    data = fields.Binary(attachment=False, readonly=True, copy=False, string="Private Evidence")
    filename = fields.Char()

    def _can_return_content(self, field_name=None, access_token=None):
        self.with_env(self.env(su=False)).check_access("read")
        return field_name == "data"


class AttendanceService(models.AbstractModel):
    _name = "training.attendance.service"
    _description = "Authorized Attendance Operations"

    @api.private
    def _session(self, session_id, *, coordinator=False, lock=False):
        session = self.env["training.session"].sudo().browse(session_id).exists()
        user = self.env.user
        if not session or not user.active or user._is_public() or session.company_id not in user.company_ids:
            raise AccessError(self.env._("This attendance record is unavailable."))
        if coordinator:
            session.with_env(self.env(su=False))._require_coordinator()
        else:
            if session.instructor_id != user.partner_id:
                raise AccessError(self.env._("Only the assigned session trainer may validate attendance."))
        if session.cancelled or session.delivery_id.state not in ("confirmed", "ongoing"):
            raise ValidationError(self.env._("Attendance requires an active, non-cancelled scheduled session."))
        if lock:
            session.delivery_id._serialize()
            session.invalidate_recordset()
        return session

    @api.private
    def _presence(self, session, enrollment_id):
        enrollment = self.env["training.enrollment"].sudo().browse(enrollment_id).exists()
        if not enrollment or enrollment.delivery_id != session.delivery_id or enrollment.state != "confirmed":
            raise AccessError(self.env._("This attendance record is unavailable."))
        presence = (
            self.env["training.attendance"]
            .sudo()
            .search([("session_id", "=", session.id), ("enrollment_id", "=", enrollment.id)], limit=1)
        )
        return presence or presence._append({"session_id": session.id, "enrollment_id": enrollment.id})

    @api.private
    def _interval(self, session, start, end, absent=False):
        if absent:
            return False, False
        try:
            # UI supplies elapsed minutes from scheduled start, independent of
            # browser timezone. Reject NaN/infinity and future claimed presence.
            start, end = float(start), float(end)
            if not math.isfinite(start) or not math.isfinite(end):
                raise ValueError
            first = session.start_at + timedelta(minutes=start)
            last = session.start_at + timedelta(minutes=end)
        except (ValueError, TypeError, OverflowError) as error:
            raise ValidationError(self.env._("Enter a valid attended interval in minutes.")) from error
        if first < session.start_at or last > session.end_at or last <= first or last > fields.Datetime.now():
            raise ValidationError(self.env._("The attended interval must be elapsed and within the scheduled session."))
        return first, last

    @api.private
    def _event(self, presence, kind, first, last, *, absent=False, anomaly=False, reason=False, data=b"", filename=""):
        before = presence.event_ids.sorted("id")[-1:]
        if kind == "correction":
            before = presence.event_ids.filtered(lambda e: e.kind in ("validation", "correction")).sorted("id")[-1:]
        after = json.dumps(
            {"start": str(first) if first else None, "end": str(last) if last else None, "absent": bool(absent)},
            sort_keys=True,
        )
        return self.env["training.attendance.event"]._append(
            {
                "attendance_id": presence.id,
                "kind": kind,
                "actor_id": self.env.uid,
                "occurred_at": fields.Datetime.now(),
                "start_at": first,
                "end_at": last,
                "absent": bool(absent),
                "anomaly": bool(anomaly),
                "wording": presence.session_id.attendance_wording if kind == "declaration" else False,
                "reason": reason,
                "before": before.after if before else False,
                "after": after,
                "data": BinaryBytes(data) if data else False,
                "filename": filename if data else False,
            }
        )

    @api.private
    def _declare(self, enrollment_id, session_id, start, end, accepted=False):
        with self.env.cr.savepoint():
            enrollment = self.env["training.learning.service"]._enrollment(enrollment_id, lock=True)
            session = self.env["training.session"].sudo().browse(session_id).exists()
            if (
                not session
                or session.delivery_id != enrollment.delivery_id
                or session.cancelled
                or session.attendance_mode == "paper"
                or session.delivery_id.state not in ("confirmed", "ongoing")
            ):
                raise AccessError(self.env._("This attendance record is unavailable."))
            if not accepted:
                raise ValidationError(self.env._("Accept the session confirmation text."))
            first, last = self._interval(session, start, end)
            presence = self._presence(session, enrollment_id)
            previous = presence.event_ids.filtered(lambda e: e.kind == "declaration")
            if previous:
                if previous.start_at != first or previous.end_at != last:
                    raise ValidationError(
                        self.env._("Your declaration is recorded. Ask the coordinator for a correction.")
                    )
                return presence
            now = fields.Datetime.now()
            anomaly = not (
                session.start_at - timedelta(minutes=session.attendance_before)
                <= now
                <= session.end_at + timedelta(minutes=session.attendance_after)
            )
            self._event(presence, "declaration", first, last, anomaly=anomaly)
            return presence

    @api.private
    def _review(
        self,
        session_id,
        enrollment_id,
        start,
        end,
        *,
        correction=False,
        paper=False,
        absent=False,
        revision=0,
        reason="",
        data=b"",
        filename="",
    ):
        with self.env.cr.savepoint():
            session = self._session(session_id, coordinator=paper or correction, lock=True)
            presence = self._presence(session, enrollment_id)
            if presence.revision != revision:
                raise ValidationError(self.env._("Attendance changed. Reload before recording your decision."))
            if fields.Datetime.now() < session.end_at:
                raise ValidationError(self.env._("Review attendance after the session ends."))
            if paper and session.attendance_mode == "electronic":
                raise ValidationError(self.env._("Choose paper or mixed collection for signed paper."))
            if (correction or paper) and (not reason.strip() or not data or not filename):
                raise ValidationError(self.env._("Provide a reason and a named evidence file."))
            if len(data) > 10 * 1024 * 1024:
                raise ValidationError(self.env._("The evidence file must not exceed 10 MB."))
            decisions = presence.event_ids.filtered(lambda e: e.kind in ("validation", "correction"))
            if decisions and not correction and not paper:
                raise ValidationError(self.env._("An existing validation requires a coordinator correction."))
            if correction and not decisions:
                raise ValidationError(self.env._("The trainer must first validate the attendance."))
            if not paper and not correction:
                if presence.enrollment_id.user_id == self.env.user:
                    raise AccessError(self.env._("A trainer cannot validate their own attendance."))
                sources = presence.event_ids.filtered(lambda e: e.kind in ("declaration", "paper"))
                if (not sources and not absent) or self.env.user in sources.actor_id:
                    raise ValidationError(
                        self.env._("Trainer validation must be separate from the source declaration.")
                    )
                if presence.event_ids.filtered("anomaly") and not reason.strip():
                    raise ValidationError(self.env._("Explain how the out-of-window anomaly was checked."))
            first, last = self._interval(session, start, end, absent)
            self._event(
                presence,
                "correction" if correction else "paper" if paper else "validation",
                first,
                last,
                absent=absent,
                reason=reason.strip(),
                data=data,
                filename=filename.replace("\\", "/").split("/")[-1],
            )
            return presence
