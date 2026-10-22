"""Tests sans réseau de l’automatisation du Project."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/project_issue_completed.py"
spec = importlib.util.spec_from_file_location("project_issue_completed", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def issue(state="closed", reason="completed"):
    return {"state": state, "state_reason": reason}


def card(option="todo"):
    return {"id": "item-1", "project": {"id": "project-1"}, "fieldValueByName": {"optionId": option}}


class SynchronizationTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.api.issue.return_value = issue()
        self.api.target.return_value = ("project-1", "status-1", "done-1")
        self.api.item.side_effect = [card(), card("done-1")]
        self.sleep = Mock()

    def run_sync(self, **kwargs):
        return module.synchronize(self.api, 42, sleep=self.sleep, **kwargs)

    def test_completed_updates_only_the_target_status_and_verifies(self):
        result = self.run_sync(dry_run=False, allow_write=True)
        self.api.set_done.assert_called_once_with("project-1", "item-1", "status-1", "done-1")
        self.assertEqual(self.api.item.call_count, 2)
        self.assertTrue(result.startswith("updated:"))

    def test_abandoned_duplicate_open_and_unknown_are_ignored(self):
        for state, reason in [
            ("closed", "not_planned"),
            ("closed", "duplicate"),
            ("open", "reopened"),
            ("closed", None),
            ("closed", "unexpected"),
        ]:
            with self.subTest(state=state, reason=reason):
                self.api.reset_mock()
                self.api.issue.return_value = issue(state, reason)
                self.assertTrue(self.run_sync(dry_run=False, allow_write=True).startswith("ignored:"))
                self.api.set_done.assert_not_called()
                self.api.target.assert_not_called()

    def test_pull_request_is_ignored(self):
        self.api.issue.return_value = {**issue(), "pull_request": {"url": "example"}}
        self.assertTrue(self.run_sync().startswith("ignored:"))
        self.api.target.assert_not_called()

    def test_dry_run_never_writes(self):
        self.assertTrue(self.run_sync().startswith("dry-run:"))
        self.api.set_done.assert_not_called()

    def test_disabled_flag_prevents_write_even_if_requested(self):
        with self.assertRaisesRegex(RuntimeError, "Écriture désactivée"):
            self.run_sync(dry_run=False, allow_write=False)
        self.api.target.assert_not_called()
        self.api.set_done.assert_not_called()

    def test_already_done_is_idempotent(self):
        self.api.item.side_effect = None
        self.api.item.return_value = card("done-1")
        self.assertTrue(self.run_sync(dry_run=False, allow_write=True).startswith("unchanged:"))
        self.api.set_done.assert_not_called()

    def test_reopened_or_abandoned_before_write_is_not_updated(self):
        for current in [issue("open", "reopened"), issue("closed", "not_planned")]:
            with self.subTest(current=current):
                self.api.issue.side_effect = [issue(), current]
                self.api.item.side_effect = [card()]
                self.assertTrue(self.run_sync(dry_run=False, allow_write=True).startswith("ignored:"))
                self.api.set_done.assert_not_called()

    def test_missing_card_is_retried_without_creating_it(self):
        self.api.item.side_effect = [None, card(), card("done-1")]
        self.run_sync(dry_run=False, allow_write=True)
        self.sleep.assert_called_once_with(10)
        self.api.set_done.assert_called_once()

    def test_missing_card_after_retries_fails_visibly(self):
        self.api.item.side_effect = None
        self.api.item.return_value = None
        with self.assertRaisesRegex(RuntimeError, "Carte absente"):
            self.run_sync(dry_run=False, allow_write=True)
        self.assertEqual(self.api.item.call_count, 6)
        self.assertEqual(self.sleep.call_count, 5)
        self.api.set_done.assert_not_called()

    def test_reopened_during_retry_stops_waiting(self):
        self.api.item.side_effect = [None]
        self.api.issue.side_effect = [issue(), issue("open", "reopened")]
        self.assertTrue(self.run_sync(dry_run=False, allow_write=True).startswith("ignored:"))
        self.sleep.assert_not_called()
        self.api.set_done.assert_not_called()

    def test_api_failure_is_not_silently_ignored(self):
        self.api.issue.side_effect = module.APIError("HTTP 403")
        with self.assertRaises(module.APIError):
            self.run_sync(dry_run=False, allow_write=True)
        self.api.set_done.assert_not_called()

    def test_unconfirmed_update_fails_visibly(self):
        self.api.item.side_effect = [card(), card()]
        with self.assertRaisesRegex(RuntimeError, "Statut final non confirmé"):
            self.run_sync(dry_run=False, allow_write=True)


class GraphQLTests(unittest.TestCase):
    def setUp(self):
        self.api = module.GitHub("fake-token-never-sent")
        self.api.graphql = Mock()

    def test_item_lookup_paginates_and_ignores_other_projects(self):
        def page(nodes, more=False, cursor=None):
            return {
                "repository": {
                    "issue": {"projectItems": {"nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": cursor}}}
                }
            }

        other = {**card(), "project": {"id": "another-project"}}
        self.api.graphql.side_effect = [page([other], True, "page-2"), page([card()])]
        self.assertEqual(self.api.item(42, "project-1")["id"], "item-1")
        self.assertEqual(self.api.graphql.call_args.args[1], {"number": 42, "cursor": "page-2"})

    def test_target_lookup_paginates(self):
        def page(nodes, more=False, cursor=None):
            return {
                "organization": {
                    "projectV2": {
                        "id": "project-1",
                        "fields": {"nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": cursor}},
                    }
                }
            }

        self.api.graphql.side_effect = [
            page([{}], True, "page-2"),
            page([{"id": "status-1", "name": "Status", "options": [{"id": "done-1", "name": "Terminé"}]}]),
        ]
        self.assertEqual(self.api.target(), ("project-1", "status-1", "done-1"))

    def test_missing_status_option_fails_instead_of_guessing(self):
        self.api.graphql.return_value = {
            "organization": {
                "projectV2": {
                    "id": "project-1",
                    "fields": {"nodes": [{"id": "status-1", "name": "Status", "options": []}]},
                }
            }
        }
        with self.assertRaisesRegex(module.APIError, "Option Terminé"):
            self.api.target()

    def test_graphql_errors_do_not_expose_response_or_token(self):
        api = module.GitHub("private-token")
        api.request = Mock(return_value={"errors": [{"message": "private-response"}]})
        with self.assertRaises(module.APIError) as context:
            api.graphql("query {}", {})
        self.assertNotIn("private", str(context.exception))

    def test_invalid_manual_issue_number_is_rejected_before_network(self):
        with patch.dict(module.os.environ, {"ISSUE_NUMBER": "42; echo unsafe", "GH_TOKEN": "fake"}):
            with patch.object(module.GitHub, "request") as request:
                with self.assertRaisesRegex(RuntimeError, "entier positif"):
                    module.main()
                request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
