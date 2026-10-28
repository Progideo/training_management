"""An explicitly authorized summary, separate from all private action content."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PracticeSummary(models.Model):
    _name = "training.practice.summary"
    _description = "Authorized Practice Summary"
    _check_company_auto = True
    _rec_name = "authorization_id"

    authorization_id = fields.Many2one(
        "training.company.authorization", required=True, ondelete="restrict", check_company=True
    )
    allocation_id = fields.Many2one("training.seat.allocation", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="allocation_id.company_id", store=True)
    body = fields.Text(required=True, string="Agreed Summary")
    authorization_reference = fields.Char(required=True, string="Agreement and Authorization Reference")
    retention_id = fields.Many2one(
        "training.retention.category", required=True, ondelete="restrict", check_company=True
    )
    published_at = fields.Datetime(readonly=True, copy=False)
    published_by_id = fields.Many2one("res.users", readonly=True, copy=False, ondelete="restrict")
    withdrawn = fields.Boolean(readonly=True, copy=False)

    @api.constrains("authorization_id", "allocation_id", "retention_id")
    def _check_scope(self):
        for row in self:
            if row.allocation_id not in row.authorization_id.allocation_ids or not row.retention_id.approved_at:
                raise ValidationError(self.env._("Choose an authorized allocation and an approved retention policy."))

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.practice.action"]._coordinator()
        values = [self._add_missing_default_values(dict(v)) for v in vals_list]
        if any(
            set(v) - {"authorization_id", "allocation_id", "body", "authorization_reference", "retention_id"}
            for v in values
        ):
            raise ValidationError(self.env._("Publish the agreed summary using the authorized action."))
        return super().create(values)

    def write(self, vals):
        self.env["training.practice.action"]._coordinator()
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()
        if any(r.published_at for r in self) or set(vals) - {
            "authorization_id",
            "allocation_id",
            "body",
            "authorization_reference",
            "retention_id",
        }:
            raise ValidationError(self.env._("Keep published summaries unchanged; withdraw and replace them."))
        return super().write(vals)

    def action_publish(self):
        self.env["training.practice.action"]._coordinator()
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()
        self._check_scope()
        for row in self.filtered(lambda r: not r.published_at):
            if (
                row.withdrawn
                or row.authorization_id.state != "active"
                or not row.body.strip()
                or not row.authorization_reference.strip()
            ):
                raise ValidationError(self.env._("Record the agreed summary and its authorization before publication."))
            super(PracticeSummary, row).write({"published_at": fields.Datetime.now(), "published_by_id": self.env.uid})  # pylint: disable=super-method-mismatch
        return True

    def action_withdraw(self):
        self.env["training.practice.action"]._coordinator()
        self.check_access("write")
        self.lock_for_update()
        return super().write({"withdrawn": True})  # pylint: disable=super-method-mismatch  # authorized withdrawal

    @api.ondelete(at_uninstall=False)
    def _keep_summary(self):
        if any(r.published_at for r in self):
            raise ValidationError(self.env._("Keep published summaries and their authorization evidence."))

    @api.private
    def _client_rows(self, allocation):
        # Reuse current P05 authorization, never employer/contact membership.
        allocation = self.env["training.company.service"]._allocation(allocation.id)
        grants = self.env["training.company.service"]._grants()
        rows = self.sudo().search(
            [
                ("allocation_id", "=", allocation.id),
                ("authorization_id", "in", grants.ids),
                ("published_at", "!=", False),
                ("withdrawn", "=", False),
            ]
        )
        return [{"body": r.body, "date": r.published_at} for r in rows]
