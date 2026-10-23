"""DOC01–02: actual restricted quality/coordinator/portal identities and PDF bytes."""

import io
import json
import zipfile
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.misc import limited_field_access_token

from .test_attendance import AttendanceCase
from .test_material import PDF
from ..models.training_closure import CATEGORIES


class ClosureCase(AttendanceCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality = new_test_user(cls.env, login="s08_quality", groups="training_management.group_training_quality")
        cls.other_quality = new_test_user(
            cls.env, login="s08_other_quality", groups="training_management.group_training_quality"
        )
        policy = (
            cls.env["training.retention.category"]
            .with_user(cls.quality)
            .create(
                {
                    "name": "Fictional approved policy",
                    "purpose": "Training evidence",
                    "responsible_id": cls.quality.id,
                    "duration_days": 365,
                    "archive_policy": "Restricted archive",
                    "deletion_policy": "Review requests; no automatic purge",
                }
            )
        )
        policy.action_approve()
        cls.retention = policy

    def dossier(self, enrollment=None):
        enrollment = enrollment or self.opened()
        return (
            self.env["training.closure"]
            .with_user(self.coordinator)
            .create(
                {
                    "enrollment_id": enrollment.id,
                    "quality_id": self.quality.id,
                    "retention_id": self.retention.id,
                }
            )
        )

    def proof(self, dossier, category="need", **values):
        return (
            self.env["training.proof"]
            .with_user(self.coordinator)
            .create(
                {
                    "dossier_id": dossier.id,
                    "category": category,
                    "source": "Fictional original file / checked scope",
                    "author": "Fictional author",
                    "produced_at": fields.Datetime.now(),
                    "data": BinaryBytes(PDF),
                    **values,
                }
            )
        )

    def validate(self, proof):
        proof.with_user(self.quality).action_validate()
        return proof

    def document(self, dossier, kind=None):
        domain = [("dossier_id", "=", dossier.id)]
        if kind:
            domain.append(("kind", "=", kind))
        return self.env["training.document"].sudo().search(domain, order="id desc", limit=1)


@tagged("post_install", "-at_install")
class TestClosure(ClosureCase):
    def test_provenance_versions_immutable_policy_and_server_fields(self):
        dossier = self.dossier()
        proof = self.proof(dossier)
        with self.assertRaises(AccessError):
            proof.action_validate()
        with self.assertRaises(AccessError):
            proof.with_user(self.other_quality).action_validate()
        self.validate(proof)
        self.assertEqual(proof.validated_by_id, self.quality)
        with self.assertRaises(ValidationError):
            proof.write({"data": BinaryBytes(PDF + b"changed")})
        with self.assertRaises((AccessError, ValidationError)):
            proof.unlink()
        with self.assertRaises(ValidationError):
            self.retention.write({"duration_days": 1})
        with self.assertRaises(AccessError):
            self.proof(dossier, version=99)
        second = self.proof(dossier)
        self.assertEqual(second.previous_id, proof)
        self.assertEqual(second.version, 2)
        self.assertIn("need", dossier._missing_keys())
        self.validate(second)
        self.assertNotIn("need", dossier._missing_keys())
        with self.assertRaises((AccessError, UserError)):
            proof.export_data(["source", "data"])
        with self.assertRaises(ValidationError):
            self.env["ir.attachment"].create(
                {"name": "bypass.pdf", "raw": PDF, "res_model": proof._name, "res_id": proof.id}
            )
        with self.assertRaises(ValidationError):
            self.proof(dossier, category="assessment", client_shared=True)
        forged = (
            self.env["training.proof"]
            .with_user(self.coordinator)
            .with_context(default_validated_at=fields.Datetime.now(), default_sha256="forged")
            .create(
                {
                    "dossier_id": dossier.id,
                    "category": "materials",
                    "source": "original",
                    "author": "author",
                    "produced_at": fields.Datetime.now(),
                }
            )
        )
        self.assertFalse(forged.validated_at)
        self.assertFalse(forged.sha256)

    def test_incomplete_dossier_exemptions_and_closed_freeze(self):
        dossier = self.dossier()
        quality = dossier.with_user(self.quality)
        with self.assertRaises(ValidationError):
            quality.action_close()
        proof = self.proof(dossier, disposition="waiver", data=False)
        with self.assertRaises(ValidationError):
            proof.with_user(self.quality).action_validate()
        proof.reason = "Fictional approved exception: original unavailable"
        self.validate(proof)
        for category, _label in CATEGORIES[1:]:
            self.validate(
                self.proof(
                    dossier, category, disposition="not_applicable", reason="Fictional case reviewed", data=False
                )
            )
        quality.action_close()
        quality.action_close()
        self.assertEqual(dossier.state, "closed")
        self.assertEqual(dossier.closed_by_id, self.quality)
        dossier.write({"client_contact_ids": [Command.clear()]})
        with self.assertRaises(ValidationError):
            self.proof(dossier)
        with self.assertRaises(ValidationError):
            dossier.write({"frozen": False})
        with self.assertRaises((AccessError, ValidationError)):
            dossier.unlink()

    def test_participation_actual_duration_and_retained_pdf(self):
        _delivery, session, enrollment = self.scheduled()
        dossier = self.dossier(enrollment)
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            presence = self.declare(session, enrollment)
            self.review(presence)
        quality_enrollment = enrollment.with_user(self.quality)
        quality_enrollment.action_certificate_participation()
        doc = self.document(dossier, "participation")
        original = doc.data.content
        snapshot = json.loads(doc.snapshot)
        self.assertEqual(snapshot["minutes"], 90)
        self.assertEqual(snapshot["origins"][0]["revision"], presence.revision)
        self.assertTrue(original.startswith(b"%PDF-"))
        quality_enrollment.action_certificate_participation()
        self.assertEqual(self.document(dossier, "participation"), doc)
        with self.assertRaises(AccessError):
            doc.with_user(self.quality).write({"data": BinaryBytes(PDF)})
        with self.assertRaises(AccessError):
            enrollment.action_certificate_participation()
        self.assertEqual(doc.data.content, original)
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            self.service(self.coordinator)._review(
                session.id,
                enrollment.id,
                45,
                120,
                revision=presence.revision,
                correction=True,
                reason="Fictional signed correction",
                data=PDF,
                filename="proof.pdf",
                definition=self.service()._definition(session),
            )
        quality_enrollment.action_certificate_participation()
        revised = self.document(dossier, "participation")
        self.assertNotEqual(revised, doc)
        self.assertEqual(json.loads(revised.snapshot)["minutes"], 75)
        enrollment.action_abandon(reason="Fictional early departure after partial attendance")
        quality_enrollment.action_certificate_participation()
        self.assertEqual(self.document(dossier, "participation"), revised)
        self.assertEqual(doc.data.content, original)
        self.assertTrue(self.env["training.document.policy"].with_user(self.portal)._can_read(doc))
        self.assertFalse(self.env["training.document.policy"].with_user(self.portal_b)._can_read(doc))
        with self.assertRaises(AccessError):
            self.env["ir.actions.report"].with_user(self.quality)._render_qweb_html(
                "training_management.certificate_document", [doc.id], data={"values": snapshot}
            )

    def test_dedicated_assessment_and_completion_not_mock_success(self):
        enrollment = self.opened()
        dossier = self.dossier(enrollment)
        quality = enrollment.with_user(self.quality)
        with self.assertRaises(ValidationError):
            quality.action_certificate_achievement()
        with self.assertRaises(ValidationError):
            quality.action_certificate_completion()
        proof = self.validate(self.proof(dossier, "assessment", score=69, threshold=70))
        with self.assertRaises(ValidationError):
            quality.action_certificate_achievement()
        newer = self.validate(self.proof(dossier, "assessment", score=70, threshold=70))
        quality.action_certificate_achievement()
        snapshot = json.loads(self.document(dossier, "achievement").snapshot)
        self.assertEqual(snapshot["origins"][0]["proof"], newer.id)
        self.assertNotEqual(proof.id, newer.id)
        activity = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create({"name": "Required activity", "delivery_id": enrollment.delivery_id.id, "criterion": "declaration"})
        )
        self.validate(self.proof(dossier, "completion"))
        with self.assertRaises(ValidationError):
            quality.action_certificate_completion()
        self.env["training.learning.service"].with_user(self.portal)._declare(enrollment.id, activity.id)
        quality.action_certificate_completion()
        self.assertTrue(self.document(dossier, "completion").data.content.startswith(b"%PDF-"))

    def test_export_scope_manifest_and_direct_permissions(self):
        dossier = self.dossier()
        # An individual dossier's customer is the participant, not a mutable employer.
        dossier.client_contact_ids = [Command.set(self.portal.partner_id.ids)]
        public = self.validate(self.proof(dossier, client_shared=True))
        private = self.validate(
            self.proof(dossier, "assessment", author="PRIVATE AUTHOR", data=BinaryBytes(PDF + b"PRIVATE RESULT"))
        )
        quality = dossier.with_user(self.quality)
        quality.action_export_client()
        client = self.document(dossier, "client")
        with zipfile.ZipFile(io.BytesIO(client.data.content)) as archive:
            index = json.loads(archive.read("index.json"))
            self.assertEqual([p["id"] for p in index["pieces"]], public.ids)
            self.assertNotIn("assessment", index["missing"])
            self.assertNotIn(f"proof-{private.id}-v1.pdf", archive.namelist())
            self.assertFalse(index["closed"])
        self.assertNotIn(b"PRIVATE", client.snapshot.encode())
        quality.action_export_internal()
        internal = self.document(dossier, "internal")
        with zipfile.ZipFile(io.BytesIO(internal.data.content)) as archive:
            self.assertIn(f"proof-{private.id}-v1.pdf", archive.namelist())
        policy = self.env["training.document.policy"]
        self.assertTrue(policy.with_user(self.portal)._can_read(client))
        for user in (self.portal_b, self.reader, self.internal, self.other_quality):
            self.assertFalse(policy.with_user(user)._can_read(client))
            self.assertFalse(policy.with_user(user)._can_read(internal))
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._get_stream_from(client.with_user(user).sudo(), "data")
        dossier.client_contact_ids = [Command.clear()]
        self.assertFalse(policy.with_user(self.portal)._can_read(client))
        self.assertFalse(policy.with_user(self.portal)._can_read(internal))
        with self.assertRaises(AccessError):
            dossier.with_user(self.coordinator).action_export_internal()
        with self.assertRaises(ValidationError):
            policy.with_user(self.quality)._check_send(client, self.portal.partner_id)

    def test_sensitive_evidence_native_form_and_field_token_scope(self):
        dossier = self.dossier()
        with Form(
            self.env["training.proof"].with_user(self.quality).with_context(default_dossier_id=dossier.id)
        ) as form:
            form.category = "assessment"
            form.source = "Fictional dedicated assessment original"
            form.author = "Fictional evaluator"
            form.produced_at = fields.Datetime.now()
            form.confidentiality = "sensitive"
            form.data = BinaryBytes(PDF)
        proof = form.record
        proof.action_validate()
        self.assertFalse(proof.with_user(self.coordinator).has_access("read"))
        with self.assertRaises(ValidationError):
            dossier.write({"quality_id": self.other_quality.id})
        policy = self.env["training.document.policy"].with_user(self.coordinator)
        self.assertFalse(policy._can_read(proof))
        self.assertNotIn("assessment", dossier._missing_keys())
        dossier.with_user(self.quality).action_export_internal()
        doc = self.document(dossier)
        with self.assertRaises(AccessError):
            self.env["ir.binary"].with_user(self.quality)._get_stream_from(doc, "snapshot")

    def test_company_client_and_enrollment_scope(self):
        dossier = self.dossier()
        with self.assertRaises(ValidationError):
            dossier.client_contact_ids = [Command.set(self.portal_b.partner_id.ids)]
        with self.assertRaises(ValidationError):
            dossier.quality_id = self.internal
        self.proof(dossier)
        with self.assertRaises(ValidationError):
            dossier.retention_id = self.retention
        outside = new_test_user(
            self.env,
            login="s08_outside",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        self.assertFalse(dossier.with_user(outside).has_access("read"))
        for user in (self.portal, self.portal_b, self.reader, self.internal, self.other_quality):
            self.assertFalse(dossier.with_user(user).has_access("read"))


@tagged("post_install", "-at_install")
class TestClosureHttp(ClosureCase, HttpCase):
    def test_native_binary_tokens_and_authenticated_portal(self):
        dossier = self.dossier()
        dossier.client_contact_ids = [Command.set(self.portal.partner_id.ids)]
        self.validate(self.proof(dossier, client_shared=True))
        dossier.with_user(self.quality).action_export_client()
        client = self.document(dossier, "client")
        token = limited_field_access_token(client, "data", scope="binary")
        url = f"/web/content/training.document/{client.id}/data?access_token={token}"
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(url).status_code, 200)
        private_token = limited_field_access_token(client, "snapshot", scope="binary")
        private_url = f"/web/content/training.document/{client.id}/snapshot?access_token={private_token}"
        self.assertIn(self.url_open(private_url).status_code, (403, 404))
        page = self.url_open("/my/training-documents")
        self.assertEqual(page.status_code, 200)
        self.assertIn(client.filename, page.text)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertIn(self.url_open(url).status_code, (403, 404))
        self.assertNotIn(client.filename, self.url_open("/my/training-documents").text)
        self.authenticate(self.portal.login, self.portal.login)
        dossier.client_contact_ids = [Command.clear()]
        self.assertIn(self.url_open(url).status_code, (403, 404))
        self.authenticate(None, None)
        self.assertIn(self.url_open(url, allow_redirects=False).status_code, (303, 403, 404))
