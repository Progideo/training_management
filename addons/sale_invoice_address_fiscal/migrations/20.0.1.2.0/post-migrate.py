"""Translate the old export choice into native criteria; never recompute documents."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env["res.company"].search([("sale_fiscal_by_invoice_address", "=", True)]):
        position = company.sale_export_fiscal_position_id
        if not position or position.auto_apply or position.country_id or position.country_group_id:
            continue
        countries = env["res.country"].search([("id", "!=", company.account_fiscal_country_id.id)])
        group = env["res.country.group"].create(
            {
                "name": f"Export sales — {company.name}",
                "country_ids": [(6, 0, countries.ids)],
            }
        )
        position.write({"auto_apply": True, "country_group_id": group.id})
