"""Private session facts for P16 decisions; no public or commercial grant."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SessionPublicationService(models.AbstractModel):
    _name = "training.session.publication.service"
    _description = "Session Publication Preparation"

    @api.private
    def _session_facts(self, delivery):
        user = self.env.user
        if not user.active or user._is_public() or not user.has_group("training_management.group_training_coordinator"):
            raise AccessError(self.env._("Only a training coordinator may inspect session availability."))
        delivery.ensure_one()
        # Rebind even a sudo record from a caller to the real actor's environment.
        delivery = delivery.with_env(self.env(su=False))
        delivery.check_access("read")
        if delivery.company_id not in self.env.companies:
            raise AccessError(self.env._("This delivery is outside the allowed companies."))
        now = fields.Datetime.now()
        occupied = delivery._occupancy(now)
        return {
            "checked_at": now,
            "kind": delivery.kind,
            "state": delivery.state,
            "program_state": delivery.program_id.state,
            "catalogue_approved": delivery.program_id.public_catalogue,
            "course_active": delivery.program_id.course_id.active,
            "start_at": delivery.start_at,
            "end_at": delivery.end_at,
            "timezone": delivery.timezone,
            "capacity": delivery.capacity,
            "occupied_seats": occupied,
            "remaining_seats": max(0, delivery.capacity - occupied) if delivery.capacity else None,
        }


class SessionPublicationDelivery(models.Model):
    _inherit = "training.delivery"  # pylint: disable=consider-merging-classes-inherited  # P16 private diagnostic

    def action_inspect_session_availability(self):
        self.ensure_one()
        self.env["training.session.publication.service"]._session_facts(self)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Session State and Availability"),
            "res_model": "training.session.publication.inspection",
            "view_mode": "form",
            "target": "new",
            "context": {"default_delivery_id": self.id},
        }


PUBLIC_FIELDS = {"session_public", "session_sales_open", "session_first_published_at", "session_guaranteed"}


class PublicSessionDelivery(models.Model):
    _inherit = "training.delivery"  # pylint: disable=consider-merging-classes-inherited  # public decisions separate from diagnostic

    session_alert_notice_ids = fields.One2many(
        "training.session.alert.notice",
        "delivery_id",
        readonly=True,
        groups="training_management.group_training_coordinator",
    )
    session_public = fields.Boolean(readonly=True, copy=False)
    session_sales_open = fields.Boolean(readonly=True, copy=False)
    session_first_published_at = fields.Datetime(readonly=True, copy=False)
    session_guaranteed = fields.Boolean(string="Guaranteed Departure", readonly=True, copy=False)

    _reason_actions = (
        "action_confirm",
        "action_cancel",
        "action_close",
        "action_publish_session",
        "action_withdraw_session",
        "action_guarantee_session",
        "action_revoke_session_guarantee",
        "action_close_session_sales",
    )

    @api.private
    def _reason_labels(self):
        return {
            **super()._reason_labels(),
            "action_publish_session": self.env._("Publish and Open Session"),
            "action_withdraw_session": self.env._("Withdraw Public Session"),
            "action_guarantee_session": self.env._("Guarantee Departure"),
            "action_revoke_session_guarantee": self.env._("Revoke Departure Guarantee"),
            "action_close_session_sales": self.env._("Close Session Sales"),
        }

    @api.model_create_multi
    def create(self, vals_list):
        if any(PUBLIC_FIELDS & values.keys() for values in vals_list) or any(
            "default_" + key in self.env.context for key in PUBLIC_FIELDS
        ):
            raise ValidationError(self.env._("Use the explicit public session actions."))
        return super().create(vals_list)

    def write(self, vals):
        if PUBLIC_FIELDS & vals.keys():
            raise ValidationError(self.env._("Use the explicit public session actions."))
        with self.env.cr.savepoint():
            # Keep the company -> delivery lock order shared with consent and transport.
            if {"company_id", "program_id", "kind", "start_at", "end_at"} & vals.keys():
                self._require_coordinator()
                self.company_id.sudo()._lock_training_schedule()
                self._serialize()
                self._reset_session_publication()
            return super().write(vals)

    @api.private
    def _reset_session_publication(self):
        for row in self.filtered(lambda d: d.session_public or d.session_guaranteed or d.session_sales_open):
            row._store(
                {"session_public": False, "session_sales_open": False, "session_guaranteed": False},
                self.env._("Session definition changed; review public decisions."),
            )

    @api.private
    def _session_can_publish(self):
        self.ensure_one()
        program = self.program_id
        return bool(
            self.kind == "session"
            and self.start_at > fields.Datetime.now()
            and self.state in ("preparation", "confirmed")
            and program.state == "published"
            and program.public_catalogue
            and program.course_id.active
            and program.company_id == self.company_id
        )

    @api.private
    def _session_public_row(self):
        self.ensure_one()
        if not self.session_public or not self.session_sales_open or not self._session_can_publish():
            return False
        full = bool(self.capacity and self._occupancy() >= self.capacity)
        return {
            "start_at": self.start_at,
            "end_at": self.end_at,
            "timezone": self.timezone,
            "status": "full" if full else "confirmed" if self.state == "confirmed" else "open",
            "guaranteed": self.session_guaranteed,
        }

    @api.private
    def _session_decide(self, decision, reason):
        self._require_coordinator()
        with self.env.cr.savepoint():
            self.company_id.sudo()._lock_training_schedule()
            self._serialize()
            reason = self._require_reason(reason)
            for row in self:
                if decision in ("publish", "guarantee") and not row._session_can_publish():
                    raise ValidationError(self.env._("Choose a future dated session and a currently public programme."))
                values = {}
                if decision == "publish":
                    values = {"session_public": True, "session_sales_open": True}
                    if not row.session_first_published_at:
                        values["session_first_published_at"] = fields.Datetime.now()
                elif decision == "withdraw":
                    values = {"session_public": False, "session_sales_open": False, "session_guaranteed": False}
                elif decision == "close":
                    values = {"session_sales_open": False}
                else:
                    values = {"session_guaranteed": decision == "guarantee"}
                changes = {key: value for key, value in values.items() if row[key] != value}
                first = "session_first_published_at" in changes
                if changes:
                    row._store(changes, reason)
                if first:
                    self.env["training.session.alert.notice"]._queue_session(row)
        return True

    def action_publish_session(self, reason=None):
        return self._session_decide("publish", reason)

    def action_withdraw_session(self, reason=None):
        return self._session_decide("withdraw", reason)

    def action_close_session_sales(self, reason=None):
        return self._session_decide("close", reason)

    def action_guarantee_session(self, reason=None):
        return self._session_decide("guarantee", reason)

    def action_revoke_session_guarantee(self, reason=None):
        return self._session_decide("revoke", reason)

    def action_change_dates(self, start_at=None, end_at=None, access_start=None, access_end=None, reason=None):
        with self.env.cr.savepoint():
            self._require_coordinator()
            self.company_id.sudo()._lock_training_schedule()
            self._serialize()
            before = (self.start_at, self.end_at)
            result = super().action_change_dates(
                start_at=start_at, end_at=end_at, access_start=access_start, access_end=access_end, reason=reason
            )
            if before != (self.start_at, self.end_at):
                self._reset_session_publication()
            return result
