"""Online registration to a priced inter-company session (decision of 21 November 2026).

A logged-in visitor registers to a published session that has a public inter-company price.
The places are reserved on a native quotation without any quotation step for the visitor:

- the session is confirmed: the visitor pays at once on the native portal page of the order;
- the session is not confirmed yet: the registration is recorded without payment and the
  visitor is asked to wait; confirming the session sends each unpaid registration a request
  to pay and confirm the participation.

An unpaid reservation keeps its places until seven days before the session starts. Paying
confirms the places; pedagogical access keeps its explicit decisions (S03).
"""

from datetime import timedelta

from odoo import SUPERUSER_ID, Command, api, fields, models
from odoo.exceptions import ValidationError

# Unpaid places are released this long before the session starts.
RELEASE_DELAY = timedelta(days=7)


class TrainingDelivery(models.Model):
    _inherit = "training.delivery"

    @api.private
    def _public_session_product(self):
        """The public inter-company price of the session's course, if any."""
        self.ensure_one()
        return (
            self.env["product.product"]
            .sudo()
            .search(
                [
                    ("product_tmpl_id.training_course_id", "=", self.program_id.course_id.id),
                    ("product_tmpl_id.training_public_session_price", "=", True),
                    ("product_tmpl_id.training_price_basis", "=", "person"),
                    ("sale_ok", "=", True),
                    ("company_id", "in", (self.company_id.id, False)),
                ],
                limit=1,
            )
        )

    @api.private
    def _registration_release_at(self):
        """Last moment an unpaid registration keeps its places."""
        self.ensure_one()
        release = self.start_at - RELEASE_DELAY
        # A late registration to a confirmed session is paid at once: its places last until the start.
        return release if release > fields.Datetime.now() else self.start_at

    def action_confirm(self, reason=None, conflict_reason=None):
        result = super().action_confirm(reason=reason, conflict_reason=conflict_reason)
        # Elevated search: a coordinator may lack Sales rights. Only the named buyer of each
        # registration receives its request, through the document policy of the order.
        orders = (
            self.env["sale.order"]
            .sudo()
            .search([("training_registration_delivery_id", "in", self.ids), ("state", "=", "draft")])
        )
        orders._training_request_payment()
        return result


class SaleOrder(models.Model):
    _inherit = "sale.order"  # pylint: disable=consider-merging-classes-inherited  # registration payment stays separate from S02 quotations

    training_registration_delivery_id = fields.Many2one(
        "training.delivery",
        string="Registered Session",
        readonly=True,
        copy=False,
        index=True,
        check_company=True,
        ondelete="restrict",
        help="Inter-company session registered online; its payment is open only once the session is confirmed.",
    )
    training_payment_requested_at = fields.Datetime(string="Payment Requested On", readonly=True, copy=False)
    training_registration_release_at = fields.Datetime(
        string="Places Held Until", compute="_compute_training_registration_release_at"
    )

    def _compute_training_registration_release_at(self):
        for order in self:
            lots = order._training_registration_lots() if order.training_registration_delivery_id else False
            order.training_registration_release_at = min(lots.mapped("expires_at")) if lots else False

    @api.private
    def _training_registration_lots(self):
        return self.env["training.seat.allocation"].sudo().search([("sale_line_id.order_id", "in", self.ids)])

    @api.private
    def _training_registration_payable(self):
        """A registration is paid only for a confirmed, future session whose places are still held."""
        self.ensure_one()
        delivery = self.training_registration_delivery_id.sudo()
        lots = self._training_registration_lots()
        return bool(
            delivery.state == "confirmed"
            and delivery.start_at > fields.Datetime.now()
            and lots
            and all(lot._available() for lot in lots)
        )

    def _has_to_be_paid(self):
        if self.training_registration_delivery_id and not self._training_registration_payable():
            return False
        return super()._has_to_be_paid()

    @api.private
    def _submit_public_session_registration(self, delivery, partner, count, key):
        """Reserve places for a logged-in buyer and prepare the order to pay; idempotent per submission."""
        company = delivery.company_id
        env = (
            self.with_user(SUPERUSER_ID)
            .sudo()
            .with_company(company)
            .with_context(mail_create_nosubscribe=True, lang=partner.lang or self.env.lang)
            .env
        )
        reference = "WEB-%s" % key
        # Native schedule and allocation changes update the delivery row: serialize the decision.
        delivery.lock_for_update()
        lots = env["training.seat.allocation"]
        existing = lots.search([("delivery_id", "=", delivery.id), ("source_reference", "=", reference)])
        if existing:
            return existing.sale_line_id.order_id
        held = lots.search(
            [
                ("delivery_id", "=", delivery.id),
                ("customer_id", "=", partner.id),
                ("sale_line_id.order_id.training_registration_delivery_id", "=", delivery.id),
            ]
        )
        if any(lot._available() for lot in held):
            raise ValidationError(
                self.env._("You are already registered to this session. Your registration is in your account.")
            )
        limit = delivery._public_registration_limit() if delivery._session_public_row() else 0
        if count not in range(1, limit + 1):
            raise ValidationError(self.env._("Choose a participant count within the current availability."))
        confirmed = delivery.state == "confirmed"
        if not confirmed and delivery.start_at - RELEASE_DELAY <= fields.Datetime.now():
            raise ValidationError(
                self.env._("This session is not confirmed and opens no more registrations online. Contact us.")
            )
        product = delivery._public_session_product()
        if not product:
            raise ValidationError(self.env._("This session has no public price."))
        release = delivery._registration_release_at()
        order = env["sale.order"].create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "user_id": False,
                "team_id": False,
                "training_request_kind": "group" if count > 1 else "individual",
                "training_requested_program_id": delivery.program_id.id,
                "training_attendee_count": count,
                "training_registration_delivery_id": delivery.id,
                "training_portal_partner_ids": [Command.set(partner.ids)],
                "require_signature": False,
                "prepayment_percent": 1.0,
                "validity_date": fields.Date.to_date(release),
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": count,
                            "training_program_id": delivery.program_id.id,
                        }
                    )
                ],
            }
        )
        env["training.seat.allocation"].create(
            {
                "delivery_id": delivery.id,
                "customer_id": partner.id,
                "sale_line_id": order.order_line.id,
                "quantity": count,
                "source_reference": reference,
                "expires_at": release,
            }
        )
        if confirmed:
            order.action_quotation_sent()
            order.training_payment_requested_at = fields.Datetime.now()
        else:
            order._training_send_registration_mail(
                "training_management_sale.mail_template_session_registration_waiting"
            )
        return order

    @api.private
    def _training_request_payment(self):
        """Ask each unpaid registration of a newly confirmed session to pay and confirm its participation."""
        for order in self.filtered(lambda order: order.state == "draft" and not order.training_payment_requested_at):
            if not order._training_registration_payable():
                continue
            order.action_quotation_sent()
            order.training_payment_requested_at = fields.Datetime.now()
            order._training_send_registration_mail(
                "training_management_sale.mail_template_session_registration_payment"
            )

    @api.private
    def _training_send_registration_mail(self, xmlid):
        template = self.env.ref(xmlid).sudo()
        for order in self:
            # The buyer is the only named contact of the order: the document policy checks the recipients.
            template.send_mail(order.id, email_layout_xmlid="mail.mail_notification_light")

    def action_confirm(self):
        result = super().action_confirm()
        for order in self.filtered("training_registration_delivery_id"):
            lots = order._training_registration_lots()
            lots.filtered(lambda lot: lot.state == "reserved" and lot._available()).action_confirm()
            if lots.filtered(lambda lot: not lot._available()):
                # Paid or confirmed after its places were released: the team decides on the places.
                order.sudo().message_post(
                    body=self.env._("The places of this registration were released before the order was confirmed."),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
        return result


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    @api.model_create_multi
    def create(self, vals_list):
        transactions = super().create(vals_list)
        for order in transactions.sale_order_ids.filtered("training_registration_delivery_id"):
            # The native transaction route does not ask whether the order has to be paid.
            if not order._training_registration_payable():
                raise ValidationError(
                    self.env._("This registration can be paid only once the session is confirmed and its places held.")
                )
        return transactions
