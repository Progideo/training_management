from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.translate import load_language


@tagged("post_install", "-at_install")
class TestTrainingSale(TransactionCase):
    """COM01 and CAT02: a qualified request keeps a safe programme link."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Fictional Sales Company B"})
        cls.salesperson = new_test_user(
            cls.env,
            login="training_sale_person",
            groups="sales_team.group_sale_salesman",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.portal = new_test_user(
            cls.env,
            login="training_sale_portal",
            groups="base.group_portal",
        )
        cls.contact = cls.env["res.partner"].create({"name": "Fictional Training Contact"})
        cls.course = cls.env["training.course"].create(
            {
                "name": "Standard Course",
                "company_id": cls.company.id,
            }
        )
        cls.course.category_id = cls.env["training.category"].create({"name": "Learning", "company_id": cls.company.id})
        cls.program = cls.env["training.program.version"].create(
            {
                "course_id": cls.course.id,
                "version": "V1",
                "title": "Programme V1",
                "objectives": "Learn the method",
                "target_audience": "Managers",
                "prerequisites": "None",
                "content": "Guided workshop",
                "duration_hours": 7,
                "delivery_mode": "onsite",
                "language_id": cls.env.ref("base.lang_en").id,
                "teaching_methods": "Exercises",
                "evaluation_criteria": "Review",
                "access_conditions": "Manual approval",
                "accessibility_contact_id": cls.contact.id,
                "accessibility_information": "Contact us",
            }
        )
        cls.program.action_validate()
        cls.product = (
            cls.env["product.template"]
            .create(
                {
                    "name": "Training service per person",
                    "type": "service",
                    "company_id": cls.company.id,
                    "training_course_id": cls.course.id,
                    "training_price_basis": "person",
                }
            )
            .product_variant_id
        )
        cls.eur = cls.env.ref("base.EUR")
        cls.partner = cls.env["res.partner"].create({"name": "Fictional Buyer"})

    def test_sales_pdf_keeps_the_quoted_version_without_extra_permissions(self):
        order = self.env["sale.order"].with_user(self.salesperson).create({"partner_id": self.partner.id})
        line = (
            self.env["sale.order.line"]
            .with_user(self.salesperson)
            .create({"order_id": order.id, "product_id": self.product.id, "training_program_id": self.program.id})
        )
        original = bytes(self.program.pdf_attachment_id.raw)
        v2 = self.program.copy({"version": "V2", "content": "New content"})
        v2.action_validate()
        v2.action_publish()
        quoted = line.training_program_id
        self.assertEqual(quoted, self.program)
        self.assertEqual(bytes(quoted._reference_pdf().raw), original)
        self.assertIn(str(self.program.pdf_attachment_id.id), quoted.action_download_pdf()["url"])
        self.assertEqual(quoted.category_id, self.course.category_id)
        with self.assertRaises(AccessError):
            quoted.action_reconstruct_pdf()

    def test_crm_qualification_opens_native_quotation_with_version(self):
        lead = (
            self.env["crm.lead"]
            .with_user(self.salesperson)
            .create(
                {
                    "name": "Group request",
                    "type": "opportunity",
                    "partner_id": self.partner.id,
                    "training_request_kind": "group",
                    "training_program_id": self.program.id,
                    "training_attendee_count": 12,
                    "training_requested_currency_id": self.eur.id,
                }
            )
        )
        context = lead.action_new_quotation()["context"]
        self.assertEqual(context["default_opportunity_id"], lead.id)
        self.assertEqual(context["default_training_requested_program_id"], self.program.id)
        self.assertEqual(context["default_training_attendee_count"], 12)
        self.assertEqual(context["default_training_requested_currency_id"], self.eur.id)
        order = (
            self.env["sale.order"]  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
            .with_user(self.salesperson)
            .with_context(context)
            .create(
                {
                    "partner_id": self.partner.id,
                }
            )
        )
        self.assertEqual(order.training_requested_program_id, self.program)
        self.assertEqual(order.opportunity_id, lead)
        self.env["sale.order.line"].with_user(self.salesperson).create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 12,
                "training_program_id": self.program.id,
            }
        )
        self.assertEqual(order.order_line.training_program_id, self.program)
        self.assertEqual(order.order_line.product_uom_qty, 12)
        quoted_label = order.order_line.training_program_label
        self.assertIn("V1", quoted_label)
        self.course.name = "Renamed course"
        self.assertEqual(order.order_line.training_program_label, quoted_label)
        html = self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder",
            [order.id],
        )[0]
        self.assertIn(quoted_label, html.decode() if isinstance(html, bytes) else html)
        self.assertFalse(
            self.env["sale.order.line"].search(
                [
                    ("order_id", "=", order.id),
                    ("product_id", "=", self.product.id),
                    ("training_program_id", "=", False),
                ]
            )
        )

    def test_invalid_program_and_company_are_refused(self):
        draft = self.program.copy({"version": "V2"})
        visible = (
            self.env["training.program.version"]
            .with_user(self.salesperson)
            .search(
                [
                    ("id", "in", [self.program.id, draft.id]),
                ]
            )
        )
        self.assertEqual(visible, self.program)
        with self.assertRaises(AccessError):
            draft.with_user(self.salesperson).read(["title"])
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        for vals in (
            {"order_id": order.id, "product_id": self.product.id},
            {"order_id": order.id, "product_id": self.product.id, "training_program_id": draft.id},
        ):
            with self.assertRaises((ValidationError, AccessError)), self.cr.savepoint():
                self.env["sale.order.line"].with_user(self.salesperson).create(vals)
        with self.assertRaises(AccessError):
            self.program.with_user(self.portal).read(["title"])
        other_course = self.env["training.course"].create(
            {
                "name": "Other Company Course",
                "company_id": self.other_company.id,
            }
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["sale.order.line"].create(
                {
                    "order_id": order.id,
                    "product_id": self.product.id,
                    "training_program_id": self.env["training.program.version"]
                    .create(
                        {
                            "course_id": other_course.id,
                            "version": "V1",
                            "title": "Other",
                        }
                    )
                    .id,
                }
            )

    def test_incomplete_request_cannot_create_training_quote(self):
        load_language(self.cr, "fr_FR")
        field = self.env["ir.model.fields"].search(
            [
                ("model", "=", "crm.lead"),
                ("name", "=", "training_request_kind"),
            ],
            limit=1,
        )
        self.assertEqual(
            field.with_context(lang="fr_FR").field_description,
            "Demande de formation",
        )
        lead = self.env["crm.lead"].create(
            {
                "name": "Unqualified",
                "type": "opportunity",
                "partner_id": self.partner.id,
                "training_request_kind": "individual",
                "training_program_id": self.program.id,
            }
        )
        with self.assertRaises(ValidationError):
            lead.action_new_quotation()

    def test_commercial_roles_do_not_replace_invoice_debtor_or_grant_access(self):
        sponsor = self.env["res.partner"].create({"name": "Fictional Ordering Organisation"})
        admin_contact = self.env["res.partner"].create(
            {
                "name": "Fictional Administrative Contact",
                "type": "contact",
            }
        )
        invoice_address = self.env["res.partner"].create(
            {
                "name": "Fictional Invoice Address",
                "parent_id": self.partner.id,
                "type": "invoice",
            }
        )
        payer = self.portal.partner_id
        lead = (
            self.env["crm.lead"]
            .with_user(self.salesperson)
            .create(
                {
                    "name": "Group roles",
                    "type": "opportunity",
                    "partner_id": self.partner.id,
                    "training_request_kind": "group",
                    "training_program_id": self.program.id,
                    "training_attendee_count": 12,
                    "training_requested_currency_id": self.eur.id,
                    "training_sponsor_id": sponsor.id,
                    "training_expected_payer_id": payer.id,
                    "training_admin_contact_id": admin_contact.id,
                }
            )
        )
        context = lead.action_new_quotation()["context"]
        self.assertEqual(context["default_training_sponsor_id"], sponsor.id)
        self.assertEqual(context["default_training_expected_payer_id"], payer.id)
        self.assertEqual(context["default_training_admin_contact_id"], admin_contact.id)
        order = (
            self.env["sale.order"]  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
            .with_user(self.salesperson)
            .with_context(context)
            .create(
                {
                    "partner_id": self.partner.id,
                }
            )
        )
        self.assertEqual(order.training_sponsor_id, sponsor)
        self.assertEqual(order.training_expected_payer_id, payer)
        self.assertEqual(order.training_admin_contact_id, admin_contact)
        self.assertEqual(order.partner_invoice_id, invoice_address)
        self.assertEqual(order._prepare_invoice()["partner_id"], invoice_address.id)
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 100,
                "training_program_id": self.program.id,
            }
        )
        order.prepayment_percent = 0.25
        self.assertGreater(order.amount_total, 0)
        self.assertTrue(order._has_to_be_paid())
        link = self.env["payment.link.wizard"].create(
            {
                "res_model": "sale.order",
                "res_id": order.id,
                "amount": 25,
                "currency_id": self.eur.id,
                "partner_id": self.partner.id,
            }
        )
        self.assertTrue(link.link)
        with self.assertRaises(AccessError):
            order.with_user(self.portal).read(["name"])
        company_contact = self.env["res.partner"].create(
            {
                "name": "Fictional Buyer Colleague",
                "parent_id": self.partner.id,
            }
        )
        company_portal = new_test_user(
            self.env,
            login="training_sale_company_portal",
            groups="base.group_portal",
            partner_id=company_contact.id,
        )
        with self.assertRaises(AccessError):
            order.with_user(company_portal).read(["name"])
        order._portal_ensure_token()
        self.assertFalse(
            order.with_user(company_portal)._get_thread_with_access(
                order.id,
                token=order.access_token,
            )
        )
        order.training_portal_partner_ids = [Command.link(company_contact.id)]
        self.assertEqual(order.with_user(company_portal).read(["name"])[0]["name"], order.name)
        self.assertTrue(
            order.with_user(company_portal)._get_thread_with_access(
                order.id,
                token=order.access_token,
            )
        )
        self.assertFalse(order.copy().training_portal_partner_ids)
        private_fields = (
            "training_sponsor_id",
            "training_expected_payer_id",
            "training_admin_contact_id",
            "training_transfer_notice_ids",
            "training_portal_partner_ids",
        )
        visible_fields = order.with_user(company_portal).fields_get()
        for field_name in private_fields:
            self.assertNotIn(field_name, visible_fields)
            with self.assertRaises(AccessError):
                order.with_user(company_portal).read([field_name])

    def test_commercial_roles_respect_operating_company(self):
        foreign_contact = self.env["res.partner"].create(
            {
                "name": "Fictional Restricted Contact",
                "company_id": self.other_company.id,
            }
        )
        for model, values in (
            ("crm.lead", {"name": "Foreign sponsor", "training_request_kind": "group"}),
            ("sale.order", {"partner_id": self.partner.id, "training_request_kind": "group"}),
        ):
            with self.assertRaises(UserError), self.cr.savepoint():
                self.env[model].create(
                    {
                        **values,
                        "company_id": self.company.id,
                        "training_sponsor_id": foreign_contact.id,
                    }
                )

    def test_independent_fixed_prices_and_price_basis(self):
        mad = self.env.ref("base.MAD")
        package_product = (
            self.env["product.template"]
            .create(
                {
                    "name": "Training service package",
                    "type": "service",
                    "company_id": self.company.id,
                    "training_course_id": self.course.id,
                    "training_price_basis": "package",
                }
            )
            .product_variant_id
        )
        pricelists = {}
        for currency, person_price, package_price in (
            (mad, 900, 12000),
            (self.eur, 125, 1600),
        ):
            pricelist = self.env["product.pricelist"].create(
                {
                    "name": "Fictional training %s" % currency.name,
                    "company_id": self.company.id,
                    "currency_id": currency.id,
                }
            )
            pricelists[currency.name] = pricelist
            for product, amount in ((self.product, person_price), (package_product, package_price)):
                self.env["product.pricelist.item"].create(
                    {
                        "pricelist_id": pricelist.id,
                        "product_tmpl_id": product.product_tmpl_id.id,
                        "compute_price": "fixed",
                        "fixed_price": amount,
                    }
                )

        for currency, person_price, package_price in (
            (mad, 900, 12000),
            (self.eur, 125, 1600),
        ):
            for product, quantity, amount in (
                (self.product, 12, person_price),
                (package_product, 1, package_price),
            ):
                order = self.env["sale.order"].create(
                    {
                        "partner_id": self.partner.id,
                        "company_id": self.company.id,
                        "pricelist_id": pricelists[currency.name].id,
                        "training_request_kind": "group",
                        "training_requested_program_id": self.program.id,
                        "training_attendee_count": 12,
                        "training_requested_currency_id": currency.id,
                    }
                )
                line = self.env["sale.order.line"].create(
                    {
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": quantity,
                        "training_program_id": self.program.id,
                    }
                )
                self.assertEqual(order.currency_id, currency)
                self.assertEqual(line.price_unit, amount)
                order._check_training_offer()
                order.action_confirm()
                self.assertEqual(order.state, "sale")
                self.assertEqual(line.price_unit, amount)
                if currency == mad and product == self.product:
                    for field_name in (
                        "training_sponsor_id",
                        "training_expected_payer_id",
                        "training_admin_contact_id",
                    ):
                        with self.assertRaises(ValidationError):
                            order.write({field_name: self.partner.id})

    def test_missing_or_changed_tariff_cannot_be_sent_or_confirmed(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Fictional EUR",
                "company_id": self.company.id,
                "currency_id": self.eur.id,
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "pricelist_id": pricelist.id,
                "training_request_kind": "group",
                "training_requested_program_id": self.program.id,
                "training_attendee_count": 12,
                "training_requested_currency_id": self.eur.id,
            }
        )
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 12,
                "training_program_id": self.program.id,
            }
        )
        order._check_training_offer()  # Native fallback price needs no explicit rule.
        rule = self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "compute_price": "fixed",
                "fixed_price": 125,
            }
        )
        line.price_unit = 125
        order._check_training_offer()
        line.product_uom_qty = 1
        with self.assertRaises(ValidationError):
            order.action_confirm()
        line.product_uom_qty = 12
        line.price_unit = 126
        line.discount = 5
        rule.compute_price = "discount"
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertEqual(line.price_unit, 126)
        self.assertEqual(line.discount, 5)

    def test_taxable_down_payment_uses_company_liability_account(self):
        self.eur.active = True
        income = self.env["account.account"].create(
            {
                "name": "Fictional Taxable Training Income",
                "code": "709902",
                "account_type": "income",
                "company_ids": [Command.set([self.company.id])],
            }
        )
        downpayment = self.env["account.account"].create(
            {
                "name": "Fictional Taxable Customer Advances",
                "code": "449902",
                "account_type": "liability_current",
                "company_ids": [Command.set([self.company.id])],
            }
        )
        self.company.downpayment_account_id = downpayment
        tax = self.env["account.tax"].create(
            {
                "name": "Fictional VAT 20%",
                "amount": 20,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
            }
        )
        product = (
            self.env["product.template"]
            .create(
                {
                    "name": "Fictional Taxable EUR Package",
                    "type": "service",
                    "invoice_policy": "order",
                    "taxes_id": [Command.set(tax.ids)],
                    "company_id": self.company.id,
                    "property_account_income_id": income.id,
                    "training_course_id": self.course.id,
                    "training_price_basis": "package",
                }
            )
            .product_variant_id
        )
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Fictional Taxable EUR List",
                "company_id": self.company.id,
                "currency_id": self.eur.id,
            }
        )
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "compute_price": "fixed",
                "fixed_price": 1600,
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "pricelist_id": pricelist.id,
                "training_request_kind": "group",
                "training_requested_program_id": self.program.id,
                "training_attendee_count": 12,
                "training_requested_currency_id": self.eur.id,
            }
        )
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product.id,
                "product_uom_qty": 1,
                "training_program_id": self.program.id,
            }
        )
        order.action_confirm()
        wizard_model = self.env["sale.advance.payment.inv"].with_context(
            active_model="sale.order",
            active_ids=order.ids,
        )
        wizard_model.create(
            {
                "sale_order_ids": [Command.set(order.ids)],
                "advance_payment_method": "fixed",
                "fixed_amount": 480,
            }
        ).create_invoices()
        advance = order.invoice_ids
        self.assertEqual(advance.amount_untaxed, 400)
        self.assertEqual(advance.amount_tax, 80)
        self.assertEqual(advance.amount_total, 480)
        self.assertEqual(advance.invoice_line_ids.filtered("is_downpayment").account_id, downpayment)
        advance.action_post()
        wizard_model.create(
            {
                "sale_order_ids": [Command.set(order.ids)],
                "advance_payment_method": "delivered",
                "deduct_down_payments": True,
            }
        ).create_invoices()
        final_invoice = order.invoice_ids - advance
        self.assertEqual(final_invoice.amount_untaxed, 1200)
        self.assertEqual(final_invoice.amount_tax, 240)
        self.assertEqual(final_invoice.amount_total, 1440)
        deduction = final_invoice.invoice_line_ids.filtered("is_downpayment")
        self.assertEqual(deduction.account_id, downpayment)
        self.assertEqual(
            final_invoice.invoice_line_ids.filtered(lambda line: line.product_id == product).account_id,
            income,
        )
        self.assertNotIn("Draft", deduction.name)

    def test_training_income_account_setting_is_accountant_only(self):
        accountant = new_test_user(
            self.env,
            login="training_sale_product_accountant",
            groups="account.group_account_manager",
            company_id=self.company.id,
            company_ids=[Command.set([self.company.id])],
        )
        accountant_view = (
            self.env["product.template"]
            .with_user(accountant)
            .get_view(
                view_type="form",
            )["arch"]
        )
        salesperson_view = (
            self.env["product.template"]
            .with_user(self.salesperson)
            .get_view(
                view_type="form",
            )["arch"]
        )
        self.assertIn('name="property_account_income_id"', accountant_view)
        self.assertNotIn('name="property_account_income_id"', salesperson_view)

    def test_native_eur_down_payment_and_final_invoice(self):
        self.eur.active = True
        income = self.env["account.account"].create(
            {
                "name": "Fictional Training Income",
                "code": "709901",
                "account_type": "income",
                "company_ids": [Command.set([self.company.id])],
            }
        )
        downpayment = self.env["account.account"].create(
            {
                "name": "Fictional Customer Advances",
                "code": "449901",
                "account_type": "liability_current",
                "company_ids": [Command.set([self.company.id])],
            }
        )
        self.company.downpayment_account_id = downpayment
        receivable = self.env["account.account"].create(
            {
                "name": "Fictional Training Receivable",
                "code": "349901",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [Command.set([self.company.id])],
            }
        )
        self.env["account.journal"].create(
            {
                "name": "Fictional Training Sales",
                "code": "FTS",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": income.id,
            }
        )
        self.partner.with_company(self.company).property_account_receivable_id = receivable
        invoice_address = self.env["res.partner"].create(
            {
                "name": "Fictional Training Billing",
                "parent_id": self.partner.id,
                "type": "invoice",
                "email": "billing-generic@example.invalid",
            }
        )
        invoice_address.with_company(self.company).property_account_receivable_id = receivable
        product = (
            self.env["product.template"]
            .create(
                {
                    "name": "Fictional EUR package",
                    "type": "service",
                    "invoice_policy": "order",
                    "taxes_id": [Command.clear()],
                    "company_id": self.company.id,
                    "property_account_income_id": income.id,
                    "training_course_id": self.course.id,
                    "training_price_basis": "package",
                }
            )
            .product_variant_id
        )
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Fictional EUR package list",
                "company_id": self.company.id,
                "currency_id": self.eur.id,
            }
        )
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "compute_price": "fixed",
                "fixed_price": 1600,
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "user_id": self.salesperson.id,
                "pricelist_id": pricelist.id,
                "training_request_kind": "group",
                "training_requested_program_id": self.program.id,
                "training_attendee_count": 12,
                "training_requested_currency_id": self.eur.id,
                "training_expected_payer_id": self.portal.partner_id.id,
            }
        )
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product.id,
                "product_uom_qty": 1,
                "training_program_id": self.program.id,
            }
        )
        order.action_confirm()
        self.assertEqual(order.amount_untaxed, 1600)
        self.assertEqual(order.partner_invoice_id, invoice_address)

        wizard_model = self.env["sale.advance.payment.inv"].with_context(
            active_model="sale.order",
            active_ids=order.ids,
        )
        advance_wizard = wizard_model.create(
            {
                "sale_order_ids": [Command.set(order.ids)],
                "advance_payment_method": "percentage",
                "amount": 25,
            }
        )
        advance_wizard.create_invoices()
        advance = order.invoice_ids
        self.assertEqual(len(advance), 1)
        self.assertEqual(advance.state, "draft")
        self.assertFalse(advance.training_portal_partner_ids)
        with self.assertRaises(UserError):
            advance.action_copy_training_portal_contacts()
        authorized = self.env["res.partner"].create(
            {
                "name": "Fictional Authorized Billing Contact",
                "parent_id": self.partner.id,
            }
        )
        order.training_portal_partner_ids = [Command.link(authorized.id)]
        with self.assertRaises(UserError):
            advance.with_user(self.portal).action_copy_training_portal_contacts()
        advance.action_copy_training_portal_contacts()
        self.assertEqual(advance.training_portal_partner_ids, authorized)
        order.training_portal_partner_ids = [Command.clear()]
        self.assertEqual(advance.training_portal_partner_ids, authorized)
        advance.training_portal_partner_ids = [Command.clear()]
        order.training_portal_partner_ids = [Command.link(authorized.id)]
        self.assertEqual(advance.currency_id, self.eur)
        self.assertEqual(advance.partner_id, invoice_address)
        self.assertEqual(advance.amount_untaxed, 400)
        self.assertTrue(advance.invoice_line_ids.filtered("is_downpayment"))
        self.assertEqual(advance.invoice_line_ids.filtered("is_downpayment").account_id, downpayment)
        self.assertEqual(advance.amount_residual, 400)
        advance.action_post()
        self.assertEqual(advance.state, "posted")
        with self.assertRaises(UserError):
            advance.action_copy_training_portal_contacts()
        self.assertEqual(advance.payment_state, "not_paid")
        self.assertEqual(advance.amount_residual, 400)

        final_wizard = wizard_model.create(
            {
                "sale_order_ids": [Command.set(order.ids)],
                "advance_payment_method": "delivered",
                "deduct_down_payments": True,
            }
        )
        final_wizard.create_invoices()
        final_invoice = order.invoice_ids - advance
        self.assertEqual(len(final_invoice), 1)
        self.assertEqual(final_invoice.state, "draft")
        self.assertFalse(final_invoice.training_portal_partner_ids)
        final_invoice.action_copy_training_portal_contacts()
        self.assertEqual(final_invoice.training_portal_partner_ids, authorized)
        final_invoice.training_portal_partner_ids = [Command.clear()]
        self.assertEqual(final_invoice.currency_id, self.eur)
        self.assertEqual(final_invoice.partner_id, invoice_address)
        self.assertEqual(final_invoice.amount_untaxed, 1200)
        final_invoice.action_post()
        self.assertEqual(final_invoice.state, "posted")
        self.assertEqual(final_invoice.payment_state, "not_paid")
        self.assertEqual(final_invoice.amount_residual, 1200)
        self.assertEqual(advance.amount_residual, 400)
        self.assertTrue(advance.training_is_sale_invoice)
        self.assertTrue(final_invoice.training_is_sale_invoice)
        downpayment_lines = final_invoice.invoice_line_ids.filtered("is_downpayment")
        self.assertTrue(downpayment_lines)
        self.assertEqual(downpayment_lines.account_id, downpayment)
        self.assertNotIn("Draft", downpayment_lines.name)
        self.assertTrue(
            all(line._get_aml_vals(hide_taxes=False)["label"] == "Down Payment" for line in downpayment_lines)
        )
        report_html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices",
            [final_invoice.id],
        )[0]
        self.assertNotIn(advance.name, report_html.decode() if isinstance(report_html, bytes) else report_html)
        colleague = self.env["res.partner"].create(
            {
                "name": "Fictional Billing Colleague",
                "parent_id": self.partner.id,
                "email": "billing-colleague@example.invalid",
            }
        )
        portal_colleague = new_test_user(
            self.env,
            login="training_sale_invoice_portal",
            groups="base.group_portal",
            partner_id=colleague.id,
        )
        with self.assertRaises(AccessError):
            final_invoice.with_user(portal_colleague).read(["name"])
        final_invoice._portal_ensure_token()
        self.assertFalse(
            final_invoice.with_user(portal_colleague)._get_thread_with_access(
                final_invoice.id,
                token=final_invoice.access_token,
            )
        )
        final_invoice.training_portal_partner_ids = [Command.link(colleague.id)]
        self.assertEqual(
            final_invoice.with_user(portal_colleague).read(["name"])[0]["name"],
            final_invoice.name,
        )
        self.assertTrue(
            final_invoice.with_user(portal_colleague)._get_thread_with_access(
                final_invoice.id,
                token=final_invoice.access_token,
            )
        )
        with self.assertRaises(AccessError):
            advance.with_user(portal_colleague).read(["name"])
        self.company.link_qr_code = True
        # Links are native; document grants still guard access to their targets.
        self.assertTrue(final_invoice._has_to_be_paid())
        link = self.env["payment.link.wizard"].create(
            {
                "res_model": "account.move",
                "res_id": final_invoice.id,
                "amount": 1200,
                "currency_id": self.eur.id,
                "partner_id": invoice_address.id,
            }
        )
        self.assertTrue(link.link)

        notice = (
            self.env["training.bank.transfer.notice"]
            .with_user(self.salesperson)
            .create(
                {
                    "order_id": order.id,
                    "amount": 300,
                    "claimed_date": "2026-10-20",
                    "reference": "FICTIONAL-TRANSFER-001",
                }
            )
        )
        self.assertEqual(notice.state, "reported")
        self.assertEqual(notice.currency_id, self.eur)
        self.assertEqual(notice.reported_by_id, self.salesperson)
        self.assertEqual(final_invoice.amount_residual, 1200)
        self.assertEqual(final_invoice.payment_state, "not_paid")
        linked_notice = self.env["training.bank.transfer.notice"].create(
            {
                "order_id": order.id,
                "invoice_id": final_invoice.id,
                "amount": 300,
                "claimed_date": "2026-10-20",
                "reference": "FICTIONAL-INVOICE-LINK-001",
            }
        )
        self.assertEqual(linked_notice.invoice_id, final_invoice)
        self.assertEqual(final_invoice.amount_residual, 1200)
        with self.assertRaises(AccessError):
            notice.with_user(self.portal).read(["reference"])
        other_salesperson = new_test_user(
            self.env,
            login="training_sale_other_company",
            groups="sales_team.group_sale_salesman",
            company_id=self.other_company.id,
            company_ids=[Command.set([self.other_company.id])],
        )
        with self.assertRaises(AccessError):
            notice.with_user(other_salesperson).read(["reference"])
        with self.assertRaises(AccessError):
            notice.with_user(self.salesperson).action_void()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["training.bank.transfer.notice"].create(
                {
                    "order_id": order.id,
                    "amount": 0,
                    "claimed_date": "2026-10-20",
                    "reference": "INVALID",
                }
            )

        bank_account = self.env["account.account"].create(
            {
                "name": "Fictional EUR Bank",
                "code": "519901",
                "account_type": "asset_cash",
                "company_ids": [Command.set([self.company.id])],
            }
        )
        outstanding_account = self.env["account.account"].create(
            {
                "name": "Fictional Outstanding Receipts",
                "code": "349902",
                "account_type": "asset_current",
                "reconcile": True,
                "company_ids": [Command.set([self.company.id])],
            }
        )
        bank_journal = self.env["account.journal"].create(
            {
                "name": "Fictional EUR Bank",
                "code": "FEB",
                "type": "bank",
                "company_id": self.company.id,
                "currency_id": self.eur.id,
                "default_account_id": bank_account.id,
            }
        )
        manual_method = bank_journal.inbound_payment_method_line_ids.filtered(lambda line: line.code == "manual")
        self.assertEqual(len(manual_method), 1)
        manual_method.payment_account_id = outstanding_account
        cash_account = self.env["account.account"].create(
            {
                "name": "Fictional EUR Cash",
                "code": "519903",
                "account_type": "asset_cash",
                "company_ids": [Command.set([self.company.id])],
            }
        )
        cash_journal = self.env["account.journal"].create(
            {
                "name": "Fictional EUR Cash",
                "code": "FEC",
                "type": "cash",
                "company_id": self.company.id,
                "currency_id": self.eur.id,
                "default_account_id": cash_account.id,
            }
        )
        cash_method = cash_journal.inbound_payment_method_line_ids.filtered(lambda line: line.code == "manual")
        self.assertEqual(len(cash_method), 1)
        payment_wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move",
                active_ids=final_invoice.ids,
            )
            .create(
                {
                    "journal_id": bank_journal.id,
                    "payment_method_line_id": manual_method.id,
                    "currency_id": self.eur.id,
                    "amount": 300,
                    "payment_difference_handling": "open",
                }
            )
        )
        first_payment = payment_wizard._create_payments()
        self.assertEqual(len(first_payment), 1)
        self.assertEqual(first_payment.memo, final_invoice.name)
        self.assertFalse(first_payment.training_bank_reference)
        self.assertFalse(first_payment.training_bank_verified_at)
        self.assertTrue(first_payment.training_receipt_restricted)
        self.assertEqual(first_payment.reconciled_invoice_ids, final_invoice)
        receipt_defaults = first_payment._message_get_default_recipients()[first_payment.id]
        self.assertEqual(receipt_defaults["partner_ids"], colleague.ids)
        self.assertFalse(receipt_defaults["email_to"])
        receipt_template = self.env.ref("account.mail_template_data_payment_receipt")
        receipt_recipients = receipt_template._generate_template(
            [first_payment.id],
            ["email_to", "email_cc", "partner_to", "partner_cc"],
        )[first_payment.id]
        self.assertEqual(receipt_recipients["partner_ids"], colleague.ids)
        receipt_composer = (
            self.env["mail.compose.message"]
            .with_context(
                default_model="account.payment",
                default_res_ids=first_payment.ids,
                default_template_id=receipt_template.id,
                default_composition_mode="comment",
            )
            .create({})
        )
        self.assertEqual(receipt_composer.partner_ids, colleague)
        self.assertTrue(receipt_composer.attachment_ids)
        prepared_receipt = receipt_composer._prepare_mail_values(first_payment.ids)[first_payment.id]
        self.assertEqual(prepared_receipt["partner_ids"], colleague.ids)
        self.assertTrue(prepared_receipt["notify_skip_followers"])
        with self.assertRaises(ValidationError):
            receipt_template.send_mail(
                first_payment.id,
                force_send=False,
                email_values={"email_to": "unlinked@example.invalid"},
            )
        receipt_mail = self.env["mail.mail"].browse(receipt_template.send_mail(first_payment.id, force_send=False))
        self.assertEqual(receipt_mail.recipient_ids, colleague)
        self.assertFalse(receipt_mail.email_to)
        receipt_message = self.env["mail.message"].create(
            {
                "model": "account.payment",
                "res_id": first_payment.id,
                "message_type": "comment",
                "body": "Fictional receipt note",
                "subtype_id": self.env.ref("mail.mt_comment").id,
                "partner_ids": [Command.set((colleague + invoice_address).ids)],
            }
        )
        notified = first_payment._notify_get_recipients(receipt_message)
        self.assertIn(colleague.id, [recipient["id"] for recipient in notified])
        self.assertNotIn(invoice_address.id, [recipient["id"] for recipient in notified])
        receipt_attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-payment-receipt.txt",
                "raw": b"Fictional payment receipt",
                "mimetype": "text/plain",
                "res_model": "account.payment",
                "res_id": first_payment.id,
            }
        )
        message_attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-payment-message.txt",
                "raw": b"Fictional receipt message",
                "mimetype": "text/plain",
                "res_model": "mail.message",
                "res_id": receipt_message.id,
            }
        )
        self.env["ir.binary"].with_user(portal_colleague)._check_training_binary_access(
            receipt_attachment,
        )
        self.env["ir.binary"].with_user(portal_colleague)._check_training_binary_access(
            message_attachment,
        )
        for attachment in (receipt_attachment, message_attachment):
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(self.portal)._check_training_binary_access(
                    attachment,
                )
        receipt_composer.partner_ids = [Command.set(invoice_address.ids)]
        with self.assertRaises(ValidationError):
            receipt_composer._prepare_mail_values(first_payment.ids)
        receipt_composer.partner_ids = [Command.set(colleague.ids)]
        receipt_composer.partner_cc_ids = [Command.set(invoice_address.ids)]
        with self.assertRaises(ValidationError):
            receipt_composer._prepare_mail_values(first_payment.ids)
        receipt_composer.partner_cc_ids = [Command.clear()]
        invoice_message = self.env["mail.message"].create(
            {
                "model": "account.move",
                "res_id": final_invoice.id,
                "message_type": "comment",
                "subtype_id": self.env.ref("mail.mt_comment").id,
                "body": "Fictional invoice note",
                "partner_ids": [Command.set(colleague.ids)],
            }
        )
        invoice_mail = self.env["mail.mail"].create(
            {
                "model": "account.move",
                "res_id": final_invoice.id,
                "subject": "Fictional queued invoice",
                "body_html": "Fictional invoice",
                "email_from": "sender@example.invalid",
                "recipient_ids": [Command.set(colleague.ids)],
                "auto_delete": False,
            }
        )
        for message in (receipt_message, invoice_message):
            self.assertTrue(message.with_user(portal_colleague).read(["body"]))
        final_invoice.training_portal_partner_ids = [Command.clear()]
        for message in (receipt_message, invoice_message):
            message.body = "Fictional confidential update after revocation"
            with self.assertRaises(AccessError):
                message.with_user(portal_colleague).read(["body"])
            self.assertFalse(message.with_user(portal_colleague).sudo()._get_with_access())
            self.assertFalse(
                self.env["mail.message"]
                .with_user(portal_colleague)
                .search(
                    [
                        ("id", "=", message.id),
                    ]
                )
            )
        server = type(self.env["ir.mail_server"])
        with (
            patch.object(server, "_disable_send", return_value=False),
            patch.object(server, "_connect__", return_value=None),
            patch.object(server, "send_email") as transport,
        ):
            for queued in (receipt_mail, invoice_mail):
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    queued.send(raise_exception=True)
            transport.assert_not_called()
        with self.assertRaises(ValidationError):
            receipt_composer._prepare_mail_values(first_payment.ids)
        with self.assertRaises(ValidationError):
            receipt_template.send_mail(first_payment.id, force_send=False)
        self.assertFalse(
            [recipient for recipient in first_payment._notify_get_recipients(receipt_message) if recipient["share"]]
        )
        for attachment in (receipt_attachment, message_attachment):
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(portal_colleague)._check_training_binary_access(
                    attachment,
                )
        final_invoice.training_portal_partner_ids = [Command.link(colleague.id)]
        with self.assertRaises(ValidationError):
            first_payment.training_bank_reference = "ALTERED"
        with self.assertRaises(ValidationError):
            first_payment.training_bank_verified = False
        with self.assertRaises(ValidationError):
            first_payment.training_bank_verified_by_id = self.portal
        self.assertEqual(final_invoice.amount_residual, 900)
        self.assertEqual(final_invoice.payment_state, "partial")
        self.assertEqual(advance.amount_residual, 400)
        self.assertEqual(notice.state, "reported")

        split_wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move",
                active_ids=advance.ids,
            )
            .create({"journal_id": bank_journal.id, "amount": 100, "payment_difference_handling": "open"})
        )
        split_wizard.action_create_payments()
        self.assertEqual(advance.amount_residual, 300)
        invoice_receivable = final_invoice.line_ids.filtered(lambda line: line.account_id == receivable)
        native_payment = self.env["account.payment"].create(
            {
                "date": "2026-10-20",
                "amount": 50,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoice_address.id,
                "journal_id": bank_journal.id,
                "currency_id": self.eur.id,
                "payment_method_line_id": manual_method.id,
                "destination_account_id": receivable.id,
            }
        )
        native_payment.action_post()
        payment_receivable = native_payment.move_id.line_ids.filtered(lambda line: line.account_id == receivable)
        (invoice_receivable + payment_receivable).reconcile()
        self.assertEqual(final_invoice.amount_residual, 850)
        self.assertTrue(native_payment.training_receipt_restricted)
        for journal in (bank_journal, cash_journal):
            statement = self.env["account.bank.statement.line"].create(
                {
                    "journal_id": journal.id,
                    "date": "2026-10-20",
                    "payment_ref": "Fictional native statement",
                    "partner_id": invoice_address.id,
                    "amount": 50,
                    "counterpart_account_id": receivable.id,
                }
            )
            counterpart = statement.move_id.line_ids.filtered(lambda line: line.account_id == receivable)
            (invoice_receivable + counterpart).reconcile()
        self.assertEqual(final_invoice.amount_residual, 750)
        accountant = new_test_user(self.env, login="training_sale_accountant", groups="account.group_account_invoice")
        notice.with_user(accountant).action_void()
        self.assertEqual(notice.state, "void")

        # S10 reuses these real native down-payment/final-invoice fixtures;
        # an advance is not omitted or counted twice in the invoice cohort.
        delivery = self.env["training.delivery"].create(
            {
                "name": "Fictional S10 financial scope",
                "program_id": self.program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 10,
            }
        )
        self.env["training.seat.allocation"].create(
            {
                "delivery_id": delivery.id,
                "customer_id": self.partner.id,
                "quantity": 1,
                "source_reference": "S10 financial scope",
                "expires_at": fields.Datetime.now() + timedelta(days=1),
                "sale_line_id": order.order_line.filtered(lambda line: line.training_program_id)[:1].id,
            }
        )
        financial_reader = new_test_user(
            self.env,
            login="s10_financial_reader",
            groups="training_management.group_training_coordinator,sales_team.group_sale_manager,account.group_account_manager",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        figures = self.env["training.dashboard.service"].with_user(financial_reader)._commercial(delivery, None, None)
        invoiced = [row for row in figures if row["kind"] == "invoices"]
        self.assertEqual(len(invoiced), 1)
        self.assertEqual(invoiced[0]["currency"], "EUR")
        self.assertEqual(invoiced[0]["amount"], 1600)
        self.assertEqual(set(invoiced[0]["ids"]), {advance.id, final_invoice.id})

    def _server_guard_order(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Fictional server guard EUR",
                "currency_id": self.eur.id,
            }
        )
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "compute_price": "fixed",
                "fixed_price": 100,
            }
        )
        return (
            self.env["sale.order"]
            .with_user(self.salesperson)
            .create(
                {
                    "partner_id": self.partner.id,
                    "pricelist_id": pricelist.id,
                    "training_request_kind": "group",
                    "training_attendee_count": 1,
                    "training_requested_program_id": self.program.id,
                    "training_requested_currency_id": self.eur.id,
                    "order_line": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1,
                                "training_program_id": self.program.id,
                            }
                        )
                    ],
                }
            )
        )

    def test_direct_sale_state_and_currency_are_guarded(self):
        order = self._server_guard_order()
        order.order_line.price_unit = 1
        order.order_line.product_uom_qty = 2
        for state in ("sent", "sale"):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                order.write({"state": state})
            self.assertEqual(order.state, "draft")
        vals = order.copy_data()[0]
        vals["state"] = "sale"
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["sale.order"].with_user(self.salesperson).create(vals)
        order.order_line.product_uom_qty = order.training_attendee_count
        order.action_confirm()
        order.write({"currency_id": self.env.ref("base.MAD").id})
        self.assertEqual(order.currency_id, self.env.ref("base.MAD"))
        self.assertEqual(order.amount_untaxed, 1)
        # A native non-training order keeps its ordinary state writes.
        native = (
            self.env["sale.order"]
            .with_user(self.salesperson)
            .create(
                {
                    "partner_id": self.partner.id,
                }
            )
        )
        native.write({"state": "sale"})
        self.assertEqual(native.state, "sale")

    def test_notice_follows_native_order_portfolio(self):
        order = self._server_guard_order()
        order.action_confirm()
        notice = (
            self.env["training.bank.transfer.notice"]
            .with_user(self.salesperson)
            .create(
                {
                    "order_id": order.id,
                    "amount": 10,
                    "claimed_date": "2026-10-22",
                    "reference": "FICTIONAL-PRIVATE-NOTICE",
                }
            )
        )
        other = new_test_user(self.env, login="fictional_other_sales", groups="sales_team.group_sale_salesman")
        finance = new_test_user(self.env, login="fictional_notice_finance", groups="account.group_account_invoice")
        manager = new_test_user(
            self.env, login="fictional_all_sales", groups="sales_team.group_sale_salesman_all_leads"
        )
        with self.assertRaises(AccessError):
            order.with_user(other).read(["name"])
        for operation in (
            lambda: notice.with_user(other).read(["reference", "amount", "claimed_date"]),
            lambda: notice.with_user(other).export_data(["reference", "amount"]),
        ):
            with self.assertRaises(AccessError):
                operation()
        self.assertFalse(self.env[notice._name].with_user(other).search([("id", "=", notice.id)]))
        for user in (self.salesperson, manager, finance):
            self.assertEqual(notice.with_user(user).read(["reference"])[0]["reference"], "FICTIONAL-PRIVATE-NOTICE")

    def test_third_currency_native_pricelist_formula_and_manual_discount(self):
        gbp = self.env.ref("base.GBP")
        gbp.active = True
        order = self._server_guard_order().with_user(self.env.user)
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Fictional Native GBP",
                "currency_id": gbp.id,
                "item_ids": [
                    Command.create(
                        {
                            "product_tmpl_id": self.product.product_tmpl_id.id,
                            "compute_price": "discount",
                            "price_discount": 10,
                        }
                    )
                ],
            }
        )
        order.pricelist_id = pricelist
        # Requested currency is advisory; the negotiated offer follows its pricelist.
        self.assertEqual(order.training_requested_currency_id, self.eur)
        self.assertNotEqual(self.company.currency_id, gbp)
        rule = order.pricelist_id.item_ids
        rule.write({"compute_price": "discount", "price_discount": 10})
        self.product.list_price = 200
        line = order.order_line
        line._compute_price_unit()
        self.assertEqual(order.currency_id, gbp)
        line._compute_discount()
        self.assertEqual(line.price_subtotal, 180)
        line.write({"price_unit": 175, "discount": 12})
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(line.price_subtotal, 154)
        self.assertEqual(order.state, "sale")
        self.assertFalse(self.env["training.enrollment"].search([]))

    def test_native_pricelist_currency_does_not_rewrite_stored_order_currency(self):
        gbp = self.env.ref("base.GBP")
        gbp.active = True
        order = self._server_guard_order().with_user(self.env.user)
        order.action_confirm()
        original_currency = order.currency_id
        original_amount = order.amount_untaxed
        order.pricelist_id.currency_id = gbp
        order.invalidate_recordset(["currency_id", "amount_untaxed"])
        self.assertEqual(order.currency_id, original_currency)
        self.assertEqual(order.amount_untaxed, original_amount)

    def test_transfer_notice_keeps_declared_currency_when_order_changes(self):
        gbp = self.env.ref("base.GBP")
        gbp.active = True
        order = self._server_guard_order()
        order.action_confirm()
        notices = self.env["training.bank.transfer.notice"].with_user(self.salesperson)
        values = {
            "order_id": order.id,
            "amount": 30,
            "claimed_date": "2026-10-20",
            "reference": "Fictional declaration only",
        }
        original = notices.create(values)
        foreign = notices.create({**values, "currency_id": gbp.id})
        self.assertEqual(original.currency_id, self.eur)
        self.assertEqual(foreign.currency_id, gbp)
        order.currency_id = self.env.ref("base.MAD")
        self.assertEqual(original.currency_id, self.eur)
        self.assertEqual(foreign.currency_id, gbp)
        self.assertFalse(order.invoice_ids)
        self.assertFalse(self.env["account.payment"].search([]))
