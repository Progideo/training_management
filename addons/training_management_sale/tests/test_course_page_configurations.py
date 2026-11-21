"""Course page for each way a course can be offered: inter, intra with or without dates, autonomy.

Optional course fields are left empty in some cases: the page must stay coherent without them.
"""

from datetime import timedelta

from lxml import html

from odoo import fields
from odoo.tests import HttpCase, tagged

from odoo.addons.training_management.tests.test_session_publication import SessionAlertCase


@tagged("post_install", "-at_install")
class TestCoursePageConfigurations(SessionAlertCase, HttpCase):
    PROGRAM_FIELDS = (
        "objectives",
        "target_audience",
        "prerequisites",
        "content",
        "teaching_methods",
        "evaluation_criteria",
        "access_conditions",
        "accessibility_information",
    )

    def new_course(self, name, **values):
        return self.env["training.course"].create(
            {
                "name": name,
                "company_id": self.company.id,
                "category_id": self.course.category_id.id,
                "public_catalogue": True,
                **values,
            }
        )

    def publish_version(self, course, version, delivery_mode="onsite", duration_hours=7, **values):
        program = (
            self.env["training.program.version"]
            .with_user(self.coordinator)
            .create(
                {
                    **{key: self.public_program[key] for key in self.PROGRAM_FIELDS},
                    "course_id": course.id,
                    "version": version,
                    "title": "Fictional %s version" % version,
                    "delivery_mode": delivery_mode,
                    "duration_hours": duration_hours,
                    "language_id": self.env.ref("base.lang_en").id,
                    "accessibility_contact_id": self.customer.id,
                    "public_catalogue": True,
                    **values,
                }
            )
        )
        program.action_validate()
        program.action_publish()
        return program

    def inter_price(self, course, amount):
        return self.env["product.template"].create(
            {
                "name": "Fictional inter-company tariff %s" % course.id,
                "company_id": self.company.id,
                "type": "service",
                "training_course_id": course.id,
                "training_price_basis": "person",
                "training_public_session_price": True,
                "list_price": amount,
                "taxes_id": [(5, 0, 0)],
            }
        )

    def dated_session(self, program, days=30, **values):
        start = fields.Datetime.now() + timedelta(days=days)
        return self.delivery(
            program_id=program.id,
            kind="session",
            capacity=8,
            start_at=start,
            end_at=start + timedelta(hours=8),
            **values,
        )

    def page(self, course, query=""):
        self.authenticate(None, None)
        response = self.url_open("/formations/catalogue/%s%s" % (course.id, query))
        self.assertEqual(response.status_code, 200)
        return html.fromstring(response.content)

    @staticmethod
    def text(root, xpath):
        return " ".join(root.xpath("string(%s)" % xpath).split())

    def tabs(self, root):
        return [
            target[len("#training_booking_") :]
            for target in root.xpath("//div[@role='tablist']/button/@data-bs-target")
        ]

    def comparison(self, root):
        return {
            " ".join(row.xpath("string(th)").split()): [
                " ".join(cell.text_content().split()) for cell in row.xpath("td")
            ]
            for row in root.xpath("//section[@id='training_course_formats']//tbody/tr[th]")
        }

    def assertCoherent(self, root):
        # Every anchor of the summary leads to a section, and each tab controls its panel.
        for anchor in root.xpath("//nav[@aria-label='Sommaire de la formation']//a/@href"):
            self.assertTrue(root.xpath("//*[@id='%s']" % anchor[1:]), anchor)
        for tab in root.xpath("//div[@role='tablist']/button[@role='tab']"):
            self.assertTrue(root.xpath("//*[@id='%s'][@role='tabpanel']" % tab.get("aria-controls")))
        self.assertEqual(
            len(root.xpath("//div[@role='tablist']/button[@aria-selected='true']")), min(1, len(self.tabs(root)))
        )
        self.assertFalse(root.xpath("//*[contains(@class, 'o_training_course_offers')]"))

    def test_inter_session_price_intra_and_autonomy_with_full_content(self):
        related = self.new_course("Fictional related course")
        course = self.new_course(
            "Fictional complete course",
            presentation="Fictional complete tagline\n\nFictional second paragraph",
            live_duration_days=3,
            public_level="advanced",
            public_certifying=True,
            public_highlights="Practice : 70 % of exercises\nProject : a real case",
            public_related_course_ids=[(6, 0, related.ids)],
            public_faq_ids=[(0, 0, {"question": "Fictional question?", "answer": "Fictional answer"})],
        )
        live = self.publish_version(course, "FULL-LIVE", "blended", 21, also_onsite=True)
        # Without a public autonomous price (sold by the eLearning application), the eLearning
        # version is not presented (decision of 21 November 2026).
        self.publish_version(course, "FULL-AUTO", "elearning", 10)
        self.inter_price(course, 4500)
        delivery = self.dated_session(live, public_location="Fictional city")
        delivery.action_publish_session(reason="Fictional publication")
        root = self.page(course)
        self.assertCoherent(root)
        self.assertEqual(self.tabs(root), ["inter", "intra"])
        self.assertFalse(root.xpath("//div[@id='training_booking_autonomous']"))
        inter = self.text(root, "//div[@id='training_booking_inter']")
        self.assertIn("4", inter)
        self.assertIn("HT par participant", inter)
        self.assertNotIn("Aucune session programmée", inter)
        self.assertEqual(
            root.xpath("//div[@id='training_booking_inter']//input[@name='session'][@checked]/@value"),
            [str(delivery.id)],
        )
        self.assertIn("Sur devis", self.text(root, "//div[@id='training_booking_intra']"))
        compared = self.comparison(root)
        self.assertEqual(compared["Dates"][0], "Sessions planifiées")
        self.assertEqual(compared["Durée"], ["3 jours", "3 jours"])
        self.assertIn("HT par participant", compared["Tarif"][0])
        self.assertEqual(compared["Tarif"][1:], ["Sur devis"])
        self.assertIn("S’inscrire", self.text(root, "//div[contains(@class, 'o_training_course_mobile_bar')]"))
        self.assertEqual(
            root.xpath("//nav[@aria-label='Sommaire de la formation']//a/@href"),
            [
                "#training_course_presentation",
                "#training_course_objectives",
                "#training_course_programme",
                "#training_course_audience",
                "#training_course_modalities",
                "#training_course_formats",
                "#training_course_faq",
            ],
        )
        self.assertIn("Fictional second paragraph", self.text(root, "//section[@id='training_course_presentation']"))
        self.assertTrue(root.xpath("//section[@id='training_course_related']"))
        schema = self.course_schema(root)
        self.assertEqual(schema["offers"][0]["price"], 4500)
        self.assertEqual(len(schema["hasCourseInstance"]), 1)
        self.assertEqual(schema["timeRequired"], "PT21H")

    def test_inter_and_intra_without_dates_keep_the_price_and_invite_an_alert(self):
        course = self.new_course(
            "Fictional course without dates", presentation="Fictional single tagline", live_duration_days=2
        )
        live = self.publish_version(course, "NODATE-LIVE", "onsite", 14, also_remote=True)
        self.inter_price(course, 3000)
        root = self.page(course)
        self.assertCoherent(root)
        self.assertEqual(self.tabs(root), ["inter", "intra"])
        inter = self.text(root, "//div[@id='training_booking_inter']")
        self.assertIn("HT par participant", inter)
        self.assertIn("Aucune session programmée", inter)
        self.assertTrue(root.xpath(f"//div[@id='training_booking_inter']//a[@href='/formations/{live.id}/date-alert']"))
        self.assertFalse(root.xpath("//input[@name='session']"))
        compared = self.comparison(root)
        self.assertEqual(compared["Dates"], ["Aucune date programmée", "À convenir avec vous"])
        self.assertEqual(compared["Lieu"], ["Lieu de la session ou à distance", "Vos locaux ou à distance"])
        # No session to register for: the mobile bar leads to the formats.
        mobile = self.text(root, "//div[contains(@class, 'o_training_course_mobile_bar')]")
        self.assertIn("HT par participant", mobile)
        self.assertIn("Voir les formats", mobile)
        self.assertNotIn("S’inscrire", mobile)
        # A one paragraph presentation is the tagline only: not repeated under a « Présentation » title.
        schema = self.course_schema(root)
        self.assertEqual(schema["offers"][0]["price"], 3000)
        self.assertNotIn("hasCourseInstance", schema)
        for script in root.xpath("//script"):
            script.getparent().remove(script)
        body = " ".join(root.xpath("string(//body)").split())
        self.assertEqual(body.count("Fictional single tagline"), 1)
        self.assertFalse(root.xpath("//section[@id='training_course_presentation']"))
        self.assertTrue(root.xpath("//details[contains(@class, 'o_training_course_share')]"))

    def test_intra_on_quotation_without_optional_course_fields(self):
        # No presentation, duration in days, level, highlights, FAQ or related course; remote only.
        course = self.new_course("Fictional bare remote course")
        self.publish_version(course, "BARE-REMOTE", "remote", 3.5)
        root = self.page(course)
        self.assertCoherent(root)
        # Neither inter-company price nor session: only the intra-company quotation is offered.
        self.assertEqual(self.tabs(root), ["intra"])
        self.assertFalse(root.xpath("//div[@id='training_booking_inter']"))
        self.assertFalse(root.xpath("//a[contains(@href, '/date-alert')]"))
        self.assertFalse(root.xpath("//p[contains(@class, 'o_training_course_tagline')]"))
        intra = self.text(root, "//div[@id='training_booking_intra']")
        self.assertIn("Sur devis", intra)
        # Without days, the duration of the version is given.
        self.assertIn("3.5 h", intra.replace(",", "."))
        self.assertFalse(root.xpath("//section[@id='training_course_formats']"))
        # An individual can still ask for a quotation.
        self.assertTrue(root.xpath("//div[@id='training_booking_intra']//a[contains(@href, 'kind=individual')]"))
        for section in ("presentation", "faq", "related", "reviews"):
            self.assertFalse(root.xpath("//section[@id='training_course_%s']" % section), section)
        self.assertIn("Sur devis", self.text(root, "//div[contains(@class, 'o_training_course_mobile_bar')]"))
        self.assertEqual(self.course_schema(root)["timeRequired"], "PT3H30M")
        self.assertNotIn("offers", self.course_schema(root))

    def test_dated_intra_session_for_a_customer_stays_private(self):
        course = self.new_course("Fictional course with a customer date", presentation="Fictional customer tagline")
        live = self.publish_version(course, "INTRA-DATED", "onsite", 7)
        private = self.dated_session(live, days=20, name="PRIVATE_CUSTOMER_SESSION", public_location="Private city")
        closed = self.dated_session(live, days=40, name="CLOSED_SALES_SESSION", public_location="Closed city")
        closed.action_publish_session(reason="Fictional publication")
        closed.action_close_session_sales(reason="Fictional closing")
        root = self.page(course)
        self.assertCoherent(root)
        page = " ".join(root.text_content().split())
        for value in (private.name, "Private city", closed.name, "Closed city"):
            self.assertNotIn(value, page)
        self.assertFalse(root.xpath("//input[@name='session']"))
        # Without a public session nor an inter-company price, only the intra-company tab remains.
        self.assertEqual(self.tabs(root), ["intra"])
        self.assertIn("Sur devis", self.text(root, "//div[@id='training_booking_intra']"))
        self.assertNotIn("hasCourseInstance", self.course_schema(root))

    def test_autonomy_without_public_price_is_not_presented(self):
        # Decision of 21 November 2026: no autonomy without a public price. The course keeps
        # its general presentation and invites a contact, like a course without programme.
        course = self.new_course(
            "Fictional autonomous course",
            presentation="Fictional autonomous tagline",
            public_highlights="Own pace : open all day",
        )
        self.publish_version(course, "AUTO-ONLY", "elearning", 5)
        root = self.page(course)
        self.assertCoherent(root)
        self.assertFalse(root.xpath("//div[@role='tablist']"))
        self.assertFalse(root.xpath("//div[@id='training_booking_autonomous']"))
        self.assertFalse(root.xpath("//section[@id='training_course_formats']"))
        self.assertFalse(root.xpath("//a[contains(@href, 'kind=individual')]"))
        self.assertTrue(root.xpath("//div[@id='training_course_actions']"))
        self.assertIn("Own pace", self.text(root, "//section[@id='training_course_presentation']"))
        self.authenticate(None, None)
        self.assertNotIn(course.name, self.url_open("/formations?format=autonomous").text)
        # A course listed only through its eLearning version leaves the catalogue with it.
        course.public_catalogue = False
        self.assertNotIn(course.name, self.url_open("/formations").text)

    def test_presented_course_without_published_programme_invites_a_contact(self):
        course = self.new_course("Fictional course without programme", presentation="Fictional lone tagline")
        root = self.page(course)
        self.assertCoherent(root)
        self.assertFalse(root.xpath("//div[@role='tablist']"))
        self.assertTrue(root.xpath("//div[@id='training_course_actions']"))
        self.assertFalse(root.xpath("//section[@id='training_course_formats']"))
        mobile = self.text(root, "//div[contains(@class, 'o_training_course_mobile_bar')]")
        self.assertIn("Sur devis", mobile)
        self.assertIn("Voir les formats", mobile)

    @staticmethod
    def course_schema(root):
        import json

        (schema,) = [
            item
            for item in map(json.loads, root.xpath("//script[@type='application/ld+json']/text()"))
            if isinstance(item, dict) and item.get("@type") == "Course"
        ]
        return schema
