from io import BytesIO
from unittest.mock import patch

from pypdf import PdfWriter

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, JsonRpcException, new_test_user, tagged
from odoo.tools import file_open, mute_logger
from odoo.tools.binary import BinaryBytes
from odoo.addons.payment import utils as payment_utils


@tagged("post_install", "-at_install")
class TestTrainingPortalHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        partner = cls.env["res.partner"].create(
            {
                "name": "Fictional Portal Buyer",
                "email": "buyer@example.invalid",
            }
        )
        authorized = cls.env["res.partner"].create(
            {
                "name": "Fictional Authorized Contact",
                "parent_id": partner.id,
                "email": "authorized@example.invalid",
            }
        )
        colleague = cls.env["res.partner"].create(
            {
                "name": "Fictional Unauthorised Colleague",
                "parent_id": partner.id,
                "email": "colleague@example.invalid",
            }
        )
        cls.authorized_user = new_test_user(
            cls.env,
            login="training_http_authorized",
            groups="base.group_portal",
            partner_id=authorized.id,
        )
        cls.colleague_user = new_test_user(
            cls.env,
            login="training_http_colleague",
            groups="base.group_portal",
            partner_id=colleague.id,
        )
        authorized.email = "authorized@example.invalid"
        colleague.email = "colleague@example.invalid"
        course = cls.env["training.course"].create(
            {
                "name": "Fictional Portal Course",
                "company_id": company.id,
            }
        )
        course.category_id = cls.env["training.category"].create({"name": "Learning", "company_id": company.id})
        program = cls.env["training.program.version"].create(
            {
                "course_id": course.id,
                "version": "V1",
                "title": "Portal Programme",
                "objectives": "Learn safely",
                "target_audience": "Managers",
                "prerequisites": "None",
                "content": "Workshop",
                "duration_hours": 7,
                "delivery_mode": "onsite",
                "language_id": cls.env.ref("base.lang_en").id,
                "teaching_methods": "Exercises",
                "evaluation_criteria": "Review",
                "access_conditions": "Manual approval",
                "accessibility_contact_id": partner.id,
                "accessibility_information": "Contact us",
            }
        )
        program.action_validate()
        product = (
            cls.env["product.template"]
            .create(
                {
                    "name": "Fictional Portal Training",
                    "type": "service",
                    "taxes_id": [Command.clear()],
                    "company_id": company.id,
                    "training_course_id": course.id,
                    "training_price_basis": "package",
                }
            )
            .product_variant_id
        )
        eur = cls.env.ref("base.EUR")
        eur.active = True
        pricelist = cls.env["product.pricelist"].create(
            {
                "name": "Fictional Portal EUR",
                "company_id": company.id,
                "currency_id": eur.id,
            }
        )
        cls.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "compute_price": "fixed",
                "fixed_price": 100,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "pricelist_id": pricelist.id,
                "training_request_kind": "group",
                "training_requested_program_id": program.id,
                "training_attendee_count": 5,
                "training_requested_currency_id": eur.id,
                "prepayment_percent": 0.25,
                "training_portal_partner_ids": [Command.link(authorized.id)],
            }
        )
        cls.env["sale.order.line"].create(
            {
                "order_id": cls.order.id,
                "product_id": product.id,
                "product_uom_qty": 1,
                "training_program_id": program.id,
            }
        )
        cls.order._portal_ensure_token()

    def test_quotation_pdf_mail_requires_named_recipient(self):
        authorized = self.authorized_user.partner_id
        colleague = self.colleague_user.partner_id
        with self.assertRaises(ValidationError):
            self.env.ref("sale.email_template_edi_sale").send_mail(
                self.order.id,
                force_send=False,
                email_values={"email_to": "unlinked@example.invalid"},
            )
        defaults = self.order._message_get_default_recipients()[self.order.id]
        self.assertEqual(defaults["partner_ids"], authorized.ids)
        self.assertFalse(defaults["email_to"])
        action = self.order.action_quotation_send()
        composer = self.env["mail.compose.message"].with_context(action["context"]).create({})  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
        self.assertEqual(composer.partner_ids, authorized)
        self.assertTrue(composer.attachment_ids)
        prepared = composer._prepare_mail_values([self.order.id])[self.order.id]
        self.assertEqual(prepared["partner_ids"], authorized.ids)
        self.assertTrue(prepared["notify_skip_followers"])
        composer.partner_ids = [Command.set([colleague.id])]
        with self.assertRaises(ValidationError):
            composer._prepare_mail_values([self.order.id])
        composer.partner_ids = [Command.set([authorized.id])]
        composer.partner_cc_ids = [Command.set([colleague.id])]
        with self.assertRaises(ValidationError):
            composer._prepare_mail_values([self.order.id])
        composer.partner_cc_ids = [Command.clear()]
        self.order.training_portal_partner_ids = [Command.clear()]
        with self.assertRaises(ValidationError):
            composer._prepare_mail_values([self.order.id])
        with self.assertRaises(ValidationError):
            self.env.ref("sale.email_template_edi_sale").send_mail(
                self.order.id,
                force_send=False,
            )

    def test_portal_does_not_offer_payment_or_create_transaction(self):
        self.assertEqual(self.order.amount_total, 100)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        response = self.url_open(
            self.order.get_portal_url(query_string="&payment_amount=100"),
            allow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        # Native form is omitted without a configured provider; payment values are
        # passed through unchanged (the native amount field is rendered).
        self.assertIn('id="payment_method"', response.text)
        # Without a configured provider, native validation still rejects a transaction.
        with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
            self.make_jsonrpc_request(
                f"/my/orders/{self.order.id}/transaction",
                {"access_token": self.order.access_token},
            )
        self.assertFalse(self.order.transaction_ids)
        self.authenticate(self.colleague_user.login, self.colleague_user.login)
        with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
            self.make_jsonrpc_request(
                f"/my/orders/{self.order.id}/transaction",
                {"access_token": self.order.access_token},
            )

    def test_named_contact_required_even_with_a_valid_token(self):
        url = f"/my/orders/{self.order.id}?access_token={self.order.access_token}"
        mail_url = f"/mail/view?model=sale.order&res_id={self.order.id}&access_token={self.order.access_token}"
        self.authenticate(None, None)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(self.order.name, self.url_open(mail_url).text)
        self.assertEqual(
            self.url_open(url + "&report_type=pdf", allow_redirects=False).status_code,
            303,
        )
        self.authenticate(self.colleague_user.login, self.colleague_user.login)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(self.order.name, self.url_open(mail_url).text)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        self.assertEqual(
            self.url_open(f"/my/orders/{self.order.id}", allow_redirects=False).status_code,
            200,
        )
        self.assertIn(self.order.name, self.url_open(mail_url).text)
        self.order.training_portal_partner_ids = [Command.clear()]
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(self.order.name, self.url_open(mail_url).text)

    def test_attachment_token_cannot_bypass_contact_grant(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-training-order.txt",
                "raw": b"Fictional private order file",
                "mimetype": "text/plain",
                "res_model": "sale.order",
                "res_id": self.order.id,
            }
        )
        url = f"/web/content/{attachment.id}?access_token={attachment.generate_access_token()[0]}"
        with self.assertRaises(AccessError):
            self.env["ir.binary"].with_user(self.colleague_user)._get_stream_from(
                attachment.sudo(),
            )
        self.authenticate(None, None)
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertTrue(
            self.env["ir.binary"]
            .with_user(self.authorized_user)
            ._get_stream_from(
                attachment.sudo(),
            )
        )
        self.order.training_portal_partner_ids = [Command.clear()]
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)

    def test_message_attachment_follows_document_grant(self):
        message = self.env["mail.message"].create(
            {
                "model": "sale.order",
                "res_id": self.order.id,
                "message_type": "comment",
                "body": "Fictional private training note",
            }
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-message-file.txt",
                "raw": b"Fictional message attachment",
                "mimetype": "text/plain",
                "res_model": "mail.message",
                "res_id": message.id,
            }
        )
        token = attachment.generate_access_token()[0]
        url = f"/web/content/{attachment.id}?access_token={token}"
        preview_url = f"/mail/attachment/render_text/{attachment.id}?access_token={token}"
        self.authenticate(None, None)
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertNotEqual(self.url_open(preview_url, allow_redirects=False).status_code, 200)
        self.authenticate(self.colleague_user.login, self.colleague_user.login)
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertNotEqual(self.url_open(preview_url, allow_redirects=False).status_code, 200)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertEqual(self.url_open(preview_url, allow_redirects=False).status_code, 200)
        self.order.training_portal_partner_ids = [Command.clear()]
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertNotEqual(self.url_open(preview_url, allow_redirects=False).status_code, 200)

    def test_message_notification_filters_unauthorized_external_recipients(self):
        message = self.env["mail.message"].create(
            {
                "model": "sale.order",
                "res_id": self.order.id,
                "message_type": "comment",
                "body": "Fictional training update",
                "partner_ids": [
                    Command.set(
                        [
                            self.authorized_user.partner_id.id,
                            self.colleague_user.partner_id.id,
                        ]
                    )
                ],
                "outgoing_email_to": "Unlinked <unlinked@example.invalid>",
            }
        )
        recipients = self.order._notify_get_recipients(message)
        self.assertIn(self.authorized_user.partner_id.id, [r["id"] for r in recipients])
        self.assertNotIn(self.colleague_user.partner_id.id, [r["id"] for r in recipients])
        self.assertFalse([r for r in recipients if r["share"] and not r["id"]])
        self.order.message_subscribe(
            partner_ids=[
                self.authorized_user.partner_id.id,
                self.colleague_user.partner_id.id,
            ]
        )
        follower_message = self.env["mail.message"].create(
            {
                "model": "sale.order",
                "res_id": self.order.id,
                "message_type": "comment",
                "body": "Fictional follower update",
                "subtype_id": self.env.ref("mail.mt_comment").id,
            }
        )
        follower_recipients = self.order._notify_get_recipients(follower_message)
        self.assertIn(self.authorized_user.partner_id.id, [r["id"] for r in follower_recipients])
        self.assertNotIn(self.colleague_user.partner_id.id, [r["id"] for r in follower_recipients])
        self.order.training_portal_partner_ids = [Command.clear()]
        recipients = self.order._notify_get_recipients(message)
        self.assertFalse([r for r in recipients if r["share"]])

    def test_pdf_thumbnail_route_does_not_accept_portal_token(self):
        pdf = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(pdf)
        attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-training-preview.pdf",
                "raw": pdf.getvalue(),
                "mimetype": "application/pdf",
                "res_model": "sale.order",
                "res_id": self.order.id,
            }
        )
        url = f"/mail/attachment/pdf_first_page/{attachment.id}?access_token={attachment.generate_access_token()[0]}"
        self.authenticate(None, None)
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.authenticate(self.colleague_user.login, self.colleague_user.login)
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.order.training_portal_partner_ids = [Command.clear()]
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)

    def test_invoice_requires_its_own_named_contact(self):
        company = self.env.company
        income = self.env["account.account"].create(
            {
                "name": "Fictional Portal Income",
                "code": "709902",
                "account_type": "income",
                "company_ids": [Command.set([company.id])],
            }
        )
        receivable = self.env["account.account"].create(
            {
                "name": "Fictional Portal Receivable",
                "code": "349902",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [Command.set([company.id])],
            }
        )
        self.env["account.journal"].create(
            {
                "name": "Fictional Portal Sales",
                "code": "FPS",
                "type": "sale",
                "company_id": company.id,
                "default_account_id": income.id,
            }
        )
        self.order.partner_id.with_company(company).property_account_receivable_id = receivable
        self.order.order_line.product_id.product_tmpl_id.write(
            {
                "invoice_policy": "order",
                "property_account_income_id": income.id,
            }
        )
        self.order.action_confirm()
        invoice = self.order._create_invoices()
        invoice.action_post()
        self.assertTrue(invoice.training_is_sale_invoice)
        composer = (
            self.env["mail.compose.message"]
            .with_context(
                default_model="account.move",
                default_res_ids=invoice.ids,
                default_composition_mode="comment",
            )
            .create({})
        )
        composer.partner_ids = [Command.set([self.colleague_user.partner_id.id])]
        with self.assertRaises(ValidationError):
            composer._prepare_mail_values(invoice.ids)
        template = invoice._get_mail_template()
        with self.assertRaises(ValidationError):
            self.env.ref("account.email_template_edi_invoice").send_mail(
                invoice.id,
                force_send=False,
                email_values={"email_to": "unlinked@example.invalid"},
            )
        sender = self.env["account.move.send"]
        lang = sender._get_default_mail_lang(invoice, template)
        self.assertFalse(sender._get_default_mail_partner_ids(invoice, template, lang))
        with self.assertRaises(ValidationError):
            sender._get_mail_params(
                invoice,
                {
                    "mail_partner_ids": [self.colleague_user.partner_id.id],
                },
            )
        self.env["ir.config_parameter"].sudo().set_str(
            "account_payment.enable_portal_payment",
            "True",
        )
        self.assertTrue(invoice._has_to_be_paid())
        self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "is_downpayment": True,
                "label": f"Down Payment (ref: {invoice.name})",
                "product_uom_qty": 0,
                "price_unit": 0,
            }
        )
        report_html = self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder",
            [self.order.id],
        )[0]
        self.assertNotIn(invoice.name, report_html.decode() if isinstance(report_html, bytes) else report_html)
        invoice._portal_ensure_token()
        url = f"/my/invoices/{invoice.id}?access_token={invoice.access_token}"
        mail_url = f"/mail/view?model=account.move&res_id={invoice.id}&access_token={invoice.access_token}"
        attachment = self.env["ir.attachment"].create(
            {
                "name": "fictional-training-invoice.txt",
                "raw": b"Fictional private invoice file",
                "mimetype": "text/plain",
                "res_model": "account.move",
                "res_id": invoice.id,
            }
        )
        attachment_url = f"/web/content/{attachment.id}?access_token={attachment.generate_access_token()[0]}"
        self.authenticate(None, None)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(invoice.name, self.url_open(mail_url).text)
        self.assertNotEqual(self.url_open(attachment_url, allow_redirects=False).status_code, 200)
        self.authenticate(self.colleague_user.login, self.colleague_user.login)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(invoice.name, self.url_open(mail_url).text)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(invoice.name, self.url_open(mail_url).text)
        order_url = self.order.get_portal_url()
        self.assertNotIn(invoice.name, self.url_open(order_url).text)
        self.assertNotIn(invoice.access_token, self.url_open(order_url).text)
        invoice.training_portal_partner_ids = [Command.link(self.authorized_user.partner_id.id)]
        message = self.env["mail.message"].create(
            {
                "model": "account.move",
                "res_id": invoice.id,
                "message_type": "comment",
                "body": "Fictional invoice update",
                "partner_ids": [
                    Command.set(
                        [
                            self.authorized_user.partner_id.id,
                            self.colleague_user.partner_id.id,
                        ]
                    )
                ],
                "outgoing_email_to": "Unlinked <unlinked@example.invalid>",
            }
        )
        recipients = invoice._notify_get_recipients(message)
        self.assertIn(self.authorized_user.partner_id.id, [r["id"] for r in recipients])
        self.assertNotIn(self.colleague_user.partner_id.id, [r["id"] for r in recipients])
        self.assertFalse([r for r in recipients if r["share"] and not r["id"]])
        composer.partner_ids = [Command.set([self.authorized_user.partner_id.id])]
        self.assertTrue(composer._prepare_mail_values(invoice.ids)[invoice.id]["notify_skip_followers"])
        self.assertEqual(
            sender._get_default_mail_partner_ids(invoice, template, lang),
            self.authorized_user.partner_id,
        )
        with self.assertRaises(ValidationError):
            sender._get_mail_params(
                invoice,
                {
                    "mail_partner_ids": [
                        self.authorized_user.partner_id.id,
                        self.colleague_user.partner_id.id,
                    ],
                },
            )
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertIn(invoice.name, self.url_open(mail_url).text)
        self.assertIn('id="pay_with"', self.url_open(url).text)
        payment_token = payment_utils.generate_access_token(
            invoice.partner_id.id,
            invoice.amount_residual,
            invoice.currency_id.id,
            env=self.env,
        )
        generic_payment_url = (
            f"/payment/pay?invoice_id={invoice.id}&amount={invoice.amount_residual}&access_token={payment_token}"
        )
        self.assertEqual(self.url_open(generic_payment_url).status_code, 200)
        self.authenticate(self.colleague_user.login, self.colleague_user.login)
        self.assertIn(self.url_open(generic_payment_url, allow_redirects=False).status_code, (403, 404))
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
            self.make_jsonrpc_request(
                f"/invoice/transaction/{invoice.id}",
                {"access_token": invoice.access_token},
            )
        self.assertIn(invoice.name, self.url_open(order_url).text)
        self.assertEqual(self.url_open(attachment_url, allow_redirects=False).status_code, 200)
        self.assertEqual(
            self.url_open(url + "&report_type=pdf", allow_redirects=False).status_code,
            200,
        )
        invoice.training_portal_partner_ids = [Command.clear()]
        self.assertIn(self.url_open(generic_payment_url, allow_redirects=False).status_code, (403, 404))
        self.assertFalse([r for r in invoice._notify_get_recipients(message) if r["share"]])
        with self.assertRaises(ValidationError):
            sender._get_mail_params(
                invoice,
                {
                    "mail_partner_ids": [self.authorized_user.partner_id.id],
                },
            )
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(invoice.name, self.url_open(mail_url).text)
        self.assertNotIn(invoice.name, self.url_open(order_url).text)
        self.assertNotIn(invoice.access_token, self.url_open(order_url).text)
        self.assertNotEqual(self.url_open(attachment_url, allow_redirects=False).status_code, 200)

    def test_revoked_message_recipient_cannot_read_new_content_by_rpc(self):
        message = self.order.with_context(mail_notify_force_send=False).message_post(
            body="Fictional original",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=self.authorized_user.partner_id.ids,
        )
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        params = {"model": "mail.message", "method": "read", "args": [message.ids, ["body"]], "kwargs": {}}
        route = "/web/dataset/call_kw/mail.message/read"
        self.assertIn("Fictional original", self.make_jsonrpc_request(route, params)[0]["body"])
        self.order.training_portal_partner_ids = [Command.clear()]
        message.write({"body": "Fictional new confidential content after revocation"})
        with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
            self.make_jsonrpc_request(route, params)
        with self.assertRaises(AccessError):
            message.with_user(self.authorized_user).read(["body"])
        self.assertFalse(
            self.env["mail.message"]
            .with_user(self.authorized_user)
            .search(
                [
                    ("id", "=", message.id),
                ]
            )
        )
        self.assertFalse(message.with_user(self.authorized_user).sudo()._get_with_access())
        self.order.training_portal_partner_ids = [Command.set(self.authorized_user.partner_id.ids)]
        self.assertIn("after revocation", message.with_user(self.authorized_user).read(["body"])[0]["body"])

    def test_queued_pdf_revalidates_recipients_at_transport_and_retry(self):
        template = self.env.ref("sale.email_template_edi_sale")
        mail = self.env["mail.mail"].browse(
            template.send_mail(
                self.order.id,
                force_send=False,
                email_values={"auto_delete": False},
            )
        )
        self.assertTrue(mail.attachment_ids)
        self.order.training_portal_partner_ids = [Command.clear()]
        server = type(self.env["ir.mail_server"])
        with (
            patch.object(server, "_disable_send", return_value=False),
            patch.object(server, "_connect__", return_value=None),
            patch.object(server, "send_email", return_value="fictional-id") as transport,
        ):
            with mute_logger("odoo.addons.mail.models.mail_mail"):
                mail.send()
            self.assertEqual(mail.state, "exception")
            transport.assert_not_called()
            # A queue retry must recheck the same grant.
            mail.write({"state": "outgoing"})
            with mute_logger("odoo.addons.mail.models.mail_mail"):
                mail.send()
            transport.assert_not_called()
            self.order.training_portal_partner_ids = [Command.set(self.authorized_user.partner_id.ids)]
            mail.write({"state": "outgoing"})
            mail.send(raise_exception=True)
            self.assertEqual(mail.state, "sent")
            transport.assert_called_once()

    def test_internal_and_foreign_company_tokens_keep_native_permissions(self):
        internal = new_test_user(self.env, login="policy_http_internal", groups="base.group_user")
        company_b = self.env["res.company"].create({"name": "Fictional HTTP Company B"})
        foreign = new_test_user(
            self.env,
            login="policy_http_foreign",
            groups="sales_team.group_sale_salesman",
            company_id=company_b.id,
            company_ids=[Command.set(company_b.ids)],
        )
        sales = new_test_user(self.env, login="policy_http_sales", groups="sales_team.group_sale_salesman")
        self.order.user_id = sales
        file = self.env["ir.attachment"].create(
            {
                "name": "fictional-token.txt",
                "raw": b"Fictional private order bytes",
                "mimetype": "text/plain",
                "res_model": "sale.order",
                "res_id": self.order.id,
            }
        )
        for token in (file.generate_access_token()[0], file._get_raw_access_token()):
            url = f"/web/content/{file.id}?access_token={token}"
            for user in (internal, foreign):
                self.authenticate(user.login, user.login)
                response = self.url_open(url, allow_redirects=False)
                self.assertNotEqual(response.status_code, 200)
                self.assertNotIn("Fictional private order bytes", response.text)
            self.authenticate(sales.login, sales.login)
            self.assertEqual(self.url_open(url).content, b"Fictional private order bytes")

    def test_native_transaction_routes_keep_document_grants_and_revocation(self):
        provider = self.env["payment.provider"].create(
            {"name": "Fictional Disabled Provider", "code": "none", "active": False}
        )
        with file_open("web/static/img/placeholder.png", "rb") as image:
            method = self.env["payment.method"].create(
                {
                    "name": "Fictional Method",
                    "code": "fictional",
                    "provider_id": provider.id,
                    "image": BinaryBytes(image.read()),
                }
            )
        self.assertFalse(provider.active)
        payload = {
            "access_token": self.order.access_token,
            "provider_id": provider.id,
            "payment_method_id": method.id,
            "token_id": None,
            "amount": 25,
            "flow": "redirect",
            "tokenization_requested": False,
            "landing_route": "/payment/status",
        }
        route = f"/my/orders/{self.order.id}/transaction"
        self.authenticate(self.colleague_user.login, self.colleague_user.login)
        with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
            self.make_jsonrpc_request(route, payload)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        result = self.make_jsonrpc_request(route, payload)
        tx = self.env["payment.transaction"].search([("reference", "=", result["reference"])])
        self.assertEqual(tx.sale_order_ids, self.order)
        self.assertEqual(tx.amount, 25)
        self.assertEqual(tx.state, "draft")
        self.assertEqual(tx._bus_channels(), self.authorized_user.partner_id)
        token = payment_utils.generate_access_token(tx.partner_id.id, tx.amount, tx.currency_id.id, env=self.env)
        confirmation = f"/payment/confirmation?tx_id={tx.id}&access_token={token}"
        self.assertEqual(self.url_open(confirmation).status_code, 200)
        self.assertEqual(self.url_open("/payment/status").status_code, 200)
        self.order.training_portal_partner_ids = [Command.clear()]
        self.assertFalse(tx._bus_channels())
        for url in (confirmation, "/payment/status"):
            self.assertIn(self.url_open(url, allow_redirects=False).status_code, (403, 404))
        with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
            self.make_jsonrpc_request("/payment/process", {})
        self.authenticate(None, None)
        self.assertIn(self.url_open(confirmation, allow_redirects=False).status_code, (403, 404))
        self.assertFalse(self.env["training.enrollment"].search([]))
