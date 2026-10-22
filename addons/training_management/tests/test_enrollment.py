import json
from datetime import timedelta
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import Command, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


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
        enrollment.action_validate_prerequisites(reason="Manual review / B2B deferred payment decision")
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
        e.action_authorize(reason="Fictional commercial decision")
        self.assertEqual(e.effective_access, "unopened")
        e.action_open_access(reason="Fictional opening")
        original_end = e.access_end
        e.action_open_access(reason="Fictional repeated opening")
        self.assertEqual(e.access_end, original_end)
        self.assertEqual(e.effective_access, "active")
        self.assertEqual(e._effective_state(original_end), "expired")
        e.action_suspend_access(reason="Fictional suspension")
        self.assertEqual(e.effective_access, "suspended")
        e.action_open_access(reason="Fictional resumption")
        self.assertEqual(e.access_end, original_end)
        e.action_revoke_authorization(reason="Fictional withdrawal")
        self.assertEqual(e.effective_access, "blocked")
        e.action_authorize(reason="Fictional new decision")
        e.action_extend_access(original_end + timedelta(days=3), reason="Fictional extension")
        self.assertEqual(e.access_end, original_end + timedelta(days=3))
        self.assertTrue(e.delivery_id.operation_ids.filtered(lambda row: 'access_end' in row.after))
        e.action_revoke_access(reason="Fictional revocation")
        with self.assertRaises(ValidationError):
            e.action_open_access(reason="Fictional reopening")

    def test_fixed_access_scheduled_and_disabled_account(self):
        now = fields.Datetime.now()
        e = self.admitted(self.delivery(access_policy="fixed", access_start=now + timedelta(days=1), access_end=now + timedelta(days=3)))
        e.action_authorize(reason="Fictional commercial decision")
        e.action_open_access(reason="Fictional opening")
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
        old.action_authorize(reason="Fictional commercial decision")
        old.action_open_access(reason="Fictional opening")
        new = self.enrollment(old.delivery_id, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        old.action_replace(new.id, reason="Fictional replacement")
        old.action_replace(new.id, reason="Fictional replacement")
        self.assertEqual(old.state, "replaced")
        self.assertEqual(old.access_state, "revoked")
        self.assertEqual(old.successor_id, new)
        self.assertEqual(new.state, "requested")
        self.assertEqual(new.prerequisites, "pending")
        self.assertFalse(new.commercially_authorized)
        self.assertFalse(new.access_end)
        target = self.enrollment(self.delivery(), participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        new.action_postpone(target.id, reason="Report requested")
        self.assertEqual(new.successor_id, target)
        self.assertEqual(new.state, "postponed")

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
        delivery.action_confirm(reason="Explicit opening below threshold")
        e = self.admitted(delivery)
        with self.assertRaises(ValidationError):
            delivery.write({"access_days": 20})
        with self.assertRaises(ValidationError):
            delivery.action_cancel()
        delivery.action_cancel(reason="Fictional cancellation")
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
        e.action_cancel(reason="Cancellation, finance reviewed separately")
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


@tagged("post_install", "-at_install")
class TestReasonPerAction(EnrollmentCase):
    """S03.1 §1: every motivated action takes its own reason, kept nowhere but the history."""

    def reasons(self, record):
        rows = record.delivery_id.operation_ids if record._name != "training.delivery" else record.operation_ids
        return rows.filtered(lambda row: row.model_name == record._name and row.record_id == record.id).mapped("reason")

    def test_two_decisions_two_reasons_and_no_stored_reason(self):
        e = self.enrollment(self.delivery())
        for model in ("training.delivery", "training.seat.allocation", "training.enrollment", "training.controlled"):
            self.assertNotIn("change_reason", self.env[model]._fields)
        e.action_validate_prerequisites(reason="First decision")
        with self.assertRaises(ValidationError):
            e.action_waive_prerequisites()
        with self.assertRaises(ValidationError):
            e.action_waive_prerequisites(reason="   ")
        self.assertEqual(e.prerequisites, "validated")
        e.action_waive_prerequisites(reason="Second decision")
        self.assertEqual(e.prerequisites, "waived")
        reasons = self.reasons(e)
        self.assertIn("First decision", reasons)
        self.assertIn("Second decision", reasons)
        e.action_confirm()
        with self.assertRaises(ValidationError):
            e.action_authorize()
        self.assertFalse(e.commercially_authorized)
        e.action_authorize(reason="Third decision")
        with self.assertRaises(ValidationError):
            e.action_open_access()
        self.assertEqual(e.access_state, "unopened")

    def test_delivery_and_lot_actions_need_a_reason_each_time(self):
        delivery = self.delivery()
        lot = self.lot(delivery)
        with self.assertRaises(ValidationError):
            lot.action_release_places(2)
        lot.action_release_places(2, reason="Release for another delivery")
        with self.assertRaises(ValidationError):
            lot.action_release_places(1)
        with self.assertRaises(ValidationError):
            lot.action_cancel()
        lot.action_cancel(reason="Lot withdrawn")
        self.assertEqual(lot.state, "cancelled")
        self.assertEqual(self.reasons(lot)[:2], ["Lot withdrawn", "Release for another delivery"])
        delivery.action_confirm()
        delivery.action_start()
        delivery.action_deliver()
        with self.assertRaises(ValidationError):
            delivery.action_close()
        delivery.action_close(reason="Delivery finished")
        self.assertEqual(delivery.state, "closed")
        self.assertIn("Delivery finished", self.reasons(delivery))

    def test_reason_assistant_only_calls_listed_public_actions(self):
        e = self.enrollment(self.delivery())
        wizard_model = self.env["training.action.reason"].with_user(self.coordinator)
        wizard = wizard_model.create({"res_model": e._name, "res_ids": str(e.id),
                                      "action_name": "action_validate_prerequisites", "reason": "Assistant decision"})
        self.assertEqual(wizard.target_count, 1)
        self.assertEqual(wizard.action_label, self.env._("Validate Prerequisites"))
        wizard.action_apply()
        self.assertEqual(e.prerequisites, "validated")
        self.assertIn("Assistant decision", self.reasons(e))
        blank = wizard_model.create({"res_model": e._name, "res_ids": str(e.id),
                                     "action_name": "action_waive_prerequisites", "reason": "  "})
        with self.assertRaises(ValidationError):
            blank.action_apply()
        for values in ({"res_model": e._name, "action_name": "unlink"}, {"res_model": e._name, "action_name": "write"},
                       {"res_model": "res.partner", "action_name": "action_archive"}):
            with self.subTest(values=values):
                bad = wizard_model.create({**values, "res_ids": str(e.id), "reason": "Forbidden"})
                with self.assertRaises(ValidationError):
                    bad.action_apply()
        gone = wizard_model.create({"res_model": e._name, "res_ids": "0",
                                    "action_name": "action_waive_prerequisites", "reason": "Missing"})
        with self.assertRaises(ValidationError):
            gone.action_apply()
        for user in (self.reader, self.internal, self.portal):
            with self.assertRaises(AccessError):
                e.with_user(user).action_open_reason()
        action = e.with_user(self.coordinator).with_context(reason_action="action_cancel").action_open_reason()
        self.assertEqual(action["res_model"], "training.action.reason")
        with self.assertRaises(ValidationError):
            e.with_user(self.coordinator).with_context(reason_action="unlink").action_open_reason()


@tagged("post_install", "-at_install")
class TestLifecycleAndAccess(EnrollmentCase):
    """S03.1 §2: closure, postponement and idempotent withdrawals."""

    def test_closure_requires_settled_enrollments(self):
        for setup in ("requested", "waiting", "reserved"):
            with self.subTest(state=setup):
                delivery = self.delivery()
                pending = self.enrollment(delivery)
                if setup == "waiting":
                    pending.action_wait()
                elif setup == "reserved":
                    pending.action_reserve(fields.Datetime.now() + timedelta(days=1))
                self.assertEqual(pending.state, setup)
                delivery.action_confirm()
                delivery.action_start()
                delivery.action_deliver()
                with self.assertRaises(ValidationError):
                    delivery.action_close(reason="Fictional closure")
                self.assertEqual(delivery.state, "delivered")
                pending.action_cancel(reason="Request withdrawn")
                delivery.action_close(reason="Fictional closure")
                self.assertEqual(delivery.state, "closed")

    def test_closure_closes_confirmed_enrollments_and_revokes_access(self):
        delivery = self.delivery()
        confirmed = self.admitted(delivery)
        confirmed.action_authorize(reason="Fictional commercial decision")
        confirmed.action_open_access(reason="Fictional opening")
        delivery.action_confirm()
        delivery.action_start()
        delivery.action_deliver()
        delivery.action_close(reason="Fictional closure")
        self.assertEqual(delivery.state, "closed")
        self.assertEqual(confirmed.state, "closed")
        self.assertEqual(confirmed.access_state, "revoked")
        self.assertNotEqual(confirmed.effective_access, "active")
        rows = delivery.operation_ids.filtered(lambda row: row.model_name == "training.enrollment" and row.record_id == confirmed.id)
        self.assertEqual(rows[:1].reason, "Fictional closure")

    def test_closed_or_cancelled_delivery_blocks_effective_access(self):
        e = self.admitted()
        e.action_authorize(reason="Fictional commercial decision")
        e.action_open_access(reason="Fictional opening")
        self.assertEqual(e._effective_state(), "active")
        for state in ("closed", "cancelled"):
            models.BaseModel.write(e.delivery_id, {"state": state})
            e.invalidate_recordset()
            self.assertEqual(e._effective_state(), "blocked", state)

    def test_postponement_has_its_own_terminal_state(self):
        e = self.admitted()
        e.action_authorize(reason="Fictional commercial decision")
        e.action_open_access(reason="Fictional opening")
        target = self.enrollment(self.delivery())
        with self.assertRaises(ValidationError):
            e.action_postpone(target.id)
        e.action_postpone(target.id, reason="Moved to a later session")
        self.assertEqual(e.state, "postponed")
        self.assertEqual(e.access_state, "revoked")
        self.assertEqual(e.successor_id, target)
        self.assertEqual(target.state, "requested")
        self.assertEqual(target.prerequisites, "pending")
        self.assertFalse(target.commercially_authorized)
        with self.assertRaises(ValidationError):
            e.action_validate_prerequisites(reason="Terminal")
        with self.assertRaises(ValidationError):
            e.action_cancel(reason="Terminal")
        replaced_source = self.admitted()
        replacement = self.enrollment(replaced_source.delivery_id, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        replaced_source.action_replace(replacement.id, reason="Another person attends")
        self.assertEqual(replaced_source.state, "replaced")

    def test_withdrawals_are_guarded_and_idempotent(self):
        delivery = self.delivery()
        e = self.admitted(delivery)
        e.action_authorize(reason="Fictional commercial decision")
        e.action_revoke_authorization(reason="First withdrawal")
        rows = len(delivery.operation_ids)
        e.action_revoke_authorization(reason="Second withdrawal")
        e.action_revoke_authorization()
        self.assertEqual(len(delivery.operation_ids), rows)
        e.action_revoke_access(reason="First revocation")
        rows = len(delivery.operation_ids)
        e.action_revoke_access(reason="Second revocation")
        e.action_revoke_access()
        self.assertEqual(len(delivery.operation_ids), rows)
        requested = self.enrollment(self.delivery())
        with self.assertRaises(ValidationError):
            requested.action_revoke_access(reason="Never opened")
        self.assertEqual(requested.access_state, "unopened")
        cancelled = self.admitted()
        cancelled.action_authorize(reason="Fictional commercial decision")
        cancelled.action_cancel(reason="Cancelled before the session")
        self.assertTrue(cancelled.commercially_authorized)
        with self.assertRaises(ValidationError):
            cancelled.action_revoke_authorization(reason="Terminal enrollment")
        cancelled.action_revoke_access(reason="Already revoked")


@tagged("post_install", "-at_install")
class TestReservationDeadlineAndUniqueness(EnrollmentCase):
    """S03.1 §3: deadline extension and the database-level open enrollment guard."""

    def test_extend_deadline_of_a_live_reservation(self):
        delivery = self.delivery()
        lot = self.lot(delivery)
        old = lot.expires_at
        new = old + timedelta(days=3)
        with self.assertRaises(ValidationError):
            lot.action_extend_deadline(new)
        with self.assertRaises(ValidationError):
            lot.action_extend_deadline(old - timedelta(hours=1), reason="Earlier than the current deadline")
        with self.assertRaises(ValidationError):
            lot.action_extend_deadline(None, reason="No new deadline")
        lot.action_extend_deadline(new, reason="Customer asked for time")
        self.assertEqual(lot.expires_at, new)
        row = delivery.operation_ids.filtered(lambda r: r.model_name == "training.seat.allocation" and r.record_id == lot.id)[:1]
        self.assertEqual(row.reason, "Customer asked for time")
        self.assertEqual(json.loads(row.before)["expires_at"], str(old))
        self.assertEqual(json.loads(row.after)["expires_at"], str(new))

    def test_extension_refused_for_expired_or_cancelled_lots(self):
        delivery = self.delivery()
        lot = self.lot(delivery, quantity=2)
        cancelled = self.lot(delivery, quantity=2, source_reference="CANCELLED")
        cancelled.action_cancel(reason="Lot withdrawn")
        with self.assertRaises(ValidationError):
            cancelled.action_extend_deadline(fields.Datetime.now() + timedelta(days=9), reason="Too late")
        future = lot.expires_at + timedelta(seconds=1)
        with patch("odoo.fields.Datetime.now", return_value=future):
            with self.assertRaises(ValidationError):
                lot.action_extend_deadline(future + timedelta(days=1), reason="Already expired")
            lot.action_expire()
            with self.assertRaises(ValidationError):
                lot.action_extend_deadline(future + timedelta(days=1), reason="Expired and recorded")
        self.assertEqual(lot.state, "expired")

    def test_extension_assistant_and_rights(self):
        from odoo.tests import Form
        lot = self.lot(self.delivery())
        old = lot.expires_at
        action = lot.action_open_extend()
        self.assertEqual(action["res_model"], "training.allocation.extend")
        form = Form(self.env[action["res_model"]].with_user(self.coordinator).with_context(action["context"]))
        form.expires_at = lot.expires_at + timedelta(days=1)
        form.reason = "Two more days"
        form.save().action_apply()
        self.assertEqual(lot.expires_at, old + timedelta(days=1))
        for user in (self.reader, self.internal, self.portal):
            with self.assertRaises(AccessError):
                lot.with_user(user).action_extend_deadline(lot.expires_at + timedelta(days=1), reason="Forbidden")

    def test_database_refuses_two_open_enrollments_for_one_person(self):
        delivery = self.delivery()
        first = self.enrollment(delivery)
        values = {"delivery_id": delivery.id, "company_id": delivery.company_id.id, "participant_id": first.participant_id.id}
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                # Bypass the model checks to prove the database guard itself.
                models.BaseModel.create(self.env["training.enrollment"], [values])
        first.action_cancel(reason="Request withdrawn")
        second = self.enrollment(delivery)
        self.assertEqual(second.state, "requested")
        self.assertEqual(first.state, "cancelled")


@tagged("post_install", "-at_install")
class TestChangeDates(EnrollmentCase):
    def session(self, **values):
        start = fields.Datetime.now() + timedelta(days=20)
        return self.delivery(kind="session", start_at=start, end_at=start + timedelta(hours=7), **values)

    def test_dates_change_is_motivated_and_journaled(self):
        delivery = self.session()
        old_start, old_end = delivery.start_at, delivery.end_at
        with self.assertRaises(ValidationError):
            delivery.action_change_dates(start_at=old_start + timedelta(days=1), end_at=old_end + timedelta(days=1))
        delivery.action_change_dates(start_at=old_start + timedelta(days=1), end_at=old_end + timedelta(days=1), reason="Trainer unavailable")
        self.assertEqual(delivery.start_at, old_start + timedelta(days=1))
        row = delivery.operation_ids.sorted("id")[-1]
        self.assertEqual(row.reason, "Trainer unavailable")
        self.assertIn("start_at", row.before)
        self.assertIn("start_at", row.after)
        count = len(delivery.operation_ids)
        delivery.action_change_dates(start_at=delivery.start_at)
        self.assertEqual(len(delivery.operation_ids), count, "An unchanged value leaves no journal line")

    def test_frozen_fields_and_states(self):
        delivery = self.session()
        e = self.enrollment(delivery)
        with self.assertRaises(ValidationError):
            delivery.write({"start_at": delivery.start_at + timedelta(days=1)})
        with self.assertRaises(ValidationError):
            delivery.write({"capacity": 0, "program_id": self.program.id})
        stored = e.access_end
        delivery.action_change_dates(start_at=delivery.start_at + timedelta(days=2), end_at=delivery.end_at + timedelta(days=2), reason="Room change")
        self.assertEqual(e.access_end, stored, "Computed access periods are never rewritten")
        autonomous = self.delivery()
        with self.assertRaises(ValidationError):
            autonomous.action_change_dates(start_at=fields.Datetime.now(), end_at=fields.Datetime.now() + timedelta(hours=1), reason="Not applicable")
        cancelled = self.session()
        cancelled.action_cancel(reason="Cancelled offer")
        with self.assertRaises(ValidationError):
            cancelled.action_change_dates(start_at=cancelled.start_at + timedelta(days=1), end_at=cancelled.end_at + timedelta(days=1), reason="Too late")

    def test_fixed_access_follows_and_cannot_shrink_under_active_access(self):
        now = fields.Datetime.now()
        delivery = self.delivery(access_policy="fixed", access_start=now + timedelta(days=1), access_end=now + timedelta(days=10))
        delivery.action_change_dates(access_end=now + timedelta(days=12), reason="Longer access")
        self.assertEqual(delivery.access_end, now + timedelta(days=12))
        e = self.admitted(delivery)
        e.action_authorize(reason="Authorized")
        e.action_open_access(reason="Opened")
        self.assertEqual(e.access_state, "active")
        with self.assertRaises(ValidationError):
            delivery.action_change_dates(access_end=now + timedelta(days=5), reason="Shorter")
        delivery.action_change_dates(access_end=now + timedelta(days=15), reason="Extended again")

    def test_assistant_and_rights(self):
        from odoo.tests import Form
        delivery = self.session()
        action = delivery.action_open_dates()
        self.assertEqual(action["res_model"], "training.delivery.dates")
        form = Form(self.env[action["res_model"]].with_user(self.coordinator).with_context(action["context"]))
        form.start_at = delivery.start_at + timedelta(days=1)
        form.end_at = delivery.end_at + timedelta(days=1)
        form.reason = "New room"
        form.save().action_apply()
        self.assertEqual(delivery.operation_ids.sorted("id")[-1].reason, "New room")
        for user in (self.reader, self.internal, self.portal):
            with self.assertRaises(AccessError):
                delivery.with_user(user).action_change_dates(start_at=delivery.start_at + timedelta(days=1), end_at=delivery.end_at + timedelta(days=1), reason="Forbidden")
