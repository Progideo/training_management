"""Retain receipt privacy without changing native accounting or historical evidence."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    last_id = 0
    while payments := env["account.payment"].search([("id", ">", last_id)], order="id", limit=500):
        protected = payments.filtered(lambda payment: payment._training_receipt_is_restricted())
        if protected:
            # Preserve original write_uid/write_date as well as all bank audit fields.
            cr.execute(
                "UPDATE account_payment SET training_receipt_restricted = TRUE WHERE id = ANY(%s)",
                [protected.ids],
            )
            protected.invalidate_recordset(["training_receipt_restricted"])
        last_id = payments[-1].id
