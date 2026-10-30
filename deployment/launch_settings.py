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


def _export_sales(env, company, source_tax, profile):
    if not profile:
        return {}
    if "sale_fiscal_by_invoice_address" not in company._fields:
        raise ValueError("Install sale_invoice_address_fiscal before export configuration")
    group = env.ref(f"account.{company.id}_{profile['tax_group_ref']}")
    if group.company_id != company:
        raise ValueError("Export tax group must belong to the company")
    key = f"launch_settings.company_{company.id}_export_sales"
    position = env.ref(key, raise_if_not_found=False)
    if not position:
        position = env["account.fiscal.position"].create({"name": profile["name"], "company_id": company.id})
        _bind(env, key, position)
    if position._name != "account.fiscal.position" or position.company_id != company:
        raise ValueError("Export fiscal position must belong to the company")
    position.write(
        {"name": profile["name"], "auto_apply": True, "vat_required": False, "note": profile["invoice_note"]}
    )
    key = f"launch_settings.company_{company.id}_export_sales_tax"
    tax = env.ref(key, raise_if_not_found=False)
    if not tax:
        tax = env["account.tax"].create(
            {
                "name": profile["tax_name"],
                "company_id": company.id,
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": 0,
                "tax_group_id": group.id,
            }
        )
        _bind(env, key, tax)
    if tax._name != "account.tax" or tax.company_id != company:
        raise ValueError("Export tax must belong to the company")
    tax.write(
        {
            "active": True,
            "amount": 0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "name": profile["tax_name"],
            "invoice_label": "0%",
            "tax_group_id": group.id,
            "fiscal_position_ids": [(6, 0, position.ids)],
            "original_tax_ids": [(6, 0, source_tax.ids)],
        }
    )
    position.tax_ids = tax
    # Native geographical matching, evaluated against the opted-in billing address.
    key = f"launch_settings.company_{company.id}_export_countries"
    countries = env["res.country"].search([("id", "!=", company.account_fiscal_country_id.id)])
    group_countries = env.ref(key, raise_if_not_found=False)
    if not group_countries:
        group_countries = env["res.country.group"].create({"name": f"Export sales — {company.name}"})
        _bind(env, key, group_countries)
    group_countries.country_ids = countries
    position.write({"country_group_id": group_countries.id, "country_id": False})
    if not company.domestic_fiscal_position_id:
        raise ValueError("Native domestic fiscal position is required")
    company.write({"sale_export_fiscal_position_id": position.id, "sale_fiscal_by_invoice_address": True})
    if position.map_tax(source_tax) != tax:
        raise ValueError("Export tax mapping failed")
    return {
        "export_fiscal_position_id": position.id,
        "export_sales_tax_id": tax.id,
        "export_sales_tax_rate": tax.amount,
        "fiscal_address": "invoice",
    }


def _sales_currencies(env, company, profile):
    def currencies(codes):
        records = env["res.currency"].with_context(active_test=False).search([("name", "in", codes)])
        if set(records.mapped("name")) != set(codes):
            raise ValueError("Unknown sales currency in deployment profile")
        return records

    active = currencies(profile.get("commercial_currencies", [profile["currency"]]))
    active.filtered(lambda item: not item.active).write({"active": True})
    result = {"commercial_currencies": sorted(active.mapped("name"))}
    for key, field in [
        ("domestic_sales_currencies", "sale_domestic_currency_ids"),
        ("foreign_sales_currencies", "sale_foreign_currency_ids"),
    ]:
        if key in profile:
            if field not in company._fields:
                raise ValueError("Upgrade sale_invoice_address_fiscal before configuring currency restrictions")
            allowed = currencies(profile[key])
            if key == "domestic_sales_currencies" and allowed and company.currency_id not in allowed:
                raise ValueError("The company base currency must be authorized for domestic sales")
            if company[field] != allowed:
                company[field] = allowed
        result[key] = sorted(company[field].mapped("name")) if field in company._fields else []
    return result


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
        if env["sale.order"].search_count([("company_id", "=", company.id), ("state", "not in", ["draft", "sent"])]):
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
        or env["sale.order"].search_count([("pricelist_id", "=", pricelist.id), ("state", "not in", ["draft", "sent"])])
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
    export = _export_sales(env, company, tax, profile.get("export_sales"))
    currencies = _sales_currencies(env, company, profile)
    env.flush_all()
    if env["account.move"].search([("company_id", "=", company.id)]) != moves:
        raise ValueError("Launch configuration must not create accounting moves")
    return {
        **export,
        **currencies,
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


def apply_pedagogical(env, profile):
    """Company defaults only: never recalculate existing periods or reservations."""
    if env.cr.dbname != profile["database"]:
        raise ValueError("Wrong target database")
    company = env.ref(profile["company_xmlid"])
    if company._name != "res.company" or company.name != profile["expected_company_name"]:
        raise ValueError("Wrong target company")
    months, days = profile["access_months"], profile["reservation_days"]
    if type(months) is not int or type(days) is not int or months <= 0 or days <= 0:
        raise ValueError("Use positive integer month and reservation durations")
    with env.cr.savepoint():
        for name, value in {"access_policy": "months", "access_months": months, "reservation_days": days}.items():
            _default(env, company, "training.delivery", name, value)
    return {"company_id": company.id, "access_months": months, "reservation_days": days}


def apply_notifications(env, profile):
    """Set only company identity/alert routing; no transport, queue rewrite or grants."""
    if env.cr.dbname != profile["database"]:
        raise ValueError("Wrong target database")
    company = env.ref(profile["company_xmlid"])
    if company._name != "res.company" or company.name != profile["expected_company_name"]:
        raise ValueError("Wrong target company")
    manager = env["res.users"].search([("login", "=", profile["manager_login"])], limit=1)
    if not manager:
        raise ValueError("Alert manager not found")
    key = f"launch_settings.company_{company.id}_notification_identity"
    template = company.training_notification_template_id or env.ref(key, raise_if_not_found=False)
    identity = {
        "email_from": profile["notification_address"],
        "reply_to": profile.get("reply_to", profile["notification_address"]),
    }
    if not template:
        template = env["mail.template"].create(
            {
                "name": f"Training notifications — {company.name}",
                "model_id": env["ir.model"]._get_id("res.company"),
                **identity,
            }
        )
        _bind(env, key, template)
    elif template.model != "res.company":
        raise ValueError("Notification identity template must target companies")
    elif any(template[field] != value for field, value in identity.items()):
        template.write(identity)
    values = {
        "training_notification_template_id": template.id,
        "training_notification_manager_id": manager.id,
        "training_alert_address": profile["manager_alert_address"],
    }
    changed = {
        key: value
        for key, value in values.items()
        if (company[key].id if key.endswith("_id") else company[key]) != value
    }
    with env.cr.savepoint():
        if changed:
            company.write(changed)
    return {"company_id": company.id, "manager_id": manager.id, "transport_activated": False}
