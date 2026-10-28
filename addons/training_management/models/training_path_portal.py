"""Personal path summaries, projected through the existing enrollment identity."""

from odoo import api, models


class TrainingPathPortal(models.AbstractModel):
    _name = "training.path.portal"
    _description = "Participant Training Path Summary"

    @api.private
    def _rows(self, path_id=None):
        # The existing policy checks active identity, operating companies, exact
        # user and participant. Company affiliation alone never grants a summary.
        enrollments = (
            self.env["training.document.policy"]
            ._enrollments()
            .filtered(
                lambda e: (
                    e.state == "closed" or (e.state == "confirmed" and e.access_state not in ("suspended", "revoked"))
                )
            )
        )
        if not enrollments:
            return []
        domain = [
            ("enrollment_id", "in", enrollments.ids),
            ("withdrawn_at", "=", False),
            ("path_id.state", "=", "validated"),
        ]
        if path_id is not None:
            domain.append(("path_id", "=", path_id))
        # Narrow read-only projection after the exact personal enrollment check.
        # No privileged records, scores, reasons, files or account IDs leave it.
        references = self.env["training.path.assignment"].sudo().search(domain)
        by_path = {}
        for reference in references:
            by_path.setdefault(reference.path_id.id, {})[reference.step_id.id] = reference
        result = []
        for path in references.path_id.sorted(lambda p: (p.name, p.id)):
            own = by_path[path.id]
            steps = []
            for step in path.step_ids.sorted(lambda s: (s.sequence, s.id)):
                reference = own.get(step.id)
                enrollment = reference.enrollment_id if reference else False
                completed = reference._is_completed() if reference else False
                effective = enrollment._effective_state() if enrollment else False
                blocked = reference._is_blocked() if reference else False
                prerequisites = step.prerequisite_ids
                if path.order_policy == "mandatory":
                    prerequisites |= path.step_ids.filtered(lambda s: s.sequence < step.sequence)
                if completed:
                    status = self.env._("Completed")
                elif enrollment and enrollment.state == "closed":
                    status = self.env._("Closed")
                elif not reference:
                    status = self.env._("Not available")
                elif blocked:
                    status = self.env._("Prerequisites pending")
                else:
                    status = {
                        "active": self.env._("Available"),
                        "scheduled": self.env._("Access starts later"),
                        "expired": self.env._("Access ended"),
                    }.get(effective, self.env._("Access pending"))
                steps.append(
                    {
                        "name": step.program_id.title,
                        "hours": step.program_id.duration_hours,
                        "status": status,
                        "completed": completed,
                        "equivalent": bool(reference and enrollment.program_id != step.program_id),
                        "prerequisites": prerequisites.sorted(lambda s: (s.sequence, s.id)).program_id.mapped("title"),
                        "url": f"/my/trainings/{enrollment.id}" if effective == "active" else False,
                    }
                )
            result.append(
                {
                    "id": path.id,
                    "name": path.name,
                    "hours": path.duration_hours,
                    "mandatory": path.order_policy == "mandatory",
                    "steps": steps,
                    "completed": sum(s["completed"] for s in steps),
                    "total": len(steps),
                }
            )
        return result
