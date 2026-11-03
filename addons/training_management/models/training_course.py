from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingCourse(models.Model):
    _inherit = "training.course"

    program_version_ids = fields.One2many(
        "training.program.version",
        "course_id",
        string="Programme Versions",
        groups="training_management.group_training_reader",
        copy=False,
    )

    def action_open_programs(self):
        self.ensure_one()
        self.check_access("read")
        self.env["training.program.version"].check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Programme Versions"),
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
                    raise ValidationError(self.env._("A course with programme versions cannot change company."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_with_programmes(self):
        self.lock_for_update()
        self.invalidate_recordset(["program_version_ids"])
        if any(course.program_version_ids for course in self):
            raise ValidationError(self.env._("Archive courses with programme versions instead of deleting them."))
