from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class EnrollmentCase(TransactionCase):
    """INS01–05, CAT02 and SEC01: actual restricted users, no portal delivery."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Fictional S03 B"})
        cls.coordinator = new_test_user(cls.env, login="s03_coord", groups="training_management.group_training_coordinator,base.group_allow_export", company_id=cls.company.id, company_ids=[Command.set(cls.company.ids)])
        cls.reader = new_test_user(cls.env, login="s03_reader", groups="training_management.group_training_reader")
        cls.internal = new_test_user(cls.env, login="s03_internal")
        cls.portal = new_test_user(cls.env, login="s03_participant", groups="base.group_portal")
        cls.portal_b = new_test_user(cls.env, login="s03_other_participant", groups="base.group_portal")
        cls.customer = cls.env["res.partner"].create({"name": "Fictional S03 Buyer"})
        cls.course = cls.env["training.course"].create({"name": "Fictional S03 Course", "company_id": cls.company.id})
        cls.program = cls.env["training.program.version"].create({
            "course_id": cls.course.id, "version": "S03-V1", "title": "Fictional S03 Programme",
            "objectives": "Practice", "target_audience": "Beginners", "prerequisites": "Reviewed manually",
            "content": "Practice", "duration_hours": 7, "delivery_mode": "elearning",
            "language_id": cls.env.ref("base.lang_en").id, "teaching_methods": "Exercises",
            "evaluation_criteria": "Review", "access_conditions": "Manual authorization",
            "accessibility_contact_id": cls.customer.id, "accessibility_information": "Contact coordination",
        })
        cls.program.action_validate()

    def delivery(self, **values):
        return self.env["training.delivery"].with_user(self.coordinator).create({
            "name": "Fictional autonomous offer", "company_id": self.company.id,
            "program_id": self.program.id, "kind": "autonomous", "capacity": 10,
            "access_policy": "duration", "access_days": 10, **values,
        })

    def lot(self, delivery, **values):
        return self.env["training.seat.allocation"].with_user(self.coordinator).create({
            "delivery_id": delivery.id, "customer_id": self.customer.id, "quantity": 10,
            "source_reference": "FICT-RESERVATION", "expires_at": fields.Datetime.now() + timedelta(days=2), **values,
        })

    def enrollment(self, delivery, **values):
        return self.env["training.enrollment"].with_user(self.coordinator).create({
            "delivery_id": delivery.id, "participant_id": self.portal.partner_id.id,
            "user_id": self.portal.id, "free_reason": "Fictional invitation", **values,
        })

    def admitted(self, delivery=None):
        enrollment = self.enrollment(delivery or self.delivery())
        enrollment.change_reason = "Manual review / B2B deferred payment decision"
        enrollment.action_validate_prerequisites()
        enrollment.action_confirm()
        return enrollment



@tagged("post_install", "-at_install")
class TestEnrollment(EnrollmentCase):

    def test_ten_places_seven_names_and_eighth_not_double_counted(self):
        delivery = self.delivery()
        lot = self.lot(delivery)
        for index in range(7):
            person = self.env["res.partner"].create({"name": "Fictional Person %s" % index})
            e = self.enrollment(delivery, participant_id=person.id, user_id=False, allocation_id=lot.id, free_reason=False)
            e.action_reserve()
        self.assertEqual(lot.unnamed_seats, 3)
        self.assertEqual(delivery.occupied_seats, 10)
        with self.assertRaises(ValidationError):
            self.lot(delivery, source_reference="OVER", quantity=1)
        with self.assertRaises(ValidationError):
            self.enrollment(delivery).action_confirm()
        self.assertEqual(delivery.occupied_seats, 10)

    def test_expiry_releases_capacity_without_cron(self):
        delivery = self.delivery(capacity=1)
        lot = self.lot(delivery, quantity=1)
        e = self.enrollment(delivery, allocation_id=lot.id)
        e.action_reserve()
        future = lot.expires_at + timedelta(seconds=1)
        with patch("odoo.fields.Datetime.now", return_value=future):
            delivery.invalidate_recordset()
            self.assertEqual(delivery.occupied_seats, 0)
            self.lot(delivery, quantity=1, source_reference="NEW", expires_at=future + timedelta(days=1))
            with self.assertRaises(ValidationError):
                e.action_confirm()
            lot.action_expire()
            self.assertEqual(e.state, "requested")
            self.assertEqual(lot.state, "expired")

    def test_admission_authorization_account_and_effective_period(self):
        e = self.admitted()
        self.assertEqual(e.effective_access, "unopened")
        with self.assertRaises(ValidationError):
            e.action_open_access()
        e.action_authorize()
        self.assertEqual(e.effective_access, "unopened")
        e.action_open_access()
        original_end = e.access_end
        e.action_open_access()
        self.assertEqual(e.access_end, original_end)
        self.assertEqual(e.effective_access, "active")
        self.assertEqual(e._effective_state(original_end), "expired")
        e.action_suspend_access()
        self.assertEqual(e.effective_access, "suspended")
        e.action_open_access()
        self.assertEqual(e.access_end, original_end)
        e.action_revoke_authorization()
        self.assertEqual(e.effective_access, "blocked")
        e.action_authorize()
        e.action_extend_access(original_end + timedelta(days=3))
        self.assertEqual(e.access_end, original_end + timedelta(days=3))
        self.assertTrue(e.delivery_id.operation_ids.filtered(lambda row: 'access_end' in row.after))
        e.action_revoke_access()
        with self.assertRaises(ValidationError):
            e.action_open_access()

    def test_fixed_access_scheduled_and_disabled_account(self):
        now = fields.Datetime.now()
        e = self.admitted(self.delivery(access_policy="fixed", access_start=now + timedelta(days=1), access_end=now + timedelta(days=3)))
        e.action_authorize()
        e.action_open_access()
        self.assertEqual(e.effective_access, "scheduled")
        self.portal.active = False
        self.assertEqual(e._effective_state(now + timedelta(days=2)), "blocked")

    def test_duplicate_identity_homonym_and_confirmation_replay(self):
        delivery = self.delivery()
        e = self.admitted(delivery)
        history = len(delivery.operation_ids)
        e.action_confirm()
        self.assertEqual(len(delivery.operation_ids), history)
        with self.assertRaises(ValidationError):
            self.enrollment(delivery)
        person = self.env["res.partner"].create({"name": self.portal.partner_id.name})
        other = self.enrollment(delivery, participant_id=person.id, user_id=False)
        self.assertNotEqual(e.participant_id, other.participant_id)
        with self.assertRaises(ValidationError):
            other.write({"user_id": self.portal.id})

    def test_waiting_order_and_manual_offer_deadline(self):
        delivery = self.delivery(capacity=1)
        first = self.enrollment(delivery)
        second = self.enrollment(delivery, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        (first | second).action_wait()
        self.assertEqual(delivery.enrollment_ids.sorted().ids, [first.id, second.id])
        with self.assertRaises(ValidationError):
            first.action_reserve()
        first.action_reserve(fields.Datetime.now() + timedelta(hours=2))
        with self.assertRaises(ValidationError):
            second.action_reserve(fields.Datetime.now() + timedelta(hours=2))
        self.assertEqual(second.state, "waiting")

    def test_transfer_and_replacement_no_admission_or_access_copied(self):
        old = self.admitted()
        old.action_authorize()
        old.action_open_access()
        new = self.enrollment(old.delivery_id, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        old.action_transfer(new.id, replacement=True)
        old.action_transfer(new.id, replacement=True)
        self.assertEqual(old.state, "replaced")
        self.assertEqual(old.access_state, "revoked")
        self.assertEqual(old.successor_id, new)
        self.assertEqual(new.state, "requested")
        self.assertEqual(new.prerequisites, "pending")
        self.assertFalse(new.commercially_authorized)
        self.assertFalse(new.access_end)
        target = self.enrollment(self.delivery(), participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        new.change_reason = "Report requested"
        new.action_transfer(target.id)
        self.assertEqual(new.successor_id, target)
        self.assertEqual(new.state, "cancelled")

    def test_direct_write_context_and_history_protected(self):
        delivery = self.delivery()
        e = self.enrollment(delivery)
        for values in ({"state": "confirmed"}, {"commercially_authorized": True}, {"access_state": "active"}, {"requested_at": "2000-01-01"}, {"participant_id": self.portal_b.partner_id.id}):
            with self.assertRaises(ValidationError):
                e.write(values)
        seeded = self.env["training.enrollment"].with_user(self.coordinator).with_context(default_state="confirmed", default_commercially_authorized=True, default_access_state="active").create({"delivery_id": delivery.id, "participant_id": self.portal_b.partner_id.id, "free_reason": "Fictional invitation"})
        self.assertEqual(seeded.state, "requested")
        self.assertFalse(seeded.commercially_authorized)
        self.assertEqual(seeded.access_state, "unopened")
        operation = delivery.operation_ids[:1]
        self.assertEqual(operation.actor_id, self.coordinator)
        with self.assertRaises(AccessError):
            operation.with_user(self.coordinator).write({"reason": "Changed"})
        with self.assertRaises(AccessError):
            operation.with_user(self.coordinator).unlink()
        with self.assertRaises(ValidationError):
            e.unlink()

    def test_roles_company_exports_and_no_portal_opening(self):
        e = self.enrollment(self.delivery())
        for user in (self.reader, self.internal, self.portal, self.portal_b, self.env.ref("base.public_user")):
            with self.subTest(user=user.login):
                for model in ("training.delivery", "training.seat.allocation", "training.enrollment", "training.operation"):
                    with self.assertRaises(AccessError):
                        self.env[model].with_user(user).search([])
                with self.assertRaises(AccessError):
                    e.with_user(user).action_confirm()
        other_course = self.env["training.course"].create({"name": "B", "company_id": self.other_company.id})
        other_program = self.program.copy({"course_id": other_course.id, "version": "B1", "accessibility_contact_id": self.customer.id})
        other_program.action_validate()
        other = self.env["training.delivery"].create({"name": "B", "company_id": self.other_company.id, "program_id": other_program.id, "kind": "autonomous", "access_policy": "duration", "access_days": 2})
        with self.assertRaises(AccessError):
            other.with_user(self.coordinator).read(["name"])
        with self.assertRaises(AccessError):
            other.with_user(self.coordinator).export_data(["name"])
        with self.assertRaises((AccessError, ValidationError)):
            self.enrollment(other)

    def test_cancellation_threshold_and_immutable_program(self):
        delivery = self.delivery(opening_threshold=3)
        with self.assertRaises(ValidationError):
            delivery.action_confirm()
        delivery.change_reason = "Explicit opening below threshold"
        delivery.action_confirm()
        e = self.admitted(delivery)
        with self.assertRaises(ValidationError):
            delivery.write({"access_days": 20})
        delivery.action_cancel()
        self.assertEqual(e.state, "cancelled")
        self.assertEqual(e.access_state, "revoked")
        self.assertEqual(delivery.state, "cancelled")
        with self.assertRaises(ValidationError):
            self.enrollment(delivery, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)

    def test_expired_lot_bounds_personal_reservation_and_context_company(self):
        delivery = self.delivery(capacity=1)
        lot = self.lot(delivery, quantity=1)
        e = self.enrollment(delivery, allocation_id=lot.id)
        e.action_reserve(lot.expires_at + timedelta(days=1))
        future = lot.expires_at + timedelta(seconds=1)
        with patch("odoo.fields.Datetime.now", return_value=future):
            self.assertFalse(e._occupies())
            self.assertEqual(delivery._occupancy(), 0)
        other = self.env["training.enrollment"].with_user(self.coordinator).with_context(
            default_company_id=self.other_company.id,
            default_program_id=False,
        ).create({"delivery_id": delivery.id, "participant_id": self.portal_b.partner_id.id, "free_reason": "Fictional invitation"})
        self.assertEqual(other.company_id, delivery.company_id)
        self.assertEqual(other.program_id, delivery.program_id)

    def test_terminal_admission_and_financial_independence(self):
        e = self.admitted()
        e.change_reason = "Cancellation, finance reviewed separately"
        e.action_cancel()
        self.assertEqual(e.access_state, "revoked")
        with self.assertRaises(ValidationError):
            e.action_validate_prerequisites()
        with self.assertRaises(ValidationError):
            e.action_suspend_access()
        with self.assertRaises(ValidationError):
            e.action_confirm()
        requested = self.enrollment(self.delivery())
        with self.assertRaises(ValidationError):
            requested.action_close()

    def test_native_forms_and_parameter_wizard(self):
        from odoo.tests import Form
        offer = Form(self.env["training.delivery"].with_user(self.coordinator))
        offer.name = "Fictional native offer"
        offer.program_id = self.program
        offer.kind = "autonomous"
        offer.access_policy = "duration"
        offer.access_days = 4
        delivery = offer.save()
        enrollment_form = Form(self.env["training.enrollment"].with_user(self.coordinator).with_context(default_delivery_id=delivery.id))
        enrollment_form.participant_id = self.portal.partner_id
        enrollment_form.user_id = self.portal
        enrollment_form.free_reason = "Fictional invitation"
        e = enrollment_form.save()
        action = e.action_open_operation()
        wizard_form = Form(self.env[action["res_model"]].with_user(self.coordinator).with_context(action["context"]))
        wizard_form.deadline = fields.Datetime.now() + timedelta(days=1)
        wizard_form.reason = "Manual place proposal"
        wizard_form.save().action_apply()
        self.assertEqual(e.state, "reserved")
        self.assertTrue(e.reservation_end)

    def test_french_delivery_and_access_labels(self):
        from odoo.tools.translate import load_language
        load_language(self.cr, "fr_FR")
        model = self.env["training.enrollment"].with_context(lang="fr_FR")
        state = dict(model.fields_get(["state"])["state"]["selection"])
        self.assertEqual(state["requested"], "Demandée")
        self.assertEqual(state["confirmed"], "Confirmée")
        self.assertEqual(self.env.ref("training_management.action_training_deliveries").with_context(lang="fr_FR").name, "Réalisations")
