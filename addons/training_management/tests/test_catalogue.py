from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestCatalogue(TransactionCase):
    """CAT01 (internal scope), CAT02 and SEC01 with restricted users."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Fictional Company B"})
        cls.coordinator = new_test_user(
            cls.env,
            login="catalogue_coordinator",
            groups="training_management.group_training_coordinator,base.group_allow_export",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.reader = new_test_user(
            cls.env,
            login="catalogue_reader",
            groups="training_management.group_training_reader,base.group_allow_export",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.internal = new_test_user(cls.env, login="catalogue_unassigned")
        cls.portal = new_test_user(
            cls.env,
            login="catalogue_portal",
            groups="base.group_portal",
        )
        cls.contact = cls.env["res.partner"].create(
            {
                "name": "Fictional Accessibility Contact",
                "company_id": cls.company.id,
            }
        )
        cls.course = (
            cls.env["training.course"]
            .with_user(cls.coordinator)
            .create(
                {
                    "name": "Standard Course A",
                    "company_id": cls.company.id,
                }
            )
        )
        cls.other_course = cls.env["training.course"].create(
            {
                "name": "Standard Course B",
                "company_id": cls.other_company.id,
            }
        )
        cls.values = {
            "course_id": cls.course.id,
            "version": "V1",
            "title": "Programme A",
            "objectives": "Apply a documented method",
            "target_audience": "Beginners",
            "prerequisites": "None",
            "content": "Practice and review",
            "duration_hours": 7,
            "delivery_mode": "onsite",
            "language_id": cls.env.ref("base.lang_en").id,
            "teaching_methods": "Guided practice",
            "evaluation_criteria": "Final exercise",
            "access_conditions": "Confirmed registration",
            "accessibility_contact_id": cls.contact.id,
            "accessibility_information": "Contact the accessibility coordinator.",
        }

    def new_program(self, **overrides):
        return (
            self.env["training.program.version"]
            .with_user(self.coordinator)
            .create(
                {
                    **self.values,
                    **overrides,
                }
            )
        )

    def test_version_lifecycle_preserves_v1(self):
        v1 = self.new_program()
        v1.action_validate()
        self.assertEqual(v1.validated_by_id, self.coordinator)
        self.assertTrue(v1.validated_at)
        v1.action_publish()
        published_at = v1.published_at
        v1.action_publish()
        self.assertEqual(v1.published_at, published_at)
        v2 = v1.copy({"version": "V2", "objectives": "New objectives"})
        self.assertEqual(v2.state, "draft")
        self.assertFalse(v2.validated_at)
        v2.action_validate()
        v2.action_publish()
        self.assertEqual(v1.objectives, self.values["objectives"])
        self.assertEqual(v1.title, self.values["title"])
        self.course.name = "Renamed catalogue entry"
        self.assertEqual(v1.title, self.values["title"])
        v1.action_retire()
        self.assertEqual(v1.state, "retired")
        self.assertEqual(v1.retired_by_id, self.coordinator)
        self.assertEqual(v2.state, "published")

    def test_incomplete_validation_and_direct_publish_refused(self):
        program = self.new_program(objectives="  ", duration_hours=0)
        with self.assertRaises(ValidationError):
            program.action_validate()
        with self.assertRaises(ValidationError):
            program.write({"state": "published"})
        self.assertEqual(program.state, "draft")

    def test_published_content_and_metadata_protected(self):
        program = self.new_program()
        program.action_validate()
        for values in (
            {"title": "Rewritten"},
            {"course_id": self.other_course.id},
            {"state": "draft"},
            {"validated_by_id": self.reader.id},
            {"validated_at": False},
            {"company_id": self.other_company.id},
        ):
            with self.subTest(values=values), self.assertRaises((ValidationError, AccessError)):
                program.write(values)
        with self.assertRaises(ValidationError):
            program.unlink()
        with self.assertRaises(ValidationError):
            program.update_field_translations("title", {"en_US": "Rewritten by translation"})

    def test_context_cannot_create_validated_version(self):
        program = (
            self.env["training.program.version"]
            .with_user(self.coordinator)
            .with_context(
                default_state="published",
                default_validated_by_id=self.reader.id,
                default_published_at="2026-01-01 00:00:00",
            )
            .create(self.values)
        )
        self.assertEqual(program.state, "draft")
        self.assertFalse(program.validated_by_id)
        self.assertFalse(program.published_at)
        with self.assertRaises(ValidationError):
            self.new_program(version="V2", state="published")

    def test_no_edit_and_transition_in_same_call(self):
        program = self.new_program()
        with self.assertRaises(ValidationError):
            program.write({"state": "validated", "objectives": "Different"})
        self.assertEqual(program.objectives, self.values["objectives"])

    @mute_logger("odoo.sql_db")
    def test_unique_reference_and_positive_duration(self):
        self.new_program()
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.new_program(version=" V1 ")
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.new_program(version="V2", duration_hours=-1)

    def test_reader_read_export_only(self):
        program = self.new_program().with_user(self.reader)
        self.assertEqual(program.read(["title"])[0]["title"], "Programme A")
        self.assertEqual(program.export_data(["version"])["datas"], [["V1"]])
        for operation in (
            lambda: program.write({"title": "Changed"}),
            program.action_validate,
            program.action_publish,
            program.action_retire,
            program.action_new_version,
            program.unlink,
            lambda: program.create({**self.values, "version": "V2"}),
            lambda: self.course.with_user(self.reader).write({"name": "Changed"}),
        ):
            with self.assertRaises(AccessError):
                operation()

    def test_unassigned_portal_public_have_no_model_access(self):
        program = self.new_program()
        for user in (self.internal, self.portal, self.env.ref("base.public_user")):
            for record in (self.course, program):
                restricted = record.with_user(user)
                for operation in (
                    lambda: restricted.read(["display_name"]),
                    lambda: restricted.write({"display_name": "Changed"}),
                    restricted.unlink,
                ):
                    with self.subTest(user=user.login, model=record._name), self.assertRaises(AccessError):
                        operation()
                with self.assertRaises((AccessError, UserError)):
                    restricted.export_data(["display_name"])
            with self.assertRaises(AccessError):
                program.with_user(user).action_validate()
            with self.assertRaises(AccessError):
                program.with_user(user).create(self.values)

    def test_cross_company_read_write_export_create_denied(self):
        other = self.env["training.program.version"].create(
            {
                **self.values,
                "course_id": self.other_course.id,
                "accessibility_contact_id": False,
            }
        )
        for user in (self.reader, self.coordinator):
            record = other.with_user(user).with_context(allowed_company_ids=[self.company.id])
            self.assertFalse(record.search([("id", "=", record.id)]))
            for operation in (
                lambda: record.read(["title"]),
                lambda: record.export_data(["title"]),
                lambda: record.write({"title": "Changed"}),
            ):
                with self.assertRaises(AccessError):
                    operation()
        with self.assertRaises(AccessError):
            self.new_program(course_id=self.other_course.id, accessibility_contact_id=False)

    def test_cross_company_contact_refused(self):
        contact = self.env["res.partner"].create(
            {
                "name": "Other contact",
                "company_id": self.other_company.id,
            }
        )
        with self.assertRaises(UserError), self.cr.savepoint():
            self.new_program(accessibility_contact_id=contact.id)

    def test_company_and_parent_history_preserved(self):
        program = self.new_program()
        with self.assertRaises(ValidationError):
            self.course.write({"company_id": self.other_company.id})
        with self.assertRaises(ValidationError):
            self.course.unlink()
        self.course.active = False
        self.assertTrue(program.exists())
        self.assertEqual(program.company_id, self.company)

    def test_batch_transition_is_atomic(self):
        first = self.new_program()
        second = self.new_program(version="V2", prerequisites="")
        with self.assertRaises(ValidationError):
            (first | second).action_validate()
        self.assertEqual(first.state, "draft")
        self.assertEqual(second.state, "draft")

    def test_source_display_name_identifies_course_and_version_in_each_language(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.course.update_field_translations(
            "name",
            {
                "en_US": "Project management",
                "fr_FR": "Gestion de projet",
            },
        )
        first = self.new_program(title="Same title")
        second = self.new_program(version="V2", title="Same title")
        for lang, course_name in (
            ("fr_FR", "Gestion de projet"),
            ("en_US", "Project management"),
        ):
            source = second.with_context(lang=lang)
            self.assertEqual(source.display_name, f"{course_name} — V2")
            self.assertEqual(first.with_context(lang=lang).display_name, f"{course_name} — V1")
            action = source.action_new_version()
            Wizard = (
                self.env[action["res_model"]]  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
                .with_user(self.coordinator)
                .with_context(
                    action["context"],
                )
            )
            form = Form(Wizard)
            self.assertEqual(form.source_id, source)
            self.assertEqual(form.source_id.display_name, f"{course_name} — V2")
        second.write({"version": "V3"})
        self.assertEqual(second.with_context(lang="fr_FR").display_name, "Gestion de projet — V3")

    def test_new_version_action_keeps_standard_course(self):
        program = self.new_program()
        program.action_validate()
        action = program.action_new_version()
        self.assertEqual(action["res_model"], "training.program.new.version")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_source_id"], program.id)
        self.assertFalse(action["context"]["default_version"])
        # Opening/cancelling the dialog must not create an abandoned programme.
        self.assertEqual(program.search_count([("course_id", "=", self.course.id)]), 1)

    def test_new_version_preserves_all_translations_in_either_session_language(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        source = self.new_program()
        translated_fields = [
            name for name, field in source._fields.items() if field.translate is True and field.store and field.copy
        ]
        self.assertIn("objectives", translated_fields)
        self.assertIn("title", translated_fields)
        translations = {name: {"en_US": f"English {name}", "fr_FR": f"Français {name}"} for name in translated_fields}
        for name, values in translations.items():
            source.update_field_translations(name, values)
        source.action_validate()
        source.action_publish()
        source_audit = source.read(["state", *source._audit_fields()])

        for index, session_language in enumerate(("fr_FR", "en_US"), start=2):
            with self.subTest(session_language=session_language):
                action = source.with_context(lang=session_language).action_new_version()
                Wizard = (
                    self.env[action["res_model"]]  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
                    .with_user(self.coordinator)
                    .with_context(
                        action["context"],
                    )
                )
                with Form(Wizard) as form:
                    form.version = f"V{index}"
                result = form.record.action_create_version()
                target = source.browse(result["res_id"])
                self.env.flush_all()
                self.env.invalidate_all()
                self.assertEqual(target.course_id, source.course_id)
                self.assertEqual(target.state, "draft")
                self.assertEqual(target.version, f"V{index}")
                self.assertTrue(all(not target[name] for name in target._audit_fields()))
                for name, values in translations.items():
                    for lang, text in values.items():
                        self.assertEqual(target.with_context(lang=lang)[name], text)
                        self.assertEqual(source.with_context(lang=lang)[name], text)
                target.with_context(lang="en_US").write({"objectives": "Changed in new draft"})
                self.env.flush_all()
                self.env.invalidate_all()
                self.assertEqual(target.with_context(lang="fr_FR").objectives, translations["objectives"]["fr_FR"])
                self.assertEqual(source.with_context(lang="en_US").objectives, translations["objectives"]["en_US"])
                self.assertEqual(source.read(["state", *source._audit_fields()]), source_audit)

    def test_new_version_wizard_access_restrictions(self):
        program = self.new_program()
        Wizard = self.env["training.program.new.version"]
        values = {"source_id": program.id, "version": "V2"}
        wizard = Wizard.with_user(self.coordinator).create(values)
        for user in (self.reader, self.internal, self.portal, self.env.ref("base.public_user")):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError), self.cr.savepoint():
                    Wizard.with_user(user).create(values)
                with self.assertRaises(AccessError):
                    wizard.with_user(user).action_create_version()
        other = self.env["training.program.version"].create(
            {
                **self.values,
                "course_id": self.other_course.id,
                "accessibility_contact_id": False,
            }
        )
        with self.assertRaises(AccessError), self.cr.savepoint():
            Wizard.with_user(self.coordinator).create({"source_id": other.id, "version": "V2"})

    @mute_logger("odoo.sql_db")
    def test_new_version_wizard_rejects_duplicate_and_blank_references(self):
        program = self.new_program()
        Wizard = self.env["training.program.new.version"].with_user(self.coordinator)
        duplicate = Wizard.create({"source_id": program.id, "version": " V1 "})
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            duplicate.action_create_version()
        blank = Wizard.create({"source_id": program.id, "version": "   "})
        with self.assertRaises(ValidationError):
            blank.action_create_version()
        self.assertEqual(program.search_count([("course_id", "=", self.course.id)]), 1)

    def test_draft_can_be_deleted(self):
        program = self.new_program()
        program.unlink()
        self.assertFalse(program.exists())

    def test_course_opens_programs_with_restricted_access(self):
        action = self.course.with_user(self.reader).action_open_programs()
        self.assertEqual(action["domain"], [("course_id", "=", self.course.id)])
        self.assertEqual(action["target"], "current")
        for user in (self.portal, self.internal):
            with self.assertRaises(AccessError):
                self.course.with_user(user).action_open_programs()
        with self.assertRaises(AccessError):
            self.other_course.with_user(self.coordinator).action_open_programs()

    def test_standalone_form_persists_after_failed_validation(self):
        action = self.course.action_open_programs()
        model = (
            self.env["training.program.version"]  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
            .with_user(self.coordinator)
            .with_context(
                action["context"],
            )
        )
        with Form(model) as form:
            form.version = "V1"
            form.duration_hours = 7
            form.delivery_mode = "onsite"
        program = form.record
        self.assertEqual(program.course_id, self.course)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            program.action_validate()
        with Form(program) as form:
            for field in (
                "objectives",
                "target_audience",
                "prerequisites",
                "content",
                "teaching_methods",
                "evaluation_criteria",
                "access_conditions",
                "accessibility_information",
            ):
                setattr(form, field, self.values[field])
            form.accessibility_contact_id = self.contact.with_user(self.coordinator)
        self.env.flush_all()
        self.env.invalidate_all()
        reloaded = model.browse(program.id)
        self.assertEqual(reloaded.content, self.values["content"])
        self.assertEqual(reloaded.objectives, self.values["objectives"])
        self.assertEqual(reloaded.accessibility_contact_id, self.contact)
        self.assertEqual(model.search_count(action["domain"]), 1)
        reloaded.action_validate()
        self.assertEqual(reloaded.state, "validated")
