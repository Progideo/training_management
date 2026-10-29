"""Only the explicit scalar projection may cross the public boundary."""

from odoo import api, models
from odoo.exceptions import AccessError, ValidationError

DOCUMENTS = ("training.publication", "training.publication.event")
FILES = DOCUMENTS + ("training.publication.notice", "training.publication.inspection")


class PublicationPolicy(models.AbstractModel):
    _inherit = "training.document.policy"  # pylint: disable=consider-merging-classes-inherited

    @api.private
    def _document(self, record):
        target = record.sudo()
        if target._name == "ir.attachment" and target.res_model in FILES:
            target = self.env[target.res_model].sudo().browse(target.res_id).exists()
        elif target._name == "mail.message" and target.model in DOCUMENTS:
            target = self.env[target.model].sudo().browse(target.res_id).exists()
        if target._name in FILES:
            if not target:
                raise AccessError(self.env._("This private publication record is unavailable."))
            return target
        return super()._document(record)

    @api.private
    def _is_pedagogical(self, document):
        return bool(document and document._name in FILES) or super()._is_pedagogical(document)

    @api.private
    def _can_read(self, record):
        document = self._document(record)
        if document._name in FILES:
            return bool(self.env.user.active and document.with_env(self.env(su=False)).has_access("read"))
        return super()._can_read(record)

    @api.private
    def _check_send(self, document, partners, **kwargs):
        if document and self._document(document)._name in DOCUMENTS:
            raise ValidationError(self.env._("Publication consent and moderation evidence must remain private."))
        return super()._check_send(document, partners, **kwargs)


class PublicationAttachment(models.Model):
    _inherit = "ir.attachment"  # pylint: disable=consider-merging-classes-inherited

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("res_model", self.env.context.get("default_res_model")) in FILES for v in vals_list):
            raise ValidationError(self.env._("Publication requests do not accept shared attachments."))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("res_model") in FILES or any(a.res_model in FILES for a in self.sudo()):
            raise ValidationError(self.env._("Publication requests do not accept shared attachments."))
        return super().write(vals)
