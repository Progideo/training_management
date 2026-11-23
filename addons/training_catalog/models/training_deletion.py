"""Deletion of evidence (conservation configurée, 22 November 2026).

Evidence stays by default, as in standard Odoo nothing is purged without a configured
rule. An administrator (``base.group_system``) may delete it, by hand or through a rule
he configured (Data Recycle, automated actions run as ``__system__``). The legal hold
(``frozen``) blocks the deletion. The real user decides, never ``sudo()`` alone: a
portal flow running in sudo stays refused.
"""

from odoo.exceptions import ValidationError


def require_evidence_deletion(records, message, error=ValidationError):
    """Refuse the deletion of evidence unless an administrator deletes it outside any hold."""
    if not records:
        return
    env = records.env
    if not env.user._is_system():
        raise error(message)
    rows = records.sudo().with_context(active_test=False)
    finished = getattr(type(records), "_training_finished_states", None)
    unfinished = rows._training_unfinished() if hasattr(rows, "_training_unfinished") else None
    if (finished is not None and any(row.state not in finished for row in rows)) or unfinished:
        raise ValidationError(env._("Only a finished or cancelled dossier can be deleted."))
    parents = getattr(type(records), "_training_hold_parents", ())
    for row in rows:
        holders = [row] if "frozen" in row._fields else []
        holders += [row[name] for name in parents if row[name]]
        if any(holder.frozen for holder in holders):
            raise ValidationError(env._("Release the legal hold before deleting this evidence."))
    # The mails of a deleted journal go with it, as Odoo deletes the messages of a deleted
    # record: once their document is gone, nobody could delete them any more.
    mail_fields = [
        name
        for name, field in rows._fields.items()
        if field.type == "many2one" and field.comodel_name == "mail.mail" and field.store
    ]
    mails = env["mail.mail"].sudo()
    for name in mail_fields:
        mails |= rows[name]
    mails.exists().unlink()
