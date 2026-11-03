from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class SharedCatalogCase(TransactionCase):
    """D20/D21/D36: usable without either application, scoped to an operator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_company = cls.env["res.company"].create({"name": "Fictional Catalogue B"})
        cls.editor = new_test_user(
            cls.env,
            login="shared_catalog_editor",
            groups="training_catalog.group_catalog_editor",
            company_id=cls.env.company.id,
            company_ids=[Command.set(cls.env.company.ids)],
        )
        cls.reader = new_test_user(
            cls.env, login="shared_catalog_reader", groups="training_catalog.group_catalog_reader"
        )
        cls.portal = new_test_user(cls.env, login="shared_catalog_portal", groups="base.group_portal")
        cls.category = cls.env["training.category"].with_user(cls.editor).create({"name": "Methods"})
        cls.course = (
            cls.env["training.course"]
            .with_user(cls.editor)
            .create(
                {
                    "name": "Fictional shared course",
                    "category_id": cls.category.id,
                    "presentation": "General presentation",
                    "general_objectives": "Apply a method",
                }
            )
        )

    def test_editor_reader_and_public_boundaries(self):
        self.assertEqual(self.course.with_user(self.reader).presentation, "General presentation")
        with self.assertRaises(AccessError):
            self.course.with_user(self.reader).write({"name": "Forbidden"})
        for user in (self.portal, self.env.ref("base.public_user")):
            with self.assertRaises(AccessError):
                self.course.with_user(user).read(["name"])
        if "training.enrollment" in self.env:
            with self.assertRaises(AccessError):
                self.env["training.enrollment"].with_user(self.editor).search([])

    def test_company_scope_and_relations(self):
        foreign = self.env["training.category"].create(
            {
                "name": "Foreign category",
                "company_id": self.other_company.id,
            }
        )
        course = self.env["training.course"].create(
            {
                "name": "Foreign course",
                "company_id": self.other_company.id,
            }
        )
        self.assertNotIn(course, self.env["training.course"].with_user(self.editor).search([]))
        with self.assertRaises(AccessError):
            course.with_user(self.editor).read(["name"])
        with self.assertRaises((AccessError, UserError, ValidationError)), self.env.cr.savepoint():
            self.course.write({"category_id": foreign.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.category.write({"company_id": self.other_company.id})

    def test_archive_and_valid_names(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.category.unlink()
        self.category.active = False
        self.assertEqual(self.course.category_id, self.category)
        for model in ("training.course", "training.category"):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.env[model].with_user(self.editor).create({"name": "  "})

    def test_catalogue_action_keeps_its_independent_form(self):
        with Form(self.course, view="training_catalog.view_training_course_form") as form:
            form.presentation = "Edited through the independent catalogue form"
        self.assertEqual(self.course.presentation, "Edited through the independent catalogue form")
        action = self.env.ref("training_catalog.action_training_courses")
        form_id = dict((mode, view_id) for view_id, mode in action.views)["form"]
        self.assertEqual(form_id, self.env.ref("training_catalog.view_training_course_form").id)
        self.assertNotIn("action_open_programs", self.env["ir.ui.view"].browse(form_id).arch_db)

    def test_catalogue_has_no_business_dependency(self):
        dependencies = (
            self.env["ir.module.module"].search([("name", "=", "training_catalog")]).dependencies_id.mapped("name")
        )
        self.assertFalse({"training_management", "training_elearning", "sale_management", "survey"} & set(dependencies))
