"""S05.1 -> complement: immutable file, reference and personal grant retained."""

import hashlib
import json
import os

from odoo.tests import new_test_user
from odoo.tools.binary import BinaryBytes

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S05 complement database only")
phase = os.environ["S052_PHASE"]
key = "training_management_test.s052_history"


def remember(name, record):
    env["ir.model.data"].create(
        {"module": "training_management_test", "name": name, "model": record._name, "res_id": record.id}
    )


def snapshot():
    material = env.ref("training_management_test.s052_material")
    enrollment = env.ref("training_management_test.s052_enrollment")
    env.cr.execute("SELECT to_jsonb(t) FROM training_material t WHERE id=%s", [material.id])
    material_row = env.cr.fetchone()[0]
    env.cr.execute(
        "SELECT to_jsonb(t) FROM training_material_assignment t WHERE material_id=%s ORDER BY id", [material.id]
    )
    references = [row[0] for row in env.cr.fetchall()]
    env.cr.execute(
        "SELECT to_jsonb(t) FROM ir_attachment t WHERE res_model='training.material' AND res_id=%s AND res_field='data' ORDER BY id",
        [material.id],
    )
    attachments = [row[0] for row in env.cr.fetchall()]
    state = enrollment.read(
        ["state", "access_start", "access_end", "user_id", "participant_id", "commercially_authorized"]
    )
    return json.dumps(
        {
            "material": material_row,
            "references": references,
            "files": attachments,
            "enrollment": state,
            "bytes": hashlib.sha256(material.data.content).hexdigest(),
        },
        sort_keys=True,
        default=str,
    )


if phase == "prepare":
    coordinator = new_test_user(
        env, login="s052_history_coord", groups="training_management.group_training_coordinator"
    )
    participant = new_test_user(env, login="s052_history_participant", groups="base.group_portal")
    program = env.ref("training_management_test.upgrade_program")
    material = (
        env["training.material"]
        .with_user(coordinator)
        .create(
            {
                "name": "Fictional preserved S05.1 file",
                "program_id": program.id,
                "filename": "history.pdf",
                "data": BinaryBytes(b"%PDF-1.4\nFictional preserved S05.1 file\n%%EOF"),
            }
        )
    )
    delivery = (
        env["training.delivery"]
        .with_user(coordinator)
        .create(
            {
                "name": "Fictional S05.1 delivery",
                "program_id": program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 10,
            }
        )
    )
    enrollment = (
        env["training.enrollment"]
        .with_user(coordinator)
        .create(
            {
                "delivery_id": delivery.id,
                "participant_id": participant.partner_id.id,
                "user_id": participant.id,
                "free_reason": "Fictional controlled upgrade",
            }
        )
    )
    enrollment.action_validate_prerequisites(reason="Fictional review")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Fictional authorization")
    enrollment.action_open_access(reason="Fictional opening")
    remember("s052_material", material)
    remember("s052_enrollment", enrollment)
    remember("s052_coordinator", coordinator)
    remember("s052_participant", participant)
    env["ir.config_parameter"].set_str(key, snapshot())
    env.cr.commit()
    print("S052_BASELINE_PREPARED")
elif phase == "verify":
    assert snapshot() == env["ir.config_parameter"].get_str(key)
    participant = env.ref("training_management_test.s052_participant")
    material = env.ref("training_management_test.s052_material")
    assert env["training.document.policy"].with_user(participant)._can_read(material)
    env.cr.execute(
        "SELECT column_default FROM information_schema.columns WHERE table_name='ir_ui_view' AND column_name='visibility'"
    )
    assert env.cr.fetchone()[0] is None
    assert not env["training.learning.entry"].search([])
    print("S052_FILE_REFERENCE_GRANT_AND_NATIVE_SCHEMA_PRESERVED")
elif phase == "french":
    from odoo import Command
    from odoo.tools.translate import load_language

    load_language(env.cr, "fr_FR")
    env["ir.module.module"]._load_module_terms(["training_management"], ["fr_FR"], overwrite=True)
    french = env.ref("base.lang_fr")
    env["website"].search([]).write({"language_ids": [Command.set(french.ids)], "default_lang_id": french.id})
    env.cr.commit()
    print("S052_FRENCH_WEBSITE_READY")
else:
    raise RuntimeError("Unknown S052 phase")
