"""Persistent fictional packages for a two-process update, on an isolated J1 base only."""

import hashlib
import io
import json
import zipfile

from odoo.tests import new_test_user

if not env.cr.dbname.startswith("tm_j1i_"):
    raise RuntimeError("Use an isolated tm_j1i_* database")
params = env["ir.config_parameter"]
key = "training_interactive.j1_snapshot"
expected = params.get_str(key)


def snapshot(resource):
    versions = resource.version_ids.sorted("id")
    files = env["training.elearning.file"].search([("version_id", "in", versions.ids)], order="id")
    return {
        "resource": resource.read(["id", "identifier", "name", "company_id", "format", "active"]),
        "versions": versions.read(
            [
                "id",
                "resource_id",
                "number",
                "sha256",
                "entrypoint",
                "state",
                "license_note",
                "provenance",
                "published_at",
                "published_by_id",
                "withdrawn_at",
                "withdrawn_by_id",
                "withdrawal_reason",
            ]
        ),
        "files": [
            {
                "id": file.id,
                "version": file.version_id.id,
                "path": file.path,
                "sha256": hashlib.sha256(file.data.content).hexdigest(),
            }
            for file in files
        ],
    }


if not expected:
    author = new_test_user(env, login="j1i_fixture_author", groups="training_interactive.group_interactive_author")
    manager = new_test_user(env, login="j1i_fixture_manager", groups="training_interactive.group_interactive_manager")
    resource = (
        env["training.elearning.resource"]
        .with_user(author)
        .create({"name": "Fictional preserved library resource", "format": "scorm12"})
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "imsmanifest.xml",
            """<manifest xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
<metadata><schemaversion>1.2</schemaversion></metadata><resources><resource identifier="sco"
adlcp:scormtype="sco" href="index.html"><file href="index.html"/></resource></resources></manifest>""",
        )
        archive.writestr("index.html", "<p>Fictional preserved bytes</p>")
    versions = env["training.elearning.version"].with_user(author)
    first = versions._import(resource, "1", stream.getvalue(), "Fictional licence", "Fictional source")
    first.action_publish()
    second = versions._import(resource, "2", stream.getvalue(), "Fictional licence", "Fictional source")
    second.action_publish()
    first.with_user(manager)._withdraw("Fictional exceptional withdrawal")
    params.set_str(key, json.dumps({"id": resource.id, "snapshot": snapshot(resource.with_env(env))}, default=str))
    # Deliberate fixture commit: the next process performs a normal module update.
    env.cr.commit()
    print("J1_INTERACTIVE_HISTORY_PREPARED")
else:
    data = json.loads(expected)
    actual = json.loads(json.dumps(snapshot(env["training.elearning.resource"].browse(data["id"])), default=str))
    assert actual == data["snapshot"], "The update changed resource identity, states or package bytes"
    print("J1_INTERACTIVE_IDENTITIES_VERSIONS_BYTES_AND_WITHDRAWAL_PRESERVED")

installed = set(env["ir.module.module"].search([("state", "=", "installed")]).mapped("name"))
if "training_management_elearning" not in installed:
    assert (
        not {
            "training_management",
            "training_management_survey",
            "training_elearning",
            "survey",
            "website_slides",
            "sale_management",
        }
        & installed
    )
    print("J1_INTERACTIVE_WITHOUT_BUSINESS_APPS_CONFIRMED")
