from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.translate import load_language
from odoo.addons.training_management_sale.controllers.portal import TrainingCustomerPortal


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
        load_language(self.cr, "fr_FR")
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
        self.env["sale.order.line"].create({
            "order_id": order.id, "product_id": self.product.id,
            "product_uom_qty": 1, "price_unit": 100,
            "training_program_id": self.program.id,
        })
        order.prepayment_percent = 0.25
        self.assertGreater(order.amount_total, 0)
        self.assertFalse(order._has_to_be_paid())
        self.assertIsNone(TrainingCustomerPortal()._get_payment_values(
            order, payment_amount=100,
        )["payment_amount"])
        with self.assertRaises(ValidationError):
            self.env["payment.transaction"].create({
                "sale_order_ids": [Command.set(order.ids)],
            })
        with self.assertRaises(ValidationError):
            self.env["payment.link.wizard"].with_context(
                active_model="sale.order", active_id=order.id,
            ).default_get(["res_model", "res_id", "amount"])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["payment.link.wizard"].create({
                "res_model": "sale.order", "res_id": order.id,
                "amount": 25, "currency_id": self.eur.id,
                "partner_id": self.partner.id,
            })
        with self.assertRaises(AccessError):
            order.with_user(self.portal).read(["name"])
        company_contact = self.env["res.partner"].create({
            "name": "Fictional Buyer Colleague", "parent_id": self.partner.id,
        })
        company_portal = new_test_user(
            self.env, login="training_sale_company_portal",
            groups="base.group_portal", partner_id=company_contact.id,
        )
        with self.assertRaises(AccessError):
            order.with_user(company_portal).read(["name"])
        order._portal_ensure_token()
        self.assertFalse(order.with_user(company_portal)._get_thread_with_access(
            order.id, token=order.access_token,
        ))
        order.training_portal_partner_ids = [Command.link(company_contact.id)]
        self.assertEqual(order.with_user(company_portal).read(["name"])[0]["name"], order.name)
        self.assertTrue(order.with_user(company_portal)._get_thread_with_access(
            order.id, token=order.access_token,
        ))
        self.assertFalse(order.copy().training_portal_partner_ids)
        private_fields = (
            "training_sponsor_id", "training_expected_payer_id",
            "training_admin_contact_id", "training_transfer_notice_ids",
            "training_portal_partner_ids",
        )
        visible_fields = order.with_user(company_portal).fields_get()
        for field_name in private_fields:
            self.assertNotIn(field_name, visible_fields)
            with self.assertRaises(AccessError):
                order.with_user(company_portal).read([field_name])

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
            "type": "invoice", "email": "billing-generic@example.invalid",
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
        self.assertTrue(advance.training_is_sale_invoice)
        self.assertTrue(final_invoice.training_is_sale_invoice)
        downpayment_lines = final_invoice.invoice_line_ids.filtered("is_downpayment")
        self.assertTrue(downpayment_lines)
        self.assertTrue(all(
            line._get_aml_vals(hide_taxes=False)["label"] == "Down Payment"
            for line in downpayment_lines
        ))
        report_html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", [final_invoice.id],
        )[0]
        self.assertNotIn(advance.name, report_html.decode() if isinstance(report_html, bytes) else report_html)
        colleague = self.env["res.partner"].create({
            "name": "Fictional Billing Colleague", "parent_id": self.partner.id,
            "email": "billing-colleague@example.invalid",
        })
        portal_colleague = new_test_user(
            self.env, login="training_sale_invoice_portal",
            groups="base.group_portal", partner_id=colleague.id,
        )
        with self.assertRaises(AccessError):
            final_invoice.with_user(portal_colleague).read(["name"])
        final_invoice._portal_ensure_token()
        self.assertFalse(final_invoice.with_user(portal_colleague)._get_thread_with_access(
            final_invoice.id, token=final_invoice.access_token,
        ))
        final_invoice.training_portal_partner_ids = [Command.link(colleague.id)]
        self.assertEqual(
            final_invoice.with_user(portal_colleague).read(["name"])[0]["name"],
            final_invoice.name,
        )
        self.assertTrue(final_invoice.with_user(portal_colleague)._get_thread_with_access(
            final_invoice.id, token=final_invoice.access_token,
        ))
        with self.assertRaises(AccessError):
            advance.with_user(portal_colleague).read(["name"])
        self.company.link_qr_code = True
        self.assertFalse(final_invoice.display_link_qr_code)
        self.assertFalse(final_invoice._get_portal_payment_link())
        self.assertFalse(final_invoice._generate_portal_payment_qr())
        invoice_html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", [final_invoice.id],
        )[0]
        self.assertNotIn(
            "payment_link_qrcode",
            invoice_html.decode() if isinstance(invoice_html, bytes) else invoice_html,
        )
        with self.assertRaises(ValidationError):
            self.env["payment.link.wizard"].with_context(
                active_model="account.move", active_id=final_invoice.id,
            ).default_get(["res_model", "res_id", "amount"])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["payment.link.wizard"].create({
                "res_model": "account.move", "res_id": final_invoice.id,
                "amount": 1200, "currency_id": self.eur.id,
                "partner_id": invoice_address.id,
            })
        with self.assertRaises(ValidationError):
            self.env["payment.transaction"].create({
                "invoice_ids": [Command.set(final_invoice.ids)],
            })

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
        cash_account = self.env["account.account"].create({
            "name": "Fictional EUR Cash", "code": "519903",
            "account_type": "asset_cash",
            "company_ids": [Command.set([self.company.id])],
        })
        cash_journal = self.env["account.journal"].create({
            "name": "Fictional EUR Cash", "code": "FEC", "type": "cash",
            "company_id": self.company.id, "currency_id": self.eur.id,
            "default_account_id": cash_account.id,
        })
        cash_method = cash_journal.inbound_payment_method_line_ids.filtered(
            lambda line: line.code == "manual"
        )
        self.assertEqual(len(cash_method), 1)
        cash_wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=final_invoice.ids,
        ).create({
            "journal_id": cash_journal.id, "currency_id": self.eur.id,
            "payment_method_line_id": cash_method.id,
        })
        with self.assertRaises(ValidationError):
            cash_wizard.action_create_payments()
        self.assertEqual(final_invoice.amount_residual, 1200)
        payment_wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=final_invoice.ids,
        ).create({
            "journal_id": bank_journal.id,
            "payment_method_line_id": manual_method.id,
            "currency_id": self.eur.id,
            "amount": 300,
            "payment_difference_handling": "open",
        })
        self.assertTrue(payment_wizard.training_bank_payment_required)
        with self.assertRaises(ValidationError):
            payment_wizard.action_create_payments()
        mad = self.env.ref("base.MAD")
        mad.active = True
        payment_wizard.training_bank_reference = " fictional-transfer-001 "
        with self.assertRaises(ValidationError):
            payment_wizard.action_create_payments()
        payment_wizard.write({
            "training_bank_verified": True,
            "currency_id": mad.id,
        })
        with self.assertRaises(ValidationError):
            payment_wizard.action_create_payments()
        payment_wizard.currency_id = self.eur
        payment_wizard.amount = 300
        payment_wizard.payment_difference_handling = "open"
        self.assertEqual(payment_wizard.amount, 300)
        payment_wizard.action_create_payments()
        first_payment = self.env["account.payment"].search([
            ("journal_id", "=", bank_journal.id),
            ("training_bank_reference", "=", "FICTIONAL-TRANSFER-001"),
        ])
        self.assertEqual(len(first_payment), 1)
        self.assertEqual(first_payment.memo, final_invoice.name)
        self.assertNotEqual(first_payment.memo, first_payment.training_bank_reference)
        self.assertTrue(first_payment.training_bank_verified)
        self.assertEqual(first_payment.training_bank_verified_by_id, self.env.user)
        self.assertTrue(first_payment.training_bank_verified_at)
        self.assertEqual(first_payment.reconciled_invoice_ids, final_invoice)
        receipt_defaults = first_payment._message_get_default_recipients()[first_payment.id]
        self.assertEqual(receipt_defaults["partner_ids"], colleague.ids)
        self.assertFalse(receipt_defaults["email_to"])
        receipt_template = self.env.ref("account.mail_template_data_payment_receipt")
        receipt_recipients = receipt_template._generate_template(
            [first_payment.id], ["email_to", "email_cc", "partner_to", "partner_cc"],
        )[first_payment.id]
        self.assertEqual(receipt_recipients["partner_ids"], colleague.ids)
        receipt_composer = self.env["mail.compose.message"].with_context(
            default_model="account.payment", default_res_ids=first_payment.ids,
            default_template_id=receipt_template.id, default_composition_mode="comment",
        ).create({})
        self.assertEqual(receipt_composer.partner_ids, colleague)
        self.assertTrue(receipt_composer.attachment_ids)
        prepared_receipt = receipt_composer._prepare_mail_values(first_payment.ids)[first_payment.id]
        self.assertEqual(prepared_receipt["partner_ids"], colleague.ids)
        self.assertTrue(prepared_receipt["notify_skip_followers"])
        with self.assertRaises(ValidationError):
            receipt_template.send_mail(
                first_payment.id, force_send=False,
                email_values={"email_to": "unlinked@example.invalid"},
            )
        receipt_mail = self.env["mail.mail"].browse(
            receipt_template.send_mail(first_payment.id, force_send=False)
        )
        self.assertEqual(receipt_mail.recipient_ids, colleague)
        self.assertFalse(receipt_mail.email_to)
        receipt_message = self.env["mail.message"].create({
            "model": "account.payment", "res_id": first_payment.id,
            "message_type": "comment", "body": "Fictional receipt note",
            "partner_ids": [Command.set((colleague + invoice_address).ids)],
        })
        notified = first_payment._notify_get_recipients(receipt_message)
        self.assertIn(colleague.id, [recipient["id"] for recipient in notified])
        self.assertNotIn(invoice_address.id, [recipient["id"] for recipient in notified])
        receipt_attachment = self.env["ir.attachment"].create({
            "name": "fictional-payment-receipt.txt", "raw": b"Fictional payment receipt",
            "mimetype": "text/plain", "res_model": "account.payment",
            "res_id": first_payment.id,
        })
        message_attachment = self.env["ir.attachment"].create({
            "name": "fictional-payment-message.txt", "raw": b"Fictional receipt message",
            "mimetype": "text/plain", "res_model": "mail.message",
            "res_id": receipt_message.id,
        })
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
        final_invoice.training_portal_partner_ids = [Command.clear()]
        with self.assertRaises(ValidationError):
            receipt_composer._prepare_mail_values(first_payment.ids)
        self.assertFalse([
            recipient for recipient in first_payment._notify_get_recipients(receipt_message)
            if recipient["share"]
        ])
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

        split_wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=advance.ids,
        ).create({
            "journal_id": bank_journal.id,
            "payment_method_line_id": manual_method.id,
            "currency_id": self.eur.id,
            "amount": 100,
            "payment_difference_handling": "open",
            "training_bank_reference": " fictional-transfer-001 ",
            "training_bank_verified": True,
        })
        self.assertTrue(split_wizard.training_bank_payment_required)
        self.assertTrue(split_wizard.training_duplicate_reference_exists)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            split_wizard.action_create_payments()
        self.assertEqual(advance.amount_residual, 400)
        split_wizard.training_duplicate_reference_reason = "Fictional split across two invoices"
        split_wizard.action_create_payments()
        self.assertEqual(advance.amount_residual, 300)
        split_payments = self.env["account.payment"].search([
            ("journal_id", "=", bank_journal.id),
            ("training_bank_reference", "=", "FICTIONAL-TRANSFER-001"),
            ("state", "in", ("paid", "reconciled")),
        ])
        self.assertEqual(len(split_payments), 2)
        self.assertTrue(split_payments.filtered("training_duplicate_reference_reason"))
        direct_payment = self.env["account.payment"].create({
            "date": "2026-10-20", "amount": 50,
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": invoice_address.id,
            "journal_id": bank_journal.id, "company_id": self.company.id,
            "currency_id": self.eur.id,
            "payment_method_line_id": manual_method.id,
            "destination_account_id": receivable.id,
            "training_bank_reference": "FICTIONAL-TRANSFER-001",
            "training_bank_verified": True,
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            direct_payment.action_post()
        untagged_payment = self.env["account.payment"].create({
            "date": "2026-10-20", "amount": 50,
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": invoice_address.id,
            "journal_id": bank_journal.id, "company_id": self.company.id,
            "currency_id": self.eur.id,
            "payment_method_line_id": manual_method.id,
            "destination_account_id": receivable.id,
        })
        untagged_payment.action_post()
        invoice_receivable = final_invoice.line_ids.filtered(
            lambda line: line.account_id == receivable
        )
        payment_receivable = untagged_payment.move_id.line_ids.filtered(
            lambda line: line.account_id == receivable
        )
        self.assertEqual(len(invoice_receivable), 1)
        self.assertEqual(len(payment_receivable), 1)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            (invoice_receivable + payment_receivable).reconcile()
        self.assertEqual(final_invoice.amount_residual, 900)
        unchecked_payment = self.env["account.payment"].create({
            "date": "2026-10-20", "amount": 50,
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": invoice_address.id,
            "journal_id": bank_journal.id, "company_id": self.company.id,
            "currency_id": self.eur.id,
            "payment_method_line_id": manual_method.id,
            "destination_account_id": receivable.id,
            "training_bank_reference": "FICTIONAL-UNCHECKED-001",
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            unchecked_payment.action_post()
        valid_direct_payment = self.env["account.payment"].create({
            "date": "2026-10-20", "amount": 50,
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": invoice_address.id,
            "journal_id": bank_journal.id, "company_id": self.company.id,
            "currency_id": self.eur.id,
            "payment_method_line_id": manual_method.id,
            "destination_account_id": receivable.id,
            "training_bank_reference": "FICTIONAL-TRANSFER-002",
            "training_bank_verified": True,
        })
        valid_direct_payment.action_post()
        unallocated_recipients = valid_direct_payment._message_get_default_recipients()[
            valid_direct_payment.id
        ]
        self.assertFalse(unallocated_recipients["partner_ids"])
        valid_receivable = valid_direct_payment.move_id.line_ids.filtered(
            lambda line: line.account_id == receivable
        )
        (invoice_receivable + valid_receivable).reconcile()
        self.assertEqual(final_invoice.amount_residual, 850)
        cash_payment = self.env["account.payment"].create({
            "date": "2026-10-20", "amount": 50,
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": invoice_address.id,
            "journal_id": cash_journal.id, "company_id": self.company.id,
            "currency_id": self.eur.id,
            "payment_method_line_id": cash_method.id,
            "destination_account_id": receivable.id,
            "training_bank_reference": "FICTIONAL-CASH-REF-001",
            "training_bank_verified": True,
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            cash_payment.action_post()
        accountant = new_test_user(
            self.env, login="training_sale_accountant",
            groups="account.group_account_invoice,sales_team.group_sale_salesman",
            company_id=self.company.id, company_ids=[Command.set([self.company.id])],
        )
        notice.with_user(accountant).action_void()
        self.assertEqual(notice.state, "void")
        self.assertEqual(final_invoice.amount_residual, 850)
        statement_line = self.env["account.bank.statement.line"].create({
            "journal_id": bank_journal.id,
            "date": "2026-10-20",
            "payment_ref": "",
            "partner_id": invoice_address.id,
            "amount": 50,
            "counterpart_account_id": receivable.id,
        })
        statement_receivable = statement_line.move_id.line_ids.filtered(
            lambda line: line.account_id == receivable
        )
        self.assertFalse(statement_line.payment_ref)
        self.assertFalse(statement_receivable.payment_id)
        (invoice_receivable + statement_receivable).reconcile()
        self.assertEqual(final_invoice.amount_residual, 800)
        mad_journal = self.env["account.journal"].create({
            "name": "Fictional MAD Bank", "code": "FMB", "type": "bank",
            "company_id": self.company.id, "currency_id": mad.id,
            "default_account_id": bank_account.id,
        })
        other_currency_line = self.env["account.bank.statement.line"].create({
            "journal_id": mad_journal.id,
            "date": "2026-10-20",
            "payment_ref": "FICTIONAL-MAD-STATEMENT",
            "partner_id": invoice_address.id,
            "amount": 50,
            "counterpart_account_id": receivable.id,
        })
        other_currency_receivable = other_currency_line.move_id.line_ids.filtered(
            lambda line: line.account_id == receivable
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            (invoice_receivable + other_currency_receivable).reconcile()
        self.assertEqual(final_invoice.amount_residual, 800)
        cash_statement = self.env["account.bank.statement.line"].create({
            "journal_id": cash_journal.id,
            "date": "2026-10-20",
            "payment_ref": "FICTIONAL-CASH-STATEMENT",
            "partner_id": invoice_address.id,
            "amount": 50,
            "counterpart_account_id": receivable.id,
        })
        cash_receivable = cash_statement.move_id.line_ids.filtered(
            lambda line: line.account_id == receivable
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            (invoice_receivable + cash_receivable).reconcile()
        self.assertEqual(final_invoice.amount_residual, 800)
