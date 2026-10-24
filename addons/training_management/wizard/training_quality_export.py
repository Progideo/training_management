"""Deliberately approved summary only: never copy a whole complaint into S08."""

import hashlib

from odoo import fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.binary import BinaryBytes


class QualityExport(models.TransientModel):
    _name = "training.quality.export"
    _description = "Approved Private Quality Summary for S08"

    complaint_id = fields.Many2one("training.complaint")
    improvement_id = fields.Many2one("training.improvement")
    dossier_id = fields.Many2one("training.closure", required=True)
    summary = fields.Text(
        required=True, help="Explicitly approve the minimum necessary summary; exclude third-party details."
    )

    def action_export(self):
        self.ensure_one()
        self.check_access("read")
        if bool(self.complaint_id) == bool(self.improvement_id) or not self.summary.strip():
            raise ValidationError(self.env._("Select one quality source and approve its minimal summary."))
        source = self.complaint_id or self.improvement_id
        source._authorize(quality=True, mutating=False)
        if source.state not in ("resolved", "closed", "effective", "ineffective"):
            raise ValidationError(
                self.env._("Finish the treatment or effectiveness decision before creating its summary.")
            )
        dossier = self.dossier_id
        dossier._authorize(quality=True)
        dossier._serialize()
        if dossier.state == "closed" or not source.delivery_id or dossier.delivery_id != source.delivery_id:
            raise ValidationError(self.env._("Choose an open S08 dossier in the same delivery."))
        fingerprint = hashlib.sha256(self.summary.encode()).hexdigest()
        event = source.event_ids.sorted("id")[-1:]
        origin = "%s:%s; event:%s; summary:%s; S093-QWEB-1" % (source._name, source.id, event.id, fingerprint)
        existing = self.env["training.proof"].search(
            [("dossier_id", "=", dossier.id), ("source", "=", origin)], limit=1
        )
        if existing:
            proof = existing
        else:
            report = self.env.ref("training_management.report_quality_summary")
            engine = self.env["ir.actions.report"]
            html = engine._render_template("training_management.quality_summary", {"summary": self.summary}).decode()
            data = engine._run_pdf_engine_without_processing(engine._get_pdf_engine(report), [html], report_ref=report)
            if not data.startswith(b"%PDF-"):
                raise ValidationError(self.env._("Quality summary PDF generation failed."))
            proof = self.env["training.proof"].create(
                {
                    "dossier_id": dossier.id,
                    "category": "incidents",
                    "confidentiality": "sensitive",
                    "source": origin,
                    "author": self.env.user.name,
                    "produced_at": fields.Datetime.now(),
                    "data": BinaryBytes(data),
                    "filename": "quality-summary.pdf",
                }
            )
        return {"type": "ir.actions.act_window", "res_model": "training.proof", "res_id": proof.id, "view_mode": "form"}


class QualitySummaryReport(models.AbstractModel):
    _name = "report.training_management.quality_summary"
    _description = "Quality Summary Report Access"

    def _get_report_values(self, docids, data=None):
        raise AccessError(self.env._("Use the controlled quality summary export action."))
