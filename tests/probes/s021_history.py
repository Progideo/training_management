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
