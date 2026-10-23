"""Keep native certification reports for ordinary Surveys only."""

from odoo import api, models
from odoo.exceptions import AccessError


class SurveyCertificationReport(models.AbstractModel):
    _name = "report.survey.certification_report_view"
    _description = "Native Survey Certification Report Boundary"

    @api.model
    def _get_report_values(self, docids, data=None):
        answers = self.env["survey.user_input"].browse(docids)
        answers.check_access("read")
        if answers.filtered("training_enrollment_id"):
            raise AccessError(self.env._("Mock exams do not issue certificates."))
        return {"doc_ids": docids, "doc_model": answers._name, "docs": answers}
