from odoo import Command
from odoo.tests import HttpCase, JsonRpcException, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestTrainingPortalHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        partner = cls.env["res.partner"].create({"name": "Fictional Portal Buyer"})
        course = cls.env["training.course"].create({
            "name": "Fictional Portal Course", "company_id": company.id,
        })
        program = cls.env["training.program.version"].create({
            "course_id": course.id, "version": "V1", "title": "Portal Programme",
            "objectives": "Learn safely", "target_audience": "Managers",
            "prerequisites": "None", "content": "Workshop", "duration_hours": 7,
            "delivery_mode": "onsite", "language_id": cls.env.ref("base.lang_en").id,
            "teaching_methods": "Exercises", "evaluation_criteria": "Review",
            "access_conditions": "Manual approval", "accessibility_contact_id": partner.id,
            "accessibility_information": "Contact us",
        })
        program.action_validate()
        product = cls.env["product.template"].create({
            "name": "Fictional Portal Training", "type": "service",
            "taxes_id": [Command.clear()], "company_id": company.id,
            "training_course_id": course.id, "training_price_basis": "package",
        }).product_variant_id
        eur = cls.env.ref("base.EUR")
        eur.active = True
        pricelist = cls.env["product.pricelist"].create({
            "name": "Fictional Portal EUR", "company_id": company.id,
            "currency_id": eur.id,
        })
        cls.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "compute_price": "fixed", "fixed_price": 100,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": partner.id, "company_id": company.id,
            "pricelist_id": pricelist.id, "training_request_kind": "group",
            "training_requested_program_id": program.id,
            "training_attendee_count": 5,
            "training_requested_currency_id": eur.id,
            "prepayment_percent": 0.25,
        })
        cls.env["sale.order.line"].create({
            "order_id": cls.order.id, "product_id": product.id,
            "product_uom_qty": 1, "training_program_id": program.id,
        })
        cls.order._portal_ensure_token()

    def test_portal_does_not_offer_payment_or_create_transaction(self):
        self.assertEqual(self.order.amount_total, 100)
        self.authenticate(None, None)
        response = self.url_open(
            self.order.get_portal_url(query_string="&payment_amount=100"),
            allow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id="o_payment_form"', response.text)
        self.assertNotIn('id="payment_method"', response.text)
        with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
            self.make_jsonrpc_request(
                f"/my/orders/{self.order.id}/transaction",
                {"access_token": self.order.access_token},
            )
        self.assertFalse(self.order.transaction_ids)
