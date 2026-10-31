"""Review 6–8: real missions, scheduled half-days and bounded dashboard queries."""

from datetime import datetime, timedelta
import logging
import json
import time
from unittest.mock import patch

from lxml import html

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged

from .test_attendance import AttendanceCase
from .test_closure import ClosureCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestHalfdayAttendance(AttendanceCase, HttpCase):
    def full_day(self, timezone="UTC", date="2027-01-04"):
        delivery = self.delivery(
            kind="session",
            start_at="2027-01-01",
            end_at=str(datetime.fromisoformat(date) + timedelta(days=1)),
            timezone=timezone,
        )
        session = self.scheduled_session(delivery)
        session.write(
            {"start_date": date, "end_date": date, "start_hour": 9, "end_hour": 17, "attendance_mode": "mixed"}
        )
        delivery.action_confirm(conflict_reason="Fictional fixture")
        with patch("odoo.fields.Datetime.now", return_value=session.start_at):
            enrollment = self.opened(delivery)
        return delivery, session, enrollment

    def sign(self, session, enrollment, key, **kwargs):
        service = self.service()
        sessions = service._day_sessions(enrollment, key).filtered(lambda s: s.attendance_mode != "paper")
        return service._declare_halfday(
            enrollment.id, key, accepted=True, definition=service._day_definition(sessions), **kwargs
        )

    def test_two_halfdays_use_planned_duration_separate_review_and_no_double_count(self):
        delivery, session, enrollment = self.full_day()
        periods = self.service()._periods(session)
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            self.sign(session, enrollment, periods[0]["key"])
            self.sign(session, enrollment, periods[0]["key"])
            rows = self.env["training.attendance"].search([("enrollment_id", "=", enrollment.id)])
            self.assertEqual(len(rows.event_ids), 1)
            self.assertEqual(rows.minutes, 0)
            self.service(self.portal_b)._review(
                session.id,
                enrollment.id,
                9999,
                -9999,
                period_key=rows.period_key,
                revision=rows.revision,
                definition=self.service()._definition(session),
            )
            self.assertEqual(rows.minutes, 180)
            summary = self.env["training.dashboard.service"].with_user(self.coordinator)._participant(enrollment.id)
            self.assertEqual(summary["attendance"][0]["minutes"], 180)
            self.assertTrue(summary["attendance_incomplete"])
            self.sign(session, enrollment, periods[1]["key"], absent=True)
            afternoon = self.env["training.attendance"].search(
                [("enrollment_id", "=", enrollment.id), ("period_key", "=", periods[1]["key"])]
            )
            self.service(self.portal_b)._review(
                session.id,
                enrollment.id,
                0,
                0,
                absent=True,
                period_key=afternoon.period_key,
                revision=afternoon.revision,
                definition=self.service()._definition(session),
            )
            self.assertEqual(afternoon.minutes, 0)
            self.assertFalse(
                self.env["training.dashboard.service"]
                .with_user(self.coordinator)
                ._participant(enrollment.id)["attendance_incomplete"]
            )
            with self.assertRaises(ValidationError):
                self.sign(session, enrollment, "2027-01-05-am")
            enrollment.action_suspend_access(reason="Fictional revocation")
            with self.assertRaises(AccessError):
                self.sign(session, enrollment, periods[0]["key"])

    def test_local_halfday_dst_and_future_time_are_server_controlled(self):
        _, session, enrollment = self.full_day("Europe/Paris", "2027-03-28")
        periods = self.service()._periods(session)
        self.assertEqual(periods[0]["key"], "2027-03-28-am")
        self.assertEqual(periods[0]["start"], datetime(2027, 3, 28, 7))
        self.assertEqual(periods[0]["end"], datetime(2027, 3, 28, 10))
        with patch("odoo.fields.Datetime.now", return_value=periods[0]["end"] - timedelta(seconds=1)):
            with self.assertRaises(ValidationError):
                self.sign(session, enrollment, periods[0]["key"])
        with patch("odoo.fields.Datetime.now", return_value=periods[0]["end"]):
            self.sign(session, enrollment, periods[0]["key"])
            with self.assertRaises(ValidationError):
                self.sign(session, enrollment, periods[1]["key"])

    def test_historical_evidence_requires_invalidation_before_halfday_replacement(self):
        _, session, enrollment = self.scheduled()
        old = self.declare(session, enrollment)
        self.review(old)
        before = old.event_ids.read(["kind", "start_at", "end_at", "occurred_at", "actor_id"])
        key = self.service()._periods(session)[0]["key"]
        with self.assertRaises(ValidationError):
            self.sign(session, enrollment, key)
        self.service(self.portal_b)._invalidate(
            session.id,
            enrollment.id,
            reason="Fictional correction",
            revision=old.revision,
            definition=self.service()._definition(session),
        )
        self.sign(session, enrollment, key)
        self.assertEqual(old.minutes, 0)
        self.assertEqual(old.event_ids[:-1].read(["kind", "start_at", "end_at", "occurred_at", "actor_id"]), before)
        with self.assertRaises(ValidationError):
            self.review(old)
        self.assertEqual(old.minutes, 0)

    def test_one_confirmation_covers_two_morning_sessions_without_hours(self):
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        first = self.scheduled_session(delivery)
        first.write({"end_hour": 10})
        second = self.scheduled_session(delivery)
        second.write({"start_hour": 10, "end_hour": 11})
        delivery.action_confirm(conflict_reason="Fictional fixture")
        with patch("odoo.fields.Datetime.now", return_value=first.start_at):
            enrollment = self.opened(delivery)
        self.authenticate(self.portal.login, self.portal.login)
        path = f"/my/trainings/{enrollment.id}/attendance"
        page = html.fromstring(self.url_open(path).content)
        forms = page.xpath("//form[@method='post']")
        self.assertEqual(len(forms), 1)
        self.assertFalse(forms[0].xpath(".//input[@name='start' or @name='end']"))
        payload = {item.get("name"): item.get("value", "") for item in forms[0].xpath(".//input[@type='hidden']")}
        payload.update(accepted="yes", attendance="present")
        self.assertEqual(self.url_open(path, data=payload).status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(len(self.env["training.attendance"].search([("enrollment_id", "=", enrollment.id)])), 2)


@tagged("post_install", "-at_install")
class TestTrainingNavigation(AttendanceCase, HttpCase):
    def test_participant_trainer_tutor_company_and_combined_roles(self):
        delivery, session, enrollment = self.scheduled()
        navigation = self.env["training.portal.navigation"]
        participant = navigation.with_user(self.portal)._links()
        self.assertFalse(any(participant[k] for k in ("sessions", "tutoring", "dashboard", "company")))
        trainer = navigation.with_user(self.portal_b)._links()
        self.assertTrue(trainer["sessions"])
        self.assertTrue(trainer["dashboard"])
        delivery.write({"learning_tutor_id": self.portal.id})
        self.assertTrue(navigation.with_user(self.portal)._links()["tutoring"])
        allocation = self.lot(delivery, quantity=1)
        grant = (
            self.env["training.company.authorization"]
            .with_user(self.coordinator)
            .create(
                {
                    "company_id": self.company.id,
                    "customer_id": self.customer.id,
                    "user_id": self.portal.id,
                    "allocation_ids": [Command.set(allocation.ids)],
                }
            )
        )
        grant.action_confirm()
        self.assertTrue(navigation.with_user(self.portal)._links()["company"])
        self.authenticate(self.portal.login, self.portal.login)
        home = html.fromstring(self.url_open("/my/home").content)
        self.assertTrue(home.xpath("//a[@href='/my/trainings']"))
        self.assertFalse(home.xpath("//a[@href='/my/training-tutoring']"))
        hub = html.fromstring(self.url_open("/my/trainings").content)
        self.assertTrue(hub.xpath("//a[@href='/my/training-tutoring']"))
        self.assertTrue(hub.xpath("//a[@href='/my/company-trainings']"))
        self.assertFalse(hub.xpath("//a[@href='/my/training-sessions']"))
        links = navigation.with_user(self.portal)._links()
        for key, path in (("practice", "training-practice"), ("paths", "training-paths")):
            self.assertEqual(len(hub.xpath(f"//a[@href='/my/{path}']")), int(links[key]))
        delivery.write({"learning_tutor_id": False})
        self.assertFalse(navigation.with_user(self.portal)._links()["tutoring"])


@tagged("post_install", "-at_install")
class TestDashboardBatching(AttendanceCase):
    def test_query_growth_and_page_details_with_multiple_sessions(self):
        delivery = self.delivery(
            kind="session", capacity=120, start_at="2027-01-01", end_at="2027-02-01", timezone="UTC"
        )
        for day in range(4, 9):
            other = self.scheduled_session(delivery)
            other.write({"start_date": f"2027-01-{day:02}", "end_date": f"2027-01-{day:02}"})
        delivery.action_confirm(conflict_reason="Fictional fixture")
        self.opened(delivery)
        service = self.env["training.dashboard.service"].with_user(self.coordinator)
        counts = []
        for target in (1, 25, 100):
            for index in range(len(delivery.enrollment_ids), target):
                partner = self.env["res.partner"].create({"name": f"Fictional performance participant {index}"})
                row = self.enrollment(delivery, participant_id=partner.id, user_id=False)
                row.action_validate_prerequisites(reason="Fictional check")
                row.action_confirm()
            self.env.flush_all()
            self.env.invalidate_all()
            before = self.cr.sql_log_count
            started = time.monotonic()
            result = service._dashboard(delivery.id, page=2, step=20)
            count = self.cr.sql_log_count - before
            counts.append(count)
            _logger.info(
                "DASHBOARD_BATCH_MEASURE participants=%s sessions=5 queries=%s elapsed=%.3f",
                target,
                count,
                time.monotonic() - started,
            )
            self.assertEqual(result["population"], target)
            self.assertLessEqual(len(result["rows"]), 20)
            self.assertEqual(result["metrics"][-1]["population"], target)
        self.assertLess(counts[-1], counts[0] + 60, counts)


@tagged("post_install", "-at_install")
class TestHalfdayCertificate(ClosureCase):
    def test_certificate_uses_only_the_validated_planned_halfday(self):
        _, session, enrollment = self.scheduled()
        service = self.service()
        key = service._periods(session)[0]["key"]
        service._declare_halfday(enrollment.id, key, accepted=True, definition=service._day_definition(session))
        presence = self.env["training.attendance"].search([("enrollment_id", "=", enrollment.id)])
        self.service(self.portal_b)._review(
            session.id,
            enrollment.id,
            999,
            999,
            period_key=key,
            revision=presence.revision,
            definition=service._definition(session),
        )
        dossier = self.dossier(enrollment)
        enrollment.with_user(self.quality).action_certificate_participation()
        document = self.document(dossier, "participation")
        self.assertEqual(json.loads(document.snapshot)["minutes"], 120)
        self.assertTrue(document.data.content.startswith(b"%PDF"))
