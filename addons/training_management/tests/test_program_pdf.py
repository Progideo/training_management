import hashlib
import io
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, tagged
from odoo.tools.pdf import PdfFileReader

from .test_catalogue import CatalogueCase


@tagged("post_install", "-at_install")
class TestProgrammePdf(CatalogueCase):
    def text(self, raw):
        return "\n".join(page.extract_text() for page in PdfFileReader(io.BytesIO(bytes(raw))).pages)

    def test_one_validation_real_pdf_and_stable_v1(self):
        program = self.new_program(content="\n".join(["Detailed fictional programme content"] * 130))
        with Form(program) as form:
            self.assertEqual(form.state, "draft")
        program.action_validate()
        attachment = program._reference_pdf()
        original = bytes(attachment.raw)
        self.assertTrue(original.startswith(b"%PDF-"))
        self.assertEqual(hashlib.sha256(original).hexdigest(), program.pdf_sha256)
        self.assertGreater(len(PdfFileReader(io.BytesIO(original)).pages), 1)
        page = PdfFileReader(io.BytesIO(original)).pages[0]
        self.assertLess(float(page.mediabox.width), float(page.mediabox.height), "The programme is A4 portrait")
        text = self.text(original)
        for expected in ("Programme A", "V1", "Objectives", "Beginners", "Practice", "On quotation", self.contact.name):
            if expected == "Practice":
                expected = "Detailed fictional"
            self.assertIn(expected, text)
        self.assertNotIn("not a reference document", text)
        self.assertTrue(
            any(
                "Evaluation" in page.extract_text() and "Final exercise" in page.extract_text()
                for page in PdfFileReader(io.BytesIO(original)).pages
            ),
            "A section title stays with its text",
        )
        self.assertEqual(program.pdf_generated_by_id, self.coordinator)
        self.assertEqual(program.pdf_language_code, "en_US")
        self.assertFalse(attachment.public)
        self.assertFalse(attachment.access_token)
        program.action_validate()
        self.assertEqual(program.pdf_attachment_id, attachment)
        program.action_publish()
        self.course.name = "Renamed course"
        self.course.category_id.name = "Changed category"
        self.course.category_id = self.env["training.category"].create(
            {"name": "Reclassified", "company_id": self.company.id}
        )
        self.company.name = "Changed organisation"
        v2 = program.copy({"version": "V2", "content": "Different content"})
        self.assertFalse(v2.pdf_attachment_id)
        self.assertFalse(v2.pdf_sha256)
        v2.action_validate()
        program.action_retire()
        self.assertEqual(bytes(program.with_user(self.reader)._reference_pdf().raw), original)
        self.assertNotEqual(v2.pdf_sha256, program.pdf_sha256)
        self.assertIn(str(attachment.id), program.with_user(self.reader).action_download_pdf()["url"])
        self.assertFalse(self.env["mail.mail"].search([("model", "=", program._name), ("res_id", "=", program.id)]))

    def test_category_is_one_native_choice_with_company_isolation(self):
        category = self.course.category_id.with_user(self.coordinator)
        other = self.env["training.category"].create({"name": "Other", "company_id": self.other_company.id})
        with self.assertRaises(AccessError):
            other.with_user(self.coordinator).read(["name"])
        with self.assertRaises(AccessError):
            category.with_user(self.reader).write({"name": "Changed"})
        with self.assertRaises(ValidationError):
            category.unlink()
        with self.assertRaises(ValidationError):
            category.write({"company_id": self.other_company.id})
        self.course.category_id = False
        program = self.new_program()
        with self.assertRaises(ValidationError):
            program.write({"category_id": category.id})
        with self.assertRaises(ValidationError):
            self.new_program(version="Forged", category_id=category.id)
        spoofed = (
            self.env["training.program.version"]
            .with_user(self.coordinator)
            .with_context(default_category_id=category.id)
            .create({**self.values, "version": "Context"})
        )
        with self.assertRaises(ValidationError):
            spoofed.action_validate()
        with self.assertRaises(ValidationError):
            program.action_validate()
        self.assertEqual(program.state, "draft")
        with Form(self.course) as form:
            form.category_id = category
        program.action_validate()
        self.assertIn(program, program.search([("category_id", "=", category.id)]))
        category.active = False
        self.assertTrue(program._reference_pdf())

    def test_french_pdf_uses_programme_language_and_parent_company_access(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(["training_management"], ["fr_FR"])
        program = self.new_program(language_id=self.env.ref("base.lang_fr").id)
        program.action_validate()
        text = self.text(program._reference_pdf().raw)
        self.assertIn("Sur devis", text)
        self.assertIn("Objectifs", text)
        self.assertEqual(program.pdf_language_code, "fr_FR")
        # A second company remains inaccessible through both file and report.
        other_category = self.env["training.category"].create(
            {"name": "Other company", "company_id": self.other_company.id}
        )
        self.other_course.category_id = other_category
        other = self.env["training.program.version"].create(
            {**self.values, "course_id": self.other_course.id, "accessibility_contact_id": False}
        )
        other.accessibility_contact_id = self.env["res.partner"].create({"name": "Fictional desk"})
        other.action_validate()
        for operation in (
            lambda: other.with_user(self.reader).action_download_pdf(),
            lambda: other.pdf_attachment_id.with_user(self.reader)._to_http_stream(),
            lambda: other.with_user(self.reader).export_data(["pdf_sha256"]),
            lambda: (
                self.env["ir.actions.report"]
                .with_user(self.reader)
                ._render_qweb_pdf("training_management.action_programme_pdf_preview", other.ids)
            ),
        ):
            with self.assertRaises(AccessError):
                operation()

    def test_generation_and_storage_failure_rollback_entire_batch(self):
        first = self.new_program()
        second = self.new_program(version="V2")
        render = type(first)._render_program_pdf

        def fail_second(record, **kwargs):
            if record.id == second.id:
                raise ValidationError(self.env._("Fictional engine failure"))
            return render(record, **kwargs)

        with patch.object(type(first), "_render_program_pdf", fail_second), self.assertRaises(ValidationError):
            (first | second).action_validate()
        self.assertEqual((first | second).mapped("state"), ["draft", "draft"])
        self.assertFalse((first | second).mapped("pdf_attachment_id"))
        self.assertFalse(self.env["ir.attachment"].sudo().search([("training_program_id", "in", (first | second).ids)]))
        with (
            patch.object(
                type(self.env["ir.attachment"]), "_create_programme_pdf", side_effect=AccessError("No storage")
            ),
            self.assertRaises(AccessError),
        ):
            first.action_validate()
        self.assertEqual(first.state, "draft")
        first.action_validate()
        self.assertTrue(first.pdf_attachment_id)

    def test_reference_is_protected_on_all_orm_paths(self):
        program = self.new_program()
        program.action_validate()
        attachment = program.pdf_attachment_id.with_user(self.coordinator)
        for values in (
            {"raw": b"changed"},
            {"public": True},
            {"res_id": 0},
            {"res_model": "res.partner"},
            {"training_program_id": False},
            {"access_token": "forged"},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                attachment.write(values)
        with self.assertRaises(ValidationError):
            attachment.unlink()
        with self.assertRaises(ValidationError):
            attachment.generate_access_token()
        with self.assertRaises(ValidationError):
            self.env["ir.attachment"].create({"name": "forged", "training_program_id": program.id})
        for values in ({"pdf_attachment_id": False}, {"pdf_sha256": "fake"}, {"pdf_legacy": True}):
            with self.assertRaises(ValidationError):
                program.with_context(training_pdf_internal=True).write(values)
        for user in (self.portal, self.internal, self.env.ref("base.public_user")):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                program.with_user(user).action_download_pdf()
            with self.assertRaises(AccessError):
                attachment.with_user(user)._can_return_content(access_token="forged")
        attachment.with_user(self.reader).check_access("read")
        self.assertEqual(attachment.with_user(self.reader)._to_http_stream().mimetype, "application/pdf")

    def test_preview_cannot_regenerate_reference_or_hide_draft(self):
        program = self.new_program()
        report = self.env["report.training_management.programme_pdf_document"].with_user(self.coordinator)
        values = report._get_report_values(program.ids, data={"draft": False})
        self.assertTrue(values["draft"])
        self.assertIn("not a reference document", self.text(program._render_program_pdf(draft=True)))
        self.assertFalse(program.pdf_attachment_id)
        program.action_validate()
        with self.assertRaises(ValidationError):
            report._get_report_values(program.ids)
        self.assertEqual(program.action_preview_pdf(), program.action_download_pdf())

    def test_historical_reconstruction_is_explicit_dated_and_idempotent(self):
        program = self.new_program()
        # Simulate the pre-lot immutable row marked by the migration, without
        # weakening the public model API or assigning fake historical PDF bytes.
        self.env.cr.execute(
            "UPDATE training_program_version SET state='validated', pdf_legacy=TRUE WHERE id=%s", [program.id]
        )
        program.invalidate_recordset()
        self.course.category_id = False
        with self.assertRaises(ValidationError):
            program.action_download_pdf()
        with self.assertRaises(AccessError):
            program.with_user(self.reader).action_reconstruct_pdf()
        action = self.env.ref("training_management.action_reconstruct_programme_pdf_selection").with_user(
            self.coordinator
        )
        action.with_context(active_model=program._name, active_ids=program.ids).run()
        original = bytes(program.pdf_attachment_id.raw)
        self.assertTrue(program.pdf_reconstructed)
        self.assertIn("Reconstructed", self.text(original))
        self.assertTrue(program.pdf_generated_at)
        program.action_reconstruct_pdf()
        self.assertEqual(original, bytes(program.pdf_attachment_id.raw))
        program.action_publish()
        self.assertFalse(self.course.category_id)

    def test_missing_or_altered_reference_is_never_recreated(self):
        program = self.new_program()
        program.action_validate()
        self.env.cr.execute("UPDATE training_program_version SET pdf_sha256='altered' WHERE id=%s", [program.id])
        program.invalidate_recordset()
        with self.assertRaises(ValidationError):
            program.action_download_pdf()
        with self.assertRaises(ValidationError):
            program.action_reconstruct_pdf()
        with self.assertRaises(ValidationError):
            program.pdf_attachment_id._to_http_stream()


@tagged("post_install", "-at_install")
class TestProgrammePdfHttp(CatalogueCase, HttpCase):
    def test_native_binary_and_report_routes_keep_parent_authorization(self):
        program = self.new_program()
        program.action_validate()
        raw = bytes(program.pdf_attachment_id.raw)
        url = program.action_download_pdf()["url"]
        self.authenticate(self.reader.login, self.reader.login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, raw)
        response = self.url_open(f"/report/pdf/training_management.programme_pdf_document/{program.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, raw, "The direct report route also returns the frozen bytes")
        # Token deliberately inserted by SQL to exercise legacy/native bypass
        # handling, which normal attachment writes prohibit.
        self.env.cr.execute(
            "UPDATE ir_attachment SET access_token='legacy-forged-token' WHERE id=%s", [program.pdf_attachment_id.id]
        )
        program.pdf_attachment_id.invalidate_recordset()
        for user in (self.portal, self.internal):
            self.authenticate(user.login, user.login)
            for path in (
                url,
                url + "&access_token=legacy-forged-token",
                f"/report/html/training_management.programme_pdf_document/{program.id}",
                f"/report/pdf/training_management.programme_pdf_document/{program.id}",
            ):
                response = self.url_open(path)
                self.assertNotEqual(response.status_code, 200, path)
                self.assertNotIn(raw, response.content)
