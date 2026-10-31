from odoo import api, models


class TrainingPortalNavigation(models.AbstractModel):
    _inherit = "training.portal.navigation"

    @api.private
    def _links(self):
        links = super()._links()
        user = self.env.user
        if not user.active or user._is_public():
            return links
        enrollments = self.env["training.exam.service"]._history_enrollments()
        recipients = (
            self.env["training.feedback.recipient"]
            .sudo()
            .search(
                [
                    ("user_id", "=", user.id),
                    ("company_id", "in", user.company_ids.ids),
                    ("campaign_id.state", "!=", "draft"),
                ]
            )
        )
        links.update(
            exams=bool(
                self.env["survey.user_input"]
                .sudo()
                .search_count(
                    [
                        ("training_enrollment_id", "in", enrollments.ids),
                    ],
                    limit=1,
                )
            ),
            feedback=any(recipient._eligible() for recipient in recipients),
        )
        return links
