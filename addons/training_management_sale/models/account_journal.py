from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # SQL-only concurrency fence, not business history or a public sequence.
    training_bank_reference_revision = fields.Integer(default=0, readonly=True, copy=False)
