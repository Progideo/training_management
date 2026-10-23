"""Capture the complete S07 fixture before upgrade, including its expected S05 reference."""

import json
import os

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S08 CI database only")
key = "training_management_test.s08_native_view_schema"
env.cr.execute("""SELECT a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
                    FROM pg_attribute a LEFT JOIN pg_attrdef d
                      ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                   WHERE a.attrelid='ir_ui_view'::regclass AND a.attname='visibility'""")
schema = json.dumps(env.cr.fetchone())
if os.environ["S08_PHASE"] == "prepare":
    history_key = "training_management_test.s052_history"
    baseline = json.loads(env["ir.config_parameter"].get_str(history_key))
    material = env.ref("training_management_test.s052_material")
    env.cr.execute(
        "SELECT to_jsonb(t) FROM training_material_assignment t WHERE material_id=%s ORDER BY id", [material.id]
    )
    current = [row[0] for row in env.cr.fetchall()]
    # All original references must still be byte-for-byte equal. The sole added
    # reference comes from the explicit S07 attendance fixture, before upgrade.
    assert all(row in current for row in baseline["references"])
    added = [row for row in current if row not in baseline["references"]]
    delivery = env.ref("training_management_test.s07_presence").session_id.delivery_id
    assert len(added) == 1 and added[0]["delivery_id"] == delivery.id
    # Creating that reference also takes S05's existing write fence. Verify
    # exactly its revision/author/date effects before capturing the full baseline.
    env.cr.execute("SELECT to_jsonb(t) FROM training_material t WHERE id=%s", [material.id])
    current_material = env.cr.fetchone()[0]
    expected_material = dict(
        baseline["material"],
        revision=baseline["material"]["revision"] + 1,
        write_uid=env.ref("training_management_test.s052_coordinator").id,
        write_date=added[0]["create_date"],
    )
    assert current_material == expected_material, "Unexpected S05 mutation during S07 fixture preparation"
    baseline["material"] = current_material
    baseline["references"] = current
    env["ir.config_parameter"].set_str(history_key, json.dumps(baseline, sort_keys=True, default=str))
    env["ir.config_parameter"].set_str(key, schema)
    env.cr.commit()  # Explicit fixture baseline only; never used after upgrade.
    print("S08_BASELINE_OK: original references unchanged; exactly one expected S07 fixture reference added")
else:
    assert schema == env["ir.config_parameter"].get_str(key)
    print("S08_NATIVE_VIEW_SCHEMA_OK: original NOT NULL and SQL default preserved")
