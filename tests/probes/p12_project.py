"""P12 exact history conservation and real concurrent operations; fictitious database only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
import os
import threading
from uuid import uuid4

from psycopg2.errors import SerializationFailure

from odoo import Command, api, fields
from odoo.exceptions import LockError
from odoo.http.retrying import retrying
from odoo.tools import SQL

if env.cr.dbname != "tm_s01_test_p09":
    raise RuntimeError("Disposable P09/P12 history database only")
phase = os.environ["P09_PHASE"]
params = env["ir.config_parameter"]
key = "training_management_test.p12"


def snapshot():
    env.flush_all()
    env.cr.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'training_%' OR tablename LIKE 'survey_%') ORDER BY tablename"
    )
    result = {}
    for (table,) in env.cr.fetchall():
        env.cr.execute(SQL("SELECT to_jsonb(t)::text FROM %s t ORDER BY to_jsonb(t)::text", SQL.identifier(table)))
        result[table] = hashlib.sha256(json.dumps(env.cr.fetchall()).encode()).hexdigest()
    return result


if phase == "project_prepare":
    prior = json.loads(params.get_str("training_management_test.p09"))
    p11 = json.loads(params.get_str("training_management_test.p11"))
    coord = env["res.users"].browse(prior["coord"])
    quality = env["res.users"].browse(p11["quality"])
    portal = env["res.users"].browse(p11["portal"])
    policy = env["training.practice.action"].browse(p11["preserved"]).retention_id
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional P12 delivery",
                "program_id": prior["program"],
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 30,
                "learning_tutor_id": quality.id,
                "evaluation_quality_id": quality.id,
                "evaluation_instructor_ids": [Command.set(quality.partner_id.ids)],
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
                "free_reason": "Fictional P12 invitation",
            }
        )
    )
    enrollment.action_validate_prerequisites(reason="Fictional review")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Fictional permission")
    enrollment.action_open_access(reason="Fictional opening")
    rubric = (
        env["training.project.rubric"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional P12 grid",
                "criterion_ids": [
                    Command.create(
                        {
                            "name": "Accuracy",
                            "level_0": "Absent",
                            "level_1": "Partial",
                            "level_2": "Correct",
                            "level_3": "Explained",
                        }
                    )
                ],
            }
        )
    )
    rubric.action_publish()
    activity = (
        env["training.learning.activity"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional P12 project",
                "delivery_id": delivery.id,
                "criterion": "validation",
                "project_rubric_id": rubric.id,
                "project_deliverable": "Fictional PDF",
                "project_service_reference": "FICT-P12",
                "project_retention_id": policy.id,
            }
        )
    )
    env["training.evaluation.authorization"].with_user(quality).create(
        {
            "delivery_id": delivery.id,
            "user_id": quality.id,
            "purpose": "project",
            "valid_from": fields.Datetime.now() - timedelta(hours=1),
            "valid_until": fields.Datetime.now() + timedelta(days=2),
            "reason": "Fictional P12 mandate",
        }
    )
    work = (
        env["training.learning.service"]
        .with_user(portal)
        ._post(
            enrollment.id,
            "submission",
            activity_id=activity.id,
            request_key=str(uuid4()),
            body="Fictional P12 work",
            data=b"%PDF-1.4\nFictional P12 original\n%%EOF",
            filename="fictional.pdf",
        )
    )
    ratings = {str(c.id): "2" for c in rubric.criterion_ids}
    decision = (
        env["training.learning.service"]
        .with_user(quality)
        ._post(
            enrollment.id,
            "correction",
            activity_id=activity.id,
            request_key=str(uuid4()),
            body="Fictional justified decision",
            parent_id=work.id,
            revision=1,
            decision="changes",
            project_ratings=ratings,
        )
    )
    grid_v2 = env[rubric._name].browse(rubric.action_new_version()["res_id"]).with_user(coord)
    grid_v2.criterion_ids.write({"level_2": "Changed only in V2"})
    grid_v2.action_publish()
    assert decision.project_snapshot["rubric"]["criteria"][0]["levels"][2] == "Correct"
    env.flush_all()
    saved = {
        "coord": coord.id,
        "portal": portal.id,
        "quality": quality.id,
        "enrollment": enrollment.id,
        "activity": activity.id,
        "work": work.id,
        "decision": decision.id,
        "ratings": ratings,
        "snapshot": snapshot(),
        "request": str(uuid4()),
        "data_hash": hashlib.sha256(work.data.content).hexdigest(),
        "decision_digest": decision.project_digest,
        "mail_count": env["training.learning.notice"].search_count([]),
    }
    params.set_str(key, json.dumps(saved))
    env.cr.commit()  # disposable fixture only
    print("P12 grid V1/V2, original, criterion decision and all prior histories baseline OK")
elif phase == "project_verify":
    saved = json.loads(params.get_str(key))
    assert snapshot() == saved["snapshot"], "P12 or earlier histories changed"
    work = env["training.learning.entry"].browse(saved["work"])
    decision = env["training.learning.entry"].browse(saved["decision"])
    assert hashlib.sha256(work.data.content).hexdigest() == saved["data_hash"]
    assert decision.project_digest == saved["decision_digest"]
    assert env["training.learning.notice"].search_count([]) == saved["mail_count"], "Retrospective notice"
    print("P12 exact grids, files, decisions, histories and no retrospective notification OK")
else:
    saved = json.loads(params.get_str(key))
    registry = env.registry
    env.cr.commit()

    def parallel(review):
        barrier = threading.Barrier(2)

        def task(_index):
            with registry.cursor() as cr:
                local = api.Environment(cr, saved["quality"] if review else saved["portal"], {})
                local.transaction.default_env = local
                local["res.users"].browse(local.uid).read(["active"])
                barrier.wait(timeout=30)

                def operation():
                    try:
                        return local["training.learning.service"]._post(
                            saved["enrollment"],
                            "correction" if review else "submission",
                            activity_id=saved["activity"],
                            request_key=saved["request"] if not review else review["key"],
                            body="Fictional concurrent decision" if review else "Fictional concurrent revision",
                            parent_id=review["submission"] if review else saved["work"],
                            revision=3 if review else 2,
                            decision="accepted" if review else False,
                            project_ratings=saved["ratings"] if review else None,
                        )
                    except LockError:
                        return False

                return retrying(operation, local)

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(task, range(2)))

    parallel(False)
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["coord"], {})
        entries = (
            local["training.learning.entry"]
            .sudo()
            .search([("enrollment_id", "=", saved["enrollment"]), ("request_key", "=", saved["request"])])
        )
        assert len(entries) == 1
        submission_id = entries.id
    decision_key = str(uuid4())
    parallel({"key": decision_key, "submission": submission_id})
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["coord"], {})
        decision = (
            local["training.learning.entry"]
            .sudo()
            .search([("enrollment_id", "=", saved["enrollment"]), ("request_key", "=", decision_key)])
        )
        assert len(decision) == 1 and decision.decision == "accepted"
        progress = local["training.learning.service"]._progress(
            local["training.enrollment"].sudo().browse(saved["enrollment"]),
            local["training.learning.activity"].sudo().browse(saved["activity"]),
        )
        assert progress.state == "validated" and progress.revision == 4
        for entry_id in (submission_id, decision.id):
            assert local["training.learning.notice"].search_count([("entry_id", "=", entry_id)]) == 1
        work = local["training.learning.entry"].sudo().browse(saved["work"])
        assert hashlib.sha256(work.data.content).hexdigest() == saved["data_hash"]
    print("P12 concurrent revision and criterion validation: one evidence and one notice per operation OK")

    # A publication which already read criteria cannot publish a stale grid
    # after a different transaction deletes its last criterion.
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["coord"], {})
        draft = local["training.project.rubric"].create(
            {
                "name": "Fictional concurrent grid",
                "criterion_ids": [
                    Command.create(
                        {
                            "name": "Last criterion",
                            "level_0": "Absent",
                            "level_1": "Partial",
                            "level_2": "Correct",
                            "level_3": "Explained",
                        }
                    )
                ],
            }
        )
        draft_id = draft.id
        cr.commit()
    with registry.cursor() as stale_cr:
        stale = api.Environment(stale_cr, saved["coord"], {})
        stale_grid = stale["training.project.rubric"].browse(draft_id)
        assert len(stale_grid.criterion_ids) == 1
        with registry.cursor() as editing_cr:
            editing = api.Environment(editing_cr, saved["coord"], {})
            editing["training.project.rubric"].browse(draft_id).criterion_ids.unlink()
            editing_cr.commit()
        try:
            stale_grid.action_publish()
        except SerializationFailure:
            stale_cr.rollback()
        else:
            raise AssertionError("Stale grid publication was not rejected")
    with registry.cursor() as cr:
        local = api.Environment(cr, saved["coord"], {})
        draft = local["training.project.rubric"].browse(draft_id)
        assert draft.state == "draft" and not draft.criterion_ids
    print("P12 concurrent criterion deletion rejects stale publication; no empty published grid OK")
