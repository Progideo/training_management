from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

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
