from odoo import fields, models


class ChallengeLaunch(models.TransientModel):
    _name = "training.gamification.challenge.launch"
    _description = "Launch a Session Challenge"

    delivery_id = fields.Many2one("training.delivery", required=True, readonly=True)
    template_id = fields.Many2one(
        "gamification.challenge",
        string="Challenge",
        required=True,
        domain=[("training_template", "=", True), ("state", "=", "draft")],
    )

    def action_launch(self):
        self.ensure_one()
        challenge = self.delivery_id._launch_training_challenge(self.template_id)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._("Challenge “%(name)s” launched.", name=challenge.name),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
