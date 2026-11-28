"""« My courses »: translate the main menu entries added untranslated by 20.0.3.9.0."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["website.menu"].search([("url", "=", "/my/trainings")])._training_courses_menu_labels()
