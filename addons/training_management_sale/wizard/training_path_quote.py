"""One native assistant prepares a full or selected path on a draft quotation."""

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


def _check_order_access(model, values):
    """Check before related fields can compute with elevated read rights."""
    order_id = values.get("order_id", model.env.context.get("default_order_id"))
    model.env["sale.order"].browse(order_id).check_access("read")


class TrainingPathQuote(models.TransientModel):
    _name = "training.path.quote"
    _description = "Prepare Path Quotation"
    _check_company_auto = True

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", compute_sudo=False)
    currency_id = fields.Many2one(related="order_id.currency_id", compute_sudo=False)
    path_id = fields.Many2one(
        "training.path", required=True, check_company=True, domain="[('state', '=', 'validated')]"
    )
    request_kind = fields.Selection([("individual", "Individual"), ("group", "Group")], required=True, default="group")
    attendee_count = fields.Integer(required=True, default=1)
    price_basis = fields.Selection([("person", "Per person"), ("package", "Package")], required=True, default="package")
    line_ids = fields.One2many("training.path.quote.line", "wizard_id")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _check_order_access(self, vals)
        return super().create(vals_list)

    def write(self, vals):
        if "order_id" in vals:
            _check_order_access(self, vals)
        return super().write(vals)

    @api.model
    def default_get(self, names):
        values = super().default_get(names)
        order = self.env["sale.order"].browse(values.get("order_id"))
        if order:
            order.check_access("read")
            values.update(
                request_kind=order.training_request_kind or "group", attendee_count=order.training_attendee_count or 1
            )
        return values

    @api.onchange("path_id", "price_basis")
    def _onchange_courses(self):
        commands = [Command.clear()]
        for step in self.path_id.step_ids:
            products = self.env["product.product"].search(
                [
                    ("training_course_id", "=", step.course_id.id),
                    ("training_price_basis", "=", self.price_basis),
                    ("company_id", "=", self.company_id.id),
                    ("type", "=", "service"),
                    ("sale_ok", "=", True),
                ],
                limit=2,
            )
            commands.append(
                Command.create(
                    {"step_id": step.id, "product_id": products.id if len(products) == 1 else False, "selected": True}
                )
            )
        self.line_ids = commands

    def action_apply(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            order = self.order_id
            order.check_access("write")
            order.lock_for_update()
            order.invalidate_recordset()
            if order.state != "draft" or order.order_line.filtered("training_program_id"):
                raise ValidationError(self.env._("Prepare the path on a draft quotation without training lines."))
            if self.path_id.state != "validated" or self.path_id.company_id != order.company_id:
                raise ValidationError(self.env._("Choose a validated path from this operating company."))
            selected = self.line_ids.filtered("selected")
            if (
                not selected
                or len(selected.step_id) != len(selected)
                or any(line.step_id.path_id != self.path_id for line in selected)
            ):
                raise ValidationError(self.env._("Select distinct courses belonging to the chosen path."))
            if self.attendee_count <= 0 or (self.request_kind == "individual" and self.attendee_count != 1):
                raise ValidationError(self.env._("Set a positive group size or one individual beneficiary."))
            for line in selected:
                product = line.product_id
                if (
                    not product
                    or product.company_id != order.company_id
                    or product.training_course_id != line.step_id.course_id
                    or product.training_price_basis != self.price_basis
                    or product.type != "service"
                    or not product.sale_ok
                ):
                    raise ValidationError(
                        self.env._(
                            "Choose an existing service product with the course and price basis required by each selected line."
                        )
                    )
                if line.price_unit < 0:
                    raise ValidationError(self.env._("Enter non-negative amounts in the quotation currency."))
            order.write(
                {
                    "training_path_id": self.path_id.id,
                    "training_path_scope": "complete"
                    if set(selected.step_id.ids) == set(self.path_id.step_ids.ids)
                    else "selection",
                    "training_price_source": "quote",
                    "training_requested_program_id": False,
                    "training_request_kind": self.request_kind,
                    "training_attendee_count": self.attendee_count,
                    "training_requested_currency_id": order.currency_id.id,
                }
            )
            values = [
                {
                    "order_id": order.id,
                    "display_type": "line_section",
                    "name": self.env._("Training Path: %s", self.path_id.name),
                }
            ]
            values += [
                {
                    "order_id": order.id,
                    "product_id": line.product_id.id,
                    "training_program_id": line.step_id.program_id.id,
                    "training_path_step_id": line.step_id.id,
                    "product_uom_qty": self.attendee_count if self.price_basis == "person" else 1,
                    "price_unit": line.price_unit,
                    "sequence": index + 11,
                }
                for index, line in enumerate(selected.sorted(lambda item: item.step_id.sequence))
            ]
            self.env["sale.order.line"].create(values)
            order._check_training_offer()
        return {"type": "ir.actions.act_window_close"}


class TrainingPathQuoteLine(models.TransientModel):
    _name = "training.path.quote.line"
    _description = "Selected Path Quotation Course"
    _check_company_auto = True

    wizard_id = fields.Many2one("training.path.quote", required=True, ondelete="cascade")
    step_id = fields.Many2one("training.path.step", required=True, check_company=True)
    course_id = fields.Many2one(related="step_id.course_id", compute_sudo=False)
    company_id = fields.Many2one(related="wizard_id.company_id", compute_sudo=False)
    price_basis = fields.Selection(related="wizard_id.price_basis", compute_sudo=False)
    selected = fields.Boolean(default=True)
    product_id = fields.Many2one(
        "product.product",
        check_company=True,
        domain="[('training_course_id', '=', course_id), ('training_price_basis', '=', price_basis), ('company_id', '=', company_id)]",
    )
    currency_id = fields.Many2one(related="wizard_id.currency_id", compute_sudo=False)
    price_unit = fields.Monetary()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.env["training.path.quote"].browse(
                vals.get("wizard_id", self.env.context.get("default_wizard_id"))
            ).check_access("write")
            self.env["training.path.step"].browse(
                vals.get("step_id", self.env.context.get("default_step_id"))
            ).check_access("read")
        return super().create(vals_list)

    def write(self, vals):
        self.wizard_id.check_access("write")
        if "wizard_id" in vals:
            self.env["training.path.quote"].browse(vals["wizard_id"]).check_access("write")
        if "step_id" in vals:
            self.env["training.path.step"].browse(vals["step_id"]).check_access("read")
        return super().write(vals)


class TrainingPathReuse(models.TransientModel):
    _name = "training.path.reuse"
    _description = "Reuse Prior Path Learning"
    _check_company_auto = True

    order_id = fields.Many2one("sale.order", required=True)
    company_id = fields.Many2one(related="order_id.company_id", compute_sudo=False)
    path_id = fields.Many2one(related="order_id.training_path_id", compute_sudo=False)
    step_id = fields.Many2one(
        "training.path.step", required=True, check_company=True, domain="[('path_id', '=', path_id)]"
    )
    enrollment_id = fields.Many2one("training.enrollment", required=True, check_company=True)
    equivalence_reason = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _check_order_access(self, vals)
        return super().create(vals_list)

    def write(self, vals):
        if "order_id" in vals:
            _check_order_access(self, vals)
        return super().write(vals)

    def action_apply(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            self.env["training.path.sale.usage"]._require_coordinator()
            self.order_id.check_access("read")
            self.enrollment_id._require_coordinator()
            self.enrollment_id.delivery_id._serialize()
            self.order_id._path_contract_lock()
            if (
                self.order_id.state != "sale"
                or self.step_id.path_id != self.order_id.training_path_id
                or not self.order_id.order_line.filtered(lambda line: line.training_path_step_id == self.step_id)
            ):
                raise ValidationError(self.env._("The acquired course must be included in the commercial offer."))
            reference = self.env["training.path.assignment"].search(
                [
                    ("step_id", "=", self.step_id.id),
                    ("participant_id", "=", self.enrollment_id.participant_id.id),
                    ("withdrawn_at", "=", False),
                ]
            )
            if reference and reference.enrollment_id != self.enrollment_id:
                raise ValidationError(self.env._("Choose the enrollment already referenced by this path step."))
            if not reference:
                reference = self.env["training.path.assignment"].create(
                    {
                        "step_id": self.step_id.id,
                        "enrollment_id": self.enrollment_id.id,
                        "equivalence_reason": self.equivalence_reason,
                    }
                )
            if not reference._is_completed():
                raise ValidationError(
                    self.env._("Only completed prior learning can replace a new contracted enrollment.")
                )
            if not self.env["training.path.sale.usage"].search_count(
                [("order_id", "=", self.order_id.id), ("reference_id", "=", reference.id), ("withdrawn_at", "=", False)]
            ):
                self.env["training.path.sale.usage"].create(
                    {"order_id": self.order_id.id, "reference_id": reference.id}
                )
        return {"type": "ir.actions.act_window_close"}
