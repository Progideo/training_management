"""General pages work with the catalogue alone; public ORM grants stay closed."""

import json
from urllib.parse import parse_qs, urlencode, urlsplit

from lxml import html

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from .test_catalog import SharedCatalogCase


@tagged("post_install", "-at_install")
class TestGeneralCatalogue(SharedCatalogCase, HttpCase):
    def course_path(self, course):
        return "/formations/catalogue/" + self.env["ir.http"]._slug((course.id, course.name))

    def test_pagination_applies_after_search_and_category(self):
        course_model = self.env["training.course"]
        courses = course_model.create(
            [
                {
                    "name": f"Fictional pagination {number:02d}",
                    "company_id": self.course.company_id.id,
                    "category_id": self.category.id,
                    "public_catalogue": True,
                }
                for number in range(13)
            ]
        )
        course_model.create(
            {
                "name": "Fictional pagination without the category",
                "company_id": self.course.company_id.id,
                "public_catalogue": True,
            }
        )
        self.authenticate(None, None)
        search = {"search": "Fictional pagination", "category": str(self.category.id)}
        root = html.fromstring(self.url_open("/formations?" + urlencode(search)).content)
        card_links = "//article//h2/a/@href"
        self.assertEqual(
            [urlsplit(url).path for url in root.xpath(card_links)],
            [self.course_path(course) for course in courses[:12]],
        )
        next_link = root.xpath("//nav//a[starts-with(@href, '/formations/page/2?')]/@href")[0]
        self.assertEqual(parse_qs(urlsplit(next_link).query), {key: [value] for key, value in search.items()})
        second = html.fromstring(self.url_open(next_link).content)
        self.assertEqual([urlsplit(url).path for url in second.xpath(card_links)], [self.course_path(courses[-1])])
        single = html.fromstring(self.url_open("/formations?search=Fictional+pagination+12").content)
        self.assertFalse(single.xpath("//nav[@aria-label='Pages du catalogue']"))

    def test_explicit_publication_company_search_and_withdrawal(self):
        self.authenticate(None, None)
        url = "/formations/catalogue/%s" % self.course.id
        self.assertEqual(self.url_open(url).status_code, 404)
        category = self.env["training.category"].create({"name": "Quality", "company_id": self.course.company_id.id})
        self.course.with_user(self.editor).write({"public_catalogue": True, "category_id": category.id})
        foreign = self.env["training.course"].create(
            {
                "name": "FICTIONAL FOREIGN PUBLIC COURSE",
                "company_id": self.other_company.id,
                "public_catalogue": True,
            }
        )
        page = self.url_open(url)
        self.assertEqual(page.status_code, 200)
        self.assertIn("General presentation", page.text)
        self.assertIn("Apply a method", page.text)
        root = self.url_open("/formations")
        self.assertIn(self.course.name, root.text)
        self.assertNotIn(foreign.name, root.text)
        card = html.fromstring(root.text).xpath(
            '//div[contains(concat(" ", normalize-space(@class), " "), " o_training_catalogue_card ")]'
        )[0]
        card_text = " ".join(card.text_content().split())
        for value in ("General presentation", "Quality", "Sur demande", "Sur devis"):
            self.assertIn(value, card_text)
        self.assertNotIn("Apply a method", card_text)
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

    def test_facets_formats_sort_and_suggestions_keep_the_query(self):
        company = self.course.sudo().company_id
        model = self.env["training.course"]
        base = {"company_id": company.id, "public_catalogue": True, "category_id": self.category.id}
        short = model.create(
            {**base, "name": "Fictional facet short", "live_duration_days": 1, "public_level": "beginner"}
        )
        long = model.create(
            {
                **base,
                "name": "Fictional facet long",
                "live_duration_days": 5,
                "public_level": "expert",
                "public_certifying": True,
            }
        )
        company.sudo().training_catalogue_suggestions = "Fictional facet\n\nUnused"
        self.authenticate(None, None)
        page = html.fromstring(self.url_open("/formations?search=Fictional+facet").content)
        titles = page.xpath("//article//h2/a/text()")
        self.assertEqual(sorted(titles), sorted([short.name, long.name]))
        self.assertIn("/formations?search=Fictional+facet", page.xpath("//section//p//a/@href"))
        certifying = html.fromstring(self.url_open("/formations?search=Fictional+facet&certifying=1").content)
        self.assertEqual(certifying.xpath("//article//h2/a/text()"), [long.name])
        # The active filter keeps the search and can be removed on its own.
        remove = certifying.xpath("//ul[@aria-label='Filtres actifs']//a/@href")[0]
        self.assertEqual(parse_qs(urlsplit(remove).query), {"search": ["Fictional facet"]})
        level = html.fromstring(self.url_open("/formations?search=Fictional+facet&level=beginner").content)
        self.assertEqual(level.xpath("//article//h2/a/text()"), [short.name])
        duration = html.fromstring(self.url_open("/formations?search=Fictional+facet&sort=duration").content)
        self.assertEqual(duration.xpath("//article//h2/a/text()"), [short.name, long.name])
        long_first = html.fromstring(self.url_open("/formations?search=Fictional+facet&duration=long").content)
        self.assertEqual(long_first.xpath("//article//h2/a/text()"), [long.name])
        # Unknown values are ignored rather than trusted.
        loose = html.fromstring(self.url_open("/formations?search=Fictional+facet&level=x&sort=x&format=x").content)
        self.assertEqual(len(loose.xpath("//article//h2/a")), 2)
        self.assertFalse(loose.xpath("//ul[@aria-label='Filtres actifs']"))

    def test_course_page_has_one_address_and_presents_the_course_facts(self):
        company = self.course.sudo().company_id
        model = self.env["training.course"]
        related = model.create({"name": "Fictional related course", "company_id": company.id, "public_catalogue": True})
        self.course.with_user(self.editor).write(
            {
                "public_catalogue": True,
                "presentation": "Fictional tagline\n\nFictional detailed presentation",
                "public_level": "beginner",
                "public_certifying": True,
                "public_reference": "FIC-01",
                "live_duration_days": 2,
                "public_highlights": "Fictional first highlight\nFictional second highlight",
                "public_related_course_ids": [(6, 0, related.ids)],
                "public_faq_ids": [(0, 0, {"question": "Fictional question?", "answer": "Fictional answer"})],
            }
        )
        self.authenticate(None, None)
        path = self.course_path(self.course)
        self.assertNotEqual(path, "/formations/catalogue/%s" % self.course.id)
        # The bare identifier and a former name redirect permanently, keeping the query.
        for old in ("/formations/catalogue/%s" % self.course.id, "/formations/catalogue/old-name-%s" % self.course.id):
            response = self.url_open(old + "?format=intra", allow_redirects=False)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(urlsplit(response.headers["Location"]).path, path)
            self.assertEqual(urlsplit(response.headers["Location"]).query, "format=intra")
        response = self.url_open(path, allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        root = html.fromstring(response.content)
        text = " ".join(root.text_content().split())
        self.assertEqual(root.xpath("//h1/text()"), [self.course.name])
        self.assertEqual(root.xpath("//p[contains(@class, 'o_training_course_tagline')]/text()"), ["Fictional tagline"])
        for value in (
            "Fictional detailed presentation",
            "Fictional first highlight",
            "Apply a method",
            "Fictional question?",
            "Fictional answer",
            "FIC-01",
            "2 jours",
            "Certifiante",
        ):
            self.assertIn(value, text)
        self.assertEqual(root.xpath("//section[@id='training_course_related']//a/@href"), [self.course_path(related)])
        toc = root.xpath("//nav[@aria-label='Sommaire de la formation']//a/@href")
        self.assertEqual(toc, ["#training_course_presentation", "#training_course_objectives", "#training_course_faq"])
        for anchor in toc:
            self.assertTrue(root.xpath("//*[@id='%s']" % anchor[1:]))
        # Without an offering application, the booking card invites a contact and no format is compared.
        self.assertFalse(root.xpath("//*[@role='tablist']"))
        self.assertFalse(root.xpath("//section[@id='training_course_formats']"))
        (schema,) = root.xpath("//script[@type='application/ld+json']/text()")
        data = json.loads(schema)
        self.assertEqual((data["@type"], data["name"], data["courseCode"]), ("Course", self.course.name, "FIC-01"))
        self.assertEqual(data["description"], "Fictional tagline")
        self.assertTrue(data["url"].endswith(path))
