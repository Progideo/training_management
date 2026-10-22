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
    reason_required = fields.Boolean(compute="_compute_labels")
    reason = fields.Text()
    conflict_description = fields.Text(readonly=True)
    conflict_reason = fields.Text(string="Reason for Resource Exception")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        context = self.env.context
        # Bound list actions pass the selection as active_* values.
        if "res_model" in fields_list and not values.get("res_model") and context.get("active_model"):
            values["res_model"] = context["active_model"]
        if "res_ids" in fields_list and not values.get("res_ids") and context.get("active_ids"):
            values["res_ids"] = ",".join(str(record_id) for record_id in context["active_ids"])
        if values.get("res_model") == "training.delivery" and values.get("action_name") == "action_confirm":
            ids = [int(item) for item in (values.get("res_ids") or "").split(",") if item.strip().isdigit()]
            records = self.env["training.delivery"].browse(ids).exists()
            records._require_coordinator()
            try:
                # Read-only preview: without a reason _reserve never records a
                # waiver. Confirmation rechecks everything under its locks.
                records.filtered(lambda item: item.state == "preparation").session_ids._reserve()
            except ValidationError as error:
                if getattr(error, "training_resource_conflict", False):
                    values["conflict_description"] = str(error)
        return values

    @api.private
    def _model(self):
        self.ensure_one()
        # Only controlled training models that list the action are accepted:
        # the assistant is not a way to call an arbitrary method by name.
        if self.res_model not in self.env or self.action_name not in getattr(
            self.env[self.res_model], "_reason_actions", ()
        ):
            raise ValidationError(self.env._("This action does not accept a reason from the assistant."))
        return self.env[self.res_model]

    @api.private
    def _record_ids(self):
        self.ensure_one()
        return [int(item) for item in (self.res_ids or "").split(",") if item.strip().isdigit()]

    @api.depends("res_model", "res_ids", "action_name")
    def _compute_labels(self):
        for wizard in self:
            wizard.reason_required = True
            try:
                model = wizard._model()
            except ValidationError:
                wizard.action_label = False
                wizard.target_count = 0
                continue
            wizard.action_label = model._reason_labels().get(wizard.action_name, wizard.action_name)
            wizard.target_count = len(wizard._record_ids())
            if wizard.res_model == "training.delivery" and wizard.action_name == "action_confirm":
                records = model.browse(wizard._record_ids()).exists()
                records.check_access("read")
                wizard.reason_required = any(records.mapped("below_threshold"))
                if not wizard.reason_required:
                    wizard.action_label = self.env._("Confirm with Exception")

    def action_apply(self):
        self.ensure_one()
        model = self._model()
        ids = self._record_ids()
        records = model.browse([i for i in ids if i]).exists()
        if not ids or not all(ids) or len(records) != len(set(ids)):
            raise ValidationError(self.env._("The selected records no longer exist."))
        records.check_access("write")
        if self.reason_required and not (self.reason or "").strip():
            raise ValidationError(self.env._("Enter a reason for this action."))
        confirmation = self.res_model == "training.delivery" and self.action_name == "action_confirm"
        try:
            # A failed member of a batch must not confirm its earlier members.
            with self.env.cr.savepoint():
                if confirmation:
                    records.action_confirm(reason=self.reason, conflict_reason=self.conflict_reason)
                else:
                    getattr(records, self.action_name)(reason=self.reason)
        except ValidationError as error:
            if not confirmation or not getattr(error, "training_resource_conflict", False):
                raise
            self.write({"conflict_description": str(error)})
            return {
                "type": "ir.actions.act_window",
                "name": self.env._("Resource Exception"),
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }
        return {"type": "ir.actions.act_window_close"}
