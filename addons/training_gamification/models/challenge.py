"""Session challenges: a native challenge copied from a template for one delivery.

An administrator prepares challenge templates (draft, flagged as templates); a
coordinator launches one on a delivery. The copy targets the delivery's
participants with an account, over the delivery dates, in personal visibility:
no ranking, no reward for the first places.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GamificationChallenge(models.Model):
    _inherit = "gamification.challenge"

    training_template = fields.Boolean(
        string="Session Challenge Template",
        copy=False,
        help="Coordinators can launch a copy of this draft challenge on a training delivery.",
    )
    training_delivery_id = fields.Many2one("training.delivery", copy=False, index="btree_not_null", ondelete="set null")

    @api.constrains("training_template", "state", "visibility_mode")
    def _check_training_template(self):
        for challenge in self.filtered("training_template"):
            if challenge.state != "draft":
                raise ValidationError(self.env._("A session challenge template stays in draft."))
            if challenge.visibility_mode != "personal":
                raise ValidationError(self.env._("Session challenges never show a ranking."))
