from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestTrainingPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.finance = new_test_user(cls.env, login="fictional_guard_finance", groups="account.group_account_invoice")
        cls.partner = cls.env["res.partner"].create({"name": "Fictional Payment Buyer"})
        accounts = []
        for code, kind, reconcile in (
            ("FX510", "asset_cash", False),
            ("FX341", "asset_current", True),
            ("FX340", "asset_receivable", True),
        ):
            accounts.append(
                cls.env["account.account"].create(
                    {
                        "name": "Fictional " + code,
                        "code": code,
                        "account_type": kind,
                        "reconcile": reconcile,
                        "company_ids": [Command.set(cls.env.company.ids)],
                    }
                )
            )
        cls.partner.property_account_receivable_id = accounts[2]
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Fictional Guard Bank",
                "code": "FXB",
                "type": "bank",
                "default_account_id": accounts[0].id,
            }
        )
        cls.method = cls.journal.inbound_payment_method_line_ids.filtered(lambda m: m.code == "manual")
        cls.method.payment_account_id = accounts[1]

    def _values(self, **extra):
        return {
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "payment_method_line_id": self.method.id,
            "amount": 10,
            "payment_type": "inbound",
            "partner_type": "customer",
            **extra,
        }

    def test_paid_write_create_and_audit_are_guarded(self):
        # Historical method id retained for the CI inventory; #102 retires bank guards.
        payments = self.env["account.payment"].with_user(self.finance)
        for method in ("action", "write"):
            values = self._values(memo="Fictional repeated native reference")
            payment = payments.create(values)
            if method == "action":
                payment.action_post()
            else:
                payment.write({"state": "paid"})
            self.assertEqual(payment.state, "paid")
            self.assertEqual(payment.move_id.state, "posted")
            self.assertFalse(payment.training_bank_verified_at)
        for field, value in (
            ("training_bank_reference", "FORGED"),
            ("training_bank_verified", True),
            ("training_bank_verified_by_id", self.finance.id),
            ("training_bank_verified_at", "2000-01-01 00:00:00"),
            ("training_duplicate_reference_reason", "FORGED"),
        ):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                payments.create(self._values(**{field: value}))
            with self.assertRaises(ValidationError), self.cr.savepoint():
                payment.write({field: value})
            with self.assertRaises(ValidationError), self.cr.savepoint():
                payments.with_context(**{"default_" + field: value}).create(self._values())
