"""Restricted-user continuity, real closure, preserved PDFs and native wizards."""

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from .test_certificate_verification import VerificationCase


@tagged("post_install", "-at_install")
class TestClosureContinuity(VerificationCase):
    def wizard(self, action, user):
        return self.env["training.closure.change"].with_user(user).with_context(**action["context"])

    def close(self, dossier):
        for category in dossier._missing_keys():
            self.validate(self.proof(dossier, category=category))
        dossier.with_user(self.quality).action_close()

    def test_archived_reviewer_transfer_restores_revocation_preserves_authors(self):
        dossier, document, verification = self.issue()
        self.close(dossier)
        original = document.read(["data", "snapshot", "actor_id", "created_at", "sha256"])
        proofs = dossier.evidence_ids.read(["data", "validated_at", "validated_by_id", "sha256"])
        closed = dossier.read(["closed_at", "closed_by_id", "state", "retention_id"])
        self.quality.sudo().active = False
        action = dossier.with_user(self.coordinator).action_reassign_quality()
        with Form(self.wizard(action, self.coordinator)) as form:
            form.quality_id = self.other_quality
            form.reason = "Fictional reviewer departure"
        form.record.action_apply()
        form.record.action_apply()
        self.assertEqual(dossier.quality_id, self.other_quality)
        self.assertEqual(dossier.read(["closed_at", "closed_by_id", "state", "retention_id"]), closed)
        self.assertEqual(document.read(["data", "snapshot", "actor_id", "created_at", "sha256"]), original)
        self.assertEqual(dossier.evidence_ids.read(["data", "validated_at", "validated_by_id", "sha256"]), proofs)
        event = dossier.event_ids.filtered(lambda e: e.operation == "reassign")
        self.assertEqual(len(event), 1)
        self.assertEqual(event.actor_id, self.coordinator)
        self.assertEqual(event.previous_quality_id, self.quality)
        self.assertEqual(event.quality_id, self.other_quality)
        with self.assertRaises(AccessError):
            verification.with_user(self.quality).sudo().action_revoke(reason="Archived reviewer")
        verification.with_user(self.other_quality).action_revoke(reason="Fictional replacement reviewer decision")
        self.assertEqual(verification.state, "revoked")
        for user in (self.portal, self.quality):
            with self.assertRaises(AccessError):
                event.with_user(user).read(["reason"])
        for action in (lambda: event.write({"reason": "Forged"}), lambda: event.copy(), lambda: event.unlink()):
            with self.assertRaises((AccessError, ValidationError)):
                action()

    def test_transfer_checks_coordinator_scope_target_and_stale_form(self):
        dossier, _document, _verification = self.issue()
        outside = new_test_user(
            self.env,
            login="continuity_outside",
            groups="training_management.group_training_quality,training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        for user in (self.quality, self.other_quality, self.portal, outside):
            with self.assertRaises(AccessError):
                dossier.with_user(user).sudo().action_reassign_quality(self.other_quality.id, "Forbidden")
        for target in (self.portal, outside):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                dossier.action_reassign_quality(target.id, "Invalid target")
        with self.assertRaises(ValidationError):
            dossier.action_reassign_quality(self.other_quality.id, " ")
        dossier.action_reassign_quality(self.other_quality.id, "Fictional transfer")
        with self.assertRaises(ValidationError):
            dossier.action_reassign_quality(self.quality.id, "Stale form", expected_quality_id=self.quality.id)
        with self.assertRaises(AccessError):
            dossier.with_user(self.quality).action_rectify("Former reviewer")

    def test_rectification_replaces_all_certificate_types_and_keeps_closed_history(self):
        dossier, _document, verification = self.issue()
        self.validate(self.proof(dossier, category="completion"))
        self.validate(self.proof(dossier, category="assessment", score=85, threshold=70))
        for kind in ("completion", "achievement"):
            getattr(dossier.enrollment_id.with_user(self.quality), "action_certificate_" + kind)()
        old_verifications = dossier.with_user(self.quality).verification_ids
        old_documents = old_verifications.document_id
        old_pdf = old_documents.read(["data", "sha256", "snapshot", "created_at", "actor_id"])
        self.close(dossier)
        old_proofs = dossier.evidence_ids
        proof_values = old_proofs.read(["data", "sha256", "validated_at", "validated_by_id"])
        first_close = dossier.event_ids.filtered(lambda e: e.operation == "close")
        closure_values = dossier.read(["closed_at", "closed_by_id"])
        action = dossier.with_user(self.quality).action_rectify()
        with Form(self.wizard(action, self.quality)) as form:
            form.reason = "Fictional late evidence correction"
        form.record.action_apply()
        form.record.action_apply()
        self.assertEqual(dossier.state, "open")
        self.assertEqual(dossier.read(["closed_at", "closed_by_id"]), closure_values)
        self.assertEqual(len(dossier.event_ids.filtered(lambda e: e.operation == "rectify")), 1)
        replacement = self.revised(dossier)
        self.assertNotEqual(replacement, verification)
        self.validate(self.proof(dossier, category="completion", source="Fictional corrected completion"))
        self.validate(self.proof(dossier, category="assessment", score=95, threshold=70))
        for old in old_verifications:
            getattr(dossier.enrollment_id.with_user(self.quality), "action_certificate_" + old.kind)()
            new = dossier.with_user(self.quality).verification_ids.filtered(
                lambda v: v.kind == old.kind and v not in old_verifications
            )
            self.assertEqual(len(new), 1)
            old.action_replace(new.id, "Fictional corrected certificate")
            self.assertEqual(old._public_values(old.token)["state"], "replaced")
            self.assertEqual(new._public_values(new.token)["state"], "valid")
        dossier.with_user(self.quality).action_close()
        self.assertEqual(dossier.state, "closed")
        self.assertEqual(len(dossier.event_ids.filtered(lambda e: e.operation == "close")), 2)
        self.assertTrue(first_close.exists())
        self.assertEqual(old_documents.read(["data", "sha256", "snapshot", "created_at", "actor_id"]), old_pdf)
        self.assertEqual(old_proofs.read(["data", "sha256", "validated_at", "validated_by_id"]), proof_values)
        with self.assertRaises(ValidationError):
            form.record.action_apply()  # A form for the first closure cannot reopen a later closure.

    def test_rectification_rejects_unauthorized_and_preserves_validated_evidence(self):
        dossier, document, _verification = self.issue()
        self.close(dossier)
        for user in (self.coordinator, self.other_quality, self.portal):
            with self.assertRaises(AccessError):
                dossier.with_user(user).sudo().action_rectify("Forbidden")
        with self.assertRaises(ValidationError):
            dossier.with_user(self.quality).action_rectify(" ")
        dossier.with_user(self.quality).action_rectify("Fictional rectification")
        with self.assertRaises(ValidationError):
            dossier.evidence_ids[:1].write({"source": "Altered original"})
        with self.assertRaises((AccessError, ValidationError)):
            document.write({"filename": "altered.pdf"})
