from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .test_closure import ClosureCase


@tagged("post_install", "-at_install")
class TestEvidenceDeletion(ClosureCase):
    """Conservation configurée (22 November 2026): evidence stays by default and only an
    administrator, by hand or through a rule he configured, deletes it; the legal hold
    blocks it. Rules (Data Recycle, automated actions) delete in sudo as ``__system__``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")

    def test_only_an_administrator_deletes_evidence(self):
        dossier = self.dossier()
        dossier.with_user(self.quality).frozen = False
        proof = self.proof(dossier)
        for user in (self.coordinator, self.quality):
            with self.assertRaises((AccessError, ValidationError)):
                proof.with_user(user).unlink()
            # sudo() alone never authorizes: the real user decides.
            with self.assertRaises(ValidationError):
                proof.with_user(user).sudo().unlink()
        proof.with_user(self.admin).sudo().unlink()
        self.assertFalse(proof.exists())

    def test_legal_hold_blocks_deletion(self):
        dossier = self.dossier()
        proof = self.proof(dossier)
        self.assertTrue(dossier.frozen)
        for record in (proof, dossier):
            with self.assertRaisesRegex(ValidationError, "legal hold"):
                record.with_user(self.admin).sudo().unlink()
        dossier.with_user(self.quality).frozen = False
        proof.with_user(self.admin).sudo().unlink()
        self.assertFalse(proof.exists())

    def test_only_a_finished_dossier_is_deleted(self):
        enrollment = self.opened()
        with self.assertRaises(AccessError):
            enrollment.with_user(self.coordinator).action_training_delete_dossier()
        with self.assertRaisesRegex(ValidationError, "finished or cancelled"):
            enrollment.with_user(self.admin).action_training_delete_dossier()
        self.assertTrue(enrollment.exists())

    def test_finished_dossier_is_deleted_with_its_evidence(self):
        enrollment = self.opened()
        delivery = enrollment.delivery_id
        enrollment.action_cancel(reason="Fictional cancellation")
        records = enrollment.sudo()._training_dossier_records()
        self.assertEqual(records[-1], enrollment)
        dependents = records[:-1]
        self.assertTrue(dependents, "an opened enrollment has training evidence")
        action = enrollment.with_user(self.admin).action_training_delete_dossier()
        self.assertFalse(enrollment.exists())
        self.assertFalse(any(rows.exists() for rows in dependents))
        # Back to the list: the deleted record cannot stay displayed.
        self.assertEqual((action["type"], action["res_model"]), ("ir.actions.act_window", "training.enrollment"))
        # The list of the menu, with its title and usual filters.
        self.assertEqual(action["id"], self.env.ref("training_management.action_training_enrollments").id)
        self.assertTrue(delivery.exists())

    def test_held_closure_keeps_the_whole_dossier(self):
        enrollment = self.opened()
        self.dossier(enrollment)
        enrollment.action_cancel(reason="Fictional cancellation")
        with self.assertRaisesRegex(ValidationError, "legal hold"):
            enrollment.with_user(self.admin).action_training_delete_dossier()
        self.assertTrue(enrollment.exists())
