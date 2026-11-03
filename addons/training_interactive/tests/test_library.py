"""D09/D21/D32/D36/D38: private versions without a learner application."""

import io
import json
import stat
import zipfile

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.misc import limited_field_access_token
from odoo.tools import mute_logger

from ..services.archive import parse_package

MANIFEST = b"""<manifest xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"><metadata>
<schemaversion>1.2</schemaversion></metadata><resources><resource identifier="sco"
adlcp:scormtype="sco" href="index.html"><file href="index.html"/></resource></resources></manifest>"""


def package(extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in {"imsmanifest.xml": MANIFEST, "index.html": b"<p>Fictional SCO</p>", **(extra or {})}.items():
            archive.writestr(name, data)
    return stream.getvalue()


def h5p_package():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "h5p.json",
            json.dumps(
                {
                    "mainLibrary": "H5P.TrueFalse",
                    "preloadedDependencies": [{"machineName": "H5P.TrueFalse", "majorVersion": 1, "minorVersion": 8}],
                }
            ),
        )
        archive.writestr("content/content.json", json.dumps({"correct": "true", "question": "Fictional question"}))
        archive.writestr(
            "H5P.TrueFalse-1.8/library.json",
            json.dumps(
                {
                    "machineName": "H5P.TrueFalse",
                    "majorVersion": 1,
                    "minorVersion": 8,
                    "preloadedJs": [{"path": "test.js"}],
                }
            ),
        )
        archive.writestr("H5P.TrueFalse-1.8/test.js", "// Fictional runtime, not a player qualification")
    return stream.getvalue()


class LibraryCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_company = cls.env["res.company"].create({"name": "Fictional Library B"})
        cls.author = new_test_user(
            cls.env, login="library_author", groups="training_interactive.group_interactive_author"
        )
        cls.manager = new_test_user(
            cls.env, login="library_manager", groups="training_interactive.group_interactive_manager"
        )
        cls.portal = new_test_user(cls.env, login="library_portal", groups="base.group_portal")
        cls.unassigned = new_test_user(cls.env, login="library_unassigned")
        cls.resource = (
            cls.env["training.elearning.resource"]
            .with_user(cls.author)
            .create({"name": "Fictional shared SCORM", "format": "scorm12"})
        )

    def version(self, number="1"):
        return (
            self.env["training.elearning.version"]
            .with_user(self.author)
            ._import(self.resource, number, package(), "Fictional licence", "Fictional source")
        )


@tagged("post_install", "-at_install")
class TestInteractiveLibrary(LibraryCase):
    def test_no_business_application_dependency_or_permission(self):
        module = self.env["ir.module.module"].search([("name", "=", "training_interactive")])
        self.assertEqual(module.dependencies_id.mapped("name"), ["training_catalog"])
        for model in ("training.enrollment", "slide.channel", "survey.survey"):
            if model in self.env:
                with self.assertRaises(AccessError):
                    self.env[model].with_user(self.author).search([])
        self.assertFalse(self.author.has_group("website.group_website_designer"))
        self.assertFalse(self.author.has_group("base.group_system"))

    def test_native_author_form_and_controlled_import(self):
        with Form(
            self.env["training.elearning.resource"].with_user(self.author), view="training_interactive.resource_form"
        ) as form:
            form.name = "Fictional form resource"
            form.format = "scorm12"
        resource = form.record
        with Form(
            self.env["training.elearning.import"].with_user(self.author), view="training_interactive.import_form"
        ) as form:
            form.resource_id = resource
            form.number = "1"
            form.data = BinaryBytes(package())
            form.license_note = "Fictional"
            form.provenance = "Tests"
        result = form.record.action_import()
        version = self.env[result["res_model"]].browse(result["res_id"]).with_user(self.author)
        self.assertEqual(version.resource_id, resource)
        version.action_publish()
        self.assertEqual(version.published_by_id, self.author)
        self.assertTrue(version.published_at)

    def test_import_guards_and_atomic_rejection(self):
        for name in ("../escape.js", "/absolute", "a/../b", "a\\b", "a//b", "a%2fb", "nested.zip"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_package(package({name: b"bad"}), "scorm12")
        for extra in (
            {"INDEX.HTML": b"collision"},
            {"large.txt": b"a" * 100000},
            {"imsmanifest.xml": b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><x>&x;</x>'},
        ):
            with self.assertRaises(ValueError):
                parse_package(package(extra), "scorm12")
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            info = zipfile.ZipInfo("link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "/etc/passwd")
        with self.assertRaises(ValueError):
            parse_package(stream.getvalue(), "scorm12")
        versions = self.env["training.elearning.version"]
        count = versions.search_count([])
        files = self.env["training.elearning.file"].search_count([])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            versions.with_user(self.author)._import(self.resource, "1", package({"../bad": b"x"}), "Test", "Test")
        self.assertEqual(versions.search_count([]), count)
        self.assertEqual(self.env["training.elearning.file"].search_count([]), files)

    def test_context_cannot_publish_and_duplicate_import_is_atomic(self):
        versions = (
            self.env["training.elearning.version"]
            .with_user(self.author)
            .with_context(
                default_state="published",
                default_published_by_id=self.manager.id,
                default_company_id=self.other_company.id,
            )
        )
        version = versions._import(self.resource, "1", package(), "Fictional", "Tests")
        self.assertEqual(version.state, "draft")
        self.assertFalse(version.published_by_id)
        self.assertEqual(version.company_id, self.resource.company_id)
        files = self.env["training.elearning.file"].search_count([])
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            versions._import(self.resource, "1", package(), "Fictional", "Tests")
        self.assertEqual(self.resource.version_ids, version)
        self.assertEqual(self.env["training.elearning.file"].search_count([]), files)

    def test_only_qualified_h5p_and_single_sco(self):
        resource = (
            self.env["training.elearning.resource"]
            .with_user(self.author)
            .create({"name": "Fictional H5P", "format": "h5p"})
        )
        version = (
            self.env["training.elearning.version"]
            .with_user(self.author)
            ._import(resource, "1", h5p_package(), "Test", "Test")
        )
        self.assertEqual(version.entrypoint, "h5p.json")
        with self.assertRaises(ValueError):
            parse_package(package({"imsmanifest.xml": MANIFEST.replace(b"1.2", b"2004")}), "scorm12")
        with self.assertRaises(ValueError):
            parse_package(
                package(
                    {
                        "imsmanifest.xml": MANIFEST.replace(
                            b"</resources>", b'<resource identifier="other" href="index.html"/></resources>'
                        )
                    }
                ),
                "scorm12",
            )

    def test_author_publication_immutable_versions_and_motivated_withdrawal(self):
        version = self.version()
        version.action_publish()
        version2 = self.version("2")
        version2.action_publish()
        self.assertEqual(version.resource_id.version_ids, version | version2)
        for values in ({"number": "3"}, {"state": "draft"}, {"entrypoint": "other.html"}):
            with self.assertRaises(ValidationError):
                version.write(values)
        with self.assertRaises(ValidationError):
            version.action_publish()
        with self.assertRaises(AccessError):
            version._withdraw("Author must not withdraw")
        version.with_user(self.manager)._withdraw("Fictional security withdrawal")
        self.assertEqual(version.state, "withdrawn")
        self.assertEqual(version.withdrawn_by_id, self.manager)
        self.assertEqual(version2.state, "published")
        with self.assertRaises(ValidationError):
            version.with_user(self.manager)._withdraw("Do not replace original decision")
        with self.assertRaises(ValidationError):
            version.sudo().unlink()

    def test_company_and_actor_refusals(self):
        foreign = self.env["training.elearning.resource"].create(
            {"name": "Other company", "format": "scorm12", "company_id": self.other_company.id}
        )
        for actor in (self.author, self.portal, self.unassigned, self.env.ref("base.public_user")):
            with self.assertRaises(AccessError):
                foreign.with_user(actor).read(["name"])
        # Passing a privileged resource must not smuggle another company's scope.
        with self.assertRaises(AccessError):
            self.env["training.elearning.version"].with_user(self.author)._import(
                foreign.sudo(), "1", package(), "T", "T"
            )
        version = self.version()
        for actor in (self.portal, self.unassigned, self.env.ref("base.public_user")):
            with self.assertRaises(AccessError):
                version.with_user(actor).action_publish()
        self.author.active = False
        with self.assertRaises(AccessError):
            version.action_publish()

    def test_files_and_native_tokens_never_stream(self):
        version = self.version()
        file = self.env["training.elearning.file"].search([("version_id", "=", version.id)], limit=1)
        token = limited_field_access_token(file, "data", scope="binary")
        for actor in (self.author, self.manager, self.portal):
            with self.assertRaises(AccessError):
                file.with_user(actor).read(["data"])
            binary = self.env["ir.binary"].with_user(actor)
            resolved = binary._find_record(res_model=file._name, res_id=file.id, field="data", access_token=token)
            with self.assertRaises(AccessError):
                binary._get_stream_from(resolved, "data")
        with self.assertRaises(AccessError):
            file.sudo().write({"path": "other"})
        with self.assertRaises(AccessError):
            file.sudo().unlink()

    def test_identity_archive_and_snapshot(self):
        version = self.version()
        identifier = self.resource.identifier
        self.resource.write({"name": "Renamed", "active": False})
        self.assertEqual(self.resource.identifier, identifier)
        self.assertEqual(version.resource_id, self.resource)
        with self.assertRaises(ValidationError):
            version.action_publish()
        for values in ({"format": "h5p"}, {"company_id": self.other_company.id}, {"identifier": "replacement"}):
            with self.assertRaises(ValidationError):
                self.resource.write(values)


@tagged("post_install", "-at_install")
class TestInteractiveBinaryHttp(LibraryCase, HttpCase):
    def test_public_native_urls_and_attachment_tokens_are_blocked(self):
        version = self.version()
        file = self.env["training.elearning.file"].search([("version_id", "=", version.id)], limit=1)
        token = limited_field_access_token(file, "data", scope="binary")
        attachment = self.env["ir.attachment"].create(
            {
                "name": "Fictional legacy public file",
                "res_model": file._name,
                "res_id": file.id,
                "raw": BinaryBytes(b"private fixture"),
                "public": True,
            }
        )
        for url in (
            f"/web/content/{file._name}/{file.id}/data?access_token={token}",
            f"/web/image/{file._name}/{file.id}/data?access_token={token}&download=1",
            f"/web/content/{attachment.id}",
        ):
            with self.subTest(url=url):
                response = self.url_open(url)
                self.assertIn(response.status_code, (403, 404))
                self.assertNotIn(b"private fixture", response.content)
