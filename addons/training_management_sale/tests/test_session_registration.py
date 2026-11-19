from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from lxml import html

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, tagged

from odoo.addons.training_management.tests.test_session_publication import SessionAlertCase


@tagged("post_install", "-at_install")
class TestPublicSessionRegistration(SessionAlertCase, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.public_program = cls.public_program.copy(
            {"version": "PUBLIC-INTER", "delivery_mode": "onsite", "public_catalogue": True}
        )
        cls.public_program.action_validate()
        cls.public_program.action_publish()

    def _form_payload(self, url, count="1"):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        form = html.fromstring(response.content)
        return {
            "csrf_token": form.xpath("//input[@name='csrf_token']/@value")[0],
            "submission_token": form.xpath("//input[@name='submission_token']/@value")[0],
            "contact": "Fictional applicant",
            "email": "session-applicant@example.invalid",
            "count": count,
        }

    def test_visitor_session_request_is_pending_and_idempotent(self):
        delivery = self.dated_delivery(name="PRIVATE_SESSION_NAME", capacity=3, timezone="Africa/Casablanca")
        self.course.sudo().public_catalogue = True
        course_url = f"/formations/catalogue/{self.course.id}"
        url = f"{course_url}/inscription/{delivery.id}"
        self.authenticate(None, None)
        self.assertEqual(self.url_open(url).status_code, 404)
        delivery.action_publish_session(reason="Fictional publication")
        response = self.url_open(course_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(url, response.text)
        self.assertNotIn(delivery.name, response.text)
        self.assertIn(f"/formations/demande?course={self.course.id}", response.text)
        group = self._form_payload(url, count="3")
        self.assertIn('role="alert"', self.url_open(url, data={**group, "count": "4"}).text)
        self.assertEqual(self.url_open(url, data={**group, "submission_token": "forged"}).status_code, 404)
        for payload in (group, group, self._form_payload(url)):
            response = self.url_open(url, data=payload)
            self.assertIn("Demande reçue", response.text)
        leads = self.env["crm.lead"].search(
            [("training_requested_delivery_id", "=", delivery.id)], order="training_attendee_count desc"
        )
        self.assertEqual(leads.mapped("training_attendee_count"), [3, 1])
        self.assertEqual(leads.mapped("training_request_kind"), ["group", "individual"])
        self.assertEqual(leads.mapped("training_requested_course_id"), self.course)
        self.assertEqual(leads.mapped("training_program_id"), self.public_program)
        self.assertEqual(leads.mapped("company_id"), self.company)
        self.assertFalse(delivery.sudo().enrollment_ids)
        self.assertFalse(delivery.sudo().allocation_ids)

    def test_wrong_course_site_full_or_changed_session_cannot_be_requested(self):
        delivery = self.dated_delivery(capacity=3)
        delivery.action_publish_session(reason="Fictional publication")
        url = f"/formations/catalogue/{self.course.id}/inscription/{delivery.id}"
        self.authenticate(None, None)
        payload = self._form_payload(url, count="2")
        self.assertEqual(
            self.url_open(f"/formations/catalogue/0/inscription/{delivery.id}", data=payload).status_code, 404
        )
        company = self.env["res.company"].create({"name": "Fictional other training provider"})
        self.assertFalse(
            self.env["training.delivery"]._public_registration_sessions(company, self.course.id, delivery.id)
        )
        start, end = delivery.start_at + timedelta(days=1), delivery.end_at + timedelta(days=1)
        delivery.action_change_dates(start_at=start, end_at=end, reason="Fictional rescheduling")
        delivery.action_publish_session(reason="Fictional republication")
        self.assertEqual(self.url_open(url, data=payload).status_code, 404)
        current_payload = self._form_payload(url)
        self.lot(delivery, quantity=3)
        self.assertEqual(self.url_open(url).status_code, 404)
        page = self.url_open(f"/formations/catalogue/{self.course.id}").text
        self.assertIn("Session complète", page)
        self.assertNotIn(url, page)
        self.assertIn('role="alert"', self.url_open(url, data=current_payload).text)
        self.assertFalse(self.env["crm.lead"].search_count([("training_requested_delivery_id", "=", delivery.id)]))

    def test_public_session_card_shows_local_schedule_sitting_mode_and_confirmation(self):
        zone = ZoneInfo("Europe/Paris")
        day = fields.Date.today() + timedelta(days=40)
        first = datetime.combine(day, time(9, 0), tzinfo=zone)
        last = datetime.combine(day + timedelta(days=2), time(17, 0), tzinfo=zone)
        delivery = self.delivery(
            program_id=self.public_program.id,
            kind="session",
            capacity=8,
            timezone="Europe/Paris",
            start_at=first.astimezone(UTC).replace(tzinfo=None),
            end_at=last.astimezone(UTC).replace(tzinfo=None),
        )
        self.env["training.session"].with_user(self.coordinator).create(
            {
                "name": "Fictional remote days",
                "delivery_id": delivery.id,
                "instructor_id": self.coordinator.partner_id.id,
                "mode": "remote",
                "location": "Fictional private access code",
                "meeting_url": "https://meeting.example.invalid/fictional-private-room",
                "start_date": day,
                "end_date": day + timedelta(days=2),
                "start_hour": 9,
                "end_hour": 17,
            }
        )
        self.course.sudo().public_catalogue = True
        delivery.action_publish_session(reason="Fictional publication")
        self.authenticate(None, None)
        self.assertNotIn("Session confirmée", self.url_open(f"/formations/catalogue/{self.course.id}").text)
        delivery.action_confirm()
        page = self.url_open(f"/formations/catalogue/{self.course.id}").text
        self.assertIn("Session confirmée", page)
        self.assertIn("9 h – 17 h", page)
        # The sitting is remote although the programme default is on site.
        self.assertTrue(any(label in page for label in ("Remote", "Distanciel")))
        self.assertNotIn("Fictional private access code", page)
        self.assertNotIn("fictional-private-room", page)
        self.assertNotIn(" Z ", page)
        self.assertNotIn("+01:00", page)
        self.assertNotIn("+02:00", page)

    def test_public_inter_company_price_is_unique_per_course_and_excludes_taxes(self):
        products = self.env["product.template"]
        values = {
            "name": "Fictional inter-company tariff",
            "type": "service",
            "training_course_id": self.course.id,
            "training_price_basis": "person",
            "list_price": 1200.0,
            "taxes_id": [(5, 0, 0)],
        }
        tariff = products.create({**values, "training_public_session_price": True})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            products.create({**values, "name": "Fictional second tariff", "training_public_session_price": True})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            products.create({**values, "training_price_basis": "package", "training_public_session_price": True})
        self.course.sudo().public_catalogue = True
        facts = self.course.sudo()._catalogue_facts(self.company)[self.course.id]
        self.assertEqual(facts["session_price"]["amount"], 1200.0)
        self.assertIn("1", facts["session_price"]["label"])
        tariff.training_public_session_price = False
        self.assertIsNone(self.course.sudo()._catalogue_facts(self.company)[self.course.id]["session_price"])
