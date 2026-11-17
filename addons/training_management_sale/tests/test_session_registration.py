from datetime import timedelta

from lxml import html

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
