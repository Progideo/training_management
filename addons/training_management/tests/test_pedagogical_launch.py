"""Calendar access and configurable reservation defaults under real permissions."""

from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, tagged

from .test_enrollment import EnrollmentCase


@tagged("post_install", "-at_install")
class TestPedagogicalLaunch(EnrollmentCase):
    def test_calendar_year_from_opening_replay_extension_revocation_and_history(self):
        delivery = self.delivery(access_policy="months", access_months=12, access_days=0)
        enrollment = self.admitted(delivery)
        enrollment.action_authorize(reason="Fictional deferred payment authorization")
        self.assertFalse(enrollment.access_start)
        start = datetime(2028, 2, 29, 10)
        with patch("odoo.fields.Datetime.now", return_value=start):
            enrollment.action_open_access(reason="Fictional explicit opening")
            self.assertEqual(enrollment.access_start, start)
            self.assertEqual(enrollment.access_end, datetime(2029, 2, 28, 10))
            history = delivery.operation_ids
            enrollment.action_open_access(reason="Replay")
            self.assertEqual(delivery.operation_ids, history)
            for user in (self.portal, self.reader, self.internal):
                with self.assertRaises(AccessError):
                    enrollment.with_user(user).action_extend_access(start + timedelta(days=800), reason="Forbidden")
            enrollment.action_extend_access(datetime(2029, 3, 31, 10), reason="Fictional authorized extension")
            self.assertEqual(enrollment.access_end, datetime(2029, 3, 31, 10))
            enrollment.action_revoke_access(reason="Fictional revocation")
            self.assertEqual(enrollment._effective_state(), "revoked")
            with self.assertRaises(ValidationError):
                enrollment.action_open_access(reason="Forbidden reopening")
            self.assertTrue(history <= delivery.operation_ids)
            self.assertEqual(enrollment.state, "confirmed")

    def test_seven_day_default_adjustment_waiting_expiration_and_manual_confirmation(self):
        delivery = self.delivery(reservation_days=7, capacity=1)
        first = self.enrollment(delivery)
        second = self.enrollment(delivery, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        (first | second).action_wait()
        now = fields.Datetime.now()
        with patch("odoo.fields.Datetime.now", return_value=now):
            action = first.with_context(operation="reserve").action_open_operation()
            with Form(
                self.env[action["res_model"]].with_user(self.coordinator).with_context(action["context"])
            ) as form:
                self.assertEqual(form.deadline, now + timedelta(days=7))
                form.reason = "Fictional provisional reservation"
            form.record.action_apply()
            self.assertEqual(first.reservation_end, now + timedelta(days=7))
            self.assertEqual(first.state, "reserved")
            self.assertEqual(first.access_state, "unopened")
            with self.assertRaises(ValidationError):
                first.action_reserve(now + timedelta(days=8))
            first.action_reserve(now + timedelta(days=8), reason="Fictional deadline adjustment")
            self.assertEqual(first.reservation_end, now + timedelta(days=8))
            self.assertTrue(delivery.operation_ids.filtered(lambda row: row.reason == "Fictional deadline adjustment"))
            with self.assertRaises(ValidationError):
                second.action_reserve()
        with patch("odoo.fields.Datetime.now", return_value=now + timedelta(days=9)):
            self.assertFalse(first._occupies())
            second.action_reserve(reason="Fictional manual waiting-list offer")
            self.assertEqual(second.state, "reserved")
            self.assertFalse(second.commercially_authorized)
            self.assertFalse(second.access_start)
            first.action_expire()
            self.assertEqual(first.state, "requested")

    def test_lot_default_explicit_override_and_cancel_release(self):
        delivery = self.delivery(reservation_days=7, capacity=3)
        now = fields.Datetime.now()
        with patch("odoo.fields.Datetime.now", return_value=now):
            lot = self.lot(delivery, expires_at=False, quantity=2)
            self.assertEqual(lot.expires_at, now + timedelta(days=7))
            other = self.lot(delivery, source_reference="OTHER", quantity=1, expires_at=now + timedelta(days=3))
            self.assertEqual(other.expires_at, now + timedelta(days=3))
            lot.action_cancel(reason="Fictional cancellation")
            self.assertEqual(delivery._occupancy(), 1)
            self.assertEqual(lot.state, "cancelled")

    def test_month_policy_configuration_and_frozen_existing_period(self):
        with self.assertRaises(ValidationError):
            self.delivery(access_policy="months", access_months=0)
        delivery = self.delivery(access_policy="months", access_months=12, reservation_days=7)
        self.admitted(delivery)
        with self.assertRaises(ValidationError):
            delivery.write({"access_months": 6})
