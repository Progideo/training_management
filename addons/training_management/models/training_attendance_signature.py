"""Private reusable drawings; every use remains a separate attendance event."""

import base64
import binascii
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from psycopg2.errors import UniqueViolation

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.binary import BinaryBytes


class AttendanceSignature(models.Model):
    _name = "training.attendance.signature"
    _description = "Private Personal Attendance Signature"

    # Deliberately no ACL: only the private service can read or change a profile.
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    drawing = fields.Binary(attachment=False, copy=False)
    version = fields.Integer(default=0, required=True)
    use_revision = fields.Integer(default=0, required=True)
    _one_owner = models.Constraint("UNIQUE(user_id)", "One personal signature per user.")

    def _can_return_content(self, field_name=None, access_token=None):
        return False

    @api.private
    def _current(self, lock=False):
        user = self.env.user
        if not user.active or user._is_public():
            raise AccessError(self.env._("Sign in with your own active account."))
        if lock:
            # Serializes first creation, replacement, deletion and use. Attendance
            # operations lock their delivery before this user; editing locks only user.
            self.env.cr.execute("SELECT id FROM res_users WHERE id = %s FOR UPDATE", [user.id])
        record = self.sudo().with_context(bin_size=False).search([("user_id", "=", user.id)], limit=1)
        if lock and not record:
            try:
                with self.env.cr.savepoint():
                    # Clear defaults so a first-use request cannot select another owner.
                    record = self.sudo().with_context({}).create({"user_id": user.id})  # pylint: disable=context-overridden  # private factory
            except UniqueViolation as error:
                raise ValidationError(self.env._("Your signature changed. Reload before confirming.")) from error
        if lock:
            record.lock_for_update()
        record.invalidate_recordset()
        if lock:
            # A lock alone cannot refresh a REPEATABLE READ snapshot. A write
            # fence on the private profile forces stale transactions to retry.
            record.write({"use_revision": record.use_revision + 1})
        return record

    @api.private
    def _save_drawing(self, drawing, version):
        record = self._current(lock=True)
        if str(record.version or 0) != str(version):
            raise ValidationError(self.env._("Your signature changed. Reload before confirming."))
        normalized = False
        if drawing:
            try:
                if not isinstance(drawing, str) or len(drawing) > 700000:
                    raise ValueError
                raw = base64.b64decode(drawing, validate=True)
                with Image.open(BytesIO(raw)) as image:
                    if image.format != "PNG" or not (1 <= image.width <= 2000 and 1 <= image.height <= 1000):
                        raise ValueError
                    image.load()
                    image = image.convert("RGBA")
                    # Reject a completely blank canvas; normalize to a safe PNG.
                    background = Image.new("RGBA", image.size, "white")
                    background.alpha_composite(image)
                    if background.convert("L").getextrema()[0] >= 250:
                        raise ValueError
                    output = BytesIO()
                    image.save(output, format="PNG")
                    normalized = BinaryBytes(output.getvalue())
            except (ValueError, binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
                raise ValidationError(
                    self.env._("Use a non-empty PNG signature, at most 2000 × 1000 pixels.")
                ) from error
        values = {"drawing": normalized, "version": (record.version or 0) + 1}
        record.write(values)

    @api.private
    def _snapshot(self, version):
        record = self._current(lock=True)
        if not record.drawing or str(record.version) != str(version):
            raise ValidationError(self.env._("Save your signature, then reload and confirm the displayed signature."))
        return {
            "signature": record.drawing,
            "signature_version": record.version,
            "signature_digest": record.drawing.checksum,
        }


class AttendanceSignedEvent(models.Model):
    _inherit = "training.attendance.event"

    signature = fields.Binary(attachment=False, readonly=True, copy=False)
    signature_version = fields.Integer(readonly=True)
    signature_digest = fields.Char(readonly=True)

    # The inherited native streaming policy only permits the existing data
    # field to coordinators. Drawings use the freshly authorized custom route.


class AttendanceSigning(models.AbstractModel):
    _inherit = "training.attendance.service"

    @api.private
    def _sign_halfday(self, enrollment_id, key, *, signature_version, **values):
        with self.env.cr.savepoint():
            self.env["training.learning.service"]._enrollment(enrollment_id, lock=True)
            snapshot = self.env["training.attendance.signature"]._snapshot(signature_version)
            return self._declare_halfday(enrollment_id, key, signature=snapshot, **values)

    @api.private
    def _sign_review(self, session_id, enrollment_id, start, end, *, signature_version, **values):
        with self.env.cr.savepoint():
            self._session(session_id, lock=True)
            snapshot = self.env["training.attendance.signature"]._snapshot(signature_version)
            return self._review(session_id, enrollment_id, start, end, signature=snapshot, **values)
