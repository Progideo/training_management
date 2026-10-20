from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestTrainingSale(TransactionCase):
    """COM01 and CAT02: a qualified request keeps a safe programme link."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Fictional Sales Company B"})
        cls.salesperson = new_test_user(
            cls.env, login="training_sale_person",
            groups="sales_team.group_sale_salesman",
            company_id=cls.company.id, company_ids=[Command.set([cls.company.id])],
        )
        cls.portal = new_test_user(
            cls.env, login="training_sale_portal", groups="base.group_portal",
        )
        cls.contact = cls.env["res.partner"].create({"name": "Fictional Training Contact"})
        cls.course = cls.env["training.course"].create({
            "name": "Standard Course", "company_id": cls.company.id,
        })
        cls.program = cls.env["training.program.version"].create({
            "course_id": cls.course.id, "version": "V1", "title": "Programme V1",
            "objectives": "Learn the method", "target_audience": "Managers",
            "prerequisites": "None", "content": "Guided workshop", "duration_hours": 7,
            "delivery_mode": "onsite", "language_id": cls.env.ref("base.lang_en").id,
            "teaching_methods": "Exercises", "evaluation_criteria": "Review",
            "access_conditions": "Manual approval", "accessibility_contact_id": cls.contact.id,
            "accessibility_information": "Contact us",
        })
        cls.program.action_validate()
        cls.product = cls.env["product.template"].create({
            "name": "Training service per person", "type": "service",
            "company_id": cls.company.id,
            "training_course_id": cls.course.id, "training_price_basis": "person",
        }).product_variant_id
        cls.eur = cls.env.ref("base.EUR")
        cls.partner = cls.env["res.partner"].create({"name": "Fictional Buyer"})

    def test_crm_qualification_opens_native_quotation_with_version(self):
        lead = self.env["crm.lead"].with_user(self.salesperson).create({
            "name": "Group request", "type": "opportunity", "partner_id": self.partner.id,
            "training_request_kind": "group", "training_program_id": self.program.id,
            "training_attendee_count": 12, "training_requested_currency_id": self.eur.id,
        })
        context = lead.action_new_quotation()["context"]
        self.assertEqual(context["default_opportunity_id"], lead.id)
        self.assertEqual(context["default_training_requested_program_id"], self.program.id)
        self.assertEqual(context["default_training_attendee_count"], 12)
        self.assertEqual(context["default_training_requested_currency_id"], self.eur.id)
        order = self.env["sale.order"].with_user(self.salesperson).with_context(context).create({
            "partner_id": self.partner.id,
        })
        self.assertEqual(order.training_requested_program_id, self.program)
        self.assertEqual(order.opportunity_id, lead)
        self.env["sale.order.line"].with_user(self.salesperson).create({
            "order_id": order.id, "product_id": self.product.id,
            "product_uom_qty": 12, "training_program_id": self.program.id,
        })
        self.assertEqual(order.order_line.training_program_id, self.program)
        self.assertEqual(order.order_line.product_uom_qty, 12)
        quoted_label = order.order_line.training_program_label
        self.assertIn("V1", quoted_label)
        self.course.name = "Renamed course"
        self.assertEqual(order.order_line.training_program_label, quoted_label)
        html = self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder", [order.id],
        )[0]
        self.assertIn(quoted_label, html.decode() if isinstance(html, bytes) else html)
        self.assertFalse(self.env["sale.order.line"].search([
            ("order_id", "=", order.id), ("product_id", "=", self.product.id),
            ("training_program_id", "=", False),
        ]))

    def test_invalid_program_and_company_are_refused(self):
        draft = self.program.copy({"version": "V2"})
        visible = self.env["training.program.version"].with_user(self.salesperson).search([
            ("id", "in", [self.program.id, draft.id]),
        ])
        self.assertEqual(visible, self.program)
        with self.assertRaises(AccessError):
            draft.with_user(self.salesperson).read(["title"])
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        for vals in (
            {"order_id": order.id, "product_id": self.product.id},
            {"order_id": order.id, "product_id": self.product.id,
             "training_program_id": draft.id},
        ):
            with self.assertRaises((ValidationError, AccessError)), self.cr.savepoint():
                self.env["sale.order.line"].with_user(self.salesperson).create(vals)
        with self.assertRaises(AccessError):
            self.program.with_user(self.portal).read(["title"])
        other_course = self.env["training.course"].create({
            "name": "Other Company Course", "company_id": self.other_company.id,
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["sale.order.line"].create({
                "order_id": order.id, "product_id": self.product.id,
                "training_program_id": self.env["training.program.version"].create({
                    "course_id": other_course.id, "version": "V1", "title": "Other",
                }).id,
            })

    def test_incomplete_request_cannot_create_training_quote(self):
        field = self.env["ir.model.fields"].search([
            ("model", "=", "crm.lead"), ("name", "=", "training_request_kind"),
        ], limit=1)
        self.assertEqual(
            field.with_context(lang="fr_FR").field_description,
            "Demande de formation",
        )
        lead = self.env["crm.lead"].create({
            "name": "Unqualified", "type": "opportunity", "partner_id": self.partner.id,
            "training_request_kind": "individual", "training_program_id": self.program.id,
        })
        with self.assertRaises(ValidationError):
            lead.action_new_quotation()

    def test_commercial_roles_do_not_replace_invoice_debtor_or_grant_access(self):
        sponsor = self.env["res.partner"].create({"name": "Fictional Ordering Organisation"})
        admin_contact = self.env["res.partner"].create({
            "name": "Fictional Administrative Contact", "type": "contact",
        })
        invoice_address = self.env["res.partner"].create({
            "name": "Fictional Invoice Address", "parent_id": self.partner.id,
            "type": "invoice",
        })
        payer = self.portal.partner_id
        lead = self.env["crm.lead"].with_user(self.salesperson).create({
            "name": "Group roles", "type": "opportunity", "partner_id": self.partner.id,
            "training_request_kind": "group", "training_program_id": self.program.id,
            "training_attendee_count": 12, "training_requested_currency_id": self.eur.id,
            "training_sponsor_id": sponsor.id,
            "training_expected_payer_id": payer.id,
            "training_admin_contact_id": admin_contact.id,
        })
        context = lead.action_new_quotation()["context"]
        self.assertEqual(context["default_training_sponsor_id"], sponsor.id)
        self.assertEqual(context["default_training_expected_payer_id"], payer.id)
        self.assertEqual(context["default_training_admin_contact_id"], admin_contact.id)
        order = self.env["sale.order"].with_user(self.salesperson).with_context(context).create({
            "partner_id": self.partner.id,
        })
        self.assertEqual(order.training_sponsor_id, sponsor)
        self.assertEqual(order.training_expected_payer_id, payer)
        self.assertEqual(order.training_admin_contact_id, admin_contact)
        self.assertEqual(order.partner_invoice_id, invoice_address)
        self.assertEqual(order._prepare_invoice()["partner_id"], invoice_address.id)
        with self.assertRaises(AccessError):
            order.with_user(self.portal).read(["name"])

    def test_commercial_roles_respect_operating_company(self):
        foreign_contact = self.env["res.partner"].create({
            "name": "Fictional Restricted Contact", "company_id": self.other_company.id,
        })
        for model, values in (
            ("crm.lead", {"name": "Foreign sponsor", "training_request_kind": "group"}),
            ("sale.order", {"partner_id": self.partner.id, "training_request_kind": "group"}),
        ):
            with self.assertRaises(UserError), self.cr.savepoint():
                self.env[model].create({
                    **values, "company_id": self.company.id,
                    "training_sponsor_id": foreign_contact.id,
                })

    def test_independent_fixed_prices_and_price_basis(self):
        mad = self.env.ref("base.MAD")
        package_product = self.env["product.template"].create({
            "name": "Training service package", "type": "service",
            "company_id": self.company.id,
            "training_course_id": self.course.id, "training_price_basis": "package",
        }).product_variant_id
        pricelists = {}
        for currency, person_price, package_price in (
            (mad, 900, 12000), (self.eur, 125, 1600),
        ):
            pricelist = self.env["product.pricelist"].create({
                "name": "Fictional training %s" % currency.name,
                "company_id": self.company.id, "currency_id": currency.id,
            })
            pricelists[currency.name] = pricelist
            for product, amount in ((self.product, person_price), (package_product, package_price)):
                self.env["product.pricelist.item"].create({
                    "pricelist_id": pricelist.id,
                    "product_tmpl_id": product.product_tmpl_id.id,
                    "compute_price": "fixed", "fixed_price": amount,
                })

        for currency, person_price, package_price in (
            (mad, 900, 12000), (self.eur, 125, 1600),
        ):
            for product, quantity, amount in (
                (self.product, 12, person_price), (package_product, 1, package_price),
            ):
                order = self.env["sale.order"].create({
                    "partner_id": self.partner.id, "company_id": self.company.id,
                    "pricelist_id": pricelists[currency.name].id,
                    "training_request_kind": "group",
                    "training_requested_program_id": self.program.id,
                    "training_attendee_count": 12,
                    "training_requested_currency_id": currency.id,
                })
                line = self.env["sale.order.line"].create({
                    "order_id": order.id, "product_id": product.id,
                    "product_uom_qty": quantity,
                    "training_program_id": self.program.id,
                })
                self.assertEqual(order.currency_id, currency)
                self.assertEqual(line.price_unit, amount)
                order._check_training_offer()
                order.action_confirm()
                self.assertEqual(order.state, "sale")
                self.assertEqual(line.price_unit, amount)
                if currency == mad and product == self.product:
                    for field_name in (
                        "training_sponsor_id", "training_expected_payer_id",
                        "training_admin_contact_id",
                    ):
                        with self.assertRaises(ValidationError):
                            order.write({field_name: self.partner.id})
                with self.assertRaises(ValidationError):
                    pricelists[currency.name].write({
                        "currency_id": (self.eur if currency == mad else mad).id,
                    })

    def test_missing_or_changed_tariff_cannot_be_sent_or_confirmed(self):
        pricelist = self.env["product.pricelist"].create({
            "name": "Fictional EUR", "company_id": self.company.id,
            "currency_id": self.eur.id,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "company_id": self.company.id,
            "pricelist_id": pricelist.id,
            "training_request_kind": "group",
            "training_requested_program_id": self.program.id,
            "training_attendee_count": 12,
            "training_requested_currency_id": self.eur.id,
        })
        line = self.env["sale.order.line"].create({
            "order_id": order.id, "product_id": self.product.id,
            "product_uom_qty": 12, "training_program_id": self.program.id,
        })
        with self.assertRaises(ValidationError):
            order.action_quotation_send()
        with self.assertRaises(ValidationError):
            order.action_confirm()
        rule = self.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id,
            "product_tmpl_id": self.product.product_tmpl_id.id,
            "compute_price": "fixed", "fixed_price": 125,
        })
        line.price_unit = 125
        order._check_training_offer()
        line.product_uom_qty = 1
        with self.assertRaises(ValidationError):
            order.action_confirm()
        line.product_uom_qty = 12
        line.price_unit = 126
        with self.assertRaises(ValidationError):
            order.action_confirm()
        line.price_unit = 125
        line.discount = 5
        with self.assertRaises(ValidationError):
            order.action_confirm()
        line.discount = 0
        rule.compute_price = "discount"
        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_native_eur_down_payment_and_final_invoice(self):
        self.eur.active = True
        income = self.env["account.account"].create({
            "name": "Fictional Training Income", "code": "709901",
            "account_type": "income", "company_ids": [Command.set([self.company.id])],
        })
        receivable = self.env["account.account"].create({
            "name": "Fictional Training Receivable", "code": "349901",
            "account_type": "asset_receivable", "reconcile": True,
            "company_ids": [Command.set([self.company.id])],
        })
        self.env["account.journal"].create({
            "name": "Fictional Training Sales", "code": "FTS", "type": "sale",
            "company_id": self.company.id, "default_account_id": income.id,
        })
        self.partner.with_company(self.company).property_account_receivable_id = receivable
        invoice_address = self.env["res.partner"].create({
            "name": "Fictional Training Billing", "parent_id": self.partner.id,
            "type": "invoice",
        })
        invoice_address.with_company(self.company).property_account_receivable_id = receivable
        product = self.env["product.template"].create({
            "name": "Fictional EUR package", "type": "service",
            "invoice_policy": "order", "taxes_id": [Command.clear()],
            "company_id": self.company.id,
            "property_account_income_id": income.id,
            "training_course_id": self.course.id, "training_price_basis": "package",
        }).product_variant_id
        pricelist = self.env["product.pricelist"].create({
            "name": "Fictional EUR package list", "company_id": self.company.id,
            "currency_id": self.eur.id,
        })
        self.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id, "product_tmpl_id": product.product_tmpl_id.id,
            "compute_price": "fixed", "fixed_price": 1600,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "company_id": self.company.id,
            "pricelist_id": pricelist.id, "training_request_kind": "group",
            "training_requested_program_id": self.program.id,
            "training_attendee_count": 12,
            "training_requested_currency_id": self.eur.id,
            "training_expected_payer_id": self.portal.partner_id.id,
        })
        self.env["sale.order.line"].create({
            "order_id": order.id, "product_id": product.id,
            "product_uom_qty": 1, "training_program_id": self.program.id,
        })
        order.action_confirm()
        self.assertEqual(order.amount_untaxed, 1600)
        self.assertEqual(order.partner_invoice_id, invoice_address)

        wizard_model = self.env["sale.advance.payment.inv"].with_context(
            active_model="sale.order", active_ids=order.ids,
        )
        advance_wizard = wizard_model.create({
            "sale_order_ids": [Command.set(order.ids)],
            "advance_payment_method": "percentage", "amount": 25,
        })
        advance_wizard.create_invoices()
        advance = order.invoice_ids
        self.assertEqual(len(advance), 1)
        self.assertEqual(advance.state, "draft")
        self.assertEqual(advance.currency_id, self.eur)
        self.assertEqual(advance.partner_id, invoice_address)
        self.assertEqual(advance.amount_untaxed, 400)
        self.assertTrue(advance.invoice_line_ids.filtered("is_downpayment"))
        self.assertEqual(advance.amount_residual, 400)
        advance.action_post()
        self.assertEqual(advance.state, "posted")
        self.assertEqual(advance.payment_state, "not_paid")
        self.assertEqual(advance.amount_residual, 400)

        final_wizard = wizard_model.create({
            "sale_order_ids": [Command.set(order.ids)],
            "advance_payment_method": "delivered", "deduct_down_payments": True,
        })
        final_wizard.create_invoices()
        final_invoice = order.invoice_ids - advance
        self.assertEqual(len(final_invoice), 1)
        self.assertEqual(final_invoice.state, "draft")
        self.assertEqual(final_invoice.currency_id, self.eur)
        self.assertEqual(final_invoice.partner_id, invoice_address)
        self.assertEqual(final_invoice.amount_untaxed, 1200)
        final_invoice.action_post()
        self.assertEqual(final_invoice.state, "posted")
        self.assertEqual(final_invoice.payment_state, "not_paid")
        self.assertEqual(final_invoice.amount_residual, 1200)
        self.assertEqual(advance.amount_residual, 400)

        notice = self.env["training.bank.transfer.notice"].with_user(
            self.salesperson
        ).create({
            "order_id": order.id,
            "amount": 300, "claimed_date": "2026-10-20",
            "reference": "FICTIONAL-TRANSFER-001",
        })
        self.assertEqual(notice.state, "reported")
        self.assertEqual(notice.currency_id, self.eur)
        self.assertEqual(notice.reported_by_id, self.salesperson)
        self.assertEqual(final_invoice.amount_residual, 1200)
        self.assertEqual(final_invoice.payment_state, "not_paid")
        linked_notice = self.env["training.bank.transfer.notice"].create({
            "order_id": order.id, "invoice_id": final_invoice.id,
            "amount": 300, "claimed_date": "2026-10-20",
            "reference": "FICTIONAL-INVOICE-LINK-001",
        })
        self.assertEqual(linked_notice.invoice_id, final_invoice)
        self.assertEqual(final_invoice.amount_residual, 1200)
        with self.assertRaises(AccessError):
            notice.with_user(self.portal).read(["reference"])
        other_salesperson = new_test_user(
            self.env, login="training_sale_other_company",
            groups="sales_team.group_sale_salesman",
            company_id=self.other_company.id,
            company_ids=[Command.set([self.other_company.id])],
        )
        with self.assertRaises(AccessError):
            notice.with_user(other_salesperson).read(["reference"])
        with self.assertRaises(AccessError):
            notice.with_user(self.salesperson).action_void()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["training.bank.transfer.notice"].create({
                "order_id": order.id, "amount": 0,
                "claimed_date": "2026-10-20", "reference": "INVALID",
            })

        bank_account = self.env["account.account"].create({
            "name": "Fictional EUR Bank", "code": "519901",
            "account_type": "asset_cash",
            "company_ids": [Command.set([self.company.id])],
        })
        outstanding_account = self.env["account.account"].create({
            "name": "Fictional Outstanding Receipts", "code": "349902",
            "account_type": "asset_current", "reconcile": True,
            "company_ids": [Command.set([self.company.id])],
        })
        bank_journal = self.env["account.journal"].create({
            "name": "Fictional EUR Bank", "code": "FEB", "type": "bank",
            "company_id": self.company.id, "currency_id": self.eur.id,
            "default_account_id": bank_account.id,
        })
        manual_method = bank_journal.inbound_payment_method_line_ids.filtered(
            lambda line: line.code == "manual"
        )
        self.assertEqual(len(manual_method), 1)
        manual_method.payment_account_id = outstanding_account
        payment_wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=final_invoice.ids,
        ).create({
            "journal_id": bank_journal.id,
            "payment_method_line_id": manual_method.id,
            "currency_id": self.eur.id,
            "amount": 300,
            "payment_difference_handling": "open",
            "communication": "FICTIONAL-TRANSFER-001",
        })
        payment_wizard.action_create_payments()
        self.assertEqual(final_invoice.amount_residual, 900)
        self.assertEqual(final_invoice.payment_state, "partial")
        self.assertEqual(advance.amount_residual, 400)
        self.assertEqual(notice.state, "reported")
        accountant = new_test_user(
            self.env, login="training_sale_accountant",
            groups="account.group_account_invoice,sales_team.group_sale_salesman",
            company_id=self.company.id, company_ids=[Command.set([self.company.id])],
        )
        notice.with_user(accountant).action_void()
        self.assertEqual(notice.state, "void")
        self.assertEqual(final_invoice.amount_residual, 900)
