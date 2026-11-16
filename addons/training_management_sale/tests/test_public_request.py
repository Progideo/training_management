from io import BytesIO
from uuid import uuid4

from lxml import html
from werkzeug.datastructures import FileStorage

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.training_management.tests.test_catalogue import CatalogueCase


@tagged("post_install", "-at_install")
class TestPublicRequest(CatalogueCase, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.EUR").active = True
        cls.salesperson = new_test_user(
            cls.env,
            login="p02_sales",
            groups="sales_team.group_sale_salesman",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )

    def published(self):
        program = self.new_program(public_catalogue=True)
        program.action_validate()
        program.action_publish()
        return program

    def request_values(self, **updates):
        return {
            "contact": "Fictional Requester",
            "email": "requester@example.invalid",
            "organisation": "Fictional Client",
            "kind": "group",
            "request_type": "custom",
            "program": "",
            "objectives": "Apply a method",
            "level": "Beginner",
            "count": "4",
            "country": str(self.env.ref("base.ma").id),
            "mode": "remote",
            "currency": "EUR",
            "date_from": "",
            "date_to": "",
            "dates_flexible": "1",
            **updates,
        }

    def test_intake_uses_crm_acknowledgement_and_private_native_attachment(self):
        program = self.published()
        values = self.request_values(
            program=str(program.id), request_type="adaptation", tools="Video conference", advice="1"
        )
        key = uuid4().hex
        pdf = b"%PDF-1.4\nFictional private specification\n%%EOF"

        def upload():
            return FileStorage(stream=BytesIO(pdf), filename="specification.pdf", content_type="application/pdf")

        lead = self.env["crm.lead"]._submit_public_request(self.company, values, key, upload())
        same = self.env["crm.lead"]._submit_public_request(self.company, values, key, upload())
        self.assertEqual(lead, same)
        self.assertEqual(lead.training_program_id, program)
        self.assertEqual(lead.training_requested_currency_id.name, "EUR")
        self.assertEqual(lead.training_attendee_count, 4)
        self.assertTrue(lead.training_advice_requested)
        notice = self.env["training.request.notice"].search([("lead_id", "=", lead.id)])
        self.assertEqual(len(notice), 1)
        self.assertTrue(notice.mail_id)
        attachment = self.env["ir.attachment"].search([("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)])
        self.assertEqual(len(attachment), 1)
        self.assertFalse(attachment.public)
        self.assertFalse(attachment.access_token)
        self.assertEqual(attachment.with_user(self.salesperson)._to_http_stream().read(), pdf)
        self.assertFalse(self.env["sale.order"].search([("opportunity_id", "=", lead.id)]))
        self.assertFalse(self.env["training.enrollment"].search([]))
        for user in (self.portal, self.env.ref("base.public_user"), self.reader):
            with self.assertRaises(AccessError):
                attachment.with_user(user)._to_http_stream()
        with self.assertRaises(ValidationError):
            self.env["crm.lead"]._submit_public_request(self.company, self.request_values(count="7"), key)
        with self.assertRaises(AccessError):
            attachment.write({"public": True})
        with self.assertRaises(AccessError):
            attachment.copy({"res_model": "res.partner", "res_id": self.contact.id})
        # A legacy native token must not bypass the lead's current ACL.
        self.env.cr.execute("UPDATE ir_attachment SET access_token='legacy-p02' WHERE id=%s", [attachment.id])
        attachment.invalidate_recordset()
        self.authenticate(None, None)
        self.assertIn(self.url_open(f"/web/content/{attachment.id}?access_token=legacy-p02").status_code, (403, 404))
        image = self.url_open(f"/web/image/{attachment.id}?access_token=legacy-p02")
        self.assertNotEqual(image.content, pdf)
        if image.status_code == 200:
            self.assertTrue(image.headers["Content-Type"].startswith("image/"), "Native placeholder only")
        else:
            self.assertIn(image.status_code, (403, 404))

    def test_catalogue_pager_preserves_legacy_quote_context(self):
        courses = self.env["training.course"].create(
            [
                {"name": f"Fictional quote pagination {number:02d}", "company_id": self.company.id, "public_catalogue": True}
                for number in range(13)
            ]
        )
        self.authenticate(None, None)
        root = html.fromstring(self.url_open("/formations?kind=individual&search=Fictional+quote+pagination").content)
        next_link = root.xpath("//nav//a[starts-with(@href, '/formations/page/2?')]/@href")[0]
        second = html.fromstring(self.url_open(next_link).content)
        self.assertEqual(second.xpath("//input[@name='kind']/@value"), ["individual"])
        self.assertEqual(second.xpath("//article//h2/a/@href"), [f"/formations/catalogue/{courses[-1].id}?kind=individual"])

    def test_http_journeys_preserve_context_and_validation_and_repetition(self):
        program = self.published()
        self.authenticate(None, None)
        page = self.url_open(f"/formations/{program.id}")
        self.assertIn("Demander un devis pour mon équipe", page.text)
        self.assertIn("Demander un devis individuel", page.text)
        self.assertIn(f"kind=group&amp;program={program.id}", page.text)
        self.assertIn(f"kind=individual&amp;program={program.id}", page.text)
        public_catalogue = self.url_open("/formations")
        self.assertNotIn('href="/formations?kind=group"', public_catalogue.text)
        self.assertNotIn('href="/formations?kind=individual"', public_catalogue.text)
        self.assertIn("Vous ne trouvez pas la formation qui vous convient ?", public_catalogue.text)
        self.assertIn("Décrire un projet sur mesure", public_catalogue.text)
        self.assertIn('href="/formations/demande?kind=group&amp;request_type=custom"', public_catalogue.text)
        catalogue = self.url_open("/formations?kind=group")
        self.assertIn(f"/formations/{program.id}?kind=group", catalogue.text)
        self.assertNotIn("Changer de parcours", catalogue.text)
        selected = self.url_open(f"/formations/{program.id}?kind=group")
        self.assertIn(f"kind=group&amp;program={program.id}", selected.text)
        self.assertNotIn(f"kind=individual&amp;program={program.id}", selected.text)
        self.assertIn("Demander un devis pour mon équipe", selected.text)
        individual = self.url_open("/formations?kind=individual")
        self.assertNotIn("Changer de parcours", individual.text)
        self.assertIn(f"/formations/{program.id}?kind=individual", individual.text)
        individual_form = html.fromstring(individual.content)
        self.assertEqual(individual_form.xpath("//input[@name='kind']/@value"), ["individual"])
        general_page = self.url_open(f"/formations/catalogue/{program.course_id.id}?kind=individual")
        self.assertEqual(general_page.status_code, 200)
        self.assertIn(f"/formations/{program.id}?kind=individual", general_page.text)
        self.assertIn("/formations?kind=individual", general_page.text)
        individual_detail = self.url_open(f"/formations/{program.id}?kind=individual")
        self.assertIn("Demander un devis individuel", individual_detail.text)
        self.assertNotIn("Demander un devis pour mon équipe", individual_detail.text)
        page = self.url_open(f"/formations/demande?kind=group&program={program.id}")
        self.assertEqual(page.status_code, 200)
        form = html.fromstring(page.content)
        self.assertEqual(form.xpath("//select[@id='kind']/option/@value"), ["group", "individual"])
        payload = {
            "csrf_token": form.xpath("//input[@name='csrf_token']/@value")[0],
            "submission_token": form.xpath("//input[@name='submission_token']/@value")[0],
            **self.request_values(program=str(program.id), request_type="catalogue"),
        }
        response = self.url_open("/formations/demande", data={**payload, "objectives": ""})
        self.assertIn('role="alert"', response.text)
        self.assertIn("Fictional Requester", response.text)
        response = self.url_open("/formations/demande", data={**payload, "kind": "individual", "count": "1"})
        self.assertIn("Demande reçue", response.text)
        self.assertEqual(
            self.url_open("/formations/demande", data={**payload, "kind": "individual", "count": "1"}).status_code, 200
        )
        leads = self.env["crm.lead"].search([("training_submission_key", "=", payload["submission_token"])])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads.training_request_kind, "individual")
        self.assertEqual(
            self.url_open("/formations/demande", data={**payload, "submission_token": "forged"}).status_code, 404
        )

    def test_server_rejects_missing_foreign_or_invalid_values_and_upload(self):
        cases = [
            {"objectives": ""},
            {"count": "0"},
            {"currency": "XXX"},
            {"country": "0"},
            {"date_from": "2026-12-01", "date_to": "2026-11-01"},
            {"mode": "invalid"},
            {"program": "2147483647", "request_type": "catalogue"},
            {"email": "invalid"},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.env["crm.lead"]._submit_public_request(self.company, self.request_values(**values), uuid4().hex)
        for filename, data in (("bad.pdf", b"not pdf"), ("bad.html", b"%PDF-")):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.env["crm.lead"]._submit_public_request(
                    self.company,
                    self.request_values(),
                    uuid4().hex,
                    FileStorage(stream=BytesIO(data), filename=filename),
                )

    def test_hourly_limits_bound_leads_acknowledgements_and_files(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_str("training_request.max_per_email_hour", "2")
        params.set_str("training_request.max_per_hour", "3")
        params.set_str("training_request.max_upload_mb_hour", "1")
        Lead = self.env["crm.lead"]
        company = self.company
        for index in range(2):
            Lead._submit_public_request(company, self.request_values(contact=f"Fictional {index}"), f"limit-{index}")
        # Replaying a recorded form stays idempotent at the limit.
        replay = Lead._submit_public_request(company, self.request_values(contact="Fictional 1"), "limit-1")
        self.assertTrue(replay)
        with self.assertRaises(ValidationError):
            Lead._submit_public_request(company, self.request_values(), "limit-email")
        other = self.request_values(email="other@example.invalid")
        Lead._submit_public_request(company, other, "limit-other")
        with self.assertRaises(ValidationError):
            Lead._submit_public_request(company, self.request_values(email="third@example.invalid"), "limit-all")
        self.assertEqual(
            self.env["training.request.notice"].sudo().search_count([("email", "=", "requester@example.invalid")]), 2
        )
        params.set_str("training_request.max_per_hour", "100")
        pdf = FileStorage(BytesIO(b"%PDF-1.4\n" + b"0" * 700000), filename="s.pdf")
        Lead._submit_public_request(company, self.request_values(email="file1@example.invalid"), "limit-file-1", pdf)
        big = FileStorage(BytesIO(b"%PDF-1.4\n" + b"1" * 700000), filename="s.pdf")
        with self.assertRaises(ValidationError):
            Lead._submit_public_request(
                company, self.request_values(email="file2@example.invalid"), "limit-file-2", big
            )

    def test_public_request_offers_and_accepts_any_active_currency(self):
        gbp = self.env.ref("base.GBP")
        gbp.active = True
        self.authenticate(None, None)
        page = self.url_open("/formations/demande")
        self.assertIn('value="GBP"', page.text)
        lead = self.env["crm.lead"]._submit_public_request(
            self.company,
            self.request_values(currency="GBP"),
            uuid4().hex,
        )
        self.assertEqual(lead.training_requested_currency_id, gbp)
        gbp.active = False
        with self.assertRaises(ValidationError):
            self.env["crm.lead"]._submit_public_request(
                self.company,
                self.request_values(currency="GBP"),
                uuid4().hex,
            )
