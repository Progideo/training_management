"""Real competing cursors: diffusion and stale edits of one native PDF file."""

from uuid import uuid4

from psycopg2.errors import SerializationFailure
from odoo import api
from odoo.exceptions import LockError, ValidationError
from odoo.tests import new_test_user
from odoo.tools.binary import BinaryBytes

if not env.cr.dbname.startswith("tm_s01_test_s021_s05"):
    raise RuntimeError("Disposable S05 test databases only")
suffix = uuid4().hex[:8]
coord = new_test_user(env, login="s05_race_" + suffix, groups="training_management.group_training_coordinator")
program = env.ref("training_management_test.upgrade_program")
pdf = b"%PDF-1.4\nFictional concurrency proof\n%%EOF"
material = (
    env["training.material"]
    .with_user(coord)
    .create(
        {
            "name": "Fictional S05 race",
            "program_id": program.id,
            "filename": "race.pdf",
            "data": BinaryBytes(pdf),
        }
    )
)
env.cr.commit()  # Synthetic fixtures, explicitly disposable database only.
context = {"allowed_company_ids": program.company_id.ids}
with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [
        api.Environment(cursor, coord.id, context)["training.material"].browse(material.id)
        for cursor in (first, second)
    ]
    assert not one.frozen_at and not two.frozen_at
    one._freeze()
    try:
        two.write({"data": BinaryBytes(pdf + b"altered")})
    except LockError:
        pass
    else:
        raise AssertionError("A held diffusion lock must reject the competing file edit")
    first.commit()
    try:
        two.write({"data": BinaryBytes(pdf + b"altered")})
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("A stale file edit must fail after concurrent diffusion")
with env.registry.cursor() as retry:
    current = api.Environment(retry, coord.id, context)["training.material"].browse(material.id)
    try:
        current.write({"data": BinaryBytes(pdf + b"altered")})
    except ValidationError:
        retry.rollback()
    else:
        raise AssertionError("A fresh retry must preserve the distributed version")
    assert current.data.content == pdf
    attachments = (
        current.env["ir.attachment"]
        .sudo()
        .search(
            [
                ("res_model", "=", "training.material"),
                ("res_id", "=", material.id),
                ("res_field", "=", "data"),
            ]
        )
    )
    assert len(attachments) == 1 and not attachments.public and not attachments.access_token
print("S05_CONCURRENCY_OK: held lock, stale edit, fresh refusal and one preserved file")
