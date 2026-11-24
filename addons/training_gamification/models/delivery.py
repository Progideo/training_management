from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingDelivery(models.Model):
    _inherit = "training.delivery"

    training_challenge_ids = fields.One2many(
        "gamification.challenge", "training_delivery_id", string="Session Challenges", readonly=True
    )
    training_challenge_count = fields.Integer(
        string="Session Challenge Count", compute="_compute_training_challenge_count"
    )

    @api.depends("training_challenge_ids")
    def _compute_training_challenge_count(self):
        for delivery in self:
            delivery.training_challenge_count = len(delivery.sudo().training_challenge_ids)

    def action_open_training_engagement(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Engagement"),
            "res_model": "training.gamification.point",
            "view_mode": "list",
            "domain": [("delivery_id", "=", self.id)],
            "context": {"search_default_group_user": 1, "create": False},
        }

    def action_launch_training_challenge(self):
        self.ensure_one()
        self.check_access("write")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Launch a Session Challenge"),
            "res_model": "training.gamification.challenge.launch",
            "view_mode": "form",
            "target": "new",
            "context": {"default_delivery_id": self.id},
        }

    def _launch_training_challenge(self, template):
        """Copy a template for this delivery; only participants with an account take part."""
        self.ensure_one()
        self.check_access("write")
        template = template.sudo()
        if not template.training_template or template.state != "draft":
            raise ValidationError(self.env._("Choose a session challenge template."))
        if not self.start_at or not self.end_at:
            raise ValidationError(self.env._("A session challenge needs the delivery dates."))
        service = self.env["training.gamification.service"]
        enrollments = self.sudo().enrollment_ids.filtered(lambda e: e.state in ("confirmed", "closed"))
        users = self.env["res.users"].union(*(service._participant_user(e) for e in enrollments))
        if not users:
            raise ValidationError(self.env._("No participant of this delivery has an account."))
        challenge = template.copy(
            {
                "name": f"{template.name} — {self.name}",
                "training_delivery_id": self.id,
                "user_domain": False,
                "user_ids": [(6, 0, users.ids)],
                "period": "once",
                "visibility_mode": "personal",
                "reward_first_id": False,
                "reward_second_id": False,
                "reward_third_id": False,
                "start_date": self.start_at.date(),
                "end_date": self.end_at.date(),
            }
        )
        challenge.action_start()
        return challenge
