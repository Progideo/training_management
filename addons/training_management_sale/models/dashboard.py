"""Commercial figures use ordinary Sales/Accounting ACLs, by original currency."""

from odoo import api, models
from odoo.tools.misc import formatLang


class DashboardService(models.AbstractModel):
    _inherit = "training.dashboard.service"

    @api.private
    def _commercial(self, delivery, start, end):
        result = super()._commercial(delivery, start, end)
        self._delivery(delivery.id)

        def period(date):
            return date and (not start or date >= start) and (not end or date <= end)

        sales = self.env["sale.order.line"]
        if not sales.has_access("read"):
            return result
        # Only commercial lines actually allocated to this delivery; ordinary
        # ACLs apply also when a coordinator lacks Sales or Accounting access.
        lots = self.env["training.seat.allocation"]
        if not lots.has_access("read"):
            return result
        allocated = lots.search([("delivery_id", "=", delivery.id)]).sale_line_id
        lines = sales.search([("id", "in", allocated.ids), ("order_id.state", "=", "sale")])
        dated_lines = lines.filtered(lambda line: period(line.order_id.date_order.date()))
        for currency in dated_lines.currency_id:
            group = dated_lines.filtered(lambda line: line.currency_id == currency)
            result.append(
                {
                    "currency": currency.name,
                    "amount": sum(group.mapped("price_subtotal")),
                    "kind": "sales",
                    "ids": group.order_id.ids,
                    "label": self.env._(
                        "Confirmed allocated sales excl. tax: %(amount)s %(currency)s · %(count)s orders · S10-1",
                        amount=formatLang(self.env, sum(group.mapped("price_subtotal")), digits=2),
                        currency=currency.name,
                        count=len(group.order_id),
                    ),
                }
            )
        invoices = self.env["account.move.line"]
        if invoices.has_access("read"):
            invoice_lines = invoices.search(
                [
                    ("sale_line_ids.order_id", "in", lines.order_id.ids),
                    ("move_id.state", "=", "posted"),
                    ("move_id.move_type", "in", ("out_invoice", "out_refund")),
                ]
            )
            invoice_lines = invoice_lines.filtered(lambda line: period(line.move_id.invoice_date))
            moves = invoice_lines.move_id
            for currency in moves.currency_id:
                group = moves.filtered(lambda move: move.currency_id == currency)
                amount = sum(move.amount_untaxed * (-1 if move.move_type == "out_refund" else 1) for move in group)
                result.append(
                    {
                        "currency": currency.name,
                        "amount": amount,
                        "kind": "invoices",
                        "ids": group.ids,
                        "label": self.env._(
                            "Whole posted invoice cohort linked to allocated orders, less refunds excl. tax: %(amount)s %(currency)s · S10-1",
                            amount=formatLang(self.env, amount, digits=2),
                            currency=currency.name,
                        ),
                    }
                )
            payments = self.env["account.payment"]
            if payments.has_access("read"):
                paid = payments.search(
                    [
                        ("reconciled_invoice_ids", "in", invoice_lines.move_id.ids),
                        ("state", "in", ("paid", "reconciled")),
                        ("payment_type", "=", "inbound"),
                    ]
                )
                # A payment covering several invoices is not an allocation to a
                # particular training: expose references, never its whole amount.
                paid = paid.filtered(lambda payment: period(payment.date))
                result.append(
                    {
                        "kind": "payments",
                        "ids": paid.ids,
                        "label": self.env._(
                            "Reconciled incoming payment references: %(count)s; amounts not allocated to this delivery",
                            count=len(paid),
                        ),
                    }
                )
        payments = self.env["account.payment"]
        if payments.has_access("read"):
            cash = payments.search(
                [
                    ("company_id", "=", delivery.company_id.id),
                    ("state", "in", ("paid", "reconciled")),
                    ("payment_type", "=", "inbound"),
                    ("partner_type", "=", "customer"),
                ]
            )
            cash = cash.filtered(lambda payment: period(payment.date))
            for currency in cash.currency_id:
                group = cash.filtered(lambda payment: payment.currency_id == currency)
                result.append(
                    {
                        "kind": "company_cash",
                        "currency": currency.name,
                        "amount": sum(group.mapped("amount")),
                        "ids": group.ids,
                        "label": self.env._(
                            "Company customer receipts in period — not allocated to a delivery: %(amount)s %(currency)s · %(count)s payments · S10-1",
                            amount=formatLang(self.env, sum(group.mapped("amount")), digits=2),
                            currency=currency.name,
                            count=len(group),
                        ),
                    }
                )
        leads = self.env["crm.lead"]
        if leads.has_access("read"):
            cohort = leads.search(
                [
                    ("training_program_id", "=", delivery.program_id.id),
                    ("company_id", "=", delivery.company_id.id),
                    ("type", "=", "opportunity"),
                    ("active", "=", True),
                ]
            )
            cohort = cohort.filtered(lambda lead: period(lead.create_date.date()))
            orders = self.env["sale.order"].search([("opportunity_id", "in", cohort.ids), ("state", "=", "sale")])
            converted = len(cohort.filtered(lambda lead: lead in orders.opportunity_id))
            ratio = self._ratio(
                self.env._("Programme opportunity cohort conversion"),
                converted,
                len(cohort),
                len(cohort),
                "qualified active programme opportunities with confirmed order / qualified active programme opportunities",
            )
            result.append(
                {
                    "kind": "conversion",
                    "numerator": converted,
                    "denominator": len(cohort),
                    "ids": cohort.ids,
                    "label": self.env._(
                        "Programme cohort conversion (creation period, current state): %(n)s / %(d)s — %(rate)s · S10-1",
                        n=converted,
                        d=len(cohort),
                        rate=(formatLang(self.env, ratio["rate"], digits=2) + " %")
                        if ratio["rate"] is not None
                        else self.env._("Not calculable"),
                    ),
                }
            )
        sources = {
            "sales": "sale.order",
            "invoices": "account.move",
            "payments": "account.payment",
            "company_cash": "account.payment",
            "conversion": "crm.lead",
        }
        for row in result:
            model_name = sources[row["kind"]]
            records = self.env[model_name].browse(row["ids"])
            records.check_access("read")
            row["details"] = [
                {"name": record.display_name, "url": "/odoo/%s/%s" % (model_name, record.id)} for record in records
            ]
        return result

    @api.private
    def _notifications(self, delivery):
        result = super()._notifications(delivery)
        model = self.env["training.request.notice"]
        if model.has_access("read"):
            for notice in model.search(
                [
                    ("lead_id.training_program_id", "=", delivery.program_id.id),
                    ("company_id", "=", delivery.company_id.id),
                ]
            ):
                result.append(
                    {
                        "kind": self.env._("Programme request acknowledgement (programme scope)"),
                        "date": str(notice.create_date),
                        "recipient": notice.lead_id.contact_name or notice.lead_id.name,
                        "template": notice.template_version,
                        "state": self._label(notice.mail_id, "state") if notice.mail_id else self.env._("Not queued"),
                        "failure": notice.mail_id.failure_reason or notice.failure or "",
                        "source": model._name,
                        "id": notice.id,
                    }
                )
        return result
