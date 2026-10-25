from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged

from odoo.addons.training_management.tests.test_catalogue import CatalogueCase


@tagged("post_install", "-at_install")
class TestCompanyRequests(CatalogueCase, HttpCase):
    def test_only_explicitly_qualified_client_requests_are_projected(self):
        self.portal.write({"company_id": self.company.id, "company_ids": [Command.set(self.company.ids)]})
        client = self.env["res.partner"].create({"name": "Fictional client A"})
        other = self.env["res.partner"].create({"name": "Fictional client B"})
        self.assertEqual(client.commercial_partner_id, client)
        self.assertTrue(self.portal.active)
        self.assertTrue(self.portal.has_group("base.group_portal"))
        self.assertIn(self.company, self.portal.company_ids)
        grant = (
            self.env["training.company.authorization"]
            .with_user(self.coordinator)
            .create({"company_id": self.company.id, "customer_id": client.id, "user_id": self.portal.id})
        )
        for name, customer, company in (
            ("Authorised client request", client, self.company),
            ("OTHER CLIENT REQUEST", other, self.company),
            ("OTHER OPERATOR REQUEST", client, self.other_company),
        ):
            self.env["crm.lead"].create(
                {
                    "name": name,
                    "company_id": company.id,
                    "partner_id": customer.id,
                    "training_request_kind": "group",
                    "training_objectives": "CONFIDENTIAL FULL CRM FIELD",
                }
            )
        service = self.env["training.company.service"].with_user(self.portal)
        self.assertFalse(service._request_rows())
        grant.action_confirm()
        self.assertEqual([r["name"] for r in service._request_rows()], ["Authorised client request"])
        self.authenticate(self.portal.login, self.portal.login)
        page = self.url_open("/my/company-trainings")
        self.assertIn("Authorised client request", page.text)
        for secret in ("OTHER CLIENT REQUEST", "OTHER OPERATOR REQUEST", "CONFIDENTIAL FULL CRM FIELD"):
            self.assertNotIn(secret, page.text)
        with self.assertRaises(AccessError):
            self.env["crm.lead"].with_user(self.portal).search([])
        grant.action_revoke()
        self.assertNotIn("Authorised client request", self.url_open("/my/company-trainings").text)
