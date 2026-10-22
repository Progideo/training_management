"""Persistent fictional fixture for a two-process install/update verification.

Run using Odoo shell with TM_UPGRADE_PHASE=prepare or verify, exclusively on a
disposable tm_s01_test_* database. The prepare commit is deliberate: the update
is a separate process and must see persisted records. Never run on development
or production data. This is not addon runtime code.
"""

import json
import os

from odoo import api
from odoo.exceptions import LockError
from odoo.tests import new_test_user
from odoo.tools.translate import load_language


if not env.cr.dbname.startswith("tm_s01_test_"):  # noqa: F821
    raise RuntimeError("Only disposable tm_s01_test_* databases are allowed.")

phase = os.environ["TM_UPGRADE_PHASE"]
snapshot_key = "training_management.test_upgrade_snapshot"
fixture_xmlid = "training_management_test.upgrade_program"
columns = [
    "id",
    "course_id",
    "company_id",
    "version",
    "title",
    "state",
    "objectives",
    "target_audience",
    "prerequisites",
    "content",
    "duration_hours",
    "delivery_mode",
    "language_id",
    "teaching_methods",
    "evaluation_criteria",
    "access_conditions",
    "accessibility_contact_id",
    "accessibility_information",
    "pricing_mode",
    "validated_by_id",
    "validated_at",
    "published_by_id",
    "published_at",
]

if phase == "prepare":
    if env.ref(fixture_xmlid, raise_if_not_found=False):
        raise RuntimeError("Fixture already exists; do not overwrite the baseline.")
    load_language(env.cr, "fr_FR")
    user = new_test_user(
        env,
        login="fictional_upgrade_coordinator",
        groups="training_management.group_training_coordinator",
    )
    contact = env["res.partner"].create({"name": "Fictional Upgrade Contact"})
    course = env["training.course"].with_user(user).create({"name": "Fictional Standard Course"})
    program = (
        env["training.program.version"]
        .with_user(user)
        .create(
            {
                "course_id": course.id,
                "version": "V1",
                "title": "Fictional Standard Programme",
                "objectives": "Preserve the original objectives",
                "target_audience": "Beginners",
                "prerequisites": "None",
                "content": "Fictional content",
                "duration_hours": 7,
                "delivery_mode": "onsite",
                "language_id": env.ref("base.lang_en").id,
                "teaching_methods": "Practice",
                "evaluation_criteria": "Exercise",
                "access_conditions": "Confirmed registration",
                "accessibility_contact_id": contact.id,
                "accessibility_information": "Contact the fictional coordinator.",
            }
        )
    )
    if "training.category" in env and not program.course_id.category_id:
        program.course_id.category_id = env["training.category"].create(
            {
                "name": "Fictional probe category",
                "company_id": program.company_id.id,
            }
        )
    program.action_validate()
    program.action_publish()
    env["ir.model.data"].create(
        {
            "module": "training_management_test",
            "name": "upgrade_program",
            "model": program._name,
            "res_id": program.id,
            "noupdate": True,
        }
    )
    snapshot = json.dumps(program.read(columns), sort_keys=True, default=str)
    env["ir.config_parameter"].set_str(snapshot_key, snapshot)
    env.cr.commit()
    print("UPGRADE_BASELINE_PERSISTED")
elif phase == "verify":
    program = env.ref(fixture_xmlid)
    expected = env["ir.config_parameter"].get_str(snapshot_key)
    actual = json.dumps(program.read(columns), sort_keys=True, default=str)
    assert actual == expected, "The update changed the published programme or its identity."
    french = env["training.program.version"].with_context(lang="fr_FR")
    states = dict(french.fields_get(["state"])["state"]["selection"])
    assert states["draft"] == "Brouillon", states
    assert (
        env.ref("training_management.action_training_courses").with_context(lang="fr_FR").name == "Formations standards"
    )
    print("FRENCH_LABELS_VERIFIED")
    # Verify native locking with two independent transactions. No fixture is
    # modified or committed in this phase.
    with env.registry.cursor() as first_cr, env.registry.cursor() as second_cr:
        user_id = program.validated_by_id.id
        first_env = api.Environment(first_cr, user_id, {})
        second_env = api.Environment(second_cr, user_id, {})
        first_env["training.program.version"].browse(program.id).action_retire()
        try:
            second_env["training.program.version"].browse(program.id).action_retire()
        except LockError:
            print("CONCURRENT_TRANSITION_REFUSED")
        else:
            raise AssertionError("A simultaneous status change was not refused.")
        first_cr.rollback()
        second_cr.rollback()
    env.cr.rollback()
    print("UPGRADE_HISTORY_UNCHANGED")
else:
    raise RuntimeError("TM_UPGRADE_PHASE must be prepare or verify.")
