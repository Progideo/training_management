from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    training_course_id = fields.Many2one(
        "training.course", string="Training Catalogue Entry",
        ondelete="restrict", check_company=True,
        help="Commercial product linked to a standard course; a programme version is chosen on each quotation line.",
    )
    training_price_basis = fields.Selection([
        ("person", "Per person"), ("package", "Package"),
    ], string="Training Price Basis")

    @api.constrains("training_course_id", "training_price_basis", "type")
    def _check_training_product(self):
        for product in self:
            if product.training_course_id and (
                product.type != "service" or not product.training_price_basis
            ):
                raise ValidationError(_("A training commercial product must be a service with a price basis."))
            if product.training_price_basis and not product.training_course_id:
                raise ValidationError(_("Choose a training catalogue entry for this price basis."))
