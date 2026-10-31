"""Pedagogical criteria and immutable evidence, on the existing S03 enrollment."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain

from .training_material import COORDINATOR

ENTRY_MODEL = "training.learning.entry"


class LearningActivity(models.Model):
    _name = "training.learning.activity"
    _description = "Training Learning Activity"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    instructions = fields.Text(translate=True)
    criterion = fields.Selection(
        [
            ("declaration", "Declared Consultation"),
            ("submission", "Exercise Submission"),
            ("validation", "Tutor Validation"),
            ("evaluation", "Evaluation Threshold (S06)"),
        ],
        required=True,
        default="declaration",
    )
    optional = fields.Boolean()
    due_days = fields.Integer(
        string="Due After Access Opens (Days)", help="Zero uses the delivery deadline, if configured."
    )
    evaluation_threshold = fields.Float(default=0, string="Evaluation Threshold (%)")
    material_assignment_id = fields.Many2one("training.material.assignment", ondelete="restrict", check_company=True)
    dependency_ids = fields.Many2many(
        "training.learning.activity",
        "training_learning_dependency_rel",
        "activity_id",
        "dependency_id",
        string="Prerequisite Activities",
        copy=False,
    )
    progress_ids = fields.One2many("training.learning.progress", "activity_id", readonly=True, copy=False)

    @api.model
    def _supports_mock_exams(self):
        return False

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(allfields=allfields, attributes=attributes)
        if not self._supports_mock_exams() and "selection" in result.get("criterion", {}):
            result["criterion"]["selection"] = [
                item for item in result["criterion"]["selection"] if item[0] != "evaluation"
            ]
        return result

    @api.constrains("criterion")
    def _check_evaluation_configuration(self):
        if any(activity.criterion == "evaluation" for activity in self):
            raise ValidationError(
                self.env._("Install the native Surveys integration before choosing a mock exam criterion.")
            )

    @api.constrains(
        "dependency_ids", "delivery_id", "optional", "due_days", "evaluation_threshold", "material_assignment_id"
    )
    def _check_definition(self):
        for activity in self:
            if activity.due_days < 0 or not 0 <= activity.evaluation_threshold <= 100:
                raise ValidationError(self.env._("Use non-negative deadlines and a threshold between 0 and 100."))
            if activity.material_assignment_id and activity.material_assignment_id.delivery_id != activity.delivery_id:
                raise ValidationError(self.env._("Choose a PDF reference from this delivery."))
            if any(d.delivery_id != activity.delivery_id for d in activity.dependency_ids):
                raise ValidationError(self.env._("Prerequisite activities must belong to the same delivery."))
            if not activity.optional and any(activity.dependency_ids.mapped("optional")):
                raise ValidationError(self.env._("An optional activity cannot block a required activity."))
            activity.dependency_ids._check_evaluation_configuration()
            todo, seen = activity.dependency_ids, self.browse()
            while todo:
                if activity in todo:
                    raise ValidationError(self.env._("Activity dependencies cannot form a cycle."))
                seen |= todo
                todo = todo.dependency_ids - seen
        # Editing an optional prerequisite must also check its existing dependants.
        if self:
            dependants = self.search([("dependency_ids", "in", self.ids), ("optional", "=", False)])
            if any(dependants.dependency_ids.mapped("optional")):
                raise ValidationError(self.env._("An optional activity cannot block a required activity."))

    @api.model_create_multi
    def create(self, vals_list):
        deliveries = self.env["training.delivery"].browse(
            [v.get("delivery_id") or self.env.context.get("default_delivery_id") for v in vals_list]
        )
        deliveries._require_coordinator()
        deliveries._serialize()
        return super().create(vals_list)

    def write(self, vals):
        self.delivery_id._require_coordinator()
        self.delivery_id._serialize()
        # A criterion that already has evidence cannot silently change meaning.
        if self.progress_ids or "delivery_id" in vals or "progress_ids" in vals:
            raise ValidationError(
                self.env._("Keep activities with recorded work unchanged; add a new activity instead.")
            )
        result = super().write(vals)
        self.search([("dependency_ids", "in", self.ids)])._check_definition()
        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_keep_work(self):
        if self.progress_ids:
            raise ValidationError(self.env._("Keep activities with recorded work."))


class LearningEvidence(models.AbstractModel):
    _name = "training.learning.evidence"
    _description = "Server-authored Learning Evidence"

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # all evidence is generated by private checked operations
        raise AccessError(self.env._("Learning evidence is generated by the authorized learning action."))

    def write(self, vals):  # pylint: disable=method-required-super  # immutable public API
        raise AccessError(self.env._("Keep learning evidence and its history unchanged."))

    @api.ondelete(at_uninstall=False)
    def _unlink_keep_evidence(self):
        raise ValidationError(self.env._("Keep learning evidence and its history unchanged."))

    def copy_data(self, default=None):  # pylint: disable=method-required-super  # do not clone authors, work or evidence
        raise ValidationError(self.env._("Learning evidence cannot be copied."))

    def _export_rows(self, fields, *, _is_toplevel_call=True):  # pylint: disable=method-required-super  # includes native relational export traversal
        self.check_access("read")
        raise UserError(self.env._("Private learning evidence cannot be exported in bulk."))

    @api.private
    def _create_evidence(self, values):
        # Private callers have checked the exact enrollment, actor and operation.
        clean = {
            k: v
            for k, v in self.env.context.items()
            if not k.startswith("default_") and k not in ("bin_size", "bin_size_data")
        }
        clean.update(tracking_disable=True, mail_create_nosubscribe=True)
        if self._name in (ENTRY_MODEL, "training.practice.entry"):
            # Native switch: a submitted original is evidence, not a web image.
            clean["image_no_postprocess"] = True
        return super(LearningEvidence, self.sudo().with_context(clean)).create(values)  # pylint: disable=context-overridden,super-method-mismatch  # narrow, server-authored evidence factory

    @api.private
    def _store_evidence(self, values):
        return super().write(values)  # pylint: disable=super-method-mismatch  # private state update after the same enrollment lock


class LearningProgress(models.Model):
    _name = "training.learning.progress"
    _inherit = "training.learning.evidence"
    _description = "Enrollment Activity Progress"
    _check_company_auto = True
    _rec_name = "activity_id"

    enrollment_id = fields.Many2one(
        "training.enrollment", required=True, ondelete="restrict", check_company=True, index=True
    )
    activity_id = fields.Many2one("training.learning.activity", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    declared_at = fields.Datetime(readonly=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("submitted", "Submitted"),
            ("changes", "Changes Requested"),
            ("validated", "Validated"),
        ],
        default="pending",
        required=True,
        readonly=True,
    )
    latest_submission_id = fields.Many2one(ENTRY_MODEL, ondelete="restrict", readonly=True, groups="base.group_system")
    revision = fields.Integer(readonly=True, default=0)
    completed = fields.Boolean(compute="_compute_completed")
    _one_progress = models.Constraint(
        "UNIQUE(enrollment_id, activity_id)", "This activity already has a progress record."
    )

    @api.depends("activity_id.criterion", "declared_at", "state", "latest_submission_id")
    def _compute_completed(self):
        for progress in self:
            progress.completed = progress._is_complete()

    @api.private
    def _is_complete(self):
        self.ensure_one()
        criterion = self.activity_id.criterion
        if criterion == "declaration":
            return bool(self.declared_at)
        if criterion == "submission":
            return bool(self.sudo().latest_submission_id)
        if criterion == "validation":
            return self.state == "validated"
        result = self.env["training.learning.service"]._evaluation_result(self.enrollment_id, self.activity_id)
        return result is not None and result >= self.activity_id.evaluation_threshold


class LearningEntry(models.Model):
    _name = ENTRY_MODEL
    _inherit = ["training.learning.evidence", "mail.thread"]
    _description = "Private Learning Entry"
    _order = "id"
    _check_company_auto = True
    _rec_name = "kind"

    enrollment_id = fields.Many2one(
        "training.enrollment", required=True, ondelete="restrict", check_company=True, index=True
    )
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    activity_id = fields.Many2one("training.learning.activity", ondelete="restrict", check_company=True)
    kind = fields.Selection(
        [
            ("submission", "Exercise Submission"),
            ("correction", "Correction"),
            ("question", "Private Help Request"),
            ("answer", "Private Answer"),
        ],
        required=True,
    )
    parent_id = fields.Many2one(ENTRY_MODEL, ondelete="restrict", check_company=True)
    request_key = fields.Char(required=True, readonly=True)
    fingerprint = fields.Char(required=True, readonly=True)
    decision = fields.Selection([("accepted", "Accepted"), ("changes", "Changes Requested")], readonly=True)
    message_id = fields.Many2one("mail.message", readonly=True, ondelete="restrict", copy=False)
    data = fields.Binary(attachment=True, readonly=True, copy=False, string="Private File")
    filename = fields.Char(readonly=True)
    sealed_at = fields.Datetime(readonly=True)
    sha256 = fields.Char(readonly=True)
    _one_request = models.Constraint(
        "UNIQUE(enrollment_id, request_key)", "This learning request has already been processed."
    )

    def _access_domain(self, operation):
        domain = super()._access_domain(operation)
        if operation == "read":
            service = self.env["training.learning.service"]
            participant = (
                self.env["training.document.policy"]._enrollments().filtered(lambda e: service._is_participant(e))
            )
            allowed = participant | service._tutored_enrollments()
            domain &= Domain("enrollment_id", "in", allowed.ids)
        return domain

    def _can_return_content(self, field_name=None, access_token=None):
        self.env["training.document.policy"]._check_read(self)
        return field_name == "data"


class TrainingDelivery(models.Model):
    _inherit = "training.delivery"  # pylint: disable=consider-merging-classes-inherited  # S05 learning and S09 evaluations have separate roles

    learning_activity_ids = fields.One2many("training.learning.activity", "delivery_id", groups=COORDINATOR)
    learning_tutor_id = fields.Many2one("res.users", ondelete="restrict", groups=COORDINATOR)
    learning_due_days = fields.Integer(string="Learning Deadline After Access Opens (Days)", groups=COORDINATOR)
    learning_inactivity_days = fields.Integer(string="Inactivity Before Reminder (Days)", groups=COORDINATOR)
    learning_reminder_days = fields.Integer(string="Reminder Interval (Days)", groups=COORDINATOR)
    learning_notice_ids = fields.One2many("training.learning.notice", "delivery_id", readonly=True, groups=COORDINATOR)

    @api.constrains(
        "learning_tutor_id", "company_id", "learning_due_days", "learning_inactivity_days", "learning_reminder_days"
    )
    def _check_learning_settings(self):
        for delivery in self:
            tutor = delivery.learning_tutor_id
            if tutor and (not tutor.active or delivery.company_id not in tutor.company_ids):
                raise ValidationError(self.env._("Assign an active tutor authorized for this operating company."))
            if min(
                delivery.learning_due_days, delivery.learning_inactivity_days, delivery.learning_reminder_days
            ) < 0 or (delivery.learning_inactivity_days and not delivery.learning_reminder_days):
                raise ValidationError(
                    self.env._("Use non-negative learning settings and an interval when reminders are enabled.")
                )

    @api.model
    def _cron_learning_reminders(self):
        return self.env["training.learning.service"]._cron_reminders()

    def action_add_learning_activity(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Add Learning Activity"),
            "res_model": "training.learning.activity",
            "view_mode": "form",
            "context": {"default_delivery_id": self.id},
        }


class TrainingEnrollment(models.Model):
    _inherit = "training.enrollment"  # pylint: disable=consider-merging-classes-inherited  # S05 progress and S08 document issuance have separate lifecycles

    learning_tutor_id = fields.Many2one(
        "res.users", ondelete="restrict", string="Individual Tutor", groups=COORDINATOR, copy=False
    )
    learning_progress_ids = fields.One2many(
        "training.learning.progress", "enrollment_id", readonly=True, groups=COORDINATOR
    )

    @api.constrains("learning_tutor_id", "company_id")
    def _check_learning_tutor(self):
        for enrollment in self:
            tutor = enrollment.learning_tutor_id
            if tutor and (not tutor.active or enrollment.company_id not in tutor.company_ids):
                raise ValidationError(self.env._("Assign an active tutor authorized for this operating company."))

    def write(self, vals):
        if "learning_tutor_id" not in vals:
            return super().write(vals)
        self._require_coordinator()
        with self.env.cr.savepoint():
            self.delivery_id._serialize()
            remaining = {k: v for k, v in vals.items() if k != "learning_tutor_id"}
            if remaining:
                super().write(remaining)
            vals = {"learning_tutor_id": vals["learning_tutor_id"]}
            for enrollment in self:
                enrollment._store(vals)
            self._check_learning_tutor()
        return True
