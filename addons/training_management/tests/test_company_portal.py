from lxml import html

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.misc import limited_field_access_token

from .test_preparation import PreparationCase


@tagged("post_install", "-at_install")
class TestCompanyPortal(PreparationCase, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal.write({"group_ids": [Command.link(cls.env.ref("base.group_allow_export").id)]})
        cls.client_b = cls.env["res.partner"].create({"name": "Fictional Client B"})

    def grant(self, allocation, user=None):
        grant = (
            self.env["training.company.authorization"]
            .with_user(self.coordinator)
            .create(
                {
                    "company_id": self.company.id,
                    "customer_id": allocation.customer_id.commercial_partner_id.id,
                    "user_id": (user or self.portal).id,
                    "allocation_ids": [Command.set(allocation.ids)],
                }
            )
        )
        grant.action_confirm()
        return grant

    def variant(self, delivery, **values):
        return (
            self.env["training.intra.version"]
            .with_user(self.coordinator)
            .create(
                {
                    "delivery_id": delivery.id,
                    "customer_id": self.customer.id,
                    "version": "Client-1",
                    "objectives": "Client A objectives",
                    "business_cases": "Client A case",
                    "instructions": "Client A instructions",
                    "data": BinaryBytes(b"%PDF-1.4\nClient A confidential scope\n%%EOF"),
                    "filename": "client-scope.pdf",
                    **values,
                }
            )
        )

    def test_company_scope_nomination_documents_and_revocation(self):
        delivery, session = self.planned(capacity=20)
        allocation = self.lot(delivery)
        other = self.lot(delivery, customer_id=self.client_b.id, source_reference="CLIENT-B", quantity=1)
        grant = self.grant(allocation)
        own = self.enrollment(
            delivery,
            allocation_id=allocation.id,
            free_reason=False,
            participant_objectives="PRIVATE participant objectives",
        )
        peer = self.enrollment(
            delivery,
            allocation_id=other.id,
            free_reason=False,
            participant_id=self.portal_b.partner_id.id,
            user_id=self.portal_b.id,
        )
        doc = (
            self.env["training.company.document"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Client A authorised document",
                    "allocation_id": allocation.id,
                    "data": BinaryBytes(b"%PDF-1.4\nClient A allowed file"),
                    "filename": "client-a.pdf",
                    "released": True,
                }
            )
        )
        hidden = self.env["training.company.document"].create(
            {
                "name": "Client B secret document",
                "allocation_id": other.id,
                "data": BinaryBytes(b"%PDF-1.4\nClient B secret file"),
                "filename": "client-b.pdf",
                "released": True,
            }
        )
        service = self.env["training.company.service"].with_user(self.portal)
        self.assertEqual([r["id"] for r in service._rows()], allocation.ids)
        nomination = service._nominate(allocation.id, "Fictional Nominee", "nominee@example.invalid")
        self.assertEqual(service._nominate(allocation.id, "Fictional Nominee", "nominee@example.invalid"), nomination)
        self.assertFalse(nomination.enrollment_id)
        self.assertEqual(own.state, "requested")
        self.assertNotEqual(own._effective_state(), "active")
        with self.assertRaises(AccessError):
            service._allocation(other.id)
        for record in (grant, nomination, doc, own, peer):
            with self.subTest(model=record._name), self.assertRaises(AccessError):
                record.with_user(self.portal).read()
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(f"/my/company-trainings/{allocation.id}")
        self.assertEqual(response.status_code, 200)
        for visible in (session.name, own.participant_id.name, doc.name, nomination.name):
            self.assertIn(visible, response.text)
        for secret in (peer.participant_id.name, hidden.name, "PRIVATE participant objectives"):
            self.assertNotIn(secret, response.text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        token = html.fromstring(response.content).xpath("//input[@name='csrf_token']/@value")[0]
        enrollment_count = self.env["training.enrollment"].search_count([])
        self.url_open(
            f"/my/company-trainings/{allocation.id}",
            data={"csrf_token": token, "name": "Fictional HTTP Nominee", "email": ""},
        )
        self.assertEqual(self.env["training.enrollment"].search_count([]), enrollment_count)
        signed = limited_field_access_token(doc, "data", scope="binary")
        self.assertIn(
            self.url_open(
                f"/web/content?model=training.company.document&amp;id={doc.id}&amp;field=data&amp;access_token={signed}".replace(
                    "&amp;", "&"
                )
            ).status_code,
            (403, 404),
        )
        own_url = f"/my/company-trainings/{allocation.id}/documents/{doc.id}"
        self.assertEqual(self.url_open(own_url).content, doc.data.content)
        for url in (
            f"/my/company-trainings/{other.id}",
            f"/my/company-trainings/{allocation.id}/documents/{hidden.id}",
            f"/web/content/training.company.document/{doc.id}/data",
        ):
            self.assertIn(self.url_open(url).status_code, (403, 404))
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(own_url).status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        grant.action_revoke()
        self.assertEqual(self.url_open(own_url).status_code, 404)
        self.assertEqual(self.url_open(f"/my/company-trainings/{allocation.id}").status_code, 404)
        with self.assertRaises(ValidationError):
            grant.action_confirm()
        doc.released = False
        with self.assertRaises(ValidationError):
            doc.write({"data": BinaryBytes(b"%PDF-changed")})

    def test_variant_approval_version_history_and_client_isolation(self):
        delivery = self.delivery()
        allocation = self.lot(delivery)
        grant = self.grant(allocation)
        original = bytes(self.program.pdf_attachment_id.raw)
        version = self.variant(delivery)
        self.assertEqual(version.program_id, self.program)
        with self.assertRaises(AccessError):
            self.delivery(intra_version_id=version.id)
        with self.assertRaises(AccessError):
            self.env["training.delivery"].with_user(self.coordinator).with_context(
                default_intra_version_id=version.id
            ).create(
                {
                    "name": "Forged client version",
                    "program_id": self.program.id,
                    "kind": "autonomous",
                    "access_policy": "duration",
                    "access_days": 10,
                }
            )
        with self.assertRaises(ValidationError):
            delivery.action_confirm()
        with self.assertRaises(ValidationError):
            version.action_confirm()
        with self.assertRaises(AccessError):
            version.with_user(self.portal).write({"state": "approved"})
        version.action_submit()
        with self.assertRaises(ValidationError):
            version.write({"objectives": "Changed without a new version"})
        self.authenticate(self.portal.login, self.portal.login)
        url = f"/my/company-trainings/{allocation.id}"
        page = self.url_open(url)
        self.assertIn(version.objectives, page.text)
        token = html.fromstring(page.content).xpath("//input[@name='csrf_token']/@value")[0]
        approve = f"{url}/versions/{version.id}/approve"
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(approve, data={"csrf_token": self.csrf_token()}).status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open(url)
        token = html.fromstring(page.content).xpath("//input[@name='csrf_token']/@value")[0]
        self.assertEqual(self.url_open(approve, data={"csrf_token": token}).status_code, 200)
        self.assertEqual(version.state, "approved")
        self.assertEqual(version.approved_contact_id, self.portal.partner_id)
        self.assertEqual(version.approved_by_id, self.portal)
        approved_at = version.approved_at
        self.url_open(approve, data={"csrf_token": token})
        self.assertEqual(version.approved_at, approved_at)
        version.action_confirm()
        delivery.action_confirm()
        self.assertEqual(delivery.intra_version_id, version)
        successor = self.variant(
            delivery, version="Client-2", previous_id=version.id, objectives="New client objectives"
        )
        successor.action_submit()
        with self.assertRaises(ValidationError):
            successor.action_confirm()
        self.assertEqual(delivery.intra_version_id, version)
        successor.write(
            {
                "agreement_contact_id": self.env["res.partner"]
                .create({"name": "Fictional client approver", "parent_id": self.customer.id})
                .id,
                "approval_reference": "Fictional agreement on Client-2",
            }
        )
        successor.action_record_agreement()
        successor.action_confirm()
        self.assertEqual(delivery.intra_version_id, successor)
        self.assertEqual(version.objectives, "Client A objectives")
        self.assertEqual(bytes(self.program.pdf_attachment_id.raw), original)
        self.assertEqual(successor.program_id, self.program)
        grant.action_revoke()
        self.assertEqual(self.url_open(f"{url}/versions/{version.id}/pdf").status_code, 404)
        with self.assertRaises(AccessError):
            version.with_user(self.portal).export_data(["objectives", "data"])
        with self.assertRaises(ValidationError):
            self.lot(delivery, customer_id=self.client_b.id, source_reference="CROSS-CLIENT", quantity=1)

    def test_native_forms_and_forged_grants_metadata_or_scope(self):
        delivery = self.delivery()
        allocation = self.lot(delivery)
        with Form(self.env["training.company.authorization"].with_user(self.coordinator)) as form:
            form.customer_id = self.customer
            form.user_id = self.portal
            form.allocation_ids.add(allocation)
        grant = form.record
        self.assertEqual(grant.state, "draft")
        with self.assertRaises(AccessError):
            grant.with_user(self.reader).action_confirm()
        with self.assertRaises(ValidationError):
            grant.write({"state": "active", "confirmed_by_id": self.portal.id})
        with self.assertRaises(ValidationError):
            grant.write({"customer_id": self.client_b.id})
        with Form(self.env["training.intra.version"].with_user(self.coordinator)) as form:
            form.delivery_id = delivery
            form.customer_id = self.customer
            form.version = "Native client version"
            form.objectives = "Fictional objectives"
            form.business_cases = "Fictional case"
            form.instructions = "Fictional instructions"
        version = form.record
        self.assertEqual(version.program_id, self.program)
        with self.assertRaises(ValidationError):
            version.write({"approved_at": "2026-10-25 12:00:00"})
