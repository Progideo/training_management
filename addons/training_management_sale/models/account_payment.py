from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_thread_with_access(self, thread_id, *, mode="read", **kwargs):
        thread = super()._get_thread_with_access(thread_id, mode=mode, **kwargs)
        if (thread and self.env.user.share and thread.sudo()._training_receipt_is_restricted()
                and (self.env.user._is_public()
                     or self.env.user.partner_id not in thread.sudo()._training_receipt_allowed_partners())):
            return self.browse()
        return thread

    def _training_receipt_is_restricted(self):
        self.ensure_one()
        return bool(
            self.training_bank_reference
            or self.reconciled_invoice_ids.filtered("training_is_sale_invoice")
        )

    def _training_receipt_allowed_partners(self):
        self.ensure_one()
        invoices = self.reconciled_invoice_ids
        training_invoices = invoices.filtered("training_is_sale_invoice")
        if not training_invoices or training_invoices != invoices:
            return self.env["res.partner"]
        allowed = training_invoices[0].training_portal_partner_ids.filtered("email")
        for invoice in training_invoices[1:]:
            allowed &= invoice.training_portal_partner_ids.filtered("email")
        return allowed

    def _message_get_default_recipients(self, with_cc=False, all_tos=False):
        recipients = super()._message_get_default_recipients(with_cc=with_cc, all_tos=all_tos)
        for payment in self.filtered(lambda item: item._training_receipt_is_restricted()):
            recipients[payment.id] = {
                "partner_ids": payment._training_receipt_allowed_partners().ids,
                "email_to": "", "email_cc": "",
            }
        return recipients

    def _notify_get_recipients(self, message, **kwargs):
        recipients = super()._notify_get_recipients(message, **kwargs)
        if not self._training_receipt_is_restricted():
            return recipients
        allowed_ids = set(self._training_receipt_allowed_partners().ids)
        return [recipient for recipient in recipients
                if not recipient["share"] or recipient["id"] in allowed_ids]

    training_bank_reference = fields.Char(
        string="Training Bank Reference", copy=False, index=True,
        help="Reference checked against the bank evidence, separate from the invoice memo.",
    )
    training_duplicate_reference_reason = fields.Char(
        string="Repeated Reference Reason", copy=False,
        help="Explain an intentional allocation of one transfer across several payments.",
    )
    training_bank_verified = fields.Boolean(
        string="Bank Receipt Checked", copy=False,
        help="The accountant confirms having checked the bank receipt before recording this payment.",
    )
    training_bank_verified_by_id = fields.Many2one(
        "res.users", string="Bank Receipt Checked By", copy=False, readonly=True,
    )
    training_bank_verified_at = fields.Datetime(
        string="Bank Receipt Checked At", copy=False, readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "training_bank_reference" in vals:
                vals["training_bank_reference"] = (
                    vals["training_bank_reference"] or ""
                ).strip().upper() or False
        return super().create(vals_list)

    def write(self, vals):
        if {"training_bank_verified_by_id", "training_bank_verified_at"} & set(vals):
            raise ValidationError(_("The bank check audit fields are set when the payment is posted."))
        if {"training_bank_reference", "training_duplicate_reference_reason",
                "training_bank_verified"} & set(vals):
            if any(payment.state != "draft" for payment in self):
                raise ValidationError(_("The bank reference of a posted payment cannot be changed."))
            if "training_bank_reference" in vals:
                vals["training_bank_reference"] = (
                    vals["training_bank_reference"] or ""
                ).strip().upper() or False
        return super().write(vals)

    def action_post(self):
        tagged_payments = self.filtered(lambda payment:
            payment.state in ("draft", "paid") and payment.training_bank_reference
        )
        if any(
            payment.payment_type != "inbound"
            or payment.journal_id.type != "bank"
            or payment.payment_method_line_id.code != "manual"
            for payment in tagged_payments
        ):
            raise ValidationError(_(
                "A training bank reference requires an incoming bank payment with the manual method."
            ))
        if any(not payment.training_bank_verified for payment in tagged_payments):
            raise ValidationError(_(
                "Confirm that the bank receipt was checked before posting a training payment."
            ))
        payments = self.filtered(lambda payment:
            payment.state in ("draft", "paid")
            and payment.payment_type == "inbound"
            and payment.journal_id.type == "bank"
            and payment.training_bank_reference
        )
        for journal_id in sorted(set(payments.journal_id.ids)):
            # Serialise duplicate checks per journal, including concurrent wizard requests.
            self.env.cr.execute(
                "SELECT id FROM account_journal WHERE id = %s FOR UPDATE", [journal_id],
            )
        seen = set()
        for payment in payments.sorted("id"):
            key = (payment.company_id.id, payment.journal_id.id, payment.training_bank_reference)
            # A finance user may not see every payment of the company. The lookup
            # only returns a boolean and is scoped to this journal and company.
            existing = self.sudo().search([
                ("company_id", "=", payment.company_id.id),
                ("journal_id", "=", payment.journal_id.id),
                ("training_bank_reference", "=", payment.training_bank_reference),
                ("state", "in", ("paid", "reconciled")),
                ("id", "!=", payment.id),
            ], limit=1)
            if (existing or key in seen) and not (payment.training_duplicate_reference_reason or "").strip():
                raise ValidationError(_(
                    "This bank reference was already recorded in this company and journal. "
                    "Explain the intentional split before continuing."
                ))
            seen.add(key)
        result = super().action_post()
        super(AccountPayment, tagged_payments).write({
            "training_bank_verified_by_id": self.env.user.id,
            "training_bank_verified_at": fields.Datetime.now(),
        })
        return result
