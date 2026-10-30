"""Billing address opt-in retains native selection and explicit tax recomputation."""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNativeFiscal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.sale_fiscal_by_invoice_address = True
        cls.billing = cls.env["res.partner"].create(
            {"name": "Fictional billing", "country_id": cls.env.ref("base.fr").id}
        )
        cls.shipping = cls.env["res.partner"].create(
            {"name": "Fictional delivery", "country_id": cls.env.ref("base.be").id}
        )
        cls.fr = cls.env["account.fiscal.position"].create(
            {
                "name": "Fictional France",
                "auto_apply": True,
                "sequence": -200,
                "country_id": cls.env.ref("base.fr").id,
            }
        )
        cls.be = cls.env["account.fiscal.position"].create(
            {
                "name": "Fictional Belgium",
                "auto_apply": True,
                "sequence": -200,
                "country_id": cls.env.ref("base.be").id,
            }
        )
        cls.product = cls.env["product.product"].create({"name": "Fictional service", "type": "service"})

    def order(self):
        return self.env["sale.order"].create(
            {
                "partner_id": self.billing.id,
                "partner_invoice_id": self.billing.id,
                "partner_shipping_id": self.shipping.id,
                "order_line": [Command.create({"product_id": self.product.id, "price_unit": 100})],
            }
        )

    def test_manual_native_position_wins_and_policy_off_uses_delivery(self):
        order = self.order()
        self.assertEqual(order.fiscal_position_id, self.fr)
        manual = self.env["account.fiscal.position"].create({"name": "Fictional manual"})
        self.billing.property_account_position_id = manual
        order._compute_fiscal_position_id()
        self.assertEqual(order.fiscal_position_id, manual)
        self.billing.property_account_position_id = False
        self.company.sale_fiscal_by_invoice_address = False
        order._compute_fiscal_position_id()
        self.assertEqual(order.fiscal_position_id, self.be)
        self.company.sale_fiscal_by_invoice_address = True
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.billing.id,
                "partner_shipping_id": self.shipping.id,
            }
        )
        self.assertEqual(invoice.fiscal_position_id, self.fr)
        purchase = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.billing.id,
                "partner_shipping_id": self.shipping.id,
            }
        )
        native = self.env["account.fiscal.position"]._get_fiscal_position(self.billing, delivery=self.shipping)
        self.assertEqual(purchase.fiscal_position_id, native)

    def test_rpc_position_change_keeps_manual_taxes_until_native_recompute(self):
        tax = self.env["account.tax"].create({"name": "Fictional manually chosen tax", "amount": 7})
        for enabled in (True, False):
            self.company.sale_fiscal_by_invoice_address = enabled
            order = self.order()
            line = order.order_line
            line.tax_ids = tax
            order.fiscal_position_id = self.be if enabled else self.fr
            self.assertEqual(line.tax_ids, tax)
            order.action_confirm()
            order.fiscal_position_id = self.fr if enabled else self.be
            self.assertEqual(line.tax_ids, tax)
            order._recompute_taxes()
            self.assertEqual(
                line.tax_ids, order.fiscal_position_id.map_tax(self.product.taxes_id._filter_taxes_by_company())
            )
