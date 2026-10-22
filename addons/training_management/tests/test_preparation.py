from datetime import datetime

from odoo import Command
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
        second.action_confirm(reason="Explicit coordinator exception")
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
        third.action_confirm(reason="Confirmed exception to unavailability")
        self.assertTrue(unavailable.active)
        with self.assertRaises((AccessError, ValidationError)):
            session.with_user(self.portal).action_change()

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
