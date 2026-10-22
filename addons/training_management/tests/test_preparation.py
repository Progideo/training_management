import json
from datetime import datetime, timedelta

from lxml import html

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, JsonRpcException, new_test_user, tagged
from odoo.tools import mute_logger

from .test_enrollment import EnrollmentCase
from ..models.training_schedule import local_instant


@tagged("post_install", "-at_install")
class PreparationCase(EnrollmentCase):
    """ORG01/02 and SEC01/02 under actual restricted identities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coordinator.email = "coord@example.invalid"
        cls.portal.partner_id.write({"email": "trainer@example.invalid", "tz": "Europe/Paris"})
        cls.portal_b.partner_id.write({"email": "person@example.invalid", "tz": "America/Montreal"})
        cls.other_coordinator = new_test_user(
            cls.env,
            login="s04_other_coord",
            groups="training_management.group_training_coordinator,base.group_allow_export",
            company_ids=[Command.set(cls.company.ids)],
        )

    def planned(self, **values):
        delivery = self.delivery(
            kind="session", start_at="2027-01-01 00:00:00", end_at="2027-02-01 00:00:00", timezone="UTC", **values
        )
        session = (
            self.env["training.session"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional S04 session",
                    "delivery_id": delivery.id,
                    "instructor_id": self.portal.partner_id.id,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/room",
                    "start_date": "2027-01-04",
                    "end_date": "2027-01-04",
                    "start_hour": 9,
                    "end_hour": 12,
                }
            )
        )
        return delivery, session

    def adaptation(self, delivery):
        enrollment = self.enrollment(delivery, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id)
        enrollment.action_validate_prerequisites(reason="Fictional review")
        enrollment.action_confirm()
        return (
            self.env["training.adaptation"]
            .with_user(self.coordinator)
            .create(
                {
                    "delivery_id": delivery.id,
                    "enrollment_id": enrollment.id,
                    "details": "SECRET S04 request",
                    "decision": "Fictional arrangement accepted",
                    "instructor_instruction": "Useful instruction only",
                }
            )
        )


@tagged("post_install", "-at_install")
class TestPreparation(PreparationCase):
    def test_native_forms_batch_and_single_confirmation(self):
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        action = delivery.action_add_sessions()
        with Form(
            self.env["training.session.edit"].with_user(self.coordinator).with_context(**action["context"])
        ) as wizard:
            wizard.name = "Three fictional sessions"
            wizard.start_date = "2027-01-04"
            wizard.instructor_id = self.portal.partner_id
            wizard.mode = "remote"
            wizard.meeting_url = "https://example.invalid/room"
            wizard.repeat_count = 3
        wizard.record.action_apply()
        self.assertEqual(len(delivery.session_ids), 3)
        delivery.action_confirm()
        self.assertEqual(delivery.state, "confirmed")
        self.assertFalse(delivery.invitation_ids)
        self.assertEqual(self.delivery().action_confirm(), True, "Autonomous: no fictitious session")
        with self.assertRaises(ValidationError):
            self.env["training.session"].with_user(self.coordinator).create(
                {
                    "name": "Fictitious",
                    "delivery_id": self.delivery().id,
                    "start_date": "2027-01-04",
                    "end_date": "2027-01-04",
                }
            )

    def test_local_time_gap_fold_and_server_instants(self):
        with self.assertRaises(ValueError):
            local_instant("2027-03-28", 2.5, "Europe/Paris")
        with self.assertRaises(ValueError):
            local_instant("2027-10-31", 2.5, "Europe/Paris")
        first = local_instant("2027-10-31", 2.5, "Europe/Paris", "first")
        second = local_instant("2027-10-31", 2.5, "Europe/Paris", "second")
        self.assertEqual((second - first).total_seconds(), 3600)
        self.assertEqual(local_instant("2027-01-04", 9, "Europe/Paris"), datetime(2027, 1, 4, 8))
        delivery, session = self.planned()
        with self.assertRaises(ValidationError):
            delivery.write({"timezone": "Europe/Paris"})
        self.assertEqual(session.start_at, datetime(2027, 1, 4, 9))

    def test_conflict_refusal_exception_modification_and_unavailability(self):
        first, _session = self.planned()
        first.action_confirm()
        second, session = self.planned()
        with self.assertRaises(ValidationError):
            second.action_confirm()
        second.action_confirm(conflict_reason="Explicit coordinator exception")
        self.assertTrue(second.operation_ids.filtered(lambda row: "conflicts" in (row.after or "")))
        with self.assertRaises(ValidationError):
            session.write({"start_hour": 10})
        with self.assertRaises(ValidationError):
            session._apply_schedule({"start_hour": 10})
        session._apply_schedule({"start_hour": 13, "end_hour": 15}, "New time")
        self.assertEqual(session.start_hour, 13)
        unavailable = (
            self.env["training.unavailability"]
            .with_user(self.coordinator)
            .create(
                {
                    "instructor_id": self.portal.partner_id.id,
                    "start_at": "2027-01-05 09:00:00",
                    "end_at": "2027-01-05 12:00:00",
                }
            )
        )
        third, third_session = self.planned()
        third_session.write({"start_date": "2027-01-05", "end_date": "2027-01-05"})
        with self.assertRaises(ValidationError):
            third.action_confirm()
        third.action_confirm(conflict_reason="Confirmed exception to unavailability")
        self.assertTrue(unavailable.active)
        with self.assertRaises((AccessError, ValidationError)):
            session.with_user(self.portal).action_change()

    def test_below_threshold_confirmation_needs_a_distinct_resource_exception(self):
        first, _first_session = self.planned()
        delivery, session = self.planned(opening_threshold=5, capacity=10)
        opening_reason = "Approved opening for a small group"
        exception_reason = "Explicitly agreed shared instructor"
        self.assertTrue(delivery.below_threshold)
        other, other_session = self.planned()
        other_session.write({"start_date": "2027-01-05", "end_date": "2027-01-05"})
        action = (other | delivery).with_context(reason_action="action_confirm").action_open_reason()
        with Form(
            self.env["training.action.reason"].with_user(self.coordinator).with_context(**action["context"])
        ) as form:
            form.reason = opening_reason
        wizard = form.record
        self.assertFalse(wizard.conflict_description)
        first.action_confirm()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            delivery.action_confirm(reason=opening_reason)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            delivery.action_confirm(conflict_reason=exception_reason)
        self.assertEqual(delivery.state, "preparation")
        self.assertFalse(delivery.operation_ids.filtered(lambda item: "conflicts" in (item.after or "")))
        action = wizard.action_apply()
        self.assertEqual(action["res_id"], wizard.id, "Keep the same confirmation assistant")
        self.assertEqual(delivery.state, "preparation")
        self.assertEqual(other.state, "preparation", "The entire confirmation batch is rolled back")
        self.assertEqual(wizard.reason, opening_reason, "No re-entry of the opening reason")
        self.assertIn(self.portal.partner_id.name, wizard.conflict_description)
        self.assertIn("UTC", wizard.conflict_description)
        self.assertFalse(delivery.operation_ids.filtered(lambda item: "conflicts" in (item.after or "")))
        with Form(wizard) as form:
            form.conflict_reason = exception_reason
        self.assertEqual(wizard.action_apply()["type"], "ir.actions.act_window_close")
        self.assertEqual(delivery.state, "confirmed")
        self.assertEqual(other.state, "confirmed")
        self.assertEqual(first.state, "confirmed")
        conflicts = delivery.operation_ids.filtered(lambda item: "conflicts" in (item.after or ""))
        self.assertEqual(conflicts.reason, exception_reason)
        self.assertIn("Resource conflicts: 1", conflicts.changes)
        # The web client reloads the whole delivery after closing the wizard,
        # including the computed, human-readable operation history.
        reread = delivery.web_read({"state": {}, "operation_ids": {"fields": {"changes": {}, "reason": {}}}})
        self.assertEqual(reread[0]["state"], "confirmed")
        self.assertTrue(any(item["reason"] == exception_reason for item in reread[0]["operation_ids"]))
        self.assertTrue(
            delivery.operation_ids.filtered(
                lambda item: '"confirmed"' in (item.after or "") and item.reason == opening_reason
            )
        )
        self.assertTrue(session._conflicts())
        self.assertFalse(delivery.invitation_ids, "Confirmation never sends invitations")
        with self.assertRaises(AccessError):
            wizard.with_user(self.portal).action_apply()

    def test_confirmation_without_conflict_keeps_one_apply_and_no_extra_reason(self):
        delivery, _session = self.planned(opening_threshold=5, capacity=10)
        action = delivery.with_context(reason_action="action_confirm").action_open_reason()
        with Form(
            self.env["training.action.reason"].with_user(self.coordinator).with_context(**action["context"])
        ) as form:
            form.reason = "Approved opening for a small group"
        wizard = form.record
        self.assertTrue(wizard.reason_required)
        self.assertFalse(wizard.conflict_description)
        self.assertEqual(wizard.action_apply()["type"], "ir.actions.act_window_close")
        self.assertEqual(delivery.state, "confirmed")
        self.assertFalse(wizard.conflict_reason)
        self.assertFalse(delivery.invitation_ids)
        other, other_session = self.planned()
        other_session.write({"start_date": "2027-01-05", "end_date": "2027-01-05"})
        self.assertTrue(other.action_confirm(), "Ordinary confirmation remains a single action")

    def test_resource_only_confirmation_does_not_require_an_opening_reason(self):
        first, _session = self.planned()
        first.action_confirm()
        delivery, _second_session = self.planned()
        action = delivery.with_context(reason_action="action_confirm").action_open_reason()
        with Form(
            self.env["training.action.reason"].with_user(self.coordinator).with_context(**action["context"])
        ) as form:
            self.assertFalse(form.reason_required)
            self.assertIn(self.portal.partner_id.name, form.conflict_description)
            form.conflict_reason = "Explicit resource exception above threshold"
        wizard = form.record
        self.assertEqual(wizard.action_apply()["type"], "ir.actions.act_window_close")
        self.assertEqual(delivery.state, "confirmed")
        self.assertFalse(wizard.reason)
        self.assertFalse(delivery.invitation_ids)

    def test_edit_reason_is_not_a_resource_exception_and_wizard_keeps_inputs(self):
        first, first_session = self.planned()
        first.action_confirm()
        second, session = self.planned()
        session.write({"start_hour": 13, "end_hour": 15})
        second.action_confirm()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            session._apply_schedule({"start_hour": 9}, "Customer requested a new time")
        self.assertEqual(session.start_hour, 13)
        with Form(
            self.env["training.session.edit"]
            .with_user(self.coordinator)
            .with_context(**session.action_change()["context"])
        ) as form:
            form.start_hour = 9
            form.reason = "Customer requested a new time"
        wizard = form.record
        action = wizard.action_apply()
        self.assertEqual(action["res_id"], wizard.id, "Conflict stays in the same assistant")
        self.assertEqual(session.start_hour, 13, "Refused edit is rolled back")
        self.assertEqual(wizard.start_hour, 9, "No re-entry of the requested schedule")
        self.assertIn(self.portal.partner_id.name, wizard.conflict_description)
        self.assertIn("UTC", wizard.conflict_description)
        self.assertFalse(second.invitation_ids)
        with Form(wizard) as form:
            form.conflict_reason = "Explicitly agreed shared instruction"
        action = wizard.action_apply()
        self.assertEqual(action["res_model"], "training.invitation.send")
        self.assertEqual(session.start_hour, 9)
        exceptions = second.operation_ids.filtered(lambda item: "conflicts" in (item.after or ""))
        self.assertEqual(exceptions.reason, "Explicitly agreed shared instruction")
        self.assertFalse(second.invitation_ids, "Recipient proposal never sends")
        # A subsequent ordinary edit has no extra step or retained exception.
        with Form(
            self.env["training.session.edit"]
            .with_user(self.coordinator)
            .with_context(**session.action_change()["context"])
        ) as form:
            form.start_hour = 16
            form.end_hour = 17
            form.reason = "New non-conflicting time"
        self.assertEqual(form.record.action_apply()["res_model"], "training.invitation.send")
        self.assertEqual(first_session.start_hour, 9)

    def test_conflicting_addition_is_atomic_and_needs_its_own_exception(self):
        delivery, session = self.planned()
        delivery.action_confirm()
        action = session.action_duplicate_session()
        with Form(
            self.env["training.session.edit"].with_user(self.coordinator).with_context(**action["context"])
        ) as form:
            form.name = "Fictional repeated additions"
            form.repeat_count = 2
            form.reason = "Additional customer request"
        wizard = form.record
        before = len(delivery.operation_ids)
        self.assertEqual(wizard.action_apply()["res_id"], wizard.id)
        self.assertEqual(len(delivery.session_ids), 1)
        self.assertEqual(len(delivery.operation_ids), before)
        with Form(wizard) as form:
            form.conflict_reason = "Explicit coordinator exception for shared resources"
        wizard.action_apply()
        self.assertEqual(len(delivery.session_ids), 3)
        self.assertTrue(delivery.operation_ids.filtered(lambda item: "conflicts" in (item.after or "")))
        with self.assertRaises(AccessError):
            wizard.with_user(self.portal).action_apply()

    def test_conflict_can_be_corrected_in_place_without_an_exception(self):
        delivery, session = self.planned()
        delivery.action_confirm()
        with Form(
            self.env["training.session.edit"]
            .with_user(self.coordinator)
            .with_context(**session.action_duplicate_session()["context"])
        ) as form:
            form.reason = "Additional customer request"
        wizard = form.record
        self.assertEqual(wizard.action_apply()["res_id"], wizard.id)
        self.assertTrue(wizard.conflict_description)
        with Form(wizard) as form:
            form.start_hour = 13
            form.end_hour = 15
            self.assertFalse(form.conflict_description)
            self.assertFalse(form.conflict_reason)
        self.assertFalse(wizard.conflict_description)
        self.assertEqual(wizard.action_apply()["res_model"], "training.invitation.send")
        self.assertEqual(len(delivery.session_ids), 2)
        self.assertFalse(delivery.operation_ids.filtered(lambda item: "conflicts" in (item.after or "")))
        self.assertFalse(delivery.invitation_ids)

    def test_confidential_recursive_and_history_exports_are_audited(self):
        delivery, _session = self.planned()
        adaptation = self.adaptation(delivery)
        history = self.env["training.adaptation.history"].with_user(self.coordinator)
        domain = [("adaptation_id", "=", adaptation.id), ("event", "=", "export")]
        for record, paths in (
            (adaptation, ["details"]),
            (delivery, ["name", "adaptation_ids/details"]),
            (adaptation.history_ids, ["after"]),
            (delivery, ["adaptation_ids/history_ids/after"]),
        ):
            before = history.search_count(domain)
            result = record.export_data(paths)
            self.assertIn("SECRET S04 request", str(result))
            events = history.search(domain)
            self.assertGreater(len(events), before)
            manifest = json.loads(events[0].before)
            self.assertIn(manifest["model"], ("training.adaptation", "training.adaptation.history"))
            self.assertTrue(manifest["records"])
            self.assertTrue(manifest["fields"])
            self.assertEqual(events[0].actor_id, self.coordinator)
        for record in (adaptation, adaptation.history_ids):
            with self.assertRaises(AccessError):
                record.with_user(self.other_coordinator).export_data(["id"])
        self.assertNotIn(
            "SECRET S04 request",
            str(delivery.with_user(self.other_coordinator).export_data(["adaptation_ids/details"])),
        )

    def test_schedule_return_is_a_new_dispatch_but_retries_are_idempotent(self):
        delivery, session = self.planned()
        self.adaptation(delivery)
        delivery.action_confirm()
        invitations = self.env["training.invitation"].with_user(self.coordinator)
        recipients = invitations._recipients(delivery)
        self.assertEqual(invitations._queue(delivery, recipients), 2)
        original = delivery.invitation_ids.sudo().mail_id
        original.write({"state": "sent"})  # Queue lifecycle only; no SMTP send.
        session._apply_schedule({"start_hour": 10}, "Change to B")
        self.assertEqual(invitations._queue(delivery, recipients), 2)
        delivery.invitation_ids.sudo().mail_id.write({"state": "sent"})
        session._apply_schedule({"start_hour": 9}, "Return to A")
        self.assertEqual(invitations._queue(delivery, recipients), 2)
        self.assertEqual(invitations._queue(delivery, recipients), 0)
        self.assertEqual(len(delivery.invitation_ids), 6)
        self.assertEqual(set(delivery.invitation_ids.mapped("dispatch_number")), {1, 2, 3})
        latest = delivery.invitation_ids.filtered(lambda item: item.dispatch_number == 3).sudo().mail_id
        latest.write({"state": "exception"})
        self.assertEqual(invitations._queue(delivery, recipients), 0)
        self.assertEqual(set(latest.mapped("state")), {"outgoing"})
        for mail in original:
            with self.assertRaises(ValidationError):
                mail._prepare_outgoing_list()
        for mail in latest:
            self.assertTrue(mail._prepare_outgoing_list())

    def test_room_capacity_commitments_and_no_double_counting(self):
        delivery, session = self.planned()
        room = (
            self.env["resource.resource"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional S04 room",
                    "resource_type": "material",
                    "training_room": True,
                    "training_capacity": 10,
                    "company_id": self.company.id,
                }
            )
        )
        session.write({"room_id": room.id})
        self.lot(delivery, quantity=10)
        self.assertEqual(delivery.occupied_seats, 10)
        with self.assertRaises(ValidationError):
            room.with_user(self.coordinator).write({"training_capacity": 9})
        delivery.action_confirm()
        with self.assertRaises(ValidationError):
            delivery.action_change_dates(start_at="2027-01-05", reason="Too narrow")
        self.assertEqual(delivery.program_id, self.program)
        self.assertEqual(delivery.occupied_seats, 10)

    def test_confidential_dossier_history_exports_attachments_and_revocation(self):
        delivery, _session = self.planned()
        adaptation = self.adaptation(delivery)
        for user in (self.portal, self.portal_b, self.reader, self.internal, self.other_coordinator):
            with self.assertRaises(AccessError):
                adaptation.with_user(user).read(["details"])
            if user == self.other_coordinator:
                self.assertFalse(adaptation.with_user(user).search([("id", "=", adaptation.id)]))
            else:
                with self.assertRaises(AccessError):
                    adaptation.with_user(user).search([("id", "=", adaptation.id)])
        with self.assertRaises(AccessError):
            delivery.with_user(self.other_coordinator).write({"adaptation_referent_id": self.other_coordinator.id})
        adaptation.write({"details": "SECRET revised", "decision": "Revised decision"})
        self.assertEqual(len(adaptation.history_ids), 2)
        self.assertEqual(adaptation.history_ids[0].actor_id, self.coordinator)
        adaptation.export_data(["details"])
        self.assertEqual(adaptation.history_ids.sorted("id")[-1].event, "export")
        with self.assertRaises(AccessError):
            adaptation.history_ids[0].write({"after": "tampered"})
        attachment = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Private fictional file",
                    "res_model": "training.adaptation",
                    "res_id": adaptation.id,
                    "raw": b"SECRET file",
                }
            )
        )
        with self.assertRaises(AccessError):
            attachment.with_user(self.other_coordinator).read(["raw"])
        delivery.write({"adaptation_deputy_id": self.other_coordinator.id})
        self.assertEqual(adaptation.with_user(self.other_coordinator).details, "SECRET revised")
        delivery.write({"adaptation_deputy_id": False})
        with self.assertRaises(AccessError):
            adaptation.with_user(self.other_coordinator).read(["details"])
        self.assertFalse(any("SECRET" in (row.after or "") for row in delivery.operation_ids))
        enrollment = adaptation.enrollment_id
        enrollment.write(
            {
                "participant_objectives": "Specific practice",
                "positioning": "Beginner",
                "instructor_summary": "Use introductory exercises",
            }
        )
        self.assertEqual(enrollment.prerequisites, "validated")
        self.assertEqual(enrollment.access_state, "unopened")

    def test_room_only_conflict_jointive_sessions_and_batch_confirmation(self):
        first, first_session = self.planned()
        room = (
            self.env["resource.resource"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional shared room",
                    "resource_type": "material",
                    "training_room": True,
                    "company_id": self.company.id,
                }
            )
        )
        first_session.write({"room_id": room.id})
        second, second_session = self.planned()
        second_session.write({"room_id": room.id, "instructor_id": self.portal_b.partner_id.id})
        first.action_confirm()
        with self.assertRaises(ValidationError):
            second.action_confirm()
        second_session.write({"start_hour": 12, "end_hour": 14})
        second.action_confirm()
        self.assertEqual(second.state, "confirmed", "Jointive room reservations are permitted")
        third, third_session = self.planned()
        fourth, fourth_session = self.planned()
        for session in third_session | fourth_session:
            session.write({"start_date": "2027-01-06", "end_date": "2027-01-06"})
        with self.assertRaises(ValidationError):
            (third | fourth).action_confirm()
        self.assertEqual((third | fourth).mapped("state"), ["preparation", "preparation"])

    def test_foreign_company_cannot_read_sessions_or_confidential_history(self):
        delivery, session = self.planned()
        adaptation = self.adaptation(delivery)
        foreign = new_test_user(
            self.env,
            login="s04_foreign_coordinator",
            groups="training_management.group_training_coordinator,base.group_allow_export",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        for record, field in ((session, "name"), (adaptation, "details"), (adaptation.history_ids, "after")):
            with self.assertRaises(AccessError):
                record.with_user(foreign).read([field])
            with self.assertRaises(AccessError):
                record.with_user(foreign).export_data([field])
        self.assertFalse(self.env["training.session"].with_user(foreign).search([]))

    def test_rpc_defaults_cannot_inject_generated_values_or_email_attachments(self):
        delivery, session = self.planned()
        with self.assertRaises(ValidationError):
            delivery.write({"kind": "autonomous"})
        delivery.write({"timezone": "UTC"})
        generated = (
            self.env["training.session"]
            .with_user(self.coordinator)
            .with_context(
                default_cancelled=True,
                default_start_at="2030-01-01",
                default_company_id=self.other_company.id,
                default_timezone="Europe/Paris",
            )
            .create(
                {
                    "name": "Fictional safe defaults",
                    "delivery_id": delivery.id,
                    "instructor_id": self.portal.partner_id.id,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/room",
                    "start_date": "2027-01-05",
                    "end_date": "2027-01-05",
                    "start_hour": 9,
                    "end_hour": 12,
                }
            )
        )
        self.assertFalse(generated.cancelled)
        self.assertEqual(generated.start_at, datetime(2027, 1, 5, 9))
        self.assertEqual(generated.company_id, self.company)
        self.assertEqual(generated.timezone, "UTC")
        attachment = self.env["ir.attachment"].create({"name": "Must not be sent", "raw": b"FORBIDDEN DEFAULT FILE"})
        delivery.action_confirm()
        invitations = (
            self.env["training.invitation"]
            .with_user(self.coordinator)
            .with_context(
                default_email_cc="unselected@example.invalid", default_attachment_ids=[Command.link(attachment.id)]
            )
        )
        invitations._queue(delivery, self.portal.partner_id)
        for mail in delivery.invitation_ids.sudo().mail_id:
            self.assertFalse(mail.email_cc)
            self.assertFalse(mail.attachment_ids)
            self.assertNotIn("FORBIDDEN DEFAULT FILE", mail.body_html)
            self.assertTrue(mail._prepare_outgoing_list())

    def test_invitation_control_local_time_idempotence_and_error_retry(self):
        delivery, session = self.planned()
        adaptation = self.adaptation(delivery)
        with self.assertRaises(ValidationError):
            self.env["training.invitation"].with_user(self.coordinator)._queue(delivery, self.portal.partner_id)
        delivery.action_confirm()
        model = self.env["training.invitation"].with_user(self.coordinator)
        recipients = model._recipients(delivery)
        self.assertEqual(model._queue(delivery, recipients), 2)
        self.assertEqual(model._queue(delivery, recipients), 0)
        self.assertEqual(len(delivery.invitation_ids), 2)
        mails = delivery.invitation_ids.sudo().mail_id
        self.assertEqual(set(mails.mapped("state")), {"outgoing"})
        for mail in mails:
            self.assertTrue(mail._prepare_outgoing_list())
        self.assertTrue(all(not mail.email_cc and not mail.recipient_cc_ids for mail in mails))
        self.assertTrue(
            all("SECRET" not in mail.body_html and "Useful instruction" not in mail.body_html for mail in mails)
        )
        self.assertEqual(
            set(delivery.invitation_ids.mapped("recipient_timezone")), {"Europe/Paris", "America/Montreal"}
        )
        mails[0].write({"state": "exception"})
        model._queue(delivery, recipients)
        self.assertEqual(mails[0].state, "outgoing")
        session._apply_schedule({"start_hour": 10}, "Fictional schedule update")
        self.assertEqual(len(delivery.invitation_ids), 2, "Editing does not send")
        for mail in mails:
            with self.assertRaises(ValidationError):
                mail._prepare_outgoing_list()
        self.assertEqual(model._queue(delivery, recipients), 2)
        with self.assertRaises(AccessError):
            model._queue(delivery, self.customer)
        self.assertEqual(adaptation.enrollment_id.access_state, "unopened")


@tagged("post_install", "-at_install")
class TestTrainerPortal(HttpCase, PreparationCase):
    """Real HTTP portal; no model access granted as a shortcut."""

    def test_http_all_assigned_sessions_are_reachable_with_upcoming_default(self):
        today = fields.Datetime.now().date()
        delivery = self.delivery(
            kind="session", start_at=today - timedelta(days=2), end_at=today + timedelta(days=203), timezone="UTC"
        )
        sessions = (
            self.env["training.session"]
            .with_user(self.coordinator)
            .create(
                [
                    {
                        "name": "Fictional upcoming %03d" % offset,
                        "delivery_id": delivery.id,
                        "instructor_id": self.portal.partner_id.id,
                        "mode": "remote",
                        "meeting_url": "https://example.invalid/room",
                        "start_date": today + timedelta(days=offset),
                        "end_date": today + timedelta(days=offset),
                        "start_hour": 9,
                        "end_hour": 12,
                    }
                    for offset in range(1, 202)
                ]
            )
        )
        past = (
            self.env["training.session"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional past session",
                    "delivery_id": delivery.id,
                    "instructor_id": self.portal.partner_id.id,
                    "mode": "remote",
                    "meeting_url": "https://example.invalid/room",
                    "start_date": today - timedelta(days=1),
                    "end_date": today - timedelta(days=1),
                    "start_hour": 9,
                    "end_hour": 12,
                }
            )
        )
        delivery.action_confirm()
        hidden, hidden_session = self.planned()
        self.authenticate(self.portal.login, self.portal.login)
        seen = set()
        for page in range(1, 7):
            response = self.url_open("/my/training-sessions/page/%s" % page)
            self.assertEqual(response.status_code, 200)
            tree = html.fromstring(response.text)
            ids = {int(link.rsplit("/", 1)[1]) for link in tree.xpath("//ul[contains(@class, 'list-group')]//a/@href")}
            self.assertLessEqual(len(ids), 40)
            self.assertFalse(seen & ids)
            seen |= ids
            self.assertNotIn(past.id, ids)
            self.assertNotIn(hidden_session.id, ids)
        self.assertEqual(seen, set(sessions.ids), "Every one of the 201 upcoming sessions is reachable")
        response = self.url_open("/my/training-sessions?filterby=past")
        self.assertIn("Fictional past session", response.text)
        self.assertNotIn("Fictional upcoming", response.text)
        response = self.url_open("/my/training-sessions/page/6?filterby=all")
        self.assertIn(sessions[-1].name, response.text)
        self.assertIn("filterby=all", response.text, "Pagination preserves the chosen period")
        self.assertEqual(self.url_open("/my/training-sessions/%s" % sessions[-1].id).status_code, 200)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertNotIn("Fictional upcoming", self.url_open("/my/training-sessions?filterby=all").text)
        self.assertEqual(self.url_open("/my/training-sessions/%s" % sessions[-1].id).status_code, 404)

    def test_http_assigned_session_and_private_content_refusals(self):
        delivery, session = self.planned()
        adaptation = self.adaptation(delivery)
        adaptation.enrollment_id.write({"instructor_summary": "AUTHORIZED POSITIONING SUMMARY"})
        delivery.action_confirm()
        attachment = (
            self.env["ir.attachment"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "S04 private HTTP file",
                    "res_model": "training.adaptation",
                    "res_id": adaptation.id,
                    "raw": b"SECRET HTTP FILE",
                    "mimetype": "text/plain",
                }
            )
        )
        download_url = "/web/content/%s?access_token=%s" % (attachment.id, attachment.generate_access_token()[0])
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open("/my/training-sessions/%s" % session.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Useful instruction only", response.text)
        self.assertIn("AUTHORIZED POSITIONING SUMMARY", response.text)
        self.assertNotIn("SECRET S04 request", response.text)
        self.assertNotEqual(self.url_open(download_url, allow_redirects=False).status_code, 200)
        for model, record_id, field in (
            ("training.session", session.id, "name"),
            ("training.adaptation", adaptation.id, "details"),
        ):
            with self.assertRaises(JsonRpcException), mute_logger("odoo.http"):
                self.make_jsonrpc_request(
                    "/web/dataset/call_kw/%s/read" % model,
                    {"model": model, "method": "read", "args": [[record_id], [field]], "kwargs": {}},
                )
        self.assertNotEqual(
            self.url_open("/my/training-sessions/%s" % session.id, data={"name": "Tampered"}).status_code, 200
        )

        self.authenticate(self.coordinator.login, self.coordinator.login)
        self.assertEqual(self.url_open(download_url).status_code, 200)
        self.authenticate(self.portal_b.login, self.portal_b.login)
        response = self.url_open("/my/training-sessions/%s" % session.id)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("Useful instruction only", response.text)
        self.authenticate(self.portal.login, self.portal.login)
        session.write(
            {"instructor_id": self.portal_b.partner_id.id}
        ) if delivery.state == "preparation" else session._apply_schedule(
            {"instructor_id": self.portal_b.partner_id.id}, "Fictional reassignment"
        )
        response = self.url_open("/my/training-sessions/%s" % session.id)
        self.assertEqual(response.status_code, 404)
