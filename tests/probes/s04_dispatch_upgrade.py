"""Persisted S04 dispatch history across the review corrections. Synthetic only."""

import json
import os

from odoo import Command
from odoo.tests import new_test_user

if not env.cr.dbname.startswith("tm_s04_test_"):
    raise RuntimeError("Disposable S04 databases only")
params = env["ir.config_parameter"]
key = "training_management.s04_dispatch_history"
phase = os.environ["S04_PHASE"]
if phase == "prepare":
    coord = new_test_user(
        env,
        login="fictional_s04_dispatch_coord",
        groups="training_management.group_training_coordinator",
        company_id=env.company.id,
        company_ids=[Command.set(env.company.ids)],
    )
    coord.email = "coord@example.invalid"
    trainer = env["res.partner"].create({"name": "Fictional dispatch trainer", "email": "trainer@example.invalid"})
    course = env["training.course"].with_user(coord).create({"name": "Fictional dispatch course"})
    program = (
        env["training.program.version"]
        .with_user(coord)
        .create(
            {
                "course_id": course.id,
                "version": "V1",
                "title": "Fictional programme",
                "objectives": "Practice",
                "target_audience": "Beginners",
                "prerequisites": "None",
                "content": "Workshop",
                "duration_hours": 3,
                "delivery_mode": "remote",
                "language_id": env.ref("base.lang_en").id,
                "teaching_methods": "Exercises",
                "evaluation_criteria": "Review",
                "access_conditions": "Manual",
                "accessibility_contact_id": trainer.id,
                "accessibility_information": "Contact coordination",
            }
        )
    )
    program.action_validate()
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional dispatch delivery",
                "program_id": program.id,
                "kind": "session",
                "timezone": "UTC",
                "start_at": "2027-01-01",
                "end_at": "2027-02-01",
                "access_policy": "duration",
                "access_days": 10,
            }
        )
    )
    session = (
        env["training.session"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional dispatch session",
                "delivery_id": delivery.id,
                "instructor_id": trainer.id,
                "mode": "remote",
                "meeting_url": "https://example.invalid/meeting",
                "start_date": "2027-01-04",
                "end_date": "2027-01-04",
                "start_hour": 9,
                "end_hour": 12,
            }
        )
    )
    delivery.action_confirm()
    inv = env["training.invitation"].with_user(coord)
    assert inv._queue(delivery, trainer) == 1
    session._apply_schedule({"start_hour": 10}, "Fictional change to B")
    assert inv._queue(delivery, trainer) == 1
    # Simulate delivered history without contacting an SMTP server.
    delivery.invitation_ids.sudo().mail_id.write({"state": "sent"})
    snapshot = delivery.invitation_ids.sudo().read(
        ["session_id", "partner_id", "fingerprint", "mail_id", "requested_by_id", "requested_at", "recipient_timezone"]
    )
    mails = delivery.invitation_ids.sudo().mail_id.read(["subject", "body_html", "email_to", "state"])
    params.set_str(
        key,
        json.dumps(
            {
                "coord": coord.id,
                "delivery": delivery.id,
                "session": session.id,
                "trainer": trainer.id,
                "invitations": snapshot,
                "mails": mails,
            },
            default=str,
        ),
    )
    env.cr.commit()  # Test-only persisted fixture in an explicitly disposable DB.
    print("S04_DISPATCH_BASELINE_PERSISTED: old A/B snapshots and messages")
elif phase == "verify":
    saved = json.loads(params.get_str(key))
    delivery = env["training.delivery"].with_user(saved["coord"]).browse(saved["delivery"])
    inv = delivery.invitation_ids.sudo()
    fields = list(saved["invitations"][0])
    assert json.loads(json.dumps(inv.read(fields), default=str)) == saved["invitations"]
    assert inv.mail_id.read(list(saved["mails"][0])) == saved["mails"]
    assert inv.sorted("id").mapped("dispatch_number") == [1, 2]
    delivery.session_ids._apply_schedule({"start_hour": 9}, "Fictional return to A after upgrade")
    model = env["training.invitation"].with_user(saved["coord"])
    trainer = env["res.partner"].browse(saved["trainer"])
    assert model._queue(delivery, trainer) == 1
    assert model._queue(delivery, trainer) == 0
    assert delivery.invitation_ids.sorted("id").mapped("dispatch_number") == [1, 2, 3]
    print("S04_DISPATCH_UPGRADE_OK: immutable history, numbered dispatches, A/B/A and idempotent replay")
    env.cr.rollback()
else:
    raise RuntimeError("Unknown phase")
