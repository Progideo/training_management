from io import BytesIO

from pypdf import PdfWriter

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, JsonRpcException, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestTrainingPortalHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        partner = cls.env["res.partner"].create({
            "name": "Fictional Portal Buyer", "email": "buyer@example.invalid",
        })
        authorized = cls.env["res.partner"].create({
            "name": "Fictional Authorized Contact", "parent_id": partner.id,
            "email": "authorized@example.invalid",
        })
        colleague = cls.env["res.partner"].create({
            "name": "Fictional Unauthorised Colleague", "parent_id": partner.id,
            "email": "colleague@example.invalid",
        })
        cls.authorized_user = new_test_user(
            cls.env, login="training_http_authorized", groups="base.group_portal",
            partner_id=authorized.id,
        )
        cls.colleague_user = new_test_user(
            cls.env, login="training_http_colleague", groups="base.group_portal",
            partner_id=colleague.id,
        )
        authorized.email = "authorized@example.invalid"
        colleague.email = "colleague@example.invalid"
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
            "training_portal_partner_ids": [Command.link(authorized.id)],
        })
        cls.env["sale.order.line"].create({
            "order_id": cls.order.id, "product_id": product.id,
            "product_uom_qty": 1, "training_program_id": program.id,
        })
        cls.order._portal_ensure_token()

    def test_quotation_pdf_mail_requires_named_recipient(self):
        authorized = self.authorized_user.partner_id
        colleague = self.colleague_user.partner_id
        with self.assertRaises(ValidationError):
            self.env.ref("sale.email_template_edi_sale").send_mail(
                self.order.id, force_send=False,
                email_values={"email_to": "unlinked@example.invalid"},
            )
        defaults = self.order._message_get_default_recipients()[self.order.id]
        self.assertEqual(defaults["partner_ids"], authorized.ids)
        self.assertFalse(defaults["email_to"])
        action = self.order.action_quotation_send()
        composer = self.env["mail.compose.message"].with_context(action["context"]).create({})
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

    def test_portal_does_not_offer_payment_or_create_transaction(self):
        self.assertEqual(self.order.amount_total, 100)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
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

    def test_named_contact_required_even_with_a_valid_token(self):
        url = f"/my/orders/{self.order.id}?access_token={self.order.access_token}"
        mail_url = (
            f"/mail/view?model=sale.order&res_id={self.order.id}"
            f"&access_token={self.order.access_token}"
        )
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
        attachment = self.env["ir.attachment"].create({
            "name": "fictional-training-order.txt", "raw": b"Fictional private order file",
            "mimetype": "text/plain", "res_model": "sale.order", "res_id": self.order.id,
        })
        url = f"/web/content/{attachment.id}?access_token={attachment.generate_access_token()[0]}"
        with self.assertRaises(AccessError):
            self.env["ir.binary"].with_user(self.colleague_user)._get_stream_from(
                attachment.sudo(),
            )
        self.authenticate(None, None)
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.authenticate(self.authorized_user.login, self.authorized_user.login)
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertTrue(self.env["ir.binary"].with_user(self.authorized_user)._get_stream_from(
            attachment.sudo(),
        ))
        self.order.training_portal_partner_ids = [Command.clear()]
        self.assertNotEqual(self.url_open(url, allow_redirects=False).status_code, 200)

    def test_message_attachment_follows_document_grant(self):
        message = self.env["mail.message"].create({
            "model": "sale.order", "res_id": self.order.id,
            "message_type": "comment", "body": "Fictional private training note",
        })
        attachment = self.env["ir.attachment"].create({
            "name": "fictional-message-file.txt", "raw": b"Fictional message attachment",
            "mimetype": "text/plain", "res_model": "mail.message", "res_id": message.id,
        })
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
        message = self.env["mail.message"].create({
            "model": "sale.order", "res_id": self.order.id,
            "message_type": "comment", "body": "Fictional training update",
            "partner_ids": [Command.set([
                self.authorized_user.partner_id.id,
                self.colleague_user.partner_id.id,
            ])],
            "outgoing_email_to": "Unlinked <unlinked@example.invalid>",
        })
        recipients = self.order._notify_get_recipients(message)
        self.assertIn(self.authorized_user.partner_id.id, [r["id"] for r in recipients])
        self.assertNotIn(self.colleague_user.partner_id.id, [r["id"] for r in recipients])
        self.assertFalse([r for r in recipients if r["share"] and not r["id"]])
        self.order.message_subscribe(partner_ids=[
            self.authorized_user.partner_id.id,
            self.colleague_user.partner_id.id,
        ])
        follower_message = self.env["mail.message"].create({
            "model": "sale.order", "res_id": self.order.id,
            "message_type": "comment", "body": "Fictional follower update",
            "subtype_id": self.env.ref("mail.mt_comment").id,
        })
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
        attachment = self.env["ir.attachment"].create({
            "name": "fictional-training-preview.pdf", "raw": pdf.getvalue(),
            "mimetype": "application/pdf", "res_model": "sale.order",
            "res_id": self.order.id,
        })
        url = (
            f"/mail/attachment/pdf_first_page/{attachment.id}"
            f"?access_token={attachment.generate_access_token()[0]}"
        )
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
        income = self.env["account.account"].create({
            "name": "Fictional Portal Income", "code": "709902",
            "account_type": "income", "company_ids": [Command.set([company.id])],
        })
        receivable = self.env["account.account"].create({
            "name": "Fictional Portal Receivable", "code": "349902",
            "account_type": "asset_receivable", "reconcile": True,
            "company_ids": [Command.set([company.id])],
        })
        self.env["account.journal"].create({
            "name": "Fictional Portal Sales", "code": "FPS", "type": "sale",
            "company_id": company.id, "default_account_id": income.id,
        })
        self.order.partner_id.with_company(company).property_account_receivable_id = receivable
        self.order.order_line.product_id.product_tmpl_id.write({
            "invoice_policy": "order", "property_account_income_id": income.id,
        })
        self.order.action_confirm()
        invoice = self.order._create_invoices()
        invoice.action_post()
        self.assertTrue(invoice.training_is_sale_invoice)
        composer = self.env["mail.compose.message"].with_context(
            default_model="account.move", default_res_ids=invoice.ids,
            default_composition_mode="comment",
        ).create({})
        composer.partner_ids = [Command.set([self.colleague_user.partner_id.id])]
        with self.assertRaises(ValidationError):
            composer._prepare_mail_values(invoice.ids)
        template = invoice._get_mail_template()
        with self.assertRaises(ValidationError):
            self.env.ref("account.email_template_edi_invoice").send_mail(
                invoice.id, force_send=False,
                email_values={"email_to": "unlinked@example.invalid"},
            )
        sender = self.env["account.move.send"]
        lang = sender._get_default_mail_lang(invoice, template)
        self.assertFalse(sender._get_default_mail_partner_ids(invoice, template, lang))
        with self.assertRaises(ValidationError):
            sender._get_mail_params(invoice, {
                "mail_partner_ids": [self.colleague_user.partner_id.id],
            })
        self.env["ir.config_parameter"].sudo().set_str(
            "account_payment.enable_portal_payment", "True",
        )
        self.assertFalse(invoice._has_to_be_paid())
        self.env["sale.order.line"].create({
            "order_id": self.order.id, "is_downpayment": True,
            "label": f"Down Payment (ref: {invoice.name})",
            "product_uom_qty": 0, "price_unit": 0,
        })
        report_html = self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder", [self.order.id],
        )[0]
        self.assertNotIn(invoice.name, report_html.decode() if isinstance(report_html, bytes) else report_html)
        invoice._portal_ensure_token()
        url = f"/my/invoices/{invoice.id}?access_token={invoice.access_token}"
        mail_url = (
            f"/mail/view?model=account.move&res_id={invoice.id}"
            f"&access_token={invoice.access_token}"
        )
        attachment = self.env["ir.attachment"].create({
            "name": "fictional-training-invoice.txt", "raw": b"Fictional private invoice file",
            "mimetype": "text/plain", "res_model": "account.move", "res_id": invoice.id,
        })
        attachment_url = (
            f"/web/content/{attachment.id}?access_token={attachment.generate_access_token()[0]}"
        )
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
        message = self.env["mail.message"].create({
            "model": "account.move", "res_id": invoice.id,
            "message_type": "comment", "body": "Fictional invoice update",
            "partner_ids": [Command.set([
                self.authorized_user.partner_id.id,
                self.colleague_user.partner_id.id,
            ])],
            "outgoing_email_to": "Unlinked <unlinked@example.invalid>",
        })
        recipients = invoice._notify_get_recipients(message)
        self.assertIn(self.authorized_user.partner_id.id, [r["id"] for r in recipients])
        self.assertNotIn(self.colleague_user.partner_id.id, [r["id"] for r in recipients])
        self.assertFalse([r for r in recipients if r["share"] and not r["id"]])
        composer.partner_ids = [Command.set([self.authorized_user.partner_id.id])]
        self.assertTrue(
            composer._prepare_mail_values(invoice.ids)[invoice.id]["notify_skip_followers"]
        )
        self.assertEqual(
            sender._get_default_mail_partner_ids(invoice, template, lang),
            self.authorized_user.partner_id,
        )
        with self.assertRaises(ValidationError):
            sender._get_mail_params(invoice, {
                "mail_partner_ids": [
                    self.authorized_user.partner_id.id,
                    self.colleague_user.partner_id.id,
                ],
            })
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 200)
        self.assertIn(invoice.name, self.url_open(mail_url).text)
        self.assertNotIn("Pay Now", self.url_open(url).text)
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
        self.assertFalse([
            r for r in invoice._notify_get_recipients(message) if r["share"]
        ])
        with self.assertRaises(ValidationError):
            sender._get_mail_params(invoice, {
                "mail_partner_ids": [self.authorized_user.partner_id.id],
            })
        self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 303)
        self.assertNotIn(invoice.name, self.url_open(mail_url).text)
        self.assertNotIn(invoice.name, self.url_open(order_url).text)
        self.assertNotIn(invoice.access_token, self.url_open(order_url).text)
        self.assertNotEqual(self.url_open(attachment_url, allow_redirects=False).status_code, 200)
