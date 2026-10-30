"""P09.3: native detailed quotations, common beneficiaries and prior work reuse."""

from lxml import html as html_parser

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, new_test_user, tagged
from odoo.tools.translate import load_language
from odoo.addons.training_management.tests.test_path import PathCase


class PathSaleCase(PathCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coordinator = new_test_user(
            cls.env,
            login="p093_coord",
            groups="training_management.group_training_coordinator,sales_team.group_sale_salesman",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.seller = new_test_user(cls.env, login="p093_seller", groups="sales_team.group_sale_salesman")
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls.pricelist = cls.env["product.pricelist"].create(
            {"name": "Fictional agreed EUR", "currency_id": cls.eur.id, "company_id": cls.company.id}
        )

    def offer(self, count=2, selected=None, basis="package"):
        path = self.path()
        path.action_validate()
        products = []
        for step in path.step_ids:
            products.append(
                self.env["product.product"].create(
                    {
                        "name": step.program_id.title,
                        "type": "service",
                        "company_id": self.company.id,
                        "training_course_id": step.course_id.id,
                        "training_price_basis": basis,
                        "taxes_id": [Command.clear()],
                        "invoice_policy": "order",
                    }
                )
            )
        order = (
            self.env["sale.order"]
            .with_user(self.coordinator)
            .create({"partner_id": self.customer.id, "user_id": self.coordinator.id, "pricelist_id": self.pricelist.id})
        )
        with Form(
            self.env["training.path.quote"].with_user(self.coordinator).with_context(default_order_id=order.id)
        ) as form:
            form.path_id = path
            form.request_kind = "individual" if count == 1 else "group"
            form.attendee_count = count
            form.price_basis = basis
            for index in range(len(form.line_ids)):
                with form.line_ids.edit(index) as line:
                    line.price_unit = 100 + index * 50
                    if selected is not None:
                        line.selected = index in selected
        form.record.action_apply()
        return order, path

    def commercial_lot(self, order, step_index, quantity=None, delivery=None):
        line = order.order_line.filtered("training_path_step_id").sorted(
            lambda item: item.training_path_step_id.sequence
        )[step_index]
        delivery = delivery or self.delivery(program_id=line.training_program_id.id)
        lot = self.lot(
            delivery,
            quantity=quantity or order.training_attendee_count,
            sale_line_id=line.id,
            source_reference=f"FICT-P093-{delivery.id}",
        )
        lot.action_confirm()
        return lot

    def named(self, lot, participant=None):
        return self.enrollment(
            lot.delivery_id,
            allocation_id=lot.id,
            free_reason=False,
            participant_id=(participant or self.portal.partner_id).id,
            user_id=self.portal.id if not participant or participant == self.portal.partner_id else False,
        )


@tagged("post_install", "-at_install")
class TestPathSale(PathSaleCase):
    def test_native_wizard_full_and_partial_quotes_no_catalogue_tariffs(self):
        order, path = self.offer()
        self.assertEqual(order.training_path_scope, "complete")
        self.assertEqual(order.training_price_source, "quote")
        self.assertEqual(set(order.order_line.training_path_step_id.ids), set(path.step_ids.ids))
        self.assertEqual(order.amount_untaxed, 250)
        self.assertFalse(self.pricelist.item_ids)
        self.assertFalse(self.env["training.enrollment"].search([]))
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertFalse(self.env["training.enrollment"].search([]))
        partial, partial_path = self.offer(count=1, selected={1}, basis="person")
        self.assertEqual(partial.training_path_scope, "selection")
        self.assertEqual(partial.order_line.training_program_id, partial_path.step_ids[1].program_id)
        self.assertEqual(partial.amount_untaxed, 150)
        partial.action_confirm()
        self.assertFalse(partial._has_to_be_paid())

    def test_partial_purchase_does_not_waive_prerequisites(self):
        order, _ = self.offer(count=1, selected={1}, basis="person")
        order.action_confirm()
        lot = self.commercial_lot(order, 0)
        enrollment = self.named(lot)
        enrollment.action_validate_prerequisites(reason="Fictional admission")
        enrollment.action_confirm()
        enrollment.action_authorize(reason="Fictional authorization")
        self.assertTrue(enrollment._path_blocked())
        with self.assertRaises(ValidationError):
            enrollment.action_open_access(reason="Fictional opening")
        self.assertEqual(len(self.env["training.path.assignment"].search([("enrollment_id", "=", enrollment.id)])), 1)

    def test_each_course_has_its_quota_and_the_contract_has_one_common_group(self):
        order, _ = self.offer()
        order.action_confirm()
        first, second = self.commercial_lot(order, 0), self.commercial_lot(order, 1)
        self.assertEqual(first.quantity + second.quantity, 4)
        person_b = self.env["res.partner"].create({"name": "Fictional common member B"})
        person_c = self.env["res.partner"].create({"name": "Fictional excess member C"})
        for lot in (first, second):
            self.named(lot)
            self.named(lot, person_b)
        self.assertEqual(len(self.env["training.path.sale.usage"].search([("order_id", "=", order.id)])), 4)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.named(second, person_c)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.commercial_lot(order, 0, quantity=1)
        self.assertEqual(
            first.delivery_id.enrollment_ids.participant_id, second.delivery_id.enrollment_ids.participant_id
        )

    def test_negotiated_values_and_accepted_scope_are_preserved(self):
        order, path = self.offer()
        lines = order.order_line.filtered("training_path_step_id")
        lines[0].write({"price_unit": 80, "discount": 10})
        self.assertEqual(order.amount_untaxed, 222)
        order.action_confirm()
        for record, values in (
            (order, {"training_attendee_count": 3}),
            (order, {"training_path_scope": "selection"}),
            (order, {"training_price_source": "pricelist"}),
            (lines[0], {"training_path_step_id": path.step_ids[1].id}),
        ):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                record.write(values)
        with self.assertRaises((ValidationError, AccessError)), self.cr.savepoint():
            lines[0].unlink()
        lines[0].write({"price_unit": 90, "discount": 5})
        self.assertEqual(lines[0].price_subtotal, 85.5)
        copied = order.copy()
        self.assertEqual(copied.state, "draft")
        self.assertEqual(copied.amount_untaxed, order.amount_untaxed)
        self.assertFalse(copied.training_path_usage_ids)
        self.assertFalse(copied.training_agreed_at)
        self.assertTrue(order.training_agreed_at)
        order.action_cancel()
        order.action_draft()
        lines[0].price_unit = 1
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.training_attendee_count = 3
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lines[0].copy({"order_id": order.id, "is_downpayment": True})

    def test_draft_line_cannot_be_moved_into_an_accepted_contract(self):
        accepted, _ = self.offer()
        accepted.action_confirm()
        draft = (
            self.env["sale.order"]
            .with_user(self.coordinator)
            .create(
                {
                    "partner_id": self.customer.id,
                    "user_id": self.coordinator.id,
                    "pricelist_id": self.pricelist.id,
                }
            )
        )
        product = self.env["product.product"].create(
            {"name": "Fictional additional service", "type": "service", "taxes_id": [Command.clear()]}
        )
        line = (
            self.env["sale.order.line"]
            .with_user(self.coordinator)
            .create(
                {
                    "order_id": draft.id,
                    "product_id": product.id,
                    "product_uom_qty": 1,
                    "price_unit": 45,
                }
            )
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            line.write({"order_id": accepted.id})
        self.assertEqual(line.order_id, draft)
        self.assertEqual(accepted.amount_untaxed, 250)

    def test_native_down_payment_final_invoice_credit_and_quotation_report(self):
        order, path = self.offer()
        order = order.with_user(self.env.user)
        income = self.env["account.account"].create(
            {
                "name": "Fictional path income",
                "code": "709903",
                "account_type": "income",
                "company_ids": [Command.set(self.company.ids)],
            }
        )
        receivable = self.env["account.account"].create(
            {
                "name": "Fictional path receivable",
                "code": "349903",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [Command.set(self.company.ids)],
            }
        )
        advance_account = self.env["account.account"].create(
            {
                "name": "Fictional path advances",
                "code": "449903",
                "account_type": "liability_current",
                "company_ids": [Command.set(self.company.ids)],
            }
        )
        self.company.downpayment_account_id = advance_account
        self.env["account.journal"].create(
            {
                "name": "Fictional path sales",
                "code": "P93",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": income.id,
            }
        )
        order.partner_invoice_id.with_company(self.company).property_account_receivable_id = receivable
        order.order_line.product_id.product_tmpl_id.property_account_income_id = income
        order.action_confirm()
        label = order.training_path_label
        html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", order.ids)[0]
        self.assertIn(label, html.decode() if isinstance(html, bytes) else html)
        wizard = self.env["sale.advance.payment.inv"].with_context(active_model="sale.order", active_ids=order.ids)
        wizard.create(
            {
                "sale_order_ids": [Command.set(order.ids)],
                "advance_payment_method": "percentage",
                "amount": 20,
            }
        ).create_invoices()
        advance = order.invoice_ids
        self.assertEqual(advance.amount_untaxed, 50)
        advance.action_post()
        wizard.create(
            {
                "sale_order_ids": [Command.set(order.ids)],
                "advance_payment_method": "delivered",
                "deduct_down_payments": True,
            }
        ).create_invoices()
        final = order.invoice_ids - advance
        self.assertEqual(final.amount_untaxed, 200)
        final.action_post()
        credit = final._reverse_moves([{"ref": "Fictional manual path credit"}], cancel=False)
        self.assertEqual(credit.move_type, "out_refund")
        self.assertEqual(credit.amount_untaxed, 200)
        credit.action_post()
        self.assertEqual(order.amount_untaxed, 250)
        self.assertFalse(order.training_path_usage_ids)
        self.assertFalse(self.env["training.enrollment"].search([]))
        self.assertEqual(order.training_path_id, path)
        downpayment_line = order.order_line.filtered(lambda line: line.is_downpayment and not line.display_type)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            downpayment_line.write({"is_downpayment": False})

    def test_french_native_assistant_and_quotation(self):
        load_language(self.cr, "fr_FR")
        order, _ = self.offer()
        assistant = self.env["training.path.quote"].with_user(self.coordinator).with_context(lang="fr_FR")
        view = assistant.get_view(self.env.ref("training_management_sale.view_path_quote_form").id, "form")
        self.assertIn("Préparer le devis", view["arch"])
        fields_description = assistant.fields_get(["price_basis", "attendee_count"])
        self.assertEqual(fields_description["attendee_count"]["string"], "Bénéficiaires prévus")
        self.assertEqual(fields_description["price_basis"]["string"], "Base tarifaire")
        order.partner_id.lang = "fr_FR"
        html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", order.ids)[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn("Parcours complet", html)
        self.assertIn("<strong>Parcours :</strong>", html)
        self.assertIn("<strong>Bénéficiaires :</strong>", html)
        self.assertEqual(
            html_parser.fromstring(html).xpath('string(//*[@name="training_path_beneficiaries"])').strip(), "2"
        )

    def test_completed_prior_work_reused_and_counted_without_new_enrollment(self):
        order, path = self.offer(count=1)
        order.action_confirm()
        delivery = self.delivery(program_id=path.step_ids[0].program_id.id)
        activity = self.activity(delivery, criterion="declaration")
        old = self.opened(delivery)
        self.service()._declare(old.id, activity.id)
        old.action_close(reason="Fictional historical completion")
        before = self.env["training.enrollment"].search_count([])
        wizard = (
            self.env["training.path.reuse"]
            .with_user(self.coordinator)
            .create({"order_id": order.id, "step_id": path.step_ids[0].id, "enrollment_id": old.id})
        )
        wizard.action_apply()
        wizard.action_apply()
        self.assertEqual(self.env["training.enrollment"].search_count([]), before)
        self.assertEqual(order.amount_untaxed, 250)
        self.assertEqual(len(order.training_path_usage_ids), 1)
        self.assertEqual(len(old.learning_progress_ids), 1)
        self.assertEqual(old.access_state, "revoked")
        lot = self.commercial_lot(order, 1)
        outsider = self.env["res.partner"].create({"name": "Fictional different beneficiary"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.named(lot, outsider)
        enrollment = self.named(lot)
        self.assertFalse(enrollment._path_blocked())

    def test_ordinary_manual_quote_supported_without_rewriting_legacy_policy(self):
        order, path = self.offer(count=1, selected={0}, basis="person")
        line = order.order_line.filtered("training_program_id")
        plain = (
            self.env["sale.order"]
            .with_user(self.coordinator)
            .create(
                {
                    "partner_id": self.customer.id,
                    "user_id": self.coordinator.id,
                    "pricelist_id": self.pricelist.id,
                    "training_request_kind": "individual",
                    "training_attendee_count": 1,
                    "training_requested_currency_id": self.eur.id,
                    "training_requested_program_id": line.training_program_id.id,
                    "training_price_source": "quote",
                    "order_line": [
                        Command.create(
                            {
                                "product_id": line.product_id.id,
                                "training_program_id": line.training_program_id.id,
                                "product_uom_qty": 1,
                                "price_unit": 73,
                            }
                        )
                    ],
                }
            )
        )
        plain.action_confirm()
        self.assertEqual(plain.amount_untaxed, 73)
        legacy = plain.copy({"training_price_source": False})
        legacy.action_confirm()
        self.assertEqual(legacy.amount_untaxed, 73)

    def test_restricted_roles_and_forged_metadata(self):
        order, path = self.offer()
        with self.assertRaises(AccessError):
            order.with_user(self.seller).action_prepare_training_path()
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["training.path.quote"].with_user(self.seller).create({"order_id": order.id, "path_id": path.id})
        with self.assertRaises(AccessError):
            self.env["training.path.quote"].with_user(self.seller).new({"order_id": order.id}).currency_id
        wizard = (
            self.env["training.path.quote"]
            .with_user(self.coordinator)
            .create({"order_id": order.id, "path_id": path.id})
        )
        with self.assertRaises(AccessError):
            wizard.with_user(self.seller).read(["path_id", "company_id"])
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["training.path.quote.line"].with_user(self.seller).create(
                {"wizard_id": wizard.id, "step_id": path.step_ids[0].id}
            )
        with self.assertRaises(AccessError):
            path.with_user(self.portal).read(["name"])
        self.assertEqual(path.with_user(self.seller).name, path.name)
        order.action_confirm()
        lot = self.commercial_lot(order, 0)
        enrollment = self.named(lot)
        usage = order.training_path_usage_ids
        for user in (self.portal, self.seller, self.reader):
            with self.assertRaises(AccessError):
                usage.with_user(user).read(["reference_id"])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["training.path.sale.usage"].with_user(self.coordinator).create(
                {"order_id": order.id, "reference_id": usage.reference_id.id, "recorded_by_id": self.portal.id}
            )
        with self.assertRaises(AccessError):
            usage.write({"recorded_at": fields.Datetime.now()})
        self.assertEqual(enrollment.access_state, "unopened")
        foreign = self.env["training.path"].create(
            {"name": "Fictional foreign path", "company_id": self.other_company.id}
        )
        with self.assertRaises(AccessError):
            foreign.with_user(self.seller).read(["name"])
        reference = usage.reference_id
        with self.assertRaises(ValidationError), self.cr.savepoint():
            usage.action_withdraw()
        usage.action_withdraw(reason="Fictional commercial correction")
        at = usage.withdrawn_at
        usage.action_withdraw(reason="Fictional repeated correction")
        self.assertEqual(usage.withdrawn_at, at)
        self.assertEqual(usage.withdrawn_by_id, self.coordinator)
        self.assertFalse(reference.withdrawn_at)
        self.assertEqual(enrollment.access_state, "unopened")
