from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # Legacy concurrency counter, kept for upgrade compatibility; no longer used.
    training_bank_reference_revision = fields.Integer(default=0, readonly=True, copy=False)
