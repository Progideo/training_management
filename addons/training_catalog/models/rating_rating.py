from odoo import fields, models


class RatingRating(models.Model):
    _inherit = "rating.rating"

    is_public_course_review = fields.Boolean(
        string="Publish on the Training Catalogue",
        groups="website.group_website_designer",
        copy=False,
    )
