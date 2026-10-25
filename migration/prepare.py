"""MIG01–MIG02: inspect a declared extraction, prepare native contacts, never apply it."""

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re

from migration.mapping import inspect_mappings


LOTS = ("contacts", "offers", "sessions", "enrollments", "balances", "supports", "results", "documents", "archive")
METHODS = {"native_import", "manual", "archive", "unknown"}
CONTACT_FIELDS = ("name", "email", "phone", "street", "city", "zip", "vat")
CSV_FIELDS = ("id", *CONTACT_FIELDS, "country_id/id", "parent_id/id", "company_id/id", "active")
XMLID = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_]+\Z")
MONEY = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?\Z")


def cents(value):
    if not isinstance(value, str) or not MONEY.fullmatch(value):
        raise ValueError("Amount must be an exact decimal string with at most two fractional digits")
    whole, _, fraction = value.removeprefix("-").partition(".")
    result = int(whole) * 100 + int(fraction.ljust(2, "0"))
    return -result if value.startswith("-") else result


def money(value):
    return f"{'-' if value < 0 else ''}{abs(value) // 100}.{abs(value) % 100:02d}"


def external_id(system, source_id):
    """Stable identity includes the source instance, not a name/email to merge on."""
    digest = hashlib.sha256(json.dumps([system, source_id], ensure_ascii=False).encode()).hexdigest()
    return "__import__.tm_m01_contact_" + digest


def text(value):
    return isinstance(value, str) and bool(value.strip())


def inspect(bundle, root):
    """Return evidence and findings. No historical values, names or file paths in the report."""
    root = Path(root).resolve()
    findings = []

    def fail(code, lot=None, row=None):
        findings.append({"code": code, "lot": lot, "row": row})

    if not isinstance(bundle, dict):
        raise ValueError("The bundle must be an object")
    if type(bundle.get("schema")) is not int or bundle["schema"] not in (1, 2):
        fail("unsupported_schema")
    if forbidden_keys(bundle):
        fail("credentials_or_permissions_forbidden")
    source = bundle.get("source", {})
    if not isinstance(source, dict) or not all(text(source.get(k)) for k in ("system", "snapshot", "owner")):
        fail("source_provenance_missing")
        source = {}
    lots = bundle.get("lots", {})
    if not isinstance(lots, dict):
        raise ValueError("Lots must be an object")
    if set(lots) != set(LOTS):
        fail("inventory_lots_missing_or_unknown")
    identities = {}
    evidence = {}
    for kind in LOTS:
        lot = lots.get(kind)
        if not isinstance(lot, dict):
            fail("invalid_lot", kind)
            continue
        if not all(text(lot.get(k)) for k in ("owner", "source_model", "target")):
            fail("lot_mapping_or_owner_missing", kind)
        method = lot.get("method")
        if not isinstance(method, str) or method not in METHODS or method == "unknown":
            fail("mapping_unresolved", kind)
        if method == "native_import" and kind != "contacts":
            fail("native_import_not_demonstrated", kind)
        if kind == "contacts" and method == "native_import":
            if lot.get("target") != "res.partner":
                fail("native_contact_target_mismatch", kind)
            company = lot.get("target_company_xmlid")
            if not isinstance(company, str) or not XMLID.fullmatch(company):
                fail("target_company_mapping_missing", kind)
        records = lot.get("records")
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            fail("invalid_records", kind)
            continue
        if type(lot.get("expected_count")) is not int or lot["expected_count"] != len(records):
            fail("source_count_mismatch", kind)
        evidence[kind] = {"count": len(records), "method": method, "target_validation": "not_executed"}
        for index, row in enumerate(records):
            identity = row.get("id")
            if not text(identity):
                fail("source_id_missing", kind, index)
                continue
            if (kind, identity) in identities:
                fail("duplicate_source_id", kind, index)
            identities[kind, identity] = row
            # Never accept credentials or grant portal access through an extraction.
            if forbidden_keys(row):
                fail("credentials_or_permissions_forbidden", kind, index)

    totals = {}
    file_count = 0
    for kind in LOTS:
        lot = lots.get(kind, {})
        if not isinstance(lot, dict) or kind not in evidence:
            continue
        for index, row in enumerate(lot["records"]):
            links = row.get("links", [])
            if not isinstance(links, list):
                fail("invalid_links", kind, index)
                links = []
            for link in links:
                if (
                    not isinstance(link, list)
                    or len(link) != 2
                    or not all(text(v) for v in link)
                    or tuple(link) not in identities
                ):
                    fail("unresolved_link", kind, index)
            if kind == "contacts":
                values = row.get("values", {})
                if not isinstance(values, dict):
                    fail("invalid_contact", kind, index)
                    continue
                if set(values) - {
                    *CONTACT_FIELDS,
                    "is_company",
                    "country_xmlid",
                    "parent_source_id",
                    *(["additional_identifiers"] if bundle.get("schema") == 2 else []),
                }:
                    fail("unsupported_contact_field", kind, index)
                if not text(values.get("name")) or type(values.get("is_company")) is not bool:
                    fail("contact_type_or_name_missing", kind, index)
                if any(
                    not isinstance(v, str)
                    for k, v in values.items()
                    if k not in ("is_company", "additional_identifiers")
                ):
                    fail("invalid_contact_value", kind, index)
                identifiers = values.get("additional_identifiers", {})
                if (
                    not isinstance(identifiers, dict)
                    or set(identifiers) - {"MA_ICE"}
                    or any(not isinstance(v, str) or not re.fullmatch(r"[0-9]{15}", v) for v in identifiers.values())
                    or (identifiers and values.get("country_xmlid") != "base.ma")
                ):
                    fail("contact_identifiers_unresolved", kind, index)
                country = values.get("country_xmlid")
                if country and (not isinstance(country, str) or not XMLID.fullmatch(country)):
                    fail("country_mapping_unresolved", kind, index)
                parent = values.get("parent_source_id")
                has_vat = bool(values.get("vat")) and values.get("vat") not in ("/", "na", "NA")
                if lot.get("method") == "native_import" and values.get("is_company") != (not parent and has_vat):
                    fail("native_company_type_unresolved", kind, index)
                if parent:
                    parent_row = identities.get((kind, parent)) if isinstance(parent, str) else None
                    if (
                        not parent_row
                        or parent == row.get("id")
                        or not isinstance(parent_row.get("values"), dict)
                        or not parent_row["values"].get("is_company")
                        or values.get("is_company")
                    ):
                        fail("contact_parent_unresolved", kind, index)
                    else:
                        parent_values = parent_row["values"]
                        if lot.get("method") == "native_import" and any(
                            values.get(k, {} if k == "additional_identifiers" else "")
                            != parent_values.get(k, {} if k == "additional_identifiers" else "")
                            for k in ("vat", "street", "city", "zip", "country_xmlid", "additional_identifiers")
                        ):
                            fail("native_shared_address_or_vat_conflict", kind, index)
            if kind == "enrollments":
                # Explicit source references; an active orphan always blocks preparation.
                if type(row.get("active")) is not bool:
                    fail("enrollment_state_unknown", kind, index)
                for target, field in (("contacts", "participant"), ("sessions", "session")):
                    identity = row.get(field)
                    if not text(identity) or (target, identity) not in identities:
                        fail("active_orphan" if row.get("active") else "unresolved_enrollment", kind, index)
            if kind == "balances":
                currency = row.get("currency")
                try:
                    amount = cents(row.get("amount"))
                    if currency not in ("MAD", "EUR"):
                        raise ValueError
                    totals[currency] = totals.get(currency, 0) + amount
                except (ValueError, TypeError):
                    fail("balance_or_currency_invalid", kind, index)
            if kind in ("supports", "documents", "archive"):
                try:
                    path = row.get("path")
                    if not text(path) or Path(path).is_absolute() or ".." in Path(path).parts:
                        raise ValueError
                    candidate = root / path
                    if any(p.is_symlink() for p in (candidate, *candidate.parents) if p != root.parent):
                        raise ValueError
                    candidate.resolve().relative_to(root)
                    if not candidate.is_file():
                        raise ValueError
                    digest = hashlib.sha256()
                    with candidate.open("rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(block)
                    if digest.hexdigest() != row.get("sha256"):
                        raise ValueError
                    if not text(row.get("access_owner")) or not text(row.get("retention")):
                        fail("file_access_or_retention_unresolved", kind, index)
                    file_count += 1
                except (OSError, ValueError, RuntimeError):
                    fail("file_missing_unsafe_or_hash_mismatch", kind, index)
            if kind == "results" and not text(row.get("historical_version")):
                fail("historical_version_unknown", kind, index)

    expected_totals = bundle.get("expected_balances")
    try:
        if not isinstance(expected_totals, dict):
            raise ValueError
        declared = {k: cents(v) for k, v in expected_totals.items()}
        if set(declared) - {"MAD", "EUR"}:
            raise ValueError
        if declared != totals:
            fail("balances_not_reconciled")
    except (ValueError, TypeError):
        fail("expected_balances_invalid")

    mapping_plan = []
    if bundle.get("schema") == 2:
        mapping_plan, mapping_findings = inspect_mappings(bundle)
        findings.extend(mapping_findings)
    elif "field_inventory" in bundle or "field_mappings" in bundle:
        fail("field_mapping_requires_schema_2")

    # This records a declared second-person check; it does not authenticate or sign it.
    review = bundle.get("review", {})
    reviewed = False
    if isinstance(review, dict) and text(review.get("reviewer")):
        samples = review.get("samples", [])
        try:
            date.fromisoformat(review.get("date", ""))
            valid_date = True
        except (ValueError, TypeError):
            valid_date = False
        reviewed = (
            review["reviewer"].strip().casefold() != source.get("owner", "").strip().casefold()
            and valid_date
            and text(review.get("notes"))
            and isinstance(samples, list)
            and bool(samples)
            and all(
                isinstance(s, list) and len(s) == 2 and all(text(v) for v in s) and tuple(s) in identities
                for s in samples
            )
        )
        if not reviewed:
            fail("second_person_review_invalid")
    return {
        "schema": 1,
        "status": "blocked" if findings else "prepared" if reviewed else "needs_review",
        "lots": evidence,
        "balances": {k: money(v) for k, v in sorted(totals.items())},
        "verified_files": file_count,
        "findings": findings,
        "second_person_review_declared": reviewed,
        "contact_target_reconciliation": "pending",
        "cutover_authorized": False,
        "field_mapping_count": len(mapping_plan),
        "field_mapping_reserves": sum(p["action"] == "reserve" for p in mapping_plan),
        "field_mapping_validation": "not_executed" if bundle.get("schema") == 2 else "not_declared",
    }


def forbidden_keys(value):
    if isinstance(value, dict):
        return any(
            any(part in key.lower() for part in ("password", "token", "secret", "credential"))
            or key in ("groups", "group_ids", "user_ids", "share")
            or forbidden_keys(item)
            for key, item in value.items()
        )
    return isinstance(value, list) and any(forbidden_keys(item) for item in value)


def contact_columns(bundle):
    return CSV_FIELDS + (("additional_identifiers",) if bundle.get("schema") == 2 else ())


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON key")
        obj[key] = value
    return obj


def contacts_csv(bundle, stream):
    """Native res.partner import: archived contacts, no accounts, no email merge."""
    writer = csv.writer(stream)
    writer.writerow(contact_columns(bundle))
    system = bundle["source"]["system"]
    # Companies first: Odoo can resolve every parent without a second pass.
    for row in sorted(bundle["lots"]["contacts"]["records"], key=lambda r: not r["values"]["is_company"]):
        values = row["values"]
        parent = values.get("parent_source_id")
        writer.writerow(
            [external_id(system, row["id"])]
            + [values.get(k, "") for k in CONTACT_FIELDS]
            + [
                values.get("country_xmlid", ""),
                external_id(system, parent) if parent else "",
                bundle["lots"]["contacts"]["target_company_xmlid"],
                "False",
            ]
            + (
                [json.dumps(values.get("additional_identifiers", {}), sort_keys=True)]
                if bundle.get("schema") == 2
                else []
            )
        )


def reconcile_contacts(bundle, stream):
    """Compare a native export of the imported selection to the exact prepared CSV."""
    if bundle["lots"]["contacts"].get("method") != "native_import":
        return [{"code": "target_reconciliation_requires_native_contacts"}]
    expected = io.StringIO()
    contacts_csv(bundle, expected)
    expected.seek(0)
    wanted = {r["id"]: r for r in csv.DictReader(expected)}
    reader = csv.DictReader(stream)
    if reader.fieldnames != list(contact_columns(bundle)):
        return [{"code": "target_columns_mismatch"}]
    observed = {}
    findings = []
    for row in reader:
        if bundle.get("schema") == 2:
            try:
                # Native export represents an empty JSON field as an empty cell.
                identifiers = json.loads(row["additional_identifiers"] or "{}", object_pairs_hook=unique_object)
                if not isinstance(identifiers, dict):
                    raise ValueError
                row["additional_identifiers"] = json.dumps(identifiers, sort_keys=True)
            except (ValueError, TypeError):
                findings.append({"code": "target_identifiers_invalid"})
        if row["id"] in observed:
            findings.append({"code": "duplicate_target_identity"})
        observed[row["id"]] = row
    if wanted.keys() != observed.keys():
        findings.append({"code": "target_contact_population_mismatch"})
    for key in wanted.keys() & observed.keys():
        if wanted[key] != observed[key]:
            findings.append({"code": "target_contact_values_or_links_mismatch"})
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path, help="New private output directory (must not exist)")
    parser.add_argument("--target-contacts", type=Path, help="Native CSV export of the imported contact selection")
    args = parser.parse_args(argv)

    try:
        raw = args.bundle.read_bytes()
        bundle = json.loads(raw, object_pairs_hook=unique_object)
        report = inspect(bundle, args.bundle.parent)
        if args.target_contacts and report["status"] != "blocked":
            observed = args.target_contacts.read_bytes()
            mismatches = reconcile_contacts(bundle, io.StringIO(observed.decode("utf-8-sig")))
            report["target_contacts_sha256"] = hashlib.sha256(observed).hexdigest()
            report["contact_target_reconciliation"] = "mismatch" if mismatches else "matched"
            report["lots"]["contacts"]["target_validation"] = report["contact_target_reconciliation"]
            report["findings"].extend(mismatches)
            if mismatches:
                report["status"] = "blocked"
        report["source_sha256"] = hashlib.sha256(raw).hexdigest()
        report["prepared_at"] = datetime.now(timezone.utc).isoformat()
        args.output.mkdir(mode=0o700)
        report_file = args.output / "report.json"
        report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        report_file.chmod(0o600)
        if report["status"] != "blocked" and bundle.get("schema") == 2:
            plan, _ = inspect_mappings(bundle)
            destination = args.output / "mapping-plan.json"
            destination.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            destination.chmod(0o600)
        if report["status"] != "blocked" and bundle["lots"]["contacts"]["method"] == "native_import":
            destination = args.output / "contacts.csv"
            with destination.open("w", newline="", encoding="utf-8") as stream:
                contacts_csv(bundle, stream)
            destination.chmod(0o600)
        print(report["status"])
        return 0 if report["status"] == "prepared" else 2
    except (OSError, ValueError, TypeError, KeyError):
        # Do not echo sensitive source values in exception diagnostics.
        parser.exit(1, "Preparation failed: invalid bundle or unavailable output; source not modified.\n")


if __name__ == "__main__":
    raise SystemExit(main())
