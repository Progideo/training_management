"""M01: demonstrate the native Contacts import contract; no old schema is assumed."""

import csv
import json

from odoo import Command
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestNativeMigrationContacts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.operator = new_test_user(
            cls.env,
            login="m01_native_operator",
            groups="base.group_user,base.group_partner_manager,base.group_allow_export",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.company_xmlid = cls.company.get_external_id()[cls.company.id]
        with file_open("training_management/tests/data/m01_contacts.csv", "r") as stream:
            cls.fields, *cls.rows = list(csv.reader(stream))
        assert cls.company_xmlid == "base.main_company"

    def native_import(self, rows):
        result = (
            self.env["res.partner"]
            .with_user(self.operator)
            .with_context(
                tracking_disable=True,
                import_file=True,
                mail_create_nosubscribe=True,
                active_test=False,
            )
            .load(self.fields, rows)
        )
        self.assertFalse([m for m in result["messages"] if m["type"] == "error"], result["messages"])
        self.assertTrue(result["ids"])
        return self.env["res.partner"].browse(result["ids"])

    def test_native_replay_preserves_identity_relationships_and_creates_no_accounts(self):
        users_before = self.env["res.users"].with_context(active_test=False).search_count([])
        mails_before = self.env["mail.mail"].search_count([])
        first = self.native_import(self.rows)
        company, person, independent = first
        self.assertTrue(company.is_company)
        self.assertFalse(person.is_company)
        self.assertEqual(person.parent_id, company)
        self.assertEqual(first.mapped("company_id"), self.company)
        self.assertEqual(company.country_id, self.env.ref("base.ma"))
        self.assertEqual(person.country_id, self.env.ref("base.ma"))
        self.assertEqual(independent.country_id, self.env.ref("base.fr"))
        self.assertFalse(independent.is_company)
        self.assertFalse(any(first.mapped("active")))
        self.assertEqual(self.native_import(self.rows), first)
        changed = [list(r) for r in self.rows]
        changed[1][1] = "Corrected fictional M01 Person"
        self.assertEqual(self.native_import(changed), first)
        self.assertEqual(person.name, changed[1][1])
        # A shared email is not a reliable source identity and must not merge contacts.
        separate = [list(self.rows[1])]
        separate[0][0] = "__import__.tm_m01_second_source_person"
        other = self.native_import(separate)
        self.assertNotEqual(other, person)
        self.assertEqual(other.email, person.email)
        self.assertEqual(self.env["res.users"].with_context(active_test=False).search_count([]), users_before)
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)
        self.assertFalse(first.user_ids)
        # Native export supplies the same identifiers, values and parent references for reconciliation.
        exported = first.with_user(self.operator).with_context(lang="en_US").export_data(self.fields)["datas"]
        self.assertEqual([[str(v) if v is not False else "False" for v in r] for r in exported], changed)

    def test_native_bad_reference_rolls_back_the_import(self):
        rows = [list(r) for r in self.rows]
        rows[0][0] = "__import__.tm_m01_rolled_back_company"
        rows[1][0] = "__import__.tm_m01_rolled_back_person"
        rows[1][9] = "__import__.tm_m01_missing_company"
        result = (
            self.env["res.partner"]
            .with_user(self.operator)
            .with_context(active_test=False, import_file=True)
            .load(self.fields, rows)
        )
        self.assertTrue([m for m in result["messages"] if m["type"] == "error"])
        self.assertFalse(self.env.ref(rows[0][0], raise_if_not_found=False))
        self.assertFalse(self.env.ref(rows[1][0], raise_if_not_found=False))
        self.assertFalse(self.env.ref(rows[2][0], raise_if_not_found=False))

    def test_archived_contacts_do_not_grant_portal_or_cross_company_access(self):
        contacts = self.native_import(self.rows)
        other_company = self.env["res.company"].create({"name": "Fictional M01 Other Company"})
        other = new_test_user(
            self.env,
            login="m01_other_company",
            groups="base.group_user,base.group_partner_manager",
            company_id=other_company.id,
            company_ids=[Command.set(other_company.ids)],
        )
        self.assertFalse(contacts.with_user(other).has_access("read"))
        self.assertFalse(contacts.with_user(self.env.ref("base.public_user")).has_access("read"))

    def test_native_import_cannot_overwrite_another_company_through_external_id(self):
        other_company = self.env["res.company"].create({"name": "Fictional M01 Foreign Company"})
        foreign = self.env["res.partner"].create(
            {"name": "Private fictional M01 Contact", "company_id": other_company.id}
        )
        self.env["ir.model.data"].create(
            {"module": "__import__", "name": "tm_m01_foreign_contact", "model": "res.partner", "res_id": foreign.id}
        )
        rows = [list(self.rows[1])]
        rows[0][0] = "__import__.tm_m01_foreign_contact"
        rows[0][9] = ""
        result = self.env["res.partner"].with_user(self.operator).with_context(import_file=True).load(self.fields, rows)
        self.assertTrue([m for m in result["messages"] if m["type"] == "error"])
        self.assertEqual(foreign.name, "Private fictional M01 Contact")
        self.assertEqual(foreign.company_id, other_company)

    def test_native_ice_json_replay_export_and_company_scope(self):
        with file_open("training_management/tests/data/m01_contacts_identifiers.csv", "r") as stream:
            self.fields, *rows = list(csv.reader(stream))
        users = self.env["res.users"].with_context(active_test=False).search_count([])
        mails = self.env["mail.mail"].search_count([])
        contacts = self.native_import(rows)
        expected = {"MA_ICE": "000000000000097"}  # Synthetic checksum-compatible fixture, no fiscal validity.
        self.assertEqual(contacts[0].additional_identifiers, expected)
        self.assertEqual(contacts[1].additional_identifiers, expected)
        self.assertFalse(contacts[2].additional_identifiers)
        self.assertEqual(self.native_import(rows), contacts)
        exported = contacts.with_user(self.operator).with_context(lang="en_US").export_data(self.fields)["datas"]
        for actual, original in zip(exported, rows, strict=True):
            self.assertEqual(json.loads(actual[-1] or "{}"), json.loads(original[-1]))
        self.assertFalse(any(contacts.mapped("active")))
        self.assertFalse(contacts.user_ids)
        self.assertEqual(self.env["res.users"].with_context(active_test=False).search_count([]), users)
        self.assertEqual(self.env["mail.mail"].search_count([]), mails)
        self.assertFalse(contacts.with_user(self.env.ref("base.public_user")).has_access("read"))
        other_company = self.env["res.company"].create({"name": "Fictional ICE Other Company"})
        other = new_test_user(
            self.env,
            login="m01_ice_other",
            groups="base.group_user,base.group_partner_manager",
            company_id=other_company.id,
            company_ids=[Command.set(other_company.ids)],
        )
        self.assertFalse(contacts.with_user(other).has_access("read"))
        portal = new_test_user(self.env, login="m01_ice_portal", groups="base.group_portal")
        self.assertFalse(contacts.with_user(portal).has_access("read"))
        # A deliberate, qualified source change updates the same archived identities.
        changed = [list(row) for row in rows]
        for row in changed[:2]:
            row[-1] = '{"MA_ICE": "000000000000000"}'
        self.assertEqual(self.native_import(changed), contacts)
        self.assertEqual(contacts[0].additional_identifiers, {"MA_ICE": "000000000000000"})
        self.assertEqual(contacts[1].additional_identifiers, contacts[0].additional_identifiers)

    def test_native_ice_bad_checksum_rolls_back_batch(self):
        with file_open("training_management/tests/data/m01_contacts_identifiers.csv", "r") as stream:
            fields, *rows = list(csv.reader(stream))
        rows[1][-1] = '{"MA_ICE": "000000000000096"}'
        result = self.env["res.partner"].with_user(self.operator).with_context(import_file=True).load(fields, rows)
        self.assertTrue([m for m in result["messages"] if m["type"] == "error"])
        for row in rows:
            self.assertFalse(self.env.ref(row[0], raise_if_not_found=False))
