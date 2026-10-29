"""P14 preserved private receipts and real transaction races, fictitious DBs only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
import os
import threading
import time
from unittest.mock import patch

from odoo import Command, api, fields
from odoo.exceptions import AccessError, LockError, ValidationError
from odoo.http.retrying import retrying
from odoo.tests import new_test_user
from odoo.tools import SQL

if env.cr.dbname not in ("tm_s01_test_p09", "tm_suite_test"):
    raise RuntimeError("Disposable P14 fixture database only")
patch.object(
    type(env["ir.mail_server"]), "send_email", side_effect=AssertionError("No real transport in P14 fixture")
).start()
phase = os.environ["P09_PHASE"]
params = env["ir.config_parameter"]
key = "training_management_test.p14"


def snapshot():
    env.flush_all()
    env.cr.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'training_%' OR tablename LIKE 'survey_%') ORDER BY tablename"
    )
    result = {}
    for (table,) in env.cr.fetchall():
        env.cr.execute(SQL("SELECT to_jsonb(t)::text FROM %s t ORDER BY to_jsonb(t)::text", SQL.identifier(table)))
        result[table] = hashlib.sha256(json.dumps(env.cr.fetchall()).encode()).hexdigest()
    for attachment in (
        env["ir.attachment"].sudo().search([("res_model", "like", "training.%"), ("type", "=", "binary")])
    ):
        result["file:%s" % attachment.id] = hashlib.sha256(
            attachment.raw.content if attachment.raw else b""
        ).hexdigest()
    return result


if phase == "publication_prepare":
    prior = json.loads(params.get_str("training_management_test.p13"))
    coord = env["res.users"].browse(prior["coord"])
    learner, peer = env["res.users"].browse(prior["users"])
    tutor = env["training.tutoring.slot"].browse(prior["slots"][0]).tutor_id
    policy = env["training.tutoring.entitlement"].search([("enrollment_id", "=", prior["enrollments"][0])]).retention_id
    moderator = new_test_user(
        env,
        login="p14_fixture_moderator",
        groups="training_management.group_training_publication_moderator",
        email="moderator@example.invalid",
    )
    program = (
        env["training.enrollment"]
        .browse(prior["enrollments"][0])
        .program_id.copy({"version": "P14-public", "public_catalogue": True})
    )
    program.action_validate()
    program.action_publish()
    now = fields.Datetime.now()
    day = (now - timedelta(days=1)).date()
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional private P14 delivery",
                "program_id": program.id,
                "kind": "session",
                "start_at": now - timedelta(days=2),
                "end_at": now + timedelta(days=30),
                "timezone": "Europe/Paris",
                "access_policy": "duration",
                "access_days": 30,
            }
        )
    )
    session = (
        env["training.session"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional private P14 session",
                "delivery_id": delivery.id,
                "instructor_id": tutor.partner_id.id,
                "mode": "onsite",
                "location": "Fictional private classroom",
                "attendance_mode": "mixed",
                "start_date": day,
                "end_date": day,
                "start_hour": 9,
                "end_hour": 10,
            }
        )
    )
    delivery.action_confirm(conflict_reason="Fictional isolated fixtures")
    rows = []
    enrollments = []
    for user in (learner, peer):
        user.partner_id.email = user.login + "@example.invalid"
        enrollment = (
            env["training.enrollment"]
            .with_user(coord)
            .create(
                {
                    "delivery_id": delivery.id,
                    "participant_id": user.partner_id.id,
                    "user_id": user.id,
                    "free_reason": "Fictional P14 fixture",
                }
            )
        )
        enrollment.action_validate_prerequisites(reason="Fictional review")
        enrollment.action_confirm()
        enrollment.action_authorize(reason="Fictional authorization")
        enrollment.action_open_access(reason="Fictional access")
        service = env["training.attendance.service"].with_user(coord)
        presence = service._review(
            session.id,
            enrollment.id,
            0,
            60,
            paper=True,
            reason="Fictional signed sheet",
            data=b"%PDF-1.4\nfictional private P14 sheet\n%%EOF",
            filename="fictional.pdf",
            definition=service._definition(session),
        )
        service.with_user(tutor)._review(
            session.id, enrollment.id, 0, 60, revision=presence.revision, definition=service._definition(session)
        )
        row = (
            env["training.publication"]
            .with_user(coord)
            .create(
                {
                    "name": "Fictional P14 review",
                    "delivery_id": delivery.id,
                    "enrollment_id": enrollment.id,
                    "retention_id": policy.id,
                }
            )
        )
        row.action_request_authorization()
        row.with_user(user).sudo()._consent(
            definition=row._definition(),
            body="Fictional P14 preserved opinion",
            identity="name",
            accepted=True,
            identity_accepted=True,
        )
        row.with_user(moderator).write({"moderation_reason": "Fictional exact content and identity checked"})
        row.with_user(moderator).action_publish()
        rows.append(row.id)
        enrollments.append(enrollment.id)
    env["training.publication"].browse(rows[1]).with_user(peer).sudo()._withdraw()
    customer = env["res.partner"].create({"name": "Fictional P14 customer"})
    allocation = (
        env["training.seat.allocation"]
        .with_user(coord)
        .create(
            {
                "delivery_id": delivery.id,
                "customer_id": customer.id,
                "quantity": 1,
                "source_reference": "FICT-P14",
                "expires_at": now + timedelta(days=30),
            }
        )
    )
    grant = (
        env["training.company.authorization"]
        .with_user(coord)
        .create(
            {
                "company_id": delivery.company_id.id,
                "customer_id": customer.id,
                "user_id": peer.id,
                "allocation_ids": [Command.set(allocation.ids)],
            }
        )
    )
    grant.action_confirm()
    case = (
        env["training.publication"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional P14 customer case",
                "kind": "case",
                "delivery_id": delivery.id,
                "allocation_id": allocation.id,
                "representative_id": peer.id,
                "retention_id": policy.id,
                "authority_reference": "Fictional explicit representative mandate",
                "body": "Fictional preserved customer case",
                "public_context": "Fictional approved public context",
                "participation_month": str(day)[:7],
                "identify_client": True,
                "confidential": False,
            }
        )
    )
    case.action_request_authorization()
    case.with_user(peer).sudo()._consent(
        definition=case._definition(), accepted=True, identity="name", identity_accepted=True
    )
    case.with_user(moderator).write({"moderation_reason": "Fictional content and customer name checked"})
    case.with_user(moderator).action_publish()
    saved = {
        "coord": coord.id,
        "moderator": moderator.id,
        "users": [learner.id, peer.id],
        "enrollments": enrollments,
        "reviews": rows,
        "case": case.id,
        "delivery": delivery.id,
        "policy": policy.id,
        "snapshot": snapshot(),
    }
    params.set_str(key, json.dumps(saved))
    env.cr.commit()  # guarded disposable synthetic database only
    print("P14 exact consent, named review, withdrawn review, authorized case and private files baseline OK")
elif phase == "publication_verify":
    saved = json.loads(params.get_str(key))
    assert snapshot() == saved["snapshot"], "P14 or earlier histories/files changed"
    print("P14 exact publication receipts, moderation, withdrawals, notices and original files preserved OK")
elif phase == "publication_concurrency":
    saved = json.loads(params.get_str(key))
    registry = env.registry
    coord = saved["coord"]
    peer = saved["users"][1]
    values = {
        "name": "Fictional concurrent P14 request",
        "delivery_id": saved["delivery"],
        "enrollment_id": saved["enrollments"][1],
        "retention_id": saved["policy"],
    }
    candidates = env["training.publication"].with_user(coord).create([values, values])
    candidate_ids = candidates.ids
    env.cr.commit()

    def race(operations):
        barrier = threading.Barrier(2)

        def task(operation):
            user, row_id, kind, definition = operation
            with registry.cursor() as cr:
                local = api.Environment(cr, user, {})
                local.transaction.default_env = local
                local["res.users"].browse(user).read(["active"])
                barrier.wait(timeout=30)

                def action():
                    row = local["training.publication"].sudo().browse(row_id)
                    if kind == "invite":
                        row.action_request_authorization()
                    elif kind == "consent":
                        row._consent(definition=definition, body="Fictional concurrent opinion", accepted=True)
                    elif kind == "publish":
                        row.action_publish()
                    else:
                        row._withdraw()
                    return row.id

                for attempt in range(15):
                    try:
                        return retrying(action, local)
                    except LockError:
                        cr.rollback()
                        local.invalidate_all()
                        if attempt == 14:
                            raise
                        time.sleep(0.01 * (attempt + 1))
                    except (AccessError, ValidationError):
                        cr.rollback()
                        return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(task, operations))

    result = race([(coord, row_id, "invite", "") for row_id in candidate_ids])
    assert sum(bool(x) for x in result) == 1, result
    winner = next(x for x in result if x)
    with registry.cursor() as cr:
        local = api.Environment(cr, coord, {})
        row = local["training.publication"].browse(winner)
        definition = row._definition()
        assert local["training.publication.notice"].sudo().search_count([("publication_id", "=", winner)]) == 1
    result = race([(peer, winner, "consent", definition)] * 2)
    assert result == [winner, winner], result
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["moderator"], {})
        row = local["training.publication"].browse(winner)
        assert len(row.event_ids) == 2
        row.write({"moderation_reason": "Fictional concurrent moderation"})
        cr.commit()
    race([(saved["moderator"], winner, "publish", ""), (peer, winner, "withdraw", "")])
    with registry.cursor() as cr:
        local = api.Environment(cr, coord, {})
        row = local["training.publication"].browse(winner)
        assert row.state == "withdrawn" and not row._public_row()
        assert len(row.event_ids.filtered(lambda e: e.state == "withdrawn")) == 1
    result = race([(peer, winner, "withdraw", "")] * 2)
    assert result == [winner, winner], result
    print(
        "P14 concurrent invitations, exact consent retries, publication versus withdrawal and duplicate withdrawal OK"
    )
else:
    raise RuntimeError("Unknown P14 fixture phase")
