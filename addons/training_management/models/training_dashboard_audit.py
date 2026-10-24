"""Export manifests and human PDF accessibility checks, without copying source PDFs."""

from odoo import api, fields, models

from odoo.exceptions import AccessError, ValidationError

from .training_evaluation import QUALITY

ODOO_FIELDS = fields


class DashboardExport(models.Model):
    _name = "training.dashboard.export"
    _inherit = "training.learning.evidence"
    _description = "Training Dashboard Export Manifest"

    company_id = fields.Many2one("res.company", required=True)
    actor_id = fields.Many2one("res.users", required=True)
    extracted_at = fields.Datetime(required=True)
    formula_version = fields.Char(default="S10-1", required=True)
    manifest = fields.Json(required=True)


class DashboardLine(models.Model):
    _inherit = "training.dashboard.line"

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        self.check_access("read")
        if any(len(path) > 1 for path in fields):
            raise ValidationError(self.env._("Export only dashboard columns, without traversing source records."))
        result = super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
        if _is_toplevel_call:
            for company in self.company_id:
                rows = self.filtered(lambda row: row.company_id == company)
                self.env["training.dashboard.export"]._create_evidence(
                    {
                        "company_id": company.id,
                        "actor_id": self.env.uid,
                        "extracted_at": ODOO_FIELDS.Datetime.now(),
                        "manifest": {
                            "enrollment_ids": rows.mapped("enrollment_id"),
                            "fields": fields,
                            "population": len(rows),
                            "scope": "current authorized enrollments",
                            "anonymous": "no individual response or non-response status",
                        },
                    }
                )
        return result


class PdfAccessibilityReview(models.Model):
    _name = "training.pdf.accessibility.review"
    _description = "Human PDF Accessibility Review"
    _order = "reviewed_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", string="PDF Review")

    program_id = fields.Many2one(
        "training.program.version", string="Programme PDF", ondelete="restrict", check_company=True
    )
    material_id = fields.Many2one(
        "training.material", string="Private Material PDF", ondelete="restrict", check_company=True
    )
    document_id = fields.Many2one("training.document", string="Issued PDF", ondelete="restrict", check_company=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True, default=lambda self: self.env.company)
    reviewer_id = fields.Many2one("res.users", required=True, readonly=True, default=lambda self: self.env.user)
    reviewed_at = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now)
    logical_reading_order = fields.Boolean(string="Logical Reading Order Checked")
    text_alternatives = fields.Boolean(string="Text Alternatives Checked")
    contrast = fields.Boolean(string="Contrast and Legibility Checked")
    selectable_text = fields.Boolean(string="Selectable Text and Navigation Checked")
    pedagogical_review = fields.Boolean(string="Pedagogical Accessibility Checked")
    source_sha256 = fields.Char(required=True, readonly=True)
    notes = fields.Text(string="Findings and Corrections", required=True)
    passed = fields.Boolean(compute="_compute_passed", string="Human Checks Passed")

    @api.depends("program_id", "material_id", "document_id")
    @api.depends_context("lang")
    def _compute_name(self):
        for row in self:
            source = row.program_id or row.material_id or row.document_id
            row.name = (
                self.env._("PDF review — %(pdf_name)s", pdf_name=source.display_name)
                if source
                else self.env._("New PDF review")
            )

    @api.depends("logical_reading_order", "text_alternatives", "contrast", "selectable_text", "pedagogical_review")
    def _compute_passed(self):
        for row in self:
            row.passed = all(
                row[name]
                for name in (
                    "logical_reading_order",
                    "text_alternatives",
                    "contrast",
                    "selectable_text",
                    "pedagogical_review",
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group(QUALITY):
            raise AccessError(self.env._("Only a quality reviewer may record a human PDF accessibility check."))
        prepared = []
        for vals in vals_list:
            choices = [
                (name, vals.get(name)) for name in ("program_id", "material_id", "document_id") if vals.get(name)
            ]
            if len(choices) != 1:
                raise ValidationError(self.env._("Choose exactly one PDF source."))
            name, source_id = choices[0]
            source = self.env[self._fields[name].comodel_name].browse(source_id).exists()
            if not source:
                raise AccessError(self.env._("This PDF is unavailable."))
            source.check_access("read")
            self.env["training.document.policy"]._check_read(source)
            if name == "program_id" and not source.pdf_attachment_id:
                raise ValidationError(self.env._("Attach the programme PDF before reviewing it."))
            if name == "document_id" and (not source.data or not source.data.content.startswith(b"%PDF-")):
                raise ValidationError(self.env._("Choose a PDF, not a dossier archive."))
            prepared.append(
                dict(
                    vals,
                    company_id=source.company_id.id,
                    reviewer_id=self.env.uid,
                    reviewed_at=fields.Datetime.now(),
                    source_sha256=source["pdf_sha256" if name == "program_id" else "sha256"],
                )
            )
        return super().create(prepared)

    def action_record_review(self):
        """The native object button saves a new form without granting write rights."""
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form"}

    def write(self, vals):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Keep this review; add a new human check after correction."))

    @api.ondelete(at_uninstall=False)
    def _keep_reviews(self):
        raise ValidationError(self.env._("Keep human PDF accessibility reviews."))
