"""Synthetic, persisted S03.1 -> S04 history. Disposable databases only."""

import json
import os

from psycopg2 import sql
from odoo import Command
from odoo.tests import new_test_user

if not env.cr.dbname.startswith("tm_s04_test_"):
    raise RuntimeError("Disposable S04 databases only")
phase = os.environ["S04_PHASE"]
params = env["ir.config_parameter"]
key = "training_management.s04_synthetic_history"


def snapshot(spec):
    result = {}
    for table, (columns, ids) in spec.items():
        env.cr.execute(
            sql.SQL("SELECT {} FROM {} WHERE id = ANY(%s) ORDER BY id").format(
                sql.SQL(",").join(map(sql.Identifier, columns)), sql.Identifier(table)
            ),
            [ids],
        )
        result[table] = env.cr.fetchall()
    return json.dumps(result, sort_keys=True, default=str)


if phase == "prepare":
    if params.get_str(key):
        raise RuntimeError("Do not overwrite history")
    coord = new_test_user(
        env,
        login="fictional_s04_upgrade_coord",
        groups="training_management.group_training_coordinator",
        company_id=env.company.id,
        company_ids=[Command.set(env.company.ids)],
    )
    person = new_test_user(env, login="fictional_s04_upgrade_person", groups="base.group_portal")
    course = env["training.course"].with_user(coord).create({"name": "Fictional S04 historical course"})
    program = (
        env["training.program.version"]
        .with_user(coord)
        .create(
            {
                "course_id": course.id,
                "version": "V1",
                "title": "Fictional S04 historical programme",
                "objectives": "Practice",
                "target_audience": "Beginners",
                "prerequisites": "None",
                "content": "Workshop",
                "duration_hours": 3,
                "delivery_mode": "elearning",
                "language_id": env.ref("base.lang_en").id,
                "teaching_methods": "Exercises",
                "evaluation_criteria": "Review",
                "access_conditions": "Manual",
                "accessibility_contact_id": person.partner_id.id,
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
                "name": "Fictional S04 historical offer",
                "program_id": program.id,
                "kind": "autonomous",
                "capacity": 10,
                "access_policy": "duration",
                "access_days": 30,
            }
        )
    )
    lot = (
        env["training.seat.allocation"]
        .with_user(coord)
        .create(
            {
                "delivery_id": delivery.id,
                "customer_id": person.partner_id.id,
                "quantity": 9,
                "source_reference": "FICT-S04-BASELINE",
                "expires_at": "2028-01-01",
            }
        )
    )
    entry = (
        env["training.enrollment"]
        .with_user(coord)
        .create(
            {
                "delivery_id": delivery.id,
                "participant_id": person.partner_id.id,
                "user_id": person.id,
                "free_reason": "Fictional historical invitation",
            }
        )
    )
    entry.action_validate_prerequisites(reason="Fictional historical review")
    entry.action_confirm()
    entry.action_authorize(reason="Fictional historical authorization")
    entry.action_open_access(reason="Fictional historical opening")
    delivery.action_confirm()
    dated = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional historical dated session",
                "program_id": program.id,
                "kind": "session",
                "start_at": "2027-01-01",
                "end_at": "2027-01-02",
                "access_policy": "duration",
                "access_days": 30,
            }
        )
    )
    dated.action_confirm()
    records = {
        "training.course": course,
        "training.program.version": program,
        "training.delivery": delivery | dated,
        "training.seat.allocation": lot,
        "training.enrollment": entry,
        "training.operation": delivery.operation_ids | dated.operation_ids,
    }
    spec = {}
    env.flush_all()
    for model, rows in records.items():
        table = env[model]._table
        env.cr.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s AND table_schema='public' ORDER BY ordinal_position",
            [table],
        )
        spec[table] = [[item[0] for item in env.cr.fetchall()], rows.ids]
    params.set_str(key, json.dumps(spec))
    params.set_str(key + ".snapshot", snapshot(spec))
    params.set_str(key + ".delivery", str(delivery.id))
    env.cr.commit()  # Test-only persisted fixture, visible after restart/update.
    print("S04_BASELINE_PERSISTED: S03.1 programmes, deliveries, places, admission, active access and audit")
elif phase == "verify":
    assert snapshot(json.loads(params.get_str(key))) == params.get_str(key + ".snapshot"), "Historical columns changed"
    assert not env["training.session"].search_count([]), "No fictitious session on upgrade"
    assert not env["training.adaptation"].search_count([]), "No confidential dossier invented"
    assert not env["training.invitation"].search_count([]), "No invitation on upgrade"
    print("S04_HISTORY_UNCHANGED: all original columns; no automatic session, dossier or invitation")
    env.cr.rollback()
else:
    raise RuntimeError("Unknown phase")
