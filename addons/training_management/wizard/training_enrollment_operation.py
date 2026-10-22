from odoo import fields, models, _
from odoo.exceptions import ValidationError


class TrainingEnrollmentOperation(models.TransientModel):
    _name = "training.enrollment.operation"
    _description = "Training Enrollment Operation"
    _check_company_auto = True

    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="enrollment_id.company_id")
    operation = fields.Selection([("reserve", "Propose or Reserve a Place"), ("extend", "Extend Access"), ("report", "Report to Another Delivery"), ("replace", "Replace Participant")], required=True, default="reserve")
    deadline = fields.Datetime()
    target_id = fields.Many2one("training.enrollment", string="New Requested Enrollment", check_company=True)
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        self.enrollment_id._require_coordinator()
        if not (self.reason or "").strip():
            raise ValidationError(_("A reason is required."))
        with self.env.cr.savepoint():
            enrollment = self.enrollment_id
            enrollment.write({"change_reason": self.reason})
            if self.operation == "reserve":
                enrollment.action_reserve(self.deadline)
            elif self.operation == "extend":
                enrollment.action_extend_access(self.deadline)
            else:
                if not self.target_id:
                    raise ValidationError(_("Choose a new requested enrollment."))
                enrollment.action_transfer(self.target_id.id, replacement=self.operation == "replace")
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
            self.allocation_id.write({"change_reason": self.reason})
            self.allocation_id.action_release_places(self.quantity)
        return {"type": "ir.actions.act_window_close"}
