"""Main -> P01–P06, repeated update and real concurrent operations, fictitious only."""
# ruff: noqa: F821 -- env is supplied by the disposable Odoo shell.

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import hashlib
import json
import os
import threading
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from odoo import api, Command, fields
from odoo.http.retrying import retrying
from odoo.tests import new_test_user
from odoo.tools.binary import BinaryBytes

if env.cr.dbname != "tm_s01_test_p01p06":
    raise RuntimeError("Disposable P01–P06 database only")
phase = os.environ["P01P06_PHASE"]
key = "training_management_test.p01p06_history"


def snapshot(saved):
    program = env["training.program.version"].browse(saved["program"])
    delivery = env["training.delivery"].browse(saved["delivery"])
    enrollment = env["training.enrollment"].browse(saved["enrollment"])
    lead = env["crm.lead"].browse(saved["lead"])
    material = env["training.material"].browse(saved["material"])
    return {
        "program": program.read(["title", "version", "state", "objectives", "content", "pdf_sha256", "published_at"]),
        "pdf": hashlib.sha256(program.pdf_attachment_id.raw.content).hexdigest(),
        "delivery": delivery.read(["name", "state", "reference", "program_id", "access_policy", "access_days"]),
        "enrollment": enrollment.read(["state", "access_state", "participant_id", "user_id"]),
        "lead": lead.read(["name", "training_request_kind", "training_program_id", "training_attendee_count"]),
        "material": material.read(["name", "version", "sha256"]),
        "material_bytes": hashlib.sha256(material.data.content).hexdigest(),
    }


if phase == "baseline":
    coord = new_test_user(env, login="p01p06_history_coord", groups="training_management.group_training_coordinator")
    portal = new_test_user(env, login="p01p06_history_portal", groups="base.group_portal")
    course = env["training.course"].create({"name": "Fictional historical course"})
    course.category_id = env["training.category"].create({"name": "Fictional category"})
    program = (
        env["training.program.version"]
        .with_user(coord)
        .create(
            {
                "course_id": course.id,
                "version": "HISTORY-1",
                "title": "Fictional internal publication",
                "objectives": "Fictional objective",
                "target_audience": "Fictional audience",
                "prerequisites": "None",
                "content": "Fictional content",
                "duration_hours": 7,
                "delivery_mode": "elearning",
                "teaching_methods": "Practice",
                "evaluation_criteria": "Observation",
                "access_conditions": "Manual",
                "accessibility_contact_id": coord.partner_id.id,
                "accessibility_information": "Fictional contact",
            }
        )
    )
    program.action_validate()
    program.action_publish()
    delivery = (
        env["training.delivery"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional history delivery",
                "program_id": program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 10,
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
    lead = env["crm.lead"].create(
        {
            "name": "Fictional historical request",
            "training_request_kind": "group",
            "training_program_id": program.id,
            "training_attendee_count": 4,
        }
    )
    material = (
        env["training.material"]
        .with_user(coord)
        .create(
            {
                "name": "Fictional private support",
                "version": "1",
                "program_id": program.id,
                "data": BinaryBytes(b"%PDF-1.4\nFictional private support"),
                "filename": "private.pdf",
            }
        )
    )
    saved = {
        "program": program.id,
        "delivery": delivery.id,
        "enrollment": enrollment.id,
        "lead": lead.id,
        "material": material.id,
        "coord": coord.id,
        "portal": portal.id,
    }
    saved["snapshot"] = snapshot(saved)
    env["ir.config_parameter"].create({"key": key, "value": json.dumps(saved, default=str)})
    env.cr.commit()  # disposable fixture must survive the separate update process
    print("P01P06_HISTORY_CAPTURED")
elif phase == "verify":
    saved = json.loads(env["ir.config_parameter"].search([("key", "=", key)]).value)
    assert json.loads(json.dumps(snapshot(saved), default=str)) == saved["snapshot"]
    program = env["training.program.version"].browse(saved["program"])
    assert not program.public_catalogue and not program.preview_pdf
    assert not env["training.company.authorization"].search_count([])
    assert not env["training.intra.version"].search_count([])
    assert not env["training.company.service"].with_user(saved["portal"])._rows()
    assert (
        not env["training.document.policy"]
        .with_user(saved["portal"])
        ._can_read(env["training.material"].browse(saved["material"]))
    )
    print("P01P06_HISTORY_PDFS_AND_ACCESS_PRESERVED")
elif phase == "concurrency":
    env.ref("base.EUR").active = True
    saved = json.loads(env["ir.config_parameter"].search([("key", "=", key)]).value)
    coord, portal = env["res.users"].browse(saved["coord"]), env["res.users"].browse(saved["portal"])
    client = env["res.partner"].create({"name": "Fictional concurrent client"})
    allocation = (
        env["training.seat.allocation"]
        .with_user(coord)
        .create(
            {
                "delivery_id": saved["delivery"],
                "customer_id": client.id,
                "quantity": 2,
                "source_reference": "P01P06-CONCURRENT",
                "expires_at": fields.Datetime.add(fields.Datetime.now(), days=2),
            }
        )
    )
    grant = (
        env["training.company.authorization"]
        .with_user(coord)
        .create(
            {
                "company_id": env.company.id,
                "customer_id": client.id,
                "user_id": portal.id,
                "allocation_ids": [Command.set(allocation.ids)],
            }
        )
    )
    grant.action_confirm()
    company_id, allocation_id, portal_id = env.company.id, allocation.id, portal.id
    registry = env.registry
    request_key = uuid4().hex
    values = {
        "contact": "Fictional concurrent requester",
        "email": "concurrent@example.invalid",
        "organisation": "Fictional concurrent client",
        "kind": "group",
        "request_type": "custom",
        "objectives": "Practice",
        "level": "Beginner",
        "count": "2",
        "country": str(env.ref("base.ma").id),
        "mode": "remote",
        "currency": "EUR",
        "dates_flexible": "1",
    }
    env.cr.commit()  # both real connections must see the same fictional grants

    def parallel(operation):
        barrier = threading.Barrier(2)

        def task(index):
            with registry.cursor() as cursor:
                task_env = api.Environment(cursor, portal_id, {})
                task_env.transaction.default_env = task_env
                # Establish both REPEATABLE READ snapshots before either write.
                task_env["res.users"].browse(portal_id).read(["active"])
                barrier.wait(timeout=30)

                def call():
                    if operation == "request":
                        file = FileStorage(
                            stream=BytesIO(b"%PDF-1.4\nFictional concurrent specification"), filename="private.pdf"
                        )
                        return (
                            task_env["crm.lead"]
                            ._submit_public_request(
                                task_env["res.company"].browse(company_id), values, request_key, file
                            )
                            .id
                        )
                    return (
                        task_env["training.company.service"]
                        ._nominate(allocation_id, "Fictional concurrent nominee", "nominee@example.invalid")
                        .id
                    )

                return retrying(call, task_env)

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(task, range(2)))
        assert ids[0] == ids[1], (operation, ids)

    parallel("request")
    parallel("nomination")
    # A cache invalidation does not renew a REPEATABLE READ snapshot.
    # Inspect both committed outcomes through a genuinely new connection.
    with registry.cursor() as verify_cursor:
        verified = api.Environment(verify_cursor, 1, {})
        lead = verified["crm.lead"].search([("training_submission_key", "=", request_key)])
        assert len(lead) == 1
        assert verified["training.request.notice"].search_count([("lead_id", "=", lead.id)]) == 1
        assert verified["ir.attachment"].search_count([("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)]) == 1
        assert verified["training.company.nomination"].search_count([("allocation_id", "=", allocation_id)]) == 1
        assert not verified["training.enrollment"].search_count([("allocation_id", "=", allocation_id)])
    print("P01P06_REAL_CONCURRENT_REQUEST_AND_NOMINATION_IDEMPOTENT")
else:
    raise RuntimeError("Unknown P01–P06 history phase")
