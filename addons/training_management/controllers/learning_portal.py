"""Native authenticated forms; no general portal ORM rights or second frontend."""

from uuid import uuid4

from odoo import http
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools.misc import format_datetime

from .material_portal import TrainingParticipantPortal


def learning_values(enrollment):
    service = request.env["training.learning.service"]
    rows = service._rows(enrollment)
    for row in rows:
        row["key"] = str(uuid4())
        row["deadline"] = (
            format_datetime(request.env, row["deadline"], tz=request.env.user.tz or enrollment.delivery_id.timezone)
            if row["deadline"]
            else False
        )
    required = [r for r in rows if not r["optional"]]
    entries = service._entries(enrollment)
    rows_by_id = {row["id"]: row for row in rows}
    for entry in entries:
        activity = rows_by_id.get(entry["activity_id"])
        entry["review_activity"] = (
            activity
            if activity and entry["kind"] == "submission" and activity["latest_submission"] == entry["id"]
            else False
        )
        entry["key"] = str(uuid4())
        entry["parent_date"] = (
            format_datetime(
                request.env, entry["parent_date"], tz=request.env.user.tz or enrollment.delivery_id.timezone
            )
            if entry["parent_date"]
            else False
        )
        entry["date"] = format_datetime(
            request.env, entry["date"], tz=request.env.user.tz or enrollment.delivery_id.timezone
        )
    return {
        "id": enrollment.id,
        "has_tutor": bool(enrollment.learning_tutor_id or enrollment.delivery_id.learning_tutor_id),
        "activities": rows,
        "entries": list(reversed(entries)),
        "required": len(required),
        "complete": sum(r["complete"] for r in required),
        "key": str(uuid4()),
        "error": False,
        "draft": "",
        "draft_ratings": {},
        "draft_activity": False,
        "draft_kind": False,
    }


class LearningPortal(http.Controller):
    @http.route(
        ["/my/training-tutoring", "/my/training-tutoring/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def tutoring(self, page=1, **kwargs):
        enrollments = request.env["training.learning.service"]._tutored_enrollments()
        pager = portal_pager(url="/my/training-tutoring", total=len(enrollments), page=page, step=40)
        rows = [
            {"id": e.id, "participant": e.participant_id.name, "name": e.delivery_id.name}
            for e in enrollments[pager["offset"] : pager["offset"] + 40]
        ]
        return TrainingParticipantPortal._private(
            request.render("training_management.portal_learning_tutoring", {"enrollments": rows, "pager": pager})
        )

    @http.route("/my/training-tutoring/<int:enrollment_id>", type="http", auth="user", website=True, methods=["GET"])
    def tutoring_detail(self, enrollment_id, **kwargs):
        try:
            enrollment = request.env["training.learning.service"]._enrollment(enrollment_id, tutor=True)
        except (AccessError, MissingError):
            raise request.not_found() from None
        return TrainingParticipantPortal._private(
            request.render(
                "training_management.portal_learning_tutor",
                {
                    "participant": enrollment.participant_id.name,
                    "name": enrollment.delivery_id.name,
                    "learning": learning_values(enrollment),
                    "is_tutor": True,
                },
            )
        )

    @http.route("/my/trainings/<int:enrollment_id>/learning", type="http", auth="user", website=True, methods=["POST"])
    def participant_post(self, enrollment_id, **values):
        return self._post(enrollment_id, values, tutor=False)

    @http.route(
        "/my/training-tutoring/<int:enrollment_id>/learning", type="http", auth="user", website=True, methods=["POST"]
    )
    def tutor_post(self, enrollment_id, **values):
        return self._post(enrollment_id, values, tutor=True)

    def _post(self, enrollment_id, values, *, tutor):
        service = request.env["training.learning.service"]
        kind = values.get("kind")
        allowed = ("correction", "answer") if tutor else ("declaration", "submission", "question")
        if kind not in allowed:
            raise request.not_found()
        try:
            service._enrollment(enrollment_id, tutor=tutor)
            activity_id = int(values.get("activity_id") or 0)
            parent_id = int(values.get("parent_id") or 0)
            revision = int(values.get("revision") or 0)
            if min(activity_id, parent_id, revision) < 0:
                raise ValueError()
        except (AccessError, MissingError, ValueError, TypeError):
            raise request.not_found() from None
        body = values.get("body", "")
        uploaded = request.httprequest.files.get("file")
        try:
            if kind == "declaration":
                service._declare(enrollment_id, activity_id)
            else:
                entry = service._post(
                    enrollment_id,
                    kind,
                    activity_id=activity_id or False,
                    parent_id=parent_id or False,
                    revision=revision,
                    body=body,
                    request_key=values.get("request_key", ""),
                    decision=values.get("decision", False),
                    project_ratings={
                        k.removeprefix("project_rating_"): v
                        for k, v in values.items()
                        if k.startswith("project_rating_")
                    }
                    or None,
                    data=uploaded.read() if uploaded else b"",
                    filename=uploaded.filename if uploaded else "",
                )
        except (AccessError, MissingError):
            raise request.not_found() from None
        except ValidationError as error:
            response = (
                self.tutoring_detail(enrollment_id) if tutor else TrainingParticipantPortal().training(enrollment_id)
            )
            response.qcontext["learning"].update(
                error=str(error),
                draft=body,
                draft_activity=activity_id,
                draft_kind=kind,
                draft_ratings={
                    k.removeprefix("project_rating_"): v for k, v in values.items() if k.startswith("project_rating_")
                },
            )
            response.status_code = 400
            return response
        path = "/my/training-tutoring/%s" if tutor else "/my/trainings/%s"
        target = path % enrollment_id
        if kind == "submission":
            target += "#learning-activity-%s" % activity_id
        elif kind == "correction":
            target += "#learning-entry-%s" % entry.id
        return request.redirect(target, code=303)
