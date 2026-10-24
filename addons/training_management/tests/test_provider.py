"""QUA03: real scoped identities, immutable evidence and nonblocking planning."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, HttpCase, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.misc import limited_field_access_token

from .test_evaluation import EvaluationCase
from .test_material import PDF


@tagged("post_install", "-at_install")
class TestProvider(EvaluationCase):
    def test_assignment_onchange_keeps_inline_warning_without_modal(self):
        today = fields.Date.today()
        dossier = self.provider()
        self.evidence(dossier, valid_from=today - timedelta(days=2), valid_until=today - timedelta(days=1))
        delivery = self.delivery()
        instructor = self.portal_b.partner_id
        cases = [
            (
                "training.delivery",
                {"company_id": delivery.company_id.id, "evaluation_instructor_ids": [Command.set(instructor.ids)]},
                "evaluation_instructor_ids",
            ),
            (
                "training.session",
                {
                    "delivery_id": delivery.id,
                    "company_id": delivery.company_id.id,
                    "instructor_id": instructor.id,
                    "start_date": str(today),
                    "end_date": str(today),
                },
                "instructor_id",
            ),
            (
                "training.session.edit",
                {
                    "delivery_id": delivery.id,
                    "company_id": delivery.company_id.id,
                    "instructor_id": instructor.id,
                    "start_date": str(today),
                    "end_date": str(today),
                    "repeat_count": 2,
                    "interval_days": 7,
                },
                "instructor_id",
            ),
        ]
        for model_name, values, changed in cases:
            with self.subTest(model=model_name):
                model = self.env[model_name].with_user(self.coordinator)
                spec = {name: {} for name in values}
                spec["instructor_warning"] = {}
                result = model.onchange(dict(values), [changed], spec)
                self.assertTrue(result["value"]["instructor_warning"])
                self.assertNotIn("warning", result)
                arch = model.get_view(view_type="form")["arch"]
                root = etree.fromstring(arch.encode())
                self.assertTrue(root.xpath("//div[@role='alert']/field[@name='instructor_warning']"))

    def test_native_delivery_save_reads_history_after_role_assignment(self):
        dossier = self.provider()
        self.evidence(
            dossier,
            valid_from=fields.Date.today() - timedelta(days=2),
            valid_until=fields.Date.today() - timedelta(days=1),
        )
        delivery = self.delivery()
        result = delivery.web_save(
            {
                "evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)],
                "evaluation_supervisor_ids": [Command.set(self.supervisor.ids)],
            },
            {"instructor_warning": {}, "operation_ids": {"fields": {"changes": {}}}},
        )
        self.assertTrue(result[0]["instructor_warning"])
        changes = "\n".join(row["changes"] for row in result[0]["operation_ids"])
        for name in ("evaluation_instructor_ids", "evaluation_supervisor_ids"):
            self.assertIn(delivery.fields_get([name])[name]["string"], changes)
        # Old immutable JSON commands are displayed without following historical
        # relations or exposing technical command arrays in the native history.
        self.assertNotIn("[[6", changes)
        self.assertEqual(delivery.evaluation_instructor_ids, self.portal_b.partner_id)

    def test_native_evidence_action_replaces_without_parent_commands(self):
        dossier = self.provider()
        first = self.evidence(dossier)
        action = dossier.with_context(default_dossier_id=999, default_state="closed").action_add_evidence()
        self.assertEqual(action["res_model"], "training.provider.evidence")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_dossier_id"], dossier.id)
        self.assertNotIn("default_state", action["context"])
        model = self.env[action["res_model"]].with_user(self.quality).with_context(**action["context"])
        with Form(model) as form:
            self.assertEqual(form.dossier_id, dossier)
            form.name = "renewed.pdf"
            form.competence = "Renewed fictional competence"
            form.source = "Fictional renewal"
            form.previous_id = first
            form.data = BinaryBytes(PDF)
        replacement = form.record
        self.assertEqual(replacement.previous_id, first)
        self.assertEqual(len(dossier.evidence_ids), 2)
        self.assertEqual(first.data.content, PDF)
        for user in (self.other_quality, self.portal, self.supervisor):
            with self.assertRaises(AccessError):
                dossier.with_user(user).action_add_evidence()
        dossier.write({"frozen": True})
        with self.assertRaises(ValidationError):
            dossier.action_add_evidence()
        dossier.write({"frozen": False})
        dossier.action_archive()
        with self.assertRaises(ValidationError):
            dossier.action_add_evidence()

    def provider(self, kind="instructor", **values):
        return (
            self.env["training.provider.dossier"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "PRIVATE fictional provider dossier",
                    "kind": kind,
                    "partner_id": self.portal_b.partner_id.id,
                    "quality_id": self.quality.id,
                    "retention_id": self.retention.id,
                    "competencies": "Fictional pedagogical competence and scope",
                    **values,
                }
            )
            .with_user(self.quality)
        )

    def evidence(self, dossier, **values):
        return (
            self.env["training.provider.evidence"]
            .with_user(self.quality)
            .create(
                {
                    "dossier_id": dossier.id,
                    "name": "PRIVATE fictional credential.pdf",
                    "competence": "Fictional competence",
                    "source": "Fictional verified issuer",
                    "data": BinaryBytes(PDF),
                    **values,
                }
            )
        )

    def test_watch_requires_analysis_and_reasoned_decision(self):
        row = self.provider("watch", source="https://example.test/watch", observed_on=fields.Date.today())
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            row.action_review()
        row.write(
            {
                "analysis": "Actual analysis of source",
                "decision": "No programme revision",
                "no_impact_reason": "Requirements already addressed",
            }
        )
        row.action_review()
        self.assertEqual(row.state, "active")
        row.write({"impact": "New module", "no_impact_reason": False, "program_id": self.program.id})
        self.assertEqual(row.state, "draft")
        row.action_review()
        self.assertEqual(row.program_id, self.program)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            row.with_user(self.coordinator).action_review()
        row.action_archive()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            row.write({"analysis": "Rewrite archived analysis"})
        self.assertEqual(row.event_ids[-1].operation, "archived")

    def test_private_grants_company_revocation_and_all_native_channels(self):
        row = self.provider()
        evidence = self.evidence(row)
        self.other_quality.group_ids = [Command.link(self.env.ref("base.group_no_one").id)]
        token = limited_field_access_token(evidence, "data", scope="binary")
        for user in (self.other_quality, self.portal, self.portal_b, self.supervisor):
            for model in ("dossier", "evidence", "event", "obligation"):
                target = self.env["training.provider." + model].with_user(user)
                if target.has_access("read"):
                    self.assertFalse(target.search([]))
                else:
                    with self.assertRaises(AccessError):
                        target.search([])
            for record in (row, evidence, row.event_ids[0]):
                with patch(
                    "odoo.addons.base.models.res_users.request", SimpleNamespace(session=SimpleNamespace(debug=True))
                ):
                    with self.assertRaises(AccessError) as caught:
                        record.with_user(user).read(["display_name"])
                    self.assertNotIn("PRIVATE", str(caught.exception))
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._get_stream_from(evidence.sudo(), "data")
            with self.assertRaises(AccessError):
                self.env["ir.binary"].with_user(user)._find_record(
                    res_model=evidence._name, res_id=evidence.id, field="data", access_token=token
                )
        for model, values in (
            ("ir.attachment", {"name": "bad.pdf", "res_model": row._name, "res_id": row.id, "raw": PDF}),
            ("mail.message", {"model": row._name, "res_id": row.id, "body": "PRIVATE"}),
            (
                "mail.activity",
                {"res_model_id": self.env["ir.model"]._get_id(row._name), "res_id": row.id, "summary": "PRIVATE"},
            ),
        ):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                self.env[model].with_user(self.quality).create(values)
        stream = self.env["ir.binary"].with_user(self.quality)._get_stream_from(evidence, "data")
        self.assertEqual(stream.download_name, evidence.name)
        with self.assertRaises(AccessError):
            self.env["ir.binary"].with_user(self.quality)._get_stream_from(evidence, "source")
        row.write({"member_ids": [Command.clear()]})
        self.assertFalse(row.with_user(self.coordinator).has_access("read"))
        self.assertFalse(evidence.with_user(self.coordinator).has_access("read"))
        other = self.env["res.company"].create({"name": "Fictional other provider operator"})
        self.quality.company_ids = [Command.link(other.id)]
        self.assertFalse(row.with_context(allowed_company_ids=[other.id]).with_user(self.quality).has_access("read"))

    def test_immutable_versioned_evidence_hold_and_forged_defaults(self):
        row = self.provider()
        first = self.evidence(row, valid_until=fields.Date.today())
        replacement = self.evidence(row, previous_id=first.id)
        self.assertEqual(replacement.previous_id, first)
        self.assertEqual(first.data.content, PDF)
        self.assertTrue(first.checksum)
        for record, vals in (
            (first, {"source": "rewrite"}),
            (row.event_ids[0], {"details": "rewrite"}),
            (row, {"state": "active"}),
        ):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                record.write(vals)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.evidence(row, previous_id=first.id)
        forged = (
            self.env["training.provider.dossier"]
            .with_user(self.quality)
            .with_context(default_state="active", default_frozen=True)
            .create({"name": "Safe", "kind": "watch", "quality_id": self.quality.id, "retention_id": self.retention.id})
        )
        self.assertEqual(forged.state, "draft")
        self.assertFalse(forged.frozen)
        row.write({"frozen": True})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.evidence(row)
        row.write({"frozen": False})
        for record in (row, first, row.event_ids[0]):
            with self.assertRaises((AccessError, ValidationError)), self.env.cr.savepoint():
                record.unlink()

    def test_subcontract_control_owner_deadline_evidence_and_history(self):
        row = self.provider("subcontract")
        obligation = (
            self.env["training.provider.obligation"]
            .with_user(self.coordinator)
            .create(
                {
                    "dossier_id": row.id,
                    "name": "Fictional contract requirement",
                    "due_date": fields.Date.today() - timedelta(days=1),
                }
            )
        )
        row.action_review()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            obligation.with_user(self.quality).action_conform()
        proof = self.evidence(row)
        obligation.write({"evidence_id": proof.id, "control": "Signed fictional contract checked"})
        obligation.with_user(self.quality).action_nonconform()
        self.assertEqual(obligation.state, "nonconform")
        self.assertEqual(obligation.checked_by_id, self.quality)
        self.assertTrue(obligation.checked_at)
        count = len(row.event_ids)
        obligation.with_user(self.quality).action_nonconform()
        self.assertEqual(len(row.event_ids), count)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            obligation.write({"control": "Rewrite historical finding"})
        with self.assertRaises((AccessError, ValidationError)), self.env.cr.savepoint():
            obligation.unlink()

    def test_expired_evidence_warns_in_session_wizard_and_async_without_block(self):
        row = self.provider()
        today = fields.Date.today()
        first = self.evidence(row, valid_from=today - timedelta(days=5), valid_until=today - timedelta(days=1))
        delivery = self.delivery(
            kind="session", start_at=str(today), end_at=str(today + timedelta(days=3)), timezone="UTC"
        )
        service = self.env["training.provider.service"].with_user(self.coordinator)
        self.assertTrue(service._assignment_warning(self.portal_b.partner_id, delivery.company_id, today))
        wizard = Form(
            self.env["training.session.edit"].with_user(self.coordinator).with_context(default_delivery_id=delivery.id)
        )
        wizard.instructor_id = self.portal_b.partner_id
        self.assertTrue(wizard.instructor_warning)
        wizard.save().action_apply()
        self.assertTrue(delivery.session_ids)
        delivery.write({"evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)]})
        self.assertTrue(delivery.instructor_warning)
        self.evidence(row, previous_id=first.id, valid_from=today)
        delivery.invalidate_recordset()
        self.assertFalse(delivery.instructor_warning)
        # Generic warning is safe even for an unassigned coordinator; no labels.
        row.write({"member_ids": [Command.clear()]})
        self.assertFalse(row.with_user(self.coordinator).has_access("read"))
        self.assertFalse(service._assignment_warning(self.portal_b.partner_id, delivery.company_id, today))
        self.assertFalse(
            service.with_user(self.portal_b)._assignment_warning(self.portal_b.partner_id, delivery.company_id, today)
        )

    def test_authorization_audit_revocation_and_no_implicit_grants(self):
        before = self.env["training.evaluation.authorization"].sudo().search_count([])
        row = self.provider()
        self.evidence(row)
        row.action_review()
        self.assertEqual(self.env["training.evaluation.authorization"].sudo().search_count([]), before)
        assignment, grant = self.assigned_evaluation()
        self.assertEqual(grant.issued_by_id, self.quality)
        self.assertTrue(grant.issued_at)
        self.decision(assignment)
        grant.write({"active": False})
        self.assertEqual(grant.revoked_by_id, self.quality)
        revoked = grant.revoked_at
        grant.write({"active": False})
        self.assertEqual(grant.revoked_at, revoked)
        with self.assertRaises(AccessError):
            self.decision(assignment)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            grant.write({"active": True})

        inactive = (
            self.env["training.evaluation.authorization"]
            .with_user(self.quality)
            .with_context(default_issued_by_id=self.other_quality.id, default_revoked_at="2099-01-01")
            .create(
                {
                    "delivery_id": assignment.delivery_id.id,
                    "user_id": self.portal_b.id,
                    "purpose": grant.purpose,
                    "valid_from": grant.valid_from,
                    "valid_until": grant.valid_until,
                    "reason": "Fictional withdrawn initial decision",
                    "active": False,
                }
            )
        )
        self.assertEqual(inactive.issued_by_id, self.quality)
        self.assertEqual(inactive.revoked_by_id, self.quality)
        self.assertEqual(inactive.issued_at, inactive.revoked_at)

    def test_s10_projection_applies_grants_before_counts_and_pagination(self):
        first = self.provider()
        hidden = self.provider(quality_id=self.other_quality.id)
        hidden.with_user(self.other_quality).write({"member_ids": [Command.clear()]})
        service = self.env["training.provider.service"].with_user(self.quality)
        self.assertEqual(
            service._states(limit=1),
            {"total": 1, "rows": [{"id": first.id, "kind": "instructor", "state": "draft", "frozen": False}]},
        )
        self.assertEqual(service._states(offset=1)["rows"], [])

    def test_native_forms_and_french_labels(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(["training_management"], ["fr_FR"])
        model = self.env["training.provider.dossier"].with_user(self.coordinator).with_context(lang="fr_FR")
        form = Form(model)
        form.name = "Fictional native watch"
        form.kind = "watch"
        form.quality_id = self.quality
        form.retention_id = self.retention
        form.source = "https://example.test/native"
        form.observed_on = fields.Date.today()
        row = form.save().with_user(self.quality)
        with Form(row) as editable:
            editable.analysis = "Fictional native analysis"
            editable.decision = "Documented decision"
            editable.no_impact_reason = "Already addressed"
        row.action_review()
        arch = model.get_view(view_type="form")["arch"]
        self.assertIn("Analyser le dossier", arch)
        self.assertIn("Veille analysée", arch)
        self.assertIn("Ajouter un justificatif", arch)
        self.assertEqual(row.action_add_evidence()["name"], "Ajouter un justificatif")
        descriptions = self.env["training.provider.event"].with_context(lang="fr_FR").fields_get(["operation"])
        labels = dict(descriptions["operation"]["selection"])
        self.assertEqual(labels["created"], "Création")
        self.assertEqual(labels["evidence"], "Justificatif ajouté")
        self.assertEqual(labels["controlled"], "Contrôle consigné")
        for model_name in ("training.session", "training.delivery", "training.session.edit"):
            description = self.env[model_name].with_context(lang="fr_FR").fields_get(["instructor_warning"])
            self.assertEqual(description["instructor_warning"]["string"], "Justificatifs de l’intervenant")

    def test_native_dossier_form_saves_evidence_and_obligations(self):
        row = self.provider("subcontract")
        with Form(row) as form:
            with form.evidence_ids.new() as evidence:
                evidence.name = "native.pdf"
                evidence.competence = "Contract scope"
                evidence.source = "Fictional signed contract"
                evidence.data = BinaryBytes(PDF)
        self.assertEqual(row.evidence_ids.data.content, PDF)
        with Form(row) as form:
            with form.obligation_ids.new() as obligation:
                obligation.name = "Native obligation"
                obligation.due_date = fields.Date.today()
                obligation.evidence_id = row.evidence_ids
                obligation.control = "Fictional control findings"
        self.assertEqual(len(row.obligation_ids), 1)
        row.action_review()
        with Form(row) as form:
            with form.obligation_ids.edit(0) as obligation:
                obligation.control = "Corrected pending findings"
        self.assertEqual(row.state, "draft")
        row.obligation_ids.action_nonconform()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            row.obligation_ids.action_conform()
        # Parent commands must not provide an alternate way to move or erase evidence.
        foreign = self.provider("subcontract")
        for field, command in (
            ("evidence_ids", Command.link(row.evidence_ids.id)),
            ("obligation_ids", Command.link(row.obligation_ids.id)),
            ("event_ids", Command.clear()),
        ):
            with self.assertRaises((AccessError, ValidationError)), self.env.cr.savepoint():
                foreign.write({field: [command]})
        row.write({"frozen": True})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            row.write(
                {
                    "evidence_ids": [
                        Command.create(
                            {"name": "late.pdf", "competence": "Scope", "source": "Fictional", "data": BinaryBytes(PDF)}
                        )
                    ]
                }
            )

    def test_direct_child_changes_invalidate_review(self):
        row = self.provider()
        first = self.evidence(row)
        row.action_review()
        self.evidence(row, previous_id=first.id)
        self.assertEqual(row.state, "draft")
        self.assertIn("reviewed", row.event_ids.mapped("operation"))
        contract = self.provider("subcontract")
        obligation = (
            self.env["training.provider.obligation"]
            .with_user(self.quality)
            .create({"dossier_id": contract.id, "name": "Initial obligation", "due_date": fields.Date.today()})
        )
        contract.action_review()
        obligation.write({"control": "Changed requirement control"})
        self.assertEqual(contract.state, "draft")
        contract.action_review()
        self.env["training.provider.obligation"].with_user(self.quality).create(
            {"dossier_id": contract.id, "name": "Additional obligation", "due_date": fields.Date.today()}
        )
        self.assertEqual(contract.state, "draft")

    def test_assignment_warning_covers_multiday_session_and_future_async(self):
        today = fields.Date.today()
        row = self.provider()
        self.evidence(row, valid_until=today + timedelta(days=1))
        delivery = self.delivery(
            kind="session", start_at=str(today), end_at=str(today + timedelta(days=10)), timezone="UTC"
        )
        wizard = (
            self.env["training.session.edit"]
            .with_user(self.coordinator)
            .create(
                {
                    "delivery_id": delivery.id,
                    "instructor_id": self.portal_b.partner_id.id,
                    "start_date": today,
                    "end_date": today + timedelta(days=2),
                }
            )
        )
        self.assertTrue(wizard.instructor_warning)
        session = (
            self.env["training.session"]
            .with_user(self.coordinator)
            .create(
                {
                    "name": "Multiday fictional session",
                    "delivery_id": delivery.id,
                    "instructor_id": self.portal_b.partner_id.id,
                    "mode": "onsite",
                    "start_date": today,
                    "end_date": today + timedelta(days=2),
                }
            )
        )
        self.assertTrue(session.instructor_warning)
        # A dated cohort can carry an asynchronous mission without any session.
        asynchronous = self.delivery(
            kind="session",
            start_at=str(today + timedelta(days=3)),
            end_at=str(today + timedelta(days=5)),
            timezone="UTC",
        )
        asynchronous.write({"evaluation_instructor_ids": [Command.set(self.portal_b.partner_id.ids)]})
        self.assertTrue(asynchronous.instructor_warning)


@tagged("post_install", "-at_install")
class TestProviderHttp(EvaluationCase, HttpCase):
    def test_native_binary_route_rechecks_grants_even_with_token(self):
        row = (
            self.env["training.provider.dossier"]
            .with_user(self.quality)
            .create(
                {
                    "name": "PRIVATE HTTP provider",
                    "kind": "watch",
                    "quality_id": self.quality.id,
                    "retention_id": self.retention.id,
                }
            )
        )
        evidence = (
            self.env["training.provider.evidence"]
            .with_user(self.quality)
            .create(
                {
                    "dossier_id": row.id,
                    "name": "PRIVATE-credential.pdf",
                    "competence": "Fictional scope",
                    "source": "PRIVATE issuer",
                    "data": BinaryBytes(PDF),
                }
            )
        )
        token = limited_field_access_token(evidence, "data", scope="binary")
        url = "/web/content/%s/%s/data?download=true&access_token=%s" % (evidence._name, evidence.id, token)
        self.authenticate(self.quality.login, self.quality.login)
        self.assertEqual(self.url_open(url).content, PDF)
        for user in (self.other_quality, self.portal_b):
            self.authenticate(user.login, user.login)
            response = self.url_open(url)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("PRIVATE", response.text)
        self.authenticate(None, None)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("PRIVATE", response.text)
