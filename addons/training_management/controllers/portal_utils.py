"""Presentation conversions only; all deadlines remain UTC on the server."""

from datetime import datetime
import pytz

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools.misc import format_datetime


def portal_datetime(value, timezone=None):
    timezone = timezone or request.env.user.tz or "UTC"
    return (
        "%s (%s)" % (format_datetime(request.env, fields.Datetime.to_datetime(value), tz=timezone), timezone)
        if value
        else ""
    )


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
