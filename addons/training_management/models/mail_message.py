"""Private learning uses native messages without inherited author/follower grants."""

from odoo import api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain

from .training_learning import ENTRY_MODEL


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.private
    def _learning_domain(self):
        service = self.env["training.learning.service"]
        participant = self.env["training.document.policy"]._enrollments().filtered(lambda e: service._is_participant(e))
        enrollments = participant | service._tutored_enrollments()
        query = self.env[ENTRY_MODEL].sudo()._search([("enrollment_id", "in", enrollments.ids)])
        return Domain("model", "!=", ENTRY_MODEL) | Domain("res_id", "any!", query)

    def _access_domain(self, operation):
        domain = super()._access_domain(operation)
        if operation == "read":
            domain &= self._learning_domain()
        return domain

    def read(self, fields=None, load="_classic_read"):
        if self and not self.env.su and self.sudo().filtered_domain(self._learning_domain()) != self:
            raise AccessError(self.env._("This private learning record is unavailable."))
        return super().read(fields=fields, load=load)

    def _get_with_access(self, mode="read", **kwargs):
        # Mail controllers can carry sudoed records or an old ownership token.
        if self and self.sudo().filtered_domain(self._learning_domain()) != self:
            return self.browse()
        return super()._get_with_access(mode=mode, **kwargs)

    @api.model_create_multi
    def create(self, vals_list):
        if any((v.get("model") or self.env.context.get("default_model")) == ENTRY_MODEL for v in vals_list):
            raise AccessError(self.env._("Use the private learning form to submit or reply."))
        return super().create(vals_list)

    @api.private
    def _create_learning_message(self, entry, body):
        self.env["training.document.policy"]._check_read(entry)
        clean = {k: v for k, v in self.env.context.items() if not k.startswith("default_")}
        # Native message storage, sanitization, server dates and author identity.
        # Direct creation does not call mail.thread's follower notification path.
        return super(MailMessage, self.sudo().with_context(clean)).create(  # pylint: disable=context-overridden,super-method-mismatch  # checked native message factory, bypass only our public create guard
            {
                "model": ENTRY_MODEL,
                "res_id": entry.id,
                "body": body,
                "subject": False,
                "message_type": "comment",
                "author_id": self.env.user.partner_id.id,
                "partner_ids": [],
                "partner_cc_ids": [],
                "attachment_ids": [],
                "subtype_id": False,
            }
        )

    def write(self, vals):
        if any(message.model == ENTRY_MODEL for message in self.sudo()):
            raise ValidationError(self.env._("Keep private learning messages unchanged."))
        if vals.get("model") == ENTRY_MODEL:
            raise ValidationError(self.env._("A message cannot be reassigned to private learning work."))
        return super().write(vals)

    def copy_data(self, default=None):
        if any(message.model == ENTRY_MODEL for message in self.sudo()):
            raise ValidationError(self.env._("Private learning messages cannot be copied."))
        return super().copy_data(default)

    @api.ondelete(at_uninstall=False)
    def _unlink_keep_learning(self):
        if any(message.model == ENTRY_MODEL for message in self.sudo()):
            raise ValidationError(self.env._("Keep private learning messages unchanged."))

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        if any(message.model == ENTRY_MODEL for message in self.sudo()):
            self.env["training.learning.entry"]._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
        return super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
