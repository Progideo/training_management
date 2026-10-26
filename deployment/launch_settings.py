"""Apply reviewed, company-scoped native launch settings from an Odoo shell.

Install the profile's localization module first. The caller owns backup, commit,
production authorization and the private profile; this function never commits.
"""

import json


def _default(env, company, model, name, value):
    field = env["ir.model.fields"].search([("model", "=", model), ("name", "=", name)], limit=1)
    if not field:
        raise ValueError(f"Unknown default field: {model}.{name}")
    domain = [("field_id", "=", field.id), ("company_id", "=", company.id), ("user_id", "=", False)]
    if "condition" in env["ir.default"]._fields:
        domain.append(("condition", "=", False))
    defaults = env["ir.default"].search(domain)
    if len(defaults) > 1:
        raise ValueError(f"Ambiguous existing default: {model}.{name}")
    value = json.dumps(value)
    if defaults:
        if defaults.json_value != value:
            defaults.write({"json_value": value})
    else:
        env["ir.default"].create({"field_id": field.id, "company_id": company.id, "json_value": value})


def _bind(env, key, record):
    module, name = key.split(".", 1)
    existing = env.ref(key, raise_if_not_found=False)
    if existing:
        if existing != record:
            raise ValueError(f"Conflicting external identifier: {key}")
    else:
        env["ir.model.data"].create(
            {"module": module, "name": name, "model": record._name, "res_id": record.id, "noupdate": True}
        )


def _apply(env, profile):
    """Initialize localization only before accounting activity; then apply defaults."""
    if not env.is_system() or env.cr.dbname != profile["database"]:
        raise ValueError("Administrator and exact target database are required")
    company = env.ref(profile["company_xmlid"])
    if company._name != "res.company" or company.name != profile["expected_company_name"]:
        raise ValueError("Unexpected target company")
    env = env(context={**env.context, "allowed_company_ids": company.ids, "tracking_disable": True})
    company = env["res.company"].browse(company.id)
    country = env["res.country"].search([("code", "=", profile["country_code"])], limit=1)
    currency = env["res.currency"].with_context(active_test=False).search([("name", "=", profile["currency"])], limit=1)
    if not country or not currency or company.country_id != country:
        raise ValueError("Company country must be reviewed before launch settings")
    module = env["ir.module.module"].search([("name", "=", profile["localization_module"])], limit=1)
    if module.state != "installed":
        raise ValueError("Install the reviewed native localization module first, without demo data")
    moves = env["account.move"].search([("company_id", "=", company.id)])
    if company.chart_template != profile["chart_template"]:
        if moves or env["account.journal"].search_count(
            [("company_id", "=", company.id), ("bank_account_id", "!=", False)]
        ):
            raise ValueError("Cannot replace accounting configuration with existing moves or configured bank journals")
        if env["sale.order"].search_count(
            [("company_id", "=", company.id), ("state", "not in", ["draft", "sent"])]
        ):
            raise ValueError("Cannot initialize accounting after commercial confirmation")
        env["account.chart.template"].try_loading(profile["chart_template"], company, install_demo=False)
        company.invalidate_recordset()
    if company.account_fiscal_country_id != country:
        raise ValueError("Localization did not set the expected fiscal country")
    if company.currency_id != currency:
        if moves:
            raise ValueError("Cannot change base currency after accounting activity")
        company.currency_id = currency
    if not currency.active:
        currency.active = True

    tax = env.ref(f"account.{company.id}_{profile['sales_tax_ref']}")
    if tax.company_id != company or tax.type_tax_use != "sale" or tax.amount != profile["sales_tax_rate"]:
        raise ValueError("Native sales tax does not match the reviewed profile")
    if company.account_sale_tax_id != tax:
        company.account_sale_tax_id = tax

    key = f"launch_settings.company_{company.id}_pricelist_{currency.name.lower()}"
    pricelist = env.ref(key, raise_if_not_found=False)
    if not pricelist:
        initial = env.ref("product.list0", raise_if_not_found=False)
        # Reuse an empty initial list only before confirmed business. No fixed
        # foreign-currency prices or confirmed documents are converted silently.
        if (
            initial
            and initial.company_id == company
            and not initial.item_ids
            and not env["sale.order"].search_count(
                [("pricelist_id", "=", initial.id), ("state", "not in", ["draft", "sent"])]
            )
        ):
            pricelist = initial
        else:
            pricelist = env["product.pricelist"].create(
                {"name": profile["pricelist_name"], "currency_id": currency.id, "company_id": company.id}
            )
        _bind(env, key, pricelist)
    if pricelist._name != "product.pricelist" or pricelist.company_id != company:
        raise ValueError("Launch pricelist must belong to the target company")
    if pricelist.currency_id != currency and (
        pricelist.item_ids
        or env["sale.order"].search_count(
            [("pricelist_id", "=", pricelist.id), ("state", "not in", ["draft", "sent"])]
        )
    ):
        raise ValueError("Existing prices or commercial history prevent a currency change")
    values = {"name": profile["pricelist_name"], "currency_id": currency.id, "active": True, "sequence": 1}
    changes = {k: v for k, v in values.items() if (pricelist[k].id if k == "currency_id" else pricelist[k]) != v}
    if changes:
        pricelist.write(changes)
    _default(env, company, "res.partner", "specific_property_product_pricelist", pricelist.id)

    term = env.ref(profile["payment_term_xmlid"])
    if (
        len(term.line_ids) != 1
        or term.line_ids.value != "percent"
        or term.line_ids.value_amount != 100
        or term.line_ids.delay_type != "days_after"
        or term.line_ids.nb_days != profile["payment_term_days"]
        or term.early_discount
        or (term.company_id and term.company_id != company)
    ):
        raise ValueError("Payment term must match the reviewed days after invoice date")
    _default(env, company, "res.partner", "property_payment_term_id", term.id)
    env.flush_all()
    if env["account.move"].search([("company_id", "=", company.id)]) != moves:
        raise ValueError("Launch configuration must not create accounting moves")
    return {
        "company_id": company.id,
        "localization_module": module.name,
        "chart_template": company.chart_template,
        "fiscal_country": company.account_fiscal_country_id.code,
        "currency": company.currency_id.name,
        "pricelist_id": pricelist.id,
        "sales_tax_id": tax.id,
        "sales_tax_rate": tax.amount,
        "payment_term_id": term.id,
        "payment_term_days": term.line_ids.nb_days,
        "accounting_moves_created": 0,
    }


def apply(env, profile):
    """Apply atomically; installing modules remains a separate deployment step."""
    with env.cr.savepoint():
        return _apply(env, profile)
