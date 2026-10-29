from odoo import api, fields, models


class SessionPublicationInspection(models.TransientModel):
    _name = "training.session.publication.inspection"
    _description = "Session State and Availability"
    _check_company_auto = True

    delivery_id = fields.Many2one("training.delivery", required=True, check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id")
    internal_state = fields.Char(compute="_compute_facts")
    program_state = fields.Char(compute="_compute_facts")
    catalogue_approved = fields.Boolean(compute="_compute_facts")
    course_active = fields.Boolean(compute="_compute_facts")
    dated_session = fields.Boolean(compute="_compute_facts")
    start_at = fields.Datetime(compute="_compute_facts")
    end_at = fields.Datetime(compute="_compute_facts")
    timezone = fields.Char(compute="_compute_facts")
    capacity = fields.Integer(compute="_compute_facts")
    occupied_seats = fields.Integer(compute="_compute_facts")
    remaining_seats = fields.Integer(compute="_compute_facts")
    unlimited = fields.Boolean(compute="_compute_facts")
    checked_at = fields.Datetime(compute="_compute_facts")

    @api.depends("delivery_id")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_facts(self):
        for wizard in self:
            if not wizard.delivery_id:
                for key in (
                    "internal_state",
                    "program_state",
                    "catalogue_approved",
                    "course_active",
                    "dated_session",
                    "start_at",
                    "end_at",
                    "timezone",
                    "capacity",
                    "occupied_seats",
                    "remaining_seats",
                    "unlimited",
                    "checked_at",
                ):
                    wizard[key] = False
                continue
            facts = self.env["training.session.publication.service"]._session_facts(wizard.delivery_id)
            wizard.internal_state = dict(wizard.delivery_id._fields["state"]._description_selection(self.env))[
                facts["state"]
            ]
            wizard.program_state = dict(
                wizard.delivery_id.program_id._fields["state"]._description_selection(self.env)
            )[facts["program_state"]]
            wizard.dated_session = facts["kind"] == "session"
            wizard.unlimited = not facts["capacity"]
            wizard.remaining_seats = facts["remaining_seats"] or 0
            for key in (
                "catalogue_approved",
                "course_active",
                "start_at",
                "end_at",
                "timezone",
                "capacity",
                "occupied_seats",
                "checked_at",
            ):
                wizard[key] = facts[key]
