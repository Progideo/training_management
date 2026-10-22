from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..models.training_schedule import local_instant


class TrainingSessionEdit(models.TransientModel):
    _name = "training.session.edit"
    _description = "Add or Change Training Sessions"
    _check_company_auto = True

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="delivery_id.company_id")
    session_id = fields.Many2one("training.session", ondelete="cascade")
    name = fields.Char(required=True, default=lambda self: self.env._("Training session"))
    instructor_id = fields.Many2one("res.partner", check_company=True)
    room_id = fields.Many2one("resource.resource", check_company=True)
    mode = fields.Selection(
        [("onsite", "On site"), ("remote", "Remote"), ("blended", "Blended")], required=True, default="onsite"
    )
    location = fields.Char()
    meeting_url = fields.Char()
    equipment = fields.Text()
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    start_hour = fields.Float(default=9, required=True)
    end_hour = fields.Float(default=17, required=True)
    start_occurrence = fields.Selection([("first", "First occurrence"), ("second", "Second occurrence")])
    end_occurrence = fields.Selection([("first", "First occurrence"), ("second", "Second occurrence")])
    repeat_count = fields.Integer(default=1, required=True)
    interval_days = fields.Integer(default=1, required=True)
    reason = fields.Text()
    conflict_description = fields.Text(readonly=True)
    conflict_reason = fields.Text(string="Reason for Resource Exception")
    cancel_session = fields.Boolean()
    propose_notice = fields.Boolean(default=True, string="Review Recipients after Saving")
    delivery_state = fields.Selection(related="delivery_id.state")
    reference_timezone = fields.Selection(related="delivery_id.timezone")
    start_ambiguous = fields.Boolean(compute="_compute_ambiguous")
    end_ambiguous = fields.Boolean(compute="_compute_ambiguous")

    @api.depends("start_date", "end_date", "start_hour", "end_hour", "reference_timezone")
    def _compute_ambiguous(self):
        for wizard in self:
            for prefix in ("start", "end"):
                ambiguous = False
                if wizard[prefix + "_date"] and wizard.reference_timezone:
                    try:
                        local_instant(wizard[prefix + "_date"], wizard[prefix + "_hour"], wizard.reference_timezone)
                    except ValueError as error:
                        ambiguous = "occurs twice" in str(error)
                wizard[prefix + "_ambiguous"] = ambiguous

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if values.get("session_id"):
            session = self.env["training.session"].browse(values["session_id"])
            session.check_access("read")
            for key in self._schedule_fields():
                if key in fields_list:
                    values[key] = session[key].id if session._fields[key].type == "many2one" else session[key]
        elif values.get("delivery_id"):
            delivery = self.env["training.delivery"].browse(values["delivery_id"])
            delivery.check_access("read")
            if delivery.start_at:
                day = fields.Datetime.context_timestamp(
                    delivery.with_context(tz=delivery.timezone), delivery.start_at
                ).date()
                values.setdefault("start_date", day)
                values.setdefault("end_date", day)
            if "default_mode" not in self.env.context:
                values["mode"] = (
                    delivery.delivery_mode if delivery.delivery_mode in ("onsite", "remote", "blended") else "onsite"
                )
        return values

    @api.model
    def _schedule_fields(self):
        return (
            "name",
            "instructor_id",
            "room_id",
            "mode",
            "location",
            "meeting_url",
            "equipment",
            "start_date",
            "end_date",
            "start_hour",
            "end_hour",
            "start_occurrence",
            "end_occurrence",
        )

    @api.onchange("start_date")
    def _onchange_start_date(self):
        self.end_date = self.start_date

    @api.onchange(
        "instructor_id",
        "room_id",
        "start_date",
        "end_date",
        "start_hour",
        "end_hour",
        "start_occurrence",
        "end_occurrence",
        "repeat_count",
        "interval_days",
        "cancel_session",
    )
    def _onchange_reservation(self):
        self.conflict_description = False
        self.conflict_reason = False

    def action_apply(self):
        self.ensure_one()
        self.delivery_id._require_coordinator()
        if not 1 <= self.repeat_count <= 100 or self.interval_days < 1:
            raise ValidationError(self.env._("Create between 1 and 100 sessions with a positive interval."))
        values = {
            key: self[key].id if self._fields[key].type == "many2one" else self[key] for key in self._schedule_fields()
        }
        try:
            # A refused batch leaves no partial session or audit entry behind.
            with self.env.cr.savepoint():
                if self.session_id:
                    if self.session_id.delivery_id != self.delivery_id or self.repeat_count != 1:
                        raise ValidationError(self.env._("Change only the selected session of this delivery."))
                    self.session_id._apply_schedule(values, self.reason, self.cancel_session, self.conflict_reason)
                else:
                    batch = []
                    for offset in range(self.repeat_count):
                        delta = timedelta(days=offset * self.interval_days)
                        batch.append(
                            {
                                **values,
                                "delivery_id": self.delivery_id.id,
                                "start_date": self.start_date + delta,
                                "end_date": self.end_date + delta,
                            }
                        )
                    self.env["training.session"]._create_scheduled(batch, self.reason, self.conflict_reason)
        except ValidationError as error:
            if not getattr(error, "training_resource_conflict", False):
                raise
            self.write({"conflict_description": str(error)})
            return {
                "type": "ir.actions.act_window",
                "name": self.env._("Resource Exception"),
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }
        if self.propose_notice and self.delivery_id.state == "confirmed":
            return self.delivery_id.action_prepare_invitations()
        return {"type": "ir.actions.act_window_close"}


class TrainingInvitationSend(models.TransientModel):
    _name = "training.invitation.send"
    _description = "Review and Send Training Invitations"

    delivery_id = fields.Many2one("training.delivery", required=True, ondelete="cascade")
    recipient_ids = fields.Many2many("res.partner", string="Recipients", required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if values.get("delivery_id"):
            delivery = self.env["training.delivery"].browse(values["delivery_id"])
            recipients = self.env["training.invitation"]._recipients(delivery)
            values["recipient_ids"] = [fields.Command.set(recipients.ids)]
        return values

    def action_send(self):
        self.ensure_one()
        self.env["training.invitation"]._queue(self.delivery_id, self.recipient_ids)
        return {"type": "ir.actions.act_window_close"}
