"""PRE01–03 under restricted identities, including native binary routes."""

from datetime import datetime, timedelta
from unittest.mock import patch

from lxml import html

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
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
        return self.service()._declare(enrollment.id, session.id, start, end, accepted=True)

    def review(self, presence, **values):
        return self.service(self.portal_b)._review(
            presence.session_id.id, presence.enrollment_id.id, 30, 120, revision=presence.revision, **values
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

            wizard = (
                self.env["training.attendance.edit"]
                .with_user(self.coordinator)
                .create(
                    {
                        "session_id": session.id,
                        "enrollment_id": enrollment.id,
                        "operation": "correction",
                        "reason": "Fictional correction through native assistant",
                        "data": BinaryBytes(PDF),
                        "filename": "check.pdf",
                    }
                )
            )
            wizard._onchange_presence()
            self.assertEqual(wizard.start_minutes, 30)
            self.assertEqual(wizard.end_minutes, 120)
            wizard.start_minutes = 90
            wizard.action_apply()
            self.assertEqual(presence.minutes, 30)
            self.assertEqual(original, presence.event_ids[:1])
            with self.assertRaises(ValidationError):
                self.declare(session, enrollment, 0, 120)
            with self.assertRaises(ValidationError):
                self.review(presence)

    def test_window_anomaly_requires_explanation_and_keeps_server_time(self):
        _, session, enrollment = self.scheduled()
        late = session.end_at + timedelta(hours=4)
        with patch("odoo.fields.Datetime.now", return_value=late):
            presence = self.declare(session, enrollment)
            self.assertEqual(presence.state, "anomaly")
            self.assertEqual(presence.event_ids.occurred_at, late)
            with self.assertRaises(ValidationError):
                self.review(presence)
            self.review(presence, reason="Fictional manual check of late declaration")
            self.assertEqual(presence.state, "validated")
            self.assertTrue(presence.event_ids[:1].anomaly)

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
            )
            self.assertEqual(presence.minutes, 60)
            self.assertEqual(presence.event_ids[-1:].before, review.after)
            self.assertEqual(original.data.content, PDF)
            self.assertEqual(len(presence.event_ids), 3)

    def test_absence_without_declaration_and_stale_trainer_submission(self):
        _, session, enrollment = self.scheduled()
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            self.service(self.portal_b)._review(session.id, enrollment.id, 0, 0, absent=True)
            presence = self.env["training.attendance"].search([("session_id", "=", session.id)])
            self.assertTrue(presence.absent)
            self.assertEqual(presence.minutes, 0)
            with self.assertRaises(ValidationError):
                self.service(self.portal_b)._review(session.id, enrollment.id, 0, 120, revision=0)

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
                    self.service(user)._review(session.id, enrollment.id, 0, 120, revision=presence.revision)
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
            presence = service._declare(enrollment.id, session.id, 30, 120, accepted=True)
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
            form.attendance_after = 30
        form.record.action_apply()
        self.assertEqual(delivery.session_ids.attendance_after, 30)

    def test_trainer_self_validation_and_current_assignment(self):
        _, session, enrollment = self.scheduled(instructor=self.portal.partner_id)
        presence = self.declare(session, enrollment)
        with self.assertRaises(AccessError):
            self.service()._review(session.id, enrollment.id, 30, 120, revision=presence.revision)
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


@tagged("post_install", "-at_install")
class TestAttendanceHttp(AttendanceCase, HttpCase):
    def test_trainer_can_record_an_absence_from_an_empty_native_form(self):
        _, session, enrollment = self.scheduled()
        self.authenticate(self.portal_b.login, self.portal_b.login)
        path = f"/my/training-sessions/{session.id}/attendance"
        response = self.url_open(path)
        page = html.fromstring(response.content)
        self.assertEqual(page.xpath("//input[@name='revision']/@value"), ["0"])
        self.assertEqual(page.xpath("//input[@name='start']/@value"), ["0"])
        csrf = page.xpath("//input[@name='csrf_token']/@value")[0]
        response = self.url_open(
            path,
            data={
                "csrf_token": csrf,
                "enrollment_id": enrollment.id,
                "revision": "0",
                "absent": "yes",
                "start": "0",
                "end": "120",
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
            presence = self.paper(session, enrollment)
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
        response = self.url_open(
            path, data={"csrf_token": csrf, "session_id": session.id, "accepted": "yes", "start": 30, "end": 120}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your declaration is recorded", response.text)
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
                "enrollment_id": enrollment.id,
                "revision": presence.revision,
                "start": 30,
                "end": 120,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(presence.minutes, 90)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(self.coordinator.login, self.coordinator.login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF)
        self.assertIn("no-store", response.headers["Cache-Control"])
