"""S05 first increment: real restricted identities, native binaries, stable versions."""

from datetime import timedelta
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.misc import limited_field_access_token

from .test_enrollment import EnrollmentCase

PDF = b"%PDF-1.4\nFictional private training PDF\n%%EOF"


@tagged("post_install", "-at_install")
class MaterialCase(EnrollmentCase):
    def material(self, **values):
        return (
            self.env["training.material"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "PRIVATE S05 SUPPORT",
                    "program_id": self.program.id,
                    "filename": "fictional.pdf",
                    "data": BinaryBytes(PDF),
                    **values,
                }
            )
        )

    def opened(self, delivery=None):
        e = self.admitted(delivery)
        e.action_authorize(reason="Fictional authorization")
        e.action_open_access(reason="Fictional opening")
        return e

    def scheduled_session(self, delivery):
        return (
            self.env["training.session"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional mixed session",
                    "delivery_id": delivery.id,
                    "instructor_id": self.portal_b.partner_id.id,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/room",
                    "start_date": "2027-01-04",
                    "end_date": "2027-01-04",
                    "start_hour": 9,
                    "end_hour": 12,
                }
            )
        )

    def attachment(self, material):
        return (
            self.env["ir.attachment"]
            .sudo()
            .search([("res_model", "=", "training.material"), ("res_id", "=", material.id), ("res_field", "=", "data")])
        )


@tagged("post_install", "-at_install")
class TestTrainingMaterial(MaterialCase):
    def test_native_forms_references_no_file_copy_and_version_freeze(self):
        with Form(
            self.env["training.material"].with_user(self.coordinator).with_context(default_program_id=self.program.id)
        ) as form:
            form.name = "PRIVATE S05 SUPPORT"
            form.version = "1"
            form.filename = "fictional.pdf"
            form.data = BinaryBytes(PDF)
        material = form.record
        d1, d2 = self.delivery(), self.delivery()
        self.assertEqual(d1.material_assignment_ids.material_id, material)
        self.assertEqual(d2.material_assignment_ids.material_id, material)
        self.assertEqual(len(self.attachment(material)), 1)
        material.data = BinaryBytes(PDF + b"\nCorrection before diffusion")
        before = material.data.content
        self.opened(d1)
        self.assertTrue(material.frozen_at)
        with self.assertRaises(ValidationError):
            material.write({"data": BinaryBytes(PDF + b"changed")})
        action = material.action_new_version()
        v2 = self.material(
            version="2", previous_id=action["context"]["default_previous_id"], data=BinaryBytes(PDF + b"V2")
        )
        self.assertEqual(d1.material_assignment_ids.material_id, material)
        self.assertEqual(self.delivery().material_assignment_ids.material_id, v2)
        d1.action_add_programme_materials()
        d1.action_add_programme_materials()
        self.assertEqual(d1.material_assignment_ids.material_id, material | v2)
        self.assertTrue(v2.frozen_at)
        old_reference = d1.material_assignment_ids.filtered(lambda ref: ref.material_id == material)
        old_reference.action_withdraw()
        self.assertEqual(material.data.content, before)
        self.assertTrue(old_reference.exists())
        with self.assertRaises(ValidationError):
            old_reference.write({"material_id": v2.id})
        with self.assertRaises(ValidationError):
            material.copy()
        with self.assertRaises(AccessError):
            old_reference.unlink()

    def test_scheduled_opening_publishes_a_stable_version_without_cron(self):
        start = fields.Datetime.now() + timedelta(days=1)
        material = self.material()
        delivery = self.delivery(access_policy="fixed", access_start=start, access_end=start + timedelta(days=5))
        enrollment = self.opened(delivery)
        policy = self.env["training.document.policy"].with_user(self.portal)
        self.assertEqual(enrollment._effective_state(), "scheduled")
        self.assertFalse(policy._can_read(material))
        # Publication fixes the selected version even if access starts tomorrow.
        self.assertTrue(material.frozen_at)
        with self.assertRaises(ValidationError):
            material.write({"data": BinaryBytes(PDF + b"changed after publication")})
        later = self.material(delivery_id=delivery.id)
        self.assertTrue(later.frozen_at)
        with patch("odoo.fields.Datetime.now", return_value=start):
            self.assertEqual(enrollment._effective_state(), "active")
            self.assertTrue(policy._can_read(material))
            self.assertTrue(policy._can_read(later))

    def test_relational_and_attachment_exports_cannot_bypass_private_pdf_export_policy(self):
        material = self.material()
        delivery = self.delivery()
        for record, paths in (
            (self.program, ["title", "material_ids/name", "material_ids/data"]),
            (delivery, ["name", "material_assignment_ids/material_id/data"]),
            (self.attachment(material), ["name", "raw"]),
        ):
            with self.assertRaises(UserError):
                record.with_user(self.coordinator).export_data(paths)
        self.assertTrue(self.program.with_user(self.coordinator).export_data(["title"]))
        ordinary = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create({"name": "ordinary.txt", "raw": b"Fictional ordinary"})
        )
        self.assertTrue(ordinary.export_data(["name"]))

    def test_current_enrollment_is_the_only_participant_grant(self):
        material = self.material()
        enrollment = self.opened()
        policy = self.env["training.document.policy"]
        self.assertTrue(policy.with_user(self.portal)._can_read(material))
        self.assertTrue(policy.with_user(self.portal)._can_read(self.program))
        for user in (self.reader, self.internal, self.portal_b, self.env.ref("base.public_user")):
            self.assertFalse(policy.with_user(user)._can_read(material))
            with self.assertRaises(AccessError):
                material.with_user(user).read(["name", "data"])
        with self.assertRaises(UserError):
            material.with_user(self.coordinator).export_data(["name", "data"])
        with self.assertRaises(AccessError):
            material.with_user(self.portal).export_data(["name"])
        with self.assertRaises(AccessError):
            self.program.with_user(self.portal).read(["content"])
        original_programme = self.program._reference_pdf().raw.content
        self.assertEqual(self.program.with_user(self.portal)._reference_pdf().raw.content, original_programme)
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_end):
            self.assertFalse(policy.with_user(self.portal)._can_read(material))
            self.assertFalse(policy.with_user(self.portal)._can_read(self.program))
        enrollment.action_suspend_access(reason="Fictional suspension")
        self.assertFalse(policy.with_user(self.portal)._can_read(material))
        enrollment.action_open_access(reason="Fictional resumption")
        enrollment.action_revoke_authorization(reason="Fictional withdrawal")
        self.assertFalse(policy.with_user(self.portal)._can_read(material))
        self.assertEqual(self.program._reference_pdf().raw.content, original_programme)

    def test_direct_binary_and_attachment_mutation_are_guarded(self):
        material = self.material()
        e = self.opened()
        attachment = self.attachment(material)
        token = limited_field_access_token(attachment, "raw", scope="binary")
        binary = self.env["ir.binary"].with_user(self.portal)
        found = binary._find_record(res_id=attachment.id, field="raw", access_token=token)
        self.assertTrue(binary._get_stream_from(found))
        for user in (self.portal_b, self.reader, self.internal, self.env.ref("base.public_user")):
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._find_record(
                    res_id=attachment.id, field="raw", access_token=token
                )
        for values in (
            {"public": True},
            {"access_token": "forged"},
            {"res_id": 0},
            {"res_field": False},
            {"res_model": "res.partner"},
            {"raw": PDF + b"changed"},
        ):
            with self.assertRaises(ValidationError):
                attachment.write(values)
        with self.assertRaises(ValidationError):
            attachment.copy({"res_model": "res.partner", "res_id": self.customer.id})
        with self.assertRaises(ValidationError):
            self.attachment(material).unlink()
        e.action_revoke_access(reason="Fictional revoke")
        with self.assertRaises(AccessError):
            binary._get_stream_from(found)
        material.action_withdraw()
        self.assertEqual(material.data.content, PDF)

    def test_group_and_company_scope_and_public_defaults(self):
        d1, d2 = self.delivery(), self.delivery()
        group = self.material(delivery_id=d1.id)
        e = self.opened(d2)
        policy = self.env["training.document.policy"].with_user(self.portal)
        self.assertFalse(policy._can_read(group))
        with self.assertRaises(ValidationError):
            self.env["training.material.assignment"].with_user(self.coordinator).create(
                {"delivery_id": d2.id, "material_id": group.id}
            )
        for values in ({"sha256": "forged"}, {"frozen_at": fields.Datetime.now()}, {"withdrawn": True}):
            with self.assertRaises(ValidationError):
                self.material(**values)
        with self.assertRaises(ValidationError):
            self.material(data=BinaryBytes(b"not a PDF"))
        with self.assertRaises(AccessError):
            self.env["training.material"].with_user(self.portal).create({"name": "forged"})
        with self.assertRaises(ValidationError):
            self.env["ir.attachment"].with_context(
                default_res_model="training.material", default_res_id=group.id
            ).create({"name": "orphan", "raw": PDF})
        foreign_course = self.env["training.course"].create(
            {"name": "Fictional foreign PDF", "company_id": self.other_company.id}
        )
        foreign_program = self.program.copy({"course_id": foreign_course.id, "version": "Foreign PDF"})
        multi_coordinator = self.coordinator.with_context(allowed_company_ids=(self.company | self.other_company).ids)
        self.coordinator.company_ids = [Command.set((self.company | self.other_company).ids)]
        foreign_material = (
            self.env["training.material"]
            .with_user(multi_coordinator)
            .with_context(allowed_company_ids=(self.company | self.other_company).ids)
            .create(
                {
                    "name": "Fictional foreign support",
                    "program_id": foreign_program.id,
                    "filename": "foreign.pdf",
                    "data": BinaryBytes(PDF),
                }
            )
        )
        self.assertEqual(self.attachment(foreign_material).company_id, self.other_company)
        self.assertFalse(policy._can_read(foreign_material))
        e.action_revoke_access(reason="Fictional revoke")
        self.assertFalse(policy._can_read(group))

    def test_trainer_assignment_and_native_company_boundaries(self):
        material = self.material()
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        session = self.scheduled_session(delivery)
        delivery.action_confirm()
        self.assertTrue(material.frozen_at)
        policy = self.env["training.document.policy"].with_user(self.portal_b)
        self.assertTrue(policy._can_read(material))
        self.assertTrue(policy._can_read(self.program))
        session._apply_schedule({"instructor_id": self.customer.id}, reason="Fictional reassignment")
        self.assertFalse(policy._can_read(material))
        e = self.opened(delivery)
        self.portal.write({"company_ids": [Command.set(self.other_company.ids)], "company_id": self.other_company.id})
        self.assertFalse(self.env["training.document.policy"].with_user(self.portal)._can_read(material))
        self.portal.write({"company_ids": [Command.set(self.company.ids)], "company_id": self.company.id})
        self.assertTrue(self.env["training.document.policy"].with_user(self.portal)._can_read(material))
        self.portal.active = False
        self.assertFalse(self.env["training.document.policy"].with_user(self.portal)._can_read(material))
        self.assertNotEqual(e._effective_state(), "active")
        with self.assertRaises(AccessError):
            material.with_user(self.reader).write({"name": "forbidden"})
        self.coordinator.write(
            {"company_ids": [Command.set(self.other_company.ids)], "company_id": self.other_company.id}
        )
        with self.assertRaises(AccessError):
            material.with_user(self.coordinator).read(["data"])

    def test_private_pdf_cannot_leave_through_an_unrelated_mail(self):
        material = self.material()
        self.opened()
        mail = self.env["mail.mail"].create(
            {
                "subject": "Fictional unrelated mail",
                "body_html": "Fictional",
                "email_from": "sender@example.invalid",
                "recipient_ids": [Command.set(self.portal.partner_id.ids)],
                "attachment_ids": [Command.set(self.attachment(material).ids)],
            }
        )
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()
        native = self.env["ir.attachment"].create({"name": "ordinary.txt", "raw": b"Fictional ordinary"})
        mail.attachment_ids = [Command.set(native.ids)]
        self.assertTrue(mail._prepare_outgoing_list())


@tagged("post_install", "-at_install")
class TestTrainingMaterialHttp(MaterialCase, HttpCase):
    def test_participant_schedule_and_trainer_download_follow_their_own_grants(self):
        material = self.material()
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        session = self.scheduled_session(delivery)
        delivery.action_confirm()
        enrollment = self.opened(delivery)
        enrollment.instructor_summary = "PRIVATE INSTRUCTOR ONLY"
        self.assertTrue(material.frozen_at)
        self.assertEqual(delivery.material_assignment_ids.material_id, material)
        file_url = f"/web/content/{self.attachment(material).id}"
        participant_url = f"/my/trainings/{enrollment.id}"
        trainer_url = f"/my/training-sessions/{session.id}"
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(participant_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(session.name, response.text)
        self.assertIn(session.meeting_url, response.text)
        self.assertNotIn(enrollment.instructor_summary, response.text)
        self.assertEqual(self.url_open(trainer_url).status_code, 404)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        response = self.url_open(trainer_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn(material.name, response.text)
        self.assertEqual(self.url_open(file_url).status_code, 200)
        self.assertEqual(self.url_open(participant_url).status_code, 404)
        session._apply_schedule({"instructor_id": self.customer.id}, reason="Fictional reassignment")
        self.assertEqual(self.url_open(trainer_url).status_code, 404)
        self.assertEqual(self.url_open(file_url).status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(file_url).status_code, 200)

    def test_native_zip_rechecks_access_and_disables_private_caching(self):
        material = self.material()
        enrollment = self.opened()
        attachment = self.attachment(material)
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(
            "/mail/attachment/zip",
            data={"file_ids": str(attachment.id), "zip_name": "training.zip", "csrf_token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(archive.read(archive.namelist()[0]), PDF)
        enrollment.action_suspend_access(reason="Fictional suspension")
        response = self.url_open(
            "/mail/attachment/zip",
            data={"file_ids": str(attachment.id), "zip_name": "training.zip", "csrf_token": self.csrf_token()},
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertNotIn(PDF, response.content)

    def test_native_pdf_preview_ownership_token_never_replaces_current_access(self):
        material = self.material(data=BinaryBytes(self.program.pdf_attachment_id.raw.content))
        enrollment = self.opened()
        attachments = self.attachment(material) | self.program.pdf_attachment_id
        urls = [f"/mail/attachment/pdf_first_page/{a.id}?access_token={a._get_ownership_token()}" for a in attachments]
        self.authenticate(self.portal_b.login, self.portal_b.login)
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        self.authenticate(self.portal.login, self.portal.login)
        for url in urls:
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.authenticate(self.portal_b.login, self.portal_b.login)
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        self.authenticate(self.portal.login, self.portal.login)
        enrollment.action_suspend_access(reason="Fictional suspension")
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        self.authenticate(None, None)
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        ordinary = self.env["ir.attachment"].create(
            {"name": "ordinary.pdf", "raw": self.program.pdf_attachment_id.raw.content}
        )
        ordinary_url = f"/mail/attachment/pdf_first_page/{ordinary.id}?access_token={ordinary._get_ownership_token()}"
        self.assertEqual(self.url_open(ordinary_url).status_code, 200)

    def test_portal_and_all_native_file_routes_recheck_the_current_grant(self):
        material = self.material()
        enrollment = self.opened()
        attachment = self.attachment(material)
        programme_file = self.program.pdf_attachment_id
        field_token = limited_field_access_token(attachment, "raw", scope="binary")
        urls = [
            f"/web/content/{attachment.id}",
            f"/web/content/training.material/{material.id}/data",
            f"/web/content/{attachment.id}?access_token={field_token}&unique=forever",
            f"/web/image/{attachment.id}?download=true",
            f"/web/content/{programme_file.id}",
        ]
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open("/my/trainings")
        self.assertEqual(response.status_code, 200)
        response = self.url_open(f"/my/trainings/{enrollment.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(material.name, response.text)
        self.assertIn("No scheduled session", response.text)
        self.assertNotIn("Participants and useful instructions", response.text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        for url in urls:
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn("no-store", response.headers["Cache-Control"], url)
        etag = response.headers.get("ETag")
        response = self.url_open(urls[0], headers={"Range": "bytes=0-8"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, PDF[:9])
        self.authenticate(self.portal_b.login, self.portal_b.login)
        for url in urls + [f"/my/trainings/{enrollment.id}"]:
            response = self.url_open(url)
            self.assertEqual(response.status_code, 404, url)
            self.assertNotIn(material.name, response.text)
        self.authenticate(self.portal.login, self.portal.login)
        with patch("odoo.fields.Datetime.now", return_value=enrollment.access_end + timedelta(seconds=1)):
            for url in urls:
                response = self.url_open(url, headers={"If-None-Match": etag or '"cached"'})
                self.assertEqual(response.status_code, 404, url)
        self.authenticate(None, None)
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 404, url)
