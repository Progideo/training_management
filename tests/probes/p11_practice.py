"""P11 preserved private evidence and real concurrent submissions, synthetic only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
import os
import threading

from odoo import api, fields
from odoo.exceptions import LockError
from odoo.http.retrying import retrying
from odoo.tests import new_test_user
from odoo.tools import SQL

if env.cr.dbname != "tm_s01_test_p09":
    raise RuntimeError("Disposable P09/P11 history database only")
phase = os.environ["P09_PHASE"]
params = env["ir.config_parameter"]
key = "training_management_test.p11"


def snapshot():
    env.flush_all()
    env.cr.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'training_%' OR tablename LIKE 'survey_%') ORDER BY tablename"
    )
    tables = [r[0] for r in env.cr.fetchall()]
    result = {}
    for table in tables:
        env.cr.execute(SQL("SELECT to_jsonb(t)::text FROM %s t ORDER BY to_jsonb(t)::text", SQL.identifier(table)))
        result[table] = hashlib.sha256(json.dumps(env.cr.fetchall()).encode()).hexdigest()
    return result


if phase == "practice_prepare":
    prior = json.loads(params.get_str("training_management_test.p09"))
    coord = env["res.users"].browse(prior["coord"])
    portal = env["training.enrollment"].browse(prior["enrollment"]).user_id
    quality = new_test_user(env, login="p11_quality", groups="training_management.group_training_quality")
    policy = (
        env["training.retention.category"]
        .with_user(quality)
        .create(
            {
                "name": "Fictional P11 evidence policy",
                "purpose": "Fictional practice",
                "responsible_id": quality.id,
                "duration_days": 365,
                "archive_policy": "Private",
                "deletion_policy": "Manual review only",
            }
        )
    )
    policy.action_approve()
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional P11 delivery",
                "program_id": prior["program"],
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 1,
                "learning_tutor_id": quality.id,
            }
        )
    )
    enrollment = (
        env["training.enrollment"]
        .with_user(coord)
        .create(
            {
                "delivery_id": delivery.id,
                "participant_id": portal.partner_id.id,
                "user_id": portal.id,
                "free_reason": "Fictional invitation",
            }
        )
    )
    enrollment.action_validate_prerequisites(reason="Fictional review")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Fictional permission")
    enrollment.action_open_access(reason="Fictional opening")
    delivery.action_confirm()
    delivery.action_start()
    delivery.action_deliver()
    actions = env["training.practice.action"].with_user(coord)
    definitions = {
        "enrollment_id": enrollment.id,
        "completed_on": str(fields.Date.today() - timedelta(days=30)),
        "horizon": "30",
        "retention_id": policy.id,
        "service_reference": "Fictional agreement",
        "trainer_feedback": True,
    }
    preserved = actions.create({**definitions, "name": "Fictional preserved action"})
    preserved.with_user(portal).sudo()._submit(
        "participant", "Private preserved P11 note", b"%PDF-1.4\nFictional P11 evidence\n%%EOF", "fictional.pdf"
    )
    preserved.with_user(quality).sudo()._submit("trainer", "Private preserved trainer feedback")
    concurrent = actions.create({**definitions, "name": "Fictional concurrent completion"})
    reminder = actions.create({**definitions, "name": "Fictional concurrent reminder"})
    env.flush_all()
    saved = {
        "coord": coord.id,
        "portal": portal.id,
        "quality": quality.id,
        "preserved": preserved.id,
        "concurrent": concurrent.id,
        "reminder": reminder.id,
        "snapshot": snapshot(),
        "entry": preserved.entry_ids[0].id,
        "file_hash": hashlib.sha256(preserved.entry_ids[0].data.content).hexdigest(),
    }
    params.set_str(key, json.dumps(saved))
    env.cr.commit()  # disposable shell only
    print("P11 private action, proof, feedback and prior histories baseline OK")
elif phase == "practice_verify":
    saved = json.loads(params.get_str(key))
    assert snapshot() == saved["snapshot"], "P11 or earlier history changed after update"
    entry = env["training.practice.entry"].browse(saved["entry"])
    assert hashlib.sha256(entry.data.content).hexdigest() == saved["file_hash"]
    assert not env["training.practice.notice"].search([]), "Update queued retrospective reminders"
    print("P11 exact histories, optional proof, trainer feedback and no retrospective mail OK")
else:
    saved = json.loads(params.get_str(key))
    registry = env.registry
    env.cr.commit()

    def parallel(role):
        barrier = threading.Barrier(2)

        def task(index):
            with registry.cursor() as cr:
                local = api.Environment(cr, saved["portal"] if role == "completion" else saved["coord"], {})
                local.transaction.default_env = local
                local["res.users"].browse(local.uid).read(["active"])
                barrier.wait(timeout=30)

                def operation():
                    try:
                        if role == "completion":
                            return (
                                local["training.practice.action"]
                                .sudo()
                                .browse(saved["concurrent"])
                                ._submit("participant", "Fictional concurrent completion")
                            )
                        action = local["training.practice.action"].sudo().browse(saved["reminder"])
                        action._lock()
                        local["training.practice.notice"]._queue_action(action, 0)
                        return True
                    except LockError:
                        return False

                return retrying(operation, local)

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(task, range(2)))

    completed = parallel("completion")
    assert sum(bool(r) for r in completed) == 1, completed
    parallel("reminder")
    with registry.cursor() as cr:
        verified = api.Environment(cr, saved["coord"], {})
        assert (
            verified["training.practice.entry"].search_count(
                [("action_id", "=", saved["concurrent"]), ("kind", "=", "done")]
            )
            == 1
        )
        notices = verified["training.practice.notice"].search([("action_id", "=", saved["reminder"])])
        assert len(notices) == 1 and notices.mail_id and notices.sudo().mail_id.state == "outgoing"
        preserved = verified["training.practice.entry"].browse(saved["entry"])
        assert hashlib.sha256(preserved.data.content).hexdigest() == saved["file_hash"]
        assert not notices.sudo().mail_id.attachment_ids
    print(
        "P11 real concurrent completion and scheduling: one completion, one native mail, private original preserved OK"
    )
