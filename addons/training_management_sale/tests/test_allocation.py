from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.addons.training_management.tests.test_enrollment import EnrollmentCase


@tagged("post_install", "-at_install")
class TestAllocationCommerce(EnrollmentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coordinator = new_test_user(cls.env, login="s03_commercial_coord", groups="training_management.group_training_coordinator,sales_team.group_sale_salesman", company_id=cls.company.id, company_ids=[Command.set(cls.company.ids)])
        cls.seller = new_test_user(cls.env, login="s03_seller", groups="sales_team.group_sale_salesman")
        cls.finance = new_test_user(cls.env, login="s03_finance", groups="account.group_account_invoice")
        cls.product = cls.env["product.template"].create({"name": "Fictional S03 Package", "type": "service", "company_id": cls.company.id, "training_course_id": cls.course.id, "training_price_basis": "package", "taxes_id": [Command.clear()]}).product_variant_id
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls.pricelist = cls.env["product.pricelist"].create({"name": "Fictional S03 EUR", "currency_id": cls.eur.id, "company_id": cls.company.id})
        cls.env["product.pricelist.item"].create({"pricelist_id": cls.pricelist.id, "product_tmpl_id": cls.product.product_tmpl_id.id, "applied_on": "1_product", "compute_price": "fixed", "fixed_price": 100})

    def order(self, count=10):
        order = self.env["sale.order"].with_user(self.coordinator).create({
            "partner_id": self.customer.id, "user_id": self.coordinator.id,
            "pricelist_id": self.pricelist.id, "training_request_kind": "group",
            "training_requested_program_id": self.program.id,
            "training_requested_currency_id": self.eur.id, "training_attendee_count": count,
            "order_line": [Command.create({"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 100, "training_program_id": self.program.id})],
        })
        order.action_confirm()
        return order

    def test_package_ten_places_seven_names_and_no_access_by_sale(self):
        delivery = self.delivery()
        order = self.order()
        self.assertFalse(delivery.enrollment_ids)
        lot = self.lot(delivery, sale_line_id=order.order_line.id)
        lot.action_confirm()
        for index in range(7):
            person = self.env["res.partner"].create({"name": "Fictional Buyer Employee %s" % index})
            e = self.enrollment(delivery, participant_id=person.id, user_id=False, allocation_id=lot.id, free_reason=False)
            e.change_reason = "Review completed"
            e.action_validate_prerequisites()
            e.action_confirm()
            self.assertEqual(e.access_state, "unopened")
        self.assertEqual(lot.unnamed_seats, 3)
        self.assertEqual(delivery.occupied_seats, 10)
        self.assertEqual(order.order_line.product_uom_qty, 1)
        with self.assertRaises(ValidationError):
            self.lot(self.delivery(), source_reference="EXCESS", quantity=1, sale_line_id=order.order_line.id)
        with self.assertRaises(ValidationError):
            order.write({"training_attendee_count": 20})
        with self.assertRaises(ValidationError):
            order.order_line.write({"product_uom_qty": 2})
        with self.assertRaises(ValidationError):
            order.action_cancel()

    def test_b2b_deferred_manual_authorization(self):
        order = self.order(count=1)
        delivery = self.delivery()
        lot = self.lot(delivery, quantity=1, sale_line_id=order.order_line.id)
        lot.action_confirm()
        e = self.enrollment(delivery, allocation_id=lot.id, free_reason=False)
        e.change_reason = "Approved B2B payment after delivery"
        e.action_waive_prerequisites()
        e.action_confirm()
        e.action_authorize()
        e.action_open_access()
        self.assertEqual(e.effective_access, "active")
        self.assertFalse(order.invoice_ids)
        self.assertFalse(order.training_portal_partner_ids)
        for user in (self.seller, self.finance, self.portal):
            with self.assertRaises(AccessError):
                e.with_user(user).action_authorize()
        lot.change_reason = "Cancel participation, review financial impact separately"
        lot.action_cancel()
        self.assertEqual(e.access_state, "revoked")
        self.assertEqual(order.state, "sale")
        order.action_cancel()

    def test_release_partial_lot_and_reallocate_without_double_sale(self):
        order = self.order()
        first = self.lot(self.delivery(), sale_line_id=order.order_line.id)
        first.action_confirm()
        first.change_reason = "Release two places for another realization"
        first.action_release_places(2)
        self.assertEqual(first.quantity, 8)
        second = self.lot(self.delivery(), quantity=2, sale_line_id=order.order_line.id)
        second.action_confirm()
        self.assertEqual(first.quantity + second.quantity, 10)
        self.assertEqual(order.training_attendee_count, 10)
        self.assertTrue(first.delivery_id.operation_ids.filtered(lambda row: 'quantity' in row.before))

    def test_source_identity_company_and_unreadable_order_refused(self):
        order = self.order(count=1)
        other = self.env["res.partner"].create({"name": "Another Fictional Customer"})
        with self.assertRaises(ValidationError):
            self.lot(self.delivery(), quantity=1, sale_line_id=order.order_line.id, customer_id=other.id)
        coordinator_only = new_test_user(self.env, login="s03_coord_without_sales", groups="training_management.group_training_coordinator")
        delivery = self.delivery().with_user(coordinator_only)
        with self.assertRaises(AccessError):
            self.env["training.seat.allocation"].with_user(coordinator_only).create({"delivery_id": delivery.id, "quantity": 1, "source_reference": "UNREADABLE", "customer_id": self.customer.id, "sale_line_id": order.order_line.id, "expires_at": fields.Datetime.now() + timedelta(days=1)})
        self.assertFalse(delivery.allocation_ids)

    def test_multiple_lines_do_not_multiply_order_entitlement(self):
        order = self.order(count=1)
        second_line = order.order_line.copy({"order_id": order.id})
        first = self.lot(self.delivery(), quantity=1, sale_line_id=order.order_line[0].id)
        first.action_confirm()
        with self.assertRaises(ValidationError):
            self.lot(self.delivery(), quantity=1, sale_line_id=second_line.id)

    def test_native_partial_release_wizard(self):
        from odoo.tests import Form
        order = self.order()
        lot = self.lot(self.delivery(), sale_line_id=order.order_line.id)
        lot.action_confirm()
        action = lot.action_open_release()
        form = Form(self.env[action["res_model"]].with_user(self.coordinator).with_context(action["context"]))
        form.quantity = 2
        form.reason = "Two places released, no automatic commercial refund"
        form.save().action_apply()
        self.assertEqual(lot.quantity, 8)
        self.assertEqual(order.state, "sale")
