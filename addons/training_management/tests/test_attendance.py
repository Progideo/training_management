"""PRE01–03 under restricted identities, including native binary routes."""

import base64
from io import BytesIO

from PIL import Image, ImageDraw

from datetime import datetime, timedelta
from unittest.mock import patch

from lxml import html

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.misc import limited_field_access_token

from .test_material import MaterialCase, PDF


class AttendanceCase(MaterialCase):
    def setUp(self):
        super().setUp()
        clock = patch("odoo.fields.Datetime.now", return_value=datetime(2027, 1, 4, 11))
        clock.start()
        self.addCleanup(clock.stop)
        # New portal confirmations reuse a drawing explicitly saved by each owner.
        output = BytesIO()
        image = Image.new("RGB", (160, 60), "white")
        ImageDraw.Draw(image).line((10, 40, 120, 10), fill="black", width=3)
        image.save(output, format="PNG")
        self.signature_png = base64.b64encode(output.getvalue()).decode()
        for owner in (self.portal, self.portal_b):
            self.env["training.attendance.signature"].with_user(owner)._save_drawing(self.signature_png, 0)

    def scheduled(self, mode="mixed", instructor=None):
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        session = self.scheduled_session(delivery)
        session.write(
            {"attendance_mode": mode, "end_hour": 11, "instructor_id": (instructor or self.portal_b.partner_id).id}
        )
        delivery.action_confirm(conflict_reason="Fictional overlapping fixture")
        with patch("odoo.fields.Datetime.now", return_value=session.start_at):
            enrollment = self.opened(delivery)
        return delivery, session, enrollment

    def service(self, user=None):
        return self.env["training.attendance.service"].with_user(user or self.portal)

    def declare(self, session, enrollment, start=30, end=120):
        return self.service()._declare(
            enrollment.id, session.id, start, end, accepted=True, definition=self.service()._definition(session)
        )

    def review(self, presence, **values):
        return self.service(self.portal_b)._review(
            presence.session_id.id,
            presence.enrollment_id.id,
            30,
            120,
            revision=presence.revision,
            **values,
            definition=self.service()._definition(presence.session_id),
        )

    def paper(self, session, enrollment, **values):
        return self.service(self.coordinator)._review(
            session.id,
            enrollment.id,
            0,
            120,
            paper=True,
            reason="Fictional signed paper",
            data=PDF,
            filename="signed.pdf",
            **values,
            definition=self.service()._definition(session),
        )


@tagged("post_install", "-at_install")
class TestAttendance(AttendanceCase):
    def test_partial_declaration_review_and_duplicate_do_not_double_minutes(self):
        _, session, enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            presence = self.declare(session, enrollment)
            self.assertEqual(presence.minutes, 0)
            original = presence.event_ids
            self.assertEqual(original.actor_id, self.portal)
            self.assertEqual(original.occurred_at, session.end_at)
            self.assertEqual(original.wording, session.attendance_wording)
            self.assertEqual(self.declare(session, enrollment), presence)
            self.assertEqual(len(presence.event_ids), 1)
            self.review(presence)
            self.assertEqual(presence.minutes, 90)
            self.assertEqual(presence.late_minutes, 30)
            self.paper(session, enrollment, revision=presence.revision)
            self.assertEqual(presence.minutes, 90)
            self.assertEqual(len(presence.event_ids), 3)

            with Form(
                self.env["training.attendance.edit"]
                .with_user(self.coordinator)
                .with_context(default_session_id=session.id, default_filename="check.pdf")
            ) as form:
                form.enrollment_id = enrollment
                form.operation = "correction"
                form.reason = "Fictional correction through native assistant"
                form.data = BinaryBytes(PDF)
                self.assertEqual(form.halfday, "legacy")
                form.absent = True
            wizard = form.record
            self.assertEqual(wizard.revision, presence.revision)
            wizard.action_apply()
            self.assertEqual(presence.minutes, 0)
            self.assertEqual(original, presence.event_ids[:1])
            with self.assertRaises(ValidationError):
                self.declare(session, enrollment, 0, 120)
            with self.assertRaises(ValidationError):
                self.review(presence)

    def test_window_anomaly_requires_explanation_and_keeps_server_time(self):
        """C06 supersedes the old window: late signatures retain their real timestamp."""
        _, session, enrollment = self.scheduled()
        late = session.end_at + timedelta(hours=4)
        with patch("odoo.fields.Datetime.now", return_value=late):
            presence = self.declare(session, enrollment)
            self.assertEqual(presence.state, "pending")
            self.assertEqual(presence.event_ids.occurred_at, late)
            self.review(presence)
            self.assertEqual(presence.state, "validated")
            self.assertFalse(presence.event_ids[:1].anomaly)
        _, second, second_enrollment = self.scheduled()
        self.assertEqual(second.attendance_after, 30)
        with patch("odoo.fields.Datetime.now", return_value=second.end_at + timedelta(minutes=30)):
            timely = self.declare(second, second_enrollment)
            self.assertEqual(timely.state, "pending")
            self.assertFalse(timely.event_ids.anomaly)

    def invalidate(self, presence, user=None, reason="Fictional wrong interval", **values):
        return self.service(user or self.portal_b)._invalidate(
            presence.session_id.id,
            presence.enrollment_id.id,
            reason=reason,
            revision=presence.revision,
            definition=self.service()._definition(presence.session_id),
            **values,
        )

    def test_invalidation_keeps_history_and_requires_new_signature(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.review(presence)
        original = presence.event_ids
        original_values = original.read(["kind", "actor_id", "occurred_at", "start_at", "end_at", "after"])
        old_revision = presence.revision
        self.invalidate(presence)
        self.assertEqual(presence.state, "invalidated")
        self.assertEqual(presence.minutes, 0)
        self.assertFalse(presence.absent)
        decision = presence.event_ids[-1:]
        self.assertEqual(decision.actor_id, self.portal_b)
        self.assertEqual(decision.reason, "Fictional wrong interval")
        self.assertEqual(decision.before, original[-1:].after)
        self.assertEqual(
            original.read(["kind", "actor_id", "occurred_at", "start_at", "end_at", "after"]), original_values
        )
        with self.assertRaises(ValidationError):
            self.service(self.portal_b)._invalidate(
                session.id,
                enrollment.id,
                reason="Stale",
                revision=old_revision,
                definition=self.service()._definition(session),
            )
        self.invalidate(presence)
        self.assertEqual(len(presence.event_ids), 3)
        with self.assertRaises(ValidationError):
            self.review(presence)
        self.declare(session, enrollment, 30, 110)
        self.service(self.portal_b)._review(
            session.id,
            enrollment.id,
            30,
            110,
            revision=presence.revision,
            definition=self.service()._definition(session),
        )
        self.assertEqual(presence.minutes, 80)
        self.assertEqual(len(presence.event_ids), 5)
        self.assertEqual(presence.event_ids[:2], original)
        with self.assertRaises(AccessError):
            decision.write({"reason": "overwrite"})
        with self.assertRaises(ValidationError):
            decision.unlink()

    def test_invalidation_permissions_reason_and_native_coordinator_assistant(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        for user in (self.portal, self.reader, self.internal):
            with self.assertRaises(AccessError):
                self.invalidate(presence, user=user)
        with self.assertRaises(ValidationError):
            self.invalidate(presence, reason="  ")
        with Form(
            self.env["training.attendance.edit"].with_user(self.coordinator).with_context(default_session_id=session.id)
        ) as form:
            form.enrollment_id = enrollment
            form.operation = "invalidation"
            form.reason = "Fictional organizer check"
        form.record.action_apply()
        self.assertEqual(presence.state, "invalidated")
        self.assertEqual(presence.event_ids[-1:].actor_id, self.coordinator)
        _, foreign_session, _ = self.scheduled(instructor=self.portal.partner_id)
        with self.assertRaises(AccessError):
            self.service(self.portal_b)._invalidate(
                foreign_session.id,
                enrollment.id,
                reason="Wrong assignment",
                definition=self.service()._definition(foreign_session),
            )
        self.coordinator.write(
            {"company_id": self.other_company.id, "company_ids": [Command.set(self.other_company.ids)]}
        )
        with self.assertRaises(AccessError):
            self.invalidate(presence, user=self.coordinator)

    def test_late_signature_keeps_access_guards_and_closure_blocks_mutation(self):
        delivery, session, enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_end + timedelta(days=400)):
            with self.assertRaises(AccessError):
                self.declare(session, enrollment)
        presence = self.declare(session, enrollment)
        delivery.action_start()
        delivery.action_deliver()
        self.review(presence)
        delivery.action_close(reason="Fictional final closure")
        original = presence.event_ids
        with self.assertRaises(AccessError):
            self.declare(session, enrollment)
        for user in (self.portal_b, self.coordinator):
            with self.assertRaises(ValidationError):
                self.invalidate(presence, user=user)
        self.assertEqual(presence.event_ids, original)

    def test_interval_bounds_elapsed_time_nonfinite_and_acceptance(self):
        _, session, enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=session.start_at + timedelta(minutes=60)):
            for start, end in ((0, 120), (-1, 30), (30, 30), (40, 30), (0, "nan"), ("inf", 30), (0, 121)):
                with self.assertRaises(ValidationError):
                    self.declare(session, enrollment, start, end)
            with self.assertRaises(ValidationError):
                self.service()._declare(enrollment.id, session.id, 0, 30)
            presence = self.declare(session, enrollment, 0, 30)
            with self.assertRaises(ValidationError):
                self.review(presence)

    def test_paper_then_distinct_trainer_and_justified_correction_preserve_provenance(self):
        _, session, enrollment = self.scheduled("paper")
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            with self.assertRaises(AccessError):
                self.declare(session, enrollment)
            presence = self.paper(session, enrollment)
            original = presence.event_ids
            self.assertEqual(original.data.content, PDF)
            self.assertEqual(presence.minutes, 0)
            self.review(presence)
            review = presence.event_ids[-1:]
            with self.assertRaises(ValidationError):
                self.service(self.coordinator)._review(
                    session.id,
                    enrollment.id,
                    60,
                    120,
                    correction=True,
                    revision=presence.revision,
                    reason="Missing evidence",
                    definition=self.service()._definition(session),
                )
            self.service(self.coordinator)._review(
                session.id,
                enrollment.id,
                60,
                120,
                correction=True,
                revision=presence.revision,
                reason="Fictional corrected interval",
                data=PDF + b" corrected",
                filename="proof.pdf",
                definition=self.service()._definition(session),
            )
            self.assertEqual(presence.minutes, 60)
            self.assertEqual(presence.event_ids[-1:].before, review.after)
            self.assertEqual(original.data.content, PDF)
            self.assertEqual(len(presence.event_ids), 3)

    def test_absence_without_declaration_and_stale_trainer_submission(self):
        _, session, enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            self.service(self.portal_b)._review(
                session.id, enrollment.id, 0, 0, absent=True, definition=self.service()._definition(session)
            )
            presence = self.env["training.attendance"].search([("session_id", "=", session.id)])
            self.assertTrue(presence.absent)
            self.assertEqual(presence.minutes, 0)
            with self.assertRaises(ValidationError):
                self.service(self.portal_b)._review(
                    session.id, enrollment.id, 0, 120, revision=0, definition=self.service()._definition(session)
                )

    def test_permissions_cross_session_reassignment_revocation_and_company(self):
        delivery, session, enrollment = self.scheduled()
        other_delivery, other_session, other_enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            for user in (self.portal_b, self.reader, self.internal):
                with self.assertRaises(AccessError):
                    self.service(user)._declare(enrollment.id, session.id, 0, 120, accepted=True)
            with self.assertRaises(AccessError):
                self.service()._declare(enrollment.id, other_session.id, 0, 120, accepted=True)
            presence = self.declare(session, enrollment)
            for user in (self.portal, self.reader, self.internal, self.coordinator):
                with self.assertRaises(AccessError):
                    self.service(user)._review(
                        session.id,
                        enrollment.id,
                        0,
                        120,
                        revision=presence.revision,
                        definition=self.service()._definition(session),
                    )
            enrollment.action_suspend_access(reason="Fictional suspension")
            with self.assertRaises(AccessError):
                self.declare(session, enrollment)
            # Current instructor identity is rechecked; no session-wide bearer grant.
            session.invalidate_recordset()
            self.portal_b.write(
                {"company_id": self.other_company.id, "company_ids": [Command.set(self.other_company.ids)]}
            )
            with self.assertRaises(AccessError):
                self.review(presence)
            self.assertNotEqual(delivery, other_delivery)
            self.assertNotEqual(enrollment, other_enrollment)

    def test_immutable_api_context_defaults_and_private_evidence(self):
        _, session, enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            service = self.service().with_context(
                default_actor_id=self.coordinator.id, default_occurred_at="2000-01-01", default_data="stolen"
            )
            presence = service._declare(
                enrollment.id, session.id, 30, 120, accepted=True, definition=service._definition(session)
            )
            event = presence.event_ids
            self.assertEqual(event.actor_id, self.portal)
            self.assertEqual(event.occurred_at, session.end_at)
            self.assertFalse(event.data)
            for record in (presence, event):
                with self.assertRaises(AccessError):
                    record.write({})
                with self.assertRaises(AccessError):
                    record.copy()
                with self.assertRaises(ValidationError):
                    record.unlink()
                for user in (self.portal, self.portal_b, self.reader, self.internal):
                    with self.assertRaises(AccessError):
                        record.with_user(user).read()
            with self.assertRaises(AccessError):
                self.env["training.attendance.event"].create({})
            with self.assertRaises(ValidationError):
                session.write({"attendance_after": 30})
            with self.assertRaises(ValidationError):
                self.env["ir.attachment"].create(
                    {"name": "leak", "res_model": event._name, "res_id": event.id, "raw": PDF, "public": True}
                )

    def test_native_configuration_and_paper_assistant(self):
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        with Form(
            self.env["training.session.edit"].with_user(self.coordinator).with_context(default_delivery_id=delivery.id)
        ) as form:
            form.name = "Fictional S07 session"
            form.mode = "remote"
            form.meeting_url = "https://example.invalid/room"
            form.start_date = "2027-01-04"
            form.end_date = "2027-01-04"
            form.attendance_mode = "mixed"
        form.record.action_apply()
        self.assertEqual(delivery.session_ids.attendance_after, 30)

    def test_paper_import_rejects_a_rescheduled_session(self):
        _, session, enrollment = self.scheduled()
        with Form(
            self.env["training.attendance.edit"]
            .with_user(self.coordinator)
            .with_context(default_session_id=session.id, default_filename="signed.pdf")
        ) as form:
            form.enrollment_id = enrollment
            form.data = BinaryBytes(PDF)
            form.reason = "Fictional signed paper"
        session._apply_schedule({"start_hour": 8.5}, reason="Fictional schedule change")
        with self.assertRaisesRegex(ValidationError, "session or confirmation text changed"):
            form.record.action_apply()
        self.assertFalse(self.env["training.attendance"].search([("session_id", "=", session.id)]))

    def test_trainer_self_validation_and_current_assignment(self):
        _, session, enrollment = self.scheduled(instructor=self.portal.partner_id)
        presence = self.declare(session, enrollment)
        with self.assertRaises(AccessError):
            self.service()._review(
                session.id,
                enrollment.id,
                30,
                120,
                revision=presence.revision,
                definition=self.service()._definition(session),
            )
        _, other_session, _ = self.scheduled()
        self.assertTrue(self.service(self.portal_b)._session(other_session.id))
        other_session._apply_schedule(
            {"instructor_id": self.coordinator.partner_id.id}, reason="Fictional reassignment"
        )
        with self.assertRaises(AccessError):
            self.service(self.portal_b)._session(other_session.id)

    def test_foreign_company_cannot_read_or_download_paper(self):
        _, session, enrollment = self.scheduled()
        presence = self.paper(session, enrollment)
        other = new_test_user(
            self.env,
            login="s07_foreign_coordinator",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        for record in (presence, presence.event_ids):
            with self.assertRaises(AccessError):
                record.with_user(other).read()
        policy = self.env["training.document.policy"].with_user(other)
        self.assertFalse(policy._can_read(presence.event_ids))
        self.assertTrue(self.env["training.document.policy"].with_user(self.coordinator)._can_read(presence.event_ids))

    def test_draft_evidence_follows_company_rights_and_cannot_become_an_attachment(self):
        _, session, enrollment = self.scheduled()
        wizard = (
            self.env["training.attendance.edit"]
            .with_user(self.coordinator)
            .create(
                {
                    "session_id": session.id,
                    "enrollment_id": enrollment.id,
                    "reason": "Fictional draft",
                    "data": BinaryBytes(PDF),
                    "filename": "draft.pdf",
                }
            )
        )
        policy = self.env["training.document.policy"].with_user(self.coordinator)
        self.assertTrue(policy._can_read(wizard))
        with self.assertRaises(ValidationError):
            self.env["ir.attachment"].create(
                {"name": "draft.pdf", "res_model": wizard._name, "res_id": wizard.id, "raw": PDF, "public": True}
            )
        self.coordinator.write(
            {"company_id": self.other_company.id, "company_ids": [Command.set(self.other_company.ids)]}
        )
        with self.assertRaises(AccessError):
            wizard.read(["data"])
        self.assertFalse(policy._can_read(wizard))

    def test_draft_cannot_link_an_enrollment_from_another_company(self):
        _, session, _ = self.scheduled()
        course = self.env["training.course"].create(
            {"name": "Fictional foreign course", "company_id": self.other_company.id}
        )
        course.category_id = self.env["training.category"].create(
            {"name": "Fictional foreign category", "company_id": self.other_company.id}
        )
        program = self.program.copy({"course_id": course.id, "version": "R61-B"})
        program.action_validate()
        delivery = self.env["training.delivery"].create(
            {
                "name": "Fictional foreign delivery",
                "company_id": self.other_company.id,
                "program_id": program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 2,
            }
        )
        enrollment = self.env["training.enrollment"].create(
            {"delivery_id": delivery.id, "participant_id": self.customer.id, "free_reason": "Fictional invitation"}
        )
        with self.assertRaises(UserError):
            self.env["training.attendance.edit"].with_user(self.coordinator).create(
                {
                    "session_id": session.id,
                    "enrollment_id": enrollment.id,
                    "reason": "Fictional foreign link",
                    "data": BinaryBytes(PDF),
                    "filename": "draft.pdf",
                }
            )


@tagged("post_install", "-at_install")
class TestAttendanceHttp(AttendanceCase, HttpCase):
    def test_http_invalidation_resigning_and_access_guards(self):
        delivery, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.review(presence)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        path = f"/my/training-sessions/{session.id}/attendance"
        page = html.fromstring(self.url_open(path).content)
        form = page.xpath("//form[input[@name='operation'][@value='invalidate']]")[0]
        payload = {item.get("name"): item.get("value", "") for item in form.xpath(".//input[@name]")}
        self.assertEqual(self.url_open(path, data={**payload, "reason": "Fictional wrong attendance"}).status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(presence.state, "invalidated")
        self.assertEqual(presence.minutes, 0)
        self.authenticate(self.portal.login, self.portal.login)
        path = f"/my/trainings/{enrollment.id}/attendance"
        page = html.fromstring(self.url_open(path).content)
        payload = {item.get("name"): item.get("value", "") for item in page.xpath("//form//input[@name]")}
        payload.update(attendance="present", accepted="yes")
        self.assertEqual(self.url_open(path, data=payload).status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(len(presence.event_ids.filtered(lambda e: e.kind == "declaration")), 1)
        halfdays = self.env["training.attendance"].search(
            [("enrollment_id", "=", enrollment.id), ("period_key", "!=", "legacy")]
        )
        self.assertEqual(len(halfdays.event_ids.filtered(lambda e: e.kind == "declaration")), 1)
        enrollment.action_suspend_access(reason="Fictional restricted access")
        self.assertEqual(self.url_open(path).status_code, 404)
        self.assertEqual(self.url_open(path, data=payload).status_code, 404)

    def test_confirmation_rejects_a_rescheduled_session(self):
        _, session, enrollment = self.scheduled()
        self.authenticate(self.portal.login, self.portal.login)
        path = f"/my/trainings/{enrollment.id}/attendance"
        form = html.fromstring(self.url_open(path).content).xpath("//form[@method='post']")[0]
        payload = {item.get("name"): item.get("value", "") for item in form.xpath(".//input[@type='hidden']")}
        payload.update(accepted="yes", attendance="present")
        session._apply_schedule({"start_hour": 8.5}, reason="Fictional schedule change")
        response = self.url_open(path, data=payload)
        self.env.invalidate_all()
        self.assertFalse(self.env["training.attendance"].search([("session_id", "=", session.id)]))
        french = html.fromstring(response.content).get("lang", "en").startswith("fr")
        expected = (
            "La séance ou le texte de confirmation a changé. Rechargez puis confirmez les informations affichées."
            if french
            else "The session or confirmation text changed. Reload and confirm the displayed information."
        )
        self.assertIn(expected, html.fromstring(response.content).text_content())

    def test_confirmation_rejects_a_changed_session_definition(self):
        _, session, enrollment = self.scheduled()
        self.authenticate(self.portal.login, self.portal.login)
        path = f"/my/trainings/{enrollment.id}/attendance"
        response = self.url_open(path)
        form = html.fromstring(response.content).xpath("//form[@method='post']")[0]
        payload = {item.get("name"): item.get("value", "") for item in form.xpath(".//input[@type='hidden']")}
        payload.update(accepted="yes", attendance="present")
        session._apply_schedule(
            {"attendance_wording": "Fictional changed confirmation text"}, reason="Fictional text change"
        )
        response = self.url_open(path, data=payload)
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        self.assertFalse(self.env["training.attendance"].search([("session_id", "=", session.id)]))
        self.assertIn("alert-danger", response.text)
        page = html.fromstring(response.content)
        payload["definition"] = page.xpath("//input[@name='definition']/@value")[0]
        response = self.url_open(path, data=payload)
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        presence = self.env["training.attendance"].search([("session_id", "=", session.id)])
        self.assertEqual(presence.event_ids.wording, "Fictional changed confirmation text")

    def test_signed_paper_absence_remains_selected_for_trainer_review(self):
        _, session, enrollment = self.scheduled("paper")
        self.paper(session, enrollment, absent=True)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        path = f"/my/training-sessions/{session.id}/attendance"
        response = self.url_open(path)
        page = html.fromstring(response.content)
        self.assertTrue(page.xpath("//option[@value='absent' and @selected]"))
        payload = {
            item.get("name"): item.get("value", "")
            for item in page.xpath("//form[not(input[@name='operation'])]//input[@type='hidden']")
        }
        payload.update(attendance="absent")
        self.assertEqual(self.url_open(path, data=payload).status_code, 200)
        self.env.invalidate_all()
        presence = self.env["training.attendance"].search([("session_id", "=", session.id)])
        self.assertTrue(presence.absent)
        self.assertEqual(presence.minutes, 0)

    def test_draft_evidence_token_never_replaces_current_authorization(self):
        _, session, enrollment = self.scheduled()
        wizard = (
            self.env["training.attendance.edit"]
            .with_user(self.coordinator)
            .create(
                {
                    "session_id": session.id,
                    "enrollment_id": enrollment.id,
                    "reason": "Fictional signed sheet",
                    "data": BinaryBytes(PDF),
                    "filename": "draft.pdf",
                }
            )
        )
        token = limited_field_access_token(wizard, "data", scope="binary")
        url = f"/web/content/{wizard._name}/{wizard.id}/data?access_token={token}"
        self.authenticate(None, None)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(self.coordinator.login, self.coordinator.login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertTrue(response.headers["Content-Disposition"].startswith("attachment"))
        peer = new_test_user(
            self.env, login="r61_peer_coordinator", groups="training_management.group_training_coordinator"
        )
        self.authenticate(peer.login, peer.login)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.coordinator.write(
            {"group_ids": [Command.unlink(self.env.ref("training_management.group_training_coordinator").id)]}
        )
        self.authenticate(self.coordinator.login, self.coordinator.login)
        self.assertEqual(self.url_open(url).status_code, 404)

    def test_review_errors_preserve_the_trainers_interval_and_comment(self):
        """The new half-day choice replaces the former interval input."""
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        path = f"/my/training-sessions/{session.id}/attendance"
        page = html.fromstring(self.url_open(path).content)
        payload = {
            item.get("name"): item.get("value", "")
            for item in page.xpath("//form[not(input[@name='operation'])]//input[@type='hidden']")
        }
        revision = payload["revision"]
        payload.update(revision="0", attendance="absent", reason="Fictional review <private>")
        response = self.url_open(path, data=payload)
        self.assertIn("alert-danger", response.text)
        page = html.fromstring(response.content)
        self.assertTrue(page.xpath("//option[@value='absent' and @selected]"))
        self.assertEqual(page.xpath("//textarea[@name='reason']/text()")[0], payload["reason"])
        payload["revision"] = revision
        self.assertEqual(self.url_open(path, data=payload).status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(presence.minutes, 0)
        self.assertTrue(presence.absent)

    def test_trainer_can_record_an_absence_from_an_empty_native_form(self):
        _, session, enrollment = self.scheduled()
        self.authenticate(self.portal_b.login, self.portal_b.login)
        path = f"/my/training-sessions/{session.id}/attendance"
        response = self.url_open(path)
        page = html.fromstring(response.content)
        self.assertEqual(page.xpath("//input[@name='revision']/@value"), ["0"])
        self.assertFalse(page.xpath("//input[@name='start' or @name='end']"))
        csrf = page.xpath("//input[@name='csrf_token']/@value")[0]
        response = self.url_open(
            path,
            data={
                "csrf_token": csrf,
                "signature_version": "1",
                "enrollment_id": enrollment.id,
                "revision": "0",
                "definition": page.xpath("//input[@name='definition']/@value")[0],
                "attendance": "absent",
                "period_key": page.xpath("//input[@name='period_key']/@value")[0],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        presence = self.env["training.attendance"].search([("session_id", "=", session.id)])
        self.assertTrue(presence.absent)
        self.assertEqual(presence.minutes, 0)

    def test_native_http_scope_csrf_and_evidence_tokens(self):
        _, session, enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            presence = self.paper(session, enrollment, period_key=self.service()._periods(session)[0]["key"])
        event = presence.event_ids
        path = f"/my/trainings/{enrollment.id}/attendance"
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("Fictional mixed session", response.text)
        document = html.fromstring(response.content)
        self.assertTrue(document.xpath("//input[@name='csrf_token']"))
        response = self.url_open(path, data={"session_id": session.id, "accepted": "yes", "start": 0, "end": 120})
        self.assertEqual(response.status_code, 400)
        csrf = document.xpath("//input[@name='csrf_token']/@value")[0]
        definition = document.xpath("//input[@name='definition']/@value")[0]
        response = self.url_open(
            path,
            data={
                "csrf_token": csrf,
                "signature_version": "1",
                "definition": definition,
                "session_id": session.id,
                "accepted": "yes",
                "period_key": presence.period_key,
                "attendance": "present",
            },
        )
        self.assertEqual(response.status_code, 200)
        french = html.fromstring(response.content).get("lang", "en").startswith("fr")
        expected = (
            "Votre déclaration est enregistrée. Contactez le coordinateur pour une correction."
            if french
            else "Your declaration is recorded. Contact the coordinator for a correction."
        )
        self.assertIn(expected, html.fromstring(response.content).text_content())
        self.env.invalidate_all()
        token = limited_field_access_token(event, "data", scope="binary")
        url = f"/web/content/{event._name}/{event.id}/data?access_token={token}"
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(path).status_code, 404)
        trainer_path = f"/my/training-sessions/{session.id}/attendance"
        response = self.url_open(trainer_path)
        self.assertEqual(response.status_code, 200)
        csrf = html.fromstring(response.content).xpath("//input[@name='csrf_token']/@value")[0]
        response = self.url_open(
            trainer_path,
            data={
                "csrf_token": csrf,
                "signature_version": "1",
                "enrollment_id": enrollment.id,
                "revision": presence.revision,
                "definition": html.fromstring(response.content).xpath("//input[@name='definition']/@value")[0],
                "period_key": presence.period_key,
                "attendance": "present",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(presence.minutes, 120)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(self.coordinator.login, self.coordinator.login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertTrue(response.headers["Content-Disposition"].startswith("attachment"))
