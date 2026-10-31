"""Préparation uniquement, exécutée par odoo shell sur la base jetable du lanceur."""

import json
import os

from odoo import Command
from odoo.tests import new_test_user
from odoo.tools.binary import BinaryBytes


def prepare(env):
    assert env.cr.dbname == "tm_suite_test"
    assert not env["res.users"].search_count([("login", "=", "browser_participant")])
    company = env.company
    users = {}
    for role, groups in (
        ("participant", "base.group_portal"),
        ("outsider", "base.group_portal"),
        ("coordinator", "training_management.group_training_coordinator"),
    ):
        users[role] = new_test_user(
            env,
            login=os.environ.get(f"TM_BROWSER_{role.upper()}", f"browser_{role}"),
            password=os.environ["TM_BROWSER_PASSWORD"],
            name=f"Fictional browser {role}",
            email=f"{role}@example.invalid",
            groups=groups,
            company_id=company.id,
            company_ids=[Command.set(company.ids)],
            lang="en_US",
        )
    coordinator = users["coordinator"]

    def model(name):
        return env[name].with_user(coordinator)

    category = model("training.category").create({"name": "Fictional browser category"})
    course = model("training.course").create({"name": "Fictional browser course", "category_id": category.id})
    program = model("training.program.version").create(
        {
            "course_id": course.id,
            "version": "BROWSER-1",
            "title": "Fictional browser programme",
            "objectives": "Practice",
            "target_audience": "Beginners",
            "prerequisites": "None",
            "content": "Exercise",
            "duration_hours": 7,
            "delivery_mode": "elearning",
            "language_id": env.ref("base.lang_en").id,
            "teaching_methods": "Practice",
            "evaluation_criteria": "Submission",
            "access_conditions": "Manual approval",
            "accessibility_contact_id": coordinator.partner_id.id,
            "accessibility_information": "Contact coordination",
        }
    )
    program.action_validate()
    material = model("training.material").create(
        {
            "name": "Fictional private browser PDF",
            "program_id": program.id,
            "filename": "fictional-browser.pdf",
            "data": BinaryBytes(b"%PDF-1.4\nFictional private browser PDF\n%%EOF"),
        }
    )
    delivery = model("training.delivery").create(
        {
            "name": "Fictional browser training",
            "program_id": program.id,
            "kind": "autonomous",
            "access_policy": "duration",
            "access_days": 10,
        }
    )
    activity = model("training.learning.activity").create(
        {"name": "Fictional browser exercise", "delivery_id": delivery.id, "criterion": "submission"}
    )
    enrollment = model("training.enrollment").create(
        {
            "delivery_id": delivery.id,
            "participant_id": users["participant"].partner_id.id,
            "user_id": users["participant"].id,
            "free_reason": "Fictional browser invitation",
        }
    )
    enrollment.action_validate_prerequisites(reason="Fictional review")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Fictional approval")
    enrollment.action_open_access(reason="Fictional opening")
    env["ir.mail_server"].search([]).write({"active": False})
    env["ir.cron"].search([]).write({"active": False})
    values = {
        "ENROLLMENT": enrollment.id,
        "ACTIVITY": activity.id,
        "MATERIAL": material.id,
        "CATEGORY_ACTION": env.ref("training_management.action_training_categories").id,
    }
    env.cr.commit()
    print("BROWSER_FIXTURE=" + json.dumps(values))


prepare(globals()["env"])
