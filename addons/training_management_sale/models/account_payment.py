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
        return bool(self.training_bank_reference or self.reconciled_invoice_ids.filtered("training_is_sale_invoice"))

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
                "partner_ids": self.env["training.document.policy"]._partners(payment, email_only=True).ids,
                "email_to": "",
                "email_cc": "",
            }
        return recipients

    def _notify_get_recipients(self, message, **kwargs):
        recipients = super()._notify_get_recipients(message, **kwargs)
        return self.env["training.document.policy"]._filter_notifications(self, recipients)

    training_bank_reference = fields.Char(
        copy=False,
        index=True,
        help="Reference checked against the bank evidence, separate from the invoice memo.",
    )
    training_duplicate_reference_reason = fields.Char(
        string="Repeated Reference Reason",
        copy=False,
        help="Explain an intentional allocation of one transfer across several payments.",
    )
    training_bank_verified = fields.Boolean(
        string="Bank Receipt Checked",
        copy=False,
        help="The accountant confirms having checked the bank receipt before recording this payment.",
    )
    training_bank_verified_by_id = fields.Many2one(
        "res.users",
        string="Bank Receipt Checked By",
        copy=False,
        readonly=True,
    )
    training_bank_verified_at = fields.Datetime(
        string="Bank Receipt Checked At",
        copy=False,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # training records are changed only through their controlled actions
        default_reference = self.default_get(["training_bank_reference"]).get("training_bank_reference")
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if "training_bank_reference" not in vals and default_reference:
                vals["training_bank_reference"] = default_reference
            if {"training_bank_verified_by_id", "training_bank_verified_at"} & set(vals):
                raise ValidationError(self.env._("The bank check audit fields are set when the payment is posted."))
            if "training_bank_reference" in vals:
                vals["training_bank_reference"] = (vals["training_bank_reference"] or "").strip().upper() or False
        # Native create accepts an already paid state; enter it through the same
        # guarded write as action_post, after all draft records exist.
        if any(
            "default_" + field in self.env.context
            for field in (
                "training_bank_verified_by_id",
                "training_bank_verified_at",
            )
        ):
            raise ValidationError(self.env._("The bank check audit fields are set when the payment is posted."))
        default_state = self.default_get(["state"]).get("state", "draft")
        states = [vals.get("state", default_state) for vals in vals_list]
        with self.env.cr.savepoint():
            return self._create_training_guarded_payments(vals_list, states)

    def _create_training_guarded_payments(self, vals_list, states):
        payments = super().create(  # pylint: disable=super-method-mismatch  # deliberate bypass of the controlled write, see _store
            [
                {**vals, "state": "draft"} if state in ("paid", "reconciled") else vals
                for vals, state in zip(vals_list, states)
            ]
        )
        for payment, state in zip(payments, states):
            target_state = state if state in ("paid", "reconciled") else payment.state
            if target_state in ("paid", "reconciled"):
                payment.write({"state": target_state})
        return payments

    def write(self, vals):
        if {"training_bank_verified_by_id", "training_bank_verified_at"} & set(vals):
            raise ValidationError(self.env._("The bank check audit fields are set when the payment is posted."))
        if {"training_bank_reference", "training_duplicate_reference_reason", "training_bank_verified"} & set(vals):
            if any(payment.state != "draft" for payment in self):
                raise ValidationError(self.env._("The bank reference of a posted payment cannot be changed."))
            if "training_bank_reference" in vals:
                vals["training_bank_reference"] = (vals["training_bank_reference"] or "").strip().upper() or False
        self.check_access("write")
        # A caller can change state through RPC/import as well as action_post.
        # Apply simultaneous reference/check changes before checking the target state.
        if vals.get("state") in ("paid", "reconciled"):
            with self.env.cr.savepoint():
                other_vals = {key: value for key, value in vals.items() if key != "state"}
                if other_vals:
                    self.write(other_vals)
                tagged = self.filtered(
                    lambda payment: (
                        payment.training_bank_reference
                        and (
                            payment.state not in ("paid", "reconciled")
                            or not payment.training_bank_verified_by_id
                            or not payment.training_bank_verified_at
                        )
                    )
                )
                tagged._check_training_bank_posting()
                if tagged:
                    super(AccountPayment, tagged).write(
                        {
                            "training_bank_verified_by_id": self.env.user.id,
                            "training_bank_verified_at": fields.Datetime.now(),
                        }
                    )
                # A payment default_state must not leak into creation of its
                # account.move (whose valid states differ from payment states).
                posting_self = self.with_context(  # pylint: disable=context-overridden  # the given context replaces the current one on purpose
                    {key: value for key, value in self.env.context.items() if key != "default_state"}
                )
                return super(AccountPayment, posting_self).write({"state": vals["state"]})
        return super().write(vals)

    def _check_training_bank_posting(self):
        tagged_payments = self
        if any(
            payment.payment_type != "inbound"
            or payment.journal_id.type != "bank"
            or payment.payment_method_line_id.code != "manual"
            for payment in tagged_payments
        ):
            raise ValidationError(
                self.env._("A training bank reference requires an incoming bank payment with the manual method.")
            )
        if any(not payment.training_bank_verified for payment in tagged_payments):
            raise ValidationError(
                self.env._("Confirm that the bank receipt was checked before posting a training payment.")
            )
        payments = tagged_payments
        for journal_id in sorted(set(payments.journal_id.ids)):
            # A lock alone does not refresh Odoo's REPEATABLE READ snapshot.
            # A real write makes a stale concurrent transaction fail with 40001;
            # Odoo's service retries the entire transaction with a fresh snapshot.
            self.env.cr.execute(
                "UPDATE account_journal SET training_bank_reference_revision = "
                "COALESCE(training_bank_reference_revision, 0) + 1 WHERE id = %s",
                [journal_id],
            )
        seen = set()
        for payment in payments.sorted("id"):
            key = (payment.company_id.id, payment.journal_id.id, payment.training_bank_reference)
            # A finance user may not see every payment of the company. The lookup
            # only returns a boolean and is scoped to this journal and company.
            existing = self.sudo().search(
                [
                    ("company_id", "=", payment.company_id.id),
                    ("journal_id", "=", payment.journal_id.id),
                    ("training_bank_reference", "=", payment.training_bank_reference),
                    ("state", "in", ("paid", "reconciled")),
                    ("id", "!=", payment.id),
                ],
                limit=1,
            )
            if (existing or key in seen) and not (payment.training_duplicate_reference_reason or "").strip():
                raise ValidationError(
                    self.env._(
                        "This bank reference was already recorded in this company and journal. "
                        "Explain the intentional split before continuing."
                    )
                )
            seen.add(key)
