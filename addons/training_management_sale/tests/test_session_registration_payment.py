"""Online registration to a priced inter-company session (decision of 21 November 2026)."""

from datetime import timedelta

from freezegun import freeze_time
from lxml import html

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools import file_open
from odoo.tools.binary import BinaryBytes

from odoo.addons.training_management.tests.test_session_publication import SessionAlertCase, prepare_session


@tagged("post_install", "-at_install")
class TestSessionRegistrationPayment(SessionAlertCase, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.public_program = cls.public_program.copy(
            {"version": "PAID-INTER", "delivery_mode": "onsite", "public_catalogue": True}
        )
        cls.public_program.action_validate()
        cls.public_program.action_publish()
        cls.course.sudo().public_catalogue = True
        cls.tariff = cls.env["product.template"].create(
            {
                "name": "Fictional inter-company tariff",
                "company_id": cls.company.id,
                "type": "service",
                "training_course_id": cls.course.id,
                "training_price_basis": "person",
                "training_public_session_price": True,
                "list_price": 900,
                "taxes_id": [(5, 0, 0)],
            }
        )
        cls.provider = cls.env["payment.provider"].create({"name": "Fictional Provider", "code": "none"})
        with file_open("web/static/img/placeholder.png", "rb") as image:
            cls.method = cls.env["payment.method"].create(
                {
                    "name": "Fictional Method",
                    "code": "fictional",
                    "provider_id": cls.provider.id,
                    "image": BinaryBytes(image.read()),
                }
            )
        cls.portal.partner_id.lang = "fr_FR" if cls.env["res.lang"]._lang_get("fr_FR") else "en_US"

    def published_session(self, days=20, **values):
        start = fields.Datetime.now() + timedelta(days=days)
        delivery = self.delivery(
            program_id=self.public_program.id,
            kind="session",
            capacity=4,
            start_at=start,
            end_at=start + timedelta(hours=7),
            **values,
        )
        prepare_session(delivery)
        delivery.action_publish_session(reason="Fictional publication")
        return delivery

    def url(self, delivery):
        return f"/formations/catalogue/{self.course.id}/inscription/{delivery.id}"

    def form(self, delivery, count="2"):
        response = self.url_open(self.url(delivery))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        page = html.fromstring(response.content)
        return page, {
            "csrf_token": page.xpath("//input[@name='csrf_token']/@value")[0],
            "submission_token": page.xpath("//input[@name='submission_token']/@value")[0],
            "count": count,
        }

    def order_of(self, delivery):
        return self.env["sale.order"].search([("training_registration_delivery_id", "=", delivery.id)])

    def pay(self, order):
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.method.id,
                "amount": order.amount_total,
                "currency_id": order.currency_id.id,
                "partner_id": order.partner_id.id,
                "sale_order_ids": [(6, 0, order.ids)],
            }
        )
        tx = tx.with_context(payment_safe_write=True)
        tx._set_done()
        # The sales part of the native post-processing; the accounting payment needs a configured journal.
        tx._check_amount_and_confirm_order()
        return tx

    def test_unconfirmed_session_registers_without_payment_then_requests_it(self):
        delivery = self.published_session()
        url = self.url(delivery)
        # An account is required: the order, its payment and the portal are personal.
        self.authenticate(None, None)
        redirected = self.url_open(url, allow_redirects=False)
        self.assertEqual(redirected.status_code, 303)
        self.assertIn("/web/login", redirected.headers["Location"])
        self.authenticate(self.portal.login, self.portal.login)
        page, payload = self.form(delivery)
        self.assertTrue(page.xpath("//*[@id='training_registration_payment_later']"))
        self.assertIn("900", page.text_content())
        self.assertTrue(
            page.xpath(f"//a[@href='/formations/demande?kind=individual&program={self.public_program.id}']")
        )
        # A forged token, a count beyond the places and a replay create nothing more.
        self.assertEqual(self.url_open(url, data={**payload, "submission_token": "forged"}).status_code, 404)
        self.assertIn('role="alert"', self.url_open(url, data={**payload, "count": "5"}).text)
        for _attempt in range(2):
            self.assertIn("Inscription enregistrée", self.url_open(url, data=payload).text)
        order = self.order_of(delivery)
        self.assertEqual(len(order), 1)
        self.assertEqual(
            (order.state, order.partner_id, order.training_attendee_count), ("draft", self.portal.partner_id, 2)
        )
        self.assertEqual(order.training_portal_partner_ids, self.portal.partner_id)
        self.assertEqual(order.order_line.product_uom_qty, 2)
        self.assertEqual(order.amount_untaxed, 1800)
        (lot,) = order._training_registration_lots()
        self.assertEqual((lot.state, lot.quantity), ("reserved", 2))
        self.assertEqual(lot.expires_at, delivery.start_at - timedelta(days=7))
        self.assertEqual(order.training_registration_release_at, lot.expires_at)
        # The places are held without payment; a second registration of the same buyer is refused.
        self.assertEqual(delivery._public_registration_limit(), 2)
        _page, second = self.form(delivery, count="1")
        self.assertIn('role="alert"', self.url_open(url, data=second).text)
        self.assertEqual(len(self.order_of(delivery)), 1)
        waiting = self.env["mail.mail"].search([("model", "=", "sale.order"), ("res_id", "=", order.id)])
        self.assertEqual(len(waiting), 1)
        self.assertEqual(waiting.recipient_ids, self.portal.partner_id)
        # No payment before the session is confirmed, even through a direct transaction.
        self.assertFalse(order._has_to_be_paid())
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.pay(order)
        # Confirming the session asks the unpaid registration to pay, once.
        delivery.with_user(self.coordinator).action_confirm(reason="Fictional confirmation below threshold")
        self.assertEqual(order.state, "sent")
        self.assertTrue(order.training_payment_requested_at)
        self.assertTrue(order._has_to_be_paid())
        requests = self.env["mail.mail"].search([("model", "=", "sale.order"), ("res_id", "=", order.id)]) - waiting
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests.recipient_ids, self.portal.partner_id)
        self.assertIn(order.access_url, requests.body_html)
        self.assertNotIn("access_token", requests.body_html)
        order._training_request_payment()
        self.assertEqual(
            len(self.env["mail.mail"].search([("model", "=", "sale.order"), ("res_id", "=", order.id)])), 2
        )
        # The portal page offers the payment; paying confirms the order and the places, not the access.
        self.assertEqual(self.url_open(order.get_portal_url()).status_code, 200)
        self.pay(order)
        self.assertEqual(order.state, "sale")
        self.assertEqual(lot.state, "confirmed")
        self.assertFalse(delivery.sudo().enrollment_ids)

    def test_confirmed_session_goes_straight_to_payment(self):
        delivery = self.published_session()
        delivery.with_user(self.coordinator).action_confirm(reason="Fictional confirmation below threshold")
        self.authenticate(self.portal.login, self.portal.login)
        page, payload = self.form(delivery, count="1")
        self.assertTrue(page.xpath("//*[@id='training_registration_payment_now']"))
        response = self.url_open(self.url(delivery), data=payload, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        order = self.order_of(delivery)
        self.assertIn(f"/my/orders/{order.id}", response.headers["Location"])
        self.assertEqual(order.state, "sent")
        self.assertTrue(order._has_to_be_paid())
        # A colleague of the buyer neither reads nor pays this order.
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertNotEqual(self.url_open(order.get_portal_url(), allow_redirects=False).status_code, 200)
        self.pay(order)
        self.assertEqual(order._training_registration_lots().state, "confirmed")

    def test_unpaid_places_are_released_seven_days_before_the_session(self):
        delivery = self.published_session(days=8)
        self.authenticate(self.portal.login, self.portal.login)
        _page, payload = self.form(delivery, count="4")
        self.url_open(self.url(delivery), data=payload)
        order = self.order_of(delivery)
        lot = order._training_registration_lots()
        self.assertEqual(delivery._public_registration_limit(), 0)
        # One day later the release date is reached: the places return to the session.
        with freeze_time(lot.expires_at + timedelta(minutes=1)):
            self.assertFalse(lot._available())
            self.assertEqual(delivery._public_registration_limit(), 4)
            delivery.with_user(self.coordinator).action_confirm(reason="Fictional late confirmation")
            self.assertEqual(order.state, "draft")
            self.assertFalse(order.training_payment_requested_at)
            self.assertFalse(order._has_to_be_paid())
        # Too late to register on an unconfirmed session: no reservation could last.
        late = self.published_session(days=5)
        _page, payload = self.form(late, count="1")
        self.assertIn('role="alert"', self.url_open(self.url(late), data=payload).text)
        self.assertFalse(self.order_of(late))

    def test_session_without_public_price_keeps_the_request(self):
        self.tariff.training_public_session_price = False
        delivery = self.published_session()
        self.authenticate(None, None)
        response = self.url_open(self.url(delivery))
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="email"', response.text)
