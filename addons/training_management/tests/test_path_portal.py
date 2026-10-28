"""P09.2 personal projection and native authenticated HTTP navigation."""

import json
from datetime import timedelta
from unittest.mock import patch

from lxml import html

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tools.translate import load_language

from .test_path import PathCase


class PathPortalCase(PathCase):
    def assigned_path(self, name=None):
        path = self.path()
        if name:
            path.name = name
        path.action_validate()
        delivery = self.delivery()
        activity = self.activity(delivery, criterion="declaration")
        enrollment = self.opened(delivery)
        first = self.reference(path.step_ids[0], enrollment)
        second_enrollment = self.admitted(self.delivery(program_id=path.step_ids[1].program_id.id))
        second = self.reference(path.step_ids[1], second_enrollment)
        return path, activity, first, second

    def summary(self, path=None, user=None):
        return self.env["training.path.portal"].with_user(user or self.portal)._rows(path.id if path else None)


@tagged("post_install", "-at_install")
class TestPathPortal(PathPortalCase):
    def test_order_progress_and_existing_access_without_side_effects(self):
        path, activity, first, second = self.assigned_path()
        counts = {
            model: self.env[model].search_count([])
            for model in (
                "training.enrollment",
                "training.learning.progress",
                "training.operation",
                "training.path.assignment",
            )
        }
        before = self.summary(path)[0]
        self.assertEqual((before["completed"], before["total"]), (0, 2))
        self.assertTrue(before["mandatory"])
        self.assertEqual(before["steps"][0]["url"], f"/my/trainings/{first.enrollment_id.id}")
        self.assertEqual(before["steps"][1]["status"], "Prerequisites pending")
        self.assertFalse(before["steps"][1]["url"])
        self.assertEqual(before["steps"][1]["prerequisites"], [first.step_id.program_id.title])
        self.assertEqual(counts, {model: self.env[model].search_count([]) for model in counts})
        self.service()._declare(first.enrollment_id.id, activity.id)
        after = self.summary(path)[0]
        self.assertEqual(after["completed"], 1)
        self.assertEqual(after["steps"][1]["status"], "Access pending")
        self.assertFalse(after["steps"][1]["url"])
        second.enrollment_id.action_authorize(reason="Fictional")
        second.enrollment_id.action_open_access(reason="Fictional")
        self.assertTrue(self.summary(path)[0]["steps"][1]["url"])
        first.enrollment_id.action_close(reason="Fictional historical completion")
        closed = self.summary(path)[0]["steps"][0]
        self.assertTrue(closed["completed"])
        self.assertFalse(closed["url"])
        self.assertEqual(len(first.enrollment_id.learning_progress_ids), 1)

    def test_identity_company_and_no_orm_permission_expansion(self):
        path, _, first, _ = self.assigned_path()
        for user in (self.portal_b, self.reader, self.internal, self.coordinator):
            self.assertEqual(self.summary(path, user), [])
        foreign = self.env["training.path"].create(
            {"name": "PRIVATE OTHER OPERATOR", "company_id": self.other_company.id}
        )
        self.assertEqual(self.summary(foreign), [])
        for model, record in (("training.path", path), ("training.path.assignment", first)):
            with self.assertRaises(AccessError):
                record.with_user(self.portal).read(["display_name"])
            self.assertFalse(self.env[model].with_user(self.portal).has_access("create"))
        rows = (
            self.env["training.path.portal"]
            .with_user(self.portal_b)
            .with_context(
                default_participant_id=self.portal.partner_id.id,
                default_user_id=self.portal.id,
            )
            ._rows(path.id)
        )
        self.assertEqual(rows, [])
        self.portal.write({"company_id": self.other_company.id, "company_ids": [Command.set(self.other_company.ids)]})
        self.assertEqual(self.summary(path), [])
        self.portal.write({"company_id": self.company.id, "company_ids": [Command.set(self.company.ids)]})
        self.portal.active = False
        self.assertEqual(self.summary(path), [])

    def test_withdrawal_revocation_suspension_and_time_never_open_access(self):
        path, _, first, second = self.assigned_path()
        second.action_withdraw(reason="Fictional correction")
        first.enrollment_id.action_suspend_access(reason="Fictional suspension")
        self.assertEqual(self.summary(path), [])
        first.enrollment_id.action_open_access(reason="Fictional resume")
        with patch("odoo.fields.Datetime.now", return_value=first.enrollment_id.access_end + timedelta(seconds=1)):
            row = self.summary(path)[0]["steps"][0]
            self.assertEqual(row["status"], "Access ended")
            self.assertFalse(row["url"])
        first.enrollment_id.action_revoke_access(reason="Fictional revocation")
        self.assertEqual(self.summary(path), [])
        first.action_withdraw(reason="Fictional withdrawal")
        self.assertEqual(self.summary(path), [])

    def test_projection_hides_equivalence_motive_and_preserves_unique_source(self):
        path = self.path(mandatory=False)
        path.action_validate()
        enrollment = self.admitted()
        reference = self.reference(path.step_ids[1], enrollment, equivalence_reason="PRIVATE EQUIVALENCE REASON")
        row = self.summary(path)[0]
        self.assertTrue(row["steps"][1]["equivalent"])
        self.assertEqual(row["steps"][0]["status"], "Not available")
        serialized = json.dumps(row)
        for private in (
            "PRIVATE EQUIVALENCE REASON",
            "validated_by",
            "validated_at",
            "participant_id",
            "score",
            "withdrawal_reason",
        ):
            self.assertNotIn(private, serialized)
        self.assertEqual(len(reference.enrollment_id), 1)
        enrollment.action_close(reason="Fictional incomplete historical closure")
        closed = self.summary(path)[0]["steps"][1]
        self.assertEqual(closed["status"], "Closed")
        self.assertFalse(closed["completed"])
        self.assertFalse(closed["url"])


@tagged("post_install", "-at_install")
class TestPathPortalHTTP(PathPortalCase, HttpCase):
    def test_personal_routes_navigation_status_and_private_headers(self):
        path, _, first, second = self.assigned_path()
        self.authenticate(self.portal.login, self.portal.login)
        listing = self.url_open("/my/training-paths")
        self.assertEqual(listing.status_code, 200)
        self.assertIn(path.name, listing.text)
        self.assertIn(f"/my/training-paths/{path.id}", listing.text)
        detail = self.url_open(f"/my/training-paths/{path.id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("no-store", detail.headers["Cache-Control"])
        self.assertIn("Cookie", detail.headers["Vary"])
        self.assertEqual(detail.headers["X-Content-Type-Options"], "nosniff")
        tree = html.fromstring(detail.content)
        links = tree.xpath("//a[starts-with(@href, '/my/trainings/')]/@href")
        self.assertEqual(links, [f"/my/trainings/{first.enrollment_id.id}"])
        self.assertNotIn(f"/my/trainings/{second.enrollment_id.id}", detail.text)
        self.assertEqual(tree.xpath("//progress/@max"), ["2"])
        self.assertIn("Prerequisites pending", detail.text)
        self.assertIn("/my/training-paths", self.url_open("/my/trainings").text)
        self.assertEqual(self.url_open(f"/my/training-paths/{path.id}", data={"attempt": "1"}).status_code, 405)

    def test_foreign_withdrawn_anonymous_and_parameter_forgery(self):
        path, _, first, second = self.assigned_path()
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(f"/my/training-paths/{path.id}").status_code, 404)
        response = self.url_open(
            f"/my/training-paths?user_id={self.portal.id}&participant_id={self.portal.partner_id.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(path.name, response.text)
        self.authenticate(self.portal.login, self.portal.login)
        first.action_withdraw(reason="Fictional withdrawal")
        second.action_withdraw(reason="Fictional withdrawal")
        self.assertEqual(self.url_open(f"/my/training-paths/{path.id}").status_code, 404)
        self.authenticate(None, None)
        response = self.url_open("/my/training-paths")
        self.assertNotIn(path.name, response.text)
        self.assertTrue(
            response.url.endswith("/web/login?redirect=%2Fmy%2Ftraining-paths") or "/web/login" in response.url
        )

    def test_french_titles_and_blocked_step_remain_escaped(self):
        load_language(self.cr, "fr_FR")
        path, _, _, _ = self.assigned_path(name="Fictional <script>private</script> path")
        self.portal.lang = "fr_FR"
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open(f"/my/training-paths/{path.id}")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script>private</script>", response.text)
        self.assertIn("&lt;script&gt;private&lt;/script&gt;", response.text)
        self.assertIn("Mes parcours", response.text)
        self.assertIn("Prérequis en attente", response.text)
        self.assertIn("Ouvrir la formation", response.text)
        self.assertIn("heures pédagogiques estimées", response.text)
        self.assertIn("étapes terminées", response.text)
