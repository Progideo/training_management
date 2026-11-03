"""Shared native versions, immutable obligations and exact enrollment isolation."""

from datetime import timedelta
from unittest.mock import patch
from odoo import fields, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged, new_test_user, HttpCase
from .test_exam import ExamCase
from odoo.addons.training_management.tests.test_closure import ClosureCase


class SharedExamCase(ExamCase):
    def shared_exam(self, with_image=False, **values):
        exam, q1, q2 = self.exam(with_image=with_image)
        # Draft conversion is forbidden by design: create a native shared definition.
        shared = (
            self.env["survey.survey"]
            .with_user(self.coordinator)
            .create(
                {
                    "title": "Fictional shared exam",
                    "training_course_id": self.program.course_id.id,
                    "time_limit": 10,
                    "scoring_success_min": 75,
                    **values,
                }
            )
        )
        for question in (q1, q2):
            question.copy({"survey_id": shared.id})
        shared.action_mock_publish()
        return shared, shared.question_ids[0], shared.question_ids[1]

    def assigned(self, delivery, exam, obligation="pass", **values):
        return (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional shared activity",
                    "delivery_id": delivery.id,
                    "criterion": "evaluation",
                    "training_exam_id": exam.id,
                    "exam_obligation": obligation,
                    **values,
                }
            )
        )


@tagged("post_install", "-at_install")
class TestExamRequirements(SharedExamCase):
    def test_coexisting_autonomous_offer_keeps_evidence_and_reader_scope_separate(self):
        if "training.elearning.exam.service" not in self.env:
            self.skipTest("Optional autonomous composition is not installed")
        exam, _, _ = self.shared_exam()
        delivery = self.delivery()
        activity = self.assigned(delivery, exam, "complete")
        enrollment = self.opened(delivery)
        manager = new_test_user(
            self.env,
            login="fictional_coexistence_coordinator",
            groups="training_elearning_survey.group_learning_exam_reader",
        )
        course = (
            self.env["slide.channel"]
            .with_user(manager)
            .create(
                {
                    "name": "Fictional autonomous edition",
                    "training_course_id": self.program.course_id.id,
                }
            )
        )
        slide = (
            self.env["slide.slide"]
            .with_user(manager)
            .create(
                {
                    "channel_id": course.id,
                    "survey_id": exam.id,
                    "learning_exam_obligation": "pass",
                    "is_published": True,
                }
            )
        )
        course.action_learning_publish()
        member = (
            self.env["slide.channel.partner"]
            .with_user(manager)
            .create(
                {
                    "channel_id": course.id,
                    "partner_id": self.portal.partner_id.id,
                }
            )
        )
        member.action_learning_activate(fields.Datetime.now() + timedelta(days=2), self.portal.id, "Fictional access")
        tm = self.env["training.exam.service"].with_user(self.portal)
        autonomous = self.env["training.elearning.exam.service"].with_user(self.portal)
        first = tm._start(enrollment.id, activity.id)
        second = autonomous._start(member.id, slide.id)
        self.assertEqual(first.survey_id, second.survey_id)
        self.assertNotEqual(first.mock_context_key, second.mock_context_key)
        self.assertNotEqual(first, second)
        tm._submit(first.id)
        self.assertTrue(self.env["training.learning.service"]._complete(enrollment, activity))
        self.assertEqual(member.completion, 0)
        for question in second.predefined_question_ids:
            autonomous._save(second.id, question.id, question.suggested_answer_ids.filtered("is_correct").ids, False)
        autonomous._submit(second.id)
        self.assertEqual(member.completion, 100)
        self.assertFalse(second.with_user(self.coordinator).search([("id", "=", second.id)]))
        self.assertFalse(first.with_user(manager).search([("id", "=", first.id)]))
        with self.assertRaises(AccessError):
            tm._submit(second.id)
        with self.assertRaises(AccessError):
            autonomous._submit(first.id)

    def test_multi_exam_optional_complete_and_pass_are_frozen_and_independent(self):
        exam, q1, q2 = self.shared_exam()
        another, _, _ = self.shared_exam()
        delivery = self.delivery()
        optional = self.assigned(delivery, another, "optional")
        completed = self.assigned(delivery, exam, "complete")
        required = self.assigned(delivery, another, "pass")
        enrollment = self.opened(delivery)
        requirements = self.env["training.exam.requirement"].search([("enrollment_id", "=", enrollment.id)])
        self.assertEqual(len(requirements), 3)
        self.assertTrue(optional.optional)
        self.assertFalse(completed.optional)
        learning = self.env["training.learning.service"].with_user(self.portal)
        service = self.env["training.exam.service"].with_user(self.portal)
        self.assertFalse(learning._complete(enrollment, completed))
        cached_progress = learning._progress(enrollment, completed, create=True)
        self.assertFalse(cached_progress.completed)
        attempt = service._start(enrollment.id, completed.id)
        self.assertFalse(learning._complete(enrollment, completed), "A launch is not a completed attempt")
        service._submit(attempt.id)
        self.assertTrue(cached_progress.completed)
        self.assertTrue(learning._complete(enrollment, completed), "A completed zero-score attempt satisfies complete")
        self.assertFalse(learning._complete(enrollment, required))
        success = service._start(enrollment.id, required.id)
        for q in success.predefined_question_ids:
            service._save(success.id, q.id, q.suggested_answer_ids.filtered("is_correct").ids, False)
        service._submit(success.id)
        self.assertTrue(learning._complete(enrollment, required))
        failed = service._start(enrollment.id, required.id)
        service._submit(failed.id)
        self.assertTrue(learning._complete(enrollment, required), "A later failure must not remove success")
        self.assertEqual(learning._shared_exam_status(enrollment, required)["score"], 100)
        for values in ({"exam_obligation": "optional"}, {"training_exam_id": exam.id}, {"optional": True}):
            with self.assertRaises(ValidationError):
                required.write(values)
        with self.assertRaises(AccessError):
            requirements.write({"obligation": "optional"})
        with self.assertRaises(AccessError):
            requirements.unlink()
        with self.assertRaises(ValidationError):
            self.assigned(delivery, exam)
        with self.assertRaises(ValidationError):
            required.unlink()
        self.assertFalse(self.env["training.learning.service"]._required_for_certificate(optional))

    def test_shared_version_two_offers_different_obligations_and_contexts(self):
        exam, _, _ = self.shared_exam()
        first_offer, second_offer = self.delivery(), self.delivery()
        first_activity = self.assigned(first_offer, exam, "complete")
        second_activity = self.assigned(second_offer, exam, "pass")
        first, second = self.opened(first_offer), self.opened(second_offer)
        service = self.env["training.exam.service"].with_user(self.portal)
        learning = self.env["training.learning.service"].with_user(self.portal)
        a = service._start(first.id, first_activity.id)
        b = service._start(second.id, second_activity.id)
        self.assertEqual(a.survey_id, b.survey_id)
        self.assertNotEqual(a.mock_context_key, b.mock_context_key)
        service._submit(a.id)
        self.assertTrue(learning._complete(first, first_activity))
        self.assertFalse(learning._complete(second, second_activity))
        with patch.object(fields.Datetime, "now", return_value=b.deadline + timedelta(seconds=1)):
            self.env["survey.user_input"]._cron_mock_expire()
        self.assertFalse(learning._complete(second, second_activity))
        with self.assertRaises(AccessError):
            service.with_user(self.portal_b)._result(a)
        with self.assertRaises(AccessError):
            service._start(first.id, second_activity.id)
        status = learning._shared_exam_status(second, second_activity)
        self.assertTrue(status["complete"])
        self.assertFalse(status["success"])

    def test_snapshot_permissions_and_foreign_course_assignment(self):
        exam, _, _ = self.shared_exam()
        delivery = self.delivery()
        activity = self.assigned(delivery, exam)
        enrollment = self.opened(delivery)
        row = self.env["training.exam.requirement"].search([("enrollment_id", "=", enrollment.id)])
        with self.assertRaises(AccessError):
            row.with_user(self.portal).read(["obligation"])
        with self.assertRaises(AccessError):
            self.env["training.exam.requirement"].create(
                {
                    "enrollment_id": enrollment.id,
                    "activity_id": activity.id,
                    "exam_id": exam.id,
                    "obligation": "optional",
                }
            )
        other_course = self.env["training.course"].create({"name": "Fictional unrelated course"})
        foreign = (
            self.env["survey.survey"]
            .with_user(self.coordinator)
            .create({"title": "Other course draft", "training_course_id": other_course.id, "time_limit": 10})
        )
        exam.question_ids[0].copy({"survey_id": foreign.id})
        foreign.action_mock_publish()
        with self.assertRaises(ValidationError):
            self.assigned(self.delivery(), foreign)
        author = new_test_user(
            self.env, login="shared_definition_only", groups="training_mock_exam.group_mock_exam_author"
        )
        attempt = self.env["training.exam.service"].with_user(self.portal)._start(enrollment.id, activity.id)
        self.assertFalse(attempt.with_user(author).search([("id", "=", attempt.id)]))
        self.assertTrue(attempt.with_user(self.coordinator).search([("id", "=", attempt.id)]))
        with self.assertRaises(AccessError):
            attempt.with_user(self.coordinator).write({"mock_reader_group_id": False})
        self.assertEqual(self.env["training.exam.service"].with_user(self.portal)._attempt(attempt.id), attempt)


@tagged("post_install", "-at_install")
class TestSharedExamPortal(SharedExamCase, HttpCase):
    def test_shared_exam_private_pages_images_and_suspension(self):
        exam, q1, q2 = self.shared_exam(with_image=True)
        delivery = self.delivery()
        activity = self.assigned(delivery, exam, "complete")
        enrollment = self.opened(delivery)
        service = self.env["training.exam.service"].with_user(self.portal)
        attempt = service._start(enrollment.id, activity.id)
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open(f"/my/training-exams/{attempt.id}")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("PRIVATE FINAL EXPLANATION", page.text)
        choice = q2.suggested_answer_ids.filtered("value_image")[0]
        image = f"/survey/get_question_image/{exam.access_token}/{attempt.access_token}/{q2.id}/{choice.id}"
        self.assertEqual(self.url_open(image).status_code, 200)
        self.assertEqual(
            self.url_open(f"/survey/start/{exam.access_token}?answer_token={attempt.access_token}").status_code, 404
        )
        service._submit(attempt.id)
        result = self.url_open(f"/my/training-exams/{attempt.id}")
        self.assertEqual(result.status_code, 200)
        self.assertIn("PRIVATE FINAL EXPLANATION", result.text)
        enrollment._store({"access_end": fields.Datetime.now() - timedelta(seconds=1)}, "Fictional expiry")
        self.assertEqual(self.url_open(image).status_code, 404)
        self.assertEqual(self.url_open(f"/my/training-exams/{attempt.id}").status_code, 404)
        enrollment._store({"access_end": fields.Datetime.now() + timedelta(days=1)}, "Fictional renewal")
        self.assertEqual(self.url_open(f"/my/training-exams/{attempt.id}").status_code, 200)
        learning = self.url_open(f"/my/trainings/{enrollment.id}")
        self.assertEqual(learning.status_code, 200)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(image).status_code, 404)
        self.assertEqual(self.url_open(f"/my/training-exams/{attempt.id}").status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        enrollment.action_suspend_access(reason="Fictional suspension")
        self.assertEqual(self.url_open(image).status_code, 404)


@tagged("post_install", "-at_install")
class TestSharedExamCertificate(ClosureCase, SharedExamCase):
    def test_required_pass_and_complete_control_the_existing_quality_certificate(self):
        exam, _, _ = self.shared_exam()
        other, _, _ = self.shared_exam()
        delivery = self.delivery()
        required = self.assigned(delivery, exam, "pass")
        to_complete = self.assigned(delivery, other, "complete")
        enrollment = self.opened(delivery)
        dossier = self.dossier(enrollment)
        self.validate(self.proof(dossier, "completion"))
        with self.assertRaises(ValidationError):
            enrollment.with_user(self.quality).action_certificate_completion()
        service = self.env["training.exam.service"].with_user(self.portal)
        attempt = service._start(enrollment.id, required.id)
        for question in attempt.predefined_question_ids:
            service._save(attempt.id, question.id, question.suggested_answer_ids.filtered("is_correct").ids, False)
        service._submit(attempt.id)
        unfinished = service._start(enrollment.id, to_complete.id)
        with self.assertRaises(ValidationError):
            enrollment.with_user(self.quality).action_certificate_completion()
        service._submit(unfinished.id)
        enrollment.with_user(self.quality).action_certificate_completion()
        self.assertTrue(self.document(dossier, "completion"))
        with self.assertRaises(AccessError):
            exam.with_user(self.quality).read(["question_ids"])


@tagged("post_install", "-at_install")
class TestSharedExamVersions(SharedExamCase):
    def test_versions_are_explicit_and_expiry_keeps_the_frozen_context(self):
        exam, _, _ = self.shared_exam()
        version = self.env["survey.survey"].browse(exam.action_mock_new_version()["res_id"]).with_user(self.coordinator)
        version.write({"training_version": "2", "training_revision_reason": "Fictional revised version"})
        version.action_mock_publish()
        delivery = self.delivery()
        first = self.assigned(delivery, exam, "complete")
        second = self.assigned(delivery, version, "pass")
        enrollment = self.opened(delivery)
        service = self.env["training.exam.service"].with_user(self.portal)
        learning = self.env["training.learning.service"].with_user(self.portal)
        a = service._start(enrollment.id, first.id)
        with self.assertRaises(ValidationError):
            service._start(enrollment.id, second.id)
        service._submit(a.id)
        self.assertTrue(learning._complete(enrollment, first))
        self.assertFalse(learning._complete(enrollment, second))
        b = service._start(enrollment.id, second.id)
        self.assertEqual(b.survey_id, version)
        enrollment._store({"access_end": fields.Datetime.now() - timedelta(seconds=1)}, "Fictional access expiry")
        self.assertEqual(service._save(b.id, b.predefined_question_ids[0].id, [], False), {"done": True})
        self.assertEqual(b.state, "done")
        self.assertFalse(b.user_input_line_ids)
        self.assertFalse(learning._complete(enrollment, second))
        with self.assertRaises(AccessError):
            service._result(b)
        with self.assertRaises(AccessError):
            service._start(enrollment.id, first.id)

    def test_optional_exam_cannot_become_a_hidden_prerequisite(self):
        exam, _, _ = self.shared_exam()
        delivery = self.delivery()
        optional = self.assigned(delivery, exam, "optional")
        with self.assertRaises(ValidationError):
            self.assigned(delivery, exam, "pass", dependency_ids=[Command.link(optional.id)])
