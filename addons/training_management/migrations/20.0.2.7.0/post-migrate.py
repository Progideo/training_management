"""Move existing identity settings to native templates without touching the mail queue."""

from email.utils import formataddr
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env["res.company"].search(
        [
            ("training_notification_address", "!=", False),
            ("training_notification_template_id", "=", False),
        ]
    ):
        template = env["mail.template"].create(
            {
                "name": f"Training notifications — {company.name}",
                "model_id": env["ir.model"]._get_id("res.company"),
                "email_from": formataddr((company.name, company.training_notification_address)),
                "reply_to": company.training_notification_address,
            }
        )
        company.training_notification_template_id = template
