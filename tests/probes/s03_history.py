"""Persistent, synthetic S02 -> S03 and S03 -> S03 upgrade fixtures.

Use S03_UPGRADE_PHASE=prepare|verify|prepare_s03|verify_s03 on an isolated
 tm_s03_test_* database. The prepare commits are deliberate, test-only.
"""
import json
import os
from datetime import timedelta

from psycopg2 import sql
from odoo import Command, fields
from odoo.tests import new_test_user

if not env.cr.dbname.startswith("tm_s03_test_"):  # noqa: F821
    raise RuntimeError("Only disposable S03 test databases are allowed")
phase = os.environ["S03_UPGRADE_PHASE"]
key = "training_management.s03_synthetic_history"
params = env["ir.config_parameter"]


def snapshot(spec):
    result = {}
    for table, values in spec.items():
        columns, ids = values
        env.cr.execute(sql.SQL("SELECT {} FROM {} WHERE id = ANY(%s) ORDER BY id").format(
            sql.SQL(", ").join(map(sql.Identifier, columns)), sql.Identifier(table)), [ids])
        result[table] = env.cr.fetchall()
    return json.dumps(result, sort_keys=True, default=str)


def specification(records):
    result = {}
    for model, rows in records.items():
        table = env[model]._table
        env[model].flush_model()
        env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s AND table_schema='public' ORDER BY ordinal_position", [table])
        result[table] = [[r[0] for r in env.cr.fetchall()], rows.ids]
    return result


if phase == "prepare":
    if params.get_str(key):
        raise RuntimeError("Do not overwrite an existing baseline")
    company = env.company
    actor = new_test_user(env, login="fictional_s03_upgrade_coord", groups="training_management.group_training_coordinator,sales_team.group_sale_salesman", company_id=company.id, company_ids=[Command.set(company.ids)])
    contact = env["res.partner"].create({"name": "Fictional S03 upgrade customer"})
    recipient = new_test_user(env, login="fictional_s03_upgrade_portal", groups="base.group_portal")
    course = env["training.course"].with_user(actor).create({"name": "Fictional S03 upgrade course"})
    program = env["training.program.version"].with_user(actor).create({"course_id": course.id, "version": "UP-V1", "title": "Fictional upgrade programme", "objectives": "Original objectives", "target_audience": "Beginners", "prerequisites": "None", "content": "Original content", "duration_hours": 7, "delivery_mode": "elearning", "language_id": env.ref("base.lang_en").id, "teaching_methods": "Exercises", "evaluation_criteria": "Review", "access_conditions": "Manual approval", "accessibility_contact_id": contact.id, "accessibility_information": "Contact coordination"})
    program.action_validate()
    program.action_publish()
    draft = program.copy({"version": "UP-V2", "objectives": "Future objectives"})
    income = env["account.account"].create({"name": "Fictional Upgrade Revenue", "code": "709981", "account_type": "income", "company_ids": [Command.set(company.ids)]})
    receivable = env["account.account"].create({"name": "Fictional Upgrade Receivable", "code": "349981", "account_type": "asset_receivable", "reconcile": True, "company_ids": [Command.set(company.ids)]})
    env["account.journal"].create({"name": "Fictional Upgrade Sales", "code": "S3U", "type": "sale", "company_id": company.id, "default_account_id": income.id})
    contact.with_company(company).property_account_receivable_id = receivable
    product = env["product.template"].create({"name": "Fictional Upgrade Package", "type": "service", "invoice_policy": "order", "company_id": company.id, "property_account_income_id": income.id, "training_course_id": course.id, "training_price_basis": "package", "taxes_id": [Command.clear()]}).product_variant_id
    currency = env.ref("base.EUR")
    currency.active = True
    pricelist = env["product.pricelist"].create({"name": "Fictional Upgrade EUR", "currency_id": currency.id, "company_id": company.id})
    env["product.pricelist.item"].create({"pricelist_id": pricelist.id, "product_tmpl_id": product.product_tmpl_id.id, "applied_on": "1_product", "compute_price": "fixed", "fixed_price": 100})
    order = env["sale.order"].with_user(actor).create({"partner_id": contact.id, "user_id": actor.id, "pricelist_id": pricelist.id, "training_request_kind": "group", "training_attendee_count": 10, "training_requested_program_id": program.id, "training_requested_currency_id": currency.id, "training_portal_partner_ids": [Command.set(recipient.partner_id.ids)], "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1, "training_program_id": program.id})]})
    order.action_confirm()
    invoice = order.sudo()._create_invoices()
    invoice.write({"training_portal_partner_ids": [Command.set(recipient.partner_id.ids)]})
    invoice.action_post()
    notice = env["training.bank.transfer.notice"].with_user(actor).create({"order_id": order.id, "invoice_id": invoice.id, "amount": 30, "claimed_date": fields.Date.today(), "reference": "FICTIONAL-UPGRADE-NOT-PAID"})
    records = {"training.course": course, "training.program.version": program | draft, "sale.order": order, "sale.order.line": order.order_line, "account.move": invoice, "account.move.line": invoice.line_ids, "training.bank.transfer.notice": notice}
    spec = specification(records)
    # M2M permissions are compared independently of regular model columns.
    for table, column, ids in (("training_sale_portal_partner_rel", "order_id", order.ids), ("training_invoice_portal_partner_rel", "move_id", invoice.ids)):
        env.cr.execute(sql.SQL("SELECT * FROM {} WHERE {} = ANY(%s) ORDER BY 1,2").format(sql.Identifier(table), sql.Identifier(column)), [ids])
        params.set_str(key + "." + table, json.dumps(env.cr.fetchall()))
    params.set_str(key, json.dumps(spec))
    params.set_str(key + ".snapshot", snapshot(spec))
    params.set_str(key + ".order", str(order.id))
    params.set_str(key + ".actor", str(actor.id))
    env.cr.commit()
    print("S02_BASELINE_PERSISTED: programme versions, order, posted invoice, notice and per-document portal permissions")
elif phase == "verify":
    spec = json.loads(params.get_str(key))
    assert snapshot(spec) == params.get_str(key + ".snapshot"), "S02 historical columns changed during upgrade"
    order = env["sale.order"].browse(int(params.get_str(key + ".order")))
    for table, column, ids in (("training_sale_portal_partner_rel", "order_id", order.ids), ("training_invoice_portal_partner_rel", "move_id", order.invoice_ids.ids)):
        env.cr.execute(sql.SQL("SELECT * FROM {} WHERE {} = ANY(%s) ORDER BY 1,2").format(sql.Identifier(table), sql.Identifier(column)), [ids])
        assert json.dumps(env.cr.fetchall()) == params.get_str(key + "." + table)
    assert not env["training.delivery"].search_count([])
    assert not env["training.enrollment"].search_count([])
    print("S02_TO_S03_HISTORY_UNCHANGED: original columns and named permissions; no automatic delivery, enrollment or access")
    env.cr.rollback()
elif phase == "prepare_s03":
    if params.get_str(key + ".s03spec"):
        raise RuntimeError("Do not overwrite S03 history")
    order = env["sale.order"].browse(int(params.get_str(key + ".order")))
    actor = env["res.users"].browse(int(params.get_str(key + ".actor")))
    user = new_test_user(env, login="fictional_s03_upgrade_participant", groups="base.group_portal")
    delivery = env["training.delivery"].with_user(actor).create({"name": "Fictional Upgrade Delivery", "program_id": order.training_requested_program_id.id, "kind": "autonomous", "capacity": 10, "access_policy": "duration", "access_days": 10})
    lot = env["training.seat.allocation"].with_user(actor).create({"delivery_id": delivery.id, "customer_id": order.partner_id.id, "quantity": 10, "sale_line_id": order.order_line.id, "source_reference": "FICTIONAL-UPGRADE-LOT", "expires_at": fields.Datetime.now() + timedelta(days=1)})
    lot.action_confirm()
    enrollment = env["training.enrollment"].with_user(actor).create({"delivery_id": delivery.id, "allocation_id": lot.id, "participant_id": user.partner_id.id, "user_id": user.id})
    enrollment.action_validate_prerequisites(reason="Manual B2B admission")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Manual B2B authorization")
    enrollment.action_open_access(reason="Manual B2B opening")
    enrollment.action_extend_access(enrollment.access_end + timedelta(days=1), reason="Manual B2B extension")
    spec = specification({"training.delivery": delivery, "training.seat.allocation": lot, "training.enrollment": enrollment, "training.operation": delivery.operation_ids})
    params.set_str(key + ".s03spec", json.dumps(spec))
    params.set_str(key + ".s03snapshot", snapshot(spec))
    env.cr.commit()
    print("S03_BASELINE_PERSISTED: allocation, admission, B2B access, extension and immutable operation history")
elif phase == "verify_s03":
    spec = json.loads(params.get_str(key + ".s03spec"))
    assert snapshot(spec) == params.get_str(key + ".s03snapshot"), "S03 update changed historical records"
    print("S03_UPDATE_HISTORY_UNCHANGED: all columns and history preserved")
    env.cr.rollback()
else:
    raise RuntimeError("Unknown S03_UPGRADE_PHASE")
