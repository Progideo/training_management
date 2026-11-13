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

    public_catalogue = fields.Boolean(string="Publier la présentation générale", copy=False)

    @api.private
    def _catalogue_offers(self, company):
        """Adapters return scalar general information, never pedagogical records."""
        return []

    @api.private
    def _catalogue_rows(self, company):
        offers = self._catalogue_offers(company)
        # Exact website operator and explicit publication grants only. Public
        # ORM access stays denied; neither privileged records nor private fields
        # are passed to a template or searched using visitor input.
        courses = self.sudo().search(
            [
                ("company_id", "=", company.id),
                ("active", "=", True),
                "|",
                ("public_catalogue", "=", True),
                ("id", "in", [offer["course_id"] for offer in offers]),
            ]
        )
        return [
            {
                "id": course.id,
                "name": course.name,
                "presentation": course.presentation or "",
                "objectives": course.general_objectives or "",
                "category_id": course.category_id.id,
                "category": course.category_id.name or "",
                "offers": [offer for offer in offers if offer["course_id"] == course.id],
            }
            for course in courses
        ]
