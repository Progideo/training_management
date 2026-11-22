"""P16 preparation: current S03 facts, no public/commercial/consent inference."""

from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, new_test_user, tagged

from .test_enrollment import EnrollmentCase


def prepare_session(delivery):
    start = (delivery.start_at + timedelta(minutes=1)).replace(second=0, microsecond=0)
    end = start + timedelta(minutes=30)
    start = start.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(delivery.timezone))
    end = end.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(delivery.timezone))
    delivery.env["training.session"].create(
        {
            "name": "Fictional private planning",
            "delivery_id": delivery.id,
            "instructor_id": delivery.env.user.partner_id.id,
            "mode": "onsite",
            "location": "Fictional private classroom",
            "start_date": start.date(),
            "end_date": end.date(),
            "start_hour": start.hour + start.minute / 60,
            "end_hour": end.hour + end.minute / 60,
        }
    )


@tagged("post_install", "-at_install")
class TestSessionPublicationPreparation(EnrollmentCase):
    def facts(self, delivery, user=None):
        return (
            self.env["training.session.publication.service"]
            .with_user(user or self.coordinator)
            ._session_facts(delivery)
        )

    def test_lot_and_unnamed_places_use_s03_once(self):
        delivery = self.delivery()
        lot = self.lot(delivery)
        for index in range(7):
            person = self.env["res.partner"].create({"name": "Fictional P16 %s" % index})
            self.enrollment(delivery, participant_id=person.id, user_id=False, allocation_id=lot.id).action_reserve()
        facts = self.facts(delivery)
        self.assertEqual((facts["capacity"], facts["occupied_seats"], facts["remaining_seats"]), (10, 10, 0))
        self.assertFalse({"public_state", "guaranteed", "subscribed", "published"} & facts.keys())

    def test_reservation_expiry_is_evaluated_at_server_time(self):
        now = fields.Datetime.now()
        delivery = self.delivery()
        self.lot(delivery, expires_at=now + timedelta(hours=1))
        self.assertEqual(self.facts(delivery)["remaining_seats"], 0)
        with patch.object(fields.Datetime, "now", return_value=now + timedelta(hours=1)):
            facts = self.facts(delivery)
        self.assertEqual(facts["remaining_seats"], 10)
        self.assertEqual(facts["checked_at"], now + timedelta(hours=1))
        self.assertEqual(delivery.allocation_ids.state, "reserved")

    def test_free_place_expiry_and_unlimited_capacity(self):
        now = fields.Datetime.now()
        delivery = self.delivery(capacity=0)
        enrollment = self.enrollment(delivery)
        enrollment.action_reserve(expires_at=now + timedelta(hours=1))
        facts = self.facts(delivery)
        self.assertIsNone(facts["remaining_seats"])
        self.assertEqual(facts["occupied_seats"], 1)
        with patch.object(fields.Datetime, "now", return_value=now + timedelta(hours=1)):
            self.assertEqual(self.facts(delivery)["occupied_seats"], 0)

    def test_dates_and_internal_confirmation_are_only_facts(self):
        start = fields.Datetime.now() + timedelta(days=4)
        delivery = self.delivery(
            kind="session", start_at=start, end_at=start + timedelta(hours=2), timezone="Europe/Paris"
        )
        prepare_session(delivery)
        delivery.action_confirm()
        facts = self.facts(delivery)
        self.assertEqual((facts["kind"], facts["state"], facts["program_state"]), ("session", "confirmed", "validated"))
        self.assertEqual(
            (facts["start_at"], facts["end_at"], facts["timezone"]), (start, start + timedelta(hours=2), "Europe/Paris")
        )
        self.assertFalse(facts["catalogue_approved"])
        self.assertTrue(facts["course_active"])
        delivery.action_cancel(reason="Fictional cancellation")
        self.assertEqual(self.facts(delivery)["state"], "cancelled")

    def test_diagnostic_has_no_delivery_history_or_mail_side_effect(self):
        delivery = self.delivery()
        before = (
            delivery.revision,
            self.env["training.operation"].search_count([]),
            self.env["mail.mail"].search_count([]),
        )
        first = self.facts(delivery)
        self.assertEqual(
            first.keys(),
            {
                "checked_at",
                "kind",
                "state",
                "program_state",
                "catalogue_approved",
                "course_active",
                "start_at",
                "end_at",
                "timezone",
                "capacity",
                "occupied_seats",
                "remaining_seats",
            },
        )
        self.facts(delivery)
        self.assertEqual(
            before,
            (
                delivery.revision,
                self.env["training.operation"].search_count([]),
                self.env["mail.mail"].search_count([]),
            ),
        )

    def test_restricted_roles_and_sudo_do_not_bypass_actor(self):
        delivery = self.delivery()
        for user in (self.reader, self.internal, self.portal, self.portal_b, self.env.ref("base.public_user")):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.facts(delivery.sudo(), user)
                with self.assertRaises(AccessError):
                    delivery.with_user(user).action_inspect_session_availability()
                with self.assertRaises(AccessError):
                    self.env["training.session.publication.inspection"].with_user(user).create(
                        {"delivery_id": delivery.id}
                    )
        user = new_test_user(
            self.env,
            login="p16_other_coord",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        with self.assertRaises(AccessError):
            self.facts(delivery.sudo(), user)
        with self.assertRaises(AccessError):
            self.env["training.session.publication.service"].with_user(user).sudo()._session_facts(delivery.sudo())

    def test_native_form_in_coordinator_company(self):
        delivery = self.delivery(capacity=0)
        action = delivery.action_inspect_session_availability()
        model = self.env[action["res_model"]].with_user(self.coordinator).with_context(**action["context"])
        with Form(model) as form:
            self.assertEqual(form.delivery_id, delivery)
            self.assertTrue(form.unlimited)
            self.assertFalse(form.dated_session)
            self.assertEqual(form.occupied_seats, 0)


class SessionAlertCase(EnrollmentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality = new_test_user(cls.env, login="p16_quality", groups="training_management.group_training_quality")
        cls.policy = (
            cls.env["training.retention.category"]
            .with_user(cls.quality)
            .create(
                {
                    "name": "Fictional P16 policy",
                    "purpose": "Voluntary date alerts",
                    "responsible_id": cls.quality.id,
                    "duration_days": 90,
                    "archive_policy": "Private archive",
                    "deletion_policy": "Manual review",
                }
            )
        )
        cls.policy.action_approve()
        names = (
            "title",
            "objectives",
            "target_audience",
            "prerequisites",
            "content",
            "duration_hours",
            "delivery_mode",
            "teaching_methods",
            "evaluation_criteria",
            "access_conditions",
            "accessibility_information",
        )
        cls.public_program = (
            cls.env["training.program.version"]
            .with_user(cls.coordinator)
            .create(
                {
                    **{key: cls.program[key] for key in names},
                    "course_id": cls.course.id,
                    "version": "P16-PUBLIC",
                    "language_id": cls.env.ref("base.lang_en").id,
                    "accessibility_contact_id": cls.customer.id,
                    "public_catalogue": True,
                }
            )
        )
        cls.public_program.action_validate()
        cls.public_program.action_publish()
        cls.portal.partner_id.email = "p16-owner@example.invalid"

    def dated_delivery(self, **values):
        start = fields.Datetime.now() + timedelta(days=10)
        return self.delivery(
            program_id=self.public_program.id,
            kind="session",
            start_at=start,
            end_at=start + timedelta(hours=2),
            **values,
        )

    def subscribe(self, user=None):
        return (
            self.env["training.session.alert.subscription"]
            .with_user(user or self.portal)
            ._subscribe(
                self.public_program.sudo(),
                accepted=True,
                definition=self.env["training.session.alert.subscription"]
                .with_user(user or self.portal)
                ._definition(self.public_program.sudo()),
            )
        )

    def notices(self, delivery):
        return self.env["training.session.alert.notice"].search([("delivery_id", "=", delivery.id)])


@tagged("post_install", "-at_install")
class TestPublicSessionRules(SessionAlertCase):
    def test_private_until_decided_and_no_guarantee_from_confirmation(self):
        delivery = self.dated_delivery()
        self.assertFalse(delivery._session_public_row())
        prepare_session(delivery)
        delivery.action_confirm()
        self.assertFalse(delivery._session_public_row())
        delivery.action_publish_session(reason="Public inter-company session approved")
        self.assertEqual(delivery._session_public_row()["status"], "confirmed")
        # Confirmation is the single public commitment; there is no separate guarantee.
        self.assertTrue(delivery._session_public_row()["confirmed"])
        self.assertNotIn("guaranteed", delivery._session_public_row())
        self.assertFalse(hasattr(delivery, "action_guarantee_session"))

    def test_public_location_seats_left_and_next_session_fact(self):
        delivery = self.dated_delivery(capacity=4, public_location="Fictional City")
        delivery.action_publish_session(reason="Fictional publication")
        row = delivery._session_public_row()
        self.assertEqual((row["location"], row["seats_left"], row["few_seats"]), ("Fictional City", 4, False))
        self.lot(delivery, quantity=2)
        row = delivery._session_public_row()
        self.assertEqual((row["seats_left"], row["few_seats"]), (2, True))
        self.company.training_few_seats_threshold = 0
        self.assertFalse(delivery._session_public_row()["few_seats"])
        course = self.public_program.course_id
        facts = course.sudo()._catalogue_facts(self.company)[course.id]
        live = self.public_program.delivery_mode in ("onsite", "remote", "blended")
        self.assertEqual((facts["live"], facts["elearning"]), (live, not live))
        self.assertEqual(facts["next_session"]["location"], "Fictional City")
        self.assertEqual(facts["next_session"]["start_at"], delivery.start_at)
        unlimited = self.dated_delivery(capacity=0)
        unlimited.action_publish_session(reason="Fictional publication")
        self.assertIsNone(unlimited._session_public_row()["seats_left"])

    def test_complete_and_expired_reservations_are_live(self):
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="Fictional publication")
        self.assertEqual(delivery._session_public_row()["status"], "open")
        now = fields.Datetime.now()
        self.lot(delivery, expires_at=now + timedelta(hours=1))
        self.assertEqual(delivery._session_public_row()["status"], "full")
        with patch.object(fields.Datetime, "now", return_value=now + timedelta(hours=1)):
            self.assertEqual(delivery._session_public_row()["status"], "open")
        with self.assertRaises(ValidationError):
            self.lot(delivery, quantity=1, source_reference="OVER")

    def test_dates_withdraw_publication_and_guarantee_without_new_alert(self):
        self.subscribe()
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="Approved")
        first = delivery.session_first_published_at
        delivery.action_change_dates(
            start_at=delivery.start_at + timedelta(days=1),
            end_at=delivery.end_at + timedelta(days=1),
            reason="Rescheduled",
        )
        self.assertFalse(delivery._session_public_row())
        delivery.action_publish_session(reason="Reviewed new dates")
        self.assertEqual(delivery.session_first_published_at, first)
        self.assertEqual(len(self.notices(delivery)), 1)
        delivery.write({"timezone": delivery.timezone, "program_id": delivery.program_id.id})
        self.assertTrue(delivery._session_public_row())
        delivery.write({"timezone": "America/Montreal"})
        self.assertFalse(delivery._session_public_row())

    def test_retirement_cancellation_start_and_sales_close_hide_session(self):
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="Approved")
        delivery.action_close_session_sales(reason="Closed commercially")
        self.assertFalse(delivery._session_public_row())
        delivery.action_publish_session(reason="Reopen")
        with patch.object(fields.Datetime, "now", return_value=delivery.start_at):
            self.assertFalse(delivery._session_public_row())
        self.public_program.action_retire()
        self.assertFalse(delivery._session_public_row())
        delivery.action_cancel(reason="Cancelled")
        self.assertFalse(delivery._session_public_row())

    def test_no_direct_fields_or_context_injection_and_real_restricted_roles(self):
        delivery = self.dated_delivery()
        for key, value in (
            ("session_public", True),
            ("session_sales_open", True),
            ("session_first_published_at", fields.Datetime.now()),
        ):
            with self.assertRaises(ValidationError):
                delivery.write({key: value})
            with self.assertRaises(ValidationError):
                self.dated_delivery(**{key: value})
            with self.assertRaises(ValidationError):
                self.delivery_context_injection(key, value)
        for user in (self.reader, self.internal, self.portal, self.quality, self.env.ref("base.public_user")):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                delivery.with_user(user).action_publish_session(reason="Forbidden")
        with self.assertRaises(ValidationError):
            delivery.action_publish_session()
        with self.assertRaises(ValidationError):
            self.delivery().action_publish_session(reason="Autonomous")

    def delivery_context_injection(self, key, value):
        return (
            self.env["training.delivery"]
            .with_user(self.coordinator)
            .with_context(**{"default_" + key: value})
            .create(
                {
                    "name": "Fictional",
                    "program_id": self.public_program.id,
                    "kind": "autonomous",
                    "access_policy": "duration",
                    "access_days": 2,
                }
            )
        )


@tagged("post_install", "-at_install")
class TestSessionDateAlerts(SessionAlertCase):
    def test_unconfirmed_visitor_requests_are_cleaned_after_60_days(self):
        # Technical cleanup (22 November 2026): a never confirmed request is no consent.
        model = self.env["training.session.alert.subscription"]
        program = self.public_program.sudo()

        def request(email):
            model._request_by_email(program, email, accepted=True, definition=model._definition(program))
            return model.sudo().search([("email", "=", email)])

        stale, recent, former = (
            request(e) for e in ("stale@example.invalid", "recent@example.invalid", "former@example.invalid")
        )
        former._confirm_by_token()
        former._unsubscribe_by_token()
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE training_session_alert_subscription SET confirmation_requested_at = now() - interval '61 days'"
            " WHERE id IN %s",
            [(stale.id, former.id)],
        )
        self.env.invalidate_all()
        done, remaining = model._gc_unconfirmed_requests()
        self.assertEqual((done, remaining), (1, False))
        self.assertFalse(stale.exists())
        self.assertTrue(recent.exists() and former.exists())
        self.assertEqual(model._gc_unconfirmed_requests(), (0, False))
        # Every consent stays evidence, even after unsubscribing: only an administrator deletes it.
        with self.assertRaises(ValidationError):
            former.with_user(self.env.ref("base.public_user")).sudo().unlink()

    def test_explicit_consent_required_without_retention_policy(self):
        # Retention is the operator's matter (21 November 2026): no policy is required nor recorded.
        model = self.env["training.session.alert.subscription"].with_user(self.portal)
        with self.assertRaises(ValidationError):
            model._subscribe(self.public_program.sudo(), accepted=False)
        sub = self.subscribe()
        self.assertTrue(sub.active_consent)
        self.assertFalse(sub.retention_id)
        with self.assertRaises(AccessError):
            self.subscribe(self.env.ref("base.public_user"))

    def test_single_recipient_address_required(self):
        for address in (False, "invalid", "p16@example.invalid, second@example.invalid"):
            self.portal.partner_id.email = address
            with self.subTest(address=address), self.assertRaises(ValidationError):
                self.subscribe()
        self.assertFalse(self.env["training.session.alert.subscription"].search([("owner_id", "=", self.portal.id)]))

    def test_stale_terms_and_operator_membership_are_refused(self):
        model = self.env["training.session.alert.subscription"].with_user(self.portal)
        with self.assertRaises(ValidationError):
            model._subscribe(self.public_program.sudo(), accepted=True, definition="stale")
        outsider = new_test_user(
            self.env,
            login="p16_other_operator",
            groups="training_management.group_training_coordinator",
            company_id=self.other_company.id,
            company_ids=[Command.set(self.other_company.ids)],
        )
        with self.assertRaises(AccessError):
            self.subscribe(outsider)
        with self.assertRaises(AccessError):
            self.dated_delivery().with_user(outsider).action_publish_session(reason="Forbidden")
        group = self.env.ref("sales_team.group_sale_salesman", raise_if_not_found=False)
        if group:
            seller = new_test_user(self.env, login="p16_sales_only", groups="sales_team.group_sale_salesman")
            with self.assertRaises(AccessError):
                self.dated_delivery().with_user(seller).action_publish_session(reason="Forbidden")

    def test_native_transport_refuses_revoked_consent(self):
        sub = self.subscribe()
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="After consent")
        notice = self.notices(delivery)
        sub._unsubscribe()
        with (
            patch.object(
                type(self.env["ir.mail_server"]), "send_email", side_effect=AssertionError("Unexpected transport")
            ) as transport,
            patch.object(type(self.env["ir.mail_server"]), "_disable_send", return_value=False),
        ):
            # Native public send is neutralized by Odoo tests; exercise the
            # actual send loop with a dummy session and forbidden SMTP transport.
            notice.mail_id._send(smtp_session=object())
            self.assertFalse(transport.called)
        self.assertEqual(notice.mail_id.state, "exception")

    def test_once_and_no_history_replay(self):
        previous = self.dated_delivery()
        previous.action_publish_session(reason="Before consent")
        sub = self.subscribe()
        self.assertEqual(sub, self.subscribe())
        self.assertFalse(self.notices(previous))
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="After consent")
        delivery.action_publish_session(reason="Repeat")
        notice = self.notices(delivery)
        self.assertEqual(len(notice), 1)
        self.assertTrue(notice._authorized())
        self.assertTrue(notice.mail_id)
        delivery.action_withdraw_session(reason="Withdraw")
        self.assertFalse(notice._authorized())
        delivery.action_publish_session(reason="Republish")
        self.assertEqual(self.notices(delivery), notice)

    def test_unsubscribe_blocks_queued_transport_and_resubscribe_does_not_revive_it(self):
        sub = self.subscribe()
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="After consent")
        notice = self.notices(delivery)
        sub._unsubscribe()
        sub._unsubscribe()
        self.assertFalse(sub.active_consent)
        self.assertEqual(self.env["training.session.alert.event"].search_count([("subscription_id", "=", sub.id)]), 2)
        with self.assertRaises(ValidationError):
            notice.mail_id._prepare_outgoing_list()
        self.subscribe()
        self.assertFalse(notice._authorized())
        new = self.dated_delivery()
        new.action_publish_session(reason="New session after resubscription")
        self.assertTrue(self.notices(new)._authorized())

    def test_owner_and_privacy_do_not_inherit_employer_or_orm_access(self):
        sub = self.subscribe()
        self.portal_b.partner_id.parent_id = self.portal.partner_id
        with self.assertRaises(AccessError):
            sub.with_user(self.portal_b).sudo()._unsubscribe()
        for name in (
            "training.session.alert.subscription",
            "training.session.alert.event",
            "training.session.alert.notice",
        ):
            with self.assertRaises(AccessError):
                self.env[name].with_user(self.portal).search([])
            with self.assertRaises(AccessError):
                self.env[name].with_user(self.coordinator).create({})
        with self.assertRaises(ValidationError):
            self.env["ir.attachment"].create(
                {"name": "Forbidden", "res_model": sub._name, "res_id": sub.id, "raw": b"private"}
            )

    def test_transport_rechecks_current_email_and_exact_envelope(self):
        self.subscribe()
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="After consent")
        notice = self.notices(delivery)
        mail = notice.mail_id
        self.assertFalse(mail.email_cc or mail.recipient_ids or mail.attachment_ids)
        self.assertNotIn(delivery.name, mail.body_html)
        original = self.portal.partner_id.email
        self.portal.partner_id.email = "p16-changed@example.invalid"
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()
        self.portal.partner_id.email = original
        mail.write({"email_cc": "intruder@example.invalid"})
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()


@tagged("post_install", "-at_install")
class TestSessionDatesHttp(SessionAlertCase, HttpCase):
    def test_consent_page_shows_no_retention_policy(self):
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open("/formations/%s/date-alert" % self.public_program.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Finalité", response.text)
        self.assertNotIn("90 jours", response.text)
        self.assertNotIn("politique", response.text.lower())

    def test_public_projection_and_authenticated_consent_withdrawal(self):
        from lxml import html

        delivery = self.dated_delivery(name="PRIVATE_P16_CUSTOMER_GROUP", timezone="Europe/Paris")
        url = "/formations/%s/sessions" % self.public_program.id
        self.authenticate(None, None)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Aucune session publique", response.text)
        delivery.action_publish_session(reason="Approved public session")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ouverte", response.text)
        self.assertIn("Europe/Paris", response.text)
        self.assertNotIn(delivery.name, response.text)
        self.assertNotIn(self.portal.partner_id.name, response.text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn("Départ garanti sur décision", response.text)
        self.authenticate(self.portal.login, self.portal.login)
        consent_url = "/formations/%s/date-alert" % self.public_program.id
        response = self.url_open(consent_url)
        self.assertEqual(response.status_code, 200)
        tree = html.fromstring(response.content)
        self.assertFalse(tree.xpath("//input[@name='accepted']/@checked"))
        for private_text in (self.policy.purpose, self.policy.archive_policy, self.policy.deletion_policy):
            self.assertNotIn(private_text, response.text)
        token = tree.xpath("//input[@name='csrf_token']/@value")[0]
        definition = tree.xpath("//input[@name='definition']/@value")[0]
        response = self.url_open(consent_url, data={"csrf_token": token, "definition": definition})
        self.assertEqual(response.status_code, 400)
        response = self.url_open(consent_url, data={"csrf_token": token, "definition": definition, "accepted": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Alerte active", response.text)
        tree = html.fromstring(response.content)
        form = tree.xpath("//form[contains(@action, '/unsubscribe')]")[0]
        unsubscribe = form.get("action")
        token = form.xpath(".//input[@name='csrf_token']/@value")[0]
        self.authenticate(self.portal_b.login, self.portal_b.login)
        self.assertEqual(self.url_open(unsubscribe, data={"csrf_token": self.csrf_token()}).status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        self.assertEqual(self.url_open(unsubscribe, data={"csrf_token": self.csrf_token()}).status_code, 200)
        sub = self.env["training.session.alert.subscription"].search([("owner_id", "=", self.portal.id)])
        self.assertFalse(sub.active_consent)
        response = self.url_open("/my/training-date-alerts")
        tree = html.fromstring(response.content)
        self.assertEqual(tree.xpath("//a[normalize-space()='Me réabonner']/@href"), [consent_url])
        revision = sub.revision
        response = self.url_open(consent_url)
        tree = html.fromstring(response.content)
        self.assertFalse(tree.xpath("//input[@name='accepted']/@checked"))
        sub.invalidate_recordset()
        self.assertFalse(sub.active_consent)
        definition = tree.xpath("//input[@name='definition']/@value")[0]
        values = {"csrf_token": self.csrf_token(), "definition": definition}
        self.assertEqual(self.url_open(consent_url, data=values).status_code, 400)
        response = self.url_open(consent_url, data=dict(values, accepted="yes"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Me réabonner", response.text)
        sub.invalidate_recordset()
        self.assertTrue(sub.active_consent)
        self.assertEqual(sub.revision, revision + 1)
        self.assertEqual(self.env[sub._name].search_count([("owner_id", "=", self.portal.id)]), 1)
        self.url_open(unsubscribe, data={"csrf_token": self.csrf_token()})
        delivery.action_cancel(reason="Fictional cancellation")
        self.authenticate(None, None)
        self.assertIn("Aucune session publique", self.url_open(url).text)
        self.public_program.action_retire()
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate(self.portal.login, self.portal.login)
        self.assertNotIn("Me réabonner", self.url_open("/my/training-date-alerts").text)
        self.assertEqual(self.url_open(consent_url).status_code, 404)

    def test_french_consent_and_notice_are_translated(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(["training_management"], ["fr_FR"])
        self.portal.partner_id.lang = "fr_FR"
        if "website" in self.env and "language_ids" in self.env["website"]._fields:
            french = self.env.ref("base.lang_fr")
            self.env["website"].search([]).write(
                {"language_ids": [Command.set(french.ids)], "default_lang_id": french.id}
            )
        self.authenticate(self.portal.login, self.portal.login)
        response = self.url_open("/formations/%s/date-alert" % self.public_program.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Je souhaite recevoir un courriel", response.text)
        self.assertNotIn("I wish to receive an email", response.text)
        sub = self.env["training.session.alert.subscription"].with_user(self.portal).with_context(lang="fr_FR")
        sub._subscribe(
            self.public_program.sudo(), accepted=True, definition=sub._definition(self.public_program.sudo())
        )
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="Publication fictive")
        notice = self.notices(delivery)
        self.assertEqual(notice.mail_id.subject, "De nouvelles dates de formation sont disponibles")

    def test_visitor_double_opt_in_and_unsubscribe_from_the_email(self):
        from freezegun import freeze_time
        from lxml import html

        def form(url, **values):
            tree = html.fromstring(self.url_open(url).content)
            data = {"csrf_token": tree.xpath("//input[@name='csrf_token']/@value")[0]}
            definition = tree.xpath("//input[@name='definition']/@value")
            if definition:
                data["definition"] = definition[0]
            return tree, {**data, **values}

        model = self.env["training.session.alert.subscription"]
        url = "/formations/%s/date-alert" % self.public_program.id
        self.authenticate(None, None)
        tree, data = form(url)
        self.assertTrue(tree.xpath("//input[@name='email'][@type='email']"))
        self.assertFalse(tree.xpath("//input[@name='accepted']/@checked"))
        self.assertEqual(self.url_open(url, data={**data, "email": "visitor@example.invalid"}).status_code, 400)
        self.assertEqual(
            self.url_open(url, data={**data, "email": "not an address", "accepted": "yes"}).status_code, 400
        )
        response = self.url_open(url, data={**data, "email": " Visitor@Example.invalid ", "accepted": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Confirmez votre alerte", response.text)
        sub = model.search([("email", "=", "visitor@example.invalid")])
        self.assertEqual((len(sub), sub.active_consent, sub.owner_id), (1, False, self.env["res.users"]))
        mail = sub.confirmation_mail_id
        self.assertEqual(mail.email_to, "visitor@example.invalid")
        self.assertFalse(mail.recipient_ids)
        link = "/formations/date-alert/confirm/%s" % sub.sudo().access_token
        self.assertIn(link, mail.body_html)
        self.assertTrue(sub._confirmation_authorized(mail))
        # The transport accepts the confirmation, and only it (pending request, requested address).
        self.assertTrue(mail._prepare_outgoing_list())
        # A repeated request neither tells whether the address is known nor sends another email.
        repeated = self.url_open(url, data={**data, "email": "visitor@example.invalid", "accepted": "yes"})
        self.assertEqual(repeated.status_code, response.status_code)
        # The website layout contains per-request tokens. Compare the public message itself.
        pages = [html.fromstring(result.content).xpath("//div[@id='wrap']/p") for result in (response, repeated)]
        self.assertEqual([len(page) for page in pages], [1, 1])
        self.assertEqual(pages[0][0].text_content(), pages[1][0].text_content())
        self.assertEqual(sub.confirmation_mail_id, mail)
        self.assertEqual(self.url_open("/formations/date-alert/confirm/forged-token").status_code, 404)
        # Opening the link does not confirm: mail scanners open links without consent.
        page, confirm = form(link)
        sub.invalidate_recordset()
        self.assertFalse(sub.active_consent)
        self.assertIn("Confirmer mon alerte", page.text_content())
        self.assertIn("Votre alerte est active", self.url_open(link, data=confirm).text)
        sub.invalidate_recordset()
        self.assertTrue(sub.active_consent)
        self.assertFalse(sub._confirmation_authorized(mail))
        with self.assertRaises(ValidationError):
            mail._prepare_outgoing_list()
        self.assertEqual(
            self.env["training.session.alert.event"].search([("subscription_id", "=", sub.id)]).operation, "subscribe"
        )
        # A session first published after the confirmation is announced to the confirmed address only.
        delivery = self.dated_delivery()
        delivery.action_publish_session(reason="After visitor consent")
        notice = self.notices(delivery)
        self.assertEqual(
            (notice.recipient_email, notice.recipient_id), ("visitor@example.invalid", self.env["res.users"])
        )
        self.assertTrue(notice._authorized())
        self.assertTrue(notice.mail_id._prepare_outgoing_list())
        unsubscribe = "/formations/date-alert/unsubscribe/%s" % sub.sudo().access_token
        self.assertIn(unsubscribe, notice.mail_id.body_html)
        _page, values = form(unsubscribe)
        self.assertIn("Vous êtes désabonné", self.url_open(unsubscribe, data=values).text)
        sub.invalidate_recordset()
        self.assertFalse(sub.active_consent)
        self.assertFalse(notice._authorized())
        # A confirmation link expires after seven days.
        self.url_open(url, data={**data, "email": "late@example.invalid", "accepted": "yes"})
        late = model.search([("email", "=", "late@example.invalid")])
        with freeze_time(late.confirmation_requested_at + timedelta(days=8)):
            self.assertFalse(late._confirmation_authorized(late.confirmation_mail_id))
            with self.assertRaises(ValidationError):
                late._confirm_by_token()
        self.assertFalse(late.active_consent)

    def test_public_dates_disambiguate_daylight_saving_offsets(self):
        import calendar
        from datetime import datetime

        year = fields.Datetime.now().year + 1
        day = max(week[calendar.SUNDAY] for week in calendar.monthcalendar(year, 10))
        start = datetime(year, 10, day, 0, 30)
        delivery = self.delivery(
            program_id=self.public_program.id,
            kind="session",
            start_at=start,
            end_at=start + timedelta(hours=1),
            timezone="Europe/Paris",
        )
        delivery.action_publish_session(reason="Fictional DST session")
        self.authenticate(None, None)
        response = self.url_open("/formations/%s/sessions" % self.public_program.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("+02:00", response.text)
        self.assertIn("+01:00", response.text)
        self.assertIn("Europe/Paris", response.text)
