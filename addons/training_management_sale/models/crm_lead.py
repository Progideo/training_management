from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    training_request_kind = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
        ],
        string="Training Request",
    )
    training_program_id = fields.Many2one(
        "training.program.version",
        string="Requested Programme Version",
        ondelete="restrict",
        check_company=True,
        domain="[('state', 'in', ('validated', 'published')), ('company_id', '=', company_id)]",
    )
    training_attendee_count = fields.Integer(string="Expected Participants")
    training_requested_currency_id = fields.Many2one(
        "res.currency",
        string="Requested Currency",
        ondelete="restrict",
        domain="[('name', 'in', ('MAD', 'EUR'))]",
    )
    training_sponsor_id = fields.Many2one(
        "res.partner",
        ondelete="restrict",
        check_company=True,
        help="Person or organisation ordering the training; it can differ from the customer.",
    )
    training_expected_payer_id = fields.Many2one(
        "res.partner",
        string="Expected Payer",
        ondelete="restrict",
        check_company=True,
        help="Planned payer only; this does not change the invoice debtor or grant access.",
    )
    training_admin_contact_id = fields.Many2one(
        "res.partner",
        string="Administrative Contact",
        ondelete="restrict",
        check_company=True,
        help="Contact for commercial administration, without automatic document access.",
    )
    training_delivery_mode = fields.Selection(
        [
            ("onsite", "On site"),
            ("remote", "Remote"),
            ("blended", "Blended"),
            ("elearning", "eLearning"),
        ],
        string="Requested Delivery Mode",
    )
    training_date_from = fields.Date(string="Preferred Start Date")
    training_date_to = fields.Date(string="Preferred End Date")

    @api.constrains("training_attendee_count", "training_date_from", "training_date_to")
    def _check_training_request_values(self):
        for lead in self:
            if lead.training_attendee_count < 0:
                raise ValidationError(self.env._("Expected participants cannot be negative."))
            if lead.training_date_from and lead.training_date_to and lead.training_date_to < lead.training_date_from:
                raise ValidationError(self.env._("The preferred end date must follow the start date."))

    def _prepare_opportunity_quotation_context(self):
        context = super()._prepare_opportunity_quotation_context()
        if not self.training_request_kind:
            return context
        self.ensure_one()
        if not self.training_program_id or self.training_program_id.state not in ("validated", "published"):
            raise ValidationError(
                self.env._("Choose a validated or published programme before creating a training quotation.")
            )
        if self.training_attendee_count <= 0 or not self.training_requested_currency_id:
            raise ValidationError(self.env._("Enter a positive participant count and requested currency."))
        if self.training_requested_currency_id.name not in ("MAD", "EUR"):
            raise ValidationError(self.env._("Training quotations use MAD or EUR."))
        self.training_program_id.check_access("read")
        context.update(
            {
                "default_training_request_kind": self.training_request_kind,
                "default_training_requested_program_id": self.training_program_id.id,
                "default_training_attendee_count": self.training_attendee_count,
                "default_training_requested_currency_id": self.training_requested_currency_id.id,
                "default_training_sponsor_id": self.training_sponsor_id.id,
                "default_training_expected_payer_id": self.training_expected_payer_id.id,
                "default_training_admin_contact_id": self.training_admin_contact_id.id,
            }
        )
        return context
