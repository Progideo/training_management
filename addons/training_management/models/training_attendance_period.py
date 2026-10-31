"""Half-days come from the actual schedule, without invented flat-rate hours."""

from datetime import datetime, time, timedelta
import hashlib

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date


class AttendancePeriods(models.AbstractModel):
    _inherit = "training.attendance.service"

    @api.private
    def _periods(self, session):
        zone = pytz.timezone(session.timezone or "UTC")
        first = pytz.UTC.localize(session.start_at).astimezone(zone)
        last = pytz.UTC.localize(session.end_at).astimezone(zone)
        day = first.date()
        periods = []
        while day <= last.date():
            for code, begin, finish in (("am", time.min, time(12)), ("pm", time(12), time.min)):
                start = zone.localize(datetime.combine(day, begin))
                end = zone.localize(datetime.combine(day + timedelta(days=code == "pm"), finish))
                start, end = max(first, start), min(last, end)
                if start < end:
                    periods.append(
                        {
                            "key": "%s-%s" % (day.isoformat(), code),
                            "label": "%s — %s"
                            % (
                                format_date(self.env, day),
                                self.env._("Morning") if code == "am" else self.env._("Afternoon"),
                            ),
                            "start": start.astimezone(pytz.UTC).replace(tzinfo=None),
                            "end": end.astimezone(pytz.UTC).replace(tzinfo=None),
                        }
                    )
            day += timedelta(days=1)
        return periods

    @api.private
    def _period(self, session, key):
        for period in self._periods(session):
            if period["key"] == key:
                return period
        raise ValidationError(self.env._("Choose a half-day from the current schedule."))

    @api.private
    def _period_end(self, session, key):
        return session.end_at if key == "legacy" else self._period(session, key)["end"]

    @api.private
    def _period_interval(self, session, key, start, end, absent):
        if key == "legacy":
            return self._interval(session, start, end, absent)
        period = self._period(session, key)
        if fields.Datetime.now() < period["end"]:
            raise ValidationError(self.env._("Confirm attendance after this half-day ends."))
        return (False, False) if absent else (period["start"], period["end"])

    @api.private
    def _check_period_transition(self, session, enrollment_id, key):
        records = (
            self.env["training.attendance"]
            .sudo()
            .search(
                [
                    ("session_id", "=", session.id),
                    ("enrollment_id", "=", enrollment_id),
                ]
            )
        )
        legacy = records.filtered(lambda row: row.period_key == "legacy")
        if key == "legacy":
            if records - legacy:
                raise ValidationError(self.env._("Use the half-day attendance records for this session."))
        else:
            self._period(session, key)
            if legacy.event_ids and legacy.event_ids.sorted("id")[-1:].kind != "invalidation":
                raise ValidationError(
                    self.env._("Invalidate the historical attendance with a reason before replacing it with half-days.")
                )

    @api.private
    def _visible_periods(self, session, enrollment_id):
        legacy = (
            self.env["training.attendance"]
            .sudo()
            .search(
                [
                    ("session_id", "=", session.id),
                    ("enrollment_id", "=", enrollment_id),
                    ("period_key", "=", "legacy"),
                ],
                limit=1,
            )
        )
        if legacy.event_ids and legacy.event_ids.sorted("id")[-1:].kind != "invalidation":
            return [
                {
                    "key": "legacy",
                    "label": self.env._("Historical attendance"),
                    "start": session.start_at,
                    "end": session.end_at,
                }
            ]
        return self._periods(session)

    @api.private
    def _day_sessions(self, enrollment, key):
        return enrollment.delivery_id.session_ids.filtered(
            lambda session: not session.cancelled and any(p["key"] == key for p in self._periods(session))
        )

    @api.private
    def _day_definition(self, sessions):
        return hashlib.sha256("|".join(self._definition(s) for s in sessions.sorted("id")).encode()).hexdigest()

    @api.private
    def _declare_halfday(self, enrollment_id, key, *, absent=False, accepted=False, definition=None):
        with self.env.cr.savepoint():
            enrollment = self.env["training.learning.service"]._enrollment(enrollment_id, lock=True)
            sessions = self._day_sessions(enrollment, key).filtered(lambda s: s.attendance_mode != "paper")
            if not sessions or definition != self._day_definition(sessions):
                raise ValidationError(
                    self.env._(
                        "The session or confirmation text changed. Reload and confirm the displayed information."
                    )
                )
            for session in sessions:
                self._declare(
                    enrollment.id,
                    session.id,
                    0,
                    0,
                    accepted=accepted,
                    absent=absent,
                    period_key=key,
                    definition=self._definition(session),
                )
        return True
