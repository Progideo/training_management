from datetime import datetime
from unittest.mock import patch

from lxml import html

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, new_test_user, tagged

from .test_attendance import AttendanceCase


@tagged("post_install", "-at_install")
class TestCourseReviews(AttendanceCase, HttpCase):
    def test_course_review_requires_own_validated_attendance_and_moderation(self):
        course = self.program.course_id.sudo()
        course.public_catalogue = True
        self.env["website"].search([]).company_id = course.company_id
        moderator = new_test_user(
            self.env,
            login="fictional_course_review_moderator",
            groups="base.group_user,website.group_website_designer",
            company_id=course.company_id.id,
            company_ids=[(6, 0, course.company_id.ids)],
        )
        other_company = self.env["res.company"].create({"name": "Fictional other review company"})
        other_moderator = new_test_user(
            self.env,
            login="fictional_other_review_moderator",
            groups="base.group_user,website.group_website_designer",
            company_id=other_company.id,
            company_ids=[(6, 0, other_company.ids)],
        )
        ratings = self.env["rating.rating"]
        domain = [("res_model", "=", "training.course"), ("res_id", "=", course.id)]
        path = f"/formations/catalogue/{course.id}"
        action = path + "/avis"
        delivery, session, enrollment = self.scheduled()
        self.review(self.declare(session, enrollment))
        self.assertFalse(course._course_review_status(self.portal))
        with patch("odoo.fields.Datetime.now", return_value=datetime(2027, 2, 2, 10)):
            delivery.action_start()
            delivery.action_deliver()
            self.assertEqual(course._course_review_status(self.portal), "eligible")
            with self.assertRaises(AccessError):
                course._submit_course_review(self.portal_b, "5", "Unauthorized review", "1")

            self.authenticate(self.portal_b.login, self.portal_b.login)
            self.assertNotIn(action, self.url_open(path).text)
            self.authenticate(self.portal.login, self.portal.login)
            page = self.url_open(path)
            self.assertIn("no-store", page.headers["Cache-Control"])
            token, = html.fromstring(page.content).xpath(f"//form[@action='{action}']//input[@name='csrf_token']/@value")
            payload = {"csrf_token": token, "score": "4", "feedback": "Fictional course review"}
            self.assertEqual(self.url_open(action, data=payload).status_code, 422)
            self.assertFalse(ratings.sudo().search_count(domain))
            payload["consent"] = "1"
            self.assertEqual(self.url_open(action, data=payload).status_code, 200)
            self.assertEqual(self.url_open(action, data=payload).status_code, 200)

            review = ratings.sudo().search(domain)
            self.assertEqual(len(review), 1)
            self.assertFalse(review.is_public_course_review)
            self.assertFalse(review.access_token)
            self.assertFalse(review.message_id)
            self.assertFalse(ratings.with_user(self.coordinator).search(domain))
            self.assertFalse(ratings.with_user(other_moderator).search(domain))
            with self.assertRaises(AccessError):
                review.with_user(other_moderator).write({"is_public_course_review": True})
            with self.assertRaises(AccessError):
                review.with_user(self.coordinator).write({"is_public_course_review": True})
            with self.assertRaises(AccessError):
                ratings.with_user(moderator).create({
                    "res_model_id": self.env["ir.model"]._get_id("training.course"), "res_id": course.id,
                    "consumed": True, "rating": 5,
                })

            self.authenticate(None, None)
            self.assertNotIn("Fictional course review", self.url_open(path).text)
            review.with_user(moderator).write({"is_public_course_review": True})
            self.assertEqual(review.course_review_moderator_id, moderator)
            self.assertTrue(review.course_review_moderated_at)
            self.assertIn("Fictional course review", self.url_open(path).text)
            review.with_user(moderator).write({"is_public_course_review": False})
            self.assertNotIn("Fictional course review", self.url_open(path).text)
