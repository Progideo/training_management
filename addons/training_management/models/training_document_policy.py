"""Current pedagogical grants; commercial integration extends this private service."""

from odoo import SUPERUSER_ID, api, models
from odoo.exceptions import AccessError, ValidationError

PEDAGOGICAL = (
    "training.material",
    "training.program.version",
    "training.learning.entry",
    "training.attendance.event",
    "training.attendance.edit",
)


class TrainingDocumentPolicy(models.AbstractModel):
    _name = "training.document.policy"
    _description = "Training Document Authorization"

    @api.private
    def _document(self, record):
        record.ensure_one()
        target = record.sudo()
        if target._name == "ir.attachment":
            if target.training_program_id:
                return target.training_program_id
            if (
                target.res_model
                not in (
                    "training.material",
                    "training.learning.entry",
                    "training.attendance.event",
                    "training.attendance.edit",
                )
                or not target.res_id
            ):
                return self.env["training.material"]
            target = self.env[target.res_model].sudo().browse(target.res_id).exists()
            if not target:
                raise AccessError(self.env._("This private learning record is unavailable."))
        elif (
            target._name == "mail.message"
            and target.model in ("training.material", "training.learning.entry")
            and target.res_id
        ):
            target = self.env[target.model].sudo().browse(target.res_id).exists()
            if not target:
                raise AccessError(self.env._("This private learning record is unavailable."))
        return target if target._name in PEDAGOGICAL else self.env["training.material"]

    @api.private
    def _is_pedagogical(self, document):
        return bool(document) and document._name in PEDAGOGICAL

    @api.private
    def _restricted(self, document):
        return self._is_pedagogical(document)

    @api.private
    def _delivery_domain(self):
        user = self.env.user
        return [("company_id", "in", user.company_ids.ids)]

    @api.private
    def _enrollments(self):
        user = self.env.user
        if user._is_public() or not user.active:
            return self.env["training.enrollment"]
        # Only authorization metadata is elevated; callers receive no arbitrary
        # enrollment record through RPC and portal templates get plain values.
        return (
            self.env["training.enrollment"]
            .sudo()
            .search(self._delivery_domain() + [("user_id", "=", user.id), ("participant_id", "=", user.partner_id.id)])
        )

    @api.private
    def _can_access_delivery(self, delivery):
        user = self.env.user
        if user._is_public() or not user.active or delivery.company_id not in user.company_ids:
            return False
        if any(e.delivery_id == delivery and e._effective_state() == "active" for e in self._enrollments()):
            return True
        if any(e.delivery_id == delivery for e in self.env["training.learning.service"]._tutored_enrollments()):
            return True
        # Same exact session assignment and lifecycle as the S04 trainer portal.
        return bool(
            self.env["training.session"]
            .sudo()
            .search_count(
                self._delivery_domain()
                + [
                    ("delivery_id", "=", delivery.id),
                    ("instructor_id", "=", user.partner_id.id),
                    ("delivery_id.state", "in", ("confirmed", "ongoing")),
                    ("cancelled", "=", False),
                ],
                limit=1,
            )
        )

    @api.private
    def _can_read(self, record):
        document = self._document(record)
        if not self._restricted(document):
            return True
        if (self.env.uid != SUPERUSER_ID and not self.env.user.active) or self.env.user._is_public():
            return False
        if document._name == "training.learning.entry":
            service = self.env["training.learning.service"]
            enrollment = document.sudo().enrollment_id
            return service._is_participant(enrollment) or service._is_tutor(enrollment)
        native = document.with_env(self.env(su=False))
        if document._name in ("training.attendance.event", "training.attendance.edit"):
            return native.has_access("read")
        if document._name == "training.program.version":
            if native.has_access("read"):
                return True
            deliveries = (
                self.env["training.delivery"]
                .sudo()
                .search(self._delivery_domain() + [("program_id", "=", document.id)])
            )
            return any(self._can_access_delivery(delivery) for delivery in deliveries)
        # Only coordinators get internal library access; catalogue, Sales and
        # Accounting roles never inherit this grant. Even native sudo/token
        # resolution is reset to the actual user for this decision.
        if native.has_access("read"):
            return True
        material = document.sudo()
        if material.withdrawn or not material.frozen_at:
            return False
        return any(not ref.withdrawn and self._can_access_delivery(ref.delivery_id) for ref in material.assignment_ids)

    @api.private
    def _check_read(self, record):
        if not self._can_read(record):
            raise AccessError(self.env._("This training document is not accessible with your current permissions."))

    @api.private
    def _check_send(self, document, partners, *, email_to=False, email_cc=False, required=True, allow_internal=False):
        if document and document._name in (
            "training.material",
            "training.learning.entry",
            "training.attendance.event",
            "training.attendance.edit",
        ):
            # S05 distributes through the authenticated portal only. Do not send
            # the private file, even on an unrelated envelope or to a follower.
            raise ValidationError(
                self.env._("Private training PDFs are available through the authenticated portal only.")
            )
