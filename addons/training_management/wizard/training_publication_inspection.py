from odoo import api, fields, models


class PublicationInspection(models.TransientModel):
    _name = "training.publication.inspection"
    _description = "Participation Evidence for a Review"
    _check_company_auto = True

    enrollment_id = fields.Many2one("training.enrollment", required=True, check_company=True)
    company_id = fields.Many2one(related="enrollment_id.company_id")
    participant_id = fields.Many2one(related="enrollment_id.participant_id")
    enrollment_state = fields.Char(compute="_compute_facts")
    validated_minutes = fields.Float(compute="_compute_facts")
    attendance_count = fields.Integer(compute="_compute_facts")
    certificate_count = fields.Integer(string="Participation Certificates", compute="_compute_facts")
    checked_at = fields.Datetime(compute="_compute_facts")

    @api.depends("enrollment_id")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_facts(self):
        for wizard in self:
            wizard.enrollment_state = False
            wizard.validated_minutes = 0
            wizard.attendance_count = 0
            wizard.certificate_count = 0
            wizard.checked_at = fields.Datetime.now()
            if wizard.enrollment_id:
                facts = self.env["training.publication.service"]._participation_facts(wizard.enrollment_id)
                wizard.enrollment_state = dict(
                    wizard.enrollment_id._fields["state"]._description_selection(self.env)
                ).get(facts["enrollment_state"])
                wizard.validated_minutes = facts["minutes"]
                wizard.attendance_count = len(facts["attendance"])
                wizard.certificate_count = len(facts["certificates"])
