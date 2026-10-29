from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.addons.training_management.tests.test_enrollment import EnrollmentCase


@tagged("post_install", "-at_install")
class TestAllocationCommerce(EnrollmentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coordinator = new_test_user(
            cls.env,
            login="s03_commercial_coord",
            groups="training_management.group_training_coordinator,sales_team.group_sale_salesman",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.seller = new_test_user(cls.env, login="s03_seller", groups="sales_team.group_sale_salesman")
        cls.finance = new_test_user(cls.env, login="s03_finance", groups="account.group_account_invoice")
        cls.product = (
            cls.env["product.template"]
            .create(
                {
                    "name": "Fictional S03 Package",
                    "type": "service",
                    "company_id": cls.company.id,
                    "training_course_id": cls.course.id,
                    "training_price_basis": "package",
                    "taxes_id": [Command.clear()],
                }
            )
            .product_variant_id
        )
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls.pricelist = cls.env["product.pricelist"].create(
            {"name": "Fictional S03 EUR", "currency_id": cls.eur.id, "company_id": cls.company.id}
        )
        cls.env["product.pricelist.item"].create(
            {
                "pricelist_id": cls.pricelist.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "applied_on": "1_product",
                "compute_price": "fixed",
                "fixed_price": 100,
            }
        )

    def order(self, count=10):
        order = (
            self.env["sale.order"]
            .with_user(self.coordinator)
            .create(
                {
                    "partner_id": self.customer.id,
                    "user_id": self.coordinator.id,
                    "pricelist_id": self.pricelist.id,
                    "training_request_kind": "group",
                    "training_requested_program_id": self.program.id,
                    "training_requested_currency_id": self.eur.id,
                    "training_attendee_count": count,
                    "order_line": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1,
                                "price_unit": 100,
                                "training_program_id": self.program.id,
                            }
                        )
                    ],
                }
            )
        )
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
            e = self.enrollment(
                delivery, participant_id=person.id, user_id=False, allocation_id=lot.id, free_reason=False
            )
            e.action_validate_prerequisites(reason="Review completed")
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
        e.action_waive_prerequisites(reason="Approved B2B payment after delivery")
        e.action_confirm()
        e.action_authorize(reason="Fictional B2B authorization")
        e.action_open_access(reason="Fictional B2B opening")
        self.assertEqual(e.effective_access, "active")
        self.assertFalse(order.invoice_ids)
        self.assertFalse(order.training_portal_partner_ids)
        for user in (self.seller, self.finance, self.portal):
            with self.assertRaises(AccessError):
                e.with_user(user).action_authorize(reason="Forbidden attempt")
        lot.action_cancel(reason="Cancel participation, review financial impact separately")
        self.assertEqual(e.access_state, "revoked")
        self.assertEqual(order.state, "sale")
        order.action_cancel()

    def test_release_partial_lot_and_reallocate_without_double_sale(self):
        order = self.order()
        first = self.lot(self.delivery(), sale_line_id=order.order_line.id)
        first.action_confirm()
        first.action_release_places(2, reason="Release two places for another realization")
        self.assertEqual(first.quantity, 8)
        second = self.lot(self.delivery(), quantity=2, sale_line_id=order.order_line.id)
        second.action_confirm()
        self.assertEqual(first.quantity + second.quantity, 10)
        self.assertEqual(order.training_attendee_count, 10)
        self.assertTrue(first.delivery_id.operation_ids.filtered(lambda row: "quantity" in row.before))

    def test_source_identity_company_and_unreadable_order_refused(self):
        order = self.order(count=1)
        other = self.env["res.partner"].create({"name": "Another Fictional Customer"})
        with self.assertRaises(ValidationError):
            self.lot(self.delivery(), quantity=1, sale_line_id=order.order_line.id, customer_id=other.id)
        coordinator_only = new_test_user(
            self.env, login="s03_coord_without_sales", groups="training_management.group_training_coordinator"
        )
        delivery = self.delivery().with_user(coordinator_only)
        with self.assertRaises(AccessError):
            self.env["training.seat.allocation"].with_user(coordinator_only).create(
                {
                    "delivery_id": delivery.id,
                    "quantity": 1,
                    "source_reference": "UNREADABLE",
                    "customer_id": self.customer.id,
                    "sale_line_id": order.order_line.id,
                    "expires_at": fields.Datetime.now() + timedelta(days=1),
                }
            )
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
        form = Form(self.env[action["res_model"]].with_user(self.coordinator).with_context(action["context"]))  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
        form.quantity = 2
        form.reason = "Two places released, no automatic commercial refund"
        form.save().action_apply()
        self.assertEqual(lot.quantity, 8)
        self.assertEqual(order.state, "sale")

    def test_cancelled_lot_no_longer_freezes_line_or_order(self):
        moves = self.env["account.move"].search([])
        payments = self.env["account.payment"].search([])
        order = self.order(count=1)
        lot = self.lot(self.delivery(), quantity=1, sale_line_id=order.order_line.id)
        lot.action_confirm()
        with self.assertRaises(ValidationError):
            order.order_line.write({"product_uom_qty": 2})
        lot.action_cancel(reason="Lot withdrawn before the session")
        order.order_line.write({"product_uom_qty": 2})
        self.assertEqual(order.order_line.product_uom_qty, 2)
        order.action_cancel()
        self.assertEqual(order.state, "cancel")
        self.assertEqual(self.env["account.move"].search([]), moves)
        self.assertEqual(self.env["account.payment"].search([]), payments)

    def test_expired_lot_binds_the_order_only_while_an_enrollment_stays_open(self):
        order = self.order(count=1)
        delivery = self.delivery()
        lot = self.lot(delivery, quantity=1, sale_line_id=order.order_line.id)
        e = self.enrollment(delivery, allocation_id=lot.id, free_reason=False)
        e.action_reserve()
        future = lot.expires_at + timedelta(seconds=1)
        with patch("odoo.fields.Datetime.now", return_value=future):
            lot.action_expire()
        self.assertEqual(lot.state, "expired")
        self.assertEqual(e.state, "requested")
        with self.assertRaises(ValidationError):
            order.order_line.write({"product_uom_qty": 2})
        with self.assertRaises(ValidationError):
            order.action_cancel()
        e.action_cancel(reason="Request withdrawn")
        order.order_line.write({"product_uom_qty": 2})
        order.action_cancel()
        self.assertEqual(order.state, "cancel")

    def test_salesperson_reads_states_but_not_admission_access_or_history(self):
        order = self.order(count=2)
        delivery = self.delivery()
        lot = self.lot(delivery, quantity=2, sale_line_id=order.order_line.id)
        lot.action_confirm()
        e = self.enrollment(delivery, allocation_id=lot.id, free_reason=False)
        e.action_waive_prerequisites(reason="Approved B2B payment after delivery")
        e.action_confirm()
        e.action_authorize(reason="Fictional authorization")
        e.action_open_access(reason="Fictional opening")
        seller = self.seller
        self.assertEqual(delivery.with_user(seller).state, delivery.state)
        self.assertEqual(delivery.with_user(seller).reference, delivery.reference)
        self.assertEqual(lot.with_user(seller).state, "confirmed")
        self.assertEqual(lot.with_user(seller).quantity, 2)
        self.assertEqual(e.with_user(seller).state, "confirmed")
        for record, name in (
            (e, "prerequisites"),
            (e, "user_id"),
            (e, "access_state"),
            (e, "access_start"),
            (e, "access_end"),
            (e, "effective_access"),
            (delivery, "operation_ids"),
        ):
            with self.subTest(field=name), self.assertRaises(AccessError):
                record.with_user(seller).read([name])
        with self.assertRaises(AccessError):
            self.env["training.operation"].with_user(seller).search([])
        for record in (delivery, lot, e):
            with self.assertRaises(AccessError):
                record.with_user(seller)._require_coordinator()
        with self.assertRaises(AccessError):
            self.env["training.enrollment"].with_user(seller).create(
                {"delivery_id": delivery.id, "participant_id": self.portal.partner_id.id}
            )
        with self.assertRaises((AccessError, ValidationError)):
            e.with_user(seller).unlink()
        self.assertTrue(e.exists())

    def test_salesperson_of_another_company_sees_nothing(self):
        delivery = self.delivery()
        other = new_test_user(
            self.env,
            login="s03_seller_b",
            groups="sales_team.group_sale_salesman",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        self.assertFalse(self.env["training.delivery"].with_user(other).search([("id", "=", delivery.id)]))

    def test_s04_commercial_cannot_access_positioning_or_adaptations(self):
        delivery = self.delivery(sponsor_need="Fictional common business need")
        enrollment = self.enrollment(delivery)
        enrollment.write({"positioning": "CONFIDENTIAL POSITIONING", "instructor_summary": "Useful summary"})
        adaptation = (
            self.env["training.adaptation"]
            .with_user(self.coordinator)
            .create(
                {
                    "delivery_id": delivery.id,
                    "enrollment_id": enrollment.id,
                    "details": "CONFIDENTIAL ARRANGEMENT",
                    "decision": "Fictional decision",
                }
            )
        )
        self.assertEqual(delivery.with_user(self.seller).sponsor_need, "Fictional common business need")
        for user in (self.seller, self.finance):
            with self.assertRaises(AccessError):
                adaptation.with_user(user).read(["details"])
            with self.assertRaises(AccessError):
                enrollment.with_user(user).read(["positioning"])
            with self.assertRaises(AccessError):
                delivery.with_user(user).action_prepare_invitations()

    def test_closure_b2b_exports_keep_explicit_customers_and_native_sales(self):
        from odoo.tools.binary import BinaryBytes
        import io
        import json
        import zipfile

        quality = new_test_user(self.env, login="s08_b2b_quality", groups="training_management.group_training_quality")
        policy = (
            self.env["training.retention.category"]
            .with_user(quality)
            .create(
                {
                    "name": "Fictional B2B policy",
                    "purpose": "Training proof",
                    "responsible_id": quality.id,
                    "duration_days": 365,
                    "archive_policy": "Restricted archive",
                    "deletion_policy": "Human review",
                }
            )
        )
        policy.action_approve()
        original_customer = self.customer
        clients, dossiers, proofs = [], [], []
        delivery = self.delivery()
        for index in range(2):
            self.customer = self.env["res.partner"].create(
                {"name": f"Fictional S08 Customer {index}", "is_company": True}
            )
            client = new_test_user(self.env, login=f"s08_b2b_client_{index}", groups="base.group_portal")
            client.partner_id.parent_id = self.customer
            clients.append(client)
            order = self.order(count=1)
            lot = self.lot(delivery, quantity=1, sale_line_id=order.order_line.id, source_reference=f"S08-{index}")
            lot.action_confirm()
            person = self.env["res.partner"].create(
                {"name": f"Fictional S08 Employee {index}", "parent_id": self.customer.id}
            )
            enrollment = self.enrollment(
                delivery, allocation_id=lot.id, free_reason=False, participant_id=person.id, user_id=False
            )
            enrollment.action_waive_prerequisites(reason="Fictional approved admission")
            enrollment.action_confirm()
            dossier = (
                self.env["training.closure"]
                .with_user(self.coordinator)
                .create(
                    {
                        "enrollment_id": enrollment.id,
                        "quality_id": quality.id,
                        "retention_id": policy.id,
                        "client_contact_ids": [Command.set(client.partner_id.ids)],
                    }
                )
            )
            proof = (
                self.env["training.proof"]
                .with_user(quality)
                .create(
                    {
                        "dossier_id": dossier.id,
                        "category": "need",
                        "source": f"Fictional scope customer {index}",
                        "author": f"Fictional author {index}",
                        "produced_at": fields.Datetime.now(),
                        "data": BinaryBytes(b"%PDF-1.4\nFictional accepted scope\n%%EOF"),
                        "client_shared": True,
                    }
                )
            )
            proof.action_validate()
            dossiers.append(dossier)
            proofs.append(proof)
        self.customer = original_customer
        dossiers[0].with_user(quality).action_export_client()
        output = self.env["training.document"].sudo().search([("dossier_id", "=", dossiers[0].id)], limit=1)
        with zipfile.ZipFile(io.BytesIO(output.data.content)) as archive:
            index = json.loads(archive.read("index.json"))
            self.assertEqual([item["id"] for item in index["pieces"]], proofs[0].ids)
            self.assertNotIn(f"proof-{proofs[1].id}-v1.pdf", archive.namelist())
        authorization = self.env["training.document.policy"]
        self.assertTrue(authorization.with_user(clients[0])._can_read(output))
        self.assertFalse(authorization.with_user(clients[1])._can_read(output))
        # An employer change does not transfer this old explicit grant.
        clients[0].partner_id.parent_id = dossiers[1].customer_id
        self.assertFalse(authorization.with_user(clients[0])._can_read(output))
        # A dedicated achievement proof is still required in this real B2B path.
        with self.assertRaises(ValidationError):
            dossiers[0].with_user(quality).action_certificate_achievement()
