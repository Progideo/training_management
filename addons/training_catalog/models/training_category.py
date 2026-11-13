from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingCategory(models.Model):
    _name = "training.category"
    _description = "Training Category"
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, ondelete="restrict"
    )

    @api.constrains("name")
    def _check_name(self):
        if any(not (record.name or "").strip() for record in self):
            raise ValidationError(self.env._("Enter a category name."))

    def write(self, vals):
        self.check_access("write")
        self.lock_for_update()
        if "company_id" in vals and any(record.company_id.id != vals["company_id"] for record in self):
            raise ValidationError(
                self.env._("A training category keeps its company. Create a category in the other company.")
            )
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used(self):
        self.lock_for_update()
        if self.env["training.course"].with_context(active_test=False).search_count([("category_id", "in", self.ids)]):
            raise ValidationError(self.env._("Archive categories used by courses instead of deleting them."))
