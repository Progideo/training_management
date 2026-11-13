"""The common reader runs without TM; capabilities remain actor/company/version scoped."""

import json
import re

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged

from .test_library import LibraryCase


@tagged("post_install", "-at_install")
class TestSharedReaders(LibraryCase, HttpCase):
    def setUp(self):
        super().setUp()
        self.portal_origin = "http://127.0.0.1:%s" % self.http_port()
        self.content_origin = "http://localhost:%s" % self.http_port()
        params = self.env["ir.config_parameter"]
        params.set_str("training_elearning.portal_origin", self.portal_origin)
        params.set_str("training_elearning.content_origin", self.content_origin)

    def preview(self):
        version = self.version()
        self.env.flush_all()
        self.authenticate(self.author.login, self.author.login)
        page = self.url_open("/training/interactive/preview/%s" % version.id)
        self.assertEqual(page.status_code, 200)
        cfg = json.loads(re.search(r'<script id="config" type="application/json">(.*?)</script>', page.text).group(1))
        source = re.search(r'<iframe[^>]+src="([^"]+)"', page.text).group(1)
        return version, cfg, source

    def test_preview_files_and_runtime_without_business_context(self):
        version, cfg, source = self.preview()
        self.assertIsNone(cfg["attempt"])
        self.assertIsNone(cfg["save"])
        self.assertIn(
            "/training_interactive/static/src/parent.js",
            self.url_open("/training/interactive/preview/%s" % version.id).text,
        )
        launch = self.url_open(source)
        self.assertEqual(launch.status_code, 200)
        self.assertEqual(launch.headers["Cache-Control"], "no-store")
        self.assertIn("media-src 'none'", launch.headers["Content-Security-Policy"])
        root = source.removesuffix("/launch")
        for suffix in ("/file/index.html", "/runner.js", "/vendor/scorm12.min.js"):
            response = self.url_open(root + suffix)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertNotIn("session_id=", response.headers.get("Set-Cookie", ""))
        self.assertEqual(self.url_open(root + "/file/unknown.html").status_code, 404)
        version.with_user(self.manager)._withdraw("Fictional withdrawal")
        self.env.flush_all()
        self.assertEqual(self.url_open(source).status_code, 403)

    def test_content_host_refuses_native_routes(self):
        for path in ("/", "/web/login", "/my", "/web/image/res.partner/1/avatar_128", "/missing"):
            response = self.url_open(self.content_origin + path, allow_redirects=False)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.url_open(self.portal_origin + "/web/login").status_code, 200)

    def test_preview_capability_cannot_bind_an_unknown_context(self):
        version = self.version()
        with self.assertRaises(AccessError):
            self.env["training.elearning.lease"].with_user(self.author)._issue(version, object())

    def test_preview_renewal_belongs_to_its_actor(self):
        version, cfg, source = self.preview()
        self.assertEqual(
            self.url_open(cfg["renew"], data={"csrf_token": cfg["csrf"], "lease": cfg["lease"]}).status_code, 200
        )
        self.authenticate(self.manager.login, self.manager.login)
        page = self.url_open("/training/interactive/preview/%s" % version.id)
        own = json.loads(re.search(r'<script id="config" type="application/json">(.*?)</script>', page.text).group(1))
        self.assertEqual(
            self.url_open(cfg["renew"], data={"csrf_token": own["csrf"], "lease": cfg["lease"]}).status_code, 403
        )
