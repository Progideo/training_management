"""Disposable CI only: signed evidence survives update and signature replacement."""

import base64
from io import BytesIO
import json
import os

from PIL import Image, ImageDraw
from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import api
from odoo.exceptions import ValidationError

if env.cr.dbname != "tm_suite_test":
    raise RuntimeError("Disposable attendance CI database only")


def png():
    image = Image.new("RGB", (160, 60), "white")
    ImageDraw.Draw(image).line((10, 40, 120, 10), fill="black", width=3)
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode()


def snapshot():
    presence = env.ref("training_management_test.signed_presence")
    env.cr.execute(
        "SELECT to_jsonb(e) FROM training_attendance_event e WHERE attendance_id=%s ORDER BY id", [presence.id]
    )
    return json.dumps({"events": [row[0] for row in env.cr.fetchall()], "minutes": presence.minutes}, sort_keys=True)


phase = os.environ["ATTENDANCE_SIGNATURE_PHASE"]
original = env.ref("training_management_test.s07_presence")
participant = original.enrollment_id.user_id
trainer = env.ref("training_management_test.s07_trainer")
signature = env["training.attendance.signature"].with_user(participant)

if phase == "prepare":
    coordinator = env.ref("training_management_test.s052_coordinator")
    day = original.session_id.start_date
    session = (
        env["training.session"]
        .with_user(coordinator)
        ._create_scheduled(
            [
                {
                    "name": "Fictional signed afternoon",
                    "delivery_id": original.session_id.delivery_id.id,
                    "instructor_id": trainer.partner_id.id,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/signed",
                    "start_date": day,
                    "end_date": day,
                    "start_hour": 14,
                    "end_hour": 16,
                }
            ],
            reason="Fictional signature upgrade fixture",
        )
    )
    for user in (participant, trainer):
        env["training.attendance.signature"].with_user(user)._save_drawing(png(), 0)
    service = env["training.attendance.service"]
    key = f"{day.isoformat()}-pm"
    service.with_user(participant)._sign_halfday(
        original.enrollment_id.id, key, signature_version=1, accepted=True, definition=service._day_definition(session)
    )
    presence = env["training.attendance"].search([("session_id", "=", session.id)])
    service.with_user(trainer)._sign_review(
        session.id,
        original.enrollment_id.id,
        0,
        0,
        signature_version=1,
        period_key=key,
        revision=presence.revision,
        definition=service._definition(session),
    )
    assert len(presence.event_ids) == 2 and all(presence.event_ids.mapped("signature")) and presence.minutes == 120
    env["ir.model.data"].create(
        {
            "module": "training_management_test",
            "name": "signed_presence",
            "model": presence._name,
            "res_id": presence.id,
        }
    )
    signature._save_drawing(False, 1)
    env["ir.config_parameter"].set_str("training_management_test.signed_snapshot", snapshot())
    env.cr.commit()  # Synthetic disposable fixture only.
    print("SIGNED_HISTORY_PREPARED")
elif phase == "verify":
    assert snapshot() == env["ir.config_parameter"].get_str("training_management_test.signed_snapshot")
    assert not signature._current().drawing and signature._current().version == 2
    assert not original.event_ids.filtered("signature"), "Historical declarations must not acquire signatures"
    print("SIGNED_HISTORY_PRESERVED: snapshots, durations, deletion and unsigned history")
elif phase == "concurrency":
    context = {"allowed_company_ids": participant.company_ids.ids}
    signature._save_drawing(png(), 2)
    env.cr.commit()
    with env.registry.cursor() as first, env.registry.cursor() as second:
        one, two = [
            api.Environment(cursor, participant.id, context)["training.attendance.signature"]
            for cursor in (first, second)
        ]
        one._save_drawing(png(), 3)
        second.execute("SET LOCAL lock_timeout = '300ms'")
        try:
            two._snapshot(3)
        except LockNotAvailable:
            second.rollback()
        else:
            raise AssertionError("Signature use bypassed replacement lock")
        first.commit()
    with env.registry.cursor() as first, env.registry.cursor() as stale:
        one = api.Environment(first, participant.id, context)["training.attendance.signature"]
        two = api.Environment(stale, participant.id, context)["training.attendance.signature"]
        assert two._current().version == 4  # Establish a real, pre-replacement snapshot.
        one._save_drawing(png(), 4)
        first.commit()
        try:
            two._snapshot(4)
        except SerializationFailure:
            stale.rollback()
        else:
            raise AssertionError("A pre-replacement snapshot must retry even after the lock was released")
    with env.registry.cursor() as retry:
        current = api.Environment(retry, participant.id, context)["training.attendance.signature"]
        try:
            current._snapshot(4)
        except ValidationError:
            pass
        else:
            raise AssertionError("Stale signature version accepted after replacement")
        assert current._snapshot(5)["signature_version"] == 5
    print("SIGNED_CONCURRENCY_OK: replacement lock, repeatable-read retry and stale signature refusal")
