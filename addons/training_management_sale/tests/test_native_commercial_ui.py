"""Client payload regressions found by the S03.1 native visual acceptance."""

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tools.safe_eval import safe_eval, time
from odoo.tools.translate import load_language

from odoo.addons.training_management.tests.test_enrollment import EnrollmentCase


@tagged("post_install", "-at_install")
class TestNativeCommercialUI(EnrollmentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seller = new_test_user(cls.env, login="s031_ui_sales", groups="sales_team.group_sale_salesman")

    def test_sales_form_payload_contains_no_undefined_or_private_fields(self):
        private = {"access_end", "access_start", "access_state", "effective_access", "prerequisites", "user_id"}
        for model in ("training.enrollment", "training.seat.allocation", "training.delivery"):
            payload = self.env[model].with_user(self.seller).get_views([(False, "form"), (False, "list")])
            metadata = payload["models"][model]["fields"]
            for view in payload["views"].values():
                arch = etree.fromstring(view["arch"].encode())
                # The web form parser requires metadata for every field node,
                # including fields inserted by modifier dependency processing.
                names = {node.get("name") for node in arch.xpath(".//field[not(ancestor::field)]")}
                self.assertFalse(names - metadata.keys(), (model, names - metadata.keys()))
                self.assertFalse(arch.xpath("./header/button"), model)
                self.assertFalse(arch.xpath(".//page[@string='History']"), model)
                if model == "training.enrollment":
                    self.assertFalse(names & private)
                    self.assertFalse(private & metadata.keys())
        enrollment = self.enrollment(self.delivery()).with_user(self.seller)
        self.assertEqual(enrollment.read(["state"])[0]["state"], "requested")
        with self.assertRaises(AccessError):
            enrollment.read(["access_end"])
        with self.assertRaises(AccessError):
            enrollment.action_confirm()

    def test_sales_navigation_and_coordinator_bound_actions(self):
        ids = {
            self.env.ref("training_management." + xmlid).id
            for xmlid in (
                "menu_training_root",
                "menu_training_deliveries",
                "menu_training_allocations",
                "menu_training_enrollments",
            )
        }
        for user in (self.seller, self.coordinator):
            self.assertTrue(ids <= self.env["ir.ui.menu"].with_user(user)._visible_menu_ids())
        action_ids = {
            self.env.ref("training_management.action_enrollment_" + name + "_selection").id
            for name in ("confirm", "authorize", "open_access")
        }
        for user, expected in ((self.seller, set()), (self.coordinator, action_ids)):
            bindings = self.env["ir.actions.actions"].with_user(user).get_bindings("training.enrollment")
            self.assertEqual({action["id"] for action in bindings.get("action", [])} & action_ids, expected)

    def test_coordinator_access_buttons_follow_server_states(self):
        view = self.env["training.enrollment"].with_user(self.coordinator).get_view(view_type="form")
        arch = etree.fromstring(view["arch"].encode())
        buttons = {
            safe_eval(node.get("context", "{}"))["reason_action"]: node
            for node in arch.xpath("./header/button[@context]")
            if "reason_action" in safe_eval(node.get("context", "{}"))
        }
        secondary = {
            self.env.ref("training_management.action_enrollment_" + name).id
            for name in ("withdraw_authorization", "suspend_access", "revoke_access")
        }
        for name in ("action_revoke_authorization", "action_suspend_access", "action_revoke_access"):
            self.assertNotIn(name, buttons)
        for user, expected in ((self.seller, set()), (self.coordinator, secondary)):
            bindings = self.env["ir.actions.actions"].with_user(user).get_bindings("training.enrollment")
            self.assertEqual({action["id"] for action in bindings.get("action", [])} & secondary, expected)
        for state in (
            "requested",
            "reserved",
            "waiting",
            "confirmed",
            "postponed",
            "closed",
            "cancelled",
            "replaced",
            "abandoned",
        ):
            for authorized in (False, True):
                for access_state in ("unopened", "suspended", "active", "revoked"):
                    values = {
                        "state": state,
                        "commercially_authorized": authorized,
                        "access_state": access_state,
                        "user_id": 1,
                    }
                    self.assertEqual(
                        safe_eval(buttons["action_authorize"].get("invisible"), values),
                        state != "confirmed" or authorized,
                    )
                    self.assertEqual(
                        safe_eval(buttons["action_open_access"].get("invisible"), values),
                        state != "confirmed" or not authorized or access_state in ("active", "revoked"),
                    )

    def test_french_bulk_actions_and_dates_wizard(self):
        load_language(self.cr, "fr_FR")
        for name, label in (
            ("confirm", "Confirmer l’inscription"),
            ("authorize", "Autoriser commercialement"),
            ("open_access", "Ouvrir / reprendre l’accès"),
        ):
            action = self.env.ref("training_management.action_enrollment_" + name + "_selection").with_context(
                lang="fr_FR"
            )
            self.assertEqual(action.name, label)
        model = self.env["training.delivery.dates"].with_user(self.coordinator).with_context(lang="fr_FR")
        for name, label in (
            ("delivery_id", "Réalisation"),
            ("start_at", "Début"),
            ("end_at", "Fin"),
            ("reason", "Motif"),
        ):
            self.assertEqual(model.fields_get([name])[name]["string"], label)
        self.assertEqual(
            self.env["training.delivery"]
            .with_context(lang="fr_FR")
            .fields_get(["activity_state"])["activity_state"]["string"],
            "Statut de l'activité",
        )
        arch = etree.fromstring(model.get_view(view_type="form")["arch"].encode())
        self.assertEqual(arch.get("string"), "Modifier les dates")
        self.assertEqual(arch.xpath("./footer/button/@string"), ["Appliquer", "Annuler"])
        for model, expected in (
            ("training.delivery", {"group_state": "État", "group_program": "Programme", "group_kind": "Type"}),
            (
                "training.seat.allocation",
                {"group_delivery": "Réalisation", "group_state": "État", "group_customer": "Client"},
            ),
            (
                "training.enrollment",
                {"group_delivery": "Réalisation", "group_state": "État", "group_allocation": "Lot de places"},
            ),
        ):
            search = self.env[model].with_user(self.seller).with_context(lang="fr_FR").get_view(view_type="search")
            arch = etree.fromstring(search["arch"].encode())
            labels = {node.get("name"): node.get("string") for node in arch.xpath(".//group/filter")}
            self.assertEqual(labels, expected)

    def test_sales_search_filters_use_only_readable_fields(self):
        for model in ("training.delivery", "training.seat.allocation", "training.enrollment"):
            commercial = self.env[model].with_user(self.seller)
            arch = etree.fromstring(commercial.get_view(view_type="search")["arch"].encode())
            for node in arch.xpath(".//filter[@domain]"):
                domain = safe_eval(node.get("domain"), {"time": time})
                commercial.search_count(domain)
            coordinator = self.env[model].with_user(self.coordinator)
            arch = etree.fromstring(coordinator.get_view(view_type="search")["arch"].encode())
            self.assertTrue(arch.xpath(".//filter[@name='to_process']"))
