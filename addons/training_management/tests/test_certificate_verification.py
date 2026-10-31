"""P20: real PDF/QR, public allowlist and controlled status transitions."""

import hashlib
import io
import json
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools.misc import limited_field_access_token
from odoo.tools.pdf import PdfReader

from .test_closure import ClosureCase


class VerificationCase(ClosureCase):
    def issue(self, verify=True):
        _, session, enrollment = self.scheduled()
        dossier = self.dossier(enrollment)
        dossier.verify_certificates = verify
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            self.review(self.declare(session, enrollment))
        enrollment.with_user(self.quality).action_certificate_participation()
        document = self.document(dossier, "participation")
        verification = self.env["training.certificate.verification"].search([("document_id", "=", document.id)])
        return dossier, document, verification

    def revised(self, dossier):
        attendance = self.env["training.attendance"].search([("enrollment_id", "=", dossier.enrollment_id.id)])
        with patch("odoo.fields.Datetime.now", return_value=attendance.session_id.end_at):
            self.service(self.coordinator)._review(
                attendance.session_id.id,
                dossier.enrollment_id.id,
                45,
                120,
                revision=attendance.revision,
                correction=True,
                reason="Fictional signed correction",
                data=b"%PDF-1.4\nfictional",
                filename="proof.pdf",
                definition=self.service()._definition(attendance.session_id),
            )
        dossier.enrollment_id.with_user(self.quality).action_certificate_participation()
        return self.env["training.certificate.verification"].search(
            [("document_id", "=", self.document(dossier, "participation").id)]
        )


@tagged("post_install", "-at_install")
class TestCertificateVerification(VerificationCase):
    def test_pdf_qr_allowlist_and_idempotency(self):
        dossier, document, verification = self.issue()
        self.assertEqual(len(verification), 1)
        self.assertEqual(len(verification.token), 43)
        self.assertEqual(document.template_version, "P20-QWEB-1")
        self.assertEqual(verification.sha256, hashlib.sha256(document.data.content).hexdigest())
        self.assertTrue(document.data.content.startswith(b"%PDF-"))
        pdf = PdfReader(io.BytesIO(document.data.content))
        self.assertEqual(len(pdf.pages), 1)
        links = [
            annotation.get_object().get("/A", {}).get("/URI")
            for page in pdf.pages
            for annotation in page.get("/Annots", [])
        ]
        self.assertIn(verification.url, links)
        self.assertIn(verification.reference, pdf.pages[0].extract_text())
        self.assertTrue(self.env["ir.actions.report"].barcode("QR", verification.url).startswith(b"\x89PNG"))
        values = verification._public_values(verification.token)
        self.assertEqual(
            set(values),
            {
                "issuer",
                "beneficiary",
                "reference",
                "kind",
                "programme",
                "programme_version",
                "issued_at",
                "state",
                "sha256",
            },
        )
        self.assertEqual(values["state"], "valid")
        self.assertEqual(values["beneficiary"], dossier.enrollment_id.participant_id.name)
        self.assertEqual(verification.reference, json.loads(document.snapshot)["reference"])
        frozen_name = values["beneficiary"]
        dossier.enrollment_id.participant_id.sudo().name = "Fictional renamed contact"
        self.assertEqual(verification._public_values(verification.token)["beneficiary"], frozen_name)
        dossier.enrollment_id.participant_id.sudo().name = frozen_name
        old_bytes = document.data.content
        dossier.enrollment_id.with_user(self.quality).action_certificate_participation()
        self.assertEqual(self.document(dossier, "participation"), document)
        self.assertEqual(document.data.content, old_bytes)
        self.assertEqual(
            self.env["training.certificate.verification"].search_count([("dossier_id", "=", dossier.id)]), 1
        )
        # Proof/filename/content never becomes writable through verification actions.
        for values in ({"state": "revoked"}, {"token": "a" * 43}, {"issuer": "Changed"}):
            with self.assertRaises(AccessError):
                verification.with_user(self.quality).write(values)
        with self.assertRaises(AccessError):
            verification.with_user(self.quality).copy()
        with self.assertRaises(AccessError):
            verification.with_user(self.quality).unlink()
        with self.assertRaises(ValidationError):
            verification.unlink()
        with self.assertRaises(AccessError):
            verification.with_user(self.quality).create({})
        for token in ("unknown", str(document.id), "x" * 43, "x" * 10000, False):
            self.assertFalse(verification._public_values(token))

    def test_completion_and_achievement_publish_no_assessment_details(self):
        dossier = self.dossier()
        dossier.verify_certificates = True
        self.validate(self.proof(dossier, category="completion"))
        self.validate(self.proof(dossier, category="assessment", score=85, threshold=70))
        for kind in ("completion", "achievement"):
            getattr(dossier.enrollment_id.with_user(self.quality), "action_certificate_" + kind)()
            document = self.document(dossier, kind)
            verification = self.env["training.certificate.verification"].search([("document_id", "=", document.id)])
            self.assertEqual(verification.kind, kind)
            self.assertEqual(document.template_version, "P20-QWEB-1")
            public = verification._public_values(verification.token)
            self.assertEqual(public["kind"], kind)
            self.assertNotIn("score", public)
            self.assertNotIn("threshold", public)
            self.assertNotIn("origins", public)

    def test_opt_in_preserves_old_pdf_and_creates_new_version(self):
        dossier, document, verification = self.issue(verify=False)
        self.assertFalse(verification)
        self.assertEqual(document.template_version, "S08-QWEB-1")
        old = document.read(["snapshot", "sha256", "created_at", "actor_id"])
        old_pdf = document.data.content
        dossier.verify_certificates = True
        dossier.enrollment_id.with_user(self.quality).action_certificate_participation()
        new = self.document(dossier, "participation")
        self.assertNotEqual(new, document)
        self.assertEqual(new.template_version, "P20-QWEB-1")
        self.assertEqual(document.read(["snapshot", "sha256", "created_at", "actor_id"]), old)
        self.assertEqual(document.data.content, old_pdf)
        self.assertFalse(self.env["training.certificate.verification"].search([("document_id", "=", document.id)]))

    def test_revocation_roles_audit_repeat_and_closed_dossier(self):
        dossier, document, verification = self.issue()
        original = document.data.content
        for user in (self.coordinator, self.other_quality, self.portal, self.portal_b, self.reader, self.internal):
            with self.assertRaises(AccessError):
                verification.with_user(user).action_revoke(reason="Forbidden")
            with self.assertRaises(AccessError):
                verification.with_user(user).sudo().action_revoke(reason="Forbidden sudo")
        outside = new_test_user(
            self.env,
            login="p20_outside",
            groups="training_management.group_training_quality",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        with self.assertRaises(AccessError):
            verification.with_user(outside).action_revoke(reason="Foreign company")
        quality = verification.with_user(self.quality)
        wizard_action = quality.action_revoke()
        wizard = (
            self.env["training.certificate.change"]
            .with_user(self.quality)
            .with_context(**wizard_action["context"])
            .create({"reason": "Fictional erroneous issuance"})
        )
        # Revocation remains possible after dossier closure without reopening it.
        self.env.cr.execute("UPDATE training_closure SET state='closed' WHERE id=%s", [dossier.id])
        dossier.invalidate_recordset()
        with self.assertRaises(ValidationError):
            quality.action_revoke(reason=" ")
        wizard.action_apply()
        verification.invalidate_recordset()
        self.assertEqual(verification.state, "revoked")
        self.assertEqual(verification.changed_by_id, self.quality)
        self.assertEqual(verification.reason, "Fictional erroneous issuance")
        audit = verification.read(["changed_at", "changed_by_id", "reason"])
        quality.action_revoke(reason="Repeated submission")
        self.assertEqual(verification.read(["changed_at", "changed_by_id", "reason"]), audit)
        self.assertEqual(verification._public_values(verification.token)["state"], "revoked")
        self.assertEqual(document.data.content, original)
        self.assertEqual(dossier.state, "closed")

    def test_replacement_checks_scope_and_preserves_each_pdf(self):
        dossier, old, verification = self.issue()
        replacement = self.revised(dossier)
        quality = verification.with_user(self.quality)
        original = old.data.content
        _, _, foreign = self.issue()
        for target in (verification, foreign):
            with self.assertRaises(ValidationError):
                quality.action_replace(replacement_id=target.id, reason="Wrong target")
        quality.action_replace(replacement_id=replacement.id, reason="Fictional corrected attendance")
        self.assertEqual(verification.replacement_id, replacement)
        self.assertEqual(verification._public_values(verification.token)["state"], "replaced")
        self.assertEqual(replacement._public_values(replacement.token)["state"], "valid")
        quality.action_replace(replacement_id=replacement.id, reason="Repeat")
        with self.assertRaises(ValidationError):
            quality.action_revoke(reason="Cannot alter terminal decision")
        replacement.with_user(self.quality).action_revoke(reason="Fictional later withdrawal")
        self.assertEqual(verification.state, "replaced")
        self.assertEqual(replacement.state, "revoked")
        self.assertEqual(old.data.content, original)
        # Re-issuing identical criteria cannot silently restore a revoked PDF.
        dossier.enrollment_id.with_user(self.quality).action_certificate_participation()
        self.assertEqual(self.document(dossier, "participation"), replacement.document_id)
        self.assertEqual(replacement.state, "revoked")


@tagged("post_install", "-at_install")
class TestCertificateVerificationHttp(VerificationCase, HttpCase):
    def test_public_status_cache_and_private_routes(self):
        dossier, document, verification = self.issue()
        path = "/training/verify/" + verification.token
        self.authenticate(None, None)
        page = self.url_open(path)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Attestation valide", page.text)
        self.assertIn(document.sha256, page.text)
        self.assertIn(dossier.enrollment_id.participant_id.name, page.text)
        self.assertNotIn("/web/content", page.text)
        self.assertNotIn(str(dossier.id) + "/data", page.text)
        for field in ("data", "snapshot", "sha256"):
            token = limited_field_access_token(document, field, scope="binary")
            private = f"/web/content/training.document/{document.id}/{field}?access_token={token}"
            self.assertIn(self.url_open(private, allow_redirects=False).status_code, (303, 403, 404))
        replacement = self.revised(dossier)
        verification.with_user(self.quality).action_replace(
            replacement_id=replacement.id, reason="Fictional public replacement"
        )
        replaced = self.url_open(path)
        self.assertIn("Attestation remplacée", replaced.text)
        self.assertNotIn("Attestation valide", replaced.text)
        self.assertNotIn(replacement.token, replaced.text)
        self.assertNotIn(replacement.url, replaced.text)
        path = "/training/verify/" + replacement.token
        self.assertIn("Attestation valide", self.url_open(path).text)
        replacement.with_user(self.quality).action_revoke(reason="Fictional revocation")
        for field in ("reason", "token", "url"):
            token = limited_field_access_token(replacement, field, scope="binary")
            private = f"/web/content/training.certificate.verification/{replacement.id}/{field}?access_token={token}"
            self.assertIn(self.url_open(private, allow_redirects=False).status_code, (303, 403, 404))
        revoked = self.url_open(path)
        self.assertIn("Attestation révoquée", revoked.text)
        self.assertNotIn("Attestation valide", revoked.text)
        unknown = self.url_open("/training/verify/" + "z" * 43)
        self.assertEqual(unknown.status_code, 404)
        self.assertIn("Attestation inconnue", unknown.text)
        for response in (page, replaced, revoked, unknown):
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
            self.assertIn("noindex", response.headers["X-Robots-Tag"])
        self.assertEqual(self.url_open(path, data={"probe": "1"}).status_code, 405)

    def test_verification_uses_native_theme_styles_without_website_trackers(self):
        _dossier, _document, verification = self.issue()
        if "google_analytics_key" in self.env["website"]._fields:
            self.env.ref("base.default_website").google_analytics_key = "G-UXFICTIONAL"
        self.authenticate(None, None)
        page = self.url_open("/training/verify/" + verification.token)
        from lxml import html

        tree = html.fromstring(page.content)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(tree.xpath("//html")), 1)
        self.assertEqual(len(tree.xpath("//main")), 1)
        self.assertTrue(tree.xpath("//link[@rel='stylesheet'][contains(@href, '/web/assets/')]"))
        self.assertFalse(tree.xpath("//style"))
        self.assertFalse(tree.xpath("//script[@src]"))
        self.assertNotIn("G-UXFICTIONAL", page.text)
        self.assertNotIn("tracking_code", page.text)
