"""Points journal: one line per grant or withdrawal, credited as native karma.

Lines are written by the service only. A withdrawal never rewrites a grant: it
adds a negative line (revision of a result, invalidated attendance). Deleting a
finished dossier deletes its lines through the standard dossier deletion, and
their karma with them.
"""

from odoo import api, fields, models
from odoo.exceptions import AccessError


class GamificationPoint(models.Model):
    _name = "training.gamification.point"
    _description = "Training Points"
    _order = "date desc, id desc"
    _check_company_auto = True
    _rec_name = "rule_id"

    rule_id = fields.Many2one("training.gamification.rule", required=True, ondelete="restrict", index=True)
    event_type = fields.Selection(related="rule_id.event_type", store=True)
    enrollment_id = fields.Many2one(
        "training.enrollment", required=True, ondelete="cascade", index=True, check_company=True
    )
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    kind = fields.Selection([("grant", "Grant"), ("withdrawal", "Withdrawal")], required=True)
    points = fields.Integer(required=True)
    date = fields.Datetime(required=True, help="Date of the training event that earned or withdrew the points.")
    source_key = fields.Char(required=True, help="Training record behind the event.")
    grant_id = fields.Many2one("training.gamification.point", ondelete="cascade", index="btree_not_null")
    withdrawn = fields.Boolean(readonly=True)

    _one_active_grant = models.UniqueIndex(
        "(rule_id, enrollment_id, source_key) WHERE kind = 'grant' AND NOT withdrawn",
        "These points were already granted for this event.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(self.env._("Points are granted by the configured rules."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(self.env._("Points are granted by the configured rules."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_by_administrator(self):
        if not self.env.su and not self.env.user._is_system():
            raise AccessError(self.env._("Only an administrator can delete points."))

    def unlink(self):
        """Remove the karma of deleted lines, then the native karma history that names them."""
        rows = self.sudo()
        # A grant takes its withdrawals with it: count them before the cascade.
        rows |= rows.search([("grant_id", "in", rows.ids)])
        net = {}
        for row in rows:
            net[row.user_id] = net.get(row.user_id, 0) + row.points
        compensation = {
            user: {"gain": -gain, "reason": self.env._("Training points deleted with their dossier")}
            for user, gain in net.items()
            if gain and user.exists()
        }
        # The compensation becomes the latest karma line, so removing older lines
        # below keeps the stored karma right.
        self.env["res.users"]._add_karma_batch(compensation)
        self.env["gamification.karma.tracking"].sudo().search(
            [("origin_ref", "in", [f"{self._name},{row_id}" for row_id in rows.ids])]
        ).unlink()
        return super(GamificationPoint, rows).unlink()
