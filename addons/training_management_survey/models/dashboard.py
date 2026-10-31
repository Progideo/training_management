"""Mock-exam score projections only, without answers or correction material."""

from odoo import api, models
from odoo.tools.misc import formatLang


class DashboardService(models.AbstractModel):
    _inherit = "training.dashboard.service"

    @api.private
    def _exams(self, enrollment, batch=None):
        self._delivery(enrollment.delivery_id.id)
        if batch is not None and "exams" not in batch:
            batch["exams"] = (
                self.env["survey.user_input"]
                .sudo()
                .search([("training_enrollment_id", "in", batch["enrollments"].ids)], order="id")
                .grouped("training_enrollment_id")
            )
        attempts = (
            batch["exams"].get(enrollment, self.env["survey.user_input"])
            if batch is not None
            else (
                self.env["survey.user_input"]
                .sudo()
                .search([("training_enrollment_id", "=", enrollment.id)], order="id")
            )
        )
        result = []
        for survey in attempts.survey_id:
            version = attempts.filtered(lambda a: a.survey_id == survey)
            completed = version.filtered(lambda attempt: attempt.state == "done")
            ongoing = len(version - completed)
            scores = completed.mapped("scoring_percentage")
            if not scores:
                result.append(
                    {
                        "version": survey.training_version,
                        "count": 0,
                        "ongoing": ongoing,
                        "first": None,
                        "last": None,
                        "best": None,
                        "label": self.env._(
                            "%(name)s · version %(version)s · %(ongoing)s unfinished attempts; no completed score",
                            name=survey.title,
                            version=survey.training_version,
                            ongoing=ongoing,
                        ),
                    }
                )
                continue
            result.append(
                {
                    "version": survey.training_version,
                    "count": len(completed),
                    "ongoing": ongoing,
                    "first": scores[0],
                    "last": scores[-1],
                    "best": max(scores),
                    "label": self.env._(
                        "%(name)s · version %(version)s · %(count)s attempts · first %(first)s / last %(last)s / best %(best)s %% (mock exam)",
                        name=survey.title,
                        version=survey.training_version,
                        count=len(completed),
                        first=formatLang(self.env, scores[0], digits=2),
                        last=formatLang(self.env, scores[-1], digits=2),
                        best=formatLang(self.env, max(scores), digits=2),
                    ),
                }
            )
            if ongoing:
                result[-1]["label"] += self.env._(" · %(ongoing)s unfinished attempts", ongoing=ongoing)
        return result
