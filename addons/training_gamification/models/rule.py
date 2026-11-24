"""Points rules configured by the organisation (gamification, 24 November 2026).

The module ships no active rule, scale or badge: an administrator creates and
activates the rules, as for retention. Points reward engagement only; they never
open an access, a session, a price or a document.
"""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class GamificationRule(models.Model):
    _name = "training.gamification.rule"
    _description = "Training Points Rule"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=False, help="Rules are delivered inactive; points are granted once active.")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    event_type = fields.Selection(selection="_selection_event_type", required=True)
    points = fields.Integer(required=True, default=5)
    max_per_enrollment = fields.Integer(
        string="Maximum per Enrollment",
        default=0,
        help="Number of times one enrollment can earn this rule; 0 = no limit.",
    )
    course_ids = fields.Many2many(
        "training.course", string="Trainings", check_company=True, help="Leave empty to apply to every training."
    )
    date_from = fields.Date(
        string="Counts Events From",
        required=True,
        default=fields.Date.context_today,
        help="Earlier events never earn points: activating a rule grants nothing retroactively.",
    )
    point_ids = fields.One2many("training.gamification.point", "rule_id", readonly=True)
    granted_count = fields.Integer(compute="_compute_granted_count", string="Points Granted")

    _positive_points = models.Constraint("CHECK(points > 0)", "A rule grants a positive number of points.")
    _positive_limit = models.Constraint("CHECK(max_per_enrollment >= 0)", "The limit cannot be negative.")

    @api.model
    def _selection_event_type(self):
        return self.env["training.gamification.service"]._event_selection()

    @api.depends("point_ids.points")
    def _compute_granted_count(self):
        for rule in self:
            rule.granted_count = sum(rule.sudo().point_ids.mapped("points"))

    @api.constrains("event_type", "points")
    def _check_event_type(self):
        types = dict(self._selection_event_type())
        for rule in self:
            if rule.event_type not in types:
                raise ValidationError(self.env._("This event is not available with the installed modules."))

    def write(self, vals):
        if self.sudo().point_ids and {"event_type", "company_id", "course_ids"} & set(vals):
            raise ValidationError(
                self.env._("Archive this rule and create another one: points were already granted for this event.")
            )
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_keep_granted(self):
        if self.sudo().point_ids:
            raise ValidationError(self.env._("Archive a rule that already granted points instead of deleting it."))

    def action_apply_now(self):
        if not self.env.user._is_system():
            raise AccessError(self.env._("Only an administrator can apply points rules."))
        self.env["training.gamification.service"]._reconcile(self.filtered("active"))
        return True

    @api.model
    def _cron_reconcile(self):
        self.env["training.gamification.service"]._reconcile()
