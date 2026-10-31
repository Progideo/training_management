"""Disposable database only: new attendance evidence survives another update."""

import hashlib
import json
import os
from datetime import timedelta

from odoo import fields
from odoo.tests import new_test_user

if env.cr.dbname != "tm_suite_test":
    raise RuntimeError("Disposable attendance CI database only")


def remember(name, record):
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": name, "model": record._name, "res_id": record.id}
    )


def snapshot():
    presence = env.ref("training_management_test.s07_presence")
    records = {}
    for table, column, value in (
        ("training_attendance", "id", presence.id),
        ("training_attendance_event", "attendance_id", presence.id),
        ("training_session", "id", presence.session_id.id),
    ):
        env.cr.execute(
            f"SELECT to_jsonb(t) FROM {table} t WHERE {column}=%s ORDER BY id", [value]
        )  # fixed identifiers above; synthetic fixtures only
        records[table] = [row[0] for row in env.cr.fetchall()]
        if table == "training_attendance":
            for row in records[table]:
                if "period_key" in row:
                    assert row.pop("period_key") == "legacy"
    records["minutes"] = presence.minutes
    records["file"] = hashlib.sha256(presence.event_ids.filtered("filename").data.content).hexdigest()
    return json.dumps(records, sort_keys=True, default=str)


if os.environ["C06_ATTENDANCE_PHASE"] == "prepare":
    coordinator = new_test_user(
        env, login="c06_history_coordinator", groups="training_management.group_training_coordinator"
    )
    participant = new_test_user(env, login="c06_history_participant", groups="base.group_portal")
    category = env["training.category"].create({"name": "Fictional C06 Category", "company_id": env.company.id})
    course = env["training.course"].create(
        {"name": "Fictional C06 Course", "company_id": env.company.id, "category_id": category.id}
    )
    program = env["training.program.version"].create(
        {
            "course_id": course.id,
            "version": "C06-1",
            "title": "Fictional C06 programme",
            "objectives": "Practice",
            "target_audience": "Beginners",
            "prerequisites": "Review",
            "content": "Fictional practice",
            "duration_hours": 2,
            "delivery_mode": "elearning",
            "language_id": env.ref("base.lang_en").id,
            "teaching_methods": "Exercises",
            "evaluation_criteria": "Review",
            "access_conditions": "Manual authorization",
            "accessibility_contact_id": coordinator.partner_id.id,
            "accessibility_information": "Contact coordination",
        }
    )
    program.action_validate()
    remember("s052_coordinator", coordinator)
    remember("s052_participant", participant)
    remember("upgrade_program", program)
    participant = env.ref("training_management_test.s052_participant")
    trainer = new_test_user(env, login="s07_history_trainer", groups="base.group_portal")
    program = env.ref("training_management_test.upgrade_program")
    day = fields.Date.today() - timedelta(days=1)
    delivery = (
        env["training.delivery"]
        .with_user(coordinator)
        .create(
            {
                "name": "Fictional attendance history",
                "program_id": program.id,
                "kind": "session",
                "start_at": str(day),
                "end_at": str(day + timedelta(days=1)),
                "timezone": "UTC",
                "access_policy": "duration",
                "access_days": 10,
            }
        )
    )
    session = (
        env["training.session"]
        .with_user(coordinator)
        .create(
            {
                "name": "Fictional attendance session",
                "delivery_id": delivery.id,
                "instructor_id": trainer.partner_id.id,
                "mode": "remote",
                "meeting_url": "https://example.invalid/session",
                "start_date": day,
                "end_date": day,
                "start_hour": 0,
                "end_hour": 2,
                "attendance_mode": "mixed",
            }
        )
    )
    delivery.action_confirm()
    enrollment = (
        env["training.enrollment"]
        .with_user(coordinator)
        .create(
            {
                "delivery_id": delivery.id,
                "participant_id": participant.partner_id.id,
                "user_id": participant.id,
                "free_reason": "Fictional CI participant",
            }
        )
    )
    enrollment.action_validate_prerequisites(reason="Fictional admission")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Fictional authorization")
    enrollment.action_open_access(reason="Fictional opening")
    presence = (
        env["training.attendance.service"]
        .with_user(participant)
        ._declare(
            enrollment.id,
            session.id,
            30,
            120,
            accepted=True,
            definition=env["training.attendance.service"]._definition(session),
        )
    )
    env["training.attendance.service"].with_user(trainer)._review(
        session.id,
        enrollment.id,
        30,
        120,
        revision=presence.revision,
        reason="Fictional verified late declaration",
        definition=env["training.attendance.service"]._definition(session),
    )
    env["training.attendance.service"].with_user(coordinator)._review(
        session.id,
        enrollment.id,
        45,
        120,
        revision=presence.revision,
        correction=True,
        reason="Fictional signed correction",
        data=b"%PDF-1.4\nFictional attendance evidence\n%%EOF",
        filename="proof.pdf",
        definition=env["training.attendance.service"]._definition(session),
    )
    env["training.attendance.service"].with_user(trainer)._invalidate(
        session.id,
        enrollment.id,
        revision=presence.revision,
        reason="Fictional invalidation retained through upgrade",
        definition=env["training.attendance.service"]._definition(session),
    )
    assert presence.state == "invalidated" and presence.minutes == 0
    remember("s07_presence", presence)
    remember("s07_trainer", trainer)
    env["ir.config_parameter"].set_str("training_management_test.s07_snapshot", snapshot())
    env.cr.commit()  # Guarded, disposable fixture only.
    print("S07_HISTORY_PREPARED")
else:
    assert snapshot() == env["ir.config_parameter"].get_str("training_management_test.s07_snapshot")
    print("S07_HISTORY_OK: declarations, wording, actors, times, correction and evidence unchanged")
