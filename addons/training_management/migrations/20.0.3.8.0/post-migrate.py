"""Training emails now come from native templates; transport compares a digest of the
queued mail. Mails queued before this version keep their original content: record its
digest so that they can still leave."""

from odoo.addons.training_management.models.training_mail_journal import mail_fingerprint

JOURNALS = {
    "training.notification": "mail_id",
    "training.learning.notice": "mail_id",
    "training.practice.notice": "mail_id",
    "training.tutoring.notice": "mail_id",
    "training.feedback.notice": "mail_id",
    "training.publication.notice": "mail_id",
    "training.operator.notice": "mail_id",
    "training.session.alert.notice": "mail_id",
    "training.session.alert.subscription": "confirmation_mail_id",
}


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    from odoo.tools import SQL

    env = api.Environment(cr, SUPERUSER_ID, {})
    for model, field in JOURNALS.items():
        if model not in env:
            continue
        rows = (
            env[model]
            .sudo()
            .with_context(active_test=False)
            .search([(field, "!=", False), ("mail_fingerprint", "=", False)])
        )
        # Direct update: the journals are retained evidence, their write metadata stays unchanged.
        for row in rows:
            cr.execute(
                SQL(
                    "UPDATE %s SET mail_fingerprint = %s WHERE id = %s",
                    SQL.identifier(env[model]._table),
                    mail_fingerprint(row[field]),
                    row.id,
                )
            )
