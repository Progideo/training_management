from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    course_review_responsible_id = fields.Many2one(
        "res.users",
        domain="[('active', '=', True), ('share', '=', False), ('company_ids', 'in', id)]",
        groups="base.group_system",
    )

    @api.private
    def _is_course_review_responsible(self, user):
        self.ensure_one()
        return (
            user.active
            and not user.share
            and self in user.company_ids
            and user.has_group("website.group_website_designer")
        )

    @api.constrains("course_review_responsible_id")
    def _check_course_review_responsible(self):
        for company in self:
            user = company.course_review_responsible_id
            if user and not company._is_course_review_responsible(user):
                raise ValidationError(self.env._("Choose an active website designer for this company."))
