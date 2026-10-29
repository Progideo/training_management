"""P14 preparation: private facts, no eligibility or publication inferred."""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form, new_test_user, tagged

from .test_closure import ClosureCase


@tagged("post_install", "-at_install")
class TestPublicationPreparation(ClosureCase):
    def facts(self, enrollment, user=None):
        return (
            self.env["training.publication.service"]
            .with_user(user or self.coordinator)
            ._participation_facts(enrollment)
        )

    def test_enrollment_and_access_do_not_invent_participation(self):
        enrollment = self.opened()
        revision = enrollment.delivery_id.revision
        audit = self.env["training.operation"].search_count([])
        facts = self.facts(enrollment)
        self.assertEqual(facts, {"enrollment_state": "confirmed", "minutes": 0, "attendance": [], "certificates": []})
        self.assertEqual(enrollment.delivery_id.revision, revision)
        self.assertEqual(self.env["training.operation"].search_count([]), audit)
        self.assertNotIn("eligible", facts)

    def test_declaration_is_distinct_from_current_validated_minutes(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.assertEqual(self.facts(enrollment)["minutes"], 0)
        self.review(presence)
        facts = self.facts(enrollment)
        self.assertEqual(facts["minutes"], 90)
        self.assertEqual(
            facts["attendance"],
            [{"id": presence.id, "revision": presence.revision, "state": "validated", "minutes": 90}],
        )
        self.service(self.coordinator)._invalidate(
            session.id,
            enrollment.id,
            reason="Fictional invalidation",
            revision=presence.revision,
            definition=self.service()._definition(session),
        )
        self.assertEqual(self.facts(enrollment)["minutes"], 0)
        self.assertEqual(self.facts(enrollment)["attendance"][0]["state"], "invalidated")

    def test_historical_certificate_does_not_override_invalidation(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.review(presence)
        dossier = self.dossier(enrollment)
        enrollment.with_user(self.quality).action_certificate_participation()
        document = self.document(dossier, "participation")
        original = document.data
        self.service(self.coordinator)._invalidate(
            session.id,
            enrollment.id,
            reason="Fictional invalidation",
            revision=presence.revision,
            definition=self.service()._definition(session),
        )
        facts = self.facts(enrollment)
        self.assertEqual(facts["minutes"], 0)
        self.assertEqual(facts["certificates"], [{"id": document.id, "kind": "participation"}])
        self.assertEqual(document.data, original)

    def test_real_restricted_roles_cannot_inspect_or_open(self):
        enrollment = self.opened()
        for user in (
            self.portal,
            self.portal_b,
            self.reader,
            self.internal,
            self.quality,
            self.env.ref("base.public_user"),
        ):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.facts(enrollment, user)
                with self.assertRaises(AccessError):
                    enrollment.with_user(user).action_inspect_publication_evidence()
                with self.assertRaises(AccessError):
                    self.env["training.publication.inspection"].with_user(user).create({"enrollment_id": enrollment.id})

    def test_other_company_even_after_sudo_and_mixed_context(self):
        enrollment = self.opened()
        outsider = new_test_user(
            self.env,
            login="p14_other_coordinator",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        service = self.env["training.publication.service"].with_user(outsider)
        with self.assertRaises(AccessError):
            service._participation_facts(enrollment.sudo())
        with self.assertRaises(AccessError):
            service.sudo()._participation_facts(enrollment.sudo())

    def test_native_dialog_current_facts_and_transient_owner(self):
        _, session, enrollment = self.scheduled()
        presence = self.declare(session, enrollment)
        self.review(presence)
        action = enrollment.with_user(self.coordinator).action_inspect_publication_evidence()
        model = self.env[action["res_model"]].with_user(self.coordinator).with_context(**action["context"])
        with Form(model) as form:
            self.assertEqual(form.validated_minutes, 90)
            self.assertEqual(form.attendance_count, 1)
            self.assertEqual(form.certificate_count, 0)
            self.assertTrue(form.checked_at)
            wizard = form.save()
        colleague = new_test_user(
            self.env,
            login="p14_colleague",
            groups="training_management.group_training_coordinator",
        )
        with self.assertRaises(AccessError):
            wizard.with_user(colleague).read(["validated_minutes"])
