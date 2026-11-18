from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, ValidationError
from odoo.tools import clean_context


REVIEW_ACTIVITY = "training_catalog.activity_course_review"


class RatingRating(models.Model):
    _name = "rating.rating"
    _inherit = ["rating.rating", "mail.thread", "mail.activity.mixin"]

    is_public_course_review = fields.Boolean(
        string="Publish on the Training Catalogue",
        groups="website.group_website_designer",
        copy=False,
    )
    course_review_course_id = fields.Many2one(
        "training.course",
        compute="_compute_course_review_course",
        store=True,
        ondelete="set null",
    )
    course_review_company_id = fields.Many2one(
        related="course_review_course_id.company_id",
        store=True,
        index="btree_not_null",
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

    def unlink(self):
        # mail.thread asks to remove ratings of this rating. Its empty result
        # must terminate the native cascade, including empty loyalty records.
        if not self:
            return True
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        course_model = self.env["ir.model"]._get_id("training.course")
        if any(
            vals.get("res_model_id", self.env.context.get("default_res_model_id")) == course_model for vals in vals_list
        ):
            raise AccessError(self.env._("Submit course reviews from the catalogue."))
        return super().create(vals_list)

    @api.private
    def _create_course_review(self, course, user, score, feedback):  # pylint: disable=missing-return,super-method-mismatch  # checked private factory keeps public writes blocked
        # Eligibility and consent are verified by the course service. Preserve
        # the native rating row without creating a public chatter message or token.
        ratings = self.sudo().with_context(
            clean_context(self.env.context),
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
        )
        try:
            with self.env.cr.savepoint():
                review = super(RatingRating, ratings).create(  # pylint: disable=super-method-mismatch  # server-authorized review factory
                    {
                        "res_model_id": self.env["ir.model"]._get_id("training.course"),
                        "res_id": course.id,
                        "partner_id": user.partner_id.id,
                        "course_review_author_id": user.id,
                        "rating": score,
                        "feedback": feedback,
                        "consumed": True,
                        "access_token": False,
                        "is_public_course_review": False,
                    }
                )
                review.flush_recordset(["res_model", "consumed"])
                review._schedule_course_review_activity()
        except IntegrityError as error:
            if error.diag.constraint_name == "rating_rating_course_review_once":
                raise ConcurrencyError("Concurrent course review; retry with a fresh snapshot") from error
            raise

    @api.private
    def _schedule_course_review_activity(self):
        self.ensure_one()
        company = self.course_review_company_id
        user = company.course_review_responsible_id
        if (
            user
            and company._is_course_review_responsible(user)
            and not self.course_review_moderated_at
            and not self.activity_search([REVIEW_ACTIVITY], only_automated=True)
        ):
            self.with_context(mail_notify_force_send=False).activity_schedule(
                REVIEW_ACTIVITY,
                user_id=user.id,
            )

    def action_approve_course_review(self):
        self._check_course_review_action()
        return self.write({"is_public_course_review": True})

    def action_reject_course_review(self):
        self._check_course_review_action()
        return self.write({"is_public_course_review": False})

    @api.private
    def _check_course_review_action(self):
        self.ensure_one()
        if self.res_model != "training.course" or not self.consumed:
            raise AccessError(self.env._("Choose a submitted course review."))

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
        result = super().write(vals)
        if reviews:
            feedback = (
                self.env._("Course review approved.")
                if vals["is_public_course_review"]
                else self.env._("Course review rejected or withdrawn.")
            )
            reviews.sudo().activity_feedback([REVIEW_ACTIVITY], feedback=feedback)
        return result
