"""S10 keeps currencies and native commercial access boundaries separate."""

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.addons.training_management.tests.test_evaluation import EvaluationCase

from .test_training_sale import TestTrainingSale


@tagged("post_install", "-at_install")
class TestDashboardSale(EvaluationCase):
    def test_two_currencies_are_not_summed_and_finance_is_not_granted(self):
        delivery = self.delivery()
        self.env.ref("sales_team.group_sale_salesman").write({"user_ids": [Command.link(self.coordinator.id)]})
        self.salesperson = self.coordinator
        self.partner = self.customer
        self.product = (
            self.env["product.template"]
            .create(
                {
                    "name": "Fictional S10 training service",
                    "type": "service",
                    "company_id": self.company.id,
                    "training_course_id": self.course.id,
                    "training_price_basis": "person",
                }
            )
            .product_variant_id
        )
        for currency in (self.env.ref("base.EUR"), self.env.ref("base.MAD")):
            currency.active = True
            self.eur = currency
            order = TestTrainingSale._server_guard_order(self)
            order.action_confirm()
            lot = self.lot(
                delivery, sale_line_id=order.order_line.id, quantity=1, source_reference="S10-" + currency.name
            )
            lot.action_confirm()
        data = self.env["training.dashboard.service"].with_user(self.coordinator)._dashboard(delivery.id)
        values = {row["currency"]: row["amount"] for row in data["commercial"] if row["kind"] == "sales"}
        self.assertEqual(values, {"EUR": 100, "MAD": 100})
        self.assertFalse(any(row["kind"] == "invoices" for row in data["commercial"]))
        delivery.write({"evaluation_supervisor_ids": [Command.set(self.supervisor.ids)]})
        restricted = self.env["training.dashboard.service"].with_user(self.supervisor)._dashboard(delivery.id)
        self.assertEqual(restricted["commercial"], [])

    def test_request_acknowledgement_reuses_mail_and_checks_current_recipient(self):
        lead = self.env["crm.lead"].create(
            {
                "name": "Fictional S10 request",
                "training_request_kind": "individual",
                "email_from": "fictional-s10@example.invalid",
                "company_id": self.company.id,
            }
        )
        journal = self.env["training.request.notice"]
        notice = journal._queue(lead)
        self.assertTrue(notice.mail_id)
        self.assertEqual(journal._queue(lead), notice)
        self.assertEqual(len(journal.search([("lead_id", "=", lead.id)])), 1)
        self.assertFalse(notice.mail_id.email_cc or notice.mail_id.recipient_ids or notice.mail_id.attachment_ids)
        lead.email_from = "changed-fictional@example.invalid"
        self.assertFalse(notice._authorized())
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()

    def test_sales_reader_can_consult_request_distribution_without_mail_access(self):
        delivery = self.delivery()
        self.env.ref("sales_team.group_sale_salesman").write({"user_ids": [Command.link(self.coordinator.id)]})
        lead = (
            self.env["crm.lead"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional S10 distribution audit",
                    "training_request_kind": "individual",
                    "training_program_id": self.program.id,
                    "email_from": "fictional-audit@example.invalid",
                    "company_id": self.company.id,
                }
            )
        )
        notice = self.env["training.request.notice"].sudo().search([("lead_id", "=", lead.id)])
        self.assertTrue(notice.mail_id)
        notice.mail_id.write({"state": "exception", "failure_reason": "Fictional distribution failure"})
        service = self.env["training.dashboard.service"].with_user(self.coordinator)
        journal = service._dashboard(delivery.id)["notifications"]
        rows = [row for row in journal if row["source"] == "training.request.notice"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["failure"], "Fictional distribution failure")
