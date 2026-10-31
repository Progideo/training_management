"""Small, current-role navigation; destination services remain authoritative."""

from odoo import api, models


class TrainingPortalNavigation(models.AbstractModel):
    _name = "training.portal.navigation"
    _description = "Authorized Training Portal Navigation"

    @api.private
    def _links(self):
        user = self.env.user
        if not user.active or user._is_public():
            return {}
        policy = self.env["training.document.policy"]
        enrollments = policy._enrollments()
        learning = self.env["training.learning.service"]
        tutored = learning._tutored_enrollments()
        active = enrollments.filtered(learning._is_participant)
        documents = (
            self.env["training.document"]
            .sudo()
            .search(
                [
                    ("company_id", "in", user.company_ids.ids),
                    "|",
                    ("dossier_id.enrollment_id.user_id", "=", user.id),
                    ("dossier_id.client_contact_ids", "in", user.partner_id.ids),
                ]
            )
        )
        # Only boolean navigation hints leave these private authorization reads.
        links = {
            "sessions": bool(
                self.env["training.session"]
                .sudo()
                .search_count(
                    [
                        ("instructor_id", "=", user.partner_id.id),
                        ("company_id", "in", user.company_ids.ids),
                        ("delivery_id.state", "in", ("confirmed", "ongoing", "delivered")),
                        ("cancelled", "=", False),
                    ],
                    limit=1,
                )
            ),
            "tutoring": bool(tutored),
            "dashboard": bool(self.env["training.dashboard.service"]._deliveries()),
            "company": bool(self.env["training.company.service"]._grants()),
            "documents": any(policy._can_read(d) for d in documents),
            "paths": bool(self.env["training.path.portal"]._rows()),
            "practice": bool(self.env["training.practice.action"]._portal_actions()),
            "evaluations": bool(
                self.env["training.evaluation.assignment"]
                .sudo()
                .search_count(self.env["training.evaluation.service"]._visible_domain(), limit=1)
            ),
            "complaints": bool(
                self.env["training.enrollment"]
                .sudo()
                .search_count(self.env["training.quality.service"]._enrollment_domain(), limit=1)
            ),
            "publications": bool(
                self.env["training.publication"]
                .sudo()
                .search_count(
                    [
                        ("owner_id", "=", user.id),
                        ("owner_partner_id", "=", user.partner_id.id),
                        ("company_id", "in", user.company_ids.ids),
                    ],
                    limit=1,
                )
            ),
            "bookings": bool(
                self.env["training.tutoring.entitlement"]
                .sudo()
                .search_count(
                    [
                        ("enrollment_id", "in", active.ids),
                    ],
                    limit=1,
                )
                or self.env["training.tutoring.booking"]
                .sudo()
                .search_count(
                    [
                        ("enrollment_id", "in", tutored.ids),
                        ("slot_id.tutor_id", "=", user.id),
                    ],
                    limit=1,
                )
            ),
        }
        return links
