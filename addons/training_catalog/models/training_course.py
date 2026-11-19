from dateutil.relativedelta import relativedelta

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
        translate=True,
        sanitize_overridable=False,
        strip_style=True,
    )

    public_reference = fields.Char()
    live_duration_days = fields.Float(string="Live Duration (days)")
    public_logo = fields.Image(max_width=256, max_height=256)

    _live_duration_nonnegative = models.Constraint(
        "CHECK(live_duration_days >= 0)",
        "Live duration cannot be negative.",
    )

    @api.constrains("name")
    def _check_name(self):
        if any(not (course.name or "").strip() for course in self):
            raise ValidationError(self.env._("A course name is required."))

    public_catalogue = fields.Boolean(string="Publier la présentation générale", copy=False)
    public_published_at = fields.Datetime(
        string="First Catalogue Publication",
        readonly=True,
        copy=False,
        help="Set once, when the general presentation is first published. Drives the « New » badge.",
    )
    public_level = fields.Selection(
        [
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("expert", "Expert"),
        ],
    )
    public_certifying = fields.Boolean(string="Leads to a Certification")
    public_highlights = fields.Text(
        string="Highlights",
        translate=True,
        help="One highlight per line; the website shows the first three.",
    )
    public_faq_ids = fields.One2many("training.course.faq", "course_id", string="Frequently Asked Questions", copy=True)
    public_related_course_ids = fields.Many2many(
        "training.course",
        "training_course_related_rel",
        "course_id",
        "related_id",
        string="Related Courses",
        check_company=True,
        domain="[('id', '!=', id), ('company_id', '=', company_id)]",
    )

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for values in vals_list:
            values.pop("public_published_at", None)
            if values.get("public_catalogue"):
                values["public_published_at"] = now
        return super().create(vals_list)

    def write(self, vals):
        if "public_published_at" in vals and not self.env.su:
            raise ValidationError(self.env._("The first publication date is set automatically."))
        result = super().write(vals)
        if vals.get("public_catalogue"):
            # Only the first publication counts: withdrawing and republishing keeps the date.
            self.filtered(lambda course: not course.public_published_at).sudo().write(
                {"public_published_at": fields.Datetime.now()}
            )
        return result

    @api.constrains("public_related_course_ids")
    def _check_related_courses(self):
        for course in self:
            if course in course.public_related_course_ids:
                raise ValidationError(self.env._("A course cannot be related to itself."))

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
        existing = (
            self.env["rating.rating"]
            .sudo()
            .search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("partner_id", "=", user.partner_id.id),
                    ("consumed", "=", True),
                ],
                limit=1,
            )
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
        return (
            self.env["rating.rating"]
            .sudo()
            .search_read(
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
        )

    @api.private
    def _catalogue_offers(self, company):
        """Adapters return scalar general information, never pedagogical records."""
        return []

    @api.private
    def _catalogue_tags(self):
        return {
            course.id: [{"label": course.category_id.name, "color": 0}] if course.category_id else [] for course in self
        }

    @api.private
    def _catalogue_facts(self, company):
        """Scalar public facts per course; delivery adapters add their own keys.

        Only fields published with the general presentation are projected. Related
        courses are limited to those currently published by the same operator.
        """
        months = company.training_catalogue_new_months
        new_since = fields.Datetime.now() - relativedelta(months=months)
        levels = dict(self._fields["public_level"]._description_selection(self.env))
        published = self.filtered("public_catalogue")
        facts = {}
        for course in self:
            presented = course in published
            related = course.public_related_course_ids.filtered(
                lambda other: other.active and other.public_catalogue and other.company_id == company
            )
            highlights = [line.strip() for line in (course.public_highlights or "").splitlines() if line.strip()]
            facts[course.id] = {
                "level": levels.get(course.public_level, "") if presented else "",
                "level_key": (course.public_level or "") if presented else "",
                "certifying": presented and course.public_certifying,
                "is_new": bool(
                    presented and months and course.public_published_at and course.public_published_at >= new_since
                ),
                "highlights": highlights[:3] if presented else [],
                "faq": [
                    {"question": row.question, "answer": row.answer}
                    for row in course.public_faq_ids.sorted(lambda row: (row.sequence, row.id))
                ]
                if presented
                else [],
                "related": [{"id": other.id, "name": other.name} for other in related] if presented else [],
                "duration_days": course.live_duration_days if presented else 0.0,
                "published_at": course.public_published_at if presented else False,
            }
        return facts

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
        facts_by_course = courses._catalogue_facts(company)
        return [
            {
                **facts_by_course[course.id],
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


class TrainingCourseFaq(models.Model):
    _name = "training.course.faq"
    _description = "Course Frequently Asked Question"
    _order = "sequence, id"
    _check_company_auto = True

    course_id = fields.Many2one("training.course", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="course_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    question = fields.Char(required=True, translate=True)
    answer = fields.Text(required=True, translate=True)
