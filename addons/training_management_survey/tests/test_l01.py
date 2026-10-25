"""L01: linked fictional journeys through the deployed native integrations."""

import hashlib
import io
import json
import zipfile
from datetime import timedelta
from unittest import SkipTest
from unittest.mock import patch
from uuid import uuid4

from lxml import html
from werkzeug.datastructures import FileStorage

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.pdf import PdfFileReader
from odoo.addons.training_management.tests.test_evaluation import EvaluationCase

from .test_exam import ExamCase


@tagged("post_install", "-at_install")
class TestLaunchAcceptance(EvaluationCase, ExamCase, HttpCase):
    """One shared fixture; discovered by the existing cumulative module suite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.env["ir.module.module"].search_count(
            [("name", "=", "training_management_sale"), ("state", "=", "installed")]
        ):
            raise SkipTest("The integrated launch journey requires the optional sales integration")
        # Commercial coordination is an explicit cumulative role, limited to its own quotes.
        cls.coordinator.group_ids = [Command.link(cls.env.ref("sales_team.group_sale_salesman").id)]
        cls.seller = cls.coordinator
        cls.portal.partner_id.email = "l01-participant@example.invalid"
        cls.portal_b.partner_id.email = "l01-trainer@example.invalid"
        cls.finance = new_test_user(
            cls.env, login="l01_finance", groups="account.group_account_invoice,sales_team.group_sale_salesman"
        )
        cls.representative = new_test_user(cls.env, login="l01_client_a", groups="base.group_portal")
        cls.representative.partner_id.parent_id = cls.customer
        cls.client_b = cls.env["res.partner"].create({"name": "Fictional L01 Client B"})
        cls.public = cls.env.ref("base.public_user")
        cls.other_coordinator = new_test_user(
            cls.env,
            login="l01_coord_b",
            groups="training_management.group_training_coordinator",
            company_id=cls.other_company.id,
            company_ids=[Command.set(cls.other_company.ids)],
        )
        cls.pdf = cls.program.pdf_attachment_id.raw.content
        cls.public_program = cls.program.with_user(cls.coordinator).copy(
            {
                "version": "L01-public",
                "public_catalogue": True,
                "preview_pdf": BinaryBytes(cls.pdf),
                "preview_filename": "fictional-preview.pdf",
                "expected_outcomes": "Fictional observable outcome",
                "practice_deliverables": "Fictional deliverable",
                "instructor_profiles": "Fictional trainer profile",
                "material_access_duration": "Fictional ten-day access",
                "included_services": "Fictional private PDF",
                "preparation_details": "Fictional preparation",
                "mock_exam_details": "Unlimited practice attempts",
                "official_exam_details": "Official examination not included",
                "preview_question_ids": [
                    Command.create(
                        {
                            "name": "Fictional demonstration",
                            "choice_a": "Expected",
                            "choice_b": "Other",
                            "correct_choice": "a",
                            "explanation": "Public demonstration only",
                        }
                    )
                ],
            }
        )
        cls.public_program.action_validate()
        cls.public_program.action_publish()
        cls.eur, cls.mad = cls.env.ref("base.EUR"), cls.env.ref("base.MAD")
        (cls.eur | cls.mad).active = True
        for currency in cls.eur | cls.mad:
            if currency != cls.company.currency_id:
                cls.env["res.currency.rate"].create(
                    {"currency_id": currency.id, "company_id": cls.company.id, "name": "2026-01-01", "rate": 1}
                )
        cls.accounts = {}
        for code, kind in (("709981", "income"), ("349981", "asset_receivable"), ("519981", "asset_cash")):
            cls.accounts[kind] = cls.env["account.account"].create(
                {
                    "name": "Fictional L01 " + kind,
                    "code": code,
                    "account_type": kind,
                    "reconcile": kind == "asset_receivable",
                    "company_ids": [Command.set(cls.company.ids)],
                }
            )
        for partner in cls.customer | cls.portal.partner_id:
            partner.with_company(cls.company).property_account_receivable_id = cls.accounts["asset_receivable"]
        cls.env["account.journal"].create(
            {
                "name": "Fictional L01 Sales",
                "code": "L01S",
                "type": "sale",
                "default_account_id": cls.accounts["income"].id,
            }
        )
        cls.bank = cls.env["account.journal"].create(
            {
                "name": "Fictional L01 EUR Bank",
                "code": "L01B",
                "type": "bank",
                "currency_id": cls.eur.id,
                "default_account_id": cls.accounts["asset_cash"].id,
            }
        )
        cls.method = cls.bank.inbound_payment_method_line_ids.filtered(lambda row: row.code == "manual")
        cls.method.payment_account_id = cls.accounts["asset_cash"]

    def _values(self, currency="MAD", kind="group", count=10):
        return {
            "contact": "Fictional L01 Requester",
            "email": "l01-requester@example.invalid",
            "organisation": "Fictional L01 Client",
            "kind": kind,
            "request_type": "catalogue",
            "program": str(self.public_program.id),
            "objectives": "Fictional applied practice",
            "level": "Beginner",
            "count": str(count),
            "country": str(self.env.ref("base.ma").id),
            "mode": "remote",
            "currency": currency,
            "dates_flexible": "1",
        }

    def _commerce(self, currency="MAD", kind="group", count=10):
        key = uuid4().hex
        values = self._values(currency, kind, count)
        leads = self.env["crm.lead"]
        upload = FileStorage(
            stream=io.BytesIO(self.pdf), filename="fictional-brief.pdf", content_type="application/pdf"
        )
        lead = leads._submit_public_request(self.company, values, key, upload)
        self.assertEqual(
            leads._submit_public_request(
                self.company,
                values,
                key,
                FileStorage(
                    stream=io.BytesIO(self.pdf), filename="fictional-brief.pdf", content_type="application/pdf"
                ),
            ),
            lead,
        )
        customer = self.customer if kind == "group" else self.portal.partner_id
        lead.with_user(self.seller).write({"partner_id": customer.id, "user_id": self.seller.id, "type": "opportunity"})
        product = (
            self.env["product.template"]
            .create(
                {
                    "name": "Fictional L01 Training",
                    "type": "service",
                    "invoice_policy": "order",
                    "company_id": self.company.id,
                    "training_course_id": self.course.id,
                    "training_price_basis": "package" if kind == "group" else "person",
                    "property_account_income_id": self.accounts["income"].id,
                    "taxes_id": [Command.clear()],
                }
            )
            .product_variant_id
        )
        price = self.env["product.pricelist"].create(
            {
                "name": "Fictional L01 " + currency,
                "currency_id": self.env.ref("base." + currency).id,
                "company_id": self.company.id,
            }
        )
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": price.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "applied_on": "1_product",
                "compute_price": "fixed",
                "fixed_price": 1000,
            }
        )
        context = lead.with_user(self.seller).action_new_quotation()["context"]
        order = (
            self.env["sale.order"]
            .with_user(self.seller)
            .with_context(**context)
            .create(
                {
                    "partner_id": customer.id,
                    "pricelist_id": price.id,
                    "order_line": [
                        Command.create(
                            {
                                "product_id": product.id,
                                "training_program_id": self.public_program.id,
                                "product_uom_qty": 1,
                                "tax_ids": [Command.clear()],
                            }
                        )
                    ],
                }
            )
        )
        self.assertEqual(order.opportunity_id, lead)
        self.assertEqual(order.currency_id.name, currency)
        order.action_confirm()
        self.assertEqual(self.env["training.request.notice"].search_count([("lead_id", "=", lead.id)]), 1)
        return lead, order

    def _allocation(self, order, delivery, quantity=10):
        allocation = self.lot(
            delivery,
            sale_line_id=order.order_line.id,
            quantity=quantity,
            customer_id=order.partner_id.commercial_partner_id.id,
        )
        allocation.action_confirm()
        return allocation

    def _grant(self, allocation):
        grant = (
            self.env["training.company.authorization"]
            .with_user(self.coordinator)
            .create(
                {
                    "company_id": self.company.id,
                    "customer_id": self.customer.id,
                    "user_id": self.representative.id,
                    "allocation_ids": [Command.set(allocation.ids)],
                }
            )
        )
        grant.action_confirm()
        return grant

    def _finish_exam(self, enrollment, activity, questions):
        service = self.env["training.exam.service"].with_user(enrollment.user_id)
        attempt = service._start(enrollment.id, activity.id)
        for question in questions:
            service._save(attempt.id, question.id, question.suggested_answer_ids.filtered("is_correct").ids, False)
        service._submit(attempt.id)
        return attempt, service._result(attempt)

    def test_r01_mad_ten_nominations_deferred_access_attendance_and_closure(self):
        _lead, order = self._commerce()
        delivery = self.delivery(
            program_id=self.public_program.id,
            kind="session",
            start_at="2027-01-01",
            end_at="2027-02-01",
            timezone="UTC",
        )
        session = self.scheduled_session(delivery)
        delivery.action_confirm()
        allocation = self._allocation(order, delivery)
        self._grant(allocation)
        service = self.env["training.company.service"].with_user(self.representative)
        selected = self.env["training.enrollment"]
        for index in range(10):
            nominee = service._nominate(
                allocation.id, "Fictional L01 Participant %s" % index, "l01-%s@example.invalid" % index
            )
            self.assertFalse(nominee.enrollment_id)
            person = self.portal.partner_id if index == 0 else self.env["res.partner"].create({"name": nominee.name})
            enrollment = self.enrollment(
                delivery,
                participant_id=person.id,
                user_id=self.portal.id if index == 0 else False,
                allocation_id=allocation.id,
                free_reason=False,
            )
            enrollment.action_validate_prerequisites(reason="Fictional checked prerequisite")
            enrollment.action_confirm()
            nominee.with_user(self.coordinator).write({"enrollment_id": enrollment.id, "state": "processed"})
            self.assertEqual(enrollment.effective_access, "unopened")
            if index == 0:
                selected = enrollment
            if index == 6:
                self.assertEqual(allocation.unnamed_seats, 3)
        self.assertEqual(allocation.unnamed_seats, 0)
        self.assertEqual(delivery.occupied_seats, 10)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.enrollment(
                delivery,
                participant_id=self.portal_b.partner_id.id,
                user_id=self.portal_b.id,
                allocation_id=allocation.id,
                free_reason=False,
            ).action_confirm()
        selected.action_authorize(reason="Fictional B2B deferred payment approved")
        selected.action_open_access(reason="Fictional coordinator opening")
        dossier = self.dossier(selected)
        attendance = self.env["training.attendance.service"]
        with patch("odoo.fields.Datetime.now", return_value=session.end_at):
            row = attendance.with_user(self.portal)._declare(
                selected.id, session.id, 0, 180, accepted=True, definition=attendance._definition(session)
            )
            attendance.with_user(self.portal_b)._review(
                session.id, selected.id, 0, 180, revision=row.revision, definition=attendance._definition(session)
            )
        self.assertEqual(row.minutes, 180)
        assessment, _authorization = self.assigned_evaluation(selected, program_id=self.public_program.id)
        self.decision(assessment, score=80)
        proof_action = assessment.with_user(self.coordinator).action_export_proof()
        self.validate(self.env["training.proof"].browse(proof_action["res_id"]).with_user(self.coordinator))
        self.validate(self.proof(dossier, "completion", data=BinaryBytes(self.pdf)))
        selected.with_user(self.quality).action_certificate_participation()
        selected.with_user(self.quality).action_certificate_achievement()
        self.assertTrue(self.document(dossier, "participation").data.content.startswith(b"%PDF-"))
        self.assertTrue(self.document(dossier, "achievement"))
        participation = self.document(dossier, "participation")
        pdf_text = "\n".join(
            page.extract_text() for page in PdfFileReader(io.BytesIO(participation.data.content)).pages
        )
        self.assertIn(self.portal.partner_id.name, pdf_text)
        with self.assertRaises(ValidationError):
            dossier.with_user(self.quality).action_close()
        for category in dossier._missing_keys():
            self.validate(
                self.proof(dossier, category, data=BinaryBytes(self.pdf), source="Fictional L01 original: " + category)
            )
        dossier.with_user(self.quality).action_close()
        self.assertEqual(dossier.state, "closed")
        selected.action_close(reason="Fictional controlled completion")
        self.assertEqual(selected.state, "closed")
        self.assertEqual(order.currency_id, self.mad)

    def test_r02_eur_partial_and_final_bank_transfer_then_manual_access(self):
        _lead, order = self._commerce("EUR", "individual", 1)
        delivery = self.delivery(
            program_id=self.public_program.id,
            capacity=1,
            kind="session",
            start_at="2027-01-01",
            end_at="2027-02-01",
            timezone="UTC",
        )
        self.scheduled_session(delivery)
        delivery.action_confirm()
        allocation = self._allocation(order, delivery, 1)
        enrollment = self.enrollment(delivery, allocation_id=allocation.id, free_reason=False)
        enrollment.action_reserve()
        enrollment.action_validate_prerequisites(reason="Fictional individual review")
        invoice = order.with_user(self.finance)._create_invoices()
        invoice.with_user(self.finance).action_post()
        self.assertEqual(invoice.currency_id, self.eur)
        for amount, reference, remaining in ((250, "L01-PART", 750), (750, "L01-BALANCE", 0)):
            wizard = (
                self.env["account.payment.register"]
                .with_user(self.finance)
                .with_context(active_model="account.move", active_ids=invoice.ids)
                .create(
                    {
                        "journal_id": self.bank.id,
                        "payment_method_line_id": self.method.id,
                        "currency_id": self.eur.id,
                        "amount": amount,
                        "payment_difference_handling": "open",
                        "training_bank_reference": reference,
                        "training_bank_verified": True,
                    }
                )
            )
            wizard.action_create_payments()
            self.assertEqual(invoice.amount_residual, remaining)
            self.assertEqual(enrollment.effective_access, "unopened")
            self.assertFalse(
                self.env["training.invitation"].search(
                    [("delivery_id", "=", delivery.id), ("partner_id", "=", self.portal.partner_id.id)]
                )
            )
        enrollment.action_confirm()
        enrollment.action_authorize(reason="Fictional verified native EUR settlement")
        enrollment.action_open_access(reason="Fictional coordinator decision")
        self.assertEqual(enrollment.effective_access, "active")
        invitation = (
            self.env["training.invitation.send"]
            .with_user(self.coordinator)
            .create({"delivery_id": delivery.id, "recipient_ids": [Command.set(self.portal.partner_id.ids)]})
        )
        invitation.action_send()
        invitation.action_send()
        self.assertEqual(
            self.env["training.invitation"].search_count(
                [("delivery_id", "=", delivery.id), ("partner_id", "=", self.portal.partner_id.id)]
            ),
            1,
        )
        payments = self.env["account.payment"].search([("reconciled_invoice_ids", "in", invoice.ids)])
        self.assertEqual(len(payments), 2)
        self.assertEqual(payments.currency_id, self.eur)
        self.assertEqual(payments.training_bank_verified_by_id, self.finance)
        self.assertFalse(invoice._get_portal_payment_link())

    def test_r03_autonomous_pdf_two_successful_attempts_and_themes(self):
        exam, q1, q2, activity, enrollment, service = self.published()
        material = self.material(data=BinaryBytes(self.pdf))
        enrollment.delivery_id.action_add_programme_materials()
        self.assertFalse(enrollment.delivery_id.session_ids)
        self.assertTrue(self.env["training.document.policy"].with_user(self.portal)._can_read(material))
        first, result = self._finish_exam(enrollment, activity, q1 | q2)
        self.assertTrue(result["success"])
        original = first.user_input_line_ids.read(["question_id", "suggested_answer_id", "answer_score"])
        second, repeated = self._finish_exam(enrollment, activity, q1 | q2)
        self.assertNotEqual(first, second)
        self.assertEqual(repeated["percentage"], 100)
        self.assertEqual(set(result["themes"]), {"Basics", "Advanced"})
        self.assertEqual(
            first.user_input_line_ids.read(["question_id", "suggested_answer_id", "answer_score"]), original
        )
        self.assertEqual((first | second).survey_id, exam)
        self.assertEqual((first | second).mapped("state"), ["done", "done"])
        dossier = self.dossier(enrollment)
        with self.assertRaises(ValidationError):
            enrollment.with_user(self.quality).action_certificate_achievement()
        self.assertFalse(dossier.output_ids)

    def test_r04_mixed_two_sessions_three_activities_and_actual_duration(self):
        delivery = self.delivery(kind="session", start_at="2027-01-01", end_at="2027-02-01", timezone="UTC")
        first = self.scheduled_session(delivery)
        second = first.copy({"name": "Fictional second session", "start_date": "2027-01-05", "end_date": "2027-01-05"})
        delivery.action_confirm()
        enrollment = self.opened(delivery)
        dossier = self.dossier(enrollment)
        learning = self.env["training.learning.service"].with_user(self.portal)
        activities = (
            self.env["training.learning.activity"]
            .with_user(self.coordinator)
            .create(
                [
                    {"name": "Fictional activity %s" % index, "delivery_id": delivery.id, "criterion": "declaration"}
                    for index in range(3)
                ]
            )
        )
        for activity in activities:
            learning._declare(enrollment.id, activity.id)
        attendance = self.env["training.attendance.service"]
        for session, begin, end in ((first, 60, 180), (second, 0, 180)):
            with patch("odoo.fields.Datetime.now", return_value=session.end_at):
                row = attendance.with_user(self.portal)._declare(
                    enrollment.id, session.id, begin, end, accepted=True, definition=attendance._definition(session)
                )
                attendance.with_user(self.portal_b)._review(
                    session.id,
                    enrollment.id,
                    begin,
                    end,
                    revision=row.revision,
                    definition=attendance._definition(session),
                )
        self.validate(self.proof(dossier, "completion", data=BinaryBytes(self.pdf)))
        enrollment.with_user(self.quality).action_certificate_participation()
        participation = self.document(dossier, "participation")
        self.assertEqual(json.loads(participation.snapshot)["minutes"], 300)
        self.assertEqual(len(learning._rows(enrollment)), 3)
        enrollment.with_user(self.quality).action_certificate_completion()
        self.assertTrue(self.document(dossier, "completion"))
        self.assertEqual(len(delivery.session_ids), 2)

    def test_r05_postponement_and_replacement_preserve_original_attempt(self):
        _exam, q1, q2, activity, original, _service = self.published()
        attempt, result = self._finish_exam(original, activity, q1 | q2)
        self.assertTrue(result["success"])
        next_delivery = self.delivery()
        postponed = self.enrollment(next_delivery)
        original.action_postpone(postponed.id, reason="Fictional postponement")
        self.assertEqual(original.state, "postponed")
        self.assertEqual(original.access_state, "revoked")
        self.assertEqual(original.successor_id, postponed)
        self.assertEqual(attempt.training_enrollment_id, original)
        postponed.action_validate_prerequisites(reason="Fictional review retained")
        postponed.action_confirm()
        replacement = self.enrollment(
            next_delivery, participant_id=self.portal_b.partner_id.id, user_id=self.portal_b.id
        )
        postponed.action_replace(replacement.id, reason="Fictional participant replacement")
        self.assertEqual(postponed.successor_id, replacement)
        self.assertEqual(next_delivery.occupied_seats, 0)
        self.assertFalse(self.env["survey.user_input"].search([("training_enrollment_id", "=", replacement.id)]))
        self.assertEqual(attempt.training_enrollment_id, original)

    def test_r06_private_http_exports_and_company_revocation(self):
        delivery = self.delivery(capacity=20)
        allocation = self.lot(delivery)
        other = self.lot(delivery, customer_id=self.client_b.id, quantity=1, source_reference="L01-CLIENT-B")
        grant = self._grant(allocation)
        own = self.enrollment(delivery, allocation_id=allocation.id, free_reason=False)
        peer = self.enrollment(
            delivery,
            allocation_id=other.id,
            free_reason=False,
            participant_id=self.portal_b.partner_id.id,
            user_id=self.portal_b.id,
        )
        document = (
            self.env["training.company.document"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Fictional client PDF",
                    "allocation_id": allocation.id,
                    "data": BinaryBytes(self.pdf),
                    "filename": "l01-client.pdf",
                    "released": True,
                }
            )
        )
        for user in (self.portal_b, self.public, self.other_coordinator):
            with self.assertRaises(AccessError):
                own.with_user(user).read(["participant_id"])
            with self.assertRaises((AccessError, UserError)):
                document.with_user(user).export_data(["name", "data"])
        self.authenticate(self.representative.login, self.representative.login)
        page = self.url_open("/my/company-trainings/%s" % allocation.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.portal.partner_id.name, page.text)
        self.assertNotIn(peer.participant_id.name, page.text)
        url = "/my/company-trainings/%s/documents/%s" % (allocation.id, document.id)
        self.assertEqual(self.url_open(url).content, self.pdf)
        self.assertEqual(self.url_open("/my/company-trainings/%s" % other.id).status_code, 404)
        delivery.evaluation_supervisor_ids = [Command.set(self.supervisor.ids)]
        dashboard = self.env["training.dashboard.service"].with_user(self.supervisor)
        self.assertTrue(dashboard._dashboard(delivery.id))
        delivery.evaluation_supervisor_ids = [Command.clear()]
        with self.assertRaises(AccessError):
            dashboard._dashboard(delivery.id)
        grant.action_revoke()
        self.assertEqual(self.url_open(url).status_code, 404)
        self.assertEqual(self.url_open("/my/company-trainings/%s" % allocation.id).status_code, 404)

    def test_r07_quality_export_index_and_confidential_exclusions(self):
        _exam, q1, q2, activity, enrollment, _service = self.published()
        self._finish_exam(enrollment, activity, q1 | q2)
        dossier = self.dossier(enrollment)
        self.representative.partner_id.parent_id = dossier.customer_id
        dossier.client_contact_ids = [Command.set(self.representative.partner_id.ids)]
        shared = self.validate(self.proof(dossier, data=BinaryBytes(self.pdf), client_shared=True))
        private = self.validate(self.proof(dossier, "assessment", data=BinaryBytes(self.pdf), score=80, threshold=70))
        dossier.with_user(self.quality).action_export_client()
        client = self.document(dossier, "client")
        original = hashlib.sha256(client.data.content).hexdigest()
        with zipfile.ZipFile(io.BytesIO(client.data.content)) as archive:
            index = json.loads(archive.read("index.json"))
            self.assertEqual([row["id"] for row in index["pieces"]], shared.ids)
            self.assertIn("missing", index)
            self.assertNotIn("proof-%s-v1.pdf" % private.id, archive.namelist())
        dossier.with_user(self.quality).action_export_internal()
        internal = self.document(dossier, "internal")
        self.assertTrue(self.env["training.document.policy"].with_user(self.representative)._can_read(client))
        self.assertFalse(self.env["training.document.policy"].with_user(self.representative)._can_read(internal))
        self.assertEqual(hashlib.sha256(client.data.content).hexdigest(), original)

    def test_r08_exam_reload_marking_expiry_and_late_submission_are_stable(self):
        _exam, q1, q2, activity, enrollment, service = self.published()
        attempt = service._start(enrollment.id, activity.id)
        self.assertEqual(service._start(enrollment.id, activity.id), attempt)
        self.authenticate(self.portal.login, self.portal.login)
        url = "/my/training-exams/%s" % attempt.id
        page = self.url_open(url)
        self.assertEqual(len(html.fromstring(page.content).xpath("//button[contains(@class, 'tm_question_link')]")), 2)
        payload = {
            "csrf_token": self.csrf_token(),
            "kind": "save",
            "question": str(q1.id),
            "choices": json.dumps(q1.suggested_answer_ids.filtered("is_correct").ids),
            "marked": "1",
        }
        for _retry in range(2):
            saved = self.url_open(url + "/save", data=payload)
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json()["saved"])
        reloaded = self.url_open(url)
        self.assertIn("tm_review", reloaded.text)
        self.assertEqual(len(attempt.user_input_line_ids), 1)
        self.assertIn(q1, attempt.training_review_ids)
        with self.assertRaises(AccessError):
            service._result(attempt)
        with patch("odoo.fields.Datetime.now", return_value=attempt.deadline + timedelta(seconds=1)):
            service._submit(attempt.id)
            result = service._result(attempt)
            service._submit(attempt.id)
            self.assertEqual(
                service._save(attempt.id, q2.id, q2.suggested_answer_ids.filtered("is_correct").ids, False),
                {"done": True},
            )
            self.assertEqual(service._result(attempt), result)
        self.assertEqual(attempt.state, "done")
        self.assertLess(result["percentage"], 100)

    def test_r09_synthetic_native_import_replay_and_linked_manual_records(self):
        partners = self.env["res.partner"].with_context(active_test=False)
        names = ["l01_replay_%s" % uuid4().hex, "l01_replay_%s" % uuid4().hex]
        company_xmlid = self.company.get_external_id()[self.company.id]
        columns = ["id", "name", "active", "country_id/id", "company_id/id", "parent_id/id"]
        data = [
            [names[0], "Fictional L01 Root", "False", "base.ma", company_xmlid, ""],
            [names[1], "Fictional L01 Contact", "False", "base.ma", company_xmlid, names[0]],
        ]
        original = self.program.pdf_attachment_id.raw.content
        first = partners.load(columns, data)
        self.assertFalse(first["messages"])
        repeated = partners.load(columns, data)
        self.assertFalse(repeated["messages"])
        self.assertEqual(first["ids"], repeated["ids"])
        loaded = partners.browse(first["ids"])
        self.assertEqual(loaded[1].parent_id, loaded[0])
        self.assertFalse(any(loaded.mapped("active")))
        self.assertFalse(
            self.env["res.users"].with_context(active_test=False).search([("partner_id", "in", loaded.ids)])
        )
        exported = loaded.export_data(columns)["datas"]
        self.assertEqual(len(exported), 2)
        self.assertEqual(loaded.company_id, self.company)
        self.assertEqual(self.program.pdf_attachment_id.raw.content, original)
        delivery = self.delivery()
        manual = self.enrollment(delivery)
        manual.action_validate_prerequisites(reason="Fictional source checked; no invented historical evidence")
        manual.action_confirm()
        self.assertEqual(manual.effective_access, "unopened")
        self.assertFalse(self.env["training.company.authorization"].search([]))

    def test_p01_p04_public_journey_and_private_pdf_repeated_request(self):
        self.authenticate(None, None)
        home = self.url_open("/formations")
        self.assertEqual(home.status_code, 200)
        self.assertLess(home.text.index("Former mon équipe"), home.text.index("Me former"))
        page = self.url_open("/formations/%s?kind=group" % self.public_program.id)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(
            self.url_open("/formations/%s/pdf" % self.public_program.id).content,
            self.public_program.pdf_attachment_id.raw.content,
        )
        self.assertEqual(self.url_open("/formations/%s/apercu.pdf" % self.public_program.id).content, self.pdf)
        question = self.public_program.preview_question_ids
        result = self.url_open(
            "/formations/%s" % self.public_program.id, data={"csrf_token": self.csrf_token(), str(question.id): "a"}
        )
        self.assertIn("Public demonstration only", result.text)
        self.assertFalse(self.env["survey.user_input"].search([("training_enrollment_id", "!=", False)]))
        self.assertTrue(PdfFileReader(io.BytesIO(self.public_program.pdf_attachment_id.raw.content)).pages)
        self.assertIn(self.url_open("/formations/%s" % self.program.id).status_code, (403, 404))
        form = html.fromstring(
            self.url_open("/formations/demande?kind=group&program=%s" % self.public_program.id).content
        )
        payload = {
            **self._values(),
            "csrf_token": form.xpath("//input[@name='csrf_token']/@value")[0],
            "submission_token": form.xpath("//input[@name='submission_token']/@value")[0],
        }
        for _index in range(2):
            response = self.url_open("/formations/demande", data=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Demande reçue", response.text)
        leads = self.env["crm.lead"].search([("training_submission_key", "=", payload["submission_token"])])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads.training_program_id, self.public_program)
        self.assertEqual(self.env["training.request.notice"].search_count([("lead_id", "=", leads.id)]), 1)
        self.assertFalse(self.env["training.enrollment"].search([]))

    def test_p05_p06_exact_client_agreement_and_successor_keep_source(self):
        delivery = self.delivery()
        allocation = self.lot(delivery)
        grant = self._grant(allocation)
        source = hashlib.sha256(self.program.pdf_attachment_id.raw.content).hexdigest()
        common = {
            "delivery_id": delivery.id,
            "customer_id": self.customer.id,
            "objectives": "Fictional exact client objectives",
            "business_cases": "Fictional client case",
            "instructions": "Fictional client instruction",
            "data": BinaryBytes(self.pdf),
            "filename": "l01-intra.pdf",
        }
        versions = self.env["training.intra.version"].with_user(self.coordinator)
        first = versions.create({**common, "version": "L01-client-1"})
        with self.assertRaises(ValidationError):
            delivery.action_confirm()
        first.action_submit()
        self.authenticate(self.representative.login, self.representative.login)
        url = "/my/company-trainings/%s" % allocation.id
        page = self.url_open(url)
        token = html.fromstring(page.content).xpath("//input[@name='csrf_token']/@value")[0]
        self.assertEqual(
            self.url_open("%s/versions/%s/approve" % (url, first.id), data={"csrf_token": token}).status_code, 200
        )
        self.assertEqual(first.approved_contact_id, self.representative.partner_id)
        first.action_confirm()
        delivery.action_confirm()
        original = first.read(["objectives", "approved_contact_id", "approved_at", "version"])
        successor = versions.create(
            {
                **common,
                "version": "L01-client-2",
                "previous_id": first.id,
                "objectives": "Fictional revised client objective",
            }
        )
        successor.action_submit()
        with self.assertRaises(ValidationError):
            successor.action_confirm()
        self.assertEqual(delivery.intra_version_id, first)
        page = self.url_open(url)
        token = html.fromstring(page.content).xpath("//input[@name='csrf_token']/@value")[0]
        self.assertEqual(
            self.url_open("%s/versions/%s/approve" % (url, successor.id), data={"csrf_token": token}).status_code, 200
        )
        successor.action_confirm()
        self.assertEqual(delivery.intra_version_id, successor)
        self.assertEqual(first.read(["objectives", "approved_contact_id", "approved_at", "version"]), original)
        self.assertEqual(hashlib.sha256(self.program.pdf_attachment_id.raw.content).hexdigest(), source)
        grant.action_revoke()
        self.assertEqual(self.url_open("%s/versions/%s/pdf" % (url, first.id)).status_code, 404)
        self.assertEqual(self.url_open("%s/versions/%s/pdf" % (url, successor.id)).status_code, 404)
