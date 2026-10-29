"""P16 history conservation and real transaction races on synthetic suite DBs."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
import os
import threading
import time
from unittest.mock import patch

from odoo import api, fields
from odoo.exceptions import AccessError, LockError, ValidationError
from odoo.http.retrying import retrying
from odoo.tools import SQL

if env.cr.dbname not in ("tm_s01_test_p09", "tm_suite_test"):
    raise RuntimeError("Disposable P16 fixture database only")
patch.object(type(env["ir.mail_server"]), "send_email", side_effect=AssertionError("No external P16 transport")).start()
phase = os.environ["P09_PHASE"]
params = env["ir.config_parameter"]
key = "training_management_test.p16"


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


def subscribe(local, program_id):
    model = local["training.session.alert.subscription"]
    program = local["training.program.version"].sudo().browse(program_id)
    return model._subscribe(program, accepted=True, definition=model._definition(program))


if phase == "sessions_prepare":
    prior = json.loads(params.get_str("training_management_test.p14"))
    coord = env["res.users"].browse(prior["coord"])
    program = env["training.delivery"].browse(prior["delivery"]).program_id
    program.company_id.training_session_alert_retention_id = prior["policy"]
    sub = subscribe(env(user=prior["users"][0]), program.id)
    now = fields.Datetime.now()
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional private P16 fixture",
                "program_id": program.id,
                "kind": "session",
                "start_at": now + timedelta(days=20),
                "end_at": now + timedelta(days=21),
                "timezone": "Europe/Paris",
                "capacity": 1,
                "access_policy": "duration",
                "access_days": 30,
            }
        )
    )
    delivery.action_publish_session(reason="Fictional publication")
    delivery.action_guarantee_session(reason="Explicit fictional operator commitment")
    notice = env["training.session.alert.notice"].search([("delivery_id", "=", delivery.id)])
    assert len(notice) == 1 and notice.mail_id
    mail = notice.mail_id
    saved = {
        "coord": coord.id,
        "user": sub.owner_id.id,
        "peer": prior["users"][1],
        "program": program.id,
        "delivery": delivery.id,
        "subscription": sub.id,
        "notice": notice.id,
        "mail": {
            "id": mail.id,
            "subject": mail.subject,
            "body": mail.body_html,
            "email": mail.email_to,
            "state": mail.state,
        },
        "snapshot": snapshot(),
    }
    params.set_str(key, json.dumps(saved))
    env.cr.commit()
    print("P16 fictional public decisions, consent and queued alert prepared")
elif phase == "sessions_verify":
    saved = json.loads(params.get_str(key))
    assert snapshot() == saved["snapshot"], "P16 or earlier history/files changed"
    mail = env["mail.mail"].browse(saved["mail"]["id"])
    assert {
        "id": mail.id,
        "subject": mail.subject,
        "body": mail.body_html,
        "email": mail.email_to,
        "state": mail.state,
    } == saved["mail"]
    assert env["training.delivery"].browse(saved["delivery"])._session_public_row()["guaranteed"]
    print("P16 and earlier histories/files/consents/mail exactly preserved")
elif phase == "sessions_concurrency":
    saved = json.loads(params.get_str(key))
    registry = env.registry
    coord, user = saved["coord"], saved["user"]
    original = env["training.delivery"].browse(saved["delivery"])
    second = original.with_user(coord).copy({"name": "Fictional concurrent P16 publication"})
    # No public decisions, history or guarantees are inherited by a new session.
    assert not second.session_public and not second.session_guaranteed and not second.session_first_published_at
    candidates = []
    for user_id in (user, saved["peer"]):
        learner = env["res.users"].browse(user_id)
        enrollment = (
            env["training.enrollment"]
            .with_user(coord)
            .create(
                {
                    "delivery_id": second.id,
                    "participant_id": learner.partner_id.id,
                    "user_id": user_id,
                    "free_reason": "Fictional P16 last-seat race",
                }
            )
        )
        enrollment.action_validate_prerequisites(reason="Fictional review")
        candidates.append(enrollment.id)
    subscribe(env(user=saved["peer"]), saved["program"])._unsubscribe()
    env.cr.commit()

    def race(operations):
        barrier = threading.Barrier(2)

        def task(operation):
            actor, kind, record_id = operation
            with registry.cursor() as cr:
                local = api.Environment(cr, actor, {})
                local.transaction.default_env = local
                local["res.users"].browse(actor).read(["active"])
                barrier.wait(timeout=30)

                def action():
                    if kind == "subscribe":
                        return subscribe(local, saved["program"]).id
                    if kind == "publish":
                        local["training.delivery"].browse(record_id).action_publish_session(
                            reason="Fictional concurrent publication"
                        )
                    elif kind == "unsubscribe":
                        local["training.session.alert.subscription"].sudo().browse(record_id)._unsubscribe()
                    elif kind == "admit":
                        local["training.enrollment"].browse(record_id).action_confirm()
                    else:
                        local["mail.mail"].sudo().browse(record_id)._prepare_outgoing_list()
                    return record_id

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

    result = race([(saved["peer"], "subscribe", 0)] * 2)
    assert result[0] and result[0] == result[1], result
    result = race([(coord, "publish", second.id)] * 2)
    assert result == [second.id, second.id], result
    result = race([(coord, "admit", row_id) for row_id in candidates])
    assert sum(bool(row_id) for row_id in result) == 1, result
    race([(user, "unsubscribe", saved["subscription"]), (coord, "transport", saved["mail"]["id"])])
    result = race([(user, "unsubscribe", saved["subscription"])] * 2)
    assert result == [saved["subscription"], saved["subscription"]], result
    with registry.cursor() as cr:
        local = api.Environment(cr, coord, {})
        sub = local["training.session.alert.subscription"].browse(saved["subscription"])
        assert not sub.active_consent
        assert (
            local["training.session.alert.event"].search_count(
                [("subscription_id", "=", sub.id), ("operation", "=", "unsubscribe")]
            )
            == 1
        )
        notices = local["training.session.alert.notice"].search([("delivery_id", "=", second.id)])
        assert len(notices) == 2 and len(notices.mail_id) == 2
        assert not local["training.session.alert.notice"].browse(saved["notice"])._authorized()
        delivery = local["training.delivery"].browse(second.id)
        assert delivery._occupancy() == 1 and delivery._session_public_row()["status"] == "full"
        assert not delivery.session_guaranteed
    print("P16 concurrent opt-ins/publications/last-place/opt-out versus transport/double opt-out OK")
else:
    raise RuntimeError("Unknown P16 fixture phase")
