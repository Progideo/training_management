from datetime import timedelta

from odoo import api, fields, models

from ..models.training_evaluation import COORDINATOR


class ProviderSessionEdit(models.TransientModel):
    _inherit = "training.session.edit"  # pylint: disable=consider-merging-classes-inherited  # Keep QUA03 warnings separate from scheduling and attendance inputs.

    instructor_warning = fields.Char(
        string="Instructor Evidence", compute="_compute_provider_warning", groups=COORDINATOR
    )

    @api.depends("instructor_id", "company_id", "start_date", "end_date", "repeat_count", "interval_days")
    def _compute_provider_warning(self):
        for row in self:
            last_date = (row.end_date or row.start_date or fields.Date.today()) + timedelta(
                days=max(0, row.repeat_count - 1) * max(1, row.interval_days)
            )
            service = self.env["training.provider.service"]
            row.instructor_warning = service._assignment_warning(
                row.instructor_id, row.company_id, row.start_date or fields.Date.today(), last_date
            )

    @api.onchange("instructor_id", "start_date", "end_date", "repeat_count", "interval_days")
    def _onchange_provider_warning(self):
        if self.instructor_warning:
            return {"warning": {"title": self.env._("Instructor Evidence"), "message": self.instructor_warning}}
        return None
