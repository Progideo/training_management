from odoo import fields, http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools.misc import format_datetime

from .material_portal import TrainingParticipantPortal
from .portal_utils import session_navigation


class AttendancePortal(http.Controller):
    @http.route(
        "/my/trainings/<int:enrollment_id>/attendance", type="http", auth="user", website=True, methods=["GET", "POST"]
    )
    def participant(self, enrollment_id, **post):
        service = request.env["training.attendance.service"]
        try:
            enrollment = request.env["training.learning.service"]._enrollment(enrollment_id)
            error = False
            if request.httprequest.method == "POST":
                try:
                    self._check_choice(post)
                    service._sign_halfday(
                        enrollment.id,
                        post.get("period_key"),
                        signature_version=post.get("signature_version"),
                        absent=post.get("attendance") == "absent",
                        accepted=post.get("accepted") == "yes",
                        definition=post.get("definition"),
                    )
                    return TrainingParticipantPortal._private(
                        request.redirect(request.httprequest.path + "?saved=1#attendance-feedback")
                    )
                except (ValueError, ValidationError) as exc:
                    error = str(exc) if isinstance(exc, ValidationError) else request.env._("Choose a valid session.")
            sessions = enrollment.delivery_id.session_ids.filtered(lambda s: not s.cancelled)
            raw_rows = self._all_rows(sessions, enrollment)
            rows = self._participant_rows(sessions, enrollment, raw_rows=raw_rows)
            if error:
                self._draft(rows, post, trainer=False)
        except (AccessError, MissingError):
            raise request.not_found() from None
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_attendance",
                {
                    **self._table_values(raw_rows, trainer=False),
                    "rows": rows,
                    "error": error,
                    "saved": post.get("saved") == "1",
                    "trainer": False,
                    "name": enrollment.delivery_id.name,
                    "attendance_back": f"/my/trainings/{enrollment.id}",
                },
            )
        )

    @http.route(
        "/my/training-sessions/<int:session_id>/attendance",
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
    )
    def trainer(self, session_id, **post):
        service = request.env["training.attendance.service"]
        try:
            session = service._session(session_id)
            error = False
            if request.httprequest.method == "POST":
                try:
                    if post.get("operation") != "invalidate":
                        self._check_choice(post)
                    operation = service._invalidate if post.get("operation") == "invalidate" else service._sign_review
                    key = post.get("period_key", "")
                    interval = (
                        ()
                        if post.get("operation") == "invalidate"
                        else (0, 0)
                        if post.get("attendance") == "absent"
                        else self._review_interval(session, int(post.get("enrollment_id", 0)), key)
                    )
                    options = (
                        {}
                        if post.get("operation") == "invalidate"
                        else {
                            "absent": post.get("attendance") == "absent",
                            "signature_version": post.get("signature_version"),
                        }
                    )
                    operation(
                        session.id,
                        int(post.get("enrollment_id", 0)),
                        *interval,
                        **options,
                        revision=int(post.get("revision", 0)),
                        period_key=key,
                        definition=post.get("definition"),
                        reason=post.get("reason", ""),
                    )
                    return TrainingParticipantPortal._private(
                        request.redirect(
                            request.httprequest.path + "?saved=1&" + session_navigation(post) + "#attendance-feedback"
                        )
                    )
                except (ValueError, ValidationError) as exc:
                    error = (
                        str(exc) if isinstance(exc, ValidationError) else request.env._("Choose a valid participant.")
                    )
            enrollments = session.delivery_id.enrollment_ids.filtered(lambda e: e.state == "confirmed")
            rows = self._all_rows(session, enrollments)
            if error:
                self._draft(rows, post, trainer=True)
        except (AccessError, MissingError):
            raise request.not_found() from None
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_attendance",
                {
                    **self._table_values(rows, trainer=True, enrollments=enrollments),
                    "matrix_url": f"/my/training-dashboard/{session.delivery_id.id}/attendance",
                    "rows": rows,
                    "error": error,
                    "saved": post.get("saved") == "1",
                    "trainer": True,
                    "name": session.name,
                    "attendance_back": f"/my/training-sessions/{session.id}?{session_navigation(post)}",
                },
            )
        )

    @staticmethod
    def _check_choice(post):
        if post.get("attendance") not in ("present", "absent"):
            raise ValidationError(request.env._("Choose present or absent for this half-day."))

    @staticmethod
    def _review_interval(session, enrollment_id, key):
        if key != "legacy":
            return 0, 0  # the server derives the complete planned half-day
        presence = (
            request.env["training.attendance"]
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
        last = presence.event_ids.filtered(lambda e: e.start_at and e.end_at).sorted("id")[-1:]
        if not last:
            raise ValidationError(request.env._("There is no historical declaration to validate."))
        return (
            (last.start_at - session.start_at).total_seconds() / 60,
            (last.end_at - session.start_at).total_seconds() / 60,
        )

    def _draft(self, rows, post, *, trainer):
        for row in rows:
            if row["period_key"] == post.get("period_key") and (
                not trainer or str(row["enrollment_id"]) == post.get("enrollment_id")
            ):
                row.update(absent=post.get("attendance") == "absent", reason=post.get("reason", ""), error=True)

    def _participant_rows(self, sessions, enrollment, raw_rows=None):
        service = request.env["training.attendance.service"]
        grouped = {}
        for row in raw_rows if raw_rows is not None else self._rows(sessions, enrollment):
            # Historical intervals remain separately reviewable; no history is reinterpreted.
            key = (row["period_key"], row["mode"] == "paper", row["session_id"] if row["period_key"] == "legacy" else 0)
            grouped.setdefault(key, []).append(row)
        result = []
        for rows in grouped.values():
            row = dict(rows[0])
            day_sessions = sessions.filtered(lambda session: session.id in [r["session_id"] for r in rows])
            row.update(
                name=" · ".join(r["name"] for r in rows),
                timezone=" / ".join(dict.fromkeys(r["timezone"] for r in rows)),
                declared=all(r["declared"] for r in rows),
                minutes=sum(r["minutes"] for r in rows),
                history=[event for r in rows for event in r["history"]],
                wording=" ".join(dict.fromkeys(r["wording"] for r in rows)),
                definition=service._day_definition(day_sessions),
                state=self._group_state(rows),
                elapsed=all(r["elapsed"] for r in rows),
                signatures=[sig for r in rows for sig in r["signatures"]],
                schedule=[part for r in rows for part in r["schedule"]],
            )
            result.append(row)
        return result

    @staticmethod
    def _group_state(rows):
        if all(row["validated"] for row in rows):
            return request.env._("Validated")
        if any(row["validated"] for row in rows):
            return request.env._("Partially validated")
        if any(row["invalidated"] for row in rows):
            return request.env._("Declaration invalidated")
        if all(row["has_source"] for row in rows):
            return request.env._("Pending Review")
        if all(row["mode"] == "paper" for row in rows):
            return request.env._("Signed paper expected")
        return request.env._("To declare")

    def _table_values(self, rows, *, trainer, enrollments=None):
        from .attendance_matrix import attendance_matrix

        signature = request.env["training.attendance.signature"]._current()
        return {
            "matrix": attendance_matrix(
                rows,
                collective=trainer,
                view="all",
                people=[{"id": e.id, "name": e.participant_id.name} for e in enrollments or []],
            ),
            "signature_version": signature.version or 0,
            "has_signature": bool(signature.drawing),
        }

    def _all_rows(self, sessions, enrollments):
        # Read once for this already-authorized population; event fields prefetch
        # across all records, rather than one search per participant/session.
        presences = (
            request.env["training.attendance"]
            .sudo()
            .search([("session_id", "in", sessions.ids), ("enrollment_id", "in", enrollments.ids)])
        )
        mapping = {(p.session_id.id, p.enrollment_id.id, p.period_key): p for p in presences}
        return [row for enrollment in enrollments for row in self._rows(sessions, enrollment, mapping)]

    def _rows(self, sessions, enrollment, mapping=None):
        rows = []
        service = request.env["training.attendance.service"]
        for session in sessions:
            legacy = mapping.get((session.id, enrollment.id, "legacy")) if mapping is not None else None
            if mapping is None:
                periods = service._visible_periods(session, enrollment.id)
            elif legacy and legacy.event_ids and legacy.event_ids.sorted("id")[-1:].kind != "invalidation":
                periods = [
                    {
                        "key": "legacy",
                        "label": request.env._("Historical attendance"),
                        "start": session.start_at,
                        "end": session.end_at,
                    }
                ]
            else:
                periods = service._periods(session)
            for period in periods:
                presence = (
                    mapping.get((session.id, enrollment.id, period["key"]), request.env["training.attendance"])
                    if mapping is not None
                    else (
                        request.env["training.attendance"]
                        .sudo()
                        .search(
                            [
                                ("session_id", "=", session.id),
                                ("enrollment_id", "=", enrollment.id),
                                ("period_key", "=", period["key"]),
                            ],
                            limit=1,
                        )
                    )
                )
                events = presence.event_ids.sorted("id")
                last = events[-1:]
                invalidation = events.filtered(lambda e: e.kind == "invalidation")[-1:]
                sources = events.filtered(
                    lambda event: event.kind in ("declaration", "paper") and event.id > (invalidation.id or 0)
                )
                tz = session.timezone
                rows.append(
                    {
                        "anchor": f"attendance-{enrollment.id}-{session.id}-{period['key']}",
                        "review_url": f"/my/training-sessions/{session.id}/attendance#attendance-{enrollment.id}-{session.id}-{period['key']}"
                        if session.instructor_id == request.env.user.partner_id
                        else False,
                        "schedule": [
                            {
                                "name": session.name,
                                "start": format_datetime(request.env, period["start"], tz=session.timezone),
                                "end": format_datetime(request.env, period["end"], tz=session.timezone),
                                "timezone": session.timezone,
                            }
                        ],
                        "start": format_datetime(request.env, period["start"], tz=session.timezone),
                        "end": format_datetime(request.env, period["end"], tz=session.timezone),
                        "signatures": [
                            {
                                "id": event.id,
                                "digest": event.signature_digest,
                                "actor": event.actor_id.name,
                                "session": session.name,
                                "absent": event.absent,
                            }
                            for event in sources
                            if event.kind == "declaration" and event.signature
                        ],
                        "anomaly": presence.state == "anomaly" if presence else False,
                        "session_id": session.id,
                        "enrollment_id": enrollment.id,
                        "period_key": period["key"],
                        "period": period["label"],
                        "name": session.name,
                        "participant": enrollment.participant_id.name,
                        "timezone": tz,
                        "wording": session.attendance_wording,
                        "definition": service._definition(session),
                        "mode": session.attendance_mode,
                        "revision": presence.revision if presence else 0,
                        "absent": bool(last.absent),
                        "reason": "",
                        "error": False,
                        "has_source": bool(sources),
                        "invalidated": last.kind == "invalidation",
                        "elapsed": fields.Datetime.now() >= period["end"],
                        "can_review": enrollment.user_id != request.env.user
                        and request.env.user not in sources.actor_id,
                        "minutes": presence.minutes if presence else 0,
                        "state": dict(presence._fields["state"]._description_selection(request.env)).get(
                            presence.state, request.env._("Not Declared")
                        )
                        if presence
                        else request.env._("Not Declared"),
                        "declared": bool(
                            events.filtered(lambda e: e.kind == "declaration" and e.id > (invalidation.id or 0))
                        ),
                        "can_invalidate": bool(
                            events.filtered(lambda e: e.kind in ("declaration", "paper"))
                            and last.kind != "invalidation"
                            and enrollment.user_id != request.env.user
                        ),
                        "validated": presence.state == "validated" if presence else False,
                        "history": [
                            {
                                "kind": dict(e._fields["kind"]._description_selection(request.env))[e.kind],
                                "date": format_datetime(request.env, e.occurred_at, tz=tz),
                                "actor": e.actor_id.name,
                                "signature_id": e.id if e.signature else False,
                                "wording": e.wording,
                                "status": (request.env._("Absent") if e.absent else request.env._("Present"))
                                if e.kind != "invalidation"
                                else False,
                                "anomaly": e.anomaly,
                                "reason": e.reason,
                            }
                            for e in events
                        ],
                    }
                )
        return rows
