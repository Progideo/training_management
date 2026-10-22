from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestTrainingPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.finance = new_test_user(cls.env, login="fictional_guard_finance",
                                    groups="account.group_account_invoice")
        cls.partner = cls.env["res.partner"].create({"name": "Fictional Payment Buyer"})
        accounts = []
        for code, kind, reconcile in (("FX510", "asset_cash", False),
                                      ("FX341", "asset_current", True),
                                      ("FX340", "asset_receivable", True)):
            accounts.append(cls.env["account.account"].create({
                "name": "Fictional " + code, "code": code, "account_type": kind,
                "reconcile": reconcile, "company_ids": [Command.set(cls.env.company.ids)],
            }))
        cls.partner.property_account_receivable_id = accounts[2]
        cls.journal = cls.env["account.journal"].create({
            "name": "Fictional Guard Bank", "code": "FXB", "type": "bank",
            "default_account_id": accounts[0].id,
        })
        cls.method = cls.journal.inbound_payment_method_line_ids.filtered(lambda m: m.code == "manual")
        cls.method.payment_account_id = accounts[1]

    def _values(self, **extra):
        return {"partner_id": self.partner.id, "journal_id": self.journal.id,
                "payment_method_line_id": self.method.id, "amount": 10,
                "payment_type": "inbound", "partner_type": "customer",
                "training_bank_reference": " fictional-repeat ", "training_bank_verified": True,
                **extra}

    def test_paid_write_create_and_audit_are_guarded(self):
        payments = self.env["account.payment"].with_user(self.finance)
        first = payments.create(self._values())
        self.assertFalse(first.training_bank_verified_at)
        first.write({"state": "paid"})
        self.assertEqual(first.training_bank_reference, "FICTIONAL-REPEAT")
        self.assertEqual(first.move_id.state, "posted")
        self.assertEqual(first.training_bank_verified_by_id, self.finance)
        self.assertTrue(first.training_bank_verified_at)
        audit = first.training_bank_verified_at
        first.action_post()
        self.assertEqual(first.training_bank_verified_at, audit)
        second = payments.create(self._values())
        for operation in (lambda: second.action_post(), lambda: second.write({"state": "paid"}),
                          lambda: second.write({"state": "reconciled"}),
                          lambda: payments.create(self._values(state="paid")),
                          lambda: payments.create(self._values(state="reconciled"))):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                operation()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            payments.with_context(default_state="paid").create(self._values())
        with self.assertRaises(ValidationError), self.cr.savepoint():
            payments.with_context(default_training_bank_verified_by_id=self.finance.id).create(self._values())
        self.assertEqual(second.state, "draft")
        self.assertFalse(second.move_id)
        self.assertFalse(second.training_bank_verified_by_id)
        second.write({"training_duplicate_reference_reason": "Intentional split across invoices"})
        second.action_post()
        self.assertEqual(second.training_bank_verified_by_id, self.finance)
        for metadata in ({"training_bank_verified_by_id": self.env.user.id},
                         {"training_bank_verified_at": "2000-01-01 00:00:00"}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                payments.create(self._values(**metadata))
            with self.assertRaises(ValidationError):
                first.write(metadata)
        unverified = payments.create(self._values(training_bank_reference="FICTIONAL-UNVERIFIED",
                                                  training_bank_verified=False))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            unverified.write({"state": "paid"})
        self.assertFalse(unverified.move_id)
        unverified.write({"state": "paid", "training_bank_verified": True})
        self.assertEqual(unverified.training_bank_verified_by_id, self.finance)
        batch = self._values(state="paid", training_bank_reference="FICTIONAL-BATCH")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            payments.create([batch.copy(), batch.copy()])
        self.assertFalse(payments.search([("training_bank_reference", "=", "FICTIONAL-BATCH")]))
        values = self._values()
        values.pop("training_bank_reference")
        contextual = payments.with_context(
            default_state="paid", default_training_bank_reference=" fictional-context ",
        ).create(values)
        self.assertEqual(contextual.training_bank_reference, "FICTIONAL-CONTEXT")
        self.assertEqual(contextual.training_bank_verified_by_id, self.finance)
        # Creating a valid paid record and ordinary native payments remain possible.
        direct = payments.create(self._values(state="paid", training_bank_reference="FICTIONAL-DIRECT"))
        self.assertEqual(direct.training_bank_verified_by_id, self.finance)
        native = payments.create(self._values(training_bank_reference=False, training_bank_verified=False))
        native.action_post()
        self.assertEqual(native.state, "paid")
        self.assertFalse(native.training_bank_verified_at)
