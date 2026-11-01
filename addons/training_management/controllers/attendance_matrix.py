"""Read-only attendance matrix and private, freshly authorized signature images."""

from datetime import date, timedelta

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools.misc import format_date

from .attendance_portal import AttendancePortal
from .material_portal import TrainingParticipantPortal


def attendance_cell(rows):
    """Project all constituent sessions; a drawing never means trainer approval."""
    count = len(rows)
    validated = sum(row["validated"] for row in rows)
    if not rows:
        code, label = "none", request.env._("Not scheduled")
    elif all(row["validated"] for row in rows):
        if all(row["absent"] for row in rows):
            code, label = "absent", request.env._("Absence validated")
        elif any(row["absent"] for row in rows):
            code, label = "partial", request.env._("Mixed attendance — all sessions reviewed")
        else:
            code, label = "validated", request.env._("Attendance validated")
    elif validated:
        code, label = "partial", request.env._("Partially validated — %(done)s/%(total)s", done=validated, total=count)
    elif any(row["invalidated"] for row in rows):
        code, label = "invalidated", request.env._("Declaration invalidated")
    elif any(row.get("anomaly") for row in rows):
        code, label = "anomaly", request.env._("Anomaly to review")
    elif not all(row["elapsed"] for row in rows):
        code, label = "future", request.env._("Upcoming")
    elif all(row["has_source"] for row in rows):
        code, label = "pending", request.env._("Declaration recorded — review expected")
    elif all(row["mode"] == "paper" for row in rows):
        code, label = "paper", request.env._("Signed paper expected")
    else:
        code, label = "declare", request.env._("To sign")
    signatures = {}
    for row in rows:
        for signature in row.get("signatures", []):
            signatures.setdefault((signature["digest"], signature["absent"]), signature)
    return {
        "code": code,
        "label": label,
        "rows": rows,
        "signatures": list(signatures.values()),
        "minutes": sum(row["minutes"] for row in rows),
    }


def attendance_matrix(rows, *, collective=False, people=None, start=None, view="week"):
    keys = sorted({row["period_key"][:10] for row in rows if row["period_key"] != "legacy"})
    selected = date.fromisoformat(start) if start else date.fromisoformat(keys[0]) if keys else date.today()
    if view not in ("day", "week", "all"):
        raise ValueError("Invalid attendance period")
    if view == "week":
        selected -= timedelta(days=selected.weekday())
    dates = [date.fromisoformat(key) for key in keys]
    if view != "all":
        dates = [selected + timedelta(days=n) for n in range(1 if view == "day" else 7)]
    columns = [{"key": day.isoformat(), "label": format_date(request.env, day)} for day in dates]
    grouped = {}
    for row in rows:
        grouped.setdefault((row["enrollment_id"], row["period_key"]), []).append(row)
    lines = []
    if collective:
        for person in people or []:
            lines.append(
                {
                    "label": person["name"],
                    "cells": [
                        attendance_cell(grouped.get((person["id"], day["key"] + "-" + half), []))
                        for day in columns
                        for half in ("am", "pm")
                    ],
                }
            )
    else:
        for day in columns:
            lines.append(
                {
                    "label": day["label"],
                    "cells": [
                        attendance_cell([row for row in rows if row["period_key"] == day["key"] + "-" + half])
                        for half in ("am", "pm")
                    ],
                }
            )
    counters = {"declare": 0, "pending": 0, "anomaly": 0}
    for line in lines:
        for cell in line["cells"]:
            counters["declare"] += any(
                r["elapsed"] and not r["validated"] and not r["has_source"] for r in cell["rows"]
            )
            counters["pending"] += any(not r["validated"] and r["has_source"] for r in cell["rows"])
            counters["anomaly"] += any(r["invalidated"] or r.get("anomaly") for r in cell["rows"])
    return {
        "columns": columns,
        "lines": lines,
        "collective": collective,
        "counters": counters,
        "start": selected.isoformat(),
        "view": view,
        "legacy": [row for row in rows if row["period_key"] == "legacy"],
    }


class AttendanceMatrixPortal(http.Controller):
    @http.route(
        "/my/training-dashboard/<int:delivery_id>/attendance", type="http", auth="user", website=True, methods=["GET"]
    )
    def matrix(self, delivery_id, **kwargs):
        try:
            service = request.env["training.dashboard.service"]
            delivery = service._delivery(delivery_id)
            sessions = service._sessions(delivery)
            enrollments = delivery.enrollment_ids.filtered(lambda e: e.state == "confirmed")
            rows = AttendancePortal()._all_rows(sessions, enrollments)
            matrix = attendance_matrix(
                rows,
                collective=True,
                people=[{"id": e.id, "name": e.participant_id.name} for e in enrollments],
                start=kwargs.get("start"),
                view=kwargs.get("view", "week"),
            )
            return TrainingParticipantPortal._private(
                request.render(
                    "training_management.portal_attendance_matrix",
                    {
                        "matrix": matrix,
                        "name": delivery.name,
                        "delivery_id": delivery.id,
                        "attendance_back": f"/my/training-dashboard/{delivery.id}",
                    },
                )
            )
        except (AccessError, MissingError):
            raise request.not_found() from None
        except ValueError:
            return TrainingParticipantPortal._private(
                request.make_response(request.env._("Choose a valid date and attendance period."), status=400)
            )

    @http.route("/my/training-signature", type="http", auth="user", website=True, methods=["GET", "POST"])
    def personal_signature(self, **post):
        service = request.env["training.attendance.signature"]
        error = False
        try:
            if request.httprequest.method == "POST":
                try:
                    if post.get("accepted") != "yes":
                        raise ValidationError(request.env._("Confirm the personal use of this signature."))
                    if post.get("operation") not in ("save", "delete"):
                        raise ValidationError(request.env._("Choose a signature operation."))
                    drawing = post.get("drawing") if post.get("operation") == "save" else False
                    if post.get("operation") == "save" and not drawing:
                        raise ValidationError(request.env._("Draw or upload your personal signature."))
                    service._save_drawing(drawing, post.get("version"))
                    return TrainingParticipantPortal._private(request.redirect("/my/training-signature?saved=1"))
                except ValidationError as exc:
                    error = str(exc)
            signature = service._current()
            return TrainingParticipantPortal._private(
                request.render(
                    "training_management.portal_personal_signature",
                    {
                        "version": signature.version or 0,
                        "has_signature": bool(signature.drawing),
                        "error": error,
                        "saved": post.get("saved") == "1",
                    },
                )
            )
        except AccessError:
            raise request.not_found() from None

    @http.route(
        ["/my/training-signature/image", "/my/training-attendance-signature/<int:event_id>"],
        type="http",
        auth="user",
        methods=["GET"],
    )
    def signature_image(self, event_id=None, **kwargs):
        try:
            if event_id is None:
                data = request.env["training.attendance.signature"]._current().drawing
            else:
                event = request.env["training.attendance.event"].sudo().browse(event_id).exists()
                if not event:
                    raise AccessError(request.env._("This attendance signature is unavailable."))
                presence = event.attendance_id
                if presence.enrollment_id.user_id == request.env.user:
                    request.env["training.learning.service"]._enrollment(presence.enrollment_id.id)
                else:
                    service = request.env["training.dashboard.service"]
                    delivery = service._delivery(presence.session_id.delivery_id.id)
                    if presence.session_id not in service._sessions(delivery):
                        raise AccessError(request.env._("This attendance signature is unavailable."))
                data = event.signature
            if not data:
                raise AccessError(request.env._("This attendance signature is unavailable."))
            response = request.make_response(
                bytes(data),
                headers=[
                    ("Content-Type", "image/png"),
                    ("X-Content-Type-Options", "nosniff"),
                    ("Content-Disposition", 'inline; filename="signature.png"'),
                ],
            )
            return TrainingParticipantPortal._private(response)
        except (AccessError, MissingError):
            raise request.not_found() from None
