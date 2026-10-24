"""Account for the single S09.1 fixture proof before capturing the upgrade baseline."""

import hashlib
import json

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S09.2 fixture database only")
key = "training_management_test.s08_snapshot"
before = json.loads(env["ir.config_parameter"].sudo().get_str(key))
dossier = env.ref("training_management_test.s08_dossier")
current = {}
for table, column, value in (
    ("training_closure", "id", dossier.id),
    ("training_proof", "dossier_id", dossier.id),
    ("training_document", "dossier_id", dossier.id),
):
    env.cr.execute(f"SELECT to_jsonb(t) FROM {table} t WHERE {column}=%s ORDER BY id", [value])
    current[table] = [r[0] for r in env.cr.fetchall()]
current["pdf"] = [hashlib.sha256(d.data.content).hexdigest() for d in dossier.output_ids]
for key_name in ("training_closure", "training_document", "pdf"):
    assert current[key_name] == before[key_name], "S09.1 fixture mutated prior closure/document evidence"
assert all(p in current["training_proof"] for p in before["training_proof"])
added = [p for p in current["training_proof"] if p not in before["training_proof"]]
assignment = env.ref("training_management_test.s091_assignment")
assert len(added) == 1
assert added[0]["source"] == "training.evaluation.result:%s; S091-QWEB-1" % assignment.reference_id.id
assert added[0]["category"] == "assessment"
env["ir.config_parameter"].sudo().set_str(key, json.dumps(current, sort_keys=True, default=str))
env.cr.commit()  # Explicit disposable baseline; no upgrade mutation is accepted here.
print("S092_BASELINE_OK: all prior closure/PDF bytes unchanged; exactly the expected S09.1 proof added")
