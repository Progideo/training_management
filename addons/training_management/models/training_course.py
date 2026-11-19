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

    @api.private
    def _catalogue_offers(self, company):
        offers = super()._catalogue_offers(company)
        # Only public, published programmes for this website operator. No
        # detailed programme, PDF, preview or question enters the projection.
        programs = (
            self.env["training.program.version"]
            .sudo()
            .search(
                [
                    ("company_id", "=", company.id),
                    ("state", "=", "published"),
                    ("public_catalogue", "=", True),
                    ("course_id.active", "=", True),
                ],
                order="published_at desc, id desc",
            )
        )
        # Every available delivery mode stays visible, each with its latest published version.
        latest = {}
        for program in programs:
            latest.setdefault((program.course_id.id, program.delivery_mode), program)
        return offers + [program._catalogue_offer() for program in latest.values()]

    @api.private
    def _has_course_review_participation(self, user):
        self.ensure_one()
        enrollments = (
            self.env["training.document.policy"]
            .with_user(user)
            ._enrollments()
            .filtered_domain(
                [
                    ("company_id", "=", self.company_id.id),
                    ("program_id.course_id", "=", self.id),
                    ("state", "in", ("confirmed", "closed")),
                    ("delivery_id.kind", "=", "session"),
                    ("delivery_id.state", "in", ("delivered", "closed")),
                    ("delivery_id.end_at", "<=", fields.Datetime.now()),
                ]
            )
        )
        attendance = (
            self.env["training.attendance"]
            .sudo()
            .search(
                [
                    ("enrollment_id", "in", enrollments.ids),
                    ("session_id.cancelled", "=", False),
                ]
            )
        )
        return any(row.state == "validated" and row.minutes > 0 for row in attendance) or (
            super()._has_course_review_participation(user)
        )
