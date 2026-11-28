from odoo import api, models

COURSES_URL = "/my/trainings"


class WebsiteMenu(models.Model):
    _inherit = "website.menu"

    def _compute_visible(self):
        res = super()._compute_visible()
        courses = self.filtered(lambda menu: menu.is_visible and menu.url == COURSES_URL)
        if courses:
            # « My courses » only for a signed-in person who has a course; the page itself
            # stays reachable and authorizes every row.
            courses.is_visible = self.env["training.portal.navigation"]._has_courses()
        return res

    @api.model
    def _training_courses_menu(self):
        """Add « My courses » to the main menu of each website lacking it, in every installed language.

        Run once at installation and by the 20.0.3.9.0 migration: a menu removed by the
        site editor is not added back by later updates.
        """
        for website in self.env["website"].search([], limit=None):
            if not website.menu_id or self.search_count([("website_id", "=", website.id), ("url", "=", COURSES_URL)]):
                continue
            menu = self.create(
                {
                    "name": self.env._("My training"),
                    "url": COURSES_URL,
                    "parent_id": website.menu_id.id,
                    "website_id": website.id,
                    "sequence": 90,
                }
            )
            menu._training_courses_menu_labels()

    def _training_courses_menu_labels(self):
        """Translate the entry in every installed language, keeping a label changed in the editor."""
        for code, _name in self.env["res.lang"].get_installed():
            label = self.with_context(lang=code).env._("My training")
            for menu in self.with_context(lang=code):
                if menu.name in ("My training", label):
                    menu.name = label
