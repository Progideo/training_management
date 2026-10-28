"""P09: immutable pedagogical composition; existing enrollments remain authoritative."""

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, ValidationError

COORDINATOR = "training_management.group_training_coordinator"


class TrainingPath(models.Model):
    _name = "training.path"
    _description = "Training Path"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    revision = fields.Integer(default=0, readonly=True, copy=False)
    state = fields.Selection(
        [("draft", "Draft"), ("validated", "Validated")], default="draft", required=True, readonly=True, copy=False
    )
    order_policy = fields.Selection(
        [("recommended", "Recommended Order"), ("mandatory", "Mandatory Order")], default="recommended", required=True
    )
    step_ids = fields.One2many("training.path.step", "path_id", copy=True)
    assignment_ids = fields.One2many(
        "training.path.assignment", "path_id", readonly=True, copy=False, groups=COORDINATOR
    )
    duration_hours = fields.Float(compute="_compute_duration")

    @api.depends("step_ids.program_id.duration_hours")
    def _compute_duration(self):
        for path in self:
            path.duration_hours = sum(path.step_ids.program_id.mapped("duration_hours"))

    @api.private
    def _lock_definition(self):  # pylint: disable=missing-return  # lock and fence only
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()
        if any(p.state != "draft" for p in self):
            raise ValidationError(self.env._("Keep validated paths unchanged; create a new path version."))
        # Child edits must also change the parent row: a stale REPEATABLE READ
        # validator must retry and inspect the newly committed definition.
        for path in self:
            super(TrainingPath, path).write({"revision": path.revision + 1})  # pylint: disable=super-method-mismatch

    def write(self, vals):
        with self.env.cr.savepoint():
            if set(vals) == {"active"}:
                self.check_access("write")
                self.lock_for_update()
                return super().write(vals)
            self._lock_definition()
            if {"state", "revision"} & vals.keys():
                raise ValidationError(self.env._("Use the validation action."))
            return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(
            v.get("state", self.env.context.get("default_state", "draft")) != "draft" or v.get("revision", 0)
            for v in vals_list
        ):
            raise ValidationError(self.env._("Create a draft path."))
        return super().create([dict(v, revision=0, state="draft") for v in vals_list])

    def copy(self, default=None):
        self.ensure_one()
        result = super().copy(default)
        if "step_ids" not in (default or {}):
            by_position = {step.sequence: step for step in result.step_ids}
            for source in self.step_ids:
                by_position[source.sequence].prerequisite_ids = [
                    Command.set([by_position[p.sequence].id for p in source.prerequisite_ids])
                ]
        return result

    def action_validate(self):
        with self.env.cr.savepoint():
            self._lock_definition()
            for path in self:
                if not path.step_ids or any(
                    s.program_id.state not in ("validated", "published") for s in path.step_ids
                ):
                    raise ValidationError(self.env._("Choose at least one validated programme."))
                path.step_ids._check_definition()
            return super().write({"state": "validated"})  # pylint: disable=super-method-mismatch  # checked transition bypasses the public content write guard

    @api.ondelete(at_uninstall=False)
    def _unlink_draft_only(self):
        self._lock_definition()


class TrainingPathStep(models.Model):
    _name = "training.path.step"
    _description = "Training Path Step"
    _order = "sequence, id"
    _rec_name = "program_id"
    _check_company_auto = True

    path_id = fields.Many2one("training.path", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="path_id.company_id", store=True)
    program_id = fields.Many2one("training.program.version", required=True, ondelete="restrict", check_company=True)
    course_id = fields.Many2one(related="program_id.course_id", store=True)
    sequence = fields.Integer(default=10, required=True)
    prerequisite_ids = fields.Many2many(
        "training.path.step", "training_path_prerequisite_rel", "step_id", "prerequisite_id", copy=False
    )
    _unique_program = models.Constraint("UNIQUE(path_id, course_id)", "Use each course once in a path.")
    _unique_sequence = models.Constraint("UNIQUE(path_id, sequence)", "Use distinct step positions.")

    @api.constrains("path_id", "company_id", "program_id", "sequence", "prerequisite_ids")
    def _check_definition(self):
        for step in self:
            if step.program_id.company_id != step.company_id:
                raise ValidationError(self.env._("Choose a standard programme from the path company."))
            if any(p.path_id != step.path_id or p.sequence >= step.sequence for p in step.prerequisite_ids):
                raise ValidationError(self.env._("Prerequisites must be earlier steps of this path."))
        # Changing an earlier position must also validate incoming references.
        for dependant in self.search([("prerequisite_ids", "in", self.ids)]):
            if any(p.sequence >= dependant.sequence for p in dependant.prerequisite_ids):
                raise ValidationError(self.env._("Prerequisites must precede their dependants."))

    @api.model_create_multi
    def create(self, vals_list):
        paths = self.env["training.path"].browse(
            [v.get("path_id") or self.env.context.get("default_path_id") for v in vals_list]
        )
        paths._lock_definition()
        return super().create(vals_list)

    def write(self, vals):
        with self.env.cr.savepoint():
            self.path_id._lock_definition()
            if "path_id" in vals:
                raise ValidationError(self.env._("Keep a step in its original path."))
            return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_draft_only(self):
        self.path_id._lock_definition()


class TrainingPathAssignment(models.Model):
    _name = "training.path.assignment"
    _inherit = "training.controlled"
    _description = "Training Path Enrollment Reference"
    _check_company_auto = True
    _rec_name = "enrollment_id"

    step_id = fields.Many2one("training.path.step", required=True, ondelete="restrict", check_company=True)
    path_id = fields.Many2one(related="step_id.path_id", store=True)
    # Keep native check_company selection domains usable before step selection.
    company_id = fields.Many2one("res.company", required=True, readonly=True, default=lambda self: self.env.company)
    enrollment_id = fields.Many2one(
        "training.enrollment", required=True, ondelete="restrict", check_company=True, index=True
    )
    participant_id = fields.Many2one(related="enrollment_id.participant_id", store=True)
    equivalence_reason = fields.Text()
    validated_by = fields.Many2one("res.users", readonly=True, required=True, default=lambda self: self.env.user)
    validated_at = fields.Datetime(readonly=True, required=True, default=fields.Datetime.now)
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    withdrawn_at = fields.Datetime(readonly=True, copy=False)
    withdrawn_by = fields.Many2one("res.users", readonly=True, copy=False)
    withdrawal_reason = fields.Text(readonly=True, copy=False)
    _reason_actions = ("action_withdraw",)

    completed = fields.Boolean(compute="_compute_status")
    blocked = fields.Boolean(compute="_compute_status")
    _one_step = models.UniqueIndex(
        "(step_id, participant_id) WHERE withdrawn_at IS NULL", "This participant already has this path step."
    )
    _one_source = models.UniqueIndex(
        "(path_id, participant_id, enrollment_id) WHERE withdrawn_at IS NULL",
        "Do not count an enrollment twice in the same path.",
    )

    @api.private
    def _is_completed(self):
        self.ensure_one()
        enrollment = self.enrollment_id
        required = enrollment.delivery_id.learning_activity_ids.filtered(lambda a: not a.optional)
        service = self.env["training.learning.service"]
        return (
            bool(required)
            and enrollment.state in ("confirmed", "closed")
            and all(service._complete(enrollment, activity) for activity in required)
        )

    @api.private
    def _is_blocked(self):
        self.ensure_one()
        required = self.step_id.prerequisite_ids
        if self.path_id.order_policy == "mandatory":
            required |= self.path_id.step_ids.filtered(lambda s: s.sequence < self.step_id.sequence)
        references = self.search(
            [
                ("step_id", "in", required.ids),
                ("participant_id", "=", self.participant_id.id),
                ("withdrawn_at", "=", False),
            ]
        )
        return len(references) != len(required) or any(not r._is_completed() for r in references)

    @api.depends(
        "enrollment_id.state",
        "enrollment_id.learning_progress_ids.state",
        "enrollment_id.learning_progress_ids.declared_at",
        "enrollment_id.learning_progress_ids.latest_submission_id",
        "enrollment_id.delivery_id.learning_activity_ids",
        "enrollment_id.delivery_id.learning_activity_ids.optional",
    )
    def _compute_status(self):
        for assignment in self:
            assignment.completed = assignment._is_completed()
            assignment.blocked = assignment._is_blocked()

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access("create")
        if not self.env.su and not self.env.user.has_group(COORDINATOR):
            raise AccessError(self.env._("Only a training coordinator may validate path references."))
        with self.env.cr.savepoint():
            prepared = []
            seen_steps, seen_sources = set(), set()
            enrollments = self.env["training.enrollment"].browse([v.get("enrollment_id") for v in vals_list])
            enrollments._require_coordinator()
            enrollments.delivery_id._serialize()
            for values in vals_list:
                if set(values) - {"step_id", "enrollment_id", "equivalence_reason"}:
                    raise ValidationError(self.env._("Validation metadata is generated by the server."))
                step = self.env["training.path.step"].browse(values.get("step_id"))
                step.check_access("read")
                step.path_id.lock_for_update()
                step.path_id.invalidate_recordset()
                enrollment = enrollments.browse(values.get("enrollment_id"))
                if step.path_id.state != "validated" or step.company_id != enrollment.company_id:
                    raise ValidationError(self.env._("Use a validated path in the enrollment company."))
                if enrollment.program_id != step.program_id and not (values.get("equivalence_reason") or "").strip():
                    raise ValidationError(self.env._("Explain and validate the equivalence between programmes."))
                step_key = (step.id, enrollment.participant_id.id)
                source_key = (step.path_id.id, enrollment.id)
                if (
                    step_key in seen_steps
                    or source_key in seen_sources
                    or self.search_count(
                        [
                            ("path_id", "=", step.path_id.id),
                            ("participant_id", "=", enrollment.participant_id.id),
                            ("withdrawn_at", "=", False),
                            "|",
                            ("step_id", "=", step.id),
                            ("enrollment_id", "=", enrollment.id),
                        ]
                    )
                ):
                    raise ValidationError(self.env._("This step or enrollment is already counted in this path."))
                seen_steps.add(step_key)
                seen_sources.add(source_key)
                prepared.append(
                    dict(
                        values,
                        company_id=step.company_id.id,
                        validated_by=self.env.uid,
                        validated_at=fields.Datetime.now(),
                        withdrawn_at=False,
                        withdrawn_by=False,
                        withdrawal_reason=False,
                    )
                )
            records = super().create(prepared)
            for record in records:
                if record.enrollment_id.access_state == "active" and record._is_blocked():
                    raise ValidationError(self.env._("Resolve path prerequisites before linking an active enrollment."))
            return records

    @api.private
    def _reason_labels(self):
        return {"action_withdraw": self.env._("Withdraw Path Reference")}

    def action_withdraw(self, reason=None):
        with self.env.cr.savepoint():
            self._require_coordinator()
            self.delivery_id._serialize()
            self.invalidate_recordset()
            for reference in self:
                if reference.withdrawn_at:
                    continue
                reference._store(
                    {
                        "withdrawn_at": fields.Datetime.now(),
                        "withdrawn_by": self.env.uid,
                        "withdrawal_reason": self._require_reason(reason),
                    },
                    reason,
                )
        return True

    def write(self, vals):  # pylint: disable=method-required-super
        raise AccessError(self.env._("Keep validated path references and their history unchanged."))

    @api.ondelete(at_uninstall=False)
    def _unlink_keep_history(self):
        raise ValidationError(self.env._("Keep validated path references and their history unchanged."))


class TrainingEnrollment(models.Model):
    _inherit = "training.enrollment"  # pylint: disable=consider-merging-classes-inherited  # P09 access constraints have their own lifecycle

    @api.private
    def _path_blocked(self):
        # Called only by the existing admission/access policy on an identified
        # enrollment. Narrow sudo reads restrictions; no private data is returned.
        references = (
            self.env["training.path.assignment"]
            .sudo()
            .search([("enrollment_id", "=", self.id), ("withdrawn_at", "=", False)])
        )
        return any(r._is_blocked() for r in references)

    def action_open_access(self, reason=None):
        with self.env.cr.savepoint():
            self._require_coordinator()
            self.delivery_id._serialize()
            if any(e._path_blocked() for e in self):
                raise ValidationError(self.env._("Complete the blocking path prerequisites before opening access."))
            return super().action_open_access(reason=reason)

    @api.private
    def _effective_state(self, now=None):
        result = super()._effective_state(now=now)
        return "blocked" if result == "active" and self._path_blocked() else result
