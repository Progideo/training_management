import io

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.pdf import PdfFileReader

from .test_catalogue import CatalogueCase


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
        from lxml import html

        tree = html.fromstring(response.content)
        self.assertEqual(tree.xpath("//h3[text()='Public chapter']/text()"), ["Public chapter"])
        self.assertIn("Public detail", tree.xpath("//li/ul/li/text()"))
        self.assertNotIn("pr84_unsafe", response.text)
        self.assertNotIn("Public explanation", response.text)
        token = self.csrf_token()
        response = self.url_open(f"/formations/{program.id}", data={"csrf_token": token, str(question.id): "a"})
        self.assertIn("Public explanation", response.text)
        self.assertEqual(self.url_open(f"/formations/{program.id}/pdf").content, raw)
        self.assertTrue(self.url_open(f"/formations/{program.id}/apercu.pdf").content.startswith(b"%PDF-"))
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
        program.with_context(lang="fr_FR").title = "Titre français du catalogue"
        program.action_validate()
        program.action_publish()
        raw = bytes(program.pdf_attachment_id.raw)
        for language, title in (("en_US", "English catalogue title"), ("fr_FR", "Titre français du catalogue")):
            current = SimpleNamespace(env=self.env(context={**self.env.context, "lang": language}), website=False)
            with patch.object(public_catalogue, "request", current):
                projected = public_catalogue.TrainingPublicCatalogue._program(program.id)
                self.assertEqual(projected.title, title)
                self.assertEqual(bytes(projected.pdf_attachment_id.raw), raw)
