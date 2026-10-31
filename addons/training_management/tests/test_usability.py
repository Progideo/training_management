"""UX01: actual role navigation, half-day states and native frontend layouts."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from lxml import html

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged

from .test_attendance import AttendanceCase
from ..controllers.attendance_portal import AttendancePortal
from ..controllers.portal_utils import local_deadline


@tagged("post_install", "-at_install", "training_usability")
class TestUsability(AttendanceCase, HttpCase):
    def test_delivered_training_stays_in_assigned_trainer_navigation(self):
        delivery, session, _enrollment = self.scheduled()
        delivery.action_start()
        delivery.action_deliver()
        self.assertTrue(self.env["training.portal.navigation"].with_user(self.portal_b)._links()["sessions"])
        self.assertEqual(self.service(self.portal_b)._session(session.id), session)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        home = html.fromstring(self.url_open("/my/trainings").content)
        self.assertTrue(home.xpath("//a[@href='/my/training-sessions']"))
        with patch("odoo.fields.Datetime.now", return_value=session.end_at + timedelta(hours=1)):
            response = self.url_open("/my/training-sessions?filterby=past")
            self.assertEqual(response.status_code, 200)
            tree = html.fromstring(response.content)
            links = tree.xpath(f"//a[starts-with(@href, '/my/training-sessions/{session.id}?')]/@href")
            self.assertEqual(len(links), 1)
            detail = html.fromstring(self.url_open(links[0]).content)
            self.assertTrue(detail.xpath("//a[contains(@href, 'filterby=past') and contains(@href, '/attendance?')]"))
        with self.assertRaises(AccessError):
            self.service(self.portal)._session(session.id)
        delivery.action_close(reason="Fictional completed review")
        self.assertFalse(self.env["training.portal.navigation"].with_user(self.portal_b)._links()["sessions"])

    def test_grouped_halfday_states_follow_recorded_evidence(self):
        _delivery, session, enrollment = self.scheduled()
        controller = AttendancePortal()
        current = SimpleNamespace(env=self.env(user=self.portal))
        key = self.service()._periods(session)[0]["key"]
        with patch("odoo.addons.training_management.controllers.attendance_portal.request", current):
            rows = controller._participant_rows(session, enrollment)
            self.assertEqual(rows[0]["state"], "To declare")
            self.assertFalse(rows[0]["declared"])
            self.service()._declare_halfday(
                enrollment.id, key, accepted=True, definition=self.service()._day_definition(session)
            )
            rows = controller._participant_rows(session, enrollment)
            self.assertEqual(rows[0]["state"], "Pending Review")
            presence = self.env["training.attendance"].search([("enrollment_id", "=", enrollment.id)])
            self.service(self.portal_b)._review(
                session.id,
                enrollment.id,
                0,
                0,
                period_key=key,
                revision=presence.revision,
                definition=self.service()._definition(session),
            )
            rows = controller._participant_rows(session, enrollment)
            self.assertEqual(rows[0]["state"], "Validated")
            self.assertEqual(rows[0]["minutes"], 120)
            self.service(self.portal_b)._invalidate(
                session.id,
                enrollment.id,
                reason="Fictional review correction",
                period_key=key,
                revision=presence.revision,
                definition=self.service()._definition(session),
            )
            rows = controller._participant_rows(session, enrollment)
            self.assertEqual(rows[0]["state"], "Declaration invalidated")
            self.assertFalse(rows[0]["declared"])

    def test_mobile_portal_markup_and_impossible_presence_are_explained(self):
        _delivery, session, enrollment = self.scheduled()
        self.authenticate(self.portal_b.login, self.portal_b.login)
        response = self.url_open(f"/my/training-sessions/{session.id}/attendance?filterby=past&page=2")
        tree = html.fromstring(response.content)
        self.assertTrue(tree.xpath("//option[@value='present'][@disabled]"))
        self.assertTrue(tree.xpath("//a[contains(@href, 'filterby=past') and contains(@href, 'page=2')]"))
        self.assertTrue(
            any(
                message in response.text
                for message in ("A participant declaration is needed", "La déclaration du participant est attendue")
            )
        )
        self.assertEqual(len(tree.xpath("//main")), 1)
        self.authenticate(self.portal.login, self.portal.login)
        page = html.fromstring(self.url_open(f"/my/trainings/{enrollment.id}").content)
        self.assertTrue(page.xpath("//a[@href='#training-activities']"))
        self.assertFalse(page.xpath("//a[contains(@href, '/tutoring')]"))

    def test_local_deadline_preserves_instant_and_rejects_dst_ambiguity(self):
        current = SimpleNamespace(env=self.env)
        with patch("odoo.addons.training_management.controllers.portal_utils.request", current):
            self.assertEqual(local_deadline("2027-01-04T12:00", "Europe/Paris"), datetime(2027, 1, 4, 11))
            for value in ("2027-03-28T02:30", "2027-10-31T02:30", "not a date"):
                with self.assertRaises(ValidationError):
                    local_deadline(value, "Europe/Paris")

    def test_public_catalogue_keeps_single_wrap_and_theme_layout(self):
        self.authenticate(None, None)
        tree = html.fromstring(self.url_open("/formations").content)
        self.assertEqual(len(tree.xpath("//main")), 1)
        self.assertEqual(len(tree.xpath("//*[@id='wrap']")), 1)
        self.assertTrue(tree.xpath("//header"))
        self.assertTrue(tree.xpath("//footer"))
        fallback = tree.xpath("//nav[@id='training_catalogue_navigation']")
        self.assertEqual(bool(fallback), "homepage_url" not in self.env["website"]._fields)

    def test_secondary_enrollment_actions_reuse_protected_native_wizards(self):
        _delivery, _session, enrollment = self.scheduled()
        action = self.env.ref("training_management.action_enrollment_postpone")
        context = {"active_model": enrollment._name, "active_id": enrollment.id, "active_ids": enrollment.ids}
        window = action.with_user(self.coordinator).with_context(**context).run()
        self.assertEqual(window["res_model"], "training.enrollment.operation")
        self.assertEqual(enrollment.state, "confirmed")
        with self.assertRaises(AccessError):
            action.with_user(self.portal).with_context(**context).run()

    def test_native_entry_opens_catalogue_for_reader_without_teaching_mission(self):
        action = self.env["training.dashboard.line"].with_user(self.reader).action_open_training()
        self.assertEqual(action["res_model"], "training.course")
        with self.assertRaises(AccessError):
            self.env["training.dashboard.line"].with_user(self.portal).action_open_training()
