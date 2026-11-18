"""One CRM operation must preserve native admission and capacity decisions."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from .test_allocation import TestAllocationCommerce


@tagged("post_install", "-at_install")
class TestCrmSessionConfirmation(TestAllocationCommerce):
    def request(self, count=1, capacity=10):
        start = fields.Datetime.now() + timedelta(days=10)
        delivery = self.delivery(kind="session", start_at=start, end_at=start + timedelta(hours=3), capacity=capacity)
        lead = (
            self.env["crm.lead"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional session request",
                    "company_id": self.company.id,
                    "user_id": self.coordinator.id,
                    "type": "lead",
                    "email_from": "fictional-requester@example.invalid",
                    "training_requested_delivery_id": delivery.id,
                    "training_program_id": self.program.id,
                    "training_requested_course_id": self.course.id,
                    "training_attendee_count": count,
                }
            )
        )
        return lead

    def assistant(self, lead, contacts=None, **values):
        action = lead.action_confirm_session_participants()
        wizard = self.env[action["res_model"]].with_user(self.coordinator).browse(action["res_id"])
        self.assertEqual(len(wizard.line_ids), lead.training_attendee_count)
        self.assertEqual(wizard.start_at, lead.training_requested_delivery_id.start_at)
        contacts = contacts or self.env["res.partner"].create(
            [
                {"name": f"Fictional attendee {number}", "email": f"fictional-attendee-{number}@example.invalid"}
                for number in range(lead.training_attendee_count)
            ]
        )
        for line, person in zip(wizard.line_ids, contacts):
            line.participant_id = person
        wizard.write(
            {
                "source": "free",
                "free_reason": "Fictional free test",
                "reason": "Reviewed the prerequisites",
                "prerequisites_checked": True,
                **values,
            }
        )
        return wizard

    def test_crm_form_opens_individual_and_group_confirmation_once(self):
        for count in (1, 3):
            lead = self.request(count=count)
            wizard = self.assistant(lead)
            with Form(wizard) as form:
                self.assertEqual(form.expected_count, count)
                self.assertEqual(len(form.line_ids), count)
            wizard.action_confirm()
            wizard.action_confirm()
            enrollments = lead.training_session_enrollment_ids
            self.assertEqual(len(enrollments), count)
            self.assertEqual(enrollments.mapped("state"), ["confirmed"] * count)
            self.assertEqual(enrollments.mapped("prerequisites"), ["validated"] * count)
            self.assertFalse(any(enrollments.mapped("commercially_authorized")))
            self.assertEqual(enrollments.mapped("access_state"), ["unopened"] * count)
            self.assertEqual(lead.training_requested_delivery_id.occupied_seats, count)
            action = lead.action_confirm_session_participants()
            self.assertEqual(action["res_model"], "training.enrollment")
            self.assertFalse(lead.training_requested_delivery_id.allocation_ids)

    def test_french_labels_for_the_confirmation_dialog(self):
        wizard = self.assistant(self.request()).with_context(lang="fr_FR")
        labels = wizard.fields_get(["prerequisites_checked", "source", "expected_count"])
        self.assertEqual(
            labels["prerequisites_checked"]["string"], "J’ai vérifié les prérequis de tous les participants"
        )
        self.assertEqual(dict(labels["source"]["selection"])["order"], "Commande confirmée")
        arch = (
            self.env.ref("training_management_sale.view_crm_session_confirmation_form")
            .with_context(lang="fr_FR")
            .arch_db
        )
        self.assertIn('string="Confirmer toutes les places"', arch)

    def test_native_rating_deletion_terminates_on_empty_and_existing_records(self):
        ratings = self.env["rating.rating"]
        self.assertTrue(ratings.browse().unlink())
        rating = ratings.create(
            {
                "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                "res_id": self.customer.id,
                "partner_id": self.customer.id,
                "rating": 5,
            }
        )
        self.assertTrue(rating.unlink())
        self.assertFalse(rating.exists())

    def test_confirmed_commercial_order_confirms_one_lot_and_all_participants(self):
        lead = self.request(count=3)
        order = self.order(count=3)
        wizard = self.assistant(lead, source="order", free_reason=False, sale_line_id=order.order_line.id)
        wizard.action_confirm()
        enrollments = lead.training_session_enrollment_ids
        allocation = enrollments.allocation_id
        self.assertEqual(allocation.sale_line_id, order.order_line)
        self.assertEqual(allocation.quantity, 3)
        self.assertEqual(allocation.state, "confirmed")
        self.assertEqual(allocation.unnamed_seats, 0)
        self.assertEqual(lead.training_requested_delivery_id.occupied_seats, 3)
        self.assertFalse(enrollments.filtered("free_reason"))
        self.assertEqual(order.state, "sale")
        wizard.action_confirm()
        self.assertEqual(len(lead.training_requested_delivery_id.allocation_ids), 1)

    def test_reuse_confirmed_lot_does_not_double_count_capacity(self):
        lead = self.request(count=2, capacity=3)
        order = self.order(count=3)
        allocation = self.lot(lead.training_requested_delivery_id, quantity=3, sale_line_id=order.order_line.id)
        allocation.action_confirm()
        wizard = self.assistant(lead, source="allocation", free_reason=False, allocation_id=allocation.id)
        wizard.action_confirm()
        self.assertEqual(lead.training_session_enrollment_ids.allocation_id, allocation)
        self.assertEqual(allocation.unnamed_seats, 1)
        self.assertEqual(lead.training_requested_delivery_id.occupied_seats, 3)

    def test_capacity_duplicate_or_prerequisite_failure_leaves_no_partial_enrollment(self):
        lead = self.request(count=2, capacity=1)
        wizard = self.assistant(lead)
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        self.assertFalse(lead.training_requested_delivery_id.enrollment_ids)
        lead = self.request(count=2)
        wizard = self.assistant(lead, prerequisites_checked=False)
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        wizard.prerequisites_checked = True
        wizard.line_ids[1].participant_id = wizard.line_ids[0].participant_id
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        self.assertFalse(lead.training_requested_delivery_id.enrollment_ids)
        wizard.line_ids[1].participant_id = self.customer
        existing = self.enrollment(lead.training_requested_delivery_id, participant_id=self.customer.id, user_id=False)
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        self.assertEqual(lead.training_requested_delivery_id.enrollment_ids, existing)
        self.assertFalse(lead.training_session_enrollment_ids)

    def test_wrong_source_changed_dates_or_other_company_are_rejected(self):
        lead = self.request()
        other_delivery = self.delivery()
        order = self.order(count=1)
        allocation = self.lot(other_delivery, quantity=1, sale_line_id=order.order_line.id)
        allocation.action_confirm()
        wizard = self.assistant(lead, source="allocation", allocation_id=allocation.id)
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        wizard.write({"source": "order", "sale_line_id": False})
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        wizard.source = "free"
        delivery = lead.training_requested_delivery_id
        delivery.action_change_dates(
            start_at=delivery.start_at + timedelta(hours=1),
            end_at=delivery.end_at + timedelta(hours=1),
            reason="Fictional rescheduling",
        )
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        self.assertFalse(delivery.enrollment_ids)
        wizard = self.assistant(lead)
        person = wizard.line_ids.participant_id
        person.sudo().company_id = self.other_company
        with self.assertRaises((ValidationError, AccessError)):
            wizard.action_confirm()

    def test_server_permissions_protected_results_and_confirmed_identity(self):
        lead = self.request()
        wizard = self.assistant(lead)
        other_coordinator = new_test_user(
            self.env,
            login="fictional_other_confirmation_coordinator",
            groups="training_management.group_training_coordinator,sales_team.group_sale_salesman",
        )
        for user in (self.seller, self.portal):
            with self.assertRaises(AccessError):
                lead.with_user(user).action_confirm_session_participants()
            with self.assertRaises(AccessError):
                wizard.with_user(user).action_confirm()
        with self.assertRaises(AccessError):
            wizard.with_user(other_coordinator).action_confirm()
        with self.assertRaises(AccessError):
            lead.write({"training_session_enrollment_ids": [Command.clear()]})
        wizard.action_confirm()
        with self.assertRaises(ValidationError):
            lead.write({"training_attendee_count": 2})
        self.assertEqual(lead.training_attendee_count, 1)
