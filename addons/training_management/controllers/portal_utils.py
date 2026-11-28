"""Presentation conversions only; all deadlines remain UTC on the server."""

from datetime import datetime
import pytz

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools.misc import format_datetime


def portal_timezone_note(timezone):
    """Return the zone name only when it differs from the reader's own zone."""
    own = request.env.user.tz or "UTC"
    return timezone if timezone and timezone != own else ""


def portal_datetime(value, timezone=None):
    """Short local date and time, without seconds; the zone is named only if it is not the reader's."""
    timezone = timezone or request.env.user.tz or "UTC"
    if not value:
        return ""
    text = format_datetime(request.env, fields.Datetime.to_datetime(value), tz=timezone, dt_format="short")
    note = portal_timezone_note(timezone)
    return "%s (%s)" % (text, note) if note else text


def portal_period(start, end, timezone=None):
    """Readable session period, e.g. « ven. 27 nov. 2026 · 09:00 – 17:00 »."""
    timezone = timezone or request.env.user.tz or "UTC"
    if not start:
        return ""
    env = request.env
    start = fields.Datetime.to_datetime(start)
    end = fields.Datetime.to_datetime(end) if end else False
    day = format_datetime(env, start, tz=timezone, dt_format="EEE d MMM y")
    start_time = format_datetime(env, start, tz=timezone, dt_format="HH:mm")
    if not end:
        return "%s · %s" % (day, start_time)
    end_day = format_datetime(env, end, tz=timezone, dt_format="EEE d MMM y")
    end_time = format_datetime(env, end, tz=timezone, dt_format="HH:mm")
    if end_day == day:
        return "%s · %s – %s" % (day, start_time, end_time)
    return "%s, %s → %s, %s" % (day, start_time, end_day, end_time)


def local_deadline(value, timezone):
    try:
        local = datetime.strptime(value, "%Y-%m-%dT%H:%M")
        return pytz.timezone(timezone).localize(local, is_dst=None).astimezone(pytz.UTC).replace(tzinfo=None)
    except (ValueError, TypeError, pytz.UnknownTimeZoneError, pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
        raise ValidationError(
            request.env._("Choose a valid local date and time. An ambiguous or nonexistent time must be changed.")
        ) from None


def session_navigation(values):
    from urllib.parse import urlencode

    period = values.get("filterby", "upcoming")
    period = period if period in ("upcoming", "past", "all") else "upcoming"
    try:
        page = max(1, int(values.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    return urlencode({"filterby": period, "page": page})
