"""Offline reprise contract: corruption, missing source, scope and exact native replay inputs."""

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from migration.prepare import CSV_FIELDS, contacts_csv, external_id, inspect, main, reconcile_contacts


EXAMPLE = Path(__file__).resolve().parents[1] / "migration/example/bundle.json"


class MigrationPreparation(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(EXAMPLE.read_text())
        self.root = EXAMPLE.parent

    def findings(self, bundle=None, root=None):
        return {r["code"] for r in inspect(bundle or self.bundle, root or self.root)["findings"]}

    def test_inventory_counts_files_and_separate_currency_reconciliation(self):
        report = inspect(self.bundle, self.root)
        self.assertEqual(report["status"], "needs_review")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["balances"], {"EUR": "120.25", "MAD": "1000.50"})
        self.assertEqual(report["verified_files"], 3)
        self.assertFalse(report["cutover_authorized"])
        self.bundle["expected_balances"]["EUR"] = "1120.75"
        self.assertIn("balances_not_reconciled", self.findings())

    def test_unknown_mapping_missing_inventory_and_duplicate_sources_block(self):
        del self.bundle["lots"]["archive"]
        self.bundle["lots"]["offers"]["method"] = "unknown"
        contacts = self.bundle["lots"]["contacts"]
        contacts["records"].append(copy.deepcopy(contacts["records"][0]))
        self.assertTrue(
            {"inventory_lots_missing_or_unknown", "mapping_unresolved", "duplicate_source_id", "source_count_mismatch"}
            <= self.findings()
        )

    def test_active_orphan_and_guessed_relationship_block(self):
        enrollment = self.bundle["lots"]["enrollments"]["records"][0]
        enrollment["participant"] = "absent"
        enrollment["links"] = [["sessions", "unknown"]]
        self.assertTrue({"active_orphan", "unresolved_link"} <= self.findings())

    def test_credentials_permissions_and_unsupported_contact_values_rejected(self):
        values = self.bundle["lots"]["contacts"]["records"][0]["values"]
        values.update({"password": "not-a-real-secret", "user_ids": [], "email": 123})
        self.assertTrue(
            {"credentials_or_permissions_forbidden", "unsupported_contact_field", "invalid_contact_value"}
            <= self.findings()
        )

    def test_file_hash_traversal_and_symlink_are_rejected(self):
        row = self.bundle["lots"]["documents"]["records"][0]
        row["sha256"] = "0" * 64
        self.assertIn("file_missing_unsafe_or_hash_mismatch", self.findings())
        row["path"] = "../example/files/evidence.txt"
        self.assertIn("file_missing_unsafe_or_hash_mismatch", self.findings())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "evidence.txt").symlink_to(self.root / "files/evidence.txt")
            row["path"] = "evidence.txt"
            self.assertIn("file_missing_unsafe_or_hash_mismatch", self.findings(root=path))

    def test_nonfinite_floating_or_unknown_currency_balances_rejected(self):
        for amount, currency in [("NaN", "EUR"), ("Infinity", "MAD"), (1.2, "EUR"), ("12", "")]:
            with self.subTest(amount=amount):
                self.bundle["lots"]["balances"]["records"][0].update(amount=amount, currency=currency)
                self.assertIn("balance_or_currency_invalid", self.findings())

    def test_historical_version_never_invented(self):
        self.bundle["lots"]["results"]["records"][0]["historical_version"] = None
        self.assertIn("historical_version_unknown", self.findings())

    def test_large_and_negative_amounts_never_round_or_compensate_across_currencies(self):
        large = "123456789012345678901234567890.99"
        self.bundle["lots"]["balances"]["records"] = [
            {"id": "large", "currency": "MAD", "amount": large},
            {"id": "credit", "currency": "MAD", "amount": "-0.01"},
        ]
        self.bundle["lots"]["balances"]["expected_count"] = 2
        expected = "123456789012345678901234567890.98"
        self.bundle["expected_balances"] = {"MAD": expected}
        report = inspect(self.bundle, self.root)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["balances"], {"MAD": expected})
        self.bundle["lots"]["balances"]["records"][0]["amount"] = "0.00x"
        self.assertIn("balance_or_currency_invalid", self.findings())

    def test_present_but_invalid_lot_cannot_pass_as_an_empty_inventory(self):
        self.bundle["lots"]["supports"] = None
        self.assertIn("invalid_lot", self.findings())

    def test_native_computed_type_and_shared_fields_cannot_erase_source_distinctions(self):
        rows = self.bundle["lots"]["contacts"]["records"]
        rows[0]["values"]["vat"] = ""
        rows[1]["values"]["country_xmlid"] = "base.fr"
        self.assertTrue({"native_company_type_unresolved", "native_shared_address_or_vat_conflict"} <= self.findings())

    def test_native_contact_input_is_stable_and_company_scoped_without_accounts(self):
        first, second = io.StringIO(), io.StringIO()
        contacts_csv(self.bundle, first)
        contacts_csv(self.bundle, second)
        self.assertEqual(first.getvalue(), second.getvalue())
        rows = list(csv.DictReader(io.StringIO(first.getvalue())))
        self.assertEqual(list(rows[0]), list(CSV_FIELDS))
        self.assertEqual(rows[1]["parent_id/id"], rows[0]["id"])
        self.assertTrue(all(r["active"] == "False" and r["company_id/id"] == "base.main_company" for r in rows))
        self.assertNotEqual(external_id("source-A", "1"), external_id("source-B", "1"))
        self.assertNotEqual(external_id("source-A", "a/b"), external_id("source-A", "a_b"))
        self.assertNotIn("password", first.getvalue())
        native_fixture = EXAMPLE.parents[2] / "addons/training_management/tests/data/m01_contacts.csv"
        with native_fixture.open(newline="") as stream:
            self.assertEqual(list(csv.reader(stream)), list(csv.reader(io.StringIO(first.getvalue()))))
        self.assertNotIn("is_company", CSV_FIELDS)
        self.bundle["lots"]["contacts"]["target_company_xmlid"] = ""
        self.assertIn("target_company_mapping_missing", self.findings())

    def test_native_target_must_match_the_demonstrated_odoo_model(self):
        self.bundle["lots"]["contacts"]["target"] = "res.users"
        self.assertIn("native_contact_target_mismatch", self.findings())

    def test_missing_method_reports_a_blocking_finding(self):
        del self.bundle["lots"]["contacts"]["method"]
        self.assertEqual(inspect(self.bundle, self.root)["status"], "blocked")
        self.assertIn("mapping_unresolved", self.findings())

    def test_manual_contacts_cannot_claim_native_target_reconciliation(self):
        stream = io.StringIO()
        contacts_csv(self.bundle, stream)
        self.bundle["lots"]["contacts"]["method"] = "manual"
        del self.bundle["lots"]["contacts"]["target_company_xmlid"]
        self.assertEqual(
            reconcile_contacts(self.bundle, io.StringIO(stream.getvalue())),
            [{"code": "target_reconciliation_requires_native_contacts"}],
        )

    def test_parent_country_and_unsupported_native_mapping_fail_closed(self):
        self.bundle["lots"]["contacts"]["records"][1]["values"].update(parent_source_id="unknown", country_xmlid="FR")
        self.bundle["lots"]["balances"]["method"] = "native_import"
        self.assertTrue(
            {"contact_parent_unresolved", "country_mapping_unresolved", "native_import_not_demonstrated"}
            <= self.findings()
        )

    def test_second_person_check_is_distinct_and_references_existing_samples(self):
        self.bundle["review"] = {
            "reviewer": "Reviewer fictif",
            "date": "2026-10-25",
            "notes": "Contrôle fictif",
            "samples": [["contacts", "company-1"], ["balances", "mad-1"]],
        }
        self.assertEqual(inspect(self.bundle, self.root)["status"], "prepared")
        self.bundle["review"]["reviewer"] = self.bundle["source"]["owner"]
        self.assertIn("second_person_review_invalid", self.findings())

    def test_native_target_reconciliation_detects_drift_duplicates_and_missing_rows(self):
        stream = io.StringIO()
        contacts_csv(self.bundle, stream)
        payload = stream.getvalue()
        self.assertEqual(reconcile_contacts(self.bundle, io.StringIO(payload)), [])
        changed = payload.replace("Personne fictive M01", "Valeur différente")
        self.assertEqual(
            reconcile_contacts(self.bundle, io.StringIO(changed))[0]["code"], "target_contact_values_or_links_mismatch"
        )
        missing = "\n".join(payload.splitlines()[:-1]) + "\n"
        self.assertEqual(
            reconcile_contacts(self.bundle, io.StringIO(missing))[0]["code"], "target_contact_population_mismatch"
        )
        duplicate = payload + payload.splitlines()[-1] + "\n"
        self.assertIn(
            "duplicate_target_identity", {r["code"] for r in reconcile_contacts(self.bundle, io.StringIO(duplicate))}
        )

    def test_cli_private_outputs_cannot_overwrite_or_release_blocked_contacts(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "output"
            self.assertEqual(main([str(EXAMPLE), str(output)]), 2)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertEqual((output / "contacts.csv").stat().st_mode & 0o777, 0o600)
            report = (output / "report.json").read_text()
            self.assertNotIn("Personne fictive", report)
            self.assertEqual(len(json.loads(report)["source_sha256"]), 64)
            with self.assertRaises(SystemExit):
                main([str(EXAMPLE), str(output)])
            source = Path(folder) / "bad.json"
            self.bundle["lots"]["contacts"]["method"] = "unknown"
            source.write_text(json.dumps(self.bundle))
            self.assertEqual(main([str(source), str(Path(folder) / "blocked")]), 2)
            self.assertFalse((Path(folder) / "blocked/contacts.csv").exists())
            source.write_text('{"schema":1,"schema":2}')
            with self.assertRaises(SystemExit):
                main([str(source), str(Path(folder) / "duplicate")])

    def test_cli_reconciles_a_utf8_native_export_and_records_its_exact_fingerprint(self):
        stream = io.StringIO()
        contacts_csv(self.bundle, stream)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "native.csv"
            raw = stream.getvalue().encode("utf-8-sig")
            target.write_bytes(raw)
            output = Path(folder) / "checked"
            self.assertEqual(main([str(EXAMPLE), str(output), "--target-contacts", str(target)]), 2)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["contact_target_reconciliation"], "matched")
            self.assertEqual(report["target_contacts_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertFalse(report["second_person_review_declared"])

    def test_native_currency_names_and_fractional_precision_are_preserved_exactly(self):
        self.bundle["lots"]["balances"]["records"] = [
            {"id": "third", "currency": "GBP", "amount": "1.234"},
            {"id": "more", "currency": "GBP", "amount": "0.001"},
            {"id": "custom", "currency": "CUSTOM", "amount": "12"},
        ]
        self.bundle["lots"]["balances"]["expected_count"] = 3
        self.bundle["expected_balances"] = {"GBP": "1.235", "CUSTOM": "12"}
        report = inspect(self.bundle, self.root)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["balances"], {"CUSTOM": "12.00", "GBP": "1.235"})


if __name__ == "__main__":
    unittest.main()
