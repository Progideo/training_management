"""P14 verified participation, exact consent, moderation, isolation and withdrawal."""

from unittest.mock import patch

from lxml import html

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tools.translate import load_language

from .test_closure import ClosureCase


class PublicationCase(ClosureCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.program.with_user(cls.coordinator).copy({"version": "P14-public", "public_catalogue": True})
        cls.program.action_validate()
        cls.program.action_publish()
        cls.moderator = new_test_user(
            cls.env,
            login="p14_moderator",
            groups="training_management.group_training_publication_moderator",
            email="moderator@example.invalid",
        )
        cls.portal.partner_id.email = "learner@example.invalid"
        cls.portal_b.partner_id.email = "representative@example.invalid"

    def setUp(self):
        super().setUp()
        transport = patch.object(
            type(self.env["ir.mail_server"]), "send_email", side_effect=AssertionError("No real transport in P14 tests")
        )
        transport.start()
        self.addCleanup(transport.stop)

    def publication(self, delivery, **values):
        return (
            self.env["training.publication"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional P14 request",
                    "delivery_id": delivery.id,
                    "retention_id": self.retention.id,
                    **values,
                }
            )
        )

    def review_request(self):
        delivery, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.review(presence)
        row = self.publication(delivery, enrollment_id=enrollment.id)
        row.action_request_authorization()
        return row, presence

    def consent(self, row, **values):
        return (
            row.with_user(row.owner_id)
            .sudo()
            ._consent(
                definition=row._definition(),
                body="Fictional public opinion" if row.kind == "review" else "",
                accepted=True,
                **values,
            )
        )

    def publish(self, row):
        row.with_user(self.moderator).write(
            {"moderation_reason": "Fictional content, identity and confidentiality checked"}
        )
        row.with_user(self.moderator).action_publish()

    def case_request(self, **values):
        delivery = self.delivery()
        delivery.action_confirm()
        allocation = self.lot(delivery)
        grant = (
            self.env["training.company.authorization"]
            .with_user(self.coordinator)
            .create(
                {
                    "company_id": self.company.id,
                    "customer_id": allocation.customer_id.commercial_partner_id.id,
                    "user_id": self.portal_b.id,
                    "allocation_ids": [Command.set(allocation.ids)],
                }
            )
        )
        grant.action_confirm()
        row = self.publication(
            delivery,
            kind="case",
            allocation_id=allocation.id,
            representative_id=self.portal_b.id,
            authority_reference="Fictional named mandate",
            body="Fictional authorized client case",
            public_context="Fictional approved training context",
            participation_month="2027-01",
            confidential=False,
            **values,
        )
        return row, grant


@tagged("post_install", "-at_install")
class TestTestimonial(PublicationCase):
    def test_native_moderator_form_and_visible_actions(self):
        row, _ = self.review_request()
        self.consent(row)
        with Form(row.with_user(self.moderator)) as form:
            form.moderation_reason = "Fictional native moderation decision"
        arch = row.with_user(self.moderator).get_view(view_type="form")["arch"]
        tree = html.fromstring(arch)
        self.assertTrue(tree.xpath("//button[@name='action_publish']"))
        self.assertTrue(tree.xpath("//field[@name='moderation_reason']"))
        row.with_user(self.moderator).action_publish()
        self.assertTrue(row._public_row())

    def test_review_exact_consent_moderation_public_projection_and_withdrawal(self):
        row, _ = self.review_request()
        self.assertEqual(row.state, "invited")
        self.assertEqual(row.participation_snapshot["minutes"], 90)
        self.assertEqual(row.participation_month, "2027-01")
        self.assertFalse(row._public_row())
        definition = row._definition()
        self.consent(row)
        row.with_user(self.portal).sudo()._consent(
            definition=definition, body="Fictional public opinion", accepted=True
        )
        self.assertEqual(len(row.event_ids), 2)
        self.assertEqual(row.consented_by_id, self.portal)
        self.assertFalse(row.public_identity)
        with self.assertRaises(AccessError):
            row.action_publish()
        self.publish(row)
        public = row._public_row()
        self.assertEqual(public["body"], "Fictional public opinion")
        self.assertNotIn(self.portal.name, str(public))
        self.assertNotIn(self.customer.name, str(public))
        self.assertEqual(set(public), {"kind", "body", "context", "month", "date", "identity"})
        row.with_user(self.moderator).action_publish()
        self.assertEqual(len(row.event_ids), 3)
        row.enrollment_id.action_suspend_access(reason="Fictional suspension after consent")
        row.with_user(self.portal).sudo()._withdraw()
        row.with_user(self.portal).sudo()._withdraw()
        self.assertFalse(row._public_row())
        self.assertEqual(len(row.event_ids), 4)
        with self.assertRaises(ValidationError):
            self.publish(row)

    def test_name_requires_distinct_consent_and_remains_exact(self):
        row, _ = self.review_request()
        with self.assertRaises(ValidationError):
            self.consent(row, identity="name")
        with self.assertRaises(ValidationError):
            row.with_user(self.portal).sudo()._consent(definition=row._definition(), body="Opinion", accepted=False)
        self.consent(row, identity="name", identity_accepted=True)
        exact = row.public_identity
        self.portal.partner_id.name = "Fictional renamed participant"
        self.publish(row)
        self.assertEqual(row._public_row()["identity"], exact)
        with self.assertRaises(ValidationError):
            row.write({"body": "Silently rewritten opinion"})

    def test_inscription_alone_pending_or_invalidated_attendance_is_not_verified(self):
        delivery, session, enrollment = self.scheduled()
        row = self.publication(delivery, enrollment_id=enrollment.id)
        with self.assertRaises(ValidationError):
            row.action_request_authorization()
        presence = self.declare(session, enrollment)
        with self.assertRaises(ValidationError):
            row.action_request_authorization()
        self.review(presence)
        row.action_request_authorization()
        self.consent(row)
        self.service(self.coordinator)._invalidate(
            session.id,
            enrollment.id,
            reason="Fictional invalidation",
            revision=presence.revision,
            definition=self.service()._definition(session),
        )
        with self.assertRaises(ValidationError):
            self.publish(row)

    def test_published_review_hidden_after_attendance_invalidation(self):
        row, presence = self.review_request()
        self.consent(row)
        self.publish(row)
        self.service(self.coordinator)._invalidate(
            presence.session_id.id,
            row.enrollment_id.id,
            reason="Fictional invalidation",
            revision=presence.revision,
            definition=self.service()._definition(presence.session_id),
        )
        self.assertFalse(row._public_row())

    def test_stale_preview_injected_state_and_duplicate_invitations(self):
        row, _ = self.review_request()
        stale = row._definition()
        self.portal.partner_id.name = "Fictional changed preview name"
        with self.assertRaises(ValidationError):
            row.with_user(self.portal).sudo()._consent(definition=stale, body="Opinion", accepted=True)
        row.action_request_authorization()
        notices = self.env["training.publication.notice"].sudo().search([("publication_id", "=", row.id)])
        self.assertEqual(len(notices), 1)
        other = self.publication(row.delivery_id, enrollment_id=row.enrollment_id.id)
        with self.assertRaises(ValidationError):
            other.action_request_authorization()
        with self.assertRaises(ValidationError):
            self.publication(row.delivery_id, enrollment_id=row.enrollment_id.id, state="published")
        with self.assertRaises(ValidationError):
            self.env["training.publication"].with_user(self.coordinator).with_context(
                default_consented_at="2027-01-01"
            ).create(
                {
                    "name": "Forged",
                    "delivery_id": row.delivery_id.id,
                    "enrollment_id": row.enrollment_id.id,
                    "retention_id": self.retention.id,
                }
            )

    def test_peer_company_staff_and_event_mutation_denied(self):
        row, _ = self.review_request()
        for user in (self.portal_b, self.reader, self.internal, self.quality, self.env.ref("base.public_user")):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                row.with_user(user).sudo()._consent(definition=row._definition(), body="Peer opinion", accepted=True)
        for user in (self.portal, self.portal_b, self.reader, self.internal, self.quality):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                row.with_user(user).read(["body"])
        stranger = new_test_user(
            self.env,
            login="p14_foreign_mod",
            groups="training_management.group_training_publication_moderator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
            email="foreign@example.invalid",
        )
        with self.assertRaises(AccessError):
            row.with_user(stranger).action_publish()
        with self.assertRaises(AccessError):
            row.event_ids.write({"reason": "Changed"})
        with self.assertRaises(ValidationError):
            row.event_ids.sudo().unlink()
        with self.assertRaises(UserError):
            row.export_data(["body"])
        with self.assertRaises(ValidationError):
            row.copy()
        with self.assertRaises(ValidationError):
            self.env["ir.attachment"].create(
                {"name": "Unsafe", "res_model": row._name, "res_id": row.id, "raw": b"private"}
            )

    def test_private_notice_rechecked_at_transport_without_doubles(self):
        row, _ = self.review_request()
        notice = self.env["training.publication.notice"].sudo().search([("publication_id", "=", row.id)])
        self.assertTrue(notice._authorized())
        self.assertTrue(notice.mail_id)
        self.assertFalse(notice.mail_id.attachment_ids)
        self.assertFalse(notice.mail_id.recipient_ids)
        notice.mail_id._prepare_outgoing_list()
        notice.mail_id.write({"email_cc": "peer@example.invalid"})
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()
        row.enrollment_id.action_suspend_access(reason="Fictional revoked invitation")
        self.assertFalse(notice._authorized())

    def test_case_exact_customer_authorization_and_separate_company_name(self):
        row, _ = self.case_request(identify_client=True)
        row.action_request_authorization()
        with self.assertRaises(ValidationError):
            self.consent(row)
        with self.assertRaises(ValidationError):
            self.publish(row)
        self.consent(row, identity="name", identity_accepted=True)
        self.publish(row)
        self.assertEqual(row._public_row()["identity"], self.customer.name)
        self.assertEqual(row.consented_by_id, self.portal_b)
        self.assertTrue(row.event_ids.filtered(lambda e: e.state == "authorized").snapshot)
        row.with_user(self.portal_b).sudo()._withdraw()
        self.assertFalse(row._public_row())

    def test_confidential_case_and_revoked_client_grant_stay_private(self):
        row, grant = self.case_request()
        row.write({"confidential": True})
        with self.assertRaises(ValidationError):
            row.action_request_authorization()
        row.write({"confidential": False})
        row.action_request_authorization()
        grant.action_revoke()
        with self.assertRaises(AccessError):
            self.consent(row)
        self.assertFalse(row._public_row())


@tagged("post_install", "-at_install")
class TestPublicationHttp(PublicationCase, HttpCase):
    def test_french_consent_form_and_missing_csrf(self):
        load_language(self.cr, "fr_FR")
        self.env["ir.module.module"].search([("name", "=", "training_management")])._update_translations(
            ["fr_FR"], overwrite=True
        )
        self.portal.lang = "fr_FR"
        if "website" in self.env and "language_ids" in self.env["website"]._fields:
            french = self.env.ref("base.lang_fr")
            self.env["website"].search([]).write(
                {"language_ids": [Command.set(french.ids)], "default_lang_id": french.id}
            )
        row, _ = self.review_request()
        self.authenticate(self.portal.login, self.portal.login)
        url = "/my/training-publications/%s" % row.id
        response = self.url_open(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Autorisation de publication", response.text)
        self.assertIn("Participant vérifié", response.text)
        tree = html.fromstring(response.content)
        self.assertFalse(tree.xpath("//input[@name='accepted' or @name='identity_accepted']/@checked"))
        self.assertTrue(tree.xpath("//label[@for='opinion']"))
        token = tree.xpath("//input[@name='csrf_token']/@value")[0]
        definition = tree.xpath("//input[@name='definition']/@value")[0]
        self.assertEqual(
            self.url_open(url, data={"operation": "consent", "definition": definition, "accepted": "yes"}).status_code,
            400,
        )
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "consent",
                "definition": definition,
                "body": "Fictional preserved unsent opinion",
                "identity": "name",
                "accepted": "yes",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Fictional preserved unsent opinion", response.text)
        self.assertIn("consentement explicite distinct", response.text)
        row.invalidate_recordset()
        self.assertEqual(row.state, "invited")

    def test_native_forms_peer_denial_public_projection_and_withdrawal(self):
        row, _ = self.review_request()
        url = "/my/training-publications/%s" % row.id
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        tree = html.fromstring(response.content)
        token = tree.xpath("//input[@name='csrf_token']/@value")[0]
        definition = tree.xpath("//input[@name='definition']/@value")[0]
        response = self.url_open(
            url,
            data={
                "csrf_token": token,
                "operation": "consent",
                "definition": definition,
                "body": "Fictional <script>alert(1)</script> opinion",
                "accepted": "yes",
                "identity": "anonymous",
            },
        )
        self.assertEqual(response.status_code, 200)
        row.invalidate_recordset()
        self.publish(row)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.assertIn(self.url_open(f"/web/content/training.publication/{row.id}/body").status_code, (403, 404))
        self.authenticate(None, None)
        public_url = f"/formations/{row.program_id.id}/avis"
        response = self.url_open(public_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("Fictional &lt;script&gt;", response.text)
        self.assertNotIn("<script>alert(1)</script>", response.text)
        self.assertNotIn(self.portal.name, response.text)
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(url)
        token = html.fromstring(response.content).xpath("//input[@name='csrf_token']/@value")[0]
        self.url_open(url, data={"csrf_token": token, "operation": "withdraw"})
        self.authenticate(None, None)
        self.assertNotIn("Fictional &lt;script&gt;", self.url_open(public_url).text)
