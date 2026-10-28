"""Native attachment/limited-field tokens cannot authorize a training exam."""

from odoo import models
from odoo.exceptions import AccessError


def _training_exam(record):
    """Classify a native record; classification alone never authorizes access."""
    target = record.sudo()
    if target._name == "ir.attachment" and target.res_model in (
        "survey.survey",
        "survey.question",
        "survey.question.answer",
        "survey.user_input",
        "survey.user_input.line",
    ):
        target = target.env[target.res_model].browse(target.res_id).exists()
    survey = record.env["survey.survey"]
    if target._name == "survey.survey":
        survey = target
    elif target._name in ("survey.question", "survey.user_input", "survey.user_input.line"):
        survey = target.survey_id
    elif target._name == "survey.question.answer":
        survey = (target.question_id or target.matrix_question_id).survey_id
    return survey.filtered(lambda s: s.training_program_id or s.orientation_company_id).with_env(record.env)


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"

    def _check_training_binary_access(self, record):
        result = super()._check_training_binary_access(record)
        # Classification may inspect a public/legacy attachment, but cannot
        # authorize files attached to protected feedback answers.
        target = record.sudo()
        if target._name == "ir.attachment" and target.res_model in ("survey.user_input", "survey.user_input.line"):
            target = self.env[target.res_model].sudo().browse(target.res_id).exists()
        if target._name == "survey.user_input.line":
            target = target.user_input_id
        if target._name == "survey.user_input" and target.training_feedback_campaign_id:
            raise AccessError(self.env._("Feedback response files are private."))
        survey = _training_exam(record)
        if survey:
            # Recheck under the original identity even if native token resolution
            # returned a privileged record. Portal images use an explicit route.
            if not self.env.user.has_group("training_management.group_training_coordinator") or (
                (survey.training_company_id or survey.orientation_company_id) not in self.env.user.company_ids
            ):
                raise AccessError(self.env._("This private exam file is unavailable."))

        return result
