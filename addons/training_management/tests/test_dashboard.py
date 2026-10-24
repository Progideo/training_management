"""S10: live scope, verifiable populations, no raw/private learning data."""

from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged

from .test_evaluation import EvaluationCase


@tagged("post_install", "-at_install")
class TestDashboard(EvaluationCase):
    def dashboard(self, user=None):
        return self.env["training.dashboard.service"].with_user(user or self.coordinator)

    def test_native_one_row_scope_search_group_export_and_revoke(self):
        assignment, _grant = self.assigned_evaluation()
        delivery = assignment.delivery_id
        other = self.delivery()
        self.opened(other)
        model = self.env["training.dashboard.line"].with_user(self.supervisor)
        self.assertEqual(model.search([]).ids, assignment.enrollment_id.ids)
        self.assertEqual(model.search_count([]), 1)
        self.assertEqual(len(model._read_group([], ["delivery_id"], ["__count"])), 1)
        line = model.browse(assignment.enrollment_id.id)
        values = line.read(["name", "state", "evaluations", "details"])[0]
        self.assertIn("Not Started", values["evaluations"])
        self.assertEqual(len(line.export_data(["name", "state"])["datas"]), 1)
        with self.assertRaises(AccessError):
            line.write({"state": "closed"})
        delivery.write({"evaluation_supervisor_ids": [Command.clear()]})
        self.assertFalse(model.search([]))
        with self.assertRaises(AccessError):
            line.read(["name"])
        with self.assertRaises(AccessError):
            line.export_data(["name"])
        with self.assertRaises(AccessError):
            self.dashboard(self.supervisor)._dashboard(delivery.id)

    def test_internal_trainer_assignment_and_revocation(self):
        trainer = new_test_user(self.env, login="s10_internal", groups="base.group_user")
        delivery = self.delivery()
        enrollment = self.opened(delivery)
        model = self.env["training.dashboard.line"].with_user(trainer)
        self.assertFalse(model.search([]))
        delivery.write({"evaluation_instructor_ids": [Command.set(trainer.partner_id.ids)]})
        self.assertEqual(model.search([]).ids, enrollment.ids)
        delivery.write({"evaluation_instructor_ids": [Command.clear()]})
        self.assertFalse(model.search([]))
        with self.assertRaises(AccessError):
            self.dashboard(trainer)._participant(enrollment.id)

    def test_session_only_internal_trainer_is_revoked_when_session_cancelled(self):
        trainer = new_test_user(self.env, login="s10_session_trainer", groups="base.group_user")
        delivery, session, enrollment = self.scheduled(instructor=trainer.partner_id)
        model = self.env["training.dashboard.line"].with_user(trainer)
        self.assertEqual(model.search([]).ids, enrollment.ids)
        self.assertEqual(len(self.dashboard(trainer)._participant(enrollment.id)["attendance"]), 1)
        with patch("odoo.fields.Datetime.now", return_value=session.start_at - timedelta(minutes=1)):
            session._apply_schedule({}, cancel=True, reason="Fictional cancellation")
        self.assertFalse(model.search([]))
        with self.assertRaises(AccessError):
            self.dashboard(trainer)._dashboard(delivery.id)

    def test_attendance_projection_declared_validated_corrected_and_paper(self):
        delivery, session, enrollment = self.scheduled()
        row = self.dashboard()._participant(enrollment.id)
        self.assertTrue(row["attendance_incomplete"])
        self.assertIsNone(row["attendance"][0]["minutes"])
        presence = self.declare(session, enrollment)
        self.assertIn("Declared", self.dashboard()._participant(enrollment.id)["attendance"][0]["state"])
        self.review(presence)
        row = self.dashboard()._participant(enrollment.id)
        self.assertEqual(row["attendance"][0]["minutes"], 90)
        self.assertFalse(row["attendance_incomplete"])
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            self.service(self.coordinator)._review(
                session.id,
                enrollment.id,
                0,
                120,
                correction=True,
                revision=presence.revision,
                reason="Fictional corrected attendance",
                data=b"%PDF-fictional",
                filename="correction.pdf",
                definition=self.service()._definition(session),
            )
        row = self.dashboard()._participant(enrollment.id)
        self.assertEqual(row["attendance"][0]["minutes"], 120)
        self.assertEqual(len(row["attendance"][0]["history"]), 3)

    def test_paper_deposit_is_not_validation_and_async_is_not_presence(self):
        delivery, session, enrollment = self.scheduled(mode="paper")
        self.assertIn("Paper to deposit", self.dashboard()._participant(enrollment.id)["attendance"][0]["state"])
        self.paper(session, enrollment)
        row = self.dashboard()._participant(enrollment.id)
        self.assertIn("awaiting review", row["attendance"][0]["state"])
        self.assertIsNone(row["attendance"][0]["minutes"])
        asynchronous = self.opened()
        row = self.dashboard()._participant(asynchronous.id)
        self.assertTrue(row["attendance_na"])
        self.assertFalse(row["attendance"])
        self.assertIsNone(self.dashboard()._dashboard(asynchronous.delivery_id.id)["metrics"][-1]["rate"])

    def test_missing_schedule_is_in_incomplete_attendance_filter(self):
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        enrollment = self.enrollment(delivery)
        row = self.dashboard()._participant(enrollment.id)
        self.assertTrue(row["attendance_missing"])
        self.assertTrue(row["attendance_incomplete"])
        self.assertEqual(self.dashboard()._dashboard(delivery.id, issue="attendance")["population"], 1)
        line = self.env["training.dashboard.line"].with_user(self.coordinator)
        self.assertEqual(line.search([("attendance_incomplete", "=", True)]).ids, enrollment.ids)
        asynchronous = self.enrollment(self.delivery())
        self.assertFalse(self.dashboard()._participant(asynchronous.id)["attendance_incomplete"])

    def test_anonymous_rows_never_read_individual_response_state(self):
        assignment, _grant = self.assigned_evaluation()
        # Anonymous population projection must not call the nominative state hook.
        feedback = (
            self.env["training.feedback"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional anonymous feedback",
                    "program_id": self.program.id,
                    "purpose": "immediate",
                    "criteria": "Fictional scale",
                    "anonymous": True,
                }
            )
        )
        campaign = (
            self.env["training.feedback.campaign"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional anonymous campaign",
                    "feedback_id": feedback.id,
                    "delivery_id": assignment.delivery_id.id,
                    "population": "Fictional participants",
                    "retention_id": self.retention.id,
                    "due_at": fields.Datetime.now(),
                }
            )
        )
        # Recipient eligibility is enforced by S09.2, even before publication.
        self.env["training.feedback.recipient"].with_user(self.coordinator).create(
            {
                "campaign_id": campaign.id,
                "user_id": self.portal.id,
                "role": "participant",
                "enrollment_id": assignment.enrollment_id.id,
            }
        )
        cls = type(self.env["training.feedback.recipient"])
        with patch.object(cls, "_nominative_state", side_effect=AssertionError("individual state touched")):
            rows = self.dashboard(self.supervisor)._participant(assignment.enrollment_id.id)["feedback"]
        self.assertEqual(rows[0]["code"], "anonymous")
        self.assertFalse(rows[0]["late"])

    def test_population_filters_do_not_duplicate_or_hide_cancelled(self):
        assignment, _grant = self.assigned_evaluation()
        enrollment = assignment.enrollment_id
        action = assignment.evaluation_id.action_new_version()
        version = self.env["training.evaluation"].with_user(self.coordinator).browse(action["res_id"])
        version.action_publish()
        second = (
            self.env["training.evaluation.assignment"]
            .with_user(self.coordinator)
            .create(
                {
                    "evaluation_id": version.id,
                    "enrollment_id": enrollment.id,
                    "opens_at": assignment.opens_at,
                    "due_at": assignment.due_at,
                }
            )
        )
        self.assertTrue(second)
        self.assertEqual(self.dashboard()._dashboard(assignment.delivery_id.id)["population"], 1)
        enrollment.action_abandon(reason="Fictional departure")
        data = self.dashboard()._dashboard(assignment.delivery_id.id, state="abandoned")
        self.assertEqual(data["population"], 1)
        self.assertEqual((data["cohort_metrics"][0]["numerator"], data["cohort_metrics"][0]["denominator"]), (1, 1))
        self.assertEqual(self.dashboard()._dashboard(assignment.delivery_id.id, state="confirmed")["population"], 0)
        with self.assertRaises(ValidationError):
            self.dashboard()._dashboard(assignment.delivery_id.id, start="2027-02-01", end="2027-01-01")
        with self.assertRaises(AccessError):
            self.dashboard()._dashboard(assignment.delivery_id.id, session_id=999999)

    def test_zero_score_is_present_and_denominator_zero_is_unavailable(self):
        assignment, _grant = self.assigned_evaluation()
        data = self.dashboard()._dashboard(assignment.delivery_id.id)
        self.assertIsNone(data["rows"][0]["evaluations"][0]["score"])
        self.assertIsNone(data["metrics"][0]["rate"])
        self.decision(assignment, score=0)
        data = self.dashboard()._dashboard(assignment.delivery_id.id)
        self.assertEqual(data["rows"][0]["evaluations"][0]["score"], 0)
        self.assertEqual(data["metrics"][0]["denominator"], 1)
        self.assertEqual(data["metrics"][0]["rate"], 0)

    def test_acquired_ratio_uses_validated_reference_and_coverage(self):
        assignment, _grant = self.assigned_evaluation()
        delivery = assignment.delivery_id
        delivery.write({"capacity": 30})
        assignments = assignment
        for index in range(19):
            partner = self.env["res.partner"].create({"name": "Fictional S10 participant %s" % index})
            enrollment = self.enrollment(delivery, participant_id=partner.id, user_id=False)
            enrollment.action_validate_prerequisites(reason="Fictional eligibility")
            enrollment.action_confirm()
            assignments |= (
                self.env["training.evaluation.assignment"]
                .with_user(self.coordinator)
                .create(
                    {
                        "evaluation_id": assignment.evaluation_id.id,
                        "enrollment_id": enrollment.id,
                        "opens_at": assignment.opens_at,
                        "due_at": assignment.due_at,
                    }
                )
            )
        for index, row in enumerate(assignments[:12]):
            self.decision(row, score=80 if index < 10 else 0)
        data = self.dashboard()._dashboard(delivery.id)
        metric = data["metrics"][0]
        self.assertEqual((metric["numerator"], metric["denominator"], metric["population"]), (10, 12, 20))
        self.assertAlmostEqual(metric["rate"], 83.3333333)
        self.assertEqual(data["population"], 20)
        self.assertEqual(len({row["id"] for row in data["rows"]}), 20)

    def test_lifecycle_notices_replay_failure_and_recipient_revocation(self):
        assignment, _grant = self.assigned_evaluation()
        enrollment = assignment.enrollment_id
        model = self.env["training.notification"].with_user(self.coordinator)
        notice = model._queue(enrollment, "confirmation", "confirmation")
        self.assertTrue(notice.mail_id)
        before = self.env["mail.mail"].sudo().search_count([])
        self.assertEqual(model._queue(enrollment, "confirmation", "confirmation"), notice)
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), before)
        notice.mail_id.sudo().write({"state": "exception", "failure_reason": "Fictional delivery error"})
        data = self.dashboard()._dashboard(enrollment.delivery_id.id)
        self.assertTrue(any("Fictional delivery error" in n["failure"] for n in data["notifications"]))
        self.assertEqual(model._queue(enrollment, "confirmation", "confirmation").mail_id.state, "outgoing")
        self.assertFalse(notice.mail_id.email_cc or notice.mail_id.recipient_ids or notice.mail_id.attachment_ids)
        enrollment.action_abandon(reason="Fictional withdrawal")
        self.assertFalse(notice._authorized())
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()

    def test_deadline_journal_is_idempotent_without_a_second_feedback_engine(self):
        assignment, _grant = self.assigned_evaluation()
        journal = self.env["training.notification"].with_user(self.coordinator)
        journal._cron_deadlines()
        first = journal.search([("assignment_id", "=", assignment.id), ("kind", "=", "deadline")])
        self.assertEqual(len(first), 1)
        journal._cron_deadlines()
        self.assertEqual(journal.search([("assignment_id", "=", assignment.id), ("kind", "=", "deadline")]), first)

    def test_export_has_manifest_but_no_new_response_identity(self):
        assignment, _grant = self.assigned_evaluation()
        line = self.env["training.dashboard.line"].with_user(self.supervisor).browse(assignment.enrollment_id.id)
        line.export_data(["name", "state"])
        log = self.env["training.dashboard.export"].with_user(self.supervisor).search([])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.manifest["enrollment_ids"], assignment.enrollment_id.ids)
        self.assertEqual(log.actor_id, self.supervisor)
        with self.assertRaises(ValidationError):
            line.export_data(["delivery_id/evaluation_supervisor_ids/login"])
        with self.assertRaises(AccessError):
            log.write({"manifest": {}})

    def test_selected_company_and_ordinary_reader_cannot_bypass_scope(self):
        assignment, _grant = self.assigned_evaluation()
        for user in (self.reader, self.internal, self.portal):
            with self.assertRaises(AccessError):
                self.dashboard(user)._dashboard(assignment.delivery_id.id)
        self.coordinator.write({"company_ids": [Command.set((self.company | self.other_company).ids)]})
        service = self.dashboard().with_context(allowed_company_ids=self.other_company.ids)
        self.assertEqual(service._deliveries(), [])
        with self.assertRaises(AccessError):
            service._dashboard(assignment.delivery_id.id)
        self.assertFalse(
            self.env["training.dashboard.line"]
            .with_user(self.coordinator)
            .with_context(allowed_company_ids=self.other_company.ids)
            .search([])
        )

    def test_pdf_review_records_human_checks_and_original_hash(self):
        material = self.material()
        self.env.ref("training_management.group_training_coordinator").write(
            {"user_ids": [Command.link(self.quality.id)]}
        )
        reviews = self.env["training.pdf.accessibility.review"].with_user(self.quality)
        form = Form(reviews, view="training_management.view_pdf_accessibility_review_form")
        form.material_id = material
        form.notes = "Fictional human check: correction needed"
        review = form.save()
        self.assertEqual(review.action_record_review()["res_id"], review.id)
        self.assertIn(material.display_name, review.name)
        self.assertEqual(reviews.fields_get(["notes"])["notes"]["string"], "Findings and Corrections")
        self.assertFalse(review.passed)
        self.assertEqual(review.source_sha256, material.sha256)
        self.assertEqual(review.reviewer_id, self.quality)
        with self.assertRaises(AccessError):
            review.write({"contrast": True})
        with self.assertRaises(AccessError):
            self.env["training.pdf.accessibility.review"].with_user(self.supervisor).create(
                {"material_id": material.id, "notes": "Unauthorized"}
            )

    def test_french_code_messages_and_native_selection_labels(self):
        from odoo.tools.translate import load_language

        load_language(self.env.cr, "fr_FR")
        delivery, _session, enrollment = self.scheduled(mode="paper")
        service = self.dashboard().with_context(lang="fr_FR")
        row = service._participant(enrollment.id)
        self.assertIn("Papier", row["attendance"][0]["state"])
        line = (
            self.env["training.dashboard.line"]
            .with_user(self.coordinator)
            .with_context(lang="fr_FR")
            .browse(enrollment.id)
        )
        labels = dict(line.fields_get(["state"])["state"]["selection"])
        self.assertNotEqual(labels["confirmed"], "Confirmed")
        self.assertIn("83,33", service._ratio("Fictif", 10, 12, 20, "S10-1")["rate_text"])
        self.assertEqual(
            self.env["training.pdf.accessibility.review"]
            .with_context(lang="fr_FR")
            .fields_get(["notes"])["notes"]["string"],
            "Constats et corrections",
        )

    def test_private_learning_entries_absent_and_no_sends_on_read(self):
        assignment, _grant = self.assigned_evaluation()
        before = self.env["mail.mail"].sudo().search_count([])
        data = self.dashboard()._dashboard(assignment.delivery_id.id)
        self.assertNotIn("entries", str(data))
        self.assertFalse(self.dashboard(self.supervisor)._dashboard(assignment.delivery_id.id)["notifications"])
        self.assertEqual(before, self.env["mail.mail"].sudo().search_count([]))


@tagged("post_install", "-at_install")
class TestDashboardHttp(EvaluationCase, HttpCase):
    def test_portal_scoped_dashboard_no_cache_and_revoked_link(self):
        assignment, _grant = self.assigned_evaluation()
        self.authenticate(self.portal_b.login, self.portal_b.login)
        url = "/my/training-dashboard/%s" % assignment.delivery_id.id
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertIn(assignment.enrollment_id.participant_id.name, response.text)
        self.assertIn("dashboard_state", response.text)
        assignment.delivery_id.write({"evaluation_instructor_ids": [Command.clear()]})
        self.assertEqual(self.url_open(url).status_code, 404)

    def test_invalid_period_is_explained_without_disclosing_an_unauthorized_delivery(self):
        assignment, _grant = self.assigned_evaluation()
        self.authenticate(self.portal_b.login, self.portal_b.login)
        url = "/my/training-dashboard/%s?start=2027-02-01&end=2027-01-01" % assignment.delivery_id.id
        response = self.url_open(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn("The end of the period must follow its start.", response.text)
        self.assertIn('role="alert"', response.text)
        self.assertIn('value="2027-02-01"', response.text)
        self.assertNotIn(assignment.enrollment_id.participant_id.name, response.text)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        assignment.delivery_id.write({"evaluation_instructor_ids": [Command.clear()]})
        denied = self.url_open(url)
        self.assertEqual(denied.status_code, 404)
        self.assertNotIn(assignment.delivery_id.name, denied.text)
