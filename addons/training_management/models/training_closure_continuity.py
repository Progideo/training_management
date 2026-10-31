"""Audited reviewer transfers and rectifications, preserving prior evidence."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_closure import COORDINATOR, QUALITY, ClosureDossier as OriginalClosure


class ClosureEvent(models.Model):
    _name = "training.closure.event"
    _inherit = "training.learning.evidence"
    _description = "Closure Dossier History"
    _order = "id desc"
    _check_company_auto = True

    dossier_id = fields.Many2one("training.closure", required=True, ondelete="restrict", index=True)
    company_id = fields.Many2one(related="dossier_id.company_id", store=True)
    operation = fields.Selection(
        [("reassign", "Reviewer Reassigned"), ("rectify", "Reopened for Rectification"), ("close", "Dossier Closed")],
        required=True,
    )
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    occurred_at = fields.Datetime(required=True)
    reason = fields.Text()
    previous_quality_id = fields.Many2one("res.users", ondelete="restrict")
    quality_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    closed_at = fields.Datetime(string="Recorded Closure Date")
    closed_by_id = fields.Many2one("res.users", string="Recorded Closure Author", ondelete="restrict")


class ClosureDossier(models.Model):
    _inherit = "training.closure"

    event_ids = fields.One2many("training.closure.event", "dossier_id", readonly=True, copy=False)

    @api.private
    def _record_lifecycle(self, operation, reason=None, previous_quality=None):
        self.ensure_one()
        # Each private caller has checked authority and serialized the dossier.
        return self.env["training.closure.event"]._create_evidence(
            {
                "dossier_id": self.id,
                "operation": operation,
                "actor_id": self.env.uid,
                "occurred_at": fields.Datetime.now(),
                "reason": reason or False,
                "previous_quality_id": previous_quality.id if previous_quality else False,
                "quality_id": self.quality_id.id,
                "closed_at": self.closed_at,
                "closed_by_id": self.closed_by_id.id,
            }
        )

    @api.private
    def _continuity_action(self, operation):
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reassign Quality Reviewer")
            if operation == "reassign"
            else self.env._("Rectify Closed Dossier"),
            "res_model": "training.closure.change",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_dossier_id": self.id,
                "default_operation": operation,
                "default_expected_quality_id": self.quality_id.id,
                "default_expected_closure_event_id": self.event_ids.filtered(lambda e: e.operation == "close")[:1].id,
            },
        }

    def action_reassign_quality(self, quality_id=None, reason=None, expected_quality_id=None):
        record = self.sudo(False)
        record.ensure_one()
        record._authorize()
        if not record.env.user.has_group(COORDINATOR):
            raise AccessError(record.env._("Only a coordinator may reassign the quality reviewer."))
        if reason is None:
            return record._continuity_action("reassign")
        if not reason.strip():
            raise ValidationError(record.env._("Explain the reviewer reassignment."))
        record._serialize()
        if record.quality_id.id == quality_id:
            return True
        if expected_quality_id is not None and record.quality_id.id != expected_quality_id:
            raise ValidationError(record.env._("The reviewer has changed. Reload the dossier."))
        reviewer = record.env["res.users"].sudo().browse(quality_id).exists() if quality_id else record.env["res.users"]
        if (
            len(reviewer) != 1
            or not reviewer.active
            or not reviewer.has_group(QUALITY)
            or record.company_id not in reviewer.company_ids
        ):
            raise ValidationError(
                record.env._("Assign an active quality reviewer authorized for this operating company.")
            )
        previous = record.quality_id
        # Only the assignment changes: evidence authors, retention and closed
        # dossier state remain untouched. The caller has no general write bypass.
        record._write_continuity({"quality_id": reviewer.id})
        record._record_lifecycle("reassign", reason.strip(), previous)
        return True

    def action_rectify(self, reason=None, expected_closure_event_id=None):
        record = self.sudo(False)
        record.ensure_one()
        record._authorize(quality=True)
        if reason is None:
            return record._continuity_action("rectify")
        if not reason.strip():
            raise ValidationError(record.env._("Explain why this closed dossier needs rectification."))
        record._serialize()
        record._authorize(quality=True)
        if record.state == "open":
            return True
        latest_close = record.event_ids.filtered(lambda e: e.operation == "close")[:1].id
        if expected_closure_event_id is not None and latest_close != expected_closure_event_id:
            raise ValidationError(record.env._("The dossier was closed again. Reload it before rectifying."))
        record._record_lifecycle("rectify", reason.strip())
        # Keep the last closure metadata and all validated evidence/documents.
        # Existing S08 versioning and P20 replacement perform the correction.
        record._write_continuity({"state": "open"})
        return True

    @api.private
    def _write_continuity(self, values):
        # pylint: disable-next=super-method-mismatch  # narrow authorized action bypasses immutable public write
        return super(OriginalClosure, self).write(values)
