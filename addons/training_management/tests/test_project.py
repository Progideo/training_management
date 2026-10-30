"""P12: criterion decisions reuse private S05 evidence and S09 qualified identities."""

from datetime import timedelta
from uuid import uuid4

from lxml import html

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tools.misc import limited_field_access_token
from odoo.tools.translate import load_language

from .test_evaluation import EvaluationCase
from .test_material import PDF


class ProjectCase(EvaluationCase):
    def setup_project(self):
        delivery = self.delivery(learning_tutor_id=self.portal_b.id)
        delivery.write(
            {
                "evaluation_quality_id": self.quality.id,
                "evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)],
            }
        )
        rubric = (
            self.env["training.project.rubric"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Grille fictive V1",
                    "criterion_ids": [
                        Command.create(
                            {
                                "name": "Exactitude",
                                "level_0": "Absent",
                                "level_1": "Partiel",
                                "level_2": "Conforme",
                                "level_3": "Justifié",
                            }
                        ),
                        Command.create(
                            {
                                "name": "Clarté",
                                "level_0": "Illisible",
                                "level_1": "Ambigu",
                                "level_2": "Lisible",
                                "level_3": "Structuré",
                            }
                        ),
                    ],
                }
            )
        )
        rubric.action_publish()
        activity = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Projet fictif",
                    "delivery_id": delivery.id,
                    "criterion": "validation",
                    "project_rubric_id": rubric.id,
                    "project_deliverable": "Rapport PDF et conclusion",
                    "project_service_reference": "FICT-P12",
                    "project_retention_id": self.retention.id,
                }
            )
        )
        enrollment = self.opened(delivery)
        grant = (
            self.env["training.evaluation.authorization"]
            .with_user(self.quality)
            .create(
                {
                    "delivery_id": delivery.id,
                    "user_id": self.portal_b.id,
                    "purpose": "project",
                    "valid_from": fields.Datetime.now() - timedelta(hours=1),
                    "valid_until": fields.Datetime.now() + timedelta(days=1),
                    "reason": "Qualification fictive P12",
                }
            )
        )
        return activity, enrollment, grant

    def project_service(self, user=None):
        return self.env["training.learning.service"].with_user(user or self.portal)

    def submit_project(self, activity, enrollment, **values):
        progress = self.project_service()._progress(enrollment, activity)
        return self.project_service()._post(
            enrollment.id,
            "submission",
            activity_id=activity.id,
            request_key=str(uuid4()),
            body="Rapport fictif privé",
            data=PDF,
            filename="rapport.pdf",
            revision=progress.revision if progress else 0,
            parent_id=progress.latest_submission_id.id if progress else False,
            **values,
        )

    def review_project(self, activity, enrollment, decision="accepted", user=None, **values):
        progress = self.project_service()._progress(enrollment, activity)
        return self.project_service(user or self.portal_b)._post(
            enrollment.id,
            "correction",
            activity_id=activity.id,
            request_key=str(uuid4()),
            body="Conclusion motivée fictive",
            parent_id=progress.latest_submission_id.id,
            revision=progress.revision,
            decision=decision,
            project_ratings={str(c.id): "2" for c in activity.project_rubric_id.criterion_ids},
            **values,
        )


@tagged("post_install", "-at_install")
class TestProject(ProjectCase):
    def test_revision_validation_and_exact_grid_history(self):
        activity, enrollment, _grant = self.setup_project()
        first = self.submit_project(activity, enrollment)
        feedback = self.review_project(activity, enrollment, "changes")
        service = self.project_service()
        self.assertFalse(service._complete(enrollment, activity))
        second = self.submit_project(activity, enrollment)
        accepted = self.review_project(activity, enrollment)
        self.assertTrue(service._complete(enrollment, activity))
        self.assertEqual(second.parent_id, first)
        self.assertEqual(first.data.content, PDF)
        self.assertEqual(feedback.project_snapshot["rubric"], accepted.project_snapshot["rubric"])
        self.assertEqual(first.project_snapshot["ratings"], {})
        self.assertEqual(len(accepted.project_snapshot["ratings"]), 2)
        self.assertTrue(accepted.project_digest)
        origin = service._certificate_origin(enrollment, activity)
        self.assertEqual(origin["project_digest"], accepted.project_digest)
        for operation in (
            lambda: accepted.write({"project_snapshot": {}}),
            lambda: first.unlink(),
            lambda: accepted.copy(),
        ):
            with self.assertRaises((AccessError, ValidationError)):
                operation()
        revised = self.review_project(activity, enrollment, "changes")
        self.assertFalse(service._complete(enrollment, activity))
        self.assertNotEqual(revised, accepted)
        self.assertEqual(accepted.decision, "accepted")

    def test_new_grid_cannot_rewrite_past_or_move_criterion(self):
        activity, enrollment, _grant = self.setup_project()
        self.submit_project(activity, enrollment)
        decision = self.review_project(activity, enrollment)
        before = decision.project_snapshot
        rubric = activity.project_rubric_id
        new = self.env[rubric._name].browse(rubric.action_new_version()["res_id"]).with_user(self.coordinator)
        new.criterion_ids[0].write({"name": "Critère révisé"})
        new.action_publish()
        self.assertEqual(new.previous_id, rubric)
        for operation in (
            lambda: rubric.write({"name": "Réécrit"}),
            lambda: rubric.criterion_ids[0].write({"level_2": "Modifié"}),
            lambda: rubric.criterion_ids[0].write({"rubric_id": new.id}),
            lambda: rubric.criterion_ids[0].unlink(),
            lambda: activity.write({"project_rubric_id": new.id}),
        ):
            with self.assertRaises(ValidationError):
                operation()
        self.assertEqual(decision.project_snapshot, before)

    def test_form_empty_rubric_then_published_and_activity(self):
        with Form(self.env["training.project.rubric"].with_user(self.coordinator)) as form:
            form.name = "Projet depuis formulaire vide"
            with form.criterion_ids.new() as criterion:
                criterion.name = "Démonstration"
                criterion.level_0 = "Absent"
                criterion.level_1 = "Partiel"
                criterion.level_2 = "Conforme"
                criterion.level_3 = "Justifié"
        rubric = form.record
        rubric.action_publish()
        activity, _enrollment, _grant = self.setup_project()
        self.assertTrue(activity.project_retention_id.approved_at)
        delivery = self.delivery()
        with Form(
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .with_context(default_delivery_id=delivery.id)
        ) as project_form:
            project_form.name = "Projet depuis formulaire vide"
            project_form.project_rubric_id = rubric
            project_form.project_deliverable = "Rapport fictif"
            project_form.project_service_reference = "FICT-P12-FORM"
            project_form.project_retention_id = self.retention
        self.assertEqual(project_form.record.criterion, "validation")
        with self.assertRaises(ValidationError):
            self.env["training.project.rubric"].with_user(self.coordinator).create({"name": "Vide"}).action_publish()

    def test_missing_ratings_reason_and_forged_validation(self):
        activity, enrollment, _grant = self.setup_project()
        entry = self.submit_project(activity, enrollment)
        for user in (self.portal, self.coordinator, self.internal, self.quality):
            with self.assertRaises(AccessError):
                self.review_project(activity, enrollment, user=user)
        for ratings, body in (
            ({}, "Motif"),
            ({"999999": "2"}, "Motif"),
            ({str(c.id): "9" for c in activity.project_rubric_id.criterion_ids}, "Motif"),
            ({str(c.id): "2" for c in activity.project_rubric_id.criterion_ids}, " "),
        ):
            with self.assertRaises(ValidationError):
                self.project_service(self.portal_b)._post(
                    enrollment.id,
                    "correction",
                    activity_id=activity.id,
                    request_key=str(uuid4()),
                    parent_id=entry.id,
                    revision=1,
                    body=body,
                    decision="accepted",
                    project_ratings=ratings,
                )
        self.assertFalse(self.project_service()._complete(enrollment, activity))

    def test_grant_mission_and_tutor_revocation_block_all_projections(self):
        activity, enrollment, grant = self.setup_project()
        entry = self.submit_project(activity, enrollment)
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .search([("res_model", "=", entry._name), ("res_id", "=", entry.id), ("res_field", "=", "data")])
        )
        policy = self.env["training.document.policy"]
        self.assertTrue(policy.with_user(self.portal_b)._can_read(attachment))
        grant.write({"active": False})
        for user in (self.portal_b, self.coordinator, self.internal, self.quality):
            self.assertFalse(policy.with_user(user)._can_read(attachment))
            self.assertFalse(self.project_service(user)._entries(enrollment))
        with self.assertRaises(AccessError):
            self.review_project(activity, enrollment)
        self.assertTrue(policy.with_user(self.portal)._can_read(attachment))
        self.assertFalse(entry.message_id.with_user(self.portal_b).search([("id", "=", entry.message_id.id)]))
        enrollment.action_suspend_access(reason="Essai fictif")
        self.assertFalse(policy.with_user(self.portal)._can_read(attachment))

    def test_participant_tutor_cannot_evaluate_self(self):
        activity, enrollment, _grant = self.setup_project()
        self.submit_project(activity, enrollment)
        enrollment.write({"learning_tutor_id": self.portal.id})
        activity.delivery_id.write({"evaluation_instructor_ids": [Command.set(self.portal.partner_id.ids)]})
        self.env["training.evaluation.authorization"].with_user(self.quality).create(
            {
                "delivery_id": activity.delivery_id.id,
                "user_id": self.portal.id,
                "purpose": "project",
                "valid_from": fields.Datetime.now() - timedelta(hours=1),
                "valid_until": fields.Datetime.now() + timedelta(days=1),
                "reason": "Rôle fictif cumulé",
            }
        )
        with self.assertRaises(AccessError):
            self.review_project(activity, enrollment, user=self.portal)

    def test_idempotent_evidence_and_generic_notice_rechecked(self):
        activity, enrollment, grant = self.setup_project()
        key = str(uuid4())
        values = dict(activity_id=activity.id, request_key=key, body="Secret P12", data=PDF, filename="secret.pdf")
        first = self.project_service()._post(enrollment.id, "submission", **values)
        repeated = self.project_service()._post(enrollment.id, "submission", **values)
        self.assertEqual(first, repeated)
        notice = self.env["training.learning.notice"].search([("entry_id", "=", first.id)])
        self.assertEqual(len(notice), 1)
        self.assertTrue(notice._authorized())
        self.assertNotIn("Secret P12", notice.mail_id.body_html)
        self.assertFalse(notice.mail_id.attachment_ids)
        grant.write({"active": False})
        self.assertFalse(notice._authorized())

    def test_removed_mission_foreign_client_and_simple_remises_preserved(self):
        activity, enrollment, _grant = self.setup_project()
        self.submit_project(activity, enrollment)
        activity.delivery_id.write({"evaluation_instructor_ids": [Command.clear()]})
        with self.assertRaises(AccessError):
            self.review_project(activity, enrollment)
        with self.assertRaises(AccessError):
            self.project_service(self.internal)._enrollment(enrollment.id)
        simple = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create({"name": "Remise simple", "delivery_id": activity.delivery_id.id, "criterion": "submission"})
        )
        self.project_service()._post(
            enrollment.id, "submission", activity_id=simple.id, request_key=str(uuid4()), body="Exercice simple"
        )
        self.assertTrue(self.project_service()._complete(enrollment, simple))
        self.assertFalse(self.project_service()._complete(enrollment, activity))

    def test_native_internal_access_company_and_assignment_rechecked(self):
        activity, enrollment, _grant = self.setup_project()
        entry = self.submit_project(activity, enrollment)
        evaluator = self.internal
        enrollment.write({"learning_tutor_id": evaluator.id})
        activity.delivery_id.write({"evaluation_instructor_ids": [Command.set(evaluator.partner_id.ids)]})
        grant = (
            self.env["training.evaluation.authorization"]
            .with_user(self.quality)
            .create(
                {
                    "delivery_id": activity.delivery_id.id,
                    "user_id": evaluator.id,
                    "purpose": "project",
                    "valid_from": fields.Datetime.now() - timedelta(hours=1),
                    "valid_until": fields.Datetime.now() + timedelta(days=1),
                    "reason": "Mission interne fictive",
                }
            )
        )
        self.assertIn(entry.id, self.env[entry._name].with_user(evaluator).search([]).ids)
        self.assertTrue(entry.with_user(evaluator).read(["project_snapshot"])[0]["project_snapshot"])
        client = new_test_user(self.env, login="p12_client", groups="base.group_portal", partner_id=self.customer.id)
        foreign = new_test_user(
            self.env,
            login="p12_foreign",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        for user in (self.coordinator, self.reader, self.quality, foreign, client):
            self.assertFalse(self.env["training.document.policy"].with_user(user)._can_read(entry))
            with self.assertRaises(AccessError):
                entry.with_user(user).read(["project_snapshot"])
        enrollment.write({"learning_tutor_id": self.portal_b.id})
        self.assertFalse(self.env[entry._name].with_user(evaluator).search([("id", "=", entry.id)]))
        with self.assertRaises(AccessError):
            entry.with_user(evaluator).read(["project_snapshot"])
        self.assertTrue(grant.active)


@tagged("post_install", "-at_install")
class TestProjectHTTP(ProjectCase, HttpCase):
    def test_authenticated_project_forms_and_private_file_tokens(self):
        activity, enrollment, grant = self.setup_project()
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(f"/my/trainings/{enrollment.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Rapport PDF", response.text)
        entry = self.submit_project(activity, enrollment)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        response = self.url_open(f"/my/training-tutoring/{enrollment.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("project_rating_", response.text)
        tree = html.fromstring(response.content)
        self.assertFalse(tree.xpath(f"//*[@id='learning-activity-{activity.id}']//form"))
        self.assertTrue(
            tree.xpath(f"//*[@id='learning-entry-{entry.id}']//select[starts-with(@name, 'project_rating_')]")
        )
        self.assertTrue(tree.xpath(f"//*[@id='learning-entry-{entry.id}']//a[contains(@href, '/data')]"))
        latest = self.submit_project(activity, enrollment)
        response = self.url_open(f"/my/training-tutoring/{enrollment.id}")
        tree = html.fromstring(response.content)
        self.assertFalse(tree.xpath(f"//*[@id='learning-entry-{entry.id}']//form"))
        self.assertEqual(
            tree.xpath(f"//*[@id='learning-entry-{latest.id}']//input[@name='parent_id']/@value"), [str(latest.id)]
        )
        progress = self.project_service()._progress(enrollment, activity)
        stale = {
            "csrf_token": self.csrf_token(),
            "kind": "correction",
            "activity_id": activity.id,
            "parent_id": entry.id,
            "revision": progress.revision,
            "request_key": str(uuid4()),
            "body": "Correction périmée",
            "decision": "accepted",
            **{f"project_rating_{c.id}": "2" for c in activity.project_rubric_id.criterion_ids},
        }
        count = self.env["training.learning.entry"].search_count([("enrollment_id", "=", enrollment.id)])
        self.assertEqual(self.url_open(f"/my/training-tutoring/{enrollment.id}/learning", data=stale).status_code, 400)
        self.assertEqual(
            count, self.env["training.learning.entry"].search_count([("enrollment_id", "=", enrollment.id)])
        )
        token = limited_field_access_token(entry, "data", scope="binary")
        url = f"/web/content/{entry._name}/{entry.id}/data?access_token={token}&download=true"
        self.assertEqual(self.url_open(url).content, PDF)
        grant.write({"active": False})
        self.assertIn(self.url_open(url).status_code, (403, 404))
        response = self.url_open(f"/my/training-tutoring/{enrollment.id}")
        self.assertNotIn("project_rating_", response.text)
        self.assertNotIn("Rapport fictif privé", response.text)
        self.authenticate(self.internal.login, self.internal.login)
        self.assertIn(self.url_open(url).status_code, (403, 404))

    def test_post_revision_and_validation_with_preserved_error_input(self):
        load_language(self.cr, "fr_FR")
        self.portal.lang = "fr_FR"
        if self.env["ir.module.module"].search_count([("name", "=", "website"), ("state", "=", "installed")]):
            french = self.env.ref("base.lang_fr")
            self.env["website"].search([]).write(
                {"language_ids": [Command.set(french.ids)], "default_lang_id": french.id}
            )
        activity, enrollment, _grant = self.setup_project()
        self.authenticate(self.portal.login, self.portal.login)
        values = {
            "csrf_token": self.csrf_token(),
            "kind": "submission",
            "activity_id": activity.id,
            "request_key": str(uuid4()),
            "body": "Texte du projet fictif",
        }
        path = f"/my/trainings/{enrollment.id}/learning"
        for _ in range(2):
            response = self.url_open(path, data=values, allow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertTrue(response.headers["Location"].endswith(f"#learning-activity-{activity.id}"))
        progress = self.project_service()._progress(enrollment, activity)
        response = self.url_open(f"/my/trainings/{enrollment.id}")
        tree = html.fromstring(response.content)
        self.assertTrue(tree.xpath(f"//*[@id='submission-saved-{activity.id}'][@role='status']"))
        self.assertIn("Votre remise a bien été enregistrée.", response.text)
        self.assertTrue(tree.xpath(f"//a[@href='#learning-entry-{progress.latest_submission_id.id}']"))
        self.assertTrue(tree.xpath(f"//*[@id='learning-entry-{progress.latest_submission_id.id}']"))
        self.assertTrue(tree.xpath(f"//*[@id='learning-activity-{activity.id}']//form/details[not(@open)]"))
        self.assertFalse(self.project_service()._complete(enrollment, activity))
        before = self.env["training.learning.entry"].search_count([("enrollment_id", "=", enrollment.id)])
        stale = dict(values, request_key=str(uuid4()), body="Version périmée non enregistrée")
        error = self.url_open(path, data=stale)
        self.assertEqual(error.status_code, 400)
        tree = html.fromstring(error.content)
        self.assertFalse(tree.xpath(f"//*[@id='submission-saved-{activity.id}']"))
        self.assertTrue(tree.xpath(f"//*[@id='learning-activity-{activity.id}']//form/details[@open]"))
        self.assertIn("Version périmée non enregistrée", error.text)
        self.assertEqual(
            before, self.env["training.learning.entry"].search_count([("enrollment_id", "=", enrollment.id)])
        )
        self.authenticate(self.portal_b.login, self.portal_b.login)
        progress = self.project_service()._progress(enrollment, activity)
        values = {
            "csrf_token": self.csrf_token(),
            "kind": "correction",
            "activity_id": activity.id,
            "request_key": str(uuid4()),
            "body": "Retour motivé conservé",
            "parent_id": progress.latest_submission_id.id,
            "revision": progress.revision,
            "decision": "accepted",
        }
        criteria = activity.project_rubric_id.criterion_ids
        values[f"project_rating_{criteria[0].id}"] = "2"
        path = f"/my/training-tutoring/{enrollment.id}/learning"
        response = self.url_open(path, data=values)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Retour motivé conservé", response.text)
        tree = html.fromstring(response.content)
        self.assertTrue(
            tree.xpath(
                f"//*[@id='learning-entry-{progress.latest_submission_id.id}']//textarea[@name='body'][text()='Retour motivé conservé']"
            )
        )
        self.assertEqual(
            html.fromstring(response.content).xpath(
                "//select[@name='project_rating_%s']/option[@selected]/@value" % criteria[0].id
            ),
            ["2"],
        )
        values[f"project_rating_{criteria[1].id}"] = "3"
        response = self.url_open(path, data=values, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        correction = self.env["training.learning.entry"].search(
            [("enrollment_id", "=", enrollment.id), ("kind", "=", "correction")]
        )
        self.assertTrue(response.headers["Location"].endswith(f"#learning-entry-{correction.id}"))
        self.assertTrue(self.project_service()._complete(enrollment, activity))
        self.assertEqual(self.url_open(path, data=values, allow_redirects=False).status_code, 303)
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(f"/my/trainings/{enrollment.id}")
        self.assertIn("Retour motivé conservé", response.text)
        self.assertIn("Grille conservée", response.text)
        forged = dict(values, csrf_token=self.csrf_token(), request_key=str(uuid4()))
        self.assertEqual(self.url_open(f"/my/trainings/{enrollment.id}/learning", data=forged).status_code, 404)
