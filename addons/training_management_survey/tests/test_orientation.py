"""P10: explainable, optional pre-purchase advice without retaining answers."""

from urllib.parse import urlencode
from io import BytesIO

from PIL import Image
from odoo.tools.binary import BinaryBytes

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.training_management.tests.test_catalogue import CatalogueCase


class OrientationCase(CatalogueCase):
    def diagnostic(self, **values):
        survey = (
            self.env["survey.survey"]
            .with_user(self.coordinator)
            .create(
                {
                    "title": "Choisir sa formation",
                    "orientation_company_id": self.company.id,
                    "orientation_contact": "Conseiller fictif : conseil@example.invalid",
                    "scoring_type": "no_scoring",
                    **values,
                }
            )
        )
        questions = (
            self.env["survey.question"]
            .with_user(self.coordinator)
            .create(
                [
                    {
                        "survey_id": survey.id,
                        "title": title,
                        "question_type": "simple_choice",
                        "sequence": index,
                        "suggested_answer_ids": [Command.create({"value": v}) for v in choices],
                    }
                    for index, (title, choices) in enumerate(
                        [
                            ("Votre pratique ?", ("Je débute", "Pratique régulière")),
                            ("Votre objectif ?", ("Découvrir", "Approfondir")),
                        ]
                    )
                ]
            )
        )
        rule = (
            self.env["training.orientation.rule"]
            .with_user(self.coordinator)
            .create(
                {
                    "survey_id": survey.id,
                    "answer_ids": [
                        Command.set(
                            questions[0].suggested_answer_ids[:1].ids + questions[1].suggested_answer_ids[:1].ids
                        )
                    ],
                    "level": "Découverte",
                    "explanation": "Commencez par les bases pour découvrir la méthode.",
                }
            )
        )
        answers = {str(q.id): str(q.suggested_answer_ids[0].id) for q in questions}
        return survey, questions, rule, answers


@tagged("post_install", "-at_install")
class TestOrientation(OrientationCase, HttpCase):
    def test_rules_complete_missing_foreign_and_ambiguous(self):
        survey, questions, rule, answers = self.diagnostic()
        other = rule.copy({"level": "Avancé"})
        survey.action_orientation_publish()
        self.assertFalse(survey._orientation_result(answers))
        # An overlapping or contradictory configuration must never choose arbitrarily.
        self.assertFalse(survey._orientation_result({}))
        self.assertFalse(survey._orientation_result({**answers, "forged": "1"}))
        self.assertFalse(
            survey._orientation_result({str(questions[0].id): str(questions[1].suggested_answer_ids[0].id)})
        )
        self.assertTrue(other)

    def test_explanation_level_and_no_match(self):
        survey, questions, rule, answers = self.diagnostic()
        survey.action_orientation_publish()
        result = survey._orientation_result(answers)
        self.assertEqual(result["name"], "Découverte")
        self.assertEqual(result["explanation"], rule.explanation)
        self.assertEqual(len(result["criteria"]), 2)
        self.assertEqual(result["programs"], [])
        self.assertFalse(
            survey._orientation_result({**answers, str(questions[0].id): str(questions[0].suggested_answer_ids[1].id)})
        )
        self.assertFalse(survey._orientation_result({str(questions[0].id): answers[str(questions[0].id)]}))
        self.assertFalse(
            survey._orientation_result({**answers, str(questions[0].id): str(questions[1].suggested_answer_ids[0].id)})
        )

    def test_public_programme_path_and_withdrawal(self):
        program = self.new_program(public_catalogue=True)
        program.action_validate()
        program.action_publish()
        path = (
            self.env["training.path"]
            .with_user(self.coordinator)
            .create({"name": "Parcours découverte", "step_ids": [Command.create({"program_id": program.id})]})
        )
        path.action_validate()
        for target in ({"program_id": program.id}, {"path_id": path.id}):
            survey, _, rule, answers = self.diagnostic()
            rule.write({"level": False, **target})
            survey.action_orientation_publish()
            self.assertEqual(survey._orientation_result(answers)["programs"], [(program.id, program.title)])
        path.active = False
        self.assertFalse(survey._orientation_result(answers))
        path.active = True
        program.action_retire()
        self.assertFalse(survey._orientation_result(answers))

    def test_definition_validation_and_company(self):
        survey, questions, rule, _ = self.diagnostic()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            rule.write({"answer_ids": [Command.set(questions[0].suggested_answer_ids.ids)]})
        private = self.new_program()
        rule.write({"level": False, "program_id": private.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            survey.action_orientation_publish()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            rule.write({"level": "Duplicate target"})
        other = self.env["training.path"].create({"name": "Other private", "company_id": self.other_company.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            rule.sudo().write({"program_id": False, "path_id": other.id})
        rule.write({"program_id": False, "level": "Découverte"})
        questions[0].comments_allowed = True
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            survey.action_orientation_publish()

    def test_freeze_copy_and_forged_publication(self):
        survey, questions, rule, _ = self.diagnostic()
        form_view = self.env.ref("training_management_survey.orientation_form_view")
        self.assertEqual(form_view.type, "form")
        self.assertIn("orientation_rule_ids", survey.get_view(view_id=form_view.id, view_type="form")["arch"])
        survey.action_orientation_publish()
        for record, vals in (
            (survey, {"title": "Changed"}),
            (survey, {"orientation_company_id": False}),
            (questions[0], {"title": "Changed"}),
            (questions[0].suggested_answer_ids[0], {"value": "Changed"}),
            (rule, {"explanation": "Changed"}),
        ):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                record.write(vals)
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                record.unlink()
        new = survey.copy()
        self.assertFalse(new.orientation_published)
        self.assertEqual(len(new.question_ids), 2)
        self.assertTrue(all(a.question_id.survey_id == new for a in new.orientation_rule_ids.answer_ids))
        new.action_orientation_publish()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.diagnostic(orientation_published=True)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["survey.survey"].with_context(default_orientation_published=True).create({"title": "Forged"})

    def test_reparenting_cannot_import_recorded_answers(self):
        diagnostic, questions, _, _ = self.diagnostic()
        ordinary = self.env["survey.survey"].with_user(self.coordinator).create({"title": "Ordinary history"})
        question = (
            self.env["survey.question"]
            .with_user(self.coordinator)
            .create(
                {
                    "survey_id": ordinary.id,
                    "title": "Answered native question",
                    "question_type": "simple_choice",
                    "suggested_answer_ids": [Command.create({"value": "Yes"}), Command.create({"value": "No"})],
                }
            )
        )
        attempt = self.env["survey.user_input"].create({"survey_id": ordinary.id})
        choice = question.suggested_answer_ids[0]
        line = self.env["survey.user_input.line"].create(
            {
                "user_input_id": attempt.id,
                "question_id": question.id,
                "answer_type": "suggestion",
                "suggested_answer_id": choice.id,
            }
        )
        for record, vals in (
            (question, {"survey_id": diagnostic.id}),
            (choice, {"question_id": questions[0].id}),
            (choice, {"matrix_question_id": questions[0].id}),
        ):
            with self.subTest(model=record._name, field=next(iter(vals))):
                with self.env.cr.savepoint():
                    with self.assertRaises(ValidationError):
                        record.with_user(self.coordinator).write(vals)
        self.assertEqual(line.question_id.survey_id, ordinary)
        self.assertEqual(line.suggested_answer_id.question_id, question)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["survey.question.answer"].with_user(self.coordinator).create(
                {
                    "question_id": question.id,
                    "matrix_question_id": questions[0].id,
                    "value": "Ambiguous parent",
                }
            )
        # Reusing a template by duplication creates new definitions, with no history.
        clone = question.with_user(self.coordinator).copy({"survey_id": diagnostic.id})
        self.assertEqual(clone.survey_id, diagnostic)
        self.assertFalse(self.env["survey.user_input.line"].search_count([("question_id", "=", clone.id)]))

    def test_rule_company_cannot_be_forged(self):
        diagnostic, _, rule, _ = self.diagnostic()
        actor = self.coordinator
        actor.company_ids = [Command.link(self.other_company.id)]
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            rule.with_user(actor).write({"company_id": self.other_company.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["training.orientation.rule"].with_user(actor).create(
                {
                    "survey_id": diagnostic.id,
                    "company_id": self.other_company.id,
                    "answer_ids": [Command.set(rule.answer_ids.ids)],
                    "level": "Forged scope",
                    "explanation": "Wrong company",
                }
            )

        copied = (
            self.env["training.orientation.rule"]
            .with_user(actor)
            .with_context(default_company_id=self.other_company.id)
            .create(
                {
                    "survey_id": diagnostic.id,
                    "answer_ids": [Command.set(rule.answer_ids.ids)],
                    "level": "Correct scope",
                    "explanation": "Derived company",
                }
            )
        )
        self.assertEqual(copied.company_id, diagnostic.orientation_company_id)

    def test_native_editor_and_text_only_public_choices(self):
        survey, questions, _, _ = self.diagnostic()
        action = survey.action_orientation_recommendations()
        self.assertTrue(action)
        view = questions.get_view(
            view_id=self.env.ref("training_management_survey.orientation_question_form").id, view_type="form"
        )
        # The specialized native editor does not advertise ignored answer features.
        from lxml import etree

        arch = etree.fromstring(view["arch"])
        answer_list = arch.xpath("//field[@name='suggested_answer_ids']/list")[0]
        self.assertEqual(answer_list.xpath("./field/@name"), ["sequence", "value"])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            survey.action_orientation_open()
        image = BytesIO()
        Image.new("RGB", (2, 2), "blue").save(image, "PNG")
        questions[0].suggested_answer_ids[0].write({"value": " ", "value_image": BinaryBytes(image.getvalue())})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            survey.action_orientation_publish()
        questions[0].suggested_answer_ids[0].value = "Readable choice"
        survey.action_orientation_publish()
        self.assertEqual(survey.action_orientation_open()["url"], f"/formations/orientation/{survey.id}")
        survey.active = False
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            survey.action_orientation_open()

    def test_permissions_and_no_native_persistence(self):
        survey, questions, rule, _ = self.diagnostic()
        survey.action_orientation_publish()
        for user in (self.portal, self.reader, self.internal, self.env.ref("base.public_user")):
            for record in (survey, questions[0], questions[0].suggested_answer_ids[0], rule):
                with self.assertRaises(AccessError), self.env.cr.savepoint():
                    record.with_user(user).read()
            for action in (
                "action_orientation_publish",
                "action_orientation_recommendations",
                "action_orientation_open",
            ):
                with self.assertRaises(AccessError), self.env.cr.savepoint():
                    getattr(survey.with_user(user), action)()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            survey.with_context(allowed_company_ids=[self.other_company.id]).with_user(self.coordinator).read()
        for values in ({"survey_id": survey.id}, {"survey_id": survey.id, "test_entry": True}):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                self.env["survey.user_input"].sudo().create(values)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["survey.user_input"].sudo().with_context(default_survey_id=survey.id).create({})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            survey.sudo()._create_answer(test_entry=True)
        ordinary = self.env["survey.survey"].create({"title": "Ordinary native survey"})
        attempt = self.env["survey.user_input"].create({"survey_id": ordinary.id})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            attempt.sudo().write({"survey_id": survey.id})
        native_question = self.env["survey.question"].create(
            {"survey_id": ordinary.id, "title": "Ordinary question", "question_type": "char_box"}
        )
        line = self.env["survey.user_input.line"].create(
            {
                "user_input_id": attempt.id,
                "question_id": native_question.id,
                "answer_type": "char_box",
                "value_char_box": "ordinary",
            }
        )
        for values in (
            {"question_id": questions[0].id},
            {"suggested_answer_id": questions[0].suggested_answer_ids[0].id},
            {"matrix_row_id": questions[0].suggested_answer_ids[0].id},
        ):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                line.sudo().write(values)
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                self.env["survey.user_input.line"].sudo().create(
                    {
                        "user_input_id": attempt.id,
                        "question_id": native_question.id,
                        "answer_type": "char_box",
                        "value_char_box": "forged orientation response",
                        **values,
                    }
                )
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["survey.user_input.line"].sudo().with_context(default_question_id=questions[0].id).create(
                {"user_input_id": attempt.id, "answer_type": "char_box", "value_char_box": "forged default"}
            )

    def test_http_public_privacy_native_boundaries_and_no_effects(self):
        survey, _, rule, answers = self.diagnostic()
        attachment = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Private diagnostic file",
                    "res_model": "survey.survey",
                    "res_id": survey.id,
                    "raw": b"PRIVATE ORIENTATION FILE",
                }
            )
        )
        survey.action_orientation_publish()
        draft, _, _, _ = self.diagnostic(title="Private draft")
        other_coordinator = new_test_user(
            self.env,
            login="orientation_other",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set([self.other_company.id])],
        )
        other = survey.sudo().copy(
            {"orientation_company_id": self.other_company.id, "title": "Other company", "user_id": other_coordinator.id}
        )
        other.action_orientation_publish()
        counts = {
            m: self.env[m].sudo().search_count([])
            for m in (
                "survey.user_input",
                "survey.user_input.line",
                "training.enrollment",
                "training.path.assignment",
                "res.partner",
            )
        }
        self.authenticate(None, None)
        self.assertIn(survey.title, self.url_open("/formations/orientation").text)
        self.assertIn("orientation", self.url_open("/formations").text)
        url = f"/formations/orientation/{survey.id}"
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(rule.explanation, response.text)
        self.assertIn("sans conservation", response.text)
        for _ in range(2):
            response = self.url_open(url, data={"csrf_token": self.csrf_token(), **answers})
            self.assertEqual(response.status_code, 200)
            self.assertIn(rule.explanation, response.text)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
            self.assertIn("ni admission", response.text)
        response = self.url_open(url, data={"csrf_token": self.csrf_token()})
        self.assertIn("Demandons conseil", response.text)
        self.assertNotIn(rule.explanation, response.text)
        response = self.url_open(url, data={"csrf_token": self.csrf_token(), **answers, "forged": "1"})
        self.assertNotIn(rule.explanation, response.text)
        response = self.url_open(url + "?" + urlencode(answers), data={"csrf_token": self.csrf_token()})
        self.assertNotIn(rule.explanation, response.text)
        self.assertIn("Demandons conseil", response.text)
        response = self.url_open(
            url, data=[("csrf_token", self.csrf_token()), *answers.items(), next(iter(answers.items()))]
        )
        self.assertNotIn(rule.explanation, response.text)
        self.assertEqual(self.url_open(url, data=answers).status_code, 400)
        for private_url in (
            f"/formations/orientation/{draft.id}",
            f"/formations/orientation/{other.id}",
            f"/survey/start/{survey.access_token}",
            f"/survey/print/{survey.access_token}",
        ):
            self.assertEqual(self.url_open(private_url).status_code, 404)
        self.assertIn(self.url_open(f"/web/content/{attachment.id}").status_code, (403, 404))
        self.authenticate(self.portal.login, self.portal.login)
        self.assertIn(rule.explanation, self.url_open(url, data={"csrf_token": self.csrf_token(), **answers}).text)
        if "crm.lead" in self.env:
            self.assertIn("/formations/demande?advice=1", response.text)
            guided = self.url_open("/formations/demande?advice=1&kind=individual")
            self.assertEqual(guided.status_code, 200)
            self.assertNotIn(rule.explanation, guided.text)
        self.authenticate(None, None)
        survey.active = False
        self.assertEqual(self.url_open(url).status_code, 404)
        self.assertEqual(counts, {m: self.env[m].sudo().search_count([]) for m in counts})
