# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools.binary import BinaryBytes
from ..services.archive import parse_package

AUTHOR = "training_interactive.group_interactive_author"
MANAGER = "training_interactive.group_interactive_manager"
PROTECTED = ("training.elearning.file", "training.elearning.version", "training.elearning.import")


class Version(models.Model):
    _name = "training.elearning.version"
    _description = "Interactive Content Version"
    _check_company_auto = True
    _rec_name = "number"
    resource_id = fields.Many2one("training.elearning.resource", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="resource_id.company_id", store=True)
    number = fields.Char(required=True)
    sha256 = fields.Char(required=True, readonly=True)
    entrypoint = fields.Char(required=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published"), ("withdrawn", "Withdrawn")],
        default="draft",
        required=True,
        readonly=True,
    )
    published_at = fields.Datetime(readonly=True)
    published_by_id = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    withdrawn_at = fields.Datetime(readonly=True)
    withdrawn_by_id = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    withdrawal_reason = fields.Text(readonly=True)
    license_note = fields.Char(required=True, readonly=True)
    provenance = fields.Text(required=True, readonly=True)
    file_ids = fields.One2many("training.elearning.file", "version_id", groups="base.group_system")
    _number_unique = models.Constraint("UNIQUE(resource_id,number)", "This version already exists.")

    @api.depends("resource_id.name", "number")
    def _compute_display_name(self):
        for version in self:
            version.display_name = "%s / v%s" % (version.resource_id.name, version.number)

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # controlled private import only
        raise AccessError(self.env._("Use the controlled package import."))

    @api.private
    def _import_error_message(self, message):
        """Translate known parser failures without exposing unexpected exception text."""
        messages = {
            "Unsafe package path": self.env._("Unsafe package path"),
            "JSON metadata too large": self.env._("JSON metadata too large"),
            "JSON object required": self.env._("JSON object required"),
            "Invalid H5P dependency": self.env._("Invalid H5P dependency"),
            "Invalid H5P library identity": self.env._("Invalid H5P library identity"),
            "Invalid H5P runtime dependencies": self.env._("Invalid H5P runtime dependencies"),
            "Only H5P TrueFalse 1.8 is qualified": self.env._("Only H5P TrueFalse 1.8 is qualified"),
            "H5P library identity mismatch": self.env._("H5P library identity mismatch"),
            "Missing H5P main runtime": self.env._("Missing H5P main runtime"),
            "Invalid H5P assets": self.env._("Invalid H5P assets"),
            "Invalid H5P asset": self.env._("Invalid H5P asset"),
            "Missing H5P runtime asset": self.env._("Missing H5P runtime asset"),
            "Invalid H5P dependencies": self.env._("Invalid H5P dependencies"),
            "Incomplete H5P runtime dependency list": self.env._("Incomplete H5P runtime dependency list"),
            "Cyclic H5P dependencies": self.env._("Cyclic H5P dependencies"),
            "Invalid TrueFalse content": self.env._("Invalid TrueFalse content"),
            "Unsupported or oversized archive": self.env._("Unsupported or oversized archive"),
            "Archive limits exceeded": self.env._("Archive limits exceeded"),
            "Unsafe or excessive archive entry": self.env._("Unsafe or excessive archive entry"),
            "Nested archives are not supported": self.env._("Nested archives are not supported"),
            "Les vidéos privées ne sont pas prises en charge dans les paquets interactifs.": self.env._(
                "Les vidéos privées ne sont pas prises en charge dans les paquets interactifs."
            ),
            "Invalid entry size": self.env._("Invalid entry size"),
            "Unsafe manifest": self.env._("Unsafe manifest"),
            "Only SCORM 1.2 single SCO is supported": self.env._("Only SCORM 1.2 single SCO is supported"),
            "A SCO resource is required": self.env._("A SCO resource is required"),
            "Missing local HTML entry point": self.env._("Missing local HTML entry point"),
            "Missing manifest file": self.env._("Missing manifest file"),
            "Invalid package archive or manifest": self.env._("Invalid package archive or manifest"),
        }
        return messages.get(message, self.env._("The interactive package could not be imported."))

    @api.private
    def _import(self, resource, number, raw, license_note, provenance):
        resource = resource.with_env(self.env)
        resource.ensure_one()
        resource.check_access("write")
        resource.lock_for_update()
        resource.invalidate_recordset()
        if not self.env.user.active or not (self.env.user.has_group(AUTHOR) or self.env.user.has_group(MANAGER)):
            raise AccessError(self.env._("Content author permission required."))
        if not resource.active or not number.strip() or not license_note.strip() or not provenance.strip():
            raise ValidationError(self.env._("Specify version, license and provenance for an active resource."))
        try:
            result = parse_package(raw, resource.format)
        except ValueError as error:
            raise ValidationError(self._import_error_message(str(error))) from error
        with self.env.cr.savepoint():
            version = super(Version, self.with_context({})).create(  # pylint: disable=super-method-mismatch,context-overridden  # checked import; discard RPC defaults
                {
                    "resource_id": resource.id,
                    "number": number,
                    "sha256": result["sha256"],
                    "entrypoint": result["entrypoint"],
                    "license_note": license_note,
                    "provenance": provenance,
                }
            )
            self.env["training.elearning.file"]._insert(
                [
                    {"version_id": version.id, "path": path, "data": BinaryBytes(data)}
                    for path, data in result["files"].items()
                ]
            )
            return version

    def write(self, values):  # pylint: disable=method-required-super  # published bytes and version history are immutable
        raise ValidationError(self.env._("Import a new version; preserve existing content."))

    @api.ondelete(at_uninstall=False)
    def _keep_history(self):
        raise ValidationError(self.env._("Keep content versions and their history."))

    def action_publish(self):
        self.check_access("write")
        if not self.env.user.active or not (self.env.su or self.env.user.has_group(AUTHOR)):
            raise AccessError(self.env._("Content author permission required."))
        self.resource_id.lock_for_update()
        self.resource_id.invalidate_recordset()
        self.lock_for_update()
        self.invalidate_recordset()
        if any(v.state != "draft" or not v.resource_id.active for v in self):
            raise ValidationError(self.env._("Publish a draft of an active resource."))
        return super().write(  # pylint: disable=super-method-mismatch  # checked lifecycle transition
            {"state": "published", "published_at": fields.Datetime.now(), "published_by_id": self.env.uid}
        )

    @api.private
    def _withdraw(self, reason):
        self.check_access("write")
        if not self.env.user.active or not (self.env.su or self.env.user.has_group(MANAGER)) or not reason.strip():
            raise AccessError(self.env._("Library manager permission and a reason are required."))
        self.lock_for_update()
        self.invalidate_recordset()
        if any(version.state == "withdrawn" for version in self):
            raise ValidationError(self.env._("The original withdrawal decision must be preserved."))
        with self.env.cr.savepoint():
            result = super().write(  # pylint: disable=super-method-mismatch
                {
                    "state": "withdrawn",
                    "withdrawal_reason": reason.strip(),
                    "withdrawn_at": fields.Datetime.now(),
                    "withdrawn_by_id": self.env.uid,
                }
            )
            self._withdraw_consumers(reason.strip())
            return result

    @api.private
    def _withdraw_consumers(self, reason):
        """Consuming applications notify their own contexts without library dependencies."""
        return True

    def action_preview(self):
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.act_url", "url": "/training/interactive/preview/%s" % self.id, "target": "new"}


class PackageFile(models.Model):
    _name = "training.elearning.file"
    _description = "Private Interactive Content File"
    version_id = fields.Many2one("training.elearning.version", required=True, ondelete="restrict")
    path = fields.Char(required=True)
    data = fields.Binary(required=True, attachment=False, groups="base.group_system")
    _path_unique = models.Constraint("UNIQUE(version_id,path)", "Unique package path required.")

    @api.model_create_multi
    def create(self, vals_list):  # pylint: disable=method-required-super  # controlled private import only
        raise AccessError(self.env._("Use the controlled package import."))

    @api.private
    def _insert(self, values):
        # Private helper, called only after authorized parsing in _import.
        return super(PackageFile, self.sudo().with_context({})).create(values)  # pylint: disable=super-method-mismatch,context-overridden  # checked import; discard RPC defaults

    def write(self, values):  # pylint: disable=method-required-super  # published bytes and version history are immutable
        raise AccessError(self.env._("Package files are immutable."))

    @api.ondelete(at_uninstall=False)
    def _keep_files(self):
        raise AccessError(self.env._("Keep historical package files."))


class Binary(models.AbstractModel):
    _inherit = "ir.binary"

    def _record_to_stream(self, record, field_name):
        if record._name in PROTECTED or (record._name == "ir.attachment" and record.sudo().res_model in PROTECTED):
            raise AccessError(self.env._("Interactive packages require the isolated content origin."))
        return super()._record_to_stream(record, field_name)


class Attachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def _access_domain(self, operation):
        domain = super()._access_domain(operation)
        if operation == "read":
            # Public attachment metadata must not grant ORM access to package bytes.
            domain &= ~Domain("res_model", "in", PROTECTED)
        return domain

    def _to_http_stream(self):
        if any(a.sudo().res_model in PROTECTED for a in self):
            raise AccessError(self.env._("Interactive packages require the isolated content origin."))
        return super()._to_http_stream()
