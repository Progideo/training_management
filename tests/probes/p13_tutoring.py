"""P13 exact history and real transaction races, strictly disposable fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
import os
import threading
import time
from uuid import uuid4

from odoo import api, fields
from odoo.exceptions import LockError, ValidationError
from odoo.http.retrying import retrying
from odoo.tests import new_test_user
from odoo.tools import SQL

if env.cr.dbname not in ("tm_s01_test_p09", "tm_suite_test"):
    raise RuntimeError("Disposable P13 database only")
phase = os.environ["P09_PHASE"]
params = env["ir.config_parameter"]
key = "training_management_test.p13"


def snapshot():
    env.flush_all()
    env.cr.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'training_%' OR tablename LIKE 'survey_%') ORDER BY tablename"
    )
    result = {}
    for (table,) in env.cr.fetchall():
        env.cr.execute(SQL("SELECT to_jsonb(t)::text FROM %s t ORDER BY to_jsonb(t)::text", SQL.identifier(table)))
        result[table] = hashlib.sha256(json.dumps(env.cr.fetchall()).encode()).hexdigest()
    # Original PDF and private files remain byte-for-byte identical as well.
    for attachment in (
        env["ir.attachment"].sudo().search([("res_model", "like", "training.%"), ("type", "=", "binary")])
    ):
        result["file:%s" % attachment.id] = hashlib.sha256(
            attachment.raw.content if attachment.raw else b""
        ).hexdigest()
    return result


if phase == "tutoring_prepare":
    coord = new_test_user(env, login="p13_fixture_coord", groups="training_management.group_training_coordinator")
    quality = new_test_user(env, login="p13_fixture_quality", groups="training_management.group_training_quality")
    tutor = new_test_user(env, login="p13_fixture_tutor", groups="base.group_portal")
    learner = new_test_user(env, login="p13_fixture_learner", groups="base.group_portal")
    peer = new_test_user(env, login="p13_fixture_peer", groups="base.group_portal")
    course = env["training.course"].create({"name": "Fictional P13 course", "company_id": env.company.id})
    course.category_id = env["training.category"].create(
        {"name": "Fictional P13 category", "company_id": env.company.id}
    )
    program = env["training.program.version"].create(
        {
            "course_id": course.id,
            "version": "P13-1",
            "title": "Fictional P13 programme",
            "objectives": "Practice",
            "target_audience": "Learners",
            "prerequisites": "Reviewed",
            "content": "Fictional programme retained",
            "duration_hours": 1,
            "delivery_mode": "elearning",
            "language_id": env.ref("base.lang_en").id,
            "teaching_methods": "Tutoring",
            "evaluation_criteria": "Review",
            "access_conditions": "Explicit authorization",
            "accessibility_contact_id": coord.partner_id.id,
            "accessibility_information": "Contact coordination",
        }
    )
    program.action_validate()
    policy = (
        env["training.retention.category"]
        .with_user(quality)
        .create(
            {
                "name": "Fictional P13 retention",
                "company_id": env.company.id,
                "purpose": "Fictional tests",
                "responsible_id": quality.id,
                "duration_days": 365,
                "archive_policy": "Preserve",
                "deletion_policy": "Manual review",
            }
        )
    )
    policy.action_approve()
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional P13 delivery",
                "program_id": program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 30,
                "learning_tutor_id": tutor.id,
                "timezone": "UTC",
            }
        )
    )
    enrollments = []
    for user in (learner, peer):
        e = (
            env["training.enrollment"]
            .with_user(coord)
            .create(
                {
                    "delivery_id": delivery.id,
                    "participant_id": user.partner_id.id,
                    "user_id": user.id,
                    "free_reason": "Fictional P13 invitation",
                }
            )
        )
        e.action_validate_prerequisites(reason="Fictional review")
        e.action_confirm()
        e.action_authorize(reason="Fictional authorization")
        e.action_open_access(reason="Fictional opening")
        env["training.tutoring.entitlement"].with_user(coord).create(
            {"enrollment_id": e.id, "included_count": 2, "service_reference": "FICT-P13", "retention_id": policy.id}
        )
        enrollments.append(e.id)
    day = (fields.Datetime.now() + timedelta(days=3)).date()
    slots = []
    for index in range(4):
        slot = (
            env["training.tutoring.slot"]
            .with_user(coord)
            .create(
                {
                    "name": "Fictional P13 slot %s" % index,
                    "delivery_id": delivery.id,
                    "tutor_id": tutor.id,
                    "kind": "individual",
                    "capacity": 1,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/tutor",
                    "start_date": day,
                    "end_date": day,
                    "start_hour": 10 + index,
                    "end_hour": 11 + index,
                    "refund_policy": "before",
                    "cancellation_hours": 24,
                    "cancellation_terms": "Fictional P13 terms",
                }
            )
        )
        slot.action_publish()
        slots.append(slot.id)
    booking = env["training.tutoring.service"].with_user(learner)._reserve(enrollments[0], slots[0], str(uuid4()))
    env["training.tutoring.service"].with_user(learner)._cancel(enrollments[0], booking.id)
    preserved = env["training.tutoring.service"].with_user(learner)._reserve(enrollments[0], slots[0], str(uuid4()))
    saved = {
        "coord": coord.id,
        "users": [learner.id, peer.id],
        "enrollments": enrollments,
        "slots": slots,
        "preserved": preserved.id,
        "cancelled": booking.id,
        "snapshot": snapshot(),
        "mail_count": env["training.tutoring.notice"].search_count([]),
    }
    params.set_str(key, json.dumps(saved))
    env.cr.commit()  # only this explicitly guarded disposable fixture
    print("P13 histories, frozen conditions, quota, cancellation, notices and original files baseline OK")
elif phase == "tutoring_verify":
    saved = json.loads(params.get_str(key))
    assert snapshot() == saved["snapshot"], "P13 or earlier histories/files changed"
    assert env["training.tutoring.notice"].search_count([]) == saved["mail_count"], "Retrospective notice"
    print("P13 exact histories, frozen rules, quota, notifications and original files preserved OK")
elif phase == "tutoring_concurrency":
    saved = json.loads(params.get_str(key))
    registry = env.registry
    env.cr.commit()

    def race(operations):
        barrier = threading.Barrier(2)

        def task(operation):
            user, enrollment, slot, token, cancel = operation
            with registry.cursor() as cr:
                local = api.Environment(cr, user, {})
                local.transaction.default_env = local
                # Force both REPEATABLE READ snapshots before either operation.
                local["res.users"].browse(user).read(["active"])
                barrier.wait(timeout=30)

                def action():
                    service = local["training.tutoring.service"]
                    if cancel:
                        return service._cancel(enrollment, cancel).id
                    return service._reserve(enrollment, slot, token).id

                for attempt in range(15):
                    try:
                        return retrying(action, local)
                    except LockError:
                        # Odoo's non-blocking record lock can reject one caller;
                        # a real retry must start with a fresh transaction.
                        cr.rollback()
                        local.invalidate_all()
                        if attempt == 14:
                            raise
                        time.sleep(0.01 * (attempt + 1))
                    except ValidationError:
                        cr.rollback()
                        return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(task, operations))

    # Two different participants contend for the final place.
    result = race(
        [(saved["users"][i], saved["enrollments"][i], saved["slots"][1], str(uuid4()), False) for i in range(2)]
    )
    assert sum(bool(r) for r in result) == 1, result
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["coord"], {})
        active = (
            local["training.tutoring.booking"]
            .sudo()
            .search([("slot_id", "=", saved["slots"][1]), ("state", "=", "confirmed")])
        )
        assert len(active) == 1
        winner = active.id
        winner_user = active.enrollment_id.user_id.id
        winner_enrollment = active.enrollment_id.id
    # The same participant competes for their final included unit, on two slots.
    # Ensure the first learner has exactly one unit remaining first.
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["users"][0], {})
        if winner_enrollment == saved["enrollments"][0]:
            local["training.tutoring.service"]._cancel(winner_enrollment, winner)
        cr.commit()
    result = race(
        [(saved["users"][0], saved["enrollments"][0], saved["slots"][i], str(uuid4()), False) for i in (2, 3)]
    )
    assert sum(bool(r) for r in result) == 1, result
    new_booking = next(r for r in result if r)
    result = race([(saved["users"][0], saved["enrollments"][0], 0, "", new_booking)] * 2)
    assert result == [new_booking, new_booking]
    # Repeated confirmation with one intention creates one row and two notices.
    token = str(uuid4())
    result = race([(saved["users"][0], saved["enrollments"][0], saved["slots"][2], token, False)] * 2)
    assert result[0] == result[1] and result[0]
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["coord"], {})
        model = local["training.tutoring.booking"].sudo()
        assert len(model.search([("enrollment_id", "=", saved["enrollments"][0]), ("request_key", "=", token)])) == 1
        for booking_id, count in ((new_booking, 4), (result[0], 2)):
            assert local["training.tutoring.notice"].search_count([("booking_id", "=", booking_id)]) == count
        assert model.browse(new_booking).refunded
        assert model.browse(saved["preserved"]).state == "confirmed"
    print("P13 concurrent final capacity, final quota, duplicate confirmation and duplicate refund OK")
else:
    raise RuntimeError("Unknown P13 fixture phase")
