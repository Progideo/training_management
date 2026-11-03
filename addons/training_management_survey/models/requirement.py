"""Offer assignments become immutable, typed enrollment obligations at confirmation."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

OBLIGATIONS = [("optional", "Optional"), ("complete", "Required to Complete"), ("pass", "Required to Pass")]


class Requirement(models.Model):
    _name = "training.exam.requirement"
    _description = "Frozen Enrollment Exam Obligation"
    enrollment_id = fields.Many2one(
        "training.enrollment", required=True, readonly=True, ondelete="restrict", index=True
    )
    delivery_id = fields.Many2one(related="enrollment_id.delivery_id", store=True)
    company_id = fields.Many2one(related="enrollment_id.company_id", store=True)
    activity_id = fields.Many2one("training.learning.activity", required=True, readonly=True, ondelete="restrict")
    exam_id = fields.Many2one("survey.survey", required=True, readonly=True, ondelete="restrict")
    obligation = fields.Selection(OBLIGATIONS, required=True, readonly=True)
    _one_requirement = models.Constraint(
        "UNIQUE(enrollment_id, activity_id)", "This enrollment already has this exam obligation."
    )

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # controlled snapshot factory only
        raise AccessError(self.env._("Exam obligations are fixed by enrollment confirmation."))

    def write(self, vals):  # pylint: disable=method-required-super  # immutable evidence
        raise AccessError(self.env._("Keep the frozen exam obligations."))

    @api.ondelete(at_uninstall=False)
    def _keep_requirements(self):
        raise AccessError(self.env._("Keep the frozen exam obligations."))

    @api.private
    def _capture(self, enrollment):
        enrollment.ensure_one()
        enrollment._require_coordinator()
        if enrollment.state != "confirmed":
            raise ValidationError(self.env._("Confirm enrollment before freezing exam obligations."))
        activities = enrollment.delivery_id.learning_activity_ids.filtered(
            lambda a: a.training_exam_id.training_course_id
        )
        values = []
        for activity in activities:
            activity._check_evaluation_configuration()
            if not self.sudo().search_count([("enrollment_id", "=", enrollment.id), ("activity_id", "=", activity.id)]):
                values.append(
                    {
                        "enrollment_id": enrollment.id,
                        "activity_id": activity.id,
                        "exam_id": activity.training_exam_id.id,
                        "obligation": activity.exam_obligation,
                    }
                )
        if values:
            return super(Requirement, self.sudo().with_context({})).create(values)  # pylint: disable=super-method-mismatch,context-overridden  # authorized factory strips RPC defaults
        return self.browse()

    @api.private
    def _for_activity(self, enrollment, activity):
        return self.sudo().search([("enrollment_id", "=", enrollment.id), ("activity_id", "=", activity.id)], limit=1)

    @api.private
    def _assigned_exam(self, enrollment, activity):
        if not activity or activity.delivery_id != enrollment.delivery_id:
            raise AccessError(self.env._("This private exam is unavailable."))
        # Classification only: quality may compute scalar completion without reading questions.
        activity = activity.sudo()
        if not activity.training_exam_id.training_course_id:
            return activity.training_exam_id
        requirement = self._for_activity(enrollment, activity)
        if (
            not requirement
            or requirement.exam_id.training_course_id != enrollment.delivery_id.program_id.course_id
            or requirement.exam_id.mock_company_id != enrollment.company_id
        ):
            raise AccessError(self.env._("This private exam is unavailable."))
        return requirement.exam_id


class Enrollment(models.Model):
    _inherit = "training.enrollment"

    @api.private
    def _store(self, values, reason=False):
        was_confirmed = self.state == "confirmed"
        result = super()._store(values, reason)
        if values.get("state") == "confirmed" and not was_confirmed:
            self.env["training.exam.requirement"]._capture(self)
        return result


class Activity(models.Model):
    _inherit = "training.learning.activity"
    exam_obligation = fields.Selection(OBLIGATIONS)
    shared_exam = fields.Boolean(compute="_compute_shared_exam")

    @api.depends("training_exam_id.training_course_id")
    def _compute_shared_exam(self):
        for activity in self:
            activity.shared_exam = bool(activity.sudo().training_exam_id.training_course_id)

    @api.private
    def _exam_offer_frozen(self):
        self.delivery_id._serialize()
        return self.env["training.enrollment"].sudo().search_count(
            [("delivery_id", "in", self.delivery_id.ids), ("state", "=", "confirmed")]
        ) or self.env["training.exam.requirement"].sudo().search_count([("delivery_id", "in", self.delivery_id.ids)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            exam = self.env["survey.survey"].browse(
                vals.get("training_exam_id") or self.env.context.get("default_training_exam_id")
            )
            if exam.training_course_id:
                delivery = self.env["training.delivery"].browse(
                    vals.get("delivery_id") or self.env.context.get("default_delivery_id")
                )
                delivery._require_coordinator()
                delivery._serialize()
                if (
                    self.env["training.enrollment"]
                    .sudo()
                    .search_count([("delivery_id", "=", delivery.id), ("state", "=", "confirmed")])
                ):
                    raise ValidationError(self.env._("Use a new offer for new exam obligations after enrollment."))
                vals.setdefault("exam_obligation", self.env.context.get("default_exam_obligation", "pass"))
                vals["optional"] = vals["exam_obligation"] == "optional"
        return super().create(vals_list)

    def write(self, vals):
        affected = self.filtered(lambda a: a.training_exam_id.training_course_id)
        target = self.env["survey.survey"].browse(vals.get("training_exam_id"))
        if target.training_course_id:
            affected |= self
        configuration = {
            "training_exam_id",
            "exam_obligation",
            "criterion",
            "optional",
            "delivery_id",
            "dependency_ids",
            "evaluation_threshold",
        }
        if affected and configuration & vals.keys() and affected._exam_offer_frozen():
            raise ValidationError(self.env._("Use a new offer for new exam obligations after enrollment."))
        if "exam_obligation" in vals:
            vals = {**vals, "optional": vals["exam_obligation"] == "optional"}
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _keep_shared_assignments(self):
        affected = self.filtered(lambda a: a.training_exam_id.training_course_id)
        if affected and affected._exam_offer_frozen():
            raise ValidationError(self.env._("Keep activities referenced by frozen exam obligations."))

    @api.constrains("exam_obligation", "training_exam_id", "optional")
    def _check_shared_obligation(self):
        for activity in self.filtered(lambda a: a.training_exam_id.training_course_id):
            if not activity.exam_obligation or activity.optional != (activity.exam_obligation == "optional"):
                raise ValidationError(self.env._("Match the optional flag to the exam obligation."))


class LearningService(models.AbstractModel):
    _inherit = "training.learning.service"

    @api.private
    def _shared_exam_status(self, enrollment, activity):
        requirement = self.env["training.exam.requirement"]._for_activity(enrollment, activity)
        if not requirement:
            return {
                "required": activity.exam_obligation != "optional",
                "complete": False,
                "success": False,
                "satisfied": False,
                "score": None,
            }
        exam = self.env["training.exam.requirement"]._assigned_exam(enrollment, activity)
        return self.env["training.exam.service"]._obligation_status(
            exam, "training.enrollment:%s" % enrollment.id, enrollment.participant_id.id, requirement.obligation
        )

    @api.private
    def _complete(self, enrollment, activity):
        if activity.sudo().training_exam_id.training_course_id:
            return self._shared_exam_status(enrollment, activity)["satisfied"]
        return super()._complete(enrollment, activity)

    @api.private
    def _evaluation_result(self, enrollment, activity):
        if activity.sudo().training_exam_id.training_course_id:
            return self._shared_exam_status(enrollment, activity)["score"]
        return super()._evaluation_result(enrollment, activity)

    @api.private
    def _evaluation_snapshot(self, enrollment, activity):
        snapshot = super()._evaluation_snapshot(enrollment, activity)
        if activity.sudo().training_exam_id.training_course_id:
            requirement = self.env["training.exam.requirement"]._for_activity(enrollment, activity)
            snapshot.update(requirement=requirement.id, obligation=requirement.obligation, exam=requirement.exam_id.id)
        return snapshot

    @api.private
    def _certificate_origin(self, enrollment, activity):
        origin = super()._certificate_origin(enrollment, activity)
        if activity.sudo().training_exam_id.training_course_id:
            requirement = self.env["training.exam.requirement"]._for_activity(enrollment, activity)
            origin["threshold"] = requirement.exam_id.scoring_success_min if requirement.obligation == "pass" else False
        return origin

    @api.private
    def _rows(self, enrollment):
        rows = super()._rows(enrollment)
        for row in rows:
            activity = self.env["training.learning.activity"].sudo().browse(row["id"])
            if activity.sudo().training_exam_id.training_course_id:
                row["exam_obligation"] = activity.exam_obligation
                row["criterion_label"] = dict(activity._fields["exam_obligation"]._description_selection(self.env))[
                    activity.exam_obligation
                ]
        return rows


class Progress(models.Model):
    _inherit = "training.learning.progress"

    @api.private
    def _is_complete(self):
        if self.activity_id.sudo().training_exam_id.training_course_id:
            return self.env["training.learning.service"]._shared_exam_status(self.enrollment_id, self.activity_id)[
                "satisfied"
            ]
        return super()._is_complete()


class Attempt(models.Model):
    _inherit = "survey.user_input"  # pylint: disable=consider-merging-classes-inherited  # contextual progress invalidation is separate from native orientation

    @api.private
    def _invalidate_exam_progress(self):
        for attempt in self.filtered("training_enrollment_id"):
            self.env["training.learning.progress"].sudo().search(
                [
                    ("enrollment_id", "=", attempt.training_enrollment_id.id),
                    ("activity_id", "=", attempt.training_activity_id.id),
                ]
            ).invalidate_recordset(["completed"])

    @api.private
    def _training_finish(self):
        result = super()._training_finish()
        self._invalidate_exam_progress()
        return result


class Revision(models.Model):
    _inherit = "training.exam.revision"

    @api.private
    def _record(self, attempt, points, reason):
        revision = super()._record(attempt, points, reason)
        attempt._invalidate_exam_progress()
        return revision
