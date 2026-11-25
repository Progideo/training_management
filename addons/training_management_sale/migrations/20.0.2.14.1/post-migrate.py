"""Readable session dates and a button in the company's email colours: reload the two
registration emails once from the module data (they are `noupdate`), with their French
translation."""

from odoo.tools import convert_file, file_path
from odoo.tools.translate import TranslationImporter

MODULE = "training_management_sale"
TEMPLATES = ("mail_template_session_registration_waiting", "mail_template_session_registration_payment")


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    convert_file(env, MODULE, "data/session_registration_mail_templates.xml", {}, mode="init", noupdate=True)
    importer = TranslationImporter(cr, verbose=False)
    xmlids = ["%s.%s" % (MODULE, name) for name in TEMPLATES]
    for code, _name in env["res.lang"].get_installed():
        if code.split("_")[0] == "fr":
            importer.load_file(file_path("%s/i18n/fr.po" % MODULE), code, xmlids=xmlids)
    importer.save(overwrite=True, force_overwrite=True)
