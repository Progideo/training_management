"""V1 -> P09, exact historical rows, repeated update and real concurrency."""

# ruff: noqa: F821 -- env is supplied by the isolated Odoo shell.
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import threading

from odoo import api
from odoo.exceptions import LockError, ValidationError
from odoo.http.retrying import retrying
from odoo.tests import new_test_user
from odoo.tools import SQL

if env.cr.dbname != "tm_s01_test_p09":
    raise RuntimeError("Disposable P09 history database only")
phase = os.environ["P09_PHASE"]
key = "training_management_test.p09"
params = env["ir.config_parameter"]


def snapshot(tables, *, business=False, database_env=None):
    database_env = database_env or env
    database_env.flush_all()
    result = {}
    for table in tables:
        expression = (
            SQL("to_jsonb(t) - ARRAY['revision','write_date','write_uid']")
            if business and table == "training_delivery"
            else SQL("to_jsonb(t)")
        )
        # P12 only adds nullable opt-in fields to existing S05 rows. Prove
        # they remain NULL before comparing every original column byte-for-byte.
        added = {
            "training_learning_activity": [
                "project_rubric_id",
                "project_deliverable",
                "project_service_reference",
                "project_retention_id",
            ],
            "training_learning_entry": ["project_snapshot", "project_digest"],
        }.get(table, [])
        if added:
            database_env.cr.execute(SQL("SELECT to_jsonb(t) FROM %s t", SQL.identifier(table)))
            for (row,) in database_env.cr.fetchall():
                for column in added:
                    assert row.get(column) is None, (table, row["id"], column)
            expression = SQL("(%s - %s::text[])", expression, added)
        database_env.cr.execute(
            SQL("SELECT (%s)::text FROM %s t ORDER BY (%s)::text", expression, SQL.identifier(table), expression)
        )
        result[table] = hashlib.sha256(json.dumps(database_env.cr.fetchall()).encode()).hexdigest()
    return result


if phase == "baseline":
    coord = new_test_user(env, login="p09_coord", groups="training_management.group_training_coordinator")
    portal = new_test_user(env, login="p09_portal", groups="base.group_portal")
    category = env["training.category"].create({"name": "Fictional path category"})
    course = env["training.course"].create({"name": "Fictional historical course", "category_id": category.id})
    program = env["training.program.version"].create(
        {
            "course_id": course.id,
            "version": "P09-HISTORY",
            "title": "Fictional historical programme",
            "objectives": "Practise",
            "target_audience": "Testers",
            "prerequisites": "None",
            "content": "Exercise",
            "duration_hours": 7,
            "delivery_mode": "remote",
            "language_id": env.ref("base.lang_en").id,
            "teaching_methods": "Practice",
            "evaluation_criteria": "Review",
            "access_conditions": "Manual",
            "accessibility_contact_id": coord.partner_id.id,
            "accessibility_information": "Fictional contact",
        }
    )
    program.action_validate()
    # PR84: preserve an old PDF verbatim even when its source already held HTML.
    formatted = program.copy(
        {
            "version": "Historical HTML",
            "content": "<h3>Historical chapter</h3><ul><li>Topic<ul><li>Detail</li></ul></li></ul>",
        }
    )
    formatted.action_validate()
    formatted_pdf = hashlib.sha256(formatted._reference_pdf().raw).hexdigest()
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional historical delivery",
                "program_id": program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 30,
            }
        )
    )
    activity = (
        env["training.learning.activity"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional historical activity",
                "delivery_id": delivery.id,
                "criterion": "declaration",
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
                "free_reason": "Fictional history",
            }
        )
    )
    enrollment.action_validate_prerequisites(reason="Fictional history")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Fictional history")
    enrollment.action_open_access(reason="Fictional history")
    env["training.learning.service"].with_user(portal)._declare(enrollment.id, activity.id)
    env.flush_all()
    env.cr.execute("""SELECT tablename FROM pg_tables WHERE schemaname='public'
        AND (tablename LIKE 'training_%' OR tablename LIKE 'survey_%')
        ORDER BY tablename""")
    tables = [r[0] for r in env.cr.fetchall()]
    saved = {
        "coord": coord.id,
        "program": program.id,
        "formatted_program": formatted.id,
        "formatted_pdf": formatted_pdf,
        "enrollment": enrollment.id,
        "snapshot": snapshot(tables),
        "business_snapshot": snapshot(tables, business=True),
    }
    params.set_str(key, json.dumps(saved))
    env.cr.commit()  # isolated fixture must survive the separate upgrade process
    print("P09_V1_PROGRESS_AND_HISTORY_CAPTURED")
elif phase == "verify":
    saved = json.loads(params.get_str(key))
    actual = snapshot(saved["snapshot"])
    assert actual == saved["snapshot"], [t for t in actual if actual[t] != saved["snapshot"][t]]
    formatted = env["training.program.version"].browse(saved["formatted_program"])
    original_content = formatted.content
    assert "<h3>Historical chapter</h3>" in formatted.content_formatted
    assert "<ul>" in formatted.content_formatted
    assert formatted.content == original_content
    assert hashlib.sha256(formatted._reference_pdf().raw).hexdigest() == saved["formatted_pdf"]
    assert not env["training.path.assignment"].search_count([])
    print("P09_ALL_V1_TRAINING_SURVEY_ROWS_IDENTICAL")
elif phase == "prepare_path":
    saved = json.loads(params.get_str(key))
    path = env["training.path"].with_user(saved["coord"]).create({"name": "Fictional migrated path"})
    step = (
        env["training.path.step"]
        .with_user(saved["coord"])
        .create(
            {
                "path_id": path.id,
                "program_id": saved["program"],
            }
        )
    )
    path.action_validate()
    ref = (
        env["training.path.assignment"]
        .with_user(saved["coord"])
        .create(
            {
                "step_id": step.id,
                "enrollment_id": saved["enrollment"],
            }
        )
    )
    assert ref.completed and not ref.blocked
    # Another path reuses exactly the same enrollment, without any enrollment copy.
    second = path.copy()
    second.action_validate()
    saved.update(
        second_step=second.step_ids.id,
        path_snapshot=snapshot(
            [
                "training_path",
                "training_path_step",
                "training_path_assignment",
            ]
        ),
    )
    assert snapshot(saved["snapshot"], business=True) == saved["business_snapshot"]
    # The delivery write fence increments its revision during attachment.
    # Capture that authorized technical change before testing the next update.
    saved["snapshot"] = snapshot(saved["snapshot"])
    saved["delivery_revision"] = ref.enrollment_id.delivery_id.revision
    params.set_str(key, json.dumps(saved))
    env.cr.commit()
    print("P09_PATH_REFERENCE_AND_ACQUIS_CAPTURED")
elif phase == "verify_path":
    saved = json.loads(params.get_str(key))
    actual = snapshot(saved["snapshot"])
    assert actual == saved["snapshot"], [t for t in actual if actual[t] != saved["snapshot"][t]]
    formatted = env["training.program.version"].browse(saved["formatted_program"])
    original_content = formatted.content
    assert "<h3>Historical chapter</h3>" in formatted.content_formatted
    assert "<ul>" in formatted.content_formatted
    assert formatted.content == original_content
    assert hashlib.sha256(formatted._reference_pdf().raw).hexdigest() == saved["formatted_pdf"]
    assert snapshot(saved["path_snapshot"]) == saved["path_snapshot"]
    assert env["training.path.assignment"].search([]).completed
    print("P09_PATH_AND_V1_PROGRESS_IDENTICAL_AFTER_UPDATE")
elif phase == "concurrency":
    saved = json.loads(params.get_str(key))
    barrier = threading.Barrier(2)
    registry = env.registry
    env.cr.commit()

    def task(index):
        with registry.cursor() as cursor:
            task_env = api.Environment(cursor, saved["coord"], {})
            task_env.transaction.default_env = task_env
            task_env["res.users"].browse(saved["coord"]).read(["active"])
            barrier.wait(timeout=30)

            def create_reference():
                try:
                    ref = task_env["training.path.assignment"].create(
                        {
                            "step_id": saved["second_step"],
                            "enrollment_id": saved["enrollment"],
                        }
                    )
                    return ref.id
                except (ValidationError, LockError):
                    return False

            return retrying(create_reference, task_env)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(task, range(2)))
    assert sum(bool(r) for r in results) == 1, results
    # A separate connection observes the committed results, outside the shell's
    # earlier REPEATABLE READ snapshot.
    with registry.cursor() as verification_cursor:
        verified = api.Environment(verification_cursor, saved["coord"], {})
        assert verified["training.path.assignment"].search_count([("step_id", "=", saved["second_step"])]) == 1
        assert snapshot(saved["snapshot"], business=True, database_env=verified) == saved["business_snapshot"]
        delivery = verified["training.enrollment"].browse(saved["enrollment"]).delivery_id
        assert delivery.revision == saved["delivery_revision"] + 1
        try:
            verified["training.path.assignment"].create(
                {
                    "step_id": saved["second_step"],
                    "enrollment_id": saved["enrollment"],
                }
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("A replay must not create another path reference")
    print("P09_REAL_CONCURRENT_REFERENCE_SINGLE_SOURCE_NO_DUPLICATE")
elif phase == "portal":
    saved = json.loads(params.get_str(key))
    tables = list(saved["snapshot"]) + list(saved["path_snapshot"])
    before = snapshot(tables)
    enrollment = env["training.enrollment"].browse(saved["enrollment"])
    rows = env["training.path.portal"].with_user(enrollment.user_id)._rows()
    assert len(rows) == 2 and all(r["completed"] == r["total"] == 1 for r in rows)
    assert all(r["steps"][0]["url"] == f"/my/trainings/{enrollment.id}" for r in rows)
    assert snapshot(tables) == before
    print("P09_PORTAL_SHARED_ENROLLMENT_READONLY_HISTORY_IDENTICAL")
else:
    raise RuntimeError("Unknown P09 probe phase")
