"""EVA01: immutable definitions, scoped assignments and append-only decisions."""

import math

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools.binary import BinaryBytes

COORDINATOR = "training_management.group_training_coordinator"
QUALITY = "training_management.group_training_quality"
SUPERVISOR = "training_management.group_training_supervisor"
PURPOSES = [("positioning", "Positioning"), ("acquired", "Learning Outcomes")]


def clean_context(record):
    # Replace rather than merge: caller defaults must not forge evidence fields.
    return record.with_context(  # pylint: disable=context-overridden
        {k: v for k, v in record.env.context.items() if not k.startswith("default_")}
    )


class EvaluationDelivery(models.Model):
    _inherit = "training.delivery"

    evaluation_supervisor_ids = fields.Many2many("res.users", string="Assigned Supervisors", groups=COORDINATOR)
    evaluation_instructor_ids = fields.Many2many(
        "res.partner",
        "training_evaluation_instructor_rel",
        string="Delivery Instructors",
        groups=COORDINATOR,
        help="Explicit teaching mission, including asynchronous delivery without a session.",
    )
    evaluation_quality_id = fields.Many2one("res.users", string="Evaluation Quality Reviewer", groups=COORDINATOR)
    evaluation_authorization_ids = fields.One2many(
        "training.evaluation.authorization", "delivery_id", groups=COORDINATOR
    )

    @api.constrains("evaluation_supervisor_ids", "evaluation_quality_id")
    def _check_evaluation_roles(self):
        for delivery in self:
            for user in delivery.evaluation_supervisor_ids:
                if not user.active or not user.has_group(SUPERVISOR) or delivery.company_id not in user.company_ids:
                    raise ValidationError(self.env._("Assign an active supervisor authorized for this company."))
            quality = delivery.evaluation_quality_id
            if quality and (
                not quality.active or not quality.has_group(QUALITY) or delivery.company_id not in quality.company_ids
            ):
                raise ValidationError(self.env._("Assign an active quality reviewer authorized for this company."))


class EvaluationAuthorization(models.Model):
    _name = "training.evaluation.authorization"
    _description = "Scoped Evaluation Authorization"
    _check_company_auto = True

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    purpose = fields.Selection(PURPOSES, required=True)
    valid_from = fields.Datetime(required=True, default=fields.Datetime.now)
    valid_until = fields.Datetime(required=True)
    active = fields.Boolean(default=True)
    reason = fields.Text(required=True)

    issued_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    issued_at = fields.Datetime(readonly=True, copy=False)
    revoked_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    revoked_at = fields.Datetime(readonly=True, copy=False)

    @api.private
    def _authorize_delivery(self, delivery):
        if (
            not self.env.user.active
            or not self.env.user.has_group(QUALITY)
            or delivery.sudo().evaluation_quality_id != self.env.user
        ):
            raise AccessError(self.env._("Only the assigned quality reviewer may authorize evaluators."))
        if delivery.sudo().company_id not in self.env.user.company_ids:
            raise AccessError(self.env._("This delivery is unavailable."))
        delivery.sudo()._serialize()

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            if set(vals) & {"issued_by_id", "issued_at", "revoked_by_id", "revoked_at"}:
                raise AccessError(self.env._("Authorization audit fields are server controlled."))
            self._authorize_delivery(self.env["training.delivery"].browse(vals.get("delivery_id")))
            now = fields.Datetime.now()
            decision = dict(vals, issued_by_id=self.env.uid, issued_at=now)
            if vals.get("active") is False:
                decision.update(revoked_by_id=self.env.uid, revoked_at=now)
            prepared.append(decision)
        return super(EvaluationAuthorization, clean_context(self)).create(prepared)

    def write(self, vals):
        for row in self:
            self._authorize_delivery(row.delivery_id)
        if set(vals) - {"active"}:
            raise ValidationError(self.env._("Retain authorization decisions; revoke and create a new authorization."))
        if vals.get("active") and any(not row.active for row in self):
            raise ValidationError(self.env._("A withdrawn authorization cannot be reactivated; create a new decision."))
        for row in self:
            prepared = dict(vals)
            if vals.get("active") is False and not row.revoked_at:
                prepared.update(revoked_by_id=self.env.uid, revoked_at=fields.Datetime.now())
            super(EvaluationAuthorization, row).write(prepared)
        return True

    @api.constrains("user_id", "valid_from", "valid_until", "reason")
    def _check_definition(self):
        for row in self:
            if (
                row.valid_until <= row.valid_from
                or not row.reason.strip()
                or not row.user_id.active
                or row.company_id not in row.user_id.company_ids
            ):
                raise ValidationError(self.env._("Set a valid period, an authorized user and a reason."))

    @api.ondelete(at_uninstall=False)
    def _keep_authorizations(self):
        raise ValidationError(self.env._("Retain authorization decisions."))


class Evaluation(models.Model):
    _name = "training.evaluation"
    _description = "Versioned Training Evaluation"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    program_id = fields.Many2one("training.program.version", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="program_id.company_id", store=True)
    purpose = fields.Selection(PURPOSES, required=True)
    version = fields.Char(required=True, default="1")
    previous_id = fields.Many2one("training.evaluation", copy=False, readonly=True, ondelete="restrict")
    criteria = fields.Text(required=True, translate=True)
    scored = fields.Boolean(default=True)
    threshold = fields.Float(default=70)
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")], default="draft", readonly=True, copy=False
    )
    published_at = fields.Datetime(readonly=True, copy=False)
    published_by_id = fields.Many2one("res.users", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.delivery"]._require_coordinator()
        if any(set(v) & {"state", "published_at", "published_by_id", "previous_id"} for v in vals_list):
            raise AccessError(self.env._("Use the publication and version actions."))
        return super(Evaluation, clean_context(self)).create(vals_list)

    def write(self, vals):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()
        if self.filtered(lambda e: e.state == "published") or set(vals) & {
            "state",
            "published_at",
            "published_by_id",
            "previous_id",
        }:
            raise ValidationError(self.env._("Published evaluations are immutable; create a new version."))
        return super().write(vals)

    @api.constrains("threshold", "criteria")
    def _check_definition(self):
        for evaluation in self:
            if (
                not math.isfinite(evaluation.threshold)
                or not 0 <= evaluation.threshold <= 100
                or not evaluation.criteria.strip()
            ):
                raise ValidationError(self.env._("Provide criteria and a finite threshold between zero and 100."))

    def action_publish(self):
        self.env["training.delivery"]._require_coordinator()
        self.check_access("write")
        self.lock_for_update()
        for evaluation in self.filtered(lambda e: e.state == "draft"):
            evaluation._publish_questionnaire()
            super(Evaluation, evaluation).write(  # pylint: disable=super-method-mismatch  # checked publication factory
                {"state": "published", "published_at": fields.Datetime.now(), "published_by_id": self.env.uid}
            )
        return True

    @api.private
    def _publish_questionnaire(self):
        """Optional native Survey integration; the core also records observed assessments."""
        return True

    def action_new_version(self):
        self.ensure_one()
        self.env["training.delivery"]._require_coordinator()
        self.check_access("read")
        if self.state != "published":
            raise ValidationError(self.env._("Publish the source first."))
        new = self.copy({"version": self.version + "+"})
        super(Evaluation, new).write({"previous_id": self.id})  # pylint: disable=super-method-mismatch
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": new.id, "view_mode": "form"}

    @api.ondelete(at_uninstall=False)
    def _keep_definitions(self):
        if self.filtered(lambda e: e.state == "published"):
            raise ValidationError(self.env._("Retain published evaluations."))


class EvaluationAssignment(models.Model):
    _name = "training.evaluation.assignment"
    _description = "Assigned Training Evaluation"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    evaluation_id = fields.Many2one("training.evaluation", required=True, ondelete="restrict", check_company=True)
    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="restrict", check_company=True)
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    participant_name = fields.Char(related="enrollment_id.participant_id.name", store=True)
    purpose = fields.Selection(related="evaluation_id.purpose", store=True)
    opens_at = fields.Datetime(required=True, default=fields.Datetime.now)
    due_at = fields.Datetime(required=True)
    state = fields.Selection(
        [
            ("expected", "Expected"),
            ("not_started", "Not Started"),
            ("in_progress", "In Progress"),
            ("submitted", "Completed / Awaiting Validation"),
            ("validated", "Validated"),
        ],
        compute="_compute_status",
    )
    result_available = fields.Boolean(compute="_compute_status")
    score = fields.Float(compute="_compute_status")
    threshold = fields.Float(related="evaluation_id.threshold")
    reference_id = fields.Many2one(
        "training.evaluation.result", readonly=True, copy=False, ondelete="restrict", groups=COORDINATOR + "," + QUALITY
    )
    result_ids = fields.One2many(
        "training.evaluation.result", "assignment_id", readonly=True, groups=COORDINATOR + "," + QUALITY
    )
    attempt_number = fields.Integer(default=1, readonly=True)
    revision = fields.Integer(default=0, readonly=True)
    started_at = fields.Datetime(readonly=True)
    submitted_at = fields.Datetime(readonly=True)

    _unique_assignment = models.Constraint(
        "UNIQUE(evaluation_id, enrollment_id)", "This evaluation version is already assigned."
    )

    @api.depends("evaluation_id.name", "participant_name")
    def _compute_name(self):
        for row in self:
            row.name = "%s — %s" % (row.evaluation_id.name, row.participant_name)

    @api.depends("started_at", "submitted_at", "reference_id", "opens_at", "attempt_number")
    def _compute_status(self):
        for row in self:
            ref = row.sudo().reference_id
            if ref.attempt_number != row.attempt_number:
                ref = self.env["training.evaluation.result"]
            row.state = (
                "validated"
                if ref
                else "submitted"
                if row.submitted_at
                else "in_progress"
                if row.started_at
                else "expected"
                if row.opens_at > fields.Datetime.now()
                else "not_started"
            )
            # Assigned readers may see the score without reading definitions or decisions.
            row.result_available = bool(ref and row.sudo().evaluation_id.scored)
            row.score = ref.score if row.result_available else 0

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.delivery"]._require_coordinator()
        allowed = {"evaluation_id", "enrollment_id", "opens_at", "due_at"}
        if any(set(v) - allowed for v in vals_list):
            raise AccessError(self.env._("Evaluation state is server controlled."))
        return super(EvaluationAssignment, clean_context(self)).create(vals_list)

    def write(self, vals):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Use the checked evaluation actions."))

    @api.constrains("evaluation_id", "enrollment_id", "opens_at", "due_at")
    def _check_assignment(self):
        for row in self:
            if (
                row.evaluation_id.state != "published"
                or row.evaluation_id.program_id != row.delivery_id.program_id
                or row.due_at <= row.opens_at
            ):
                raise ValidationError(
                    self.env._("Assign a published evaluation of this programme with a valid period.")
                )

    @api.private
    def _store(self, vals):
        return super().write(vals)  # pylint: disable=super-method-mismatch  # checked private transition

    def action_record(self):
        self.ensure_one()
        self.env["training.evaluation.service"]._assignment(self.id, evaluate=True)
        return {
            "type": "ir.actions.act_window",
            "res_model": "training.evaluation.record",
            "view_mode": "form",
            "target": "new",
            "context": {"default_assignment_id": self.id, "default_revision": self.revision},
        }

    def action_export_proof(self):
        self.ensure_one()
        self.check_access("read")
        dossier = self.env["training.closure"].search([("enrollment_id", "=", self.enrollment_id.id)], limit=1)
        dossier._authorize()
        dossier._serialize()
        if not dossier or dossier.state == "closed" or self.state != "validated":
            raise ValidationError(self.env._("Choose an open closure dossier and a validated evaluation."))
        result = self.sudo().reference_id
        category = "assessment" if self.purpose == "acquired" else "positioning"
        if category == "assessment" and not self.evaluation_id.scored:
            raise ValidationError(
                self.env._("A qualitative assessment cannot supply a scored achievement certificate.")
            )
        source = "training.evaluation.result:%s; S091-QWEB-1" % result.id
        existing = self.env["training.proof"].search(
            [("dossier_id", "=", dossier.id), ("source", "=", source)], limit=1
        )
        if existing:
            proof = existing
        else:
            engine = self.env["ir.actions.report"]
            report = self.env.ref("training_management.report_evaluation")
            values = self.env["report.training_management.evaluation_document"]._get_report_values([result.id])
            html = engine._render_template("training_management.evaluation_document", values).decode()
            data = engine._run_pdf_engine_without_processing(engine._get_pdf_engine(report), [html], report_ref=report)
            if not data.startswith(b"%PDF-"):
                raise ValidationError(self.env._("Evaluation PDF generation failed."))
            proof = self.env["training.proof"].create(
                {
                    "dossier_id": dossier.id,
                    "category": category,
                    "source": source,
                    "author": result.author_id.name,
                    "produced_at": result.create_date,
                    "data": BinaryBytes(data),
                    "filename": "evaluation-%s.pdf" % result.id,
                    "score": result.score,
                    "threshold": self.threshold,
                }
            )
        return {"type": "ir.actions.act_window", "res_model": "training.proof", "res_id": proof.id, "view_mode": "form"}

    @api.ondelete(at_uninstall=False)
    def _keep_assignments(self):
        raise ValidationError(self.env._("Retain evaluation assignments and their history."))


class EvaluationResult(models.Model):
    _name = "training.evaluation.result"
    _description = "Immutable Evaluation Decision"
    _order = "id desc"

    assignment_id = fields.Many2one("training.evaluation.assignment", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="assignment_id.company_id", store=True)
    previous_id = fields.Many2one("training.evaluation.result", ondelete="restrict")
    attempt_number = fields.Integer(required=True)
    kind = fields.Selection(
        [("validation", "Validation"), ("reopening", "Reopening")], required=True, default="validation"
    )
    score = fields.Float()
    conclusion = fields.Text(required=True)
    source = fields.Text(required=True)
    reason = fields.Text(required=True)
    author_id = fields.Many2one("res.users", required=True, ondelete="restrict")

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Use the evaluation validation action."))

    def write(self, vals):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Evaluation decisions are immutable."))

    @api.private
    def _record(self, vals):
        return super(EvaluationResult, clean_context(self).sudo()).create(vals)  # pylint: disable=super-method-mismatch

    @api.ondelete(at_uninstall=False)
    def _keep_results(self):
        raise ValidationError(self.env._("Retain evaluation decisions."))


class EvaluationService(models.AbstractModel):
    _name = "training.evaluation.service"
    _description = "Scoped Evaluation Operations"

    @api.private
    def _staff(self, delivery):
        user = self.env.user
        if not user.active or user._is_public() or delivery.company_id not in user.company_ids:
            return False
        if user.has_group(COORDINATOR):
            return True
        if user.has_group(SUPERVISOR) and user in delivery.evaluation_supervisor_ids:
            return True
        if user.has_group(QUALITY) and delivery.evaluation_quality_id == user:
            return True
        return self._teaching_mission(delivery)

    @api.private
    def _teaching_mission(self, delivery):
        user = self.env.user
        return user.partner_id in delivery.evaluation_instructor_ids or bool(
            self.env["training.session"]
            .sudo()
            .search_count(
                [
                    ("delivery_id", "=", delivery.id),
                    ("instructor_id", "=", user.partner_id.id),
                    ("cancelled", "=", False),
                ],
                limit=1,
            )
        )

    @api.private
    def _assignment(self, assignment_id, *, evaluate=False, participant=False, lock=False):
        row = self.env["training.evaluation.assignment"].sudo().browse(assignment_id).exists()
        user = self.env.user
        if not row or not user.active or user._is_public() or row.company_id not in user.company_ids:
            raise AccessError(self.env._("This evaluation is unavailable."))
        own = self.env["training.learning.service"]._is_participant(row.enrollment_id)
        if (participant and not own) or (not participant and not own and not self._staff(row.delivery_id)):
            raise AccessError(self.env._("This evaluation is unavailable."))
        if lock:
            row.delivery_id._serialize()
            row.invalidate_recordset()
            return self._assignment(assignment_id, evaluate=evaluate, participant=participant)
        if evaluate:
            now = fields.Datetime.now()
            grant = (
                self.env["training.evaluation.authorization"]
                .sudo()
                .search_count(
                    [
                        ("delivery_id", "=", row.delivery_id.id),
                        ("user_id", "=", user.id),
                        ("purpose", "=", row.purpose),
                        ("active", "=", True),
                        ("valid_from", "<=", now),
                        ("valid_until", ">=", now),
                    ],
                    limit=1,
                )
            )
            if not grant or not self._teaching_mission(row.delivery_id) or row.enrollment_id.user_id == user:
                raise AccessError(
                    self.env._("A current teaching assignment and evaluation authorization are required.")
                )
        return row

    @api.private
    def _start(self, assignment_id):
        row = self._assignment(assignment_id, participant=True, lock=True)
        now = fields.Datetime.now()
        if not row.opens_at <= now <= row.due_at or row.submitted_at:
            raise ValidationError(self.env._("This evaluation is not open for a new attempt."))
        if not row.started_at:
            row._store({"started_at": now, "revision": row.revision + 1})
        return row

    @api.private
    def _submit(self, assignment_id):
        row = self._assignment(assignment_id, participant=True, lock=True)
        if row.submitted_at:
            return row
        if not row.started_at or fields.Datetime.now() > row.due_at:
            raise ValidationError(self.env._("Start the evaluation and submit before its deadline."))
        row._store({"submitted_at": fields.Datetime.now(), "revision": row.revision + 1})
        return row

    @api.private
    def _validate(self, assignment_id, *, revision, score, conclusion, source, reason):
        row = self._assignment(assignment_id, evaluate=True, lock=True)
        if row.revision != revision or not all((x or "").strip() for x in (conclusion, source, reason)):
            raise ValidationError(
                self.env._("Reload the current evaluation and provide conclusion, source and reason.")
            )
        if not row.evaluation_id.scored:
            score = 0
        if score is None or not math.isfinite(score) or not 0 <= score <= 100:
            raise ValidationError(self.env._("Use a finite score between zero and 100."))
        result = self.env["training.evaluation.result"]._record(
            {
                "assignment_id": row.id,
                "previous_id": row.reference_id.id,
                "attempt_number": row.attempt_number,
                "score": score if row.evaluation_id.scored else 0,
                "conclusion": conclusion,
                "source": source,
                "reason": reason,
                "author_id": self.env.uid,
            }
        )
        now = fields.Datetime.now()
        row._store(
            {
                "reference_id": result.id,
                "started_at": row.started_at or now,
                "submitted_at": row.submitted_at or now,
                "revision": row.revision + 1,
            }
        )
        return result


class EvaluationReport(models.AbstractModel):
    _name = "report.training_management.evaluation_document"
    _description = "Dedicated Evaluation Evidence Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env["training.evaluation.result"].browse(docids)
        records.check_access("read")
        if any(row.kind != "validation" for row in records):
            raise AccessError(self.env._("Only validated evaluations can supply evidence."))
        return {
            "docs": records,
            "purpose_labels": dict(self.env["training.evaluation"]._fields["purpose"]._description_selection(self.env)),
        }


class EvaluationPortalService(models.AbstractModel):
    _inherit = "training.evaluation.service"

    @api.private
    def _visible_domain(self):
        user = self.env.user
        if not user.active or user._is_public():
            return [("id", "=", False)]
        company = Domain("company_id", "in", user.company_ids.ids)
        if user.has_group(COORDINATOR):
            delivery_domain = company
        else:
            sessions = (
                self.env["training.session"]
                .sudo()
                .search(company & Domain("instructor_id", "=", user.partner_id.id) & Domain("cancelled", "=", False))
            )
            rights = Domain("evaluation_instructor_ids", "in", user.partner_id.ids) | Domain(
                "id", "in", sessions.delivery_id.ids
            )
            if user.has_group(SUPERVISOR):
                rights |= Domain("evaluation_supervisor_ids", "in", user.ids)
            if user.has_group(QUALITY):
                rights |= Domain("evaluation_quality_id", "=", user.id)
            delivery_domain = company & rights
        allowed = self.env["training.delivery"].sudo().search(delivery_domain)
        own = (
            self.env["training.document.policy"]
            ._enrollments()
            .filtered(self.env["training.learning.service"]._is_participant)
        )
        return company & (Domain("delivery_id", "in", allowed.ids) | Domain("enrollment_id", "in", own.ids))

    @api.private
    def _state_label(self, row):
        return dict(row._fields["state"]._description_selection(self.env))[row.state]

    @api.private
    def _portal_values(self, row):
        try:
            self._assignment(row.id, evaluate=True)
            can_evaluate = True
        except AccessError:
            can_evaluate = False
        ref = (
            row.reference_id
            if row.result_available or row.state == "validated"
            else self.env["training.evaluation.result"]
        )
        return {
            "row_id": row.id,
            "name": row.name,
            "purpose": dict(row._fields["purpose"]._description_selection(self.env))[row.purpose],
            "version": row.evaluation_id.version,
            "criteria": row.evaluation_id.criteria,
            "state": self._state_label(row),
            "validated": row.state == "validated",
            "due": row.due_at,
            "revision": row.revision,
            "attempt_number": row.attempt_number,
            "scored": row.evaluation_id.scored,
            "has_score": row.result_available,
            "score": row.score,
            "threshold": row.threshold,
            "conclusion": ref.conclusion if ref else False,
            "can_evaluate": can_evaluate,
            "can_reopen": self.env.user.has_group(COORDINATOR),
            "own": self.env["training.learning.service"]._is_participant(row.enrollment_id),
            "online": False,
            "review_answers": [],
            "proposed_score": None,
            "questions": [],
            "history": [
                {
                    "attempt": result.attempt_number,
                    "score": result.score,
                    "scored": row.evaluation_id.scored,
                    "conclusion": result.conclusion,
                    "date": result.create_date,
                }
                for result in row.result_ids.filtered(lambda r: r.kind == "validation")
            ]
            if (can_evaluate or self.env["training.learning.service"]._is_participant(row.enrollment_id))
            else [],
            "submitted": bool(row.submitted_at),
            "started": bool(row.started_at),
        }

    @api.private
    def _participant_attempt(self, assignment_id, attempt_number):
        row = self._assignment(assignment_id, participant=True, lock=True)
        if row.attempt_number != attempt_number:
            raise ValidationError(self.env._("Reload the current evaluation attempt before answering."))
        return row

    @api.private
    def _portal_answers(self, assignment_id, post, *, attempt_number, submit=False):
        self._participant_attempt(assignment_id, attempt_number)
        if submit:
            return self._submit(assignment_id)
        return self._assignment(assignment_id, participant=True)

    @api.private
    def _reopen(self, assignment_id, *, revision, reason, due_at):
        row = self._assignment(assignment_id, lock=True)
        self.env["training.delivery"]._require_coordinator()
        due = fields.Datetime.to_datetime(due_at)
        if row.revision != revision or not (reason or "").strip() or not due or due <= fields.Datetime.now():
            raise ValidationError(self.env._("Reload and provide a reason and future deadline."))
        if not row.submitted_at:
            raise ValidationError(self.env._("Complete the current attempt first."))
        self.env["training.evaluation.result"]._record(
            {
                "assignment_id": row.id,
                "kind": "reopening",
                "previous_id": row.reference_id.id,
                "attempt_number": row.attempt_number,
                "source": str(row.due_at),
                "conclusion": str(due),
                "reason": reason,
                "author_id": self.env.uid,
            }
        )
        row._store(
            {
                "attempt_number": row.attempt_number + 1,
                "started_at": False,
                "submitted_at": False,
                "opens_at": fields.Datetime.now(),
                "due_at": due,
                "revision": row.revision + 1,
            }
        )
        return row
