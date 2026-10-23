"""Persist fictional document grants and compare them across a native update."""

import hashlib
import json
import os

from odoo import Command

if not env.cr.dbname.startswith("tm_s01_test_s021_"):
    raise RuntimeError("Disposable S02.1 databases only")
phase = os.environ["S021_PHASE"]
params = env["ir.config_parameter"]
key = "training_management.s021_history"


def snapshot(spec):
    values = {}
    for model, (ids, columns) in spec.items():
        values[model] = env[model].browse(ids).read(columns)
    return json.dumps(values, sort_keys=True, default=str)


if phase == "prepare":
    if params.get_str(key):
        raise RuntimeError("Do not overwrite historical fixtures")
    # The published programme is prepared by the existing catalogue probe.
    program = env.ref("training_management_test.upgrade_program")
    buyer = env["res.partner"].create({"name": "Fictional S02.1 Buyer"})
    contact = env["res.partner"].create({"name": "Fictional S02.1 Contact", "email": "s021@example.invalid"})
    order = env["sale.order"].create(
        {
            "partner_id": buyer.id,
            "training_request_kind": "group",
            "training_requested_program_id": program.id,
            "training_portal_partner_ids": [Command.set(contact.ids)],
        }
    )
    order._portal_ensure_token()
    message = env["mail.message"].create(
        {
            "model": order._name,
            "res_id": order.id,
            "body": "Fictional preserved message",
            "message_type": "comment",
            "partner_ids": [Command.set(contact.ids)],
        }
    )
    attachment = env["ir.attachment"].create(
        {
            "name": "fictional-s021.txt",
            "raw": b"Fictional preserved attachment",
            "res_model": "mail.message",
            "res_id": message.id,
        }
    )
    attachment.generate_access_token()
    delivery = env["training.delivery"].create(
        {
            "name": "Fictional S02.1 Autonomous",
            "program_id": program.id,
            "kind": "autonomous",
            "access_policy": "duration",
            "access_days": 30,
        }
    )
    queued = env["mail.mail"].create(
        {
            "model": order._name,
            "res_id": order.id,
            "subject": "Fictional preserved queue",
            "body_html": "Fictional preserved queue",
            "email_from": "sender@example.invalid",
            "recipient_ids": [Command.set(contact.ids)],
            "auto_delete": False,
        }
    )
    accounts = {}
    for name, kind, reconcile in (
        ("income", "income", False),
        ("receivable", "asset_receivable", True),
        ("bank", "asset_cash", False),
        ("outstanding", "asset_current", True),
    ):
        accounts[name] = env["account.account"].create(
            {
                "name": "Fictional S02.1 " + name,
                "code": "H021" + name,
                "account_type": kind,
                "reconcile": reconcile,
                "company_ids": [Command.set(env.company.ids)],
            }
        )
    buyer.property_account_receivable_id = accounts["receivable"]
    sales_journal = env["account.journal"].create(
        {
            "name": "Fictional S02.1 Sales",
            "type": "sale",
            "code": "H21",
            "default_account_id": accounts["income"].id,
        }
    )
    bank = env["account.journal"].create(
        {
            "name": "Fictional S02.1 Bank",
            "type": "bank",
            "code": "H2B",
            "default_account_id": accounts["bank"].id,
        }
    )
    bank.inbound_payment_method_line_ids.filtered(lambda line: line.code == "manual").payment_account_id = accounts[
        "outstanding"
    ]
    product = env["product.product"].create({"name": "Fictional historical service", "type": "service"})
    sale_line = env["sale.order.line"].create(
        {
            "order_id": order.id,
            "product_id": product.id,
            "price_unit": 100,
            "product_uom_qty": 1,
        }
    )
    invoice = env["account.move"].create(
        {
            "move_type": "out_invoice",
            "partner_id": buyer.id,
            "journal_id": sales_journal.id,
            "training_portal_partner_ids": [Command.set(contact.ids)],
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "Fictional historical service",
                        "quantity": 1,
                        "price_unit": 100,
                        "account_id": accounts["income"].id,
                        "tax_ids": [Command.clear()],
                        "sale_line_ids": [Command.set(sale_line.ids)],
                    }
                )
            ],
        }
    )
    invoice.action_post()
    env["account.payment.register"].with_context(active_model="account.move", active_ids=invoice.ids).create(
        {
            "journal_id": bank.id,
            "training_bank_reference": "HISTORICAL-S021",
            "training_bank_verified": True,
        }
    ).action_create_payments()
    payment = env["account.payment"].search([("training_bank_reference", "=", "HISTORICAL-S021")])
    assert len(payment) == 1 and payment.reconciled_invoice_ids == invoice
    specs = {
        "sale.order": [
            order.ids,
            [
                "name",
                "state",
                "partner_id",
                "company_id",
                "training_requested_program_id",
                "training_portal_partner_ids",
                "access_token",
            ],
        ],
        "mail.message": [message.ids, ["body", "model", "res_id", "partner_ids", "create_uid", "create_date"]],
        "ir.attachment": [
            attachment.ids + program.pdf_attachment_id.ids,
            [
                "name",
                "res_model",
                "res_id",
                "res_field",
                "checksum",
                "public",
                "access_token",
                "create_uid",
                "create_date",
            ],
        ],
        "training.delivery": [delivery.ids, ["name", "program_id", "state", "access_policy", "access_days"]],
        "mail.mail": [queued.ids, ["model", "res_id", "state", "recipient_ids", "subject", "body_html"]],
        "account.move": [
            invoice.ids,
            [
                "name",
                "state",
                "amount_total",
                "amount_residual",
                "payment_state",
                "training_portal_partner_ids",
                "training_is_sale_invoice",
                "line_ids",
            ],
        ],
        "account.payment": [
            payment.ids,
            [
                "state",
                "amount",
                "move_id",
                "reconciled_invoice_ids",
                "training_bank_reference",
                "training_bank_verified_by_id",
                "training_bank_verified_at",
            ],
        ],
    }
    params.set_str(
        key,
        json.dumps(
            {
                "spec": specs,
                "snapshot": snapshot(specs),
                "pdf": program.pdf_attachment_id.id,
                "sha": hashlib.sha256(program.pdf_attachment_id.raw).hexdigest(),
            }
        ),
    )
    env.cr.commit()  # Test-only fixture deliberately persisted across processes.
    print("S021_DOCUMENTS_GRANTS_PDF_AND_QUEUE_PERSISTED")
elif phase == "verify":
    expected = json.loads(params.get_str(key))
    assert snapshot(expected["spec"]) == expected["snapshot"], "Historical documents or grants changed"
    assert hashlib.sha256(env["ir.attachment"].browse(expected["pdf"]).raw).hexdigest() == expected["sha"]
    print("S021_DOCUMENTS_GRANTS_PDF_AND_QUEUE_UNCHANGED")
    env.cr.rollback()
else:
    raise RuntimeError("Use S021_PHASE=prepare|verify")
