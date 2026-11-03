from odoo import fields, models


class Configure(models.TransientModel):
    _name = "training.elearning.question.configure"
    _description = "Configure Enriched Exam Question"
    question_id = fields.Many2one("survey.question", required=True)
    kind = fields.Selection([("matching", "Appariement"), ("ordering", "Mise en ordre")], required=True)
    items = fields.Text(
        required=True,
        string="Éléments",
        help="Appariement : gauche | droite, une paire par ligne. Mise en ordre : un élément par ligne, dans l’ordre correct.",
    )

    def action_configure(self):
        self.ensure_one()
        self.check_access("read")
        self.question_id._configure_interaction(self.kind, self.items)
        return {"type": "ir.actions.act_window_close"}
