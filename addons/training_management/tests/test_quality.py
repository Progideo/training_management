"""QUA01–02: actual restricted identities, confidential files, decisions and S08."""

import json
from datetime import timedelta
from uuid import uuid4

from lxml import html
from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.misc import limited_field_access_token

from .test_closure import ClosureCase
from .test_material import PDF


class QualityCase(ClosureCase):
    def complaint(self, **values):
        enrollment = self.opened()
        vals = {
            "name": "Fictional private complaint",
            "description": "CONFIDENTIAL original third-party detail",
            "delivery_id": enrollment.delivery_id.id,
            "enrollment_id": enrollment.id,
            "complainant_id": enrollment.participant_id.id,
            "quality_id": self.quality.id,
            "retention_id": self.retention.id,
            "due_date": fields.Date.today() + timedelta(days=5),
            "portal_visible": True,
            **values,
        }
        return self.env["training.complaint"].with_user(self.coordinator).create(vals).with_user(self.quality)

    def improvement(self, complaint=None, **values):
        complaint = complaint or self.complaint()
        return (
            self.env["training.improvement"]
            .with_user(self.quality)
            .create(
                {
                    "name": "Fictional corrected support",
                    "company_id": complaint.company_id.id,
                    "delivery_id": complaint.delivery_id.id,
                    "complaint_id": complaint.id,
                    "origin": "complaint",
                    "origin_reference": "Fictional complaint and identified support version",
                    "quality_id": self.quality.id,
                    "retention_id": self.retention.id,
                    "due_date": fields.Date.today() + timedelta(days=5),
                    **values,
                }
            )
        )

    def intake(self):
        enrollment = self.opened()
        enrollment.delivery_id.write(
            {
                "complaint_quality_id": self.quality.id,
                "complaint_retention_id": self.retention.id,
                "complaint_response_days": 5,
            }
        )
        return enrollment

    def resolve(self, row):
        row.action_start()
        row.write(
            {
                "treatment": "PRIVATE internal treatment",
                "reply": "Communicable reply",
                "resolution_reason": "Documented correction",
            }
        )
        row.action_resolve()
        return row


@tagged("post_install", "-at_install")
class TestQuality(QualityCase):
    def test_complaint_lifecycle_reply_reopen_and_history(self):
        row = self.complaint()
        with self.assertRaises(ValidationError):
            row.action_close()
        row.action_start()
        with self.assertRaises(ValidationError):
            row.action_resolve()
        self.resolve(row)
        row.action_close()
        count = len(row.event_ids)
        row.action_close()
        self.assertEqual(len(row.event_ids), count)
        original = [(r.id, r.details) for r in row.event_ids]
        with self.assertRaises(ValidationError):
            row.write({"reply": "Rewritten historical reply"})
        with self.assertRaises(ValidationError):
            row.action_reopen()
        row.action_reopen("Fictional additional investigation")
        self.assertEqual(row.state, "processing")
        self.assertFalse(row.closed_at)
        self.assertEqual([(r.id, r.details) for r in row.event_ids[: len(original)]], original)
        self.assertTrue(any(json.loads(r.details)["before"].get("closed_at") for r in row.event_ids))
        with self.assertRaises(AccessError):
            row.write({"state": "closed"})
        with self.assertRaises(AccessError):
            row.write({"description": "Replace original"})
        with self.assertRaises(AccessError):
            row.event_ids[:1].write({"reason": "forged"})
        with self.assertRaises(AccessError):
            self.env["training.quality.event"].with_user(self.quality).create({"complaint_id": row.id})
        with self.assertRaises((AccessError, ValidationError)):
            row.unlink()

    def test_implementation_never_means_effective_and_failure_needs_follow_up(self):
        action = self.improvement()
        with self.assertRaises(ValidationError):
            action.action_plan()
        action.write(
            {
                "decision": "Correct support",
                "effectiveness_criterion": "Observed errors disappear",
                "verification_plan": "Review a later fictional training",
            }
        )
        action.action_plan()
        with self.assertRaises(ValidationError):
            action.action_implement()
        action.write({"implementation": "Corrected fictional PDF", "output_reference": "Support V2 / revision 2"})
        action.action_implement()
        self.assertEqual(action.state, "done")
        self.assertFalse(action.verified_at)
        with self.assertRaises(ValidationError):
            action.action_verify(True, "Too early")
        action.action_check_effectiveness()
        with self.assertRaises(ValidationError):
            action.action_verify(False, "Still incorrect")
        action.action_verify(False, "Review still finds errors", "Correct V3 and review again")
        old = action.event_ids[-1].details
        action.action_replan("Documented follow-up")
        action.action_plan()
        action.action_implement()
        action.action_check_effectiveness()
        action.action_verify(True, "Later review confirms the criterion")
        action.action_verify(True, "Later review confirms the criterion")
        self.assertIn(old, action.event_ids.mapped("details"))
        self.assertEqual(action.verifier_id, self.quality)
        self.assertEqual(action.state, "effective")

    def test_explicit_staff_scope_search_export_and_withdrawal(self):
        row = self.complaint()
        action = self.improvement(row)
        outsider = new_test_user(
            self.env, login="s093_supervisor", groups="training_management.group_training_supervisor,base.group_user"
        )
        for user in (self.other_quality, self.portal, self.portal_b, outsider):
            with self.subTest(user=user.login):
                self.assertFalse(row.with_user(user).has_access("read"))
                self.assertFalse(action.with_user(user).has_access("read"))
                with self.assertRaises(AccessError):
                    row.with_user(user).read(["name", "description"])
        self.assertNotIn(row.id, self.env["training.complaint"].with_user(self.other_quality).search([]).ids)
        self.assertFalse(
            self.env["training.complaint"].with_user(self.other_quality)._read_group([], ["state"], ["__count"])
        )
        self.other_quality.group_ids = [Command.link(self.env.ref("base.group_allow_export").id)]
        with self.assertRaises(AccessError):
            row.with_user(self.other_quality).export_data(["description"])
        row.with_user(self.coordinator).write({"treatment": "Assigned coordinator treatment"})
        with self.assertRaises(AccessError):
            row.with_user(self.coordinator).action_resolve()
        row.write({"member_ids": [Command.clear()], "responsible_id": self.quality.id})
        self.assertFalse(row.with_user(self.coordinator).has_access("read"))
        row.write({"quality_id": self.other_quality.id, "responsible_id": self.other_quality.id})
        self.assertFalse(row.with_user(self.quality).has_access("read"))
        self.assertFalse(action.with_user(self.quality).has_access("read"))
        self.assertTrue(action.with_user(self.other_quality).has_access("read"))

    def test_files_binary_tokens_chatter_and_provenance(self):
        row = self.complaint()
        file = (
            self.env["training.quality.file"]
            .with_user(self.quality)
            .create(
                {
                    "complaint_id": row.id,
                    "name": "Fictional private evidence.pdf",
                    "source": "Original fictional document",
                    "data": BinaryBytes(PDF),
                }
            )
        )
        original = file.data.content
        self.assertEqual(file.create_uid, self.quality)
        self.assertEqual(file.company_id, row.company_id)
        token = limited_field_access_token(file, "data", scope="binary")
        for user in (self.portal, self.other_quality, self.portal_b):
            self.assertFalse(file.with_user(user).has_access("read"))
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._get_stream_from(file.sudo(), "data")
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._find_record(
                    res_model=file._name, res_id=file.id, field="data", access_token=token
                )
        with self.assertRaises(AccessError):
            self.env["ir.binary"].with_user(self.quality)._get_stream_from(file, "source")
        self.env["ir.binary"].with_user(self.quality)._get_stream_from(file, "data", filename_field="source")
        with self.assertRaises(AccessError):
            file.write({"data": BinaryBytes(b"replacement")})
        with self.assertRaises(AccessError):
            self.env["ir.attachment"].with_user(self.quality).create(
                {"name": "leak.pdf", "res_model": row._name, "res_id": row.id, "raw": PDF, "public": True}
            )
        with self.assertRaises(AccessError):
            self.env["mail.message"].with_user(self.quality).create(
                {"model": row._name, "res_id": row.id, "body": "Secret"}
            )
        with self.assertRaises(AccessError):
            self.env["mail.activity"].with_user(self.quality).create(
                {
                    "res_model_id": self.env["ir.model"]._get_id(row._name),
                    "res_id": row.id,
                    "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
                    "user_id": self.other_quality.id,
                    "summary": "Secret",
                }
            )
        self.assertEqual(file.data.content, original)
        row.write({"member_ids": [Command.clear()], "responsible_id": self.quality.id})
        self.assertFalse(file.with_user(self.coordinator).has_access("read"))
        self.assertFalse(row.event_ids.with_user(self.coordinator).has_access("read"))

    def test_portal_intake_idempotence_original_and_reply_projection(self):
        enrollment = self.intake()
        service = self.env["training.quality.service"].with_user(self.portal)
        key = str(uuid4())
        row = service._receive(enrollment.id, key, "Fictional complaint", "Original message")
        self.assertEqual(service._receive(enrollment.id, key, "Repeated", "Repeated").id, row.id)
        self.assertFalse(row.with_user(self.coordinator).has_access("read"))
        row = row.with_user(self.quality)
        row.write({"treatment": "SECRET INTERNAL PROCESS", "reply": "DRAFT REPLY"})
        self.assertFalse(service._values(row)["reply"])
        self.assertNotIn("treatment", service._values(row))
        self.resolve(row)
        self.assertEqual(service._values(row)["reply"], "Communicable reply")
        row.action_reopen("Fictional reason")
        self.assertFalse(service._values(row)["reply"])
        row.action_revoke_portal("Explicit withdrawal")
        with self.assertRaises(AccessError):
            service._values(row)
        with self.assertRaises(AccessError):
            service._receive(enrollment.id, key, "Repeated", "Repeated")

    def test_portal_eligibility_expiry_revocation_and_forged_enrollment(self):
        enrollment = self.intake()
        service = self.env["training.quality.service"].with_user(self.portal)
        self.env.cr.execute(
            "UPDATE training_enrollment SET access_end=%s WHERE id=%s",
            [fields.Datetime.now() - timedelta(days=1), enrollment.id],
        )
        enrollment.invalidate_recordset()
        row = service._receive(enrollment.id, str(uuid4()), "Delayed complaint", "After normal material expiry")
        with self.assertRaises(AccessError):
            self.env["training.quality.service"].with_user(self.portal_b)._values(row)
        with self.assertRaises(AccessError):
            self.env["training.quality.service"].with_user(self.portal_b)._receive(
                enrollment.id, str(uuid4()), "Forged", "Forged"
            )
        enrollment.action_revoke_access(reason="Fictional access withdrawal")
        with self.assertRaises(AccessError):
            service._values(row)

    def test_holds_deadlines_unapproved_policy_and_forged_defaults(self):
        row = self.complaint(due_date=fields.Date.today() - timedelta(days=1))
        self.assertTrue(row.overdue)
        self.assertIn(
            row.id, self.env["training.complaint"].with_user(self.quality).search([("overdue", "=", True)]).ids
        )
        row.write({"frozen": True})
        with self.assertRaises(ValidationError):
            row.action_start()
        with self.assertRaises(AccessError):
            row.with_user(self.coordinator).write({"frozen": False})
        row.write({"frozen": False})
        self.resolve(row).action_close()
        row.invalidate_recordset()
        self.assertFalse(row.overdue)
        row2 = self.complaint()
        self.assertEqual(row2.state, "received")
        self.assertFalse(row2.closed_at)
        with self.assertRaises(AccessError):
            self.complaint(state="closed")
        foreign = self.env["res.company"].create({"name": "Fictional other operating company"})
        with self.assertRaises((AccessError, ValidationError)):
            self.complaint(company_id=foreign.id)

    def test_minimal_s08_summary_and_closed_dossier(self):
        row = self.resolve(self.complaint())
        dossier = self.dossier(row.enrollment_id.with_user(self.coordinator))
        wizard = (
            self.env["training.quality.export"]
            .with_user(self.quality)
            .create(
                {
                    "complaint_id": row.id,
                    "dossier_id": dossier.id,
                    "summary": "Approved minimal summary without third-party details",
                }
            )
        )
        action = wizard.action_export()
        proof = self.env["training.proof"].with_user(self.quality).browse(action["res_id"])
        self.assertTrue(proof.data.content.startswith(b"%PDF-"))
        self.assertEqual(proof.confidentiality, "sensitive")
        self.assertEqual(proof.category, "incidents")
        self.assertFalse(proof.client_shared)
        self.assertFalse(proof.validated_at)
        self.assertEqual(wizard.action_export()["res_id"], proof.id)
        proof.action_validate()
        preserved = proof.data.content
        row.action_reopen("Additional facts")
        self.resolve(row)
        wizard.summary = "A second explicitly approved summary"
        revised = self.env["training.proof"].with_user(self.quality).browse(wizard.action_export()["res_id"])
        self.assertEqual(revised.previous_id, proof)
        self.assertEqual(proof.data.content, preserved)
        with self.assertRaises(AccessError):
            wizard.with_user(self.other_quality).action_export()
        with self.assertRaises(AccessError):
            self.env["report.training_management.quality_summary"].with_user(self.portal)._get_report_values(
                [wizard.id]
            )

        # Fixture a closed target to exercise the export guard independently of S08's own closure tests.
        self.env.cr.execute("UPDATE training_closure SET state='closed' WHERE id=%s", [dossier.id])
        dossier.invalidate_recordset()
        with self.assertRaises(ValidationError):
            wizard.action_export()

    def test_native_form_workflow(self):
        row = self.complaint()
        with Form(row) as form:
            form.treatment = "Fictional treatment"
            form.reply = "Fictional communicable reply"
        row.action_start()
        row.action_resolve()
        row.action_close()

    def test_default_context_cannot_forge_workflow_or_file_audit(self):
        row = self.complaint()
        creator = (
            self.env["training.complaint"]
            .with_user(self.quality)
            .with_context(
                default_state="closed",
                default_closed_at=fields.Datetime.now(),
                default_submission_key="forged",
                default_portal_revoked=True,
            )
        )
        created = creator.create(
            {
                "name": "Fictional safe defaults",
                "description": "Original",
                "quality_id": self.quality.id,
                "retention_id": self.retention.id,
                "due_date": fields.Date.today(),
                "complainant_id": self.portal.partner_id.id,
            }
        )
        self.assertEqual(created.state, "received")
        self.assertFalse(created.closed_at or created.submission_key or created.portal_revoked)
        file = (
            self.env["training.quality.file"]
            .with_user(self.quality)
            .with_context(
                default_company_id=999999,
                default_sha256="forged",
            )
            .create({"complaint_id": row.id, "name": "safe.txt", "source": "Fictional", "data": BinaryBytes(b"x")})
        )
        self.assertEqual(file.company_id, row.company_id)
        self.assertNotEqual(file.sha256, "forged")
        row.write({"frozen": True})
        with self.assertRaises(ValidationError):
            self.env["training.quality.file"].with_user(self.quality).create(
                {
                    "complaint_id": row.id,
                    "name": "held.txt",
                    "source": "Fictional",
                    "data": BinaryBytes(b"x"),
                }
            )

    def test_portal_complaint_remains_accessible_after_enrollment_closure(self):
        enrollment = self.intake()
        self.env.cr.execute("UPDATE training_enrollment SET state='closed' WHERE id=%s", [enrollment.id])
        enrollment.invalidate_recordset()
        service = self.env["training.quality.service"].with_user(self.portal)
        row = service._receive(enrollment.id, str(uuid4()), "After training", "Fictional complaint")
        self.assertEqual(service._values(row)["description"], "Fictional complaint")
        row.with_user(self.quality).action_revoke_portal("Fictional explicit withdrawal")
        with self.assertRaises(AccessError):
            service._values(row)

    def test_private_activity_cannot_be_reparented_and_origin_is_consistent(self):
        row = self.complaint()
        activity = self.env["mail.activity"].create(
            {
                "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                "res_id": self.coordinator.partner_id.id,
                "user_id": self.coordinator.id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
            }
        )
        with self.assertRaises(AccessError):
            activity.write({"res_model_id": self.env["ir.model"]._get_id(row._name), "res_id": row.id})
        with self.assertRaises(ValidationError):
            self.improvement(row, origin="review")
        other = self.complaint()
        file = (
            self.env["training.quality.file"]
            .with_user(self.quality)
            .create(
                {
                    "complaint_id": row.id,
                    "name": "original.txt",
                    "source": "Fictional",
                    "data": BinaryBytes(b"x"),
                }
            )
        )
        with self.assertRaises(ValidationError):
            self.env["training.quality.file"].with_user(self.quality).create(
                {
                    "complaint_id": other.id,
                    "previous_id": file.id,
                    "name": "wrong.txt",
                    "source": "Fictional",
                    "data": BinaryBytes(b"y"),
                }
            )


@tagged("post_install", "-at_install")
class TestQualityHttp(QualityCase, HttpCase):
    def test_portal_submission_csrf_peer_denial_and_private_files(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(["training_management"], ["fr_FR"])
        self.portal.write({"lang": "fr_FR"})
        if "website" in self.env:
            french = self.env.ref("base.lang_fr")
            self.env["website"].search([]).write(
                {"language_ids": [Command.set(french.ids)], "default_lang_id": french.id}
            )
        enrollment = self.intake()
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open("/my/training-complaints/new")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Déposer une réclamation confidentielle", page.text)
        self.assertIn("Sélectionnez votre formation", page.text)
        tree = html.fromstring(page.content)
        key = tree.xpath('//input[@name="submission_key"]/@value')[0]
        csrf = tree.xpath('//input[@name="csrf_token"]/@value')[0]
        result = self.url_open(
            "/my/training-complaints/new",
            data={
                "csrf_token": csrf,
                "submission_key": key,
                "enrollment_id": enrollment.id,
                "subject": "HTTP private complaint",
                "description": "Original confidential message",
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertIn("HTTP private complaint", result.text)
        row = self.env["training.complaint"].sudo().search([("submission_key", "=", key)])
        self.assertEqual(len(row), 1)
        self.resolve(row.with_user(self.quality))
        self.assertIn("Communicable reply", self.url_open("/my/training-complaints/%s" % row.id).text)
        self.assertNotIn("PRIVATE internal treatment", self.url_open("/my/training-complaints/%s" % row.id).text)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open("/my/training-complaints/%s" % row.id).status_code, 404)
        self.assertNotIn("HTTP private complaint", self.url_open("/my/training-complaints").text)
        self.authenticate(None, None)
        self.assertEqual(self.url_open("/my/training-complaints/%s" % row.id).status_code, 200)  # Native login page.
