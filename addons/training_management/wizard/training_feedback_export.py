"""Explicit S08 destination: collective summary only, no individual answers."""

from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.tools.binary import BinaryBytes


class FeedbackExport(models.TransientModel):
    _name = "training.feedback.export"
    _description = "Attach Feedback Summary to S08"

    campaign_id = fields.Many2one("training.feedback.campaign", required=True)
    dossier_id = fields.Many2one("training.closure", required=True)

    def action_export(self):
        self.ensure_one()
        self.check_access("read")
        campaign = self.env["training.feedback.service"]._campaign(self.campaign_id.id, staff=True, lock=True)
        dossier = self.dossier_id
        dossier._authorize()
        dossier._serialize()
        if campaign.state != "closed" or dossier.state == "closed" or dossier.delivery_id != campaign.delivery_id:
            raise ValidationError(self.env._("Choose a closed campaign and an open dossier in the same delivery."))
        source = "training.feedback.campaign:%s; S092-QWEB-1" % campaign.id
        proof = self.env["training.proof"].search([("dossier_id", "=", dossier.id), ("source", "=", source)], limit=1)
        if not proof:
            engine = self.env["ir.actions.report"]
            report = self.env.ref("training_management.report_feedback")
            values = self.env["report.training_management.feedback_document"]._get_report_values(campaign.ids)
            html = engine._render_template("training_management.feedback_document", values).decode()
            data = engine._run_pdf_engine_without_processing(engine._get_pdf_engine(report), [html], report_ref=report)
            if not data.startswith(b"%PDF-"):
                raise ValidationError(self.env._("Feedback PDF generation failed."))
            proof = self.env["training.proof"].create(
                {
                    "dossier_id": dossier.id,
                    "category": "feedback",
                    "source": source,
                    "author": self.env._("Feedback campaign"),
                    "produced_at": campaign.closed_at,
                    "data": BinaryBytes(data),
                    "filename": "feedback-%s.pdf" % campaign.id,
                }
            )
        return {"type": "ir.actions.act_window", "res_model": "training.proof", "res_id": proof.id, "view_mode": "form"}
