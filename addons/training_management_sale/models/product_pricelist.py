from odoo import models, _
from odoo.exceptions import ValidationError


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def write(self, vals):
        if "currency_id" in vals:
            # The order currency is computed from the pricelist, including after confirmation.
            # Search across companies so a pricelist administrator cannot alter another
            # company's confirmed training order through a shared pricelist.
            confirmed = self.env["sale.order"].sudo().search_count([
                ("pricelist_id", "in", self.ids),
                ("state", "=", "sale"),
                ("training_request_kind", "!=", False),
            ])
            if confirmed:
                raise ValidationError(_("The currency of a pricelist used by a confirmed training order cannot be changed."))
        return super().write(vals)
