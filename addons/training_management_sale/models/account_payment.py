from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_thread_with_access(self, thread_id, *, mode="read", **kwargs):
        thread = super()._get_thread_with_access(thread_id, mode=mode, **kwargs)
        # Native token/author paths still need the current document grant.
        if thread and not self.env["training.document.policy"]._can_read(thread):
            return self.browse()
        return thread

    def _training_receipt_is_restricted(self):
        self.ensure_one()
        return bool(
            self.training_receipt_restricted
            or self.training_bank_reference
            or self.reconciled_invoice_ids.filtered("training_is_sale_invoice")
        )

    def _training_receipt_allowed_partners(self):
        self.ensure_one()
        invoices = self.reconciled_invoice_ids
        if self.move_id:
            lines = self.move_id.line_ids
            matched = (lines.matched_debit_ids.debit_move_id | lines.matched_credit_ids.credit_move_id).move_id
            if not invoices or invoices - matched:
                return self.env["res.partner"]
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
                "partner_ids": self.env["training.document.policy"]._partners(payment, email_only=True).ids,
                "email_to": "",
                "email_cc": "",
            }
        return recipients

    def _notify_get_recipients(self, message, **kwargs):
        recipients = super()._notify_get_recipients(message, **kwargs)
        return self.env["training.document.policy"]._filter_notifications(self, recipients)

    training_receipt_restricted = fields.Boolean(
        readonly=True,
        copy=False,
        help="Privacy marker retained after a training payment is unreconciled.",
    )

    training_bank_reference = fields.Char(
        readonly=True,
        copy=False,
        index=True,
        help="Reference checked against the bank evidence, separate from the invoice memo.",
    )
    training_duplicate_reference_reason = fields.Char(
        string="Repeated Reference Reason",
        readonly=True,
        copy=False,
        help="Explain an intentional allocation of one transfer across several payments.",
    )
    training_bank_verified = fields.Boolean(
        string="Bank Receipt Checked",
        readonly=True,
        copy=False,
        help="The accountant confirms having checked the bank receipt before recording this payment.",
    )
    training_bank_verified_by_id = fields.Many2one(
        "res.users",
        string="Bank Receipt Checked By",
        readonly=True,
        copy=False,
    )
    training_bank_verified_at = fields.Datetime(
        string="Bank Receipt Checked At",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        legacy = {
            "training_bank_reference",
            "training_bank_verified",
            "training_bank_verified_by_id",
            "training_bank_verified_at",
            "training_duplicate_reference_reason",
        }
        if any(legacy & vals.keys() for vals in vals_list) or any(
            "default_" + field in self.env.context for field in legacy
        ):
            raise ValidationError(self.env._("Historical bank evidence is read-only."))
        payments = super().create(vals_list)
        payments._retain_training_receipt_privacy()
        return payments

    def write(self, vals):
        # Freeze legacy evidence without imposing its old policy on native payments.
        if set(vals) & {
            "training_bank_reference",
            "training_bank_verified",
            "training_bank_verified_by_id",
            "training_bank_verified_at",
            "training_duplicate_reference_reason",
        } or ("training_receipt_restricted" in vals and not vals["training_receipt_restricted"]):
            raise ValidationError(self.env._("Historical bank evidence and receipt privacy are read-only."))
        if "invoice_ids" in vals:
            self._retain_training_receipt_privacy()
        result = super().write(vals)
        if "invoice_ids" in vals:
            self._retain_training_receipt_privacy()
        return result

    def _retain_training_receipt_privacy(self):
        for payment in self.filtered(lambda item: not item.training_receipt_restricted):
            if payment._training_receipt_is_restricted():
                super(AccountPayment, payment).write({"training_receipt_restricted": True})  # pylint: disable=super-method-mismatch
        return True
