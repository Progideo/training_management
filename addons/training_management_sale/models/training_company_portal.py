from odoo import api, models


class TrainingCompanyService(models.AbstractModel):
    _inherit = "training.company.service"

    @api.private
    def _request_rows(self):
        rows = []
        seen = set()
        for grant in self._grants():
            leads = (
                self.env["crm.lead"]
                .sudo()
                .search(
                    [
                        ("company_id", "=", grant.company_id.id),
                        ("training_request_kind", "=", "group"),
                        ("partner_id.commercial_partner_id", "=", grant.customer_id.id),
                    ]
                )
            )
            rows += [{"name": lead.name, "stage": lead.stage_id.name} for lead in leads if lead.id not in seen]
            seen.update(leads.ids)
        return rows
