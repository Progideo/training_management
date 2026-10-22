from odoo import fields, models, _
from odoo.exceptions import ValidationError


class TrainingProgramNewVersion(models.TransientModel):
    _name = "training.program.new.version"
    _description = "New Programme Version"
    _check_company_auto = True

    source_id = fields.Many2one(
        "training.program.version",
        string="Source Programme",
        required=True,
        readonly=True,
        ondelete="cascade",
        check_company=True,
    )
    company_id = fields.Many2one(related="source_id.company_id", store=True)
    version = fields.Char(string="Version Reference", required=True)

    def action_create_version(self):
        self.ensure_one()
        self.check_access("read")
        source = self.source_id
        source.check_access("read")
        source.check_access("create")
        reference = (self.version or "").strip()
        if not reference:
            raise ValidationError(_("A version reference is required."))
        # Keep the source stable while native copy reads every translation.
        source._lock_courses()
        source.lock_for_update()
        source.invalidate_recordset()
        program = source.copy({"version": reference})
        return {
            "type": "ir.actions.act_window",
            "name": _("New Programme Version"),
            "res_model": program._name,
            "view_mode": "form",
            "res_id": program.id,
            "target": "current",
        }
