from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Give an existing delivery its company reference, in creation order."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    deliveries = env["training.delivery"].search([("reference", "=", False)], order="id")
    for delivery in deliveries:
        # Plain SQL: the business write refuses reference changes, and no journal line is wanted.
        cr.execute(
            "UPDATE training_delivery SET reference = %s WHERE id = %s",
            [env["training.delivery"]._next_reference(delivery.company_id), delivery.id],
        )
    deliveries.invalidate_recordset(["reference"])
