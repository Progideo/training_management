"""Checked portal operations. Elevation never decides who is authorized."""

import hashlib
import json
from datetime import timedelta
from uuid import UUID

from markupsafe import Markup
from psycopg2.errors import SerializationFailure

from odoo import api, fields, models
from odoo.exceptions import AccessError, LockError, ValidationError
from odoo.fields import Domain
from odoo.tools.binary import BinaryBytes
from odoo.tools import SQL

MAX_LEARNING_UPLOAD_SIZE = 20 * 1024 * 1024


class LearningService(models.AbstractModel):
    _name = "training.learning.service"
    _description = "Training Learning Operations"

    @api.private
    def _is_participant(self, enrollment):
        user = self.env.user
        return bool(
            user.active
            and not user._is_public()
            and enrollment.company_id in user.company_ids
            and enrollment.user_id == user
            and enrollment.participant_id == user.partner_id
            and enrollment._effective_state() == "active"
        )

    @api.private
    def _is_tutor(self, enrollment):
        user = self.env.user
        return bool(
            user.active
            and not user._is_public()
            and enrollment.company_id in user.company_ids
            and (enrollment.learning_tutor_id or enrollment.delivery_id.learning_tutor_id) == user
            and enrollment.state == "confirmed"
            and enrollment.delivery_id.state not in ("closed", "cancelled")
        )

    @api.private
    def _enrollment(self, enrollment_id, *, tutor=False, lock=False):
        enrollment = self.env["training.enrollment"].sudo().browse(enrollment_id).exists()
        check = self._is_tutor if tutor else self._is_participant
        if not enrollment or not check(enrollment):
            raise AccessError(self.env._("This private learning record is unavailable."))
        if lock:
            # Parallel learners share the delivery lock; administrative changes
            # still require its exclusive S03 lock. Lock order stays delivery,
            # enrollment. SKIP LOCKED preserves native non-blocking conflicts.
            delivery = enrollment.delivery_id
            locked = self.env.execute_query(
                SQL("SELECT id FROM training_delivery WHERE id = %s FOR SHARE SKIP LOCKED", delivery.id)
            )
            if not locked:
                raise LockError(self.env._("Cannot grab a lock on records"))
            enrollment.lock_for_update(allow_referencing=True)
            # A no-op write is an MVCC fence for this enrollment only: stale
            # snapshots must retry even after the previous lock was released.
            # No business field, timestamp or operation history is rewritten.
            self.env.cr.execute(
                SQL("UPDATE training_enrollment SET write_date = write_date WHERE id = %s", enrollment.id)
            )
            delivery.invalidate_recordset()
            enrollment.invalidate_recordset()
            if not check(enrollment):
                raise AccessError(self.env._("This private learning record is unavailable."))
        return enrollment

    @api.private
    def _tutored_enrollments(self):
        user = self.env.user
        if not user.active or user._is_public():
            return self.env["training.enrollment"]
        return (
            self.env["training.enrollment"]
            .sudo()
            .search(
                [
                    ("company_id", "in", user.company_ids.ids),
                    ("state", "=", "confirmed"),
                    ("delivery_id.state", "not in", ("closed", "cancelled")),
                    "|",
                    ("learning_tutor_id", "=", user.id),
                    "&",
                    ("learning_tutor_id", "=", False),
                    ("delivery_id.learning_tutor_id", "=", user.id),
                ]
            )
        )

    @api.private
    def _evaluation_result(self, enrollment, activity):
        """S06 integration point: return its authoritative score, never a client score.

        No parallel attempt/result model or simulated exam is introduced by S05.
        """
        return None

    @api.private
    def _progress(self, enrollment, activity, *, create=False):
        progress = (
            self.env["training.learning.progress"]
            .sudo()
            .search([("enrollment_id", "=", enrollment.id), ("activity_id", "=", activity.id)], limit=1)
        )
        if not progress and create:
            progress = progress._create_evidence({"enrollment_id": enrollment.id, "activity_id": activity.id})
        return progress

    @api.private
    def _complete(self, enrollment, activity):
        progress = self._progress(enrollment, activity)
        if progress:
            return progress._is_complete()
        if activity.criterion == "evaluation":
            result = self._evaluation_result(enrollment, activity)
            return result is not None and result >= activity.evaluation_threshold
        return False

    @api.private
    def _available(self, enrollment, activity):
        return all(self._complete(enrollment, dependency) for dependency in activity.dependency_ids)

    @api.private
    def _activity(self, enrollment, activity_id):
        activity = self.env["training.learning.activity"].sudo().browse(activity_id).exists()
        if not activity or activity.delivery_id != enrollment.delivery_id:
            raise AccessError(self.env._("This private learning record is unavailable."))
        if not self._available(enrollment, activity):
            raise ValidationError(self.env._("Complete the prerequisite activities first."))
        return activity

    @api.private
    def _declare(self, enrollment_id, activity_id):
        with self.env.cr.savepoint():
            enrollment = self._enrollment(enrollment_id, lock=True)
            activity = self._activity(enrollment, activity_id)
            if activity.criterion != "declaration":
                raise ValidationError(self.env._("Use the completion criterion configured for this activity."))
            progress = self._progress(enrollment, activity, create=True)
            if not progress.declared_at:
                progress._store_evidence({"declared_at": fields.Datetime.now(), "revision": progress.revision + 1})
            return progress

    @api.private
    def _post(
        self,
        enrollment_id,
        kind,
        *,
        activity_id=False,
        body="",
        data=b"",
        filename="",
        request_key="",
        parent_id=False,
        revision=0,
        decision=False,
        project_ratings=None,
    ):
        tutor = kind in ("correction", "answer")
        if kind not in ("submission", "correction", "question", "answer"):
            raise ValidationError(self.env._("Choose a supported learning action."))
        try:
            request_key = str(UUID(request_key))
        except (ValueError, TypeError, AttributeError) as error:
            raise ValidationError(self.env._("Reload this page before submitting your work.")) from error
        body = body.strip()
        filename = filename.replace("\\", "/").split("/")[-1] if data else ""
        if (not body and not data and kind != "correction") or (data and not filename):
            raise ValidationError(self.env._("Enter a message or select a named file."))
        if len(data) > MAX_LEARNING_UPLOAD_SIZE:
            raise ValidationError(self.env._("Select a named file of at most 20 MB."))
        if kind == "correction" and decision not in ("accepted", "changes"):
            raise ValidationError(self.env._("Choose Accepted or Changes Requested."))
        payload = {
            "kind": kind,
            "activity": activity_id,
            "body": body,
            "filename": filename,
            "file": hashlib.sha256(data).hexdigest(),
            "parent": parent_id,
            "decision": decision,
        }
        if project_ratings is not None:
            payload["project_ratings"] = project_ratings
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.env.cr.savepoint():
            enrollment = self._enrollment(enrollment_id, tutor=tutor, lock=True)
            entries = self.env["training.learning.entry"].sudo()
            previous = entries.search(
                [("enrollment_id", "=", enrollment.id), ("request_key", "=", request_key)], limit=1
            )
            if previous:
                if previous.fingerprint != fingerprint or previous.create_uid != self.env.user:
                    raise ValidationError(self.env._("This submission identifier already belongs to different work."))
                if previous.activity_id.project_rubric_id:
                    self._project_snapshot(enrollment, previous.activity_id, kind, project_ratings, body)
                return previous
            activity = (
                self._activity(enrollment, activity_id) if activity_id else self.env["training.learning.activity"]
            )
            project_snapshot = (
                self._project_snapshot(enrollment, activity, kind, project_ratings, body) if activity else False
            )
            parent = entries.browse(parent_id).exists() if parent_id else entries.browse()
            if parent_id and (not parent or parent.enrollment_id != enrollment or parent.activity_id != activity):
                raise AccessError(self.env._("This private learning record is unavailable."))
            progress = (
                self._progress(enrollment, activity, create=True)
                if activity
                else self.env["training.learning.progress"]
            )
            if kind in ("submission", "correction"):
                if not activity or activity.criterion not in ("submission", "validation"):
                    raise ValidationError(
                        self.env._("This activity does not accept exercise submissions or corrections.")
                    )
                if progress.revision != revision or parent != progress.latest_submission_id:
                    raise ValidationError(self.env._("New work was recorded. Reload before continuing."))
            if kind == "answer" and (not parent or parent.kind != "question"):
                raise ValidationError(self.env._("Reply to the exact private help request."))
            if kind == "question" and parent:
                raise ValidationError(self.env._("Create a new private help request instead of changing its origin."))
            entry = entries._create_evidence(
                {
                    "enrollment_id": enrollment.id,
                    "activity_id": activity.id,
                    "kind": kind,
                    "project_snapshot": project_snapshot,
                    "project_digest": hashlib.sha256(
                        json.dumps(project_snapshot, sort_keys=True, ensure_ascii=False).encode()
                    ).hexdigest()
                    if project_snapshot
                    else False,
                    "parent_id": parent.id,
                    "request_key": request_key,
                    "fingerprint": fingerprint,
                    "decision": decision if kind == "correction" else False,
                    "data": BinaryBytes(data) if data else False,
                    "filename": filename,
                    "sha256": hashlib.sha256(data).hexdigest() if data else False,
                }
            )
            # Native mail.message stores the private text; no followers, recipient
            # list or delivery/enrollment chatter receives it, and no SMTP is called.
            message = self.env["mail.message"]._create_learning_message(
                entry, Markup('<p style="white-space: pre-wrap">%s</p>') % body
            )
            entry.invalidate_recordset(["data"])
            entry._store_evidence(
                {
                    "message_id": message.id,
                    "sealed_at": fields.Datetime.now(),
                    "sha256": hashlib.sha256(entry.data.content).hexdigest() if data else False,
                }
            )
            if kind == "submission":
                progress._store_evidence(
                    {"latest_submission_id": entry.id, "state": "submitted", "revision": progress.revision + 1}
                )
            elif kind == "correction":
                progress._store_evidence(
                    {"state": "validated" if decision == "accepted" else "changes", "revision": progress.revision + 1}
                )
            if kind in ("submission", "question"):
                recipient = enrollment.learning_tutor_id or enrollment.delivery_id.learning_tutor_id
            else:
                recipient = enrollment.user_id
            self.env["training.learning.notice"]._queue(enrollment, "entry:%s" % entry.id, recipient, entry=entry)
            return entry

    @api.private
    def _deadline(self, enrollment, activity):
        days = activity.due_days or enrollment.delivery_id.learning_due_days
        return enrollment.access_start + timedelta(days=days) if days and enrollment.access_start else False

    @api.private
    def _rows(self, enrollment):
        """Only call after the exact participant/tutor grant; return plain values."""
        rows = []
        for activity in enrollment.delivery_id.learning_activity_ids.sorted(lambda a: (a.sequence, a.id)):
            progress = self._progress(enrollment, activity)
            reference = activity.material_assignment_id
            material = reference.material_id
            rows.append(
                {
                    "id": activity.id,
                    "name": activity.name,
                    "instructions": activity.instructions,
                    "criterion": activity.criterion,
                    "criterion_label": dict(activity._fields["criterion"]._description_selection(self.env))[
                        activity.criterion
                    ],
                    "optional": activity.optional,
                    "available": self._available(enrollment, activity),
                    "complete": self._complete(enrollment, activity),
                    "deadline": self._deadline(enrollment, activity),
                    "state": progress.state if progress else "pending",
                    "revision": progress.revision if progress else 0,
                    "latest_submission": progress.latest_submission_id.id if progress else False,
                    "material_url": f"/web/content/training.material/{material.id}/data?download=true&filename_field=filename"
                    if material and material.frozen_at and not material.withdrawn and not reference.withdrawn
                    else False,
                }
            )
        return rows

    @api.private
    def _entries(self, enrollment):
        return [
            {
                "project_snapshot": e.project_snapshot,
                "id": e.id,
                "kind": e.kind,
                "author": e.create_uid.name,
                "date": e.create_date,
                "activity": e.activity_id.name,
                "activity_id": e.activity_id.id,
                "body": e.message_id.body,
                "parent": e.parent_id.id,
                "parent_date": e.parent_id.create_date if e.parent_id else False,
                "decision": e.decision,
                "filename": e.filename,
                "file_url": f"/web/content/training.learning.entry/{e.id}/data?download=true&filename_field=filename"
                if e.filename
                else False,
            }
            for e in self.env["training.learning.entry"]
            .sudo()
            .search(Domain("enrollment_id", "=", enrollment.id) & self._project_entry_domain())
        ]

    @api.private
    def _last_activity(self, enrollment):
        entry = (
            self.env["training.learning.entry"]
            .sudo()
            .search(
                [
                    ("enrollment_id", "=", enrollment.id),
                    ("kind", "in", ("submission", "question")),
                ],
                order="create_date desc, id desc",
                limit=1,
            )
        )
        declarations = (
            self.env["training.learning.progress"]
            .sudo()
            .search([("enrollment_id", "=", enrollment.id), ("declared_at", "!=", False)])
            .mapped("declared_at")
        )
        dates = [enrollment.access_start, entry.create_date if entry else False, *declarations]
        return max(date for date in dates if date)

    @api.private
    def _reminder_due(self, enrollment, now=None):
        now = now or fields.Datetime.now()
        delivery = enrollment.delivery_id
        if (
            enrollment._effective_state(now) != "active"
            or not delivery.learning_inactivity_days
            or not delivery.learning_reminder_days
        ):
            return False
        last = self._last_activity(enrollment)
        if now < last + timedelta(days=delivery.learning_inactivity_days):
            return False
        required = delivery.learning_activity_ids.filtered(lambda a: not a.optional and a.criterion != "evaluation")
        return bool(any(not self._complete(enrollment, a) and self._available(enrollment, a) for a in required))

    @api.model
    def _cron_reminders(self):
        # Native ir.cron schedules delivery; business intervals are explicit offer
        # settings, disabled by default, not arbitrary per-customer constants.
        now = fields.Datetime.now()
        enrollments = (
            self.env["training.enrollment"]
            .sudo()
            .search(
                [
                    ("access_state", "=", "active"),
                    ("delivery_id.learning_inactivity_days", ">", 0),
                ]
            )
        )
        for enrollment in enrollments:
            try:
                with self.env.cr.savepoint():
                    delivery = enrollment.delivery_id.try_lock_for_update()
                    if not delivery:
                        continue
                    delivery._serialize()
                    enrollment.invalidate_recordset()
                    if not self._reminder_due(enrollment, now):
                        continue
                    last = self._last_activity(enrollment)
                    first_due = last + timedelta(days=delivery.learning_inactivity_days)
                    window = int((now - first_due).total_seconds() // (delivery.learning_reminder_days * 86400))
                    key = "reminder:%s:%s" % (fields.Datetime.to_string(last), window)
                    self.env["training.learning.notice"]._queue(enrollment, key, enrollment.user_id)
            except SerializationFailure:
                # Another transaction committed after this cron's snapshot.
                # Leave this delivery to the next fresh run; retain unrelated
                # reminders already queued in this transaction.
                continue
