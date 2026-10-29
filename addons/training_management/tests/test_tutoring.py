"""P13 quota, capacity, native planning and private notices with restricted actors."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tools.translate import load_language

from .test_closure import ClosureCase


class TutoringCase(ClosureCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.peer = new_test_user(cls.env, login="p13_peer", groups="base.group_portal")

    def setup_tutoring(self, count=2, **slot_values):
        delivery = self.delivery(learning_tutor_id=self.portal_b.id, timezone="UTC")
        enrollment = self.opened(delivery)
        entitlement = (
            self.env["training.tutoring.entitlement"]
            .with_user(self.coordinator)
            .create(
                {
                    "enrollment_id": enrollment.id,
                    "included_count": count,
                    "service_reference": "FICT-P13",
                    "retention_id": self.retention.id,
                }
            )
        )
        slot = self.slot(delivery, **slot_values)
        slot.action_publish()
        return entitlement, slot

    def slot(self, delivery, **values):
        day = (fields.Datetime.now() + timedelta(days=3)).date()
        return (
            self.env["training.tutoring.slot"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional P13 slot",
                    "delivery_id": delivery.id,
                    "tutor_id": self.portal_b.id,
                    "kind": "individual",
                    "capacity": 1,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/tutoring",
                    "start_date": day,
                    "end_date": day,
                    "start_hour": 10,
                    "end_hour": 11,
                    "refund_policy": "before",
                    "cancellation_hours": 24,
                    "cancellation_terms": "Fictional agreed cancellation terms",
                    **values,
                }
            )
        )

    def reserve(self, entitlement, slot, key=None, user=None):
        return (
            self.env["training.tutoring.service"]
            .with_user(user or self.portal)
            ._reserve(entitlement.enrollment_id.id, slot.id, key or str(uuid4()))
        )

    def cancel(self, booking, user=None):
        return (
            self.env["training.tutoring.service"]
            .with_user(user or self.portal)
            ._cancel(booking.enrollment_id.id, booking.id)
        )


@tagged("post_install", "-at_install")
class TestTutoring(TutoringCase):
    def test_confirmation_quota_idempotency_and_notices(self):
        entitlement, slot = self.setup_tutoring(count=1)
        self.assertEqual(entitlement.used_count, 0)
        key = str(uuid4())
        booking = self.reserve(entitlement, slot, key)
        self.assertEqual(self.reserve(entitlement, slot, key), booking)
        self.assertEqual(self.reserve(entitlement, slot), booking)
        self.assertEqual(entitlement.used_count, 1)
        self.assertEqual(slot.occupied_count, 1)
        self.assertEqual(booking.create_uid, self.portal)
        other = self.slot(slot.delivery_id, start_hour=11, end_hour=12)
        other.action_publish()
        with self.assertRaises(ValidationError):
            self.reserve(entitlement, other)
        notices = self.env["training.tutoring.notice"].sudo().search([("booking_id", "=", booking.id)])
        self.assertEqual(len(notices), 2)
        self.assertEqual(notices.recipient_id, self.portal | self.portal_b)
        self.assertTrue(all(notices.mapped("mail_id")))
        self.assertFalse(notices.mail_id.attachment_ids)
        self.assertFalse(notices.mail_id.recipient_ids)
        for notice in notices:
            self.assertTrue(notice._authorized())
            notice.mail_id._prepare_outgoing_list()
        self.assertFalse(
            self.env["training.learning.progress"].search([("enrollment_id", "=", booking.enrollment_id.id)])
        )

    def test_announced_refund_deadline_repetition_and_new_intent(self):
        entitlement, slot = self.setup_tutoring(count=1)
        booking = self.reserve(entitlement, slot)
        self.cancel(booking)
        self.cancel(booking)
        self.assertTrue(booking.refunded)
        self.assertEqual(entitlement.used_count, 0)
        self.assertEqual(slot.occupied_count, 0)
        self.assertEqual(self.reserve(entitlement, slot, booking.request_key), booking)
        second = self.reserve(entitlement, slot)
        self.assertNotEqual(second, booking)
        with patch("odoo.fields.Datetime.now", return_value=second.refund_deadline + timedelta(seconds=1)):
            self.cancel(second)
        self.assertFalse(second.refunded)
        self.assertEqual(entitlement.used_count, 1)
        with self.assertRaises(ValidationError):
            self.reserve(entitlement, slot)

    def test_exact_deadline_no_refund_and_coordinator_cancellation(self):
        entitlement, slot = self.setup_tutoring()
        booking = self.reserve(entitlement, slot)
        with patch("odoo.fields.Datetime.now", return_value=booking.refund_deadline):
            self.cancel(booking)
        self.assertTrue(booking.refunded)
        no_refund = self.slot(slot.delivery_id, start_hour=11, end_hour=12, refund_policy="never")
        no_refund.action_publish()
        booking = self.reserve(entitlement, no_refund)
        self.cancel(booking)
        self.assertFalse(booking.refunded)
        next_booking = self.reserve(entitlement, no_refund)
        no_refund.action_cancel()
        no_refund.action_cancel()
        self.assertTrue(next_booking.refunded)
        self.assertEqual(next_booking.cancelled_by_id, self.coordinator)
        self.assertEqual(next_booking.state, "cancelled")

    def test_collective_capacity_and_no_shared_participant_access(self):
        entitlement, slot = self.setup_tutoring(kind="collective", capacity=2)
        # A real second portal identity, never a contact-based grant.
        peer = self.enrollment(slot.delivery_id, participant_id=self.peer.partner_id.id, user_id=self.peer.id)
        peer.action_validate_prerequisites(reason="Fictional review")
        peer.action_confirm()
        peer.action_authorize(reason="Fictional authorization")
        peer.action_open_access(reason="Fictional opening")
        right = (
            self.env["training.tutoring.entitlement"]
            .with_user(self.coordinator)
            .create(
                {
                    "enrollment_id": peer.id,
                    "included_count": 1,
                    "service_reference": "FICT-P13-peer",
                    "retention_id": self.retention.id,
                }
            )
        )
        first = self.reserve(entitlement, slot)
        self.reserve(right, slot, user=self.peer)
        self.assertEqual(slot.occupied_count, 2)
        with self.assertRaises(AccessError):
            first.with_user(self.peer).read(["state"])
        with self.assertRaises(AccessError):
            self.cancel(first, user=self.peer)
        with self.assertRaises(AccessError):
            self.reserve(entitlement, slot, user=self.peer)

    def test_restricted_roles_companies_revocation_and_transport(self):
        entitlement, slot = self.setup_tutoring()
        booking = self.reserve(entitlement, slot)
        with self.assertRaises(AccessError):
            slot.with_user(self.portal).action_cancel()
        with self.assertRaises(AccessError):
            entitlement.with_user(self.internal).read(["included_count"])
        with self.assertRaises(AccessError):
            booking.with_user(self.portal).create({"slot_id": slot.id})
        with self.assertRaises(UserError):
            booking.with_user(self.coordinator).export_data(["state"])
        notice = (
            self.env["training.tutoring.notice"]
            .sudo()
            .search([("booking_id", "=", booking.id), ("recipient_id", "=", self.portal.id)])
        )
        entitlement.enrollment_id.action_suspend_access(reason="Fictional suspension")
        with self.assertRaises(AccessError):
            self.cancel(booking)
        self.assertFalse(notice._authorized())
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()
        self.portal.write({"company_id": self.other_company.id, "company_ids": [Command.set(self.other_company.ids)]})
        with self.assertRaises(AccessError):
            self.reserve(entitlement, slot)

    def test_frozen_definitions_forms_and_injected_defaults(self):
        entitlement, slot = self.setup_tutoring()
        with self.assertRaises(ValidationError):
            slot.write({"capacity": 5})
        with self.assertRaises(ValidationError):
            slot.unlink()
        with self.assertRaises(ValidationError):
            entitlement.write({"included_count": 99})
        with self.assertRaises(ValidationError):
            slot.delivery_id.write({"timezone": "Europe/Paris"})
        draft = self.slot(slot.delivery_id, start_hour=11, end_hour=12)
        with Form(draft) as form:
            form.name = "Fictional edited draft"
        with self.assertRaises(ValidationError):
            self.slot(slot.delivery_id, kind="individual", capacity=2)
        with self.assertRaises(ValidationError):
            self.slot(slot.delivery_id, state="published")
        booking = (
            self.env["training.tutoring.service"]
            .with_user(self.portal)
            .with_context(default_refunded=True, default_state="cancelled")
            ._reserve(entitlement.enrollment_id.id, slot.id, str(uuid4()))
        )
        self.assertEqual(booking.state, "confirmed")
        self.assertFalse(booking.refunded)

    def test_resource_conflicts_joint_intervals_and_local_time(self):
        entitlement, slot = self.setup_tutoring()
        conflict = self.slot(slot.delivery_id)
        with self.assertRaises(ValidationError):
            conflict.action_publish()
        adjacent = self.slot(slot.delivery_id, start_hour=11, end_hour=12)
        adjacent.action_publish()
        with self.assertRaises(ValidationError):
            self.env["training.unavailability"].with_user(self.coordinator).create(
                {
                    "company_id": self.company.id,
                    "instructor_id": self.portal_b.partner_id.id,
                    "start_at": slot.start_at,
                    "end_at": slot.end_at,
                }
            )
        slot.action_cancel()
        self.env["training.unavailability"].with_user(self.coordinator).create(
            {
                "company_id": self.company.id,
                "instructor_id": self.portal_b.partner_id.id,
                "start_at": slot.start_at,
                "end_at": slot.end_at,
            }
        )
        with self.assertRaises(ValidationError):
            conflict.action_publish()
        paris = self.delivery(timezone="Europe/Paris")
        with self.assertRaises(ValidationError):
            self.slot(paris, start_date="2027-03-28", end_date="2027-03-28", start_hour=2.5, end_hour=4)
        with self.assertRaises(ValidationError):
            self.slot(paris, start_date="2027-10-31", end_date="2027-10-31", start_hour=2.5, end_hour=4)
        valid = self.slot(
            paris, start_date="2027-10-31", end_date="2027-10-31", start_hour=2.5, end_hour=4, start_occurrence="second"
        )
        self.assertEqual(valid.duration_hours, 1.5)

    def test_started_slot_and_notice_tampering(self):
        entitlement, slot = self.setup_tutoring()
        booking = self.reserve(entitlement, slot)
        with patch("odoo.fields.Datetime.now", return_value=slot.start_at):
            with self.assertRaises(ValidationError):
                self.cancel(booking)
        notice = self.env["training.tutoring.notice"].sudo().search([("booking_id", "=", booking.id)], limit=1)
        notice.mail_id.write({"email_cc": "peer@example.invalid"})
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()

    def test_last_capacity_access_horizon_and_tutor_reassignment(self):
        entitlement, slot = self.setup_tutoring()
        self.reserve(entitlement, slot)
        peer = self.enrollment(slot.delivery_id, participant_id=self.peer.partner_id.id, user_id=self.peer.id)
        peer.action_validate_prerequisites(reason="Fictional review")
        peer.action_confirm()
        peer.action_authorize(reason="Fictional authorization")
        peer.action_open_access(reason="Fictional opening")
        right = (
            self.env["training.tutoring.entitlement"]
            .with_user(self.coordinator)
            .create(
                {
                    "enrollment_id": peer.id,
                    "included_count": 1,
                    "service_reference": "FICT-peer",
                    "retention_id": self.retention.id,
                }
            )
        )
        with self.assertRaises(ValidationError):
            self.reserve(right, slot, user=self.peer)
        future_day = (fields.Datetime.now() + timedelta(days=15)).date()
        future = self.slot(slot.delivery_id, start_date=future_day, end_date=future_day)
        future.action_publish()
        with self.assertRaises(ValidationError):
            self.reserve(entitlement, future)
        notice = (
            self.env["training.tutoring.notice"]
            .sudo()
            .search([("enrollment_id", "=", entitlement.enrollment_id.id), ("recipient_id", "=", self.portal_b.id)])
        )
        entitlement.enrollment_id.write({"learning_tutor_id": self.peer.id})
        self.assertFalse(notice._authorized())
        with self.assertRaises(AccessError):
            self.reserve(entitlement, future)

    def test_booking_attachments_and_cross_company_coordinator_are_denied(self):
        entitlement, slot = self.setup_tutoring()
        booking = self.reserve(entitlement, slot)
        with self.assertRaises(ValidationError):
            self.env["ir.attachment"].create(
                {
                    "name": "forged.txt",
                    "raw": b"private",
                    "res_model": booking._name,
                    "res_id": booking.id,
                    "public": True,
                }
            )
        ordinary = self.env["ir.attachment"].create({"name": "ordinary.txt", "raw": b"fictional"})
        with self.assertRaises(ValidationError):
            ordinary.write({"res_model": booking._name, "res_id": booking.id})
        outsider = new_test_user(
            self.env,
            login="p13_other_coord",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        with self.assertRaises(AccessError):
            slot.with_user(outsider).action_cancel()
        with self.assertRaises(AccessError):
            booking.with_user(outsider).read(["cancellation_terms"])

    def test_reciprocal_session_conflict_and_room_capacity(self):
        start = fields.Datetime.now() + timedelta(days=3)
        day = start.date()
        delivery = self.delivery(
            kind="session",
            start_at=fields.Datetime.to_datetime(str(day) + " 08:00:00"),
            end_at=fields.Datetime.to_datetime(str(day) + " 18:00:00"),
            opening_threshold=0,
        )
        slot = self.slot(delivery)
        slot.action_publish()
        session = (
            self.env["training.session"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional S04 conflict",
                    "delivery_id": delivery.id,
                    "instructor_id": self.portal_b.partner_id.id,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/session",
                    "start_date": day,
                    "end_date": day,
                    "start_hour": 10,
                    "end_hour": 11,
                }
            )
        )
        with self.assertRaises(ValidationError):
            session._reserve("Fictional S04 override does not move P13")
        slot.action_cancel()
        session._reserve()
        delivery.action_confirm()
        blocked = self.slot(delivery)
        with self.assertRaises(ValidationError):
            blocked.action_publish()
        room = self.env["resource.resource"].create(
            {
                "name": "Fictional P13 room",
                "company_id": self.company.id,
                "resource_type": "material",
                "training_room": True,
                "training_capacity": 2,
            }
        )
        room_slot = self.slot(
            self.delivery(), start_hour=12, end_hour=13, kind="collective", capacity=2, room_id=room.id
        )
        room_slot.action_publish()
        with self.assertRaises(ValidationError):
            room.write({"training_capacity": 1})


@tagged("post_install", "-at_install")
class TestTutoringHttp(TutoringCase, HttpCase):
    def test_authenticated_forms_private_headers_and_peer_denial(self):
        entitlement, slot = self.setup_tutoring()
        self.authenticate(self.portal.login, self.portal.login)
        url = "/my/trainings/%s/tutoring" % entitlement.enrollment_id.id
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn(b"Fictional agreed cancellation terms", response.content)
        from lxml import html

        token = html.fromstring(response.content).xpath("//input[@name='csrf_token']/@value")[0]
        response = self.url_open(
            url, data={"csrf_token": token, "action": "reserve", "slot_id": slot.id, "request_key": str(uuid4())}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.env["training.tutoring.booking"].search_count([("slot_id", "=", slot.id)]), 1)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.assertIn(b"Fictional P13 slot", self.url_open("/my/training-bookings").content)

    def test_french_mobile_form_escaping_and_direct_content(self):
        load_language(self.cr, "fr_FR")
        self.env["ir.module.module"].search([("name", "=", "training_management")])._update_translations(
            ["fr_FR"], overwrite=True
        )
        self.portal.lang = "fr_FR"
        if "website" in self.env and "language_ids" in self.env["website"]._fields:
            french = self.env.ref("base.lang_fr")
            self.env["website"].search([]).write(
                {"language_ids": [Command.set(french.ids)], "default_lang_id": french.id}
            )
        entitlement, slot = self.setup_tutoring(name="<script>Fictional P13</script>")
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(
            "/my/trainings/%s/tutoring" % entitlement.enrollment_id.id,
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Créneaux de tutorat disponibles", response.text)
        self.assertIn("Confirmer la réservation — une unité", response.text)
        self.assertIn("&lt;script&gt;Fictional P13&lt;/script&gt;", response.text)
        self.assertNotIn("<script>Fictional P13</script>", response.text)
        booking = self.reserve(entitlement, slot)
        direct = self.url_open("/web/content/training.tutoring.booking/%s/cancellation_terms" % booking.id)
        self.assertIn(direct.status_code, (403, 404))
