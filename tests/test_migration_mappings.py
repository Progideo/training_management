"""Validated mapping policies: no dropped source, arbitrary target or access grant."""

import copy
import csv
import io
import json
import shutil
from pathlib import Path
import tempfile
import unittest

from migration.mapping import POLICIES, inspect_mappings
from migration.prepare import contacts_csv, inspect, main, reconcile_contacts

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "migration/example/qualified-bundle.json"


class MigrationMappings(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(EXAMPLE.read_text())

    def codes(self):
        return {item["code"] for item in inspect(self.bundle, EXAMPLE.parent)["findings"]}

    def mapping(self, policy):
        return next(m for m in self.bundle["field_mappings"] if m["policy"] == policy)

    def test_every_policy_has_provenance_and_a_non_executable_plan(self):
        report = inspect(self.bundle, EXAMPLE.parent)
        self.assertEqual(report["findings"], [])
        plan, findings = inspect_mappings(self.bundle)
        self.assertFalse(findings)
        self.assertEqual({m["policy"] for m in plan}, set(POLICIES))
        self.assertEqual(report["field_mapping_count"], len(POLICIES))
        self.assertTrue(all(not m["execution_authorized"] for m in plan))
        self.assertTrue(all(m["target_validation"] == "not_executed" for m in plan))
        policies = {m["policy"]: m for m in plan}
        self.assertEqual(policies["duration"]["targets"], ["training.program.version.duration_hours"])
        self.assertEqual(policies["publication"]["action"], "closed_manual")
        self.assertEqual(policies["historical_presence"]["action"], "archive")
        self.assertEqual(policies["optional_project"]["action"], "reserve")
        self.assertEqual(policies["transient"]["action"], "exclude_transient")

    def test_missing_extra_duplicate_inventory_or_mapping_blocks(self):
        original = copy.deepcopy(self.bundle)
        for mutation in (
            lambda b: b["field_mappings"].pop(),
            lambda b: b["field_mappings"].append(copy.deepcopy(b["field_mappings"][0])),
            lambda b: b["field_inventory"]["fields"].append(["FICTITIOUS.source", "forgotten"]),
            lambda b: b["field_inventory"]["fields"].append(b["field_inventory"]["fields"][0]),
        ):
            self.bundle = copy.deepcopy(original)
            mutation(self.bundle)
            self.assertTrue(self.codes())

    def test_bad_shapes_never_emit_a_plan_as_valid(self):
        original = copy.deepcopy(self.bundle)
        for key, bad in (("field_inventory", None), ("field_mappings", None), ("field_mappings", [None])):
            self.bundle = copy.deepcopy(original)
            self.bundle[key] = bad
            self.assertTrue(self.codes())
        self.bundle = copy.deepcopy(original)
        self.bundle["lots"]["contacts"]["records"] = None
        self.assertIn("invalid_records", self.codes())

    def test_no_arbitrary_target_or_unknown_policy(self):
        self.mapping("duration")["target"] = "slide.channel.total_time"
        self.assertIn("field_mapping_invalid", self.codes())
        del self.mapping("duration")["target"]
        self.mapping("duration")["policy"] = "copy_legacy"
        self.assertIn("field_mapping_invalid", self.codes())

    def test_original_archive_and_semantic_qualification_required(self):
        self.mapping("fiscal_identifier")["qualification"] = " "
        self.mapping("unqualified")["archive"] = []
        self.mapping("duration")["records"] = [["offers", "absent"]]
        self.assertTrue(
            {"field_qualification_missing", "field_originals_archive_missing", "field_mapping_reference_unresolved"}
            <= self.codes()
        )

    def test_transient_has_no_records_and_inverse_is_not_a_native_import(self):
        self.mapping("transient")["records"] = [["offers", "offer-1"]]
        self.assertIn("transient_records_not_migrated", self.codes())
        self.mapping("inverse_relation")["method"] = "native_import"
        self.assertIn("field_mapping_invalid", self.codes())

    def test_ice_requires_explicit_per_contact_mapping_and_country(self):
        # Both parent and linked contact need provenance before generating their JSON.
        self.assertFalse(self.codes())
        self.mapping("ice")["records"] = []
        self.mapping("ice")["expected_record_count"] = 0
        self.assertIn("ice_contact_mapping_required", self.codes())
        self.bundle["lots"]["contacts"]["records"][0]["values"]["country_xmlid"] = "base.fr"
        self.assertIn("contact_identifiers_unresolved", self.codes())

    def test_unknown_identifiers_bad_shapes_and_parent_conflicts_block(self):
        rows = self.bundle["lots"]["contacts"]["records"]
        original = copy.deepcopy(rows[0]["values"])
        for invalid in ({"MA_RC": "fictional"}, {"MA_ICE": "short"}, {"MA_ICE": 97}, None, []):
            rows[0]["values"] = {**original, "additional_identifiers": invalid}
            self.assertIn("contact_identifiers_unresolved", self.codes())
        rows[0]["values"] = original
        rows[1]["values"]["additional_identifiers"] = {"MA_ICE": "000000000000000"}
        self.assertIn("native_shared_address_or_vat_conflict", self.codes())

    def test_generated_csv_equals_native_fixture_and_json_reconciliation(self):
        output = io.StringIO()
        contacts_csv(self.bundle, output)
        fixture = ROOT / "addons/training_management/tests/data/m01_contacts_identifiers.csv"
        self.assertEqual(output.getvalue(), fixture.read_text().replace("\n", "\r\n"))
        # Empty native JSON export cells and whitespace/key-order differences are semantic.
        rows = list(csv.reader(io.StringIO(output.getvalue())))
        rows[1][-1] = '{ "MA_ICE" : "000000000000097" }'
        rows[3][-1] = ""
        native = io.StringIO()
        csv.writer(native).writerows(rows)
        native.seek(0)
        self.assertEqual(reconcile_contacts(self.bundle, native), [])
        for bad in ('{"MA_ICE":"000000000000097","MA_ICE":"000000000000000"}', "[]", '{"MA_RC":"lost"}'):
            rows[1][-1] = bad
            native = io.StringIO()
            csv.writer(native).writerows(rows)
            native.seek(0)
            self.assertTrue(reconcile_contacts(self.bundle, native))

    def test_schema_1_cannot_silently_ignore_new_mappings(self):
        self.bundle["schema"] = 1
        self.assertIn("field_mapping_requires_schema_2", self.codes())
        self.assertIn("unsupported_contact_field", self.codes())

    def test_cli_private_plan_and_no_output_payload_when_mapping_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "valid"
            self.assertEqual(main([str(EXAMPLE), str(destination)]), 2)  # Second review pending.
            self.assertEqual((destination / "mapping-plan.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(json.loads((destination / "mapping-plan.json").read_text())), len(POLICIES))
            # Copy the synthetic files to keep path/hash checks meaningful.
            shutil.copytree(EXAMPLE.parent / "files", Path(folder) / "files")
            self.mapping("duration")["qualification"] = ""
            source = Path(folder) / "invalid.json"
            source.write_text(json.dumps(self.bundle))
            destination = Path(folder) / "blocked"
            self.assertEqual(main([str(source), str(destination)]), 2)
            self.assertFalse((destination / "contacts.csv").exists())
            self.assertFalse((destination / "mapping-plan.json").exists())

    def test_empty_field_selection_requires_explicit_count_qualification_and_archive(self):
        mapping = self.mapping("answer_image")
        mapping["records"] = []
        self.assertIn("field_record_count_mismatch", self.codes())
        mapping["expected_record_count"] = 0
        mapping["qualification"] = "No source image; metadata and absence check archived, no invented question."
        self.assertFalse(self.codes())
        mapping["qualification"] = ""
        self.assertIn("field_empty_selection_unqualified", self.codes())
        mapping["qualification"] = "Declared absent"
        mapping["archive"] = []
        self.assertIn("field_originals_archive_missing", self.codes())

    def test_field_record_counts_and_duplicate_references_fail_closed(self):
        mapping = self.mapping("duration")
        for invalid in (None, True, -1, "1", 0, 2):
            mapping["expected_record_count"] = invalid
            self.assertIn("field_record_count_mismatch", self.codes())
        mapping["records"] *= 2
        mapping["expected_record_count"] = 2
        self.assertIn("field_record_count_mismatch", self.codes())

    def test_source_without_specific_fields_needs_no_invented_mapping(self):
        self.bundle["field_inventory"] = {"expected_count": 0, "fields": []}
        self.bundle["field_mappings"] = []
        for row in self.bundle["lots"]["contacts"]["records"]:
            row["values"].pop("additional_identifiers", None)
        self.assertFalse(self.codes())
        report = inspect(self.bundle, EXAMPLE.parent)
        self.assertEqual(report["field_mapping_count"], 0)
        self.assertFalse(report["cutover_authorized"])
