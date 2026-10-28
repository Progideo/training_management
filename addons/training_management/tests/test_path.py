"""P09 restricted users, existing learning evidence and access policy."""

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, tagged
from odoo.tools.translate import load_language

from .test_learning import LearningCase


@tagged("post_install", "-at_install")
class TestTrainingPath(LearningCase):
    def path(self, mandatory=True):
        course = (
            self.env["training.course"]
            .with_user(self.coordinator)
            .create({"name": "Fictional second course", "category_id": self.course.category_id.id})
        )
        program = self.program.copy({"version": "P09", "course_id": course.id})
        program.action_validate()
        path = (
            self.env["training.path"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional P09 path",
                    "order_policy": "mandatory" if mandatory else "recommended",
                    "step_ids": [
                        Command.create({"program_id": self.program.id, "sequence": 10}),
                        Command.create({"program_id": program.id, "sequence": 20}),
                    ],
                }
            )
        )
        return path

    def reference(self, step, enrollment, **values):
        return (
            self.env["training.path.assignment"]
            .with_user(self.coordinator)
            .create(
                {
                    "step_id": step.id,
                    "enrollment_id": enrollment.id,
                    **values,
                }
            )
        )

    def test_native_form_and_frozen_definition(self):
        with Form(self.env["training.path"].with_user(self.coordinator)) as form:
            form.name = "Fictional native path"
        self.assertEqual(form.record.state, "draft")
        path = self.path()
        path.action_validate()
        self.assertEqual(path.duration_hours, sum(path.step_ids.program_id.mapped("duration_hours")))
        for record, values in (
            (path, {"name": "Changed"}),
            (path.step_ids[:1], {"sequence": 30}),
        ):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                record.write(values)
            with self.assertRaises(ValidationError), self.cr.savepoint():
                record.unlink()
        self.assertEqual(path.copy().state, "draft")
        path.active = False
        path.active = True
        enrollment = self.admitted()
        with Form(self.env["training.path.assignment"].with_user(self.coordinator)) as form:
            form.step_id = path.step_ids[0]
            form.enrollment_id = enrollment
        self.assertEqual(form.record.company_id, self.company)
        self.assertEqual(form.record.validated_by, self.coordinator)

    def test_prerequisites_existing_acquis_and_no_duplicate_work(self):
        path = self.path()
        path.action_validate()
        first, second = path.step_ids
        d1, activity, e1 = self.setup_learning()
        # Existing acquired work is referenced, without reopening/copying it.
        entry = self.post(e1, activity_id=activity.id)
        self.post(e1, kind="correction", activity_id=activity.id, parent_id=entry.id, revision=1, decision="accepted")
        ref1 = self.reference(first, e1)
        self.assertTrue(ref1.completed)
        d2 = self.delivery(program_id=second.program_id.id)
        e2 = self.admitted(d2)
        ref2 = self.reference(second, e2)
        self.assertFalse(ref2.blocked)
        before = (self.env["training.enrollment"].search_count([]), len(e1.learning_progress_ids))
        e2.action_authorize(reason="Fictional")
        e2.action_open_access(reason="Fictional")
        self.assertEqual(e2._effective_state(), "active")
        self.assertEqual(before, (self.env["training.enrollment"].search_count([]), len(e1.learning_progress_ids)))
        for values in ({}, {"validated_by": self.portal.id}):
            with self.assertRaises((ValidationError, AccessError)), self.cr.savepoint():
                self.reference(first, e1, **values)
        self.assertEqual(d1.occupied_seats, 1)

    def test_missing_required_step_blocks_even_direct_access(self):
        path = self.path()
        path.action_validate()
        second = path.step_ids[1]
        e = self.admitted(self.delivery(program_id=second.program_id.id))
        ref = self.reference(second, e)
        self.assertTrue(ref.blocked)
        e.action_authorize(reason="Fictional")
        with self.assertRaises(ValidationError):
            e.action_open_access(reason="Fictional")
        # The private resource policy also checks the restriction dynamically.
        self.assertTrue(e._path_blocked())
        self.assertEqual(e.access_state, "unopened")

    def test_active_enrollment_cannot_be_silently_blocked(self):
        path = self.path()
        path.action_validate()
        e = self.opened(self.delivery(program_id=path.step_ids[1].program_id.id))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.reference(path.step_ids[1], e)
        self.assertEqual(e._effective_state(), "active")
        self.assertFalse(self.env["training.path.assignment"].search([("enrollment_id", "=", e.id)]))

    def test_recommended_order_explicit_prerequisite_and_equivalence(self):
        path = self.path(mandatory=False)
        first, second = path.step_ids
        second.prerequisite_ids = [Command.set(first.ids)]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            first.prerequisite_ids = [Command.set(second.ids)]
        path.action_validate()
        duplicate = path.copy()
        self.assertEqual(duplicate.step_ids[1].prerequisite_ids, duplicate.step_ids[0])
        e = self.admitted()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.reference(second, e)
        ref = self.reference(second, e, equivalence_reason="Fictional programme comparison validated")
        self.assertEqual(ref.validated_by, self.coordinator)
        self.assertTrue(ref.blocked)
        self.assertFalse(ref.completed)  # No required activities is not an acquisition.
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.reference(first, e)
        with self.assertRaises(AccessError):
            ref.write({"equivalence_reason": "Changed"})
        with self.assertRaises((AccessError, ValidationError)):
            ref.unlink()

    def test_real_restricted_users_and_company_isolation(self):
        path = self.path()
        path.action_validate()
        ref = self.reference(path.step_ids[0], self.admitted())
        for user in (self.portal, self.portal_b, self.internal, self.reader):
            with self.assertRaises(AccessError):
                ref.with_user(user).read(["participant_id"])
        self.assertEqual(path.with_user(self.reader).name, path.name)
        with self.assertRaises(AccessError):
            path.with_user(self.reader).read(["assignment_ids"])
        with self.assertRaises(AccessError):
            path.with_user(self.reader).action_validate()
        foreign = self.env["training.path"].create({"name": "Other company", "company_id": self.other_company.id})
        with self.assertRaises(AccessError):
            foreign.with_user(self.coordinator).read(["name"])

    def test_french_native_labels_and_server_error(self):
        load_language(self.cr, "fr_FR")
        path = self.path().with_context(lang="fr_FR")
        path.action_validate()
        self.assertEqual(path.fields_get(["order_policy"])["order_policy"]["string"], "Politique d’ordre")
        self.assertEqual(
            self.env.ref("training_management.menu_training_paths").with_context(lang="fr_FR").name,
            "Parcours de formation",
        )
        with self.assertRaisesRegex(ValidationError, "Conserver les parcours validés"):
            path.write({"name": "Changed"})

    def test_withdrawal_is_audited_repeatable_and_releases_only_its_constraint(self):
        path = self.path()
        path.action_validate()
        enrollment = self.admitted(self.delivery(program_id=path.step_ids[1].program_id.id))
        ref = self.reference(path.step_ids[1], enrollment)
        self.assertTrue(enrollment._path_blocked())
        with self.assertRaises(ValidationError):
            ref.action_withdraw()
        with self.assertRaises(AccessError):
            ref.with_user(self.reader).action_withdraw(reason="Forbidden")
        reason_action = ref.with_context(reason_action="action_withdraw").action_open_reason()
        wizard = (
            self.env["training.action.reason"]
            .with_user(self.coordinator)
            .with_context(**reason_action["context"])
            .create({"reason": "Fictional erroneous assignment"})
        )
        wizard.action_apply()
        timestamp = ref.withdrawn_at
        ref.action_withdraw(reason="Replay")
        self.assertEqual(ref.withdrawn_at, timestamp)
        self.assertEqual(ref.withdrawn_by, self.coordinator)
        self.assertFalse(enrollment._path_blocked())
        self.assertEqual(
            self.env["training.operation"].search_count(
                [
                    ("model_name", "=", ref._name),
                    ("record_id", "=", ref.id),
                ]
            ),
            1,
        )
        replacement = self.reference(path.step_ids[1], enrollment)
        self.assertNotEqual(ref, replacement)
        self.assertTrue(ref.exists())
        self.assertTrue(enrollment._path_blocked())

    def test_acquired_later_step_keeps_existing_access_without_prior_step(self):
        path = self.path()
        path.action_validate()
        second = path.step_ids[1]
        delivery = self.delivery(program_id=second.program_id.id)
        activity = self.activity(delivery, criterion="declaration")
        enrollment = self.opened(delivery)
        self.service()._declare(enrollment.id, activity.id)
        ref = self.reference(second, enrollment)
        self.assertTrue(ref.completed)
        self.assertFalse(ref.blocked)
        self.assertEqual(enrollment._effective_state(), "active")
        self.assertFalse(
            self.env["training.path.assignment"].search(
                [
                    ("step_id", "=", path.step_ids[0].id),
                ]
            )
        )
