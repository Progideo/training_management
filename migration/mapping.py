"""Validated target policies, independent of private production field names.

A plan is a manual work list, never an ORM payload or permission to migrate.
"""

# Policy: destination, action, qualification required. No arbitrary target fields.
POLICIES = {
    "catalogue": (("training.course", "training.program.version"), "manual", True),
    "delivery": (("training.delivery", "training.program.version"), "manual", True),
    "programme_template": (("training.program.version",), "manual", True),
    "instructors": (
        ("res.partner", "training.session.instructor_id", "training.delivery.evaluation_instructor_ids"),
        "manual",
        True,
    ),
    "description": (("slide.channel.description",), "manual", True),
    "duration": (("training.program.version.duration_hours",), "manual", True),
    "commercial_reference": (("product.product.default_code",), "manual", True),
    "category": (("training.category", "slide.channel.tag"), "manual", True),
    "publication": (
        ("slide.channel.is_published", "slide.channel.visibility", "slide.channel.enroll"),
        "closed_manual",
        True,
    ),
    "exam": (("survey.survey",), "manual", True),
    "survey_purpose": (("survey.survey.survey_type",), "manual", True),
    "survey_context": (("training.delivery",), "manual", True),
    "answer_image": (("survey.question.answer.value_image",), "manual", True),
    "ice": (("res.partner.additional_identifiers.MA_ICE",), "native_contacts", False),
    "partner_projection": (("res.partner",), "reconcile", True),
    "fiscal_identifier": (("res.partner.vat",), "manual", True),
    "analytic_identity": (("account.analytic.plan", "account.analytic.account"), "manual", True),
    "inverse_relation": ((), "reconstruct", True),
    "transient": ((), "exclude_transient", False),
    "legacy_state": ((), "archive", False),
    "historical_result": ((), "archive", False),
    "historical_presence": ((), "archive", False),
    "amount_words": (("account.move.amount_total_words", "res.currency.amount_to_text"), "archive", False),
    "optional_project": (("project.project",), "reserve", False),
    "fiscal_period": (("res.company.fiscalyear_last_day", "res.company.fiscalyear_last_month"), "reserve", False),
    "unqualified": ((), "reserve", False),
}


def inspect_mappings(bundle):
    """Require exact coverage and provenance; return a private, non-executable plan."""
    findings = []
    plan = []

    def fail(code, row=None):
        findings.append({"code": code, "lot": "field_mappings", "row": row})

    def pair(value):
        return isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) and v.strip() for v in value)

    inventory = bundle.get("field_inventory")
    mappings = bundle.get("field_mappings")
    if (
        not isinstance(inventory, dict)
        or not isinstance(inventory.get("fields"), list)
        or not inventory["fields"]
        or any(not pair(p) for p in inventory["fields"])
        or type(inventory.get("expected_count")) is not int
        or inventory["expected_count"] != len(inventory["fields"])
        or not isinstance(mappings, list)
    ):
        fail("field_inventory_invalid")
        return plan, findings
    sources = [tuple(p) for p in inventory["fields"]]
    if len(set(sources)) != len(sources):
        fail("field_inventory_duplicate")
    lots = bundle.get("lots", {})
    identities = {
        (lot, row.get("id"))
        for lot, definition in lots.items()
        if isinstance(definition, dict) and isinstance(definition.get("records"), list)
        for row in definition.get("records", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    seen = set()
    ice_contacts = set()
    for index, mapping in enumerate(mappings):
        if (
            not isinstance(mapping, dict)
            or set(mapping) - {"source", "policy", "records", "archive", "qualification"}
            or not pair(mapping.get("source"))
            or not isinstance(mapping.get("policy"), str)
            or mapping["policy"] not in POLICIES
        ):
            fail("field_mapping_invalid", index)
            continue
        source = tuple(mapping["source"])
        if source in seen:
            fail("field_mapping_duplicate", index)
        seen.add(source)
        targets, action, qualification = POLICIES[mapping["policy"]]
        notes = mapping.get("qualification")
        if qualification and (not isinstance(notes, str) or not notes.strip()):
            fail("field_qualification_missing", index)
        records, archives = mapping.get("records"), mapping.get("archive")
        for refs in (records, archives):
            if not isinstance(refs, list) or any(not pair(r) or tuple(r) not in identities for r in refs):
                fail("field_mapping_reference_unresolved", index)
        if action == "exclude_transient":
            if records != [] or archives != []:
                fail("transient_records_not_migrated", index)
        else:
            # Every persistent source field retains originals, even when no target exists.
            if (
                not archives
                or not isinstance(archives, list)
                or any(not pair(r) or r[0] != "archive" for r in archives)
            ):
                fail("field_originals_archive_missing", index)
            if action not in ("archive", "reserve") and not records:
                fail("field_target_records_missing", index)
        if mapping["policy"] == "ice" and isinstance(records, list):
            for ref in records:
                if pair(ref) and ref[0] == "contacts":
                    ice_contacts.add(ref[1])
                else:
                    fail("ice_contact_mapping_required", index)
        plan.append(
            {
                **mapping,
                "targets": list(targets),
                "action": action,
                "target_validation": "not_executed",
                "execution_authorized": False,
            }
        )
    if seen != set(sources):
        fail("field_inventory_not_covered")
    contacts = lots.get("contacts", {})
    if isinstance(contacts, dict) and isinstance(contacts.get("records"), list):
        for row in contacts["records"]:
            if isinstance(row, dict) and isinstance(row.get("values"), dict):
                if row["values"].get("additional_identifiers") and row.get("id") not in ice_contacts:
                    fail("ice_contact_mapping_required")
    return plan, findings
