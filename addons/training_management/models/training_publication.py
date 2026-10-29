"""Private participation facts for P14; no publication or consent grant."""

from odoo import api, models
from odoo.exceptions import AccessError


class PublicationService(models.AbstractModel):
    _name = "training.publication.service"
    _description = "Training Publication Preparation"

    @api.private
    def _participation_facts(self, enrollment):
        # This diagnostic is internal. It does not use an access token or infer
        # eligibility from enrollment state, learning access or a past PDF.
        user = self.env.user
        if not user.active or user._is_public() or not user.has_group("training_management.group_training_coordinator"):
            raise AccessError(self.env._("Only a training coordinator may inspect participation evidence."))
        enrollment.ensure_one()
        enrollment = enrollment.with_env(self.env(su=False))
        enrollment.check_access("read")
        if enrollment.company_id not in self.env.companies:
            raise AccessError(self.env._("This enrollment is outside the allowed companies."))
        # Narrow read of evidence for the already authorized enrollment only.
        attendance = self.env["training.attendance"].sudo().search([("enrollment_id", "=", enrollment.id)])
        certificates = (
            self.env["training.document"]
            .sudo()
            .search(
                [
                    ("dossier_id.enrollment_id", "=", enrollment.id),
                    ("kind", "=", "participation"),
                ]
            )
        )
        return {
            "enrollment_state": enrollment.state,
            "minutes": sum(a.minutes for a in attendance if a.state == "validated"),
            "attendance": [
                {"id": a.id, "revision": a.revision, "state": a.state, "minutes": a.minutes}
                for a in attendance.sorted("id")
            ],
            "certificates": [{"id": c.id, "kind": c.kind} for c in certificates.sorted("id")],
        }


class PublicationEnrollment(models.Model):
    _inherit = "training.enrollment"  # pylint: disable=consider-merging-classes-inherited  # P14 evidence inspection

    def action_inspect_publication_evidence(self):
        self.ensure_one()
        self.env["training.publication.service"]._participation_facts(self)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Participation Evidence for a Review"),
            "res_model": "training.publication.inspection",
            "view_mode": "form",
            "target": "new",
            "context": {"default_enrollment_id": self.id},
        }
