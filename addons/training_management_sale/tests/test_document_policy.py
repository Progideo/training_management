"""S02.1: shared grants, native fallbacks and real restricted profiles."""

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import file_open
from odoo.tools.binary import BinaryBytes


@tagged("post_install", "-at_install")
class TestTrainingDocumentPolicy(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sales = new_test_user(cls.env, login="policy_sales", groups="sales_team.group_sale_salesman")
        cls.finance = new_test_user(cls.env, login="policy_finance", groups="account.group_account_invoice")
        cls.internal = new_test_user(cls.env, login="policy_internal", groups="base.group_user")
        cls.buyer = cls.env["res.partner"].create({"name": "Fictional Policy Buyer"})
        cls.allowed = new_test_user(cls.env, login="policy_allowed", groups="base.group_portal")
        cls.denied = new_test_user(cls.env, login="policy_denied", groups="base.group_portal")
        for user in cls.allowed | cls.denied:
            user.partner_id.write({"parent_id": cls.buyer.id, "email": user.login + "@example.invalid"})
        cls.accounts = {}
        for key, kind, reconcile in (
            ("income", "income", False),
            ("receivable", "asset_receivable", True),
            ("bank", "asset_cash", False),
            ("outstanding", "asset_current", True),
        ):
            cls.accounts[key] = cls.env["account.account"].create(
                {
                    "name": "Fictional Policy " + key,
                    "code": "POL" + key,
                    "account_type": kind,
                    "reconcile": reconcile,
                    "company_ids": [Command.set(cls.env.company.ids)],
                }
            )
        cls.buyer.property_account_receivable_id = cls.accounts["receivable"]
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Fictional Policy Sales",
                "code": "POL",
                "type": "sale",
                "default_account_id": cls.accounts["income"].id,
            }
        )
        cls.bank = cls.env["account.journal"].create(
            {
                "name": "Fictional Policy Bank",
                "code": "POB",
                "type": "bank",
                "default_account_id": cls.accounts["bank"].id,
            }
        )
        cls.bank.inbound_payment_method_line_ids.filtered(
            lambda m: m.code == "manual"
        ).payment_account_id = cls.accounts["outstanding"]
        cls.product = cls.env["product.product"].create({"name": "Fictional Policy Service", "type": "service"})

    def setUp(self):
        super().setUp()
        self.policy = self.env["training.document.policy"]
        self.order = (
            self.env["sale.order"]
            .with_user(self.sales)
            .create(
                {
                    "partner_id": self.buyer.id,
                    "training_request_kind": "group",
                    "training_portal_partner_ids": [Command.set(self.allowed.partner_id.ids)],
                }
            )
        )

    def _invoice(self, *, training=True):
        line = (
            self.env["sale.order.line"]
            .with_user(self.sales)
            .create({"order_id": self.order.id, "product_id": self.product.id, "product_uom_qty": 1, "price_unit": 100})
        )
        return (
            self.env["account.move"]
            .with_user(self.finance)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.buyer.id,
                    "journal_id": self.sale_journal.id,
                    "training_portal_partner_ids": [Command.set(self.allowed.partner_id.ids)],
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "Fictional Service",
                                "quantity": 1,
                                "price_unit": 100,
                                "account_id": self.accounts["income"].id,
                                "tax_ids": [Command.clear()],
                                "sale_line_ids": [Command.set(line.ids if training else [])],
                            }
                        )
                    ],
                }
            )
        )

    def test_current_grant_does_not_replace_native_internal_rights(self):
        self.assertTrue(self.policy.with_user(self.allowed)._can_read(self.order))
        self.assertFalse(self.policy.with_user(self.denied)._can_read(self.order))
        self.assertFalse(self.policy.with_user(self.internal)._can_read(self.order))
        with self.assertRaises(AccessError):
            self.order.with_user(self.internal).read(["name"])
        self.assertTrue(self.order.with_user(self.allowed).read(["name"]))
        self.order.training_portal_partner_ids = [Command.clear()]
        with self.assertRaises(AccessError):
            self.order.with_user(self.allowed).read(["name"])
        self.assertFalse(self.order.with_user(self.denied)._get_thread_with_access(self.order.id))

    def test_message_file_and_binary_entry_points_recheck_revocation(self):
        message = self.env["mail.message"].create(
            {
                "model": "sale.order",
                "res_id": self.order.id,
                "body": "Fictional private message",
                "message_type": "comment",
                "partner_ids": [Command.set(self.allowed.partner_id.ids)],
            }
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional.txt",
                "raw": b"Fictional private file",
                "res_model": "mail.message",
                "res_id": message.id,
            }
        )
        token = attachment.generate_access_token()[0]
        binary = self.env["ir.binary"].with_user(self.allowed)
        found = binary._find_record(res_id=attachment.id, access_token=token, field="raw")
        self.assertTrue(binary._get_stream_from(found))
        self.assertEqual(self.policy._document(attachment), self.order.sudo())
        self.order.training_portal_partner_ids = [Command.clear()]
        with self.assertRaises(AccessError):
            binary._find_record(res_id=attachment.id, access_token=token, field="raw")
        with self.assertRaises(AccessError):
            binary._get_stream_from(found)
        self.assertFalse(message.with_user(self.allowed).sudo()._get_with_access())
        self.assertFalse(self.env["mail.message"].with_user(self.allowed).search([("id", "=", message.id)]))
        with self.assertRaises(AccessError):
            message.with_user(self.allowed).read(["body"])
        # Native export already rejects non-administrators; no custom override.
        for user in (self.allowed, self.sales, self.internal):
            with self.assertRaises(AccessError):
                message.with_user(user).export_data(["body"])

    def test_native_scheduled_composer_uses_guarded_preparation(self):
        composer = (
            self.env["mail.compose.message"]
            .with_user(self.sales)
            .with_context(
                default_model="sale.order", default_res_ids=self.order.ids, default_composition_mode="comment"
            )
            .create({"scheduled_date": "2099-01-01 12:00:00", "body": "Fictional scheduled note"})
        )
        composer.partner_ids = [Command.set(self.denied.partner_id.ids)]
        scheduled = self.env["mail.scheduled.message"]
        count = scheduled.search_count([])
        with self.assertRaises(ValidationError):
            composer._action_schedule_message()
        self.assertEqual(scheduled.search_count([]), count)
        composer.partner_ids = [Command.set(self.allowed.partner_id.ids)]
        self.assertEqual(len(composer._action_schedule_message()), 1)

    def test_invoice_sending_without_template_keeps_named_defaults(self):
        invoice = self._invoice()
        invoice.action_post()
        wizard = (
            self.env["account.move.send.wizard"]
            .with_user(self.finance)
            .create({"move_id": invoice.id, "template_id": False})
        )
        self.assertEqual(wizard.mail_partner_ids, self.allowed.partner_id)
        invoice.training_portal_partner_ids = [Command.clear()]
        wizard._compute_mail_partners()
        self.assertFalse(wizard.mail_partner_ids)

    def test_receipt_intersection_and_mixed_documents_use_real_reconciliation(self):
        first, second = self._invoice(), self._invoice()
        second.training_portal_partner_ids = [Command.set((self.allowed.partner_id | self.denied.partner_id).ids)]
        invoices = first | second
        invoices.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create(
                {
                    "journal_id": self.bank.id,
                    "group_payment": True,
                }
            )
        )
        wizard.action_create_payments()
        payment = self.env["account.payment"].search([("invoice_ids", "in", invoices.ids)])
        self.assertEqual(len(payment), 1)
        self.assertEqual(payment.reconciled_invoice_ids, invoices)
        self.assertEqual(self.policy._partners(payment), self.allowed.partner_id)
        self.assertFalse(self.policy.with_user(self.denied)._can_read(payment))
        self.assertTrue(self.policy.with_user(self.allowed)._can_read(payment))
        second.training_portal_partner_ids = [Command.set(self.denied.partner_id.ids)]
        self.assertFalse(self.policy._partners(payment))
        with self.assertRaises(ValidationError):
            self.policy._check_send(payment, self.allowed.partner_id)
        # A native (non-training) invoice in the same receipt closes external grants.
        native, training = self._invoice(training=False), self._invoice()
        mixed = native | training
        mixed.action_post()
        extra = (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(active_model="account.move", active_ids=mixed.ids)
            .create(
                {
                    "journal_id": self.bank.id,
                    "group_payment": True,
                }
            )
        )
        extra.action_create_payments()
        mixed_payment = self.env["account.payment"].search([("invoice_ids", "in", mixed.ids)])
        self.assertEqual(len(mixed_payment), 1)
        self.assertEqual(mixed_payment.reconciled_invoice_ids, mixed)
        self.assertFalse(self.policy._partners(mixed_payment))

    def test_unallocated_receipt_and_non_training_native_fallback(self):
        payment = (
            self.env["account.payment"]
            .with_user(self.finance)
            .create(
                {
                    "partner_id": self.buyer.id,
                    "journal_id": self.bank.id,
                    "amount": 10,
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "training_receipt_restricted": True,
                }
            )
        )
        self.assertTrue(self.policy._restricted(payment))
        self.assertFalse(self.policy._partners(payment))
        self.assertFalse(self.policy.with_user(self.allowed)._can_read(payment))
        native = self.env["sale.order"].with_user(self.sales).create({"partner_id": self.buyer.id})
        self.assertFalse(self.policy._restricted(native))
        self.policy._check_send(native, self.denied.partner_id, email_to="native@example.invalid")
        file = self.env["ir.attachment"].create(
            {"name": "native.txt", "raw": b"Fictional native file", "res_model": "sale.order", "res_id": native.id}
        )
        public = self.env.ref("base.public_user")
        self.assertTrue(
            self.env["ir.binary"]
            .with_user(public)
            ._find_record(res_id=file.id, access_token=file.generate_access_token()[0], field="raw")
        )

    def test_batch_payments_preserve_bank_metadata(self):
        invoices = self._invoice() | self._invoice()
        invoices.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create(
                {
                    "journal_id": self.bank.id,
                    "group_payment": False,
                }
            )
        )
        wizard.action_create_payments()
        payments = self.env["account.payment"].search([("invoice_ids", "in", invoices.ids)])
        self.assertEqual(len(payments), 2)
        self.assertEqual(payments.mapped("reconciled_invoice_ids"), invoices)
        self.assertFalse(payments.mapped("training_bank_verified_by_id"))
        self.assertTrue(all(payments.mapped("training_receipt_restricted")))
        payments.move_id.line_ids.remove_move_reconcile()
        for payment in payments:
            self.assertTrue(self.policy._restricted(payment))
            self.assertFalse(self.policy._partners(payment))
            with self.assertRaises(ValidationError):
                payment.write({"training_receipt_restricted": False})

    def test_payment_link_write_and_compute_still_refuse_training(self):
        native = self.env["sale.order"].with_user(self.sales).create({"partner_id": self.buyer.id})
        wizard = (
            self.env["payment.link.wizard"]
            .with_user(self.sales)
            .create(
                {
                    "res_model": "sale.order",
                    "res_id": native.id,
                    "amount": 100,
                    "currency_id": native.currency_id.id,
                    "partner_id": self.buyer.id,
                }
            )
        )
        self.assertTrue(wizard.link)
        wizard.write({"res_id": self.order.id})
        wizard._compute_link()
        self.assertTrue(wizard.link)

    def test_transaction_write_cannot_attach_a_training_document(self):
        provider = self.env["payment.provider"].create({"name": "Fictional Provider", "code": "none"})
        with file_open("web/static/img/placeholder.png", "rb") as image:
            method = self.env["payment.method"].create(
                {
                    "name": "Fictional Method",
                    "code": "fictional",
                    "provider_id": provider.id,
                    "image": BinaryBytes(image.read()),
                }
            )
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": provider.id,
                "payment_method_id": method.id,
                "reference": "FICTIONAL-POLICY-TX",
                "amount": 100,
                "currency_id": self.env.company.currency_id.id,
                "partner_id": self.buyer.id,
            }
        )
        for values in (
            {"sale_order_ids": [Command.set(self.order.ids)]},
            {"invoice_ids": [Command.set(self._invoice().ids)]},
        ):
            tx.with_user(self.finance).with_context(payment_safe_write=True).write(values)
        self.assertEqual(tx.sale_order_ids, self.order)
        self.assertTrue(tx.invoice_ids.training_is_sale_invoice)

    def test_native_invoice_sender_ignores_followers_outside_selected_contacts(self):
        invoice = self._invoice()
        invoice.action_post()
        # Even an internal follower is not an explicitly selected document recipient.
        invoice.message_subscribe(partner_ids=(self.denied.partner_id | self.sales.partner_id).ids)
        sender = self.env["account.move.send"].with_user(self.finance).with_context(mail_notify_force_send=False)
        template = self.env.ref("account.email_template_edi_invoice")
        params = sender._get_mail_params(
            invoice,
            {
                "mail_partner_ids": self.allowed.partner_id.ids,
                "mail_attachments_widget": [],
                "author_partner_id": self.finance.partner_id.id,
                "mail_body": "Fictional invoice notification",
                "mail_subject": "Fictional named-contact invoice",
            },
        )
        sender._send_mail(invoice, template, subtype_id=self.env.ref("mail.mt_comment").id, **params)
        message = invoice.message_ids.filtered(lambda m: m.subject == "Fictional named-contact invoice")
        self.assertEqual(len(message), 1)
        self.assertEqual(message.partner_ids, self.allowed.partner_id)
        recipients = message.notification_ids.res_partner_id
        self.assertIn(self.allowed.partner_id, recipients)
        self.assertNotIn(self.denied.partner_id, recipients)
        self.assertNotIn(self.sales.partner_id, recipients)

    def test_internal_binary_token_cannot_replace_native_document_rights(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-internal-token.txt",
                "raw": b"Fictional private data",
                "res_model": "sale.order",
                "res_id": self.order.id,
            }
        )
        token = attachment.generate_access_token()[0]
        foreign_company = self.env["res.company"].create({"name": "Fictional Token Company B"})
        foreign_sales = new_test_user(
            self.env,
            login="policy_foreign_sales",
            groups="sales_team.group_sale_salesman",
            company_id=foreign_company.id,
            company_ids=[Command.set(foreign_company.ids)],
        )
        for user in (self.internal, foreign_sales):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._find_record(
                    res_id=attachment.id, access_token=token, field="raw"
                )
        self.assertTrue(
            self.env["ir.binary"]
            .with_user(self.sales)
            ._find_record(res_id=attachment.id, access_token=token, field="raw")
        )

    def test_ordinary_mail_cannot_send_a_foreign_protected_attachment(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-private-quotation.txt",
                "raw": b"Fictional private quote",
                "res_model": "sale.order",
                "res_id": self.order.id,
            }
        )
        native = self.env["sale.order"].with_user(self.sales).create({"partner_id": self.buyer.id})
        mail = self.env["mail.mail"].create(
            {
                "model": "sale.order",
                "res_id": native.id,
                "subject": "Fictional ordinary mail",
                "body_html": "Fictional body",
                "email_from": "sender@example.invalid",
                "recipient_ids": [Command.set(self.denied.partner_id.ids)],
                "attachment_ids": [Command.set(attachment.ids)],
            }
        )
        with self.assertRaisesRegex(ValidationError, "currently authorized named contacts"):
            mail.sudo()._prepare_outgoing_list()
        mail.recipient_ids = [Command.set(self.allowed.partner_id.ids)]
        self.assertTrue(mail.sudo()._prepare_outgoing_list())
        self.order.training_portal_partner_ids = [Command.clear()]
        with self.assertRaisesRegex(ValidationError, "currently authorized named contacts"):
            mail.sudo()._prepare_outgoing_list()

    def test_scheduled_delivery_keeps_selected_recipients_only(self):
        self.order.message_subscribe(partner_ids=self.internal.partner_id.ids)
        composer = (
            self.env["mail.compose.message"]
            .with_user(self.sales)
            .with_context(
                default_model="sale.order", default_res_ids=self.order.ids, default_composition_mode="comment"
            )
            .create(
                {
                    "scheduled_date": "2099-01-01 12:00:00",
                    "subject": "Fictional deferred selected contacts",
                    "body": "Fictional scheduled private body",
                }
            )
        )
        composer.partner_ids = [Command.set(self.allowed.partner_id.ids)]
        scheduled = composer._action_schedule_message()
        scheduled.with_context(mail_notify_force_send=False).post_message()
        message = self.order.message_ids.filtered(lambda m: m.subject == "Fictional deferred selected contacts")
        self.assertEqual(len(message), 1)
        recipients = message.notification_ids.res_partner_id
        self.assertIn(self.allowed.partner_id, recipients)
        self.assertNotIn(self.internal.partner_id, recipients)

    def test_scheduled_revocation_does_not_notify_the_old_recipient(self):
        composer = (
            self.env["mail.compose.message"]
            .with_user(self.sales)
            .with_context(
                default_model="sale.order", default_res_ids=self.order.ids, default_composition_mode="comment"
            )
            .create(
                {
                    "scheduled_date": "2099-01-01 12:00:00",
                    "subject": "Fictional revoked schedule",
                    "body": "Fictional content after revoke",
                }
            )
        )
        composer.partner_ids = [Command.set(self.allowed.partner_id.ids)]
        scheduled = composer._action_schedule_message()
        self.order.training_portal_partner_ids = [Command.clear()]
        scheduled.with_context(mail_notify_force_send=False).post_message()
        message = self.order.message_ids.filtered(lambda m: m.subject == "Fictional revoked schedule")
        self.assertEqual(len(message), 1)
        self.assertNotIn(self.allowed.partner_id, message.notification_ids.res_partner_id)
        with self.assertRaises(AccessError):
            message.with_user(self.allowed).read(["body"])

    def test_non_training_schedule_keeps_native_followers(self):
        native = self.env["sale.order"].with_user(self.sales).create({"partner_id": self.buyer.id})
        native.message_subscribe(partner_ids=self.internal.partner_id.ids)
        composer = (
            self.env["mail.compose.message"]
            .with_user(self.sales)
            .with_context(default_model="sale.order", default_res_ids=native.ids, default_composition_mode="comment")
            .create(
                {
                    "scheduled_date": "2099-01-01 12:00:00",
                    "subject": "Fictional native schedule",
                    "body": "Fictional ordinary message",
                }
            )
        )
        composer.partner_ids = [Command.set(self.allowed.partner_id.ids)]
        composer._action_schedule_message().with_context(mail_notify_force_send=False).post_message()
        message = native.message_ids.filtered(lambda m: m.subject == "Fictional native schedule")
        self.assertEqual(len(message), 1)
        self.assertIn(self.internal.partner_id, message.notification_ids.res_partner_id)

    def test_native_foreign_currency_payment_partial_and_credit(self):
        company = self.env.company
        usd, eur, gbp = (self.env.ref("base." + code) for code in ("USD", "EUR", "GBP"))
        company.currency_id = usd
        (usd | eur | gbp).write({"active": True})
        for currency, rate in ((usd, 1), (eur, 0.5), (gbp, 0.25)):
            self.env["res.currency.rate"].create(
                {
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "name": "2026-10-01",
                    "rate": rate,
                }
            )
        invoice = self._invoice()
        invoice.write({"currency_id": eur.id, "invoice_date": "2026-10-20", "date": "2026-10-20"})
        invoice.action_post()
        self.assertEqual(invoice.amount_total, 100)
        self.assertEqual(invoice.amount_total_signed, 200)
        self.bank.currency_id = gbp
        wizard = (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create(
                {
                    "journal_id": self.bank.id,
                    "currency_id": gbp.id,
                    "amount": 25,
                    "payment_date": "2026-10-20",
                    "payment_difference_handling": "open",
                }
            )
        )
        payment = wizard._create_payments()
        self.assertEqual(payment.currency_id, gbp)
        self.assertEqual(invoice.amount_residual, 50)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertFalse(payment.training_bank_reference)
        self.assertTrue(payment.training_receipt_restricted)
        self.assertTrue(self.policy.with_user(self.allowed)._can_read(payment))
        self.assertFalse(self.policy.with_user(self.denied)._can_read(payment))
        # A native credit note settles the remaining balance, without a second balance.
        credit = invoice._reverse_moves(default_values_list=[{"date": "2026-10-20"}], cancel=False)
        credit.invoice_line_ids.price_unit = 50
        credit.action_post()
        self.assertTrue(credit.training_is_sale_invoice)
        receivables = (invoice | credit).line_ids.filtered(
            lambda line: line.account_id == self.accounts["receivable"] and not line.reconciled
        )
        receivables.with_user(self.finance).reconcile()
        self.assertEqual(invoice.amount_residual, 0)
        self.assertEqual(credit.amount_residual, 0)
        self.assertFalse(self.env["training.enrollment"].search([]))
        payment.move_id.line_ids.remove_move_reconcile()
        self.assertTrue(payment.training_receipt_restricted)
        self.assertFalse(self.policy.with_user(self.allowed)._can_read(payment))

    def test_native_cash_and_alternative_payment_method(self):
        cash = self.env["account.journal"].create(
            {
                "name": "Fictional Native Cash",
                "code": "PNC",
                "type": "cash",
                "default_account_id": self.accounts["bank"].id,
            }
        )
        method = self.env["account.payment.method"].create(
            {
                "name": "Fictional local method",
                "code": "fictional_local",
                "payment_type": "inbound",
            }
        )
        method_line = self.env["account.payment.method.line"].create(
            {
                "payment_method_id": method.id,
                "journal_id": cash.id,
                "payment_account_id": self.accounts["outstanding"].id,
            }
        )
        invoice = self._invoice()
        invoice.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create({"journal_id": cash.id, "payment_method_line_id": method_line.id, "amount": 40})
        )
        payment = wizard._create_payments()
        self.assertEqual(payment.payment_method_line_id, method_line)
        self.assertEqual(invoice.amount_residual, 60)
        self.assertFalse(payment.training_bank_verified)
        self.assertTrue(payment.training_receipt_restricted)

    def test_native_exchange_difference_uses_company_accounts(self):
        company = self.env.company
        usd, eur = self.env.ref("base.USD"), self.env.ref("base.EUR")
        company.currency_id = usd
        eur.active = True
        for currency, date, rate in (
            (usd, "2026-10-01", 1),
            (eur, "2026-10-01", 0.5),
            (eur, "2026-10-20", 0.25),
        ):
            self.env["res.currency.rate"].create(
                {
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "name": date,
                    "rate": rate,
                }
            )
        exchange_accounts = {}
        for code, kind in (("POLFXG", "income"), ("POLFXL", "expense")):
            exchange_accounts[kind] = self.env["account.account"].create(
                {
                    "name": "Fictional " + code,
                    "code": code,
                    "account_type": kind,
                    "company_ids": [Command.set(company.ids)],
                }
            )
        exchange_journal = self.env["account.journal"].create(
            {
                "name": "Fictional Native Exchange",
                "code": "PFX",
                "type": "general",
            }
        )
        company.write(
            {
                "currency_exchange_journal_id": exchange_journal.id,
                "income_currency_exchange_account_id": exchange_accounts["income"].id,
                "expense_currency_exchange_account_id": exchange_accounts["expense"].id,
            }
        )
        invoice = self._invoice()
        invoice.write({"currency_id": eur.id, "invoice_date": "2026-10-01", "date": "2026-10-01"})
        invoice.action_post()
        self.assertEqual(invoice.amount_total_signed, 200)
        wizard = (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create(
                {
                    "journal_id": self.bank.id,
                    "currency_id": eur.id,
                    "amount": 100,
                    "payment_date": "2026-10-20",
                    "payment_difference_handling": "open",
                }
            )
        )
        payment = wizard._create_payments()
        self.assertEqual(invoice.amount_residual, 0)
        self.assertEqual(payment.amount, 100)
        exchange = self.env["account.move"].search([("journal_id", "=", exchange_journal.id), ("state", "=", "posted")])
        self.assertTrue(exchange)
        gain = exchange.line_ids.filtered(lambda line: line.account_id == exchange_accounts["income"])
        self.assertEqual(sum(gain.mapped("credit")), 200)
        self.assertTrue(payment.training_receipt_restricted)
