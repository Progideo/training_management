"""« My courses »: one page per signed-in person, menu entry, landing page and « My account » cards."""

from unittest.mock import patch

from lxml import html

from odoo.tests import HttpCase, new_test_user, tagged

from .test_attendance import AttendanceCase


@tagged("post_install", "-at_install", "training_courses")
class TestCoursesPage(AttendanceCase, HttpCase):
    def outsider(self):
        return new_test_user(self.env, login="courses.outsider", groups="base.group_portal", name="Fictional outsider")

    def page(self, user):
        self.authenticate(user.login, user.login)
        response = self.url_open("/my/trainings")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        return html.fromstring(response.content)

    def test_participant_sees_training_and_attendance_to_sign(self):
        delivery, session, enrollment = self.scheduled()
        tree = self.page(self.portal)
        self.assertEqual(len(tree.xpath("//h1")), 1)
        rows = tree.xpath("//section[@id='courses_trainings']//a[@href='/my/trainings/%s']" % enrollment.id)
        self.assertTrue(rows)
        self.assertIn(delivery.name, rows[0].text_content())
        todo = tree.xpath(f"//section[@id='courses_todo']//a[@href='/my/trainings/{enrollment.id}/attendance']")
        self.assertTrue(todo, "an elapsed half-day without declaration is to sign")
        # The trainer section and its link belong to trainers only.
        self.assertFalse(tree.xpath("//section[@id='courses_sessions']"))
        # Once declared, the half-day leaves the participant's actions and reaches the trainer's.
        key = self.service()._periods(session)[0]["key"]
        self.service()._declare_halfday(
            enrollment.id, key, accepted=True, definition=self.service()._day_definition(session)
        )
        tree = self.page(self.portal)
        self.assertFalse(tree.xpath(f"//a[@href='/my/trainings/{enrollment.id}/attendance']"))
        trainer = self.page(self.portal_b)
        self.assertTrue(
            trainer.xpath(f"//section[@id='courses_todo']//a[@href='/my/training-sessions/{session.id}/attendance']")
        )
        self.assertFalse(trainer.xpath("//section[@id='courses_trainings']"))

    def test_trainer_sees_upcoming_sessions(self):
        # The fixture session ends at the frozen current time: still listed as current.
        _delivery, session, _enrollment = self.scheduled()
        tree = self.page(self.portal_b)
        self.assertTrue(tree.xpath(f"//section[@id='courses_sessions']//a[@href='/my/training-sessions/{session.id}']"))
        self.assertTrue(tree.xpath("//section[@id='courses_sessions']//a[@href='/my/training-sessions']"))

    def test_person_without_course(self):
        outsider = self.outsider()
        navigation = self.env["training.portal.navigation"]
        self.assertFalse(navigation.with_user(outsider)._has_courses())
        tree = self.page(outsider)
        self.assertTrue(tree.xpath("//p[contains(@class, 'o_training_courses_empty')]"))
        self.assertTrue(tree.xpath("//a[@href='/formations']"))

    def test_menu_entry_only_for_people_with_a_course(self):
        self.scheduled()
        website = self.env["website"].get_current_website()
        menus = self.env["website.menu"]
        menus.search([("url", "=", "/my/trainings")]).unlink()
        menus._training_courses_menu()
        menus._training_courses_menu()
        menu = menus.search([("website_id", "=", website.id), ("url", "=", "/my/trainings")])
        self.assertEqual(len(menu), 1, "added once per website")
        self.assertEqual(menu.parent_id, website.menu_id)
        self.assertTrue(menu.with_user(self.portal).is_visible)
        self.assertTrue(menu.with_user(self.portal_b).is_visible)
        self.assertFalse(menu.with_user(self.outsider()).is_visible)
        self.assertFalse(menu.with_user(self.env.ref("base.public_user")).is_visible)

    def test_landing_page_after_login(self):
        self.scheduled()
        for user, expected in ((self.portal, "/my/trainings"), (self.outsider(), "/my")):
            self.logout()
            login = self.url_open("/web/login")
            csrf = html.fromstring(login.content).xpath("//input[@name='csrf_token']/@value")[0]
            response = self.url_open(
                "/web/login", data={"login": user.login, "password": user.login, "csrf_token": csrf}
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.url.split("?")[0].endswith(expected), (user.login, response.url))

    def test_account_cards(self):
        self.scheduled()
        counters = {
            "training_course_count": "common_category",
            "training_signature_count": "common_category",
            "training_date_alert_count": "common_category",
        }
        self.authenticate(self.portal.login, self.portal.login)
        values = self.make_jsonrpc_request("/my/counters", {"counters": counters})
        self.assertEqual(values["training_course_count"], 1)
        self.assertEqual(values["training_signature_count"], 1)
        self.assertEqual(values["training_date_alert_count"], 0)
        home = html.fromstring(self.url_open("/my/home").content)
        for url in ("/my/trainings", "/my/training-signature", "/my/training-date-alerts"):
            self.assertTrue(home.xpath(f"//div[contains(@class, 'o_portal_index_card')]//a[@href='{url}']"), url)
        outsider = self.outsider()
        self.authenticate(outsider.login, outsider.login)
        values = self.make_jsonrpc_request("/my/counters", {"counters": counters})
        self.assertEqual(values["training_course_count"], 0)
        self.assertEqual(values["training_signature_count"], 0)

    def test_online_courses_contributed_by_another_module(self):
        outsider = self.outsider()
        row = {
            "label": "Ongoing",
            "ongoing": True,
            "name": "Fictional autonomous course",
            "detail": "Next: fictional lesson",
            "progress": 40,
            "url": "/my/learning/1",
            "button": "Continue",
            "sort": 0,
        }
        Contributions = type(self.env["training.my.courses"])
        with (
            patch.object(Contributions, "_has_courses", lambda self: True),
            patch.object(Contributions, "_online_rows", lambda self: [row]),
        ):
            self.assertTrue(self.env["training.portal.navigation"].with_user(outsider)._has_courses())
            tree = self.page(outsider)
            self.assertTrue(tree.xpath("//section[@id='courses_online']//a[@href='/my/learning/1']"))
            self.assertFalse(tree.xpath("//p[contains(@class, 'o_training_courses_empty')]"))
