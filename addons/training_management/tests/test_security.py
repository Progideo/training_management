"""SEC01–02: transversal gaps, complementing the existing workflow suites."""

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools.misc import limited_field_access_token

from .test_preparation import PreparationCase


class SecurityCase(PreparationCase):
    def confidential_file(self):
        delivery = self.delivery()
        adaptation = self.adaptation(delivery)
        attachment = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "CONFIDENTIAL-S11.pdf",
                    "res_model": adaptation._name,
                    "res_id": adaptation.id,
                    "raw": self.program.pdf_attachment_id.raw.content,
                    "mimetype": "application/pdf",
                }
            )
        )
        return delivery, adaptation, attachment


@tagged("post_install", "-at_install")
class TestSecurity(SecurityCase):
    def test_adaptation_policy_mail_and_current_identity(self):
        delivery, adaptation, attachment = self.confidential_file()
        policy = self.env["training.document.policy"]
        for source in (attachment, adaptation, adaptation.history_ids[:1]):
            self.assertEqual(policy._document(source)._name, adaptation._name if source == attachment else source._name)
            self.assertTrue(policy.with_user(self.coordinator)._can_read(source.sudo()))
            self.assertFalse(policy.with_user(self.other_coordinator)._can_read(source.sudo()))
            self.assertFalse(policy.with_user(self.portal_b)._can_read(source.sudo()))
        # A private attachment on an unrelated outgoing envelope must not be sent.
        mail = self.env["mail.mail"].create(
            {
                "subject": "Fictional",
                "body_html": "<p>Fictional</p>",
                "email_to": "fictional@example.invalid",
                "attachment_ids": [Command.link(attachment.id)],
            }
        )
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()
        delivery.write({"adaptation_deputy_id": self.other_coordinator.id})
        self.assertTrue(policy.with_user(self.other_coordinator)._can_read(attachment))
        delivery.write({"adaptation_deputy_id": False})
        self.assertFalse(policy.with_user(self.other_coordinator)._can_read(attachment))

    def test_archived_user_cannot_read_search_group_or_export(self):
        delivery = self.delivery()
        enrollment = self.enrollment(delivery)
        samples = (self.course, self.program, delivery, enrollment, delivery.operation_ids)
        # Prime Odoo's rule cache while this actual restricted account is active.
        for record in samples:
            record.with_user(self.coordinator).read(["id"])
        self.coordinator.with_user(self.env.ref("base.user_root")).active = False
        for record in samples:
            model = record.with_user(self.coordinator)
            self.assertFalse(model.search([("id", "in", record.ids)]))
            self.assertFalse(model._read_group([("id", "in", record.ids)], [], ["__count"])[0][0])
            with self.assertRaises(AccessError):
                model.read(["id"])
            with self.assertRaises(AccessError):
                model.export_data(["id"])

    def test_denial_diagnostics_do_not_disclose_private_labels(self):
        _delivery, adaptation, _attachment = self.confidential_file()
        adaptation.enrollment_id.participant_id.sudo().name = "PRIVATE-S11-PERSON"
        self.other_coordinator.sudo().group_ids += self.env.ref("base.group_no_one")
        diagnostic = (
            self.env["ir.access"]
            .with_user(self.other_coordinator)
            ._make_record_access_error(adaptation.with_user(self.other_coordinator), "read")
        )
        self.assertNotIn("PRIVATE-S11-PERSON", str(diagnostic))
        self.assertNotIn("SECRET S04", str(diagnostic))

    def test_file_audit_has_identity_and_scope_without_content(self):
        _delivery, adaptation, attachment = self.confidential_file()
        binary = self.env["ir.binary"].with_user(self.coordinator)
        with patch("odoo.addons.training_management.models.training_security._logger.info") as log:
            binary._get_stream_from(attachment.with_user(self.coordinator).sudo(), "raw")
        self.assertEqual(log.call_count, 1)
        args = log.call_args.args
        self.assertEqual(args[1:5], (self.coordinator.id, self.company.id, adaptation._name, adaptation.id))
        self.assertNotIn("CONFIDENTIAL-S11", str(args))
        self.assertNotIn("SECRET S04", str(args))
        with patch("odoo.addons.training_management.models.training_security._logger.info") as log:
            with self.assertRaises(AccessError):
                binary.with_user(self.other_coordinator)._get_stream_from(attachment.sudo(), "raw")
        self.assertFalse(any("file prepared" in str(call) for call in log.call_args_list))

    def test_native_export_identifier_scope_and_immutable_manifest(self):
        delivery = self.delivery()
        enrollment = self.enrollment(delivery)
        audit = self.env["training.export.audit"].with_user(self.coordinator)
        prior = audit.search([])
        enrollment.export_data(["id", "state"])
        created = audit.search([]) - prior
        self.assertEqual(len(created), 1)
        self.assertEqual(created.actor_id, self.coordinator)
        self.assertEqual(
            created.manifest,
            {
                "model": enrollment._name,
                "ids": enrollment.ids,
                "fields": [["id"], ["state"]],
                "population": 1,
            },
        )
        self.assertEqual(len(created.sha256), 64)
        self.assertNotIn(enrollment.participant_id.name, str(created.manifest))
        self.assertFalse(created.with_user(self.other_coordinator).search([("id", "=", created.id)]))
        with self.assertRaises(AccessError):
            created.write({"manifest": {}})
        with self.assertRaises(AccessError):
            created.unlink()
        with self.assertRaises(ValidationError):
            created.sudo().unlink()
        with self.assertRaises(AccessError):
            audit.create({"actor_id": self.coordinator.id})
        # A guessed external-id-only export must not bypass the source rules.
        self.internal.sudo().group_ids += self.env.ref("base.group_allow_export")
        with self.assertRaises(AccessError):
            enrollment.with_user(self.internal).export_data(["id"])
        self.assertEqual(audit.search_count([]), len(prior) + 1)


@tagged("post_install", "-at_install")
class TestSecurityHttp(SecurityCase, HttpCase):
    def test_confidential_pdf_preview_rechecks_role_and_cache(self):
        delivery, _adaptation, attachment = self.confidential_file()
        preview = f"/mail/attachment/pdf_first_page/{attachment.id}?access_token={attachment._get_ownership_token()}"
        token = limited_field_access_token(attachment, "raw", scope="binary")
        download = f"/web/content/{attachment.id}?access_token={token}&unique=s11&download=true"
        self.authenticate(self.other_coordinator.login, self.other_coordinator.login)
        for url in (preview, download):
            self.assertEqual(self.url_open(url).status_code, 404)
        delivery.write({"adaptation_deputy_id": self.other_coordinator.id})
        for url in (preview, download):
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertNotIn("public", response.headers["Cache-Control"])
        delivery.write({"adaptation_deputy_id": False})
        for url in (preview, download):
            response = self.url_open(url)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("PRIVATE-S11", response.text)
        self.authenticate(None, None)
        self.assertEqual(self.url_open(preview).status_code, 404)
        ordinary = self.env["ir.attachment"].create(
            {"name": "ordinary.pdf", "raw": self.program.pdf_attachment_id.raw.content}
        )
        ordinary_url = f"/mail/attachment/pdf_first_page/{ordinary.id}?access_token={ordinary._get_ownership_token()}"
        self.assertEqual(self.url_open(ordinary_url).status_code, 200)
