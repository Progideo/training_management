from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingCourse(models.Model):
    _name = "training.course"
    _description = "Standard Training Course"
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    category_id = fields.Many2one("training.category", ondelete="restrict", check_company=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="restrict",
        index=True,
    )
    presentation = fields.Text(translate=True, string="General Presentation")
    general_objectives = fields.Text(translate=True)

    @api.constrains("name")
    def _check_name(self):
        if any(not (course.name or "").strip() for course in self):
            raise ValidationError(self.env._("A course name is required."))
