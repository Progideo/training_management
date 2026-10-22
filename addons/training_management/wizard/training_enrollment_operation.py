from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TrainingEnrollmentOperation(models.TransientModel):
    _name = "training.enrollment.operation"
    _description = "Training Enrollment Operation"
    _check_company_auto = True

    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="enrollment_id.company_id")
    operation = fields.Selection([("reserve", "Propose or Reserve a Place"), ("extend", "Extend Access"), ("postpone", "Postpone to Another Delivery"), ("replace", "Replace Participant")], required=True, default="reserve")
    deadline = fields.Datetime()
    target_id = fields.Many2one("training.enrollment", string="New Requested Enrollment", check_company=True)
    source_delivery_id = fields.Many2one(related="enrollment_id.delivery_id")
    source_participant_id = fields.Many2one(related="enrollment_id.participant_id")
    source_allocation_id = fields.Many2one(related="enrollment_id.allocation_id")
    reason = fields.Text(required=True)

    @api.onchange("operation")
    def _onchange_operation(self):
        self.target_id = False

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        self.enrollment_id._require_coordinator()
        if not (self.reason or "").strip():
            raise ValidationError(_("A reason is required."))
        with self.env.cr.savepoint():
            enrollment = self.enrollment_id
            if self.operation == "reserve":
                enrollment.action_reserve(self.deadline, reason=self.reason)
            elif self.operation == "extend":
                enrollment.action_extend_access(self.deadline, reason=self.reason)
            else:
                if not self.target_id:
                    raise ValidationError(_("Choose a new requested enrollment."))
                if self.operation == "replace":
                    enrollment.action_replace(self.target_id.id, reason=self.reason)
                else:
                    enrollment.action_postpone(self.target_id.id, reason=self.reason)
        return {"type": "ir.actions.act_window_close"}


class TrainingDeliveryDates(models.TransientModel):
    _name = "training.delivery.dates"
    _description = "Change Training Delivery Dates"
    _check_company_auto = True

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id")
    kind = fields.Selection(related="delivery_id.kind")
    access_policy = fields.Selection(related="delivery_id.access_policy")
    start_at = fields.Datetime()
    end_at = fields.Datetime()
    access_start = fields.Datetime()
    access_end = fields.Datetime()
    reason = fields.Text(required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        delivery = self.env["training.delivery"].browse(values.get("delivery_id") or self.env.context.get("default_delivery_id"))
        if delivery:
            for name in ("start_at", "end_at", "access_start", "access_end"):
                if name in fields_list and name not in values:
                    values[name] = delivery[name]
        return values

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        self.delivery_id._require_coordinator()
        delivery = self.delivery_id
        with self.env.cr.savepoint():
            delivery.action_change_dates(
                start_at=self.start_at if delivery.kind == "session" else None,
                end_at=self.end_at if delivery.kind == "session" else None,
                access_start=self.access_start if delivery.access_policy == "fixed" else None,
                access_end=self.access_end if delivery.access_policy == "fixed" else None,
                reason=self.reason,
            )
        return {"type": "ir.actions.act_window_close"}


class TrainingAllocationExtend(models.TransientModel):
    _name = "training.allocation.extend"
    _description = "Extend a Training Reservation Deadline"
    _check_company_auto = True

    allocation_id = fields.Many2one("training.seat.allocation", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="allocation_id.company_id")
    expires_at = fields.Datetime(string="New Deadline", required=True)
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        self.allocation_id._require_coordinator()
        with self.env.cr.savepoint():
            self.allocation_id.action_extend_deadline(self.expires_at, reason=self.reason)
        return {"type": "ir.actions.act_window_close"}


class TrainingAllocationRelease(models.TransientModel):
    _name = "training.allocation.release"
    _description = "Release Training Places"
    _check_company_auto = True

    allocation_id = fields.Many2one("training.seat.allocation", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="allocation_id.company_id")
    quantity = fields.Integer(required=True, default=1)
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        self.allocation_id._require_coordinator()
        with self.env.cr.savepoint():
            self.allocation_id.action_release_places(self.quantity, reason=self.reason)
        return {"type": "ir.actions.act_window_close"}
