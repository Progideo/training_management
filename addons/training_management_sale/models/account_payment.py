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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "training_bank_reference" in vals:
                vals["training_bank_reference"] = (
                    vals["training_bank_reference"] or ""
                ).strip().upper() or False
        return super().create(vals_list)

    def write(self, vals):
        if {"training_bank_reference", "training_duplicate_reference_reason"} & set(vals):
            if any(payment.state != "draft" for payment in self):
                raise ValidationError(_("The bank reference of a posted payment cannot be changed."))
            if "training_bank_reference" in vals:
                vals["training_bank_reference"] = (
                    vals["training_bank_reference"] or ""
                ).strip().upper() or False
        return super().write(vals)

    def action_post(self):
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
        return super().action_post()
