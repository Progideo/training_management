from odoo import api, models
from odoo.tools import format_amount


class TrainingCourse(models.Model):
    _inherit = "training.course"

    @api.private
    def _catalogue_facts(self, company):
        facts = super()._catalogue_facts(company)
        products = (
            self.env["product.template"]
            .sudo()
            .search(
                [
                    ("training_course_id", "in", self.ids),
                    ("training_public_session_price", "=", True),
                    ("training_price_basis", "=", "person"),
                    ("sale_ok", "=", True),
                    ("company_id", "in", (company.id, False)),
                ]
            )
        )
        for course in self:
            product = products.filtered(lambda p, c=course: p.training_course_id == c)[:1]
            price = None
            if product and course.public_catalogue:
                # Amount excluding taxes, in the operator's currency; « HT » is added by the page.
                taxes = product.taxes_id.filtered(lambda tax: tax.company_id == company)
                currency = product.currency_id
                amount = taxes.compute_all(product.list_price, currency, 1.0, product=product)["total_excluded"]
                price = {"amount": amount, "label": format_amount(self.env, amount, currency)}
            facts[course.id]["session_price"] = price
        return facts
