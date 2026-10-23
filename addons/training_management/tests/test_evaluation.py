"""S09.1: real scoped roles, preserved decisions and dedicated S08 evidence."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged

from .test_closure import ClosureCase


class EvaluationCase(ClosureCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supervisor = new_test_user(
            cls.env,
            login="s091_supervisor",
            groups="base.group_user,base.group_allow_export,training_management.group_training_supervisor",
        )

    def assigned_evaluation(self, enrollment=None, **definition):
        delivery = enrollment.delivery_id if enrollment else self.delivery()
        enrollment = enrollment or self.opened(delivery)
        delivery.write(
            {
                "evaluation_quality_id": self.quality.id,
                "evaluation_supervisor_ids": [Command.set(self.supervisor.ids)],
                "evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)],
            }
        )
        evaluation = (
            self.env["training.evaluation"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional dedicated assessment",
                    "program_id": self.program.id,
                    "purpose": "acquired",
                    "criteria": "Observed answers",
                    "threshold": 75,
                    **definition,
                }
            )
        )
        evaluation.action_publish()
        row = (
            self.env["training.evaluation.assignment"]
            .with_user(self.coordinator)
            .create(
                {
                    "evaluation_id": evaluation.id,
                    "enrollment_id": enrollment.id,
                    "opens_at": fields.Datetime.now() - timedelta(hours=1),
                    "due_at": fields.Datetime.now() + timedelta(days=1),
                }
            )
        )
        grant = (
            self.env["training.evaluation.authorization"]
            .with_user(self.quality)
            .create(
                {
                    "delivery_id": delivery.id,
                    "user_id": self.portal_b.id,
                    "purpose": evaluation.purpose,
                    "valid_from": fields.Datetime.now() - timedelta(hours=1),
                    "valid_until": fields.Datetime.now() + timedelta(days=1),
                    "reason": "Fictional qualified evaluator",
                }
            )
        )
        return row, grant

    def decision(self, row, score=75, user=None):
        return (
            self.env["training.evaluation.service"]
            .with_user(user or self.portal_b)
            ._validate(
                row.id,
                revision=row.revision,
                score=score,
                conclusion="Observed result",
                source="Fictional assessment sheet",
                reason="Checked response",
            )
        )


@tagged("post_install", "-at_install")
class TestEvaluation(EvaluationCase):
    def test_versions_and_no_implicit_zero(self):
        row, _grant = self.assigned_evaluation()
        self.assertEqual(row.state, "not_started")
        self.assertFalse(row.result_available)
        with self.assertRaises(ValidationError):
            row.evaluation_id.write({"threshold": 0})
        version = row.evaluation_id.action_new_version()
        v2 = self.env["training.evaluation"].browse(version["res_id"])
        self.assertEqual(v2.previous_id, row.evaluation_id)
        self.assertEqual(v2.state, "draft")
        result = self.decision(row, score=0)
        self.assertTrue(row.result_available)
        self.assertEqual(row.score, 0)
        self.assertEqual(row.state, "validated")
        revised = self.decision(row, score=80)
        self.assertEqual(revised.previous_id, result)
        self.assertEqual(result.score, 0)
        with self.assertRaises(AccessError):
            result.write({"score": 100})

    def test_supervisor_is_scoped_read_only_and_revoked(self):
        row, _grant = self.assigned_evaluation()
        other, _grant2 = self.assigned_evaluation()
        other.delivery_id.write({"evaluation_supervisor_ids": [Command.clear()]})
        model = self.env["training.evaluation.assignment"].with_user(self.supervisor)
        self.assertIn(row.id, model.search([]).ids)
        self.assertNotIn(other.id, model.search([]).ids)
        with self.assertRaises(AccessError):
            self.decision(row, user=self.supervisor)
        with self.assertRaises(AccessError):
            model.browse(row.id).write({"score": 100})
        with self.assertRaises(AccessError):
            self.env["training.evaluation.result"].with_user(self.supervisor).search([])
        row.delivery_id.write({"evaluation_supervisor_ids": [Command.clear()]})
        self.assertFalse(model.search([("id", "=", row.id)]))
        with self.assertRaises(AccessError):
            self.env["training.evaluation.service"].with_user(self.supervisor)._assignment(row.id)

    def test_authorization_and_teaching_mission_both_required(self):
        row, grant = self.assigned_evaluation()
        with self.assertRaises(AccessError):
            self.decision(row, user=self.coordinator)
        grant.write({"active": False})
        with self.assertRaises(AccessError):
            self.decision(row)
        row2, grant2 = self.assigned_evaluation()
        row2.delivery_id.write({"evaluation_instructor_ids": [Command.clear()]})
        with self.assertRaises(AccessError):
            self.decision(row2)
        with self.assertRaises(AccessError):
            grant2.with_user(self.coordinator).write({"active": False})

    def test_supervision_does_not_preserve_withdrawn_teaching_mission(self):
        row, _grant = self.assigned_evaluation()
        row.delivery_id.write({"evaluation_instructor_ids": [Command.set(self.supervisor.partner_id.ids)]})
        self.env["training.evaluation.authorization"].with_user(self.quality).create(
            {
                "delivery_id": row.delivery_id.id,
                "user_id": self.supervisor.id,
                "purpose": row.purpose,
                "valid_until": fields.Datetime.now() + timedelta(days=1),
                "reason": "Fictional explicit teaching and supervision roles",
            }
        )
        self.decision(row, user=self.supervisor)
        row.delivery_id.write({"evaluation_instructor_ids": [Command.clear()]})
        # The supervisor retains scoped reading, but no teaching mission.
        self.env["training.evaluation.service"].with_user(self.supervisor)._assignment(row.id)
        with self.assertRaises(AccessError):
            self.decision(row, user=self.supervisor)

    def test_participant_states_deadline_and_stale_decision(self):
        row, _grant = self.assigned_evaluation()
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        self.assertEqual(row.state, "in_progress")
        service._submit(row.id)
        self.assertEqual(row.state, "submitted")
        revision = row.revision
        service._submit(row.id)
        self.assertEqual(row.revision, revision)
        self.decision(row)
        with self.assertRaises(ValidationError):
            self.env["training.evaluation.service"].with_user(self.portal_b)._validate(
                row.id, revision=revision, score=75, conclusion="Stale", source="Fictional", reason="Stale"
            )
        with self.assertRaises(AccessError):
            self.env["training.evaluation.service"].with_user(self.portal_b)._start(row.id)

    def test_observed_portal_form_is_bound_to_its_attempt(self):
        row, _grant = self.assigned_evaluation()
        service = self.env["training.evaluation.service"].with_user(self.portal)
        service._start(row.id)
        service._portal_answers(row.id, {}, attempt_number=1, submit=True)
        self.env["training.evaluation.service"].with_user(self.coordinator)._reopen(
            row.id, revision=row.revision, reason="Fictional retry", due_at=fields.Datetime.now() + timedelta(days=2)
        )
        service._start(row.id)
        with self.assertRaises(ValidationError):
            service._portal_answers(row.id, {}, attempt_number=1, submit=True)
        self.assertEqual(row.state, "in_progress")
        service._portal_answers(row.id, {}, attempt_number=2, submit=True)
        self.assertEqual(row.state, "submitted")

    def test_dedicated_evaluation_supplies_s08_without_rewriting_proof(self):
        row, _grant = self.assigned_evaluation()
        dossier = self.dossier(row.enrollment_id)
        self.decision(row)
        action = row.action_export_proof()
        proof = self.env["training.proof"].browse(action["res_id"])
        original = proof.data.content
        self.assertTrue(original.startswith(b"%PDF-"))
        self.assertEqual(proof.score, 75)
        self.assertEqual(proof.threshold, 75)
        self.assertEqual(row.action_export_proof()["res_id"], proof.id)
        self.validate(proof)
        dossier.with_user(self.quality).action_certificate_achievement()
        self.decision(row, score=90)
        action2 = row.action_export_proof()
        self.assertNotEqual(action2["res_id"], proof.id)
        self.assertEqual(proof.data.content, original)
        self.assertEqual(proof.score, 75)

    def test_qualitative_and_positioning_do_not_issue_scored_achievement(self):
        row, _grant = self.assigned_evaluation(scored=False, purpose="positioning")
        self.decision(row)
        self.assertFalse(row.result_available)
        dossier = self.dossier(row.enrollment_id)
        action = row.action_export_proof()
        proof = self.env["training.proof"].browse(action["res_id"])
        self.assertEqual(proof.category, "positioning")
        self.validate(proof)
        with self.assertRaises(ValidationError):
            dossier.with_user(self.quality).action_certificate_achievement()

    def test_foreign_company_and_participant_do_not_gain_access(self):
        row, _grant = self.assigned_evaluation()
        foreign = self.env["res.company"].create({"name": "Fictional S091 foreign operator"})
        self.supervisor.write({"company_ids": [Command.set(foreign.ids)], "company_id": foreign.id})
        with self.assertRaises(AccessError):
            self.env["training.evaluation.service"].with_user(self.supervisor)._assignment(row.id)
        with self.assertRaises(AccessError):
            self.env["training.evaluation.assignment"].with_user(self.portal).search([])
        self.assertFalse(self.env["training.evaluation.assignment"].with_user(self.supervisor).search([]))

    def test_reopening_keeps_reference_history_and_requires_new_result(self):
        row, _grant = self.assigned_evaluation()
        original = self.decision(row)
        self.env["training.evaluation.service"].with_user(self.coordinator)._reopen(
            row.id,
            revision=row.revision,
            reason="Second observed assessment",
            due_at=fields.Datetime.now() + timedelta(days=3),
        )
        self.assertEqual(row.attempt_number, 2)
        self.assertEqual(row.state, "not_started")
        self.assertFalse(row.result_available)
        self.assertEqual(original.score, 75)
        self.assertEqual(self.decision(row, score=90).previous_id, original)

    def test_supervisor_read_and_export_only_authorized_summary(self):
        row, _grant = self.assigned_evaluation()
        self.decision(row)
        summary = row.with_user(self.supervisor).read(["name", "state", "score", "result_available"])[0]
        self.assertEqual(summary["score"], 75)
        self.assertEqual(row.with_user(self.supervisor).export_data(["name", "score"])["datas"], [[row.name, 75]])
        with self.assertRaises(AccessError):
            row.with_user(self.supervisor).export_data(["result_ids/source"])
        self.assertEqual(
            self.env["training.evaluation.service"].with_user(self.supervisor)._portal_values(row)["history"], []
        )

    def test_two_clients_and_two_realizations_keep_personal_scope(self):
        client_a, client_b = self.env["res.partner"].create(
            [
                {"name": "Fictional S091 client A", "is_company": True},
                {"name": "Fictional S091 client B", "is_company": True},
            ]
        )
        self.portal.partner_id.parent_id = client_a
        other = new_test_user(self.env, login="s091_other_customer_participant", groups="base.group_portal")
        other.partner_id.parent_id = client_b
        enrollment = self.enrollment(self.delivery(), participant_id=other.partner_id.id, user_id=other.id)
        enrollment.action_validate_prerequisites(reason="Fictional separate client")
        enrollment.action_confirm()
        enrollment.action_authorize(reason="Fictional separate client")
        enrollment.action_open_access(reason="Fictional separate client")
        a, _grant = self.assigned_evaluation()
        b, _grant2 = self.assigned_evaluation(enrollment=enrollment)
        for user, own, foreign in ((self.portal, a, b), (other, b, a)):
            service = self.env["training.evaluation.service"].with_user(user)
            self.assertEqual(service._assignment(own.id).id, own.id)
            with self.assertRaises(AccessError):
                service._assignment(foreign.id)
            visible = self.env["training.evaluation.assignment"].sudo().search(service._visible_domain())
            self.assertIn(own.id, visible.ids)
            self.assertNotIn(foreign.id, visible.ids)
