"""ORG01: preparation on the existing delivery/enrollment, private adaptations."""

import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .training_schedule import COORDINATOR


class TrainingDelivery(models.Model):
    _inherit = "training.delivery"  # pylint: disable=consider-merging-classes-inherited  # Keep preparation separate from learning.

    sponsor_need = fields.Text(string="Sponsor Needs")
    can_prepare = fields.Boolean(compute="_compute_can_prepare")
    adaptation_referent_id = fields.Many2one(
        "res.users",
        string="Confidentiality Referent",
        ondelete="restrict",
        groups=COORDINATOR,
        default=lambda self: self.env.user if self.env.user.has_group(COORDINATOR) else False,
    )
    adaptation_deputy_id = fields.Many2one(
        "res.users", string="Confidentiality Deputy", ondelete="restrict", groups=COORDINATOR
    )
    session_ids = fields.One2many("training.session", "delivery_id", groups=COORDINATOR)
    adaptation_ids = fields.One2many("training.adaptation", "delivery_id", groups=COORDINATOR)
    invitation_ids = fields.One2many("training.invitation", "delivery_id", groups=COORDINATOR)

    @api.depends_context("uid")
    def _compute_can_prepare(self):
        for delivery in self:
            delivery.can_prepare = self.env.user.has_group(COORDINATOR)

    @api.constrains("adaptation_referent_id", "adaptation_deputy_id", "company_id")
    def _check_referents(self):
        for delivery in self:
            for user in delivery.adaptation_referent_id | delivery.adaptation_deputy_id:
                if not user.has_group(COORDINATOR) or delivery.company_id not in user.company_ids or not user.active:
                    raise ValidationError(
                        self.env._("The referent and deputy must be active coordinators of this company.")
                    )

    @api.private
    def _require_adaptation_access(self):
        self._require_coordinator()
        if not self.env.su and any(
            self.env.user not in item.adaptation_referent_id | item.adaptation_deputy_id for item in self
        ):
            raise AccessError(self.env._("Only the named referent or deputy may access confidential adaptations."))

    @api.private
    def _check_capacity(self):
        super()._check_capacity()
        self.session_ids._check_room()
        return True

    @api.private
    def _transition(self, target, reason=None, conflict_reason=None):
        self._require_coordinator()
        if target == "confirmed":
            self.company_id._lock_training_schedule()
            self._serialize()
            for delivery in self:
                if delivery.state == target:
                    continue
                if delivery.kind == "session":
                    sessions = delivery.session_ids.filtered(lambda item: not item.cancelled)
                    if not sessions:
                        raise ValidationError(self.env._("Add the sessions before confirming this dated delivery."))
                    sessions._reserve(conflict_reason)
                # Transition each delivery immediately: a later member of the
                # same batch must see the resources reserved by an earlier one.
                super(TrainingDelivery, delivery)._transition(target, reason)
            return True
        return super()._transition(target, reason)

    def action_confirm(self, reason=None, conflict_reason=None):
        return self._transition("confirmed", reason, conflict_reason)

    def write(self, vals):
        if self.session_ids and any(
            key in vals
            and any(
                item[key].id != vals[key] if item._fields[key].type == "many2one" else item[key] != vals[key]
                for item in self
            )
            for key in ("company_id", "program_id", "kind")
        ):
            raise ValidationError(self.env._("A delivery with sessions keeps its company, programme and kind."))
        if set(vals) & {"adaptation_referent_id", "adaptation_deputy_id"}:
            self._require_coordinator()
            # A coordinator cannot grant themselves access to an existing
            # confidential dossier. Its current referent/deputy manages it.
            protected = self.filtered(
                lambda delivery: (
                    self.env["training.adaptation"].sudo().search_count([("delivery_id", "=", delivery.id)])
                )
            )
            protected._require_adaptation_access()
        if "timezone" in vals and self.session_ids and any(item.timezone != vals["timezone"] for item in self):
            raise ValidationError(self.env._("The reference timezone is preserved once sessions exist."))
        result = super().write(vals)
        if set(vals) & {"start_at", "end_at", "kind", "company_id"}:
            self.session_ids.filtered(lambda item: not item.cancelled)._check_definition()
        return result

    def action_change_dates(self, start_at=None, end_at=None, access_start=None, access_end=None, reason=None):
        result = super().action_change_dates(start_at, end_at, access_start, access_end, reason)
        self.session_ids.filtered(lambda item: not item.cancelled)._check_definition()
        return result

    def action_add_sessions(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Add Sessions"),
            "res_model": "training.session.edit",
            "view_mode": "form",
            "target": "new",
            "context": {"default_delivery_id": self.id},
        }

    def action_prepare_invitations(self):
        self.ensure_one()
        self._require_coordinator()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Send Invitations"),
            "res_model": "training.invitation.send",
            "view_mode": "form",
            "target": "new",
            "context": {"default_delivery_id": self.id},
        }


class TrainingEnrollment(models.Model):
    _inherit = "training.enrollment"  # pylint: disable=consider-merging-classes-inherited  # Keep positioning separate from learning.

    participant_objectives = fields.Text(groups=COORDINATOR)
    positioning = fields.Text(groups=COORDINATOR)
    instructor_summary = fields.Text(string="Positioning Summary for Instructor", groups=COORDINATOR)

    @api.model_create_multi
    def create(self, vals_list):
        keys = {"participant_objectives", "positioning", "instructor_summary"}
        records = super().create([{key: value for key, value in vals.items() if key not in keys} for vals in vals_list])
        for record, vals in zip(records, vals_list):
            content = {key: vals[key] for key in keys if key in vals}
            if content:
                record.write(content)
        return records

    def write(self, vals):
        keys = {"participant_objectives", "positioning", "instructor_summary"}
        content = {key: value for key, value in vals.items() if key in keys}
        other = {key: value for key, value in vals.items() if key not in keys}
        if content:
            self._require_coordinator()
            self.delivery_id._serialize()
            for record in self:
                record._store(content)
        return super().write(other) if other else True


class TrainingAdaptation(models.Model):
    _name = "training.adaptation"
    _description = "Confidential Training Adaptation"
    _rec_name = "enrollment_id"
    _check_company_auto = True

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="delivery_id.company_id", store=True)
    enrollment_id = fields.Many2one("training.enrollment", required=True, ondelete="restrict", check_company=True)
    details = fields.Text(string="Confidential Request")
    decision = fields.Text(required=True)
    instructor_instruction = fields.Text(string="Instruction for Assigned Instructor")
    history_ids = fields.One2many("training.adaptation.history", "adaptation_id", readonly=True)

    _unique_enrollment = models.Constraint(
        "UNIQUE(enrollment_id)", "Use the existing adaptation dossier for this enrollment."
    )

    @api.private
    def _authorize(self):
        self.check_access("write" if self else "create")
        self.delivery_id._require_adaptation_access()

    @api.constrains("enrollment_id", "delivery_id", "decision")
    def _check_definition(self):
        for item in self:
            if item.enrollment_id.delivery_id != item.delivery_id or not (item.decision or "").strip():
                raise ValidationError(
                    self.env._("Choose an enrollment of this delivery and record the adaptation decision.")
                )

    @api.private
    def _snapshot(self):
        self.ensure_one()
        return json.dumps(
            {key: self[key] for key in ("details", "decision", "instructor_instruction")}, ensure_ascii=False
        )

    @api.private
    def _audit(self, before, event="change"):
        self.ensure_one()
        self._authorize()
        # Narrow elevation: append only, after dossier-level authorization. No
        # sensitive values are copied to training.operation or mail.thread.
        self.env["training.adaptation.history"].sudo()._append(
            {
                "adaptation_id": self.id,
                "actor_id": self.env.uid,
                "occurred_at": fields.Datetime.now(),
                "before": before,
                "after": self._snapshot() if event == "change" else False,
                "event": event,
            }
        )

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access("create")
        deliveries = self.env["training.delivery"].browse([values["delivery_id"] for values in vals_list])
        deliveries._require_adaptation_access()
        deliveries._serialize()
        if any(
            set(values) - {"delivery_id", "enrollment_id", "details", "decision", "instructor_instruction"}
            for values in vals_list
        ):
            raise AccessError(self.env._("Only adaptation content can be supplied."))
        clean_context = {key: value for key, value in self.env.context.items() if not key.startswith("default_")}
        records = super(TrainingAdaptation, self.with_context(clean_context)).create(vals_list)  # pylint: disable=context-overridden  # deliberately discard untrusted defaults
        for record in records:
            record._audit(False)
        return records

    def write(self, vals):
        self._authorize()
        if set(vals) - {"details", "decision", "instructor_instruction"}:
            raise AccessError(self.env._("An adaptation keeps its enrollment and protected history."))
        self.delivery_id._serialize()
        self.lock_for_update()
        self.invalidate_recordset()
        snapshots = {item.id: item._snapshot() for item in self}
        result = super().write(vals)
        for item in self:
            if item._snapshot() != snapshots[item.id]:
                item._audit(snapshots[item.id])
        return result

    def unlink(self):  # pylint: disable=method-required-super  # immutable history: cancellation replaces deletion
        raise AccessError(self.env._("Adaptation history must be preserved."))  # pylint: disable=no-raise-unlink  # preserve audit

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        # Native recursive exports call _export_rows, not export_data on the
        # related model. Authorize and audit here to cover every entry point.
        self._authorize()
        result = super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
        for item in self:
            item._audit(json.dumps({"model": self._name, "fields": fields, "records": self.ids}), "export")
        return result


class TrainingAdaptationHistory(models.Model):
    _name = "training.adaptation.history"
    _description = "Confidential Adaptation History"
    _order = "id desc"

    adaptation_id = fields.Many2one("training.adaptation", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="adaptation_id.company_id", store=True)
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    occurred_at = fields.Datetime(required=True)
    event = fields.Selection([("change", "Change"), ("export", "Export")], required=True)
    before = fields.Text()
    after = fields.Text()

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        self.check_access("read")
        self.adaptation_id._authorize()
        result = super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
        for dossier in self.adaptation_id:
            dossier._audit(json.dumps({"model": self._name, "fields": fields, "records": self.ids}), "export")
        return result

    @api.private
    def _append(self, vals):
        return super().create(vals)  # pylint: disable=super-method-mismatch  # private append-only history

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # server-authored immutable records
        raise AccessError(self.env._("History is generated by the server."))

    def write(self, vals):  # pylint: disable=method-required-super  # immutable records
        raise AccessError(self.env._("History is immutable."))  # pylint: disable=no-raise-unlink  # preserve audit

    def unlink(self):  # pylint: disable=method-required-super  # immutable history: cancellation replaces deletion
        raise AccessError(self.env._("History is immutable."))  # pylint: disable=no-raise-unlink  # preserve audit
