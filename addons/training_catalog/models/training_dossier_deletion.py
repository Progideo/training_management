from odoo import api, models
from odoo.exceptions import AccessError

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
        for records in self.sudo().with_context(active_test=False)._training_dossier_records():
            records.exists().unlink()
        return True

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
