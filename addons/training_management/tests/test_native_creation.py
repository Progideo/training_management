from datetime import timedelta
import json

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval

from .test_enrollment import EnrollmentCase


@tagged("post_install", "-at_install")
class TestNativeCreation(EnrollmentCase):
    """INS01/02, SEC01: empty forms, domain choices and immutable audit rendering."""

    def test_empty_allocation_form_and_required_expiry(self):
        model = self.env["training.seat.allocation"].with_user(self.coordinator)
        with Form(model) as form:
            self.assertEqual(form.company_id, self.company)
            self.assertEqual(form.unnamed_seats, 0)
            form.delivery_id = self.delivery()
            form.customer_id = self.customer
            form.source_reference = "NATIVE-FORM"
            form.expires_at = fields.Datetime.now() + timedelta(days=1)
        self.assertEqual(form.record.quantity, 1)
        self.assertEqual(form.record.company_id, self.company)
        with self.assertRaises(AssertionError):
            with Form(model) as incomplete:
                incomplete.delivery_id = self.delivery()
                incomplete.customer_id = self.customer
                incomplete.source_reference = "MISSING-EXPIRY"

    def test_delivery_search_domain_on_empty_forms(self):
        delivery = self.delivery()
        for name in ("training.enrollment", "training.seat.allocation"):
            model = self.env[name].with_user(self.coordinator)
            draft = model.new({})
            domain = safe_eval(model.fields_get(["delivery_id"])["delivery_id"]["domain"],
                               {"company_id": draft.company_id.id})
            choices = self.env["training.delivery"].with_user(self.coordinator).search(domain)
            self.assertIn(delivery, choices)
        with Form(self.env["training.enrollment"].with_user(self.coordinator)) as form:
            form.delivery_id = delivery
            form.participant_id = self.portal.partner_id
            form.free_reason = "Fictional invitation entered in the form"
        self.assertEqual(form.record.state, "requested")
        self.assertEqual(form.record.company_id, delivery.company_id)
        self.assertFalse(form.record.commercially_authorized)

    def test_company_default_does_not_allow_foreign_context_or_write(self):
        delivery = self.delivery()
        for name in ("training.enrollment", "training.seat.allocation"):
            model = self.env[name].with_user(self.coordinator)
            with self.assertRaises((AccessError, ValidationError)):
                model.with_context(allowed_company_ids=self.other_company.ids).new({}).company_id
        record = self.enrollment(delivery)
        with self.assertRaises(ValidationError):
            record.write({"company_id": self.other_company.id})

    def test_transfer_labels_and_domain(self):
        draft = self.env["training.enrollment"].new({})
        self.assertEqual(draft.display_name, self.env._("New Enrollment"))
        source = self.enrollment(self.delivery())
        replacement = self.enrollment(source.delivery_id, participant_id=self.portal_b.partner_id.id,
                                      user_id=self.portal_b.id)
        report = self.enrollment(self.delivery())
        self.assertNotEqual(source.display_name, report.display_name)
        self.assertIn(source.delivery_id.name, source.display_name)
        self.assertIn(str(source.id), source.display_name)
        wizard = self.env["training.enrollment.operation"].with_user(self.coordinator)
        view = wizard.get_view(view_id=self.env.ref("training_management.view_training_enrollment_operation").id)
        from lxml import etree
        domain_text = etree.fromstring(view["arch"]).xpath("//field[@name='target_id']/@domain")[0]
        for operation, expected in (("replace", replacement), ("report", report)):
            domain = safe_eval(domain_text, dict(operation=operation, company_id=self.company.id,
                              enrollment_id=source.id, source_delivery_id=source.delivery_id.id,
                              source_allocation_id=False, source_participant_id=source.participant_id.id))
            choices = self.env["training.enrollment"].with_user(self.coordinator).search(domain)
            self.assertIn(expected, choices)
            self.assertNotIn(source, choices)
            self.assertNotIn(report if operation == "replace" else replacement, choices)
        with Form(wizard.with_context(default_enrollment_id=source.id)) as form:
            form.operation = "replace"
            form.target_id = replacement
            form.operation = "report"
            self.assertFalse(form.target_id)
            form.reason = "Fictional report choice"

    def test_audit_rendering_localizes_without_rewriting_evidence(self):
        from odoo.tools.translate import load_language
        load_language(self.env.cr, "fr_FR")
        enrollment = self.admitted()
        enrollment.action_authorize()
        enrollment.action_open_access()
        self.assertIn(f"(Enrollment {enrollment.id})", enrollment.with_context(lang="en_US").display_name)
        self.assertIn(f"(Inscription {enrollment.id})", enrollment.with_context(lang="fr_FR").display_name)
        rows = enrollment.delivery_id.operation_ids
        raw = {row.id: (row.before, row.after, row.record_label) for row in rows}
        fr = rows.with_context(lang="fr_FR", tz="Africa/Casablanca")
        text = "\n".join(fr.mapped("changes"))
        self.assertNotIn("False", text)
        self.assertNotIn("True", text)
        self.assertIn("Oui", text)
        start = enrollment.access_start
        from odoo.tools.misc import format_datetime
        expected = format_datetime(fr.env, start, tz="Africa/Casablanca")
        self.assertIn(expected, text)
        self.assertNotIn(str(start), text)
        for row in rows:
            self.assertEqual(raw[row.id], (row.before, row.after, row.record_label))
            json.loads(row.after)
