"""« My courses »: main menu entry for databases installed before 20.0.3.9.0."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    api.Environment(cr, SUPERUSER_ID, {})["website.menu"]._training_courses_menu()
