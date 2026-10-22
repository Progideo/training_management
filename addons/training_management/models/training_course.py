from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TrainingCourse(models.Model):
    _name = "training.course"
    _description = "Standard Training Course"
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="restrict",
        index=True,
    )
    program_version_ids = fields.One2many(
        "training.program.version",
        "course_id",
        string="Programme Versions",
        copy=False,
    )

    @api.constrains("name")
    def _check_name(self):
        if any(not (course.name or "").strip() for course in self):
            raise ValidationError(_("A course name is required."))

    def action_open_programs(self):
        self.ensure_one()
        self.check_access("read")
        self.env["training.program.version"].check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": _("Programme Versions"),
            "res_model": "training.program.version",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("course_id", "=", self.id)],
            "context": {
                **self.env.context,
                "default_course_id": self.id,
                "default_title": self.name,
            },
        }

    def write(self, vals):
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()
        if "company_id" in vals:
            for course in self:
                if vals["company_id"] != course.company_id.id and course.program_version_ids:
                    raise ValidationError(_("A course with programme versions cannot change company."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_with_programmes(self):
        self.lock_for_update()
        self.invalidate_recordset(["program_version_ids"])
        if any(course.program_version_ids for course in self):
            raise ValidationError(_("Archive courses with programme versions instead of deleting them."))
