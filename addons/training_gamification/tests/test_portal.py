"""« My progress »: one's own points, rank, badges and challenges, nobody else's."""

import re

from odoo.tests import HttpCase, tagged

from .test_gamification import GamificationCase


@tagged("post_install", "-at_install")
class TestProgressPortal(GamificationCase, HttpCase):
    def csrf(self):
        return re.search(r'name="csrf_token" value="([^"]+)"', self.url_open("/my/training-progress").text).group(1)

    def test_progress_page_shows_only_own_progress(self):
        self.rule(name="Fictional assiduity")
        self.validated_presence()
        self.reconcile()
        badge = self.env["gamification.badge"].create({"name": "Fictional badge"})
        self.env["gamification.badge.user"].sudo().create({"user_id": self.portal.id, "badge_id": badge.id})

        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open("/my/training-progress")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Fictional assiduity", page.text)
        self.assertIn("Fictional badge", page.text)
        self.assertIn("no-store", page.headers["Cache-Control"])
        self.assertEqual(self.url_open(f"/my/training-progress/badge/{badge.id}").status_code, 200)

        self.authenticate(self.portal_b.login, self.portal_b.login)
        page = self.url_open("/my/training-progress")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("Fictional assiduity", page.text)
        self.assertNotIn("Fictional badge", page.text)
        self.assertEqual(self.url_open(f"/my/training-progress/badge/{badge.id}").status_code, 404)

    def test_profile_publication_is_the_participant_choice(self):
        if "website_published" not in self.portal._fields:
            self.skipTest("Public profiles need the website.")
        self.assertFalse(self.portal.website_published)
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open("/my/training-progress", data={"operation": "publish", "csrf_token": self.csrf()})
        self.assertEqual(page.status_code, 200)
        self.portal.invalidate_recordset(["website_published"])
        self.assertTrue(self.portal.website_published)
        self.assertFalse(self.portal_b.website_published)
        self.url_open("/my/training-progress", data={"operation": "unpublish", "csrf_token": self.csrf()})
        self.portal.invalidate_recordset(["website_published"])
        self.assertFalse(self.portal.website_published)
