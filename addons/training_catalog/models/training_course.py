from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


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
    public_programme = fields.Html(
        string="Public Programme",
        translate=True,
        sanitize_overridable=False,
        strip_style=True,
    )

    public_reference = fields.Char(string="Public Reference")
    live_duration_days = fields.Float(string="Live Duration (days)")
    public_logo = fields.Image(string="Public Logo", max_width=256, max_height=256)

    _live_duration_nonnegative = models.Constraint(
        "CHECK(live_duration_days >= 0)", "Live duration cannot be negative.",
    )

    @api.constrains("name")
    def _check_name(self):
        if any(not (course.name or "").strip() for course in self):
            raise ValidationError(self.env._("A course name is required."))

    public_catalogue = fields.Boolean(string="Publier la présentation générale", copy=False)

    @api.private
    def _published_catalogue_course(self, company, course_id):
        return self.sudo().search(
            [
                ("id", "=", course_id),
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("public_catalogue", "=", True),
            ],
            limit=1,
        )

    @api.private
    def _has_course_review_participation(self, user):
        """Each delivery adapter supplies its verified participation evidence."""
        return False

    @api.private
    def _course_review_status(self, user):
        self.ensure_one()
        if not user.active or user._is_public():
            return False
        existing = self.env["rating.rating"].sudo().search(
            [("res_model", "=", self._name), ("res_id", "=", self.id),
             ("partner_id", "=", user.partner_id.id), ("consumed", "=", True)],
            limit=1,
        )
        if existing:
            if existing.is_public_course_review:
                return "published"
            return "not_published" if existing.course_review_moderated_at else "pending"
        return "eligible" if self._has_course_review_participation(user) else False

    @api.private
    def _submit_course_review(self, user, score, feedback, consent):
        self.ensure_one()
        if not self.active or not self.public_catalogue:
            raise AccessError(self.env._("This course is unavailable."))
        status = self._course_review_status(user)
        if status in ("pending", "published", "not_published"):
            return
        if status != "eligible":
            raise AccessError(self.env._("Only participants can review this course."))
        feedback = feedback.strip()
        if score not in ("1", "2", "3", "4", "5") or not 0 < len(feedback) <= 2000 or consent != "1":
            raise ValidationError(self.env._("Enter a rating, a comment of up to 2,000 characters and your consent."))
        self.env["rating.rating"]._create_course_review(self, user, int(score), feedback)

    @api.private
    def _public_reviews(self):
        self.ensure_one()
        return self.env["rating.rating"].sudo().search_read(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("consumed", "=", True),
                ("is_public_course_review", "=", True),
            ],
            ["rating", "feedback"],
            order="write_date desc, id desc",
            limit=20,
        )

    @api.private
    def _catalogue_offers(self, company):
        """Adapters return scalar general information, never pedagogical records."""
        return []

    @api.private
    def _catalogue_tags(self):
        return {
            course.id: [{"label": course.category_id.name, "color": 0}] if course.category_id else []
            for course in self
        }

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
        tags_by_course = courses._catalogue_tags()
        return [
            {
                "id": course.id,
                "name": course.name,
                "presentation": course.presentation or "",
                "objectives": course.general_objectives or "",
                "category_id": course.category_id.id,
                "category": course.category_id.name or "",
                "tags": tags_by_course[course.id],
                "offers": [offer for offer in offers if offer["course_id"] == course.id],
            }
            for course in courses
        ]
