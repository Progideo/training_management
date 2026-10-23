"""Synthetic S04 -> categories/PDF history and real concurrent transactions."""

import hashlib
import json
import os
from pathlib import Path
import runpy

from odoo import api
from odoo.exceptions import LockError, ValidationError
from odoo.tests import new_test_user
from odoo.tools import file_path

if not env.cr.dbname.startswith("tm_catpdf_test"):
    raise RuntimeError("Only disposable catalogue/PDF databases are allowed")
phase = os.environ["CATALOGUE_PHASE"]
params = env["ir.config_parameter"]
key = "training_management.catalogue_pdf_probe"
columns = ["id", "course_id", "version", "title", "objectives", "content", "state", "validated_at", "published_at"]
new_view_names = ("view_training_category_list", "view_training_category_form", "programme_pdf_document")


def visibility_default():
    env.cr.execute(
        """SELECT pg_get_expr(d.adbin, d.adrelid)
             FROM pg_attribute a
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = 'ir_ui_view'::regclass
              AND a.attname = 'visibility' AND NOT a.attisdropped"""
    )
    return env.cr.fetchone()


if phase == "prepare":
    # Prove this is a direct S04 upgrade, with no catalogue/PDF placeholders.
    for name in new_view_names:
        assert not env.ref("training_management." + name, raise_if_not_found=False)
    default_before = visibility_default()
    visibility_before = []
    if default_before is not None:
        env.cr.execute("SELECT id, visibility FROM ir_ui_view ORDER BY id")
        visibility_before = env.cr.fetchall()
    coordinator = new_test_user(
        env, login="catpdf_coordinator", groups="training_management.group_training_coordinator"
    )
    contact = env["res.partner"].create({"name": "Fictional accessibility desk"})
    course = env["training.course"].with_user(coordinator).create({"name": "Fictional historical programme"})
    program = (
        env["training.program.version"]
        .with_user(coordinator)
        .create(
            {
                "course_id": course.id,
                "version": "V1",
                "title": "Fictional programme V1",
                "objectives": "Apply a method",
                "target_audience": "Professionals",
                "prerequisites": "None",
                "content": "Learn and practise",
                "duration_hours": 7,
                "delivery_mode": "remote",
                "language_id": env.ref("base.lang_en").id,
                "teaching_methods": "Exercises",
                "evaluation_criteria": "Review",
                "access_conditions": "On registration",
                "accessibility_contact_id": contact.id,
                "accessibility_information": "accessibility@example.invalid",
            }
        )
    )
    program.action_validate()
    program.action_publish()
    existing = env["ir.attachment"].create(
        {
            "name": "Fictional existing commercial document.txt",
            "raw": b"Preserved historical document",
            "res_model": program._name,
            "res_id": program.id,
        }
    )
    delivery = (
        env["training.delivery"]
        .with_user(coordinator)
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
    params.set_str(
        key,
        json.dumps(
            {
                "program": program.id,
                "coordinator": coordinator.id,
                "attachment": existing.id,
                "delivery": delivery.id,
                "snapshot": program.read(columns),
                "visibility_default": default_before,
                "view_visibility": visibility_before,
            },
            default=str,
        ),
    )
    env.cr.commit()  # Test-only persisted fixture across process/version changes.
    print("S04_PROGRAMME_WITHOUT_CATEGORY_OR_REFERENCE_PDF_PERSISTED")
elif phase == "verify":
    spec = json.loads(params.get_str(key))
    default_after = visibility_default()
    assert (list(default_after) if default_after is not None else None) == spec["visibility_default"]
    env.cr.execute("SELECT to_regclass('pg_temp.training_pdf_visibility_default_restore')")
    assert env.cr.fetchone()[0] is None
    if spec["view_visibility"]:
        ids = [row[0] for row in spec["view_visibility"]]
        env.cr.execute("SELECT id, visibility FROM ir_ui_view WHERE id = ANY(%s) ORDER BY id", [ids])
        assert [list(row) for row in env.cr.fetchall()] == spec["view_visibility"]
    for name in new_view_names:
        assert env.ref("training_management." + name).arch_db
    print("DIRECT_S04_UPGRADE_NO_VIEW_PREPARATION_SCHEMA_AND_VISIBILITY_PRESERVED")
    program = env["training.program.version"].with_user(spec["coordinator"]).browse(spec["program"])
    assert json.loads(json.dumps(program.read(columns), default=str)) == spec["snapshot"]
    assert program.pdf_legacy and not program.pdf_attachment_id and not program.category_id
    assert bytes(env["ir.attachment"].browse(spec["attachment"]).raw) == b"Preserved historical document"
    assert env["training.delivery"].browse(spec["delivery"]).program_id == program
    try:
        program.action_download_pdf()
    except ValidationError:
        pass
    else:
        raise AssertionError("No historical PDF should have been invented")
    program.action_reconstruct_pdf()
    original = bytes(program._reference_pdf().raw)
    program.action_reconstruct_pdf()
    assert bytes(program._reference_pdf().raw) == original and program.pdf_reconstructed
    env["res.lang"]._activate_lang("fr_FR")
    env["ir.module.module"]._load_module_terms(["training_management"], ["fr_FR"])
    program.course_id.category_id = env["training.category"].create(
        {"name": "Gestion de projet", "company_id": program.company_id.id}
    )
    new = program.with_context(lang="fr_FR").copy(
        {
            "version": "V2",
            "title": "Gestion de projet — programme détaillé",
            "language_id": env.ref("base.lang_fr").id,
            "content": "\n".join(f"Séquence {i} : étude de cas, échanges et mise en pratique." for i in range(1, 81)),
        }
    )
    assert not new.pdf_attachment_id and not new.pdf_legacy
    new.action_validate()
    new.action_publish()
    race = new.copy({"version": "V3"})
    proofs = Path(os.environ["CATALOGUE_PDF_PROOFS"])
    proofs.mkdir(parents=True, exist_ok=True)
    (proofs / "programme-fr.pdf").write_bytes(bytes(new._reference_pdf().raw))
    (proofs / "programme-historique.pdf").write_bytes(original)
    spec.update(
        {"new": new.id, "race": race.id, "sha": new.pdf_sha256, "old_sha": hashlib.sha256(original).hexdigest()}
    )
    params.set_str(key, json.dumps(spec))
    env.cr.commit()  # Test-only fixtures reused after a second module update.
    print("HISTORY_PRESERVED_RECONSTRUCTION_DATED_AND_FRENCH_PDF_PERSISTED")
elif phase == "repeat":
    spec = json.loads(params.get_str(key))
    for record_id, sha in ((spec["new"], spec["sha"]), (spec["program"], spec["old_sha"])):
        program = env["training.program.version"].browse(record_id)
        assert hashlib.sha256(program._reference_pdf().raw).hexdigest() == sha
    default = visibility_default()
    assert (list(default) if default is not None else None) == spec["visibility_default"]
    if default is not None:
        migrate = runpy.run_path(file_path("training_management/migrations/20.0.1.4.0/pre-migration.py"))["migrate"]

        class InterruptedUpgrade(Exception):
            pass

        # Failure must roll back the temporary schema change too. A custom SQL
        # default must remain untouched rather than being replaced or dropped.
        for custom_default in (False, True):
            try:
                with env.cr.savepoint():
                    if custom_default:
                        env.cr.execute("ALTER TABLE ir_ui_view ALTER COLUMN visibility SET DEFAULT 'connected'")
                    before = visibility_default()
                    migrate(env.cr, "20.0.1.3.2")
                    if custom_default:
                        assert visibility_default() == before
                    else:
                        assert visibility_default()[0] is not None
                    raise InterruptedUpgrade()
            except InterruptedUpgrade:
                pass
            assert visibility_default() == default
            env.cr.execute("SELECT to_regclass('pg_temp.training_pdf_visibility_default_restore')")
            assert env.cr.fetchone()[0] is None
        print("MIGRATION_FAILURE_ROLLBACK_AND_CUSTOM_SQL_DEFAULT_PRESERVED")
    print("REFERENCE_PDF_BYTES_UNCHANGED_AFTER_REPEATED_UPGRADE")
elif phase == "concurrency":
    spec = json.loads(params.get_str(key))
    with env.registry.cursor() as cr1, env.registry.cursor() as cr2:
        e1 = api.Environment(cr1, spec["coordinator"], {})
        e2 = api.Environment(cr2, spec["coordinator"], {})
        first = e1["training.program.version"].browse(spec["race"])
        second = e2["training.program.version"].browse(spec["race"])
        first.action_validate()
        try:
            second.action_validate()
        except LockError:
            cr2.rollback()
        else:
            raise AssertionError("Simultaneous validation was not refused")
        sha = first.pdf_sha256
        cr1.commit()  # Test-only: let the refused transaction retry committed state.
    # A real request retry starts a new transaction/snapshot.
    with env.registry.cursor() as retry:
        current = api.Environment(retry, spec["coordinator"], {})
        second = current["training.program.version"].browse(spec["race"])
        second.action_validate()
        assert second.pdf_sha256 == sha
        assert current["ir.attachment"].sudo().search_count([("training_program_id", "=", second.id)]) == 1
        retry.rollback()
    print("CONCURRENT_VALIDATION_REFUSED_RETRY_REUSES_SINGLE_PDF")
else:
    raise RuntimeError("Unknown probe phase")
