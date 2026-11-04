"""General pages work with the catalogue alone; public ORM grants stay closed."""

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from .test_catalog import SharedCatalogCase


@tagged("post_install", "-at_install")
class TestGeneralCatalogue(SharedCatalogCase, HttpCase):
    def test_explicit_publication_company_search_and_withdrawal(self):
        self.authenticate(None, None)
        url = "/formations/catalogue/%s" % self.course.id
        self.assertEqual(self.url_open(url).status_code, 404)
        self.course.with_user(self.editor).write({"public_catalogue": True})
        foreign = self.env["training.course"].create(
            {"name": "FICTIONAL FOREIGN PUBLIC COURSE", "company_id": self.other_company.id, "public_catalogue": True}
        )
        page = self.url_open(url)
        self.assertEqual(page.status_code, 200)
        self.assertIn("General presentation", page.text)
        self.assertIn("Apply a method", page.text)
        root = self.url_open("/formations")
        self.assertIn(self.course.name, root.text)
        self.assertNotIn(foreign.name, root.text)
        self.assertEqual(self.url_open("/formations/catalogue/%s" % foreign.id).status_code, 404)
        self.assertNotIn(self.course.name, self.url_open("/formations?search=UNPUBLISHED_SECRET_SEARCH").text)
        self.assertIn(self.course.name, self.url_open("/formations?search=General%20presentation").text)
        self.assertNotIn(self.course.name, self.url_open("/formations?category=999999").text)
        self.assertNotIn(self.course.name, self.url_open("/formations?mode=autonomous").text)
        with self.assertRaises(AccessError):
            self.course.with_user(self.env.ref("base.public_user")).read(["presentation"])
        self.course.with_user(self.editor).write({"public_catalogue": False})
        self.assertEqual(self.url_open(url).status_code, 404)
        self.course.with_user(self.editor).write({"public_catalogue": True, "active": False})
        self.assertEqual(self.url_open(url).status_code, 404)

    def test_operator_comes_from_native_website_host(self):
        self.course.with_user(self.editor).write({"public_catalogue": True})
        foreign = self.env["training.course"].create(
            {
                "name": "FICTIONAL WEBSITE B OFFER",
                "company_id": self.other_company.id,
                "public_catalogue": True,
            }
        )
        self.env["website"].create(
            {
                "name": "Fictional catalogue B",
                "domain": "http://fictional-catalogue-b.example.invalid",
                "company_id": self.other_company.id,
            }
        )
        self.authenticate(None, None)
        headers = {"Host": "fictional-catalogue-b.example.invalid"}
        root = self.url_open("/formations", headers=headers, allow_redirects=False)
        self.assertEqual(root.status_code, 200)
        self.assertIn(foreign.name, root.text)
        self.assertNotIn(self.course.name, root.text)
        own = self.url_open("/formations/catalogue/%s" % self.course.id, headers=headers, allow_redirects=False)
        self.assertEqual(own.status_code, 404)
