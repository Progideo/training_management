from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    training_course_id = fields.Many2one(
        "training.course",
        string="Training Catalogue Entry",
        ondelete="restrict",
        check_company=True,
        help="Commercial product linked to a standard course; a programme version is chosen on each quotation line.",
    )
    training_price_basis = fields.Selection(
        [
            ("person", "Per person"),
            ("package", "Package"),
        ],
    )

    training_public_session_price = fields.Boolean(
        string="Public Inter-company Price",
        copy=False,
        help="Price per participant, excluding taxes, shown on the website for the inter-company sessions of this course.",
    )

    @api.constrains("training_public_session_price", "training_course_id", "training_price_basis", "sale_ok", "active")
    def _check_public_session_price(self):
        for product in self.filtered("training_public_session_price"):
            if product.training_price_basis != "person" or not product.sale_ok:
                raise ValidationError(
                    self.env._("The public inter-company price must be a saleable per-person tariff.")
                )
            others = self.search_count(
                [
                    ("id", "!=", product.id),
                    ("training_course_id", "=", product.training_course_id.id),
                    ("training_public_session_price", "=", True),
                ]
            )
            if others:
                raise ValidationError(self.env._("A course has only one public inter-company price."))

    @api.constrains("training_course_id", "training_price_basis", "type")
    def _check_training_product(self):
        for product in self:
            if product.training_course_id and (product.type != "service" or not product.training_price_basis):
                raise ValidationError(self.env._("A training commercial product must be a service with a price basis."))
            if product.training_price_basis and not product.training_course_id:
                raise ValidationError(self.env._("Choose a training catalogue entry for this price basis."))
