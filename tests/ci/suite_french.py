"""Prepare the French Website before running the complete cumulative suite."""
# ruff: noqa: F821 -- Odoo shell provides env.

from odoo import Command
from odoo.tools.translate import load_language

if env.cr.dbname != "tm_suite_test":
    raise RuntimeError("Only the disposable cumulative suite database is allowed")
load_language(env.cr, "fr_FR")
french = env.ref("base.lang_fr")
env["website"].search([]).write({"language_ids": [Command.set(french.ids)], "default_lang_id": french.id})
env.cr.commit()
print("CUMULATIVE_FRENCH_WEBSITE_READY")
