"""Public projection of a published programme; no participant or evaluation data."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingPublicProgramme(models.Model):
    _inherit = "training.program.version"  # pylint: disable=consider-merging-classes-inherited  # public projection is separate from private PDF generation

    public_catalogue = fields.Boolean(string="Approved for Public Catalogue", copy=False)
    expected_outcomes = fields.Text(translate=True)
    practice_deliverables = fields.Text(translate=True)
    instructor_profiles = fields.Text(translate=True)
    material_access_duration = fields.Char(translate=True)
    included_services = fields.Text(translate=True)
    preparation_details = fields.Text(translate=True)
    mock_exam_details = fields.Text(translate=True)
    official_exam_details = fields.Text(translate=True)
    unconfirmed_information = fields.Text(translate=True)
    preview_pdf = fields.Binary(attachment=False, copy=False, string="Public PDF Extract")
    preview_filename = fields.Char(string="Public Extract Filename")
    preview_question_ids = fields.One2many("training.preview.question", "program_id", copy=True)

    @api.constrains("preview_pdf", "preview_filename")
    def _check_public_extract(self):
        for program in self:
            if program.preview_pdf and (
                not program.preview_pdf.content.startswith(b"%PDF-")
                or len(program.preview_pdf.content) > 10 * 1024 * 1024
                or not (program.preview_filename or "").lower().endswith(".pdf")
            ):
                raise ValidationError(self.env._("The public extract must be a PDF of at most 10 MB."))

    @api.private
    def _catalogue_sections(self):
        self.ensure_one()
        labels = [
            ("objectives", self.env._("Objectives")),
            ("target_audience", self.env._("Target audience")),
            ("prerequisites", self.env._("Prerequisites")),
            ("content", self.env._("Programme content")),
            ("teaching_methods", self.env._("Teaching methods")),
            ("evaluation_criteria", self.env._("Evaluation")),
            ("access_conditions", self.env._("Access conditions")),
            ("accessibility_information", self.env._("Accessibility")),
            ("expected_outcomes", self.env._("Expected outcomes")),
            ("practice_deliverables", self.env._("Exercises and deliverables")),
            ("instructor_profiles", self.env._("Instructor profiles")),
            ("material_access_duration", self.env._("Material access duration")),
            ("included_services", self.env._("Included training services")),
            ("preparation_details", self.env._("Exam preparation")),
            ("mock_exam_details", self.env._("Mock exam (not an official certification)")),
            ("official_exam_details", self.env._("Official exam and inclusion")),
        ]
        pending = [label for name, label in labels[8:] if not self[name]]
        sections = [(label, self[name] or self.env._("Not confirmed")) for name, label in labels]
        if pending or self.unconfirmed_information:
            sections.append(
                (
                    self.env._("Information awaiting confirmation"),
                    "\n".join(pending + [self.unconfirmed_information or ""]),
                )
            )
        return sections


class TrainingPreviewQuestion(models.Model):
    _name = "training.preview.question"
    _description = "Public Demonstration Question"
    _order = "sequence, id"
    _check_company_auto = True

    program_id = fields.Many2one("training.program.version", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="program_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    choice_a = fields.Char(required=True, translate=True)
    choice_b = fields.Char(required=True, translate=True)
    correct_choice = fields.Selection([("a", "A"), ("b", "B")], required=True, default="a")
    explanation = fields.Text(required=True, translate=True)

    @api.private
    def _check_editable_programs(self, programs):
        programs.check_access("write")
        programs._lock_courses()
        programs.lock_for_update()
        programs.invalidate_recordset()
        if any(p.state != "draft" for p in programs):
            raise ValidationError(self.env._("Public demonstration questions are frozen with their programme."))

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access("create")
        values = [self._add_missing_default_values(dict(vals)) for vals in vals_list]
        self._check_editable_programs(self.env["training.program.version"].browse([v["program_id"] for v in values]))
        return super().create(values)

    def write(self, vals):
        self.check_access("write")
        programs = self.program_id
        if vals.get("program_id"):
            programs |= self.env["training.program.version"].browse(vals["program_id"])
        self._check_editable_programs(programs)
        return super().write(vals)

    def unlink(self):
        self.check_access("unlink")
        self._check_editable_programs(self.program_id)
        return super().unlink()
