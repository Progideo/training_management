from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, ValidationError
from odoo.tools import clean_context


class RatingRating(models.Model):
    _inherit = "rating.rating"

    is_public_course_review = fields.Boolean(
        string="Publish on the Training Catalogue",
        groups="website.group_website_designer",
        copy=False,
    )
    course_review_course_id = fields.Many2one(
        "training.course", compute="_compute_course_review_course", store=True, ondelete="set null",
    )
    course_review_company_id = fields.Many2one(
        related="course_review_course_id.company_id", store=True, index="btree_not_null",
    )
    course_review_author_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="set null")
    course_review_moderator_id = fields.Many2one("res.users", readonly=True, copy=False)
    course_review_moderated_at = fields.Datetime(readonly=True, copy=False)

    _course_review_once = models.UniqueIndex(
        "(res_id, partner_id) WHERE res_model = 'training.course' AND consumed AND partner_id IS NOT NULL",
        "A participant can only submit one review per course.",
    )

    @api.depends("res_model", "res_id")
    def _compute_course_review_course(self):
        courses = self.filtered(lambda rating: rating.res_model == "training.course")
        for review in courses:
            review.course_review_course_id = self.env["training.course"].sudo().browse(review.res_id).exists()
        (self - courses).course_review_course_id = False

    @api.model_create_multi
    def create(self, vals_list):
        course_model = self.env["ir.model"]._get_id("training.course")
        if any(vals.get("res_model_id", self.env.context.get("default_res_model_id")) == course_model for vals in vals_list):
            raise AccessError(self.env._("Submit course reviews from the catalogue."))
        return super().create(vals_list)

    @api.private
    def _create_course_review(self, course, user, score, feedback):
        # Eligibility and consent are verified by the course service. Preserve
        # the native rating row without creating a public chatter message or token.
        ratings = self.sudo().with_context(clean_context(self.env.context))
        try:
            with self.env.cr.savepoint():
                review = super(RatingRating, ratings).create({
                    "res_model_id": self.env["ir.model"]._get_id("training.course"),
                    "res_id": course.id,
                    "partner_id": user.partner_id.id,
                    "course_review_author_id": user.id,
                    "rating": score,
                    "feedback": feedback,
                    "consumed": True,
                    "access_token": False,
                    "is_public_course_review": False,
                })
                review.flush_recordset(["res_model", "consumed"])
        except IntegrityError as error:
            if error.diag.constraint_name == "rating_rating_course_review_once":
                raise ConcurrencyError("Concurrent course review; retry with a fresh snapshot") from error
            raise

    def write(self, vals):
        course_model = self.env["ir.model"]._get_id("training.course")
        reviews = self.filtered(lambda rating: rating.res_model == "training.course")
        if reviews or vals.get("res_model_id") == course_model:
            if (
                reviews != self
                or set(vals) != {"is_public_course_review"}
                or not self.env.user.has_group("website.group_website_designer")
                or any(review.course_review_company_id not in self.env.companies for review in reviews)
            ):
                raise AccessError(self.env._("Only website designers can moderate course reviews in their companies."))
            if vals["is_public_course_review"]:
                for review in reviews.sudo():
                    course = review.course_review_course_id
                    author = review.course_review_author_id
                    if (
                        not course.active
                        or not course.public_catalogue
                        or not author.active
                        or author.partner_id != review.partner_id
                        or not course._has_course_review_participation(author)
                    ):
                        raise ValidationError(self.env._("Publication requires verified participation."))
            vals = {
                **vals,
                "course_review_moderator_id": self.env.user.id,
                "course_review_moderated_at": fields.Datetime.now(),
            }
        return super().write(vals)
