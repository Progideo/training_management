"""Request acknowledgements now come from a native template: record the digest of mails
queued before this version so that transport accepts them."""

from odoo.addons.training_management.models.training_mail_journal import mail_fingerprint


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    rows = env["training.request.notice"].sudo().search([("mail_id", "!=", False), ("mail_fingerprint", "=", False)])
    for row in rows:
        row._store_evidence({"mail_fingerprint": mail_fingerprint(row.mail_id)})
