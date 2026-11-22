from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import SQL

from .training_deletion import require_evidence_deletion

# Native models holding training evidence, deleted with their dossier.
EVIDENCE_NATIVE_MODELS = ("survey.user_input",)


class TrainingDossierDeletion(models.AbstractModel):
    _name = "training.dossier.deletion"
    _description = "Deletion of a Finished Training Dossier"

    def action_training_delete_dossier(self):
        """Delete finished dossiers with the training evidence depending on them, deepest first.

        Meant for an administrator, by hand or from an automated action he configured
        (conservation configurée, 22 November 2026). Native records (sales, invoices,
        leads) are never deleted: when one still references the dossier, the database
        refuses and nothing is deleted.
        """
        if not self.env.user._is_system():
            raise AccessError(self.env._("Only an administrator can delete a dossier."))
        require_evidence_deletion(self, self.env._("Keep this dossier and its evidence."))
        ordered = self.sudo().with_context(active_test=False)._training_dossier_records()
        self._training_break_cycles(ordered)
        for records in ordered:
            records.exists().unlink()
        return True

    def action_training_anonymize_dossier(self):
        """Clear the personal data copied by finished dossiers and their training evidence.

        Each model lists its copies in ``_training_personal_fields``; the evidence itself
        stays. Sent mails of the journals are deleted. Meant for an administrator, by hand
        or from an automated action he configured (conservation configurée).
        """
        if not self.env.user._is_system():
            raise AccessError(self.env._("Only an administrator can anonymize a dossier."))
        if not self:
            return True
        require_evidence_deletion(self, self.env._("Keep this dossier and its evidence."))
        dossiers = self.sudo().with_context(active_test=False)
        dossiers._training_clear_personal(dossiers._training_dossier_records())
        if "anonymized_at" in dossiers._fields:
            # Training records are immutable through the ORM: stamp them like the copies.
            self.env.cr.execute(
                SQL(
                    "UPDATE %s SET anonymized_at = %s WHERE id IN %s",
                    SQL.identifier(dossiers._table),
                    fields.Datetime.now(),
                    tuple(dossiers.ids),
                )
            )
            dossiers.invalidate_recordset(["anonymized_at"])
        return True

    @api.private
    def _training_clear_personal(self, recordsets):
        mails = self.env["mail.mail"]
        self.env.flush_all()
        for rows in recordsets:
            if not rows:
                continue
            names = getattr(type(rows), "_training_personal_fields", ())
            placeholders = getattr(type(rows), "_training_personal_placeholders", ())
            for name in names:
                if name in placeholders:
                    # A recipient is required: a neutral address unique to the row replaces it.
                    value = SQL("'anonymized-' || id || '@anonymized.invalid'")
                else:
                    value = SQL("%s", "" if rows._fields[name].required else None)
                # Bypass the write guards of the evidence: only the personal copy changes.
                self.env.cr.execute(
                    SQL(
                        "UPDATE %s SET %s = %s WHERE id IN %s",
                        SQL.identifier(rows._table),
                        SQL.identifier(name),
                        value,
                        tuple(rows.ids),
                    )
                )
            if names:
                rows.invalidate_recordset(names)
            if "mail_id" in rows._fields:
                mails |= rows.mail_id
        mails.exists().unlink()

    @api.private
    def _training_break_cycles(self, ordered):
        """Clear optional links between records deleted together (two evidence rows may reference each other)."""
        doomed = {}
        for records in ordered:
            doomed.setdefault(records._name, set()).update(records.ids)
        self.env.flush_all()
        for records in ordered:
            for field in records._fields.values():
                targets = doomed.get(getattr(field, "comodel_name", None))
                if field.type != "many2one" or not field.store or field.required or not targets:
                    continue
                self.env.cr.execute(
                    SQL(
                        "UPDATE %s SET %s = NULL WHERE id IN %s AND %s IN %s",
                        SQL.identifier(records._table),
                        SQL.identifier(field.name),
                        tuple(records.ids),
                        SQL.identifier(field.name),
                        tuple(targets),
                    )
                )
            records.invalidate_recordset()

    @api.private
    def _training_dossier_records(self):
        """Recordsets to delete with ``self``: dependents first, ``self`` last."""
        dependents = {}

        def fields_to(model_name):
            if model_name not in dependents:
                dependents[model_name] = [
                    (name, field.name)
                    for name, model in self.env.registry.items()
                    if not model._abstract
                    and not model._transient
                    and name != model_name
                    and (name.startswith("training.") or name in EVIDENCE_NATIVE_MODELS)
                    for field in model._fields.values()
                    if field.type == "many2one"
                    and field.store
                    and field.comodel_name == model_name
                    and field.ondelete != "set null"
                ]
            return dependents[model_name]

        ordered, seen = [], set()

        def visit(records):
            records = records.browse([rid for rid in records.ids if (records._name, rid) not in seen])
            if not records:
                return
            seen.update((records._name, rid) for rid in records.ids)
            for model_name, field_name in fields_to(records._name):
                visit(records.env[model_name].search([(field_name, "in", records.ids)]))
            ordered.append(records)

        visit(self)
        return ordered
