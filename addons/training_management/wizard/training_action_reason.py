from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingActionReason(models.TransientModel):
    """Collect the reason of one motivated action, then call its public method.

    The assistant only chooses which public method receives the reason. Every
    control (rights, state, company, locking, history) stays in the models.
    """

    _name = "training.action.reason"
    _description = "Training Action Reason"

    res_model = fields.Char(string="Model", required=True)
    res_ids = fields.Char(string="Record IDs", required=True)
    action_name = fields.Char(string="Action Method", required=True)
    action_label = fields.Char(string="Action", compute="_compute_labels")
    target_count = fields.Integer(string="Selected Records", compute="_compute_labels")
    reason = fields.Text(required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        context = self.env.context
        # Bound list actions pass the selection as active_* values.
        if "res_model" in fields_list and not values.get("res_model") and context.get("active_model"):
            values["res_model"] = context["active_model"]
        if "res_ids" in fields_list and not values.get("res_ids") and context.get("active_ids"):
            values["res_ids"] = ",".join(str(record_id) for record_id in context["active_ids"])
        return values

    @api.private
    def _model(self):
        self.ensure_one()
        # Only controlled training models that list the action are accepted:
        # the assistant is not a way to call an arbitrary method by name.
        if self.res_model not in self.env or self.action_name not in getattr(
                self.env[self.res_model], "_reason_actions", ()):
            raise ValidationError(self.env._("This action does not accept a reason from the assistant."))
        return self.env[self.res_model]

    @api.private
    def _record_ids(self):
        self.ensure_one()
        return [int(item) for item in (self.res_ids or "").split(",") if item.strip().isdigit()]

    @api.depends("res_model", "res_ids", "action_name")
    def _compute_labels(self):
        for wizard in self:
            try:
                model = wizard._model()
            except ValidationError:
                wizard.action_label = False
                wizard.target_count = 0
                continue
            wizard.action_label = model._reason_labels().get(wizard.action_name, wizard.action_name)
            wizard.target_count = len(wizard._record_ids())

    def action_apply(self):
        self.ensure_one()
        model = self._model()
        ids = self._record_ids()
        records = model.browse(ids).exists()
        if not ids or len(records) != len(set(ids)):
            raise ValidationError(self.env._("The selected records no longer exist."))
        records.check_access("write")
        getattr(records, self.action_name)(reason=self.reason)
        return {"type": "ir.actions.act_window_close"}
