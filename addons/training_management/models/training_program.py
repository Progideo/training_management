import re

from lxml.html.defs import tags as HTML_TAGS

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_sanitize, is_html_empty, plaintext2html


class TrainingProgramVersion(models.Model):
    _name = "training.program.version"
    _description = "Training Programme Version"
    _rec_name = "title"
    _order = "course_id, id desc"
    _check_company_auto = True

    course_id = fields.Many2one(
        "training.course",
        string="Standard Course",
        required=True,
        ondelete="restrict",
        check_company=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="course_id.company_id",
        store=True,
        index=True,
    )
    version = fields.Char(string="Version Reference", required=True)
    title = fields.Char(string="Programme Title", required=True, translate=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("published", "Published"),
            ("retired", "Retired"),
        ],
        default="draft",
        required=True,
        copy=False,
        readonly=True,
        index=True,
    )
    objectives = fields.Text(translate=True)
    target_audience = fields.Text(translate=True)
    prerequisites = fields.Text(translate=True)
    content = fields.Text(translate=True)
    content_formatted = fields.Html(
        string="Programme Content",
        compute="_compute_content_formatted",
        inverse="_inverse_content_formatted",
        sanitize=True,
        sanitize_overridable=False,
        help="Headings and nested lists are preserved in the programme and its PDF.",
    )

    duration_hours = fields.Float(string="Duration (hours)")
    delivery_mode = fields.Selection(
        [
            ("onsite", "On site"),
            ("remote", "Remote"),
            ("blended", "Blended"),
            ("elearning", "eLearning"),
        ]
    )
    language_id = fields.Many2one(
        "res.lang",
        string="Programme Language",
        default=lambda self: self.env["res.lang"].search(
            [("code", "=", self.env.lang or "en_US")],
            limit=1,
        ),
        ondelete="restrict",
    )
    teaching_methods = fields.Text(translate=True)
    evaluation_criteria = fields.Text(translate=True)
    access_conditions = fields.Text(translate=True)
    accessibility_contact_id = fields.Many2one(
        "res.partner",
        ondelete="restrict",
        check_company=True,
    )
    accessibility_information = fields.Text(
        translate=True,
        help="Contact instructions preserved in this programme version.",
    )
    pricing_mode = fields.Selection(
        [("quotation", "On quotation")],
        default="quotation",
        required=True,
        help="Commercial prices will be managed by standard Odoo products and quotations.",
    )
    validated_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    validated_at = fields.Datetime(readonly=True, copy=False)
    published_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    published_at = fields.Datetime(readonly=True, copy=False)
    retired_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    retired_at = fields.Datetime(readonly=True, copy=False)

    _unique_version = models.Constraint(
        "UNIQUE(course_id, version)",
        "The version reference must be unique for each course.",
    )
    _positive_duration = models.Constraint(
        "CHECK(duration_hours >= 0)",
        "Duration cannot be negative.",
    )

    @api.depends("content")
    @api.depends_context("lang")
    def _compute_content_formatted(self):
        # One source of truth: keep the existing translated storage/API, expose
        # a native sanitized HTML editor. Legacy plain text keeps its line breaks.
        for program in self:
            value = program.content or ""
            program.content_formatted = (
                html_sanitize(value)
                if any(tag.lower() in HTML_TAGS for tag in re.findall(r"</?([a-z][a-z0-9]*)\b[^>]*>", value, re.I))
                else plaintext2html(value)
            )

    def _inverse_content_formatted(self):
        for program in self:
            program.write({"content": html_sanitize(program.content_formatted or "")})

    @api.depends("course_id.name", "version")
    @api.depends_context("lang")
    def _compute_display_name(self):
        for program in self:
            program.display_name = " — ".join(
                filter(
                    None,
                    (
                        program.course_id.name,
                        program.version,
                    ),
                )
            )

    def _audit_fields(self):
        return {
            "validated_by_id",
            "validated_at",
            "published_by_id",
            "published_at",
            "retired_by_id",
            "retired_at",
        }

    def _lock_courses(self, extra_course_id=None):
        courses = self.mapped("course_id")
        if extra_course_id:
            courses |= self.env["training.course"].browse(extra_course_id)
        courses.check_access("read")
        courses.lock_for_update()

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access("create")
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if "category_id" in vals:
                raise ValidationError(self.env._("The programme category is defined by its course."))
            if vals.get("state", "draft") != "draft" or self._audit_fields().intersection(vals):
                raise ValidationError(self.env._("New programme versions must be drafts without validation metadata."))
            if "company_id" in vals:
                raise ValidationError(self.env._("The programme company is defined by its course."))
            vals["state"] = "draft"
            vals.update(dict.fromkeys(self._audit_fields(), False))
            vals["version"] = (vals.get("version") or "").strip()
            course_id = vals.get("course_id") or self.env.context.get("default_course_id")
            course = self.env["training.course"].browse(course_id)
            course.check_access("read")
            course.lock_for_update()
            prepared.append(vals)
        return super().create(prepared)

    @api.constrains("title", "version")
    def _check_identification(self):
        for program in self:
            if not (program.title or "").strip() or not (program.version or "").strip():
                raise ValidationError(self.env._("A programme title and version reference are required."))

    def _check_complete(self):
        required_fields = (
            "objectives",
            "target_audience",
            "prerequisites",
            "content",
            "delivery_mode",
            "language_id",
            "teaching_methods",
            "evaluation_criteria",
            "access_conditions",
            "accessibility_contact_id",
            "accessibility_information",
        )
        for program in self:
            missing = [
                name
                for name in required_fields
                if not program[name] or (isinstance(program[name], str) and not program[name].strip())
            ]
            if missing or is_html_empty(program.content_formatted) or program.duration_hours <= 0:
                raise ValidationError(
                    self.env._("Complete all programme information and enter a positive duration before validation.")
                )

    def write(self, vals):
        self.check_access("write")
        if "category_id" in vals:
            raise ValidationError(self.env._("The programme category is defined by its course."))
        self._lock_courses(vals.get("course_id"))
        self.lock_for_update()
        self.invalidate_recordset()
        if self._audit_fields().intersection(vals) or "company_id" in vals:
            raise ValidationError(self.env._("Validation metadata and programme company cannot be edited."))
        values = dict(vals)
        if "version" in values:
            values["version"] = (values["version"] or "").strip()
        if any(record.state != "draft" for record in self) and set(values) - {"state"}:
            raise ValidationError(self.env._("Validated programme content is immutable. Create a new draft version."))
        target = values.get("state")
        if "state" in values and not target:
            raise ValidationError(self.env._("This programme status transition is not allowed."))
        if target:
            transitions = {"draft": "validated", "validated": "published", "published": "retired"}
            if set(values) != {"state"}:
                raise ValidationError(self.env._("Save programme content before changing its status."))
            if any(record.state != target and transitions.get(record.state) != target for record in self):
                raise ValidationError(self.env._("This programme status transition is not allowed."))
            changing = self.filtered(lambda record: record.state != target)
            if not changing:
                return True
            if target in ("validated", "published"):
                changing._check_complete()
            values.update(
                {
                    f"{target}_by_id": self.env.uid,
                    f"{target}_at": fields.Datetime.now(),
                }
            )
            # A failed PDF must roll back every member of a validation batch,
            # including the state/audit written before rendering.
            with self.env.cr.savepoint():
                result = super(TrainingProgramVersion, changing).write(values)
                if target == "validated":
                    changing._freeze_program_pdf()
                return result
        return super().write(values)

    def action_validate(self):
        return self.write({"state": "validated"})

    @api.private
    def _store_pdf_metadata(self, values):
        self._require_pdf_coordinator()
        return super().write(values)  # pylint: disable=super-method-mismatch  # private metadata write after controlled generation

    def action_publish(self):
        return self.write({"state": "published"})

    def action_retire(self):
        return self.write({"state": "retired"})

    def action_new_version(self):
        self.ensure_one()
        self.check_access("read")
        self.check_access("create")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("New Programme Version"),
            "res_model": "training.program.new.version",
            "view_mode": "form",
            "target": "new",
            "context": {
                **self.env.context,
                "default_source_id": self.id,
                "default_version": False,
            },
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_except_validated(self):
        self._lock_courses()
        self.lock_for_update()
        self.invalidate_recordset(["state"])
        if any(program.state != "draft" for program in self):
            raise ValidationError(self.env._("Validated programme versions cannot be deleted."))
