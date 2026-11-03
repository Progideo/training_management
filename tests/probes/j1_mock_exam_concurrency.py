"""Real concurrent native transactions on an isolated fictional engine fixture."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import threading

from odoo import api, fields
from odoo.exceptions import LockError
from odoo.http.retrying import retrying

if not env.cr.dbname.startswith("tm_j1m_"):
    raise RuntimeError("Use an isolated tm_j1m_* database")
spec = json.loads(env["ir.config_parameter"].get_str("training_mock_exam.j1_runtime_snapshot"))
registry = env.registry
barrier = threading.Barrier(2)
env.cr.commit()


def launch(index):
    with registry.cursor() as cursor:
        task_env = api.Environment(cursor, spec["learner"], {})
        task_env.transaction.default_env = task_env
        barrier.wait(timeout=30)

        def checked_launch():
            try:
                with cursor.savepoint():
                    return (
                        task_env["training.mock.exam.service"]
                        ._start_native(task_env["survey.survey"].sudo().browse(spec["exam"]), "test.concurrent:1", {})
                        .id
                    )
            except LockError:
                return False  # The HTTP layer retries a busy request; it never creates a second attempt.

        return retrying(checked_launch, task_env)


with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(launch, range(2)))
assert len({item for item in results if item}) == 1, results
with registry.cursor() as cursor:
    checked_env = api.Environment(cursor, spec["learner"], {})
    inputs = checked_env["survey.user_input"].sudo()
    concurrent = inputs.search([("mock_context_key", "=", "test.concurrent:1")])
    assert len(concurrent) == 1 and concurrent.id in results
    different = checked_env["training.mock.exam.service"]._start_native(
        checked_env["survey.survey"].sudo().browse(spec["exam"]), "test.concurrent:2", {}
    )
    assert concurrent != different and not different.user_input_line_ids
    concurrent._training_store({"deadline": fields.Datetime.now() - timedelta(seconds=1)})
    ids = concurrent.id, different.id
    cursor.commit()
print("J1_MOCK_CONCURRENT_LAUNCHES_ONE_ATTEMPT_PER_CONTEXT_CONFIRMED")

barrier = threading.Barrier(2)


def close(index):
    with registry.cursor() as cursor:
        task_env = api.Environment(cursor, spec["learner"], {})
        task_env.transaction.default_env = task_env
        barrier.wait(timeout=30)

        def checked_close():
            try:
                with cursor.savepoint():
                    if index:
                        task_env["survey.user_input"]._cron_mock_expire()
                    else:
                        task_env["survey.user_input"].sudo().browse(ids[0])._mock_close_if_expired()
            except LockError:
                pass

        retrying(checked_close, task_env)


with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(close, range(2)))
with registry.cursor() as cursor:
    checked_env = api.Environment(cursor, spec["learner"], {})
    first, other = [checked_env["survey.user_input"].sudo().browse(i) for i in ids]
    assert first.state == "done" and first.end_datetime == first.deadline
    assert other.state == "in_progress" and not other.user_input_line_ids
    completed = checked_env["survey.user_input"].sudo().browse(spec["ids"][0])
    assert completed.state == "done" and completed.scoring_percentage == 100
print("J1_MOCK_CONCURRENT_CRON_AND_REQUEST_CLOSE_AT_DEADLINE_WITHOUT_CONTEXT_LEAK_CONFIRMED")
