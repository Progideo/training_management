"""The three session emails are now written in English with a French translation. They are
`noupdate`: reload them once from the module data, with their French translation."""

from odoo.tools import convert_file, file_path
from odoo.tools.translate import TranslationImporter

MODULE = "training_management_sale"
FILES = ("data/session_confirmation_template.xml", "data/session_registration_mail_templates.xml")
TEMPLATES = (
    "mail_template_session_confirmation",
    "mail_template_session_registration_waiting",
    "mail_template_session_registration_payment",
)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for filename in FILES:
        convert_file(env, MODULE, filename, {}, mode="init", noupdate=True)
    importer = TranslationImporter(cr, verbose=False)
    xmlids = ["%s.%s" % (MODULE, name) for name in TEMPLATES]
    for code, _name in env["res.lang"].get_installed():
        if code.split("_")[0] == "fr":
            importer.load_file(file_path("%s/i18n/fr.po" % MODULE), code, xmlids=xmlids)
    importer.save(overwrite=True, force_overwrite=True)
