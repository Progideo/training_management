from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TrainingSeatAllocation(models.Model):
    _inherit = "training.seat.allocation"

    sale_line_id = fields.Many2one(
        "sale.order.line", string="Commercial Line", ondelete="restrict", check_company=True, index=True
    )

    @api.private
    def _check_source(self):
        self.ensure_one()
        self._check_sale_limit(require_confirmed=True)

    @api.private
    def _check_sale_limit(self, require_confirmed=False):
        self.ensure_one()
        line = self.sale_line_id
        if not line:
            if require_confirmed:
                return super()._check_source()
            return
        # Coordination does not imply Sales access: native read rights on the
        # source order/line are required, with roles explicitly combined.
        line.check_access("read")
        order = line.order_id
        order.check_access("read")
        order.lock_for_update()
        order.invalidate_recordset()
        super(SaleOrder, order).write({"training_allocation_revision": order.training_allocation_revision + 1})
        line.lock_for_update()
        line.invalidate_recordset()
        # This column is a concurrency fence only, including stale snapshots.
        super(SaleOrderLine, line).write({"training_allocation_revision": line.training_allocation_revision + 1})
        if (
            order.company_id != self.company_id
            or line.training_program_id != self.delivery_id.program_id
            or order.partner_id != self.customer_id
            or not order.training_request_kind
            or order.state == "cancel"
            or (require_confirmed and order.state != "sale")
        ):
            raise ValidationError(
                _(
                    "The allocation must match a readable commercial line, customer, company and programme; commitment requires a confirmed order."
                )
            )
        lots = self.search([("sale_line_id.order_id", "=", order.id)])
        committed = sum(lot.quantity for lot in lots if lot._available())
        # S02 fixes the explicit contractual participant count on the order.
        # A later catalogue price-basis change must not rewrite this entitlement.
        limit = order.training_attendee_count
        if committed > limit:
            raise ValidationError(_("Allocated places exceed the commercial line's participant entitlement."))

    @api.model_create_multi
    def create(self, vals_list):
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            for record in records.sorted(lambda item: item.sale_line_id.id):
                record._check_sale_limit()
            return records


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    training_allocation_revision = fields.Integer(readonly=True, default=0, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any("training_allocation_revision" in values for values in vals_list):
            raise ValidationError(_("The allocation revision is server-managed."))
        return super().create([{**values, "training_allocation_revision": 0} for values in vals_list])

    def write(self, vals):
        if "training_allocation_revision" in vals:
            raise ValidationError(_("The allocation revision is server-managed."))
        if set(vals) & {"order_id", "product_id", "product_uom_qty", "training_program_id", "product_uom_id"}:
            self.check_access("write")
            # Narrow elevated existence check: protect linked history without
            # exposing enrollment data or granting Sales a coordinator role.
            lots = self.env["training.seat.allocation"].sudo().search([("sale_line_id", "in", self.ids)])
            # Only live lots, or lots still carrying an open enrollment, bind the line.
            if any(lot._holds_source() for lot in lots):
                raise ValidationError(
                    _(
                        "Commercial lines with allocated training places are fixed. Use a controlled commercial revision."
                    )
                )
        return super().write(vals)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    training_allocation_revision = fields.Integer(readonly=True, default=0, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any("training_allocation_revision" in values for values in vals_list):
            raise ValidationError(_("The allocation revision is server-managed."))
        return super().create([{**values, "training_allocation_revision": 0} for values in vals_list])

    def write(self, vals):
        if "training_allocation_revision" in vals:
            raise ValidationError(_("The allocation revision is server-managed."))
        protected = {
            "training_attendee_count",
            "partner_id",
            "company_id",
            "training_request_kind",
            "training_requested_program_id",
        }
        if set(vals) & protected or vals.get("state") == "cancel":
            self.check_access("write")
            lots = self.env["training.seat.allocation"].sudo().search([("sale_line_id.order_id", "in", self.ids)])
            # A cancelled or expired lot without an open enrollment no longer binds the order.
            bound = lots.filtered(lambda lot: lot._holds_source())
            if bound and set(vals) & protected:
                raise ValidationError(
                    _("Orders with training allocations keep their customer, programme and participant entitlement.")
                )
            if bound and vals.get("state") == "cancel":
                raise ValidationError(
                    _("Cancel the training allocations explicitly before cancelling the commercial order.")
                )
        return super().write(vals)
