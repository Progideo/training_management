import io
import json
from unittest.mock import patch
from urllib.parse import urlsplit

from lxml import html

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.pdf import PdfFileReader

from .test_catalogue import CatalogueCase


def priced_autonomy(env, amount=990.0):
    """Public autonomous price, as projected by the application selling the eLearning offer."""
    course_class = type(env["training.course"])
    facts = course_class._catalogue_facts

    def priced(records, company):
        rows = facts(records, company)
        for row in rows.values():
            if row.get("elearning"):
                row["autonomous"] = {**(row.get("autonomous") or {}), "price": {"amount": amount, "label": "990"}}
        return rows

    return patch.object(course_class, "_catalogue_facts", priced)


@tagged("post_install", "-at_install")
class TestPublicCatalogue(CatalogueCase, HttpCase):
    def test_public_version_pdf_demo_and_private_boundaries(self):
        program = self.new_program(
            public_catalogue=True,
            expected_outcomes="Produce an action plan",
            official_exam_details="Not included",
            content='<h3 onclick="pr84_unsafe()">Public chapter</h3><ul><li>Topic<ul><li>Public detail</li></ul></li></ul><script>pr84_unsafe()</script>',
        )
        question = (
            self.env["training.preview.question"]
            .with_user(self.coordinator)
            .create(
                {
                    "program_id": program.id,
                    "name": "Public example?",
                    "choice_a": "Yes",
                    "choice_b": "No",
                    "correct_choice": "a",
                    "explanation": "Public explanation",
                }
            )
        )
        program.write(
            {"preview_pdf": BinaryBytes(b"%PDF-1.4\nfictional public extract"), "preview_filename": "extract.pdf"}
        )
        # Both fields must be written together in the real form.
        program.action_validate()
        raw = bytes(program.pdf_attachment_id.raw)
        program.action_publish()
        private = self.new_program(version="PRIVATE", title="Private unpublished programme")
        self.authenticate(None, None)
        response = self.url_open("/formations")
        self.assertEqual(response.status_code, 200)
        self.assertIn(program.title, response.text)
        self.assertNotIn(private.title, response.text)
        response = self.url_open(f"/formations/{program.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Produce an action plan", response.text)
        self.assertIn("Not included", response.text)
        for value in ("Public chapter", "Public detail", "pr84_unsafe", "Public example?", "Public explanation"):
            self.assertNotIn(value, response.text)
        self.assertIn(f"/formations/{program.id}/pdf", response.text)
        general = self.url_open(f"/formations/catalogue/{program.course_id.id}")
        self.assertEqual(general.status_code, 200)
        self.assertIn("Produce an action plan", general.text)
        self.assertNotIn("Public detail", general.text)
        hidden_search = self.url_open("/formations?search=Public%20detail")
        self.assertNotIn(program.title, hidden_search.text)
        token = self.csrf_token()
        response = self.url_open(f"/formations/{program.id}", data={"csrf_token": token, str(question.id): "a"})
        self.assertIn(response.status_code, (400, 403, 404, 405))
        self.assertNotIn("Public explanation", response.text)
        # The programme is public: its frozen reference PDF is served as stored.
        public_pdf = self.url_open(f"/formations/{program.id}/pdf")
        self.assertEqual(public_pdf.status_code, 200)
        self.assertEqual(public_pdf.content, raw)
        self.assertEqual(public_pdf.headers["Content-Type"], "application/pdf")
        self.assertEqual(self.url_open(f"/formations/{program.id}/apercu.pdf").status_code, 404)
        self.assertEqual(bytes(program.pdf_attachment_id.raw), raw)
        self.assertIn(
            "Produce an action plan", "\n".join(p.extract_text() for p in PdfFileReader(io.BytesIO(raw)).pages)
        )
        for url in (
            f"/formations/{private.id}",
            f"/formations/{private.id}/pdf",
            f"/web/content/{program.pdf_attachment_id.id}",
            f"/web/content/training.program.version/{program.id}/preview_pdf",
        ):
            self.assertIn(self.url_open(url).status_code, (403, 404))
        with self.assertRaises(AccessError):
            question.with_user(self.portal).read(["explanation"])
        with self.assertRaises(ValidationError):
            question.write({"explanation": "Changed"})
        with self.assertRaises(ValidationError):
            program.write({"included_services": "Changed"})
        program.action_retire()
        self.assertEqual(self.url_open(f"/formations/{program.id}/pdf").status_code, 404)

    def test_extract_validation_and_cross_company_publication(self):
        program = self.new_program()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            program.write({"preview_pdf": BinaryBytes(b"not pdf"), "preview_filename": "bad.pdf"})
        other = self.env["training.program.version"].create(
            {
                **self.values,
                "course_id": self.other_course.id,
                "public_catalogue": True,
                "accessibility_contact_id": self.env["res.partner"].create({"name": "Other desk"}).id,
            }
        )
        self.other_course.category_id = self.env["training.category"].create(
            {"name": "Other", "company_id": self.other_company.id}
        )
        other.action_validate()
        other.action_publish()
        self.authenticate(None, None)
        self.assertEqual(self.url_open(f"/formations/{other.id}").status_code, 404)

    def test_catalogue_uses_current_language_without_replacing_contract_pdf(self):
        # Controller projection must honor a language already chosen by native routing,
        # with and without the optional Website addon.
        from types import SimpleNamespace
        from unittest.mock import patch
        from ..controllers import public_catalogue

        self.env["res.lang"]._activate_lang("fr_FR")
        program = self.new_program(public_catalogue=True, title="English catalogue title")
        # Set both stored translations even when the database defaults to French.
        program.update_field_translations(
            "title", {"en_US": "English catalogue title", "fr_FR": "Titre français du catalogue"}
        )
        program.action_validate()
        program.action_publish()
        raw = bytes(program.pdf_attachment_id.raw)
        for language, title in (("en_US", "English catalogue title"), ("fr_FR", "Titre français du catalogue")):
            current = SimpleNamespace(env=self.env(context={**self.env.context, "lang": language}), website=False)
            with patch.object(public_catalogue, "request", current):
                projected = public_catalogue.TrainingPublicCatalogue._program(program.id)
                self.assertEqual(projected.title, title)
                self.assertEqual(bytes(projected.pdf_attachment_id.raw), raw)

    @staticmethod
    def course_schema(root):
        (schema,) = [
            item
            for item in map(json.loads, root.xpath("//script[@type='application/ld+json']/text()"))
            if isinstance(item, dict) and item.get("@type") == "Course"
        ]
        return schema

    def test_catalogue_offers_latest_trainer_led_and_elearning_versions_with_their_modes(self):
        older = self.new_program(public_catalogue=True, version="V1", title="Fictional older on-site version")
        older.action_validate()
        older.action_publish()
        latest = self.new_program(
            public_catalogue=True,
            version="V2",
            title="Fictional on-site or remote version",
            duration_hours=21,
            also_remote=True,
        )
        latest.action_validate()
        latest.action_publish()
        autonomous = self.new_program(
            public_catalogue=True,
            version="V4",
            title="Fictional autonomous version",
            delivery_mode="elearning",
            duration_hours=3.5,
        )
        autonomous.action_validate()
        autonomous.action_publish()
        # A version led by a trainer declares its possible modes, main mode first.
        self.assertEqual(latest._live_modes(), ["onsite", "remote"])
        self.assertEqual(older._live_modes(), ["onsite"])
        self.assertEqual(autonomous._live_modes(), [])
        labels = dict(latest._fields["delivery_mode"]._description_selection(latest.env))
        self.assertIn(labels["onsite"], latest._modes_label())
        self.assertIn(labels["remote"].lower(), latest._modes_label())
        self.assertEqual(older._modes_label(), labels["onsite"])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.new_program(version="V9", delivery_mode="elearning", also_onsite=True)
        offers = {
            offer["title"]: offer
            for offer in self.env["training.course"]._catalogue_offers(self.company)
            if offer["course_id"] == self.course.id
        }
        # The latest version led by a trainer and the latest eLearning version.
        self.assertEqual(set(offers), {latest.title, autonomous.title})
        self.assertEqual(offers[latest.title]["modes"], ["onsite", "remote"])
        self.assertIn("21 h", offers[latest.title]["conditions"])
        self.assertIn(latest._modes_label(), offers[latest.title]["conditions"])
        self.assertNotIn("21.0", offers[latest.title]["conditions"])
        self.assertIn("Prix sur devis", offers[latest.title]["conditions"])
        self.assertNotIn("Prix sur devis", offers[autonomous.title]["conditions"])
        self.assertNotEqual(offers[autonomous.title]["kind"], offers[latest.title]["kind"])
        self.assertEqual(autonomous._public_duration_hours().replace(",", "."), "3.5")
        facts = self.course.sudo()._catalogue_facts(self.company)[self.course.id]
        self.assertEqual((facts["live_modes"], facts["elearning"]), (["onsite", "remote"], True))
        self.authenticate(None, None)
        # Without a public price, the eLearning version is not presented (decision of 21 November 2026).
        bare = html.fromstring(self.url_open(f"/formations/catalogue/{self.course.id}").content)
        self.assertEqual(bare.xpath("//div[@role='tablist']/button/@data-bs-target"), ["#training_booking_intra"])
        self.assertNotIn(self.course.name, self.url_open("/formations?format=autonomous").text)
        priced = priced_autonomy(self.env)
        priced.start()
        self.addCleanup(priced.stop)
        path = "/formations/catalogue/" + self.env["ir.http"]._slug((self.course.id, self.course.name))
        # A version page redirects permanently to its course page; only the latest versions are selected.
        for program, query in ((latest, f"version={latest.id}"), (older, ""), (autonomous, f"version={autonomous.id}")):
            moved = self.url_open(f"/formations/{program.id}", allow_redirects=False)
            self.assertEqual(moved.status_code, 301)
            self.assertEqual(urlsplit(moved.headers["Location"]).path, path)
            self.assertEqual(urlsplit(moved.headers["Location"]).query, query)
        # Both declared modes are found by the catalogue filters.
        for mode in ("onsite", "remote"):
            self.assertIn(self.course.name, self.url_open(f"/formations?mode={mode}").text)
        self.assertIn(self.course.name, self.url_open("/formations?remote=1").text)
        page = self.url_open(f"/formations/{autonomous.id}")
        self.assertEqual(page.status_code, 200)
        if "website" in self.env:
            # The page title comes from the Website layout only.
            title = html.fromstring(page.content).findtext(".//title") or ""
            self.assertIn(self.course.name, title)
            self.assertNotIn("Public programme", title)
        self.assertNotIn(f"/formations/{autonomous.id}/avis", page.text)
        # The chosen version gives its details (here its duration); the version itself is not
        # named on the page, and offers are not listed twice.
        root = html.fromstring(page.content)
        self.assertEqual(self.course_schema(root)["timeRequired"], "PT3H30M")
        self.assertNotIn(autonomous.title, page.text)
        self.assertFalse(root.xpath("//*[contains(@class, 'o_training_course_offers')]"))
        general = self.url_open(f"/formations/catalogue/{self.course.id}")
        self.assertNotIn(older.title, general.text)
        # By default the page presents the version led by a trainer.
        tree = html.fromstring(general.content)
        self.assertIn("21 h", tree.xpath("string(//dl[contains(@class, 'o_training_course_figures')])"))
        self.assertEqual(self.course_schema(tree)["timeRequired"], "PT21H")
        self.assertNotIn("Version V2", tree.xpath("string(//section[@id='training_course_modalities'])"))
        # Without an inter-company price nor session, the trainer-led version is offered in intra
        # only; with the autonomous version, both formats are compared after the description.
        tabs = tree.xpath("//div[@role='tablist']/button/@data-bs-target")
        self.assertEqual(tabs, ["#training_booking_intra", "#training_booking_autonomous"])
        self.assertEqual(
            tree.xpath("//section[@id='training_course_formats']//thead/tr/th/text()"),
            ["Intra-entreprise", "En autonomie"],
        )
        # The comparison closes the details of the course, before the questions.
        sections = tree.xpath("//div[contains(@class, 'col-lg-8')]/section/@id")
        self.assertLess(sections.index("training_course_modalities"), sections.index("training_course_formats"))
        # Each format can be chosen from the comparison, which opens its tab of the booking card.
        self.assertEqual(
            tree.xpath("//section[@id='training_course_formats']//tbody/tr[last()]//a/@href"),
            [f"?format={key}#training_course_booking" for key in ("intra", "autonomous")],
        )
        self.assertFalse(tree.xpath("//div[@id='training_booking_inter']"))
        # Each column of the comparison carries its format, so the chosen tab can be highlighted.
        self.assertEqual(
            tree.xpath("//section[@id='training_course_formats']//th[@data-format]/@data-format"),
            ["intra", "autonomous"],
        )
        self.assertEqual(
            tree.xpath(
                "//section[@id='training_course_formats']//*[contains(@class, 'o_training_course_selected')]/@data-format"
            ),
            ["intra"] * 9,
        )
        chosen = html.fromstring(self.url_open(f"/formations/catalogue/{self.course.id}?format=autonomous").content)
        self.assertEqual(
            chosen.xpath("//div[@role='tablist']/button[@aria-selected='true']/@data-bs-target"),
            ["#training_booking_autonomous"],
        )

    def test_course_page_without_session_price_or_review_stays_usable(self):
        program = self.new_program(public_catalogue=True, version="EMPTY-1", title="Fictional bare version")
        program.action_validate()
        program.action_publish()
        self.authenticate(None, None)
        page = self.url_open(f"/formations/catalogue/{self.course.id}")
        self.assertEqual(page.status_code, 200)
        tree = html.fromstring(page.content)
        # No session and no inter-company price: no inter-company tab, the intra quotation remains.
        self.assertFalse(tree.xpath("//div[@id='training_booking_inter']"))
        self.assertFalse(tree.xpath(f"//a[@href='/formations/{program.id}/date-alert']"))
        self.assertIn("Sur devis", tree.xpath("string(//div[@id='training_booking_intra'])"))
        self.assertFalse(tree.xpath("//section[@id='training_course_reviews']"))
        self.assertFalse(
            tree.xpath("//nav[@aria-label='Sommaire de la formation']//a[@href='#training_course_reviews']")
        )
        self.assertIn("Sur devis", tree.xpath("string(//div[contains(@class, 'o_training_course_mobile_bar')])"))
        # Accessible tabs: labelled list, each tab controls a focusable panel.
        self.assertEqual(tree.xpath("//div[@role='tablist']/@aria-label"), ["Formats de la formation"])
        for tab in tree.xpath("//div[@role='tablist']/button[@role='tab']"):
            (panel,) = tree.xpath("//*[@id='%s']" % tab.get("aria-controls"))
            self.assertEqual((panel.get("role"), panel.get("tabindex")), ("tabpanel", "0"))
            self.assertEqual(panel.get("aria-labelledby"), tab.get("id"))
        self.assertEqual(
            tree.xpath("//div[@role='tablist']/button[@aria-selected='true']/@data-bs-target"),
            ["#training_booking_intra"],
        )
        # Every anchor of the summary leads to a section of the page.
        for anchor in tree.xpath("//nav[@aria-label='Sommaire de la formation']//a/@href"):
            self.assertTrue(tree.xpath("//*[@id='%s']" % anchor[1:]), anchor)
