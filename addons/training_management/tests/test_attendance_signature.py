"""Signed half-days: snapshot preservation, role boundaries and actual portal tables."""

import base64
from types import SimpleNamespace
from unittest.mock import patch

from lxml import html

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged

from .test_attendance import AttendanceCase
from ..controllers.attendance_matrix import attendance_matrix
from ..controllers.attendance_portal import AttendancePortal


@tagged("post_install", "-at_install")
class TestAttendanceSignatures(AttendanceCase, HttpCase):
    def sign(self, session, enrollment, **values):
        return self.service()._sign_halfday(
            enrollment.id,
            self.service()._periods(session)[0]["key"],
            signature_version=1,
            accepted=True,
            definition=self.service()._day_definition(session),
            **values,
        )

    def test_snapshot_replacement_deletion_and_stale_confirmation(self):
        _, session, enrollment = self.scheduled()
        self.sign(session, enrollment)
        presence = self.env["training.attendance"].search([("enrollment_id", "=", enrollment.id)])
        declaration = presence.event_ids
        original = declaration.read(["signature", "signature_digest", "signature_version", "actor_id", "wording"])
        self.service(self.portal_b)._sign_review(
            session.id,
            enrollment.id,
            0,
            0,
            signature_version=1,
            period_key=presence.period_key,
            revision=presence.revision,
            definition=self.service()._definition(session),
        )
        self.assertEqual(presence.minutes, 120)
        self.assertEqual(presence.event_ids[-1:].signature_version, 1)
        self.assertTrue(presence.event_ids[-1:].wording)
        personal = self.env["training.attendance.signature"].with_user(self.portal)
        personal._save_drawing(self.signature_png, 1)
        personal._save_drawing(False, 2)
        self.assertFalse(personal._current().drawing)
        self.assertEqual(declaration.read(list(original[0].keys())), original)
        with self.assertRaises(ValidationError):
            self.sign(session, enrollment)
        with self.assertRaises(AccessError):
            personal.search([])
        with self.assertRaises(AccessError):
            declaration.with_user(self.portal).write({"signature": False})

    def test_invalid_png_and_missing_signature_never_create_attendance(self):
        _, session, enrollment = self.scheduled()
        personal = self.env["training.attendance.signature"].with_user(self.portal)
        for value in ("bad", base64.b64encode(b"<svg/> ").decode()):
            with self.assertRaises(ValidationError):
                personal._save_drawing(value, 1)
        personal._save_drawing(False, 1)
        with self.assertRaises(ValidationError):
            self.sign(session, enrollment)
        self.assertFalse(self.env["training.attendance"].search([("enrollment_id", "=", enrollment.id)]))

    def test_table_signature_before_review_and_private_image_scope(self):
        delivery, session, enrollment = self.scheduled()
        self.sign(session, enrollment)
        event = self.env["training.attendance"].search([("enrollment_id", "=", enrollment.id)]).event_ids
        path = f"/my/training-attendance-signature/{event.id}"
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open(f"/my/trainings/{enrollment.id}/attendance")
        self.assertEqual(page.status_code, 200)
        tree = html.fromstring(page.content)
        self.assertTrue(tree.xpath("//table[contains(@class,'tm_attendance_matrix')]//img"))
        self.assertTrue(tree.xpath("//span[contains(@class,'tm_attendance_pending')]"))
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, bytes(event.signature))
        self.assertIn("no-store", response.headers["Cache-Control"])
        outsider = new_test_user(self.env, login="signature_outsider", groups="base.group_portal")
        self.authenticate(outsider.login, outsider.login)
        self.assertEqual(self.url_open(path).status_code, 404)
        self.assertEqual(self.url_open(f"/my/training-dashboard/{delivery.id}/attendance").status_code, 404)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(path).status_code, 200)
        self.assertEqual(self.url_open(f"/my/training-dashboard/{delivery.id}/attendance").status_code, 200)
        self.assertNotEqual(
            self.url_open(f"/web/content/training.attendance.event/{event.id}/signature").status_code, 200
        )
        enrollment.action_suspend_access(reason="Fictional revoked access")
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(path).status_code, 404)

    def test_supervisor_read_only_and_assignment_removal(self):
        delivery, session, enrollment = self.scheduled()
        self.sign(session, enrollment)
        supervisor = new_test_user(
            self.env,
            login="signature_supervisor",
            groups="base.group_user,training_management.group_training_supervisor",
        )
        delivery.write({"evaluation_supervisor_ids": [Command.link(supervisor.id)]})
        self.authenticate(supervisor.login, supervisor.login)
        path = f"/my/training-dashboard/{delivery.id}/attendance"
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(html.fromstring(response.content).xpath("//form[@method='post']"))
        self.assertEqual(self.url_open(f"/my/training-sessions/{session.id}/attendance").status_code, 404)
        delivery.write({"evaluation_supervisor_ids": [Command.clear()]})
        self.assertEqual(self.url_open(path).status_code, 404)

    def test_partial_matrix_has_real_duration_and_no_invented_afternoon(self):
        delivery, session, enrollment = self.scheduled()
        second = (
            self.env["training.session"]
            .with_user(self.coordinator)
            ._create_scheduled(
                [
                    {
                        "name": "Fictional second morning session",
                        "delivery_id": delivery.id,
                        "instructor_id": self.portal_b.partner_id.id,
                        "mode": "remote",
                        "meeting_url": "https://example.invalid/second",
                        "start_date": "2027-01-04",
                        "end_date": "2027-01-04",
                        "start_hour": 11,
                        "end_hour": 12,
                    }
                ],
                reason="Fictional additional morning session",
            )
        )
        with patch("odoo.fields.Datetime.now", return_value=second.end_at):
            service = self.service()
            service._sign_halfday(
                enrollment.id,
                "2027-01-04-am",
                signature_version=1,
                accepted=True,
                definition=service._day_definition(session | second),
            )
            presence = self.env["training.attendance"].search([("session_id", "=", session.id)])
            self.service(self.portal_b)._sign_review(
                session.id,
                enrollment.id,
                0,
                0,
                signature_version=1,
                period_key=presence.period_key,
                revision=presence.revision,
                definition=service._definition(session),
            )
            current = SimpleNamespace(env=self.env(user=self.portal))
            with (
                patch("odoo.addons.training_management.controllers.attendance_portal.request", current),
                patch("odoo.addons.training_management.controllers.attendance_matrix.request", current),
            ):
                rows = AttendancePortal()._all_rows(session | second, enrollment)
                matrix = attendance_matrix(rows, view="all")
                morning, afternoon = matrix["lines"][0]["cells"]
                self.assertEqual(morning["code"], "partial")
                self.assertIn("1/2", morning["label"])
                self.assertEqual(morning["minutes"], 120)
                self.assertEqual(len(morning["signatures"]), 1)
                self.assertEqual(afternoon["code"], "none")

    def test_signature_page_csrf_version_and_deletion(self):
        self.authenticate(self.portal.login, self.portal.login)
        path = "/my/training-signature"
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        tree = html.fromstring(response.content)
        payload = {i.get("name"): i.get("value", "") for i in tree.xpath("//form//input[@type='hidden']")}
        response = self.url_open(path, data={**payload, "operation": "delete", "accepted": "yes"})
        self.assertEqual(response.status_code, 200)
        self.env.invalidate_all()
        self.assertFalse(self.env["training.attendance.signature"].with_user(self.portal)._current().drawing)
        response = self.url_open(
            path, data={**payload, "operation": "save", "accepted": "yes", "drawing": self.signature_png}
        )
        self.assertIn("alert-danger", response.text)
        self.assertFalse(self.env["training.attendance.signature"].with_user(self.portal)._current().drawing)
