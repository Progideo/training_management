from odoo import models


class KarmaTracking(models.Model):
    _inherit = "gamification.karma.tracking"

    def _get_origin_selection_values(self):
        return super()._get_origin_selection_values() + [("training.gamification.point", self.env._("Training Points"))]
