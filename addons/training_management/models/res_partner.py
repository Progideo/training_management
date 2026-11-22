from odoo import models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import email_normalize

# Native records whose contact must stay as it is: their own tools decide.
NATIVE_DOCUMENTS = ("account.move", "sale.order", "crm.lead")
CONTACT_FIELDS = ("email", "phone", "street", "street2", "city", "zip", "vat", "website", "comment", "function")


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_training_anonymize_participant(self):
        """Anonymize a participant used only for training (conservation configurée, 22 November 2026).

        Every training dossier of the contact is anonymized, then the contact itself is
        renamed and archived. A contact with a user or native documents is refused: its
        login or documents keep personal data that their own tools decide on.
        """
        if not self.env.user._is_system():
            raise AccessError(self.env._("Only an administrator can anonymize a participant."))
        env = self.sudo().with_context(active_test=False).env
        for partner in self.sudo().with_context(active_test=False):
            if partner.user_ids:
                raise ValidationError(
                    self.env._("Delete the user of %(name)s first: its login keeps personal data.", name=partner.name)
                )
            for model in NATIVE_DOCUMENTS:
                if model in env and env[model].search_count([("partner_id", "=", partner.id)], limit=1):
                    raise ValidationError(
                        self.env._(
                            "%(name)s has native documents (%(model)s): anonymize them with their own tools first.",
                            name=partner.name,
                            model=env[model]._description,
                        )
                    )
            enrollments = env["training.enrollment"].search(
                [("participant_id", "=", partner.id), ("anonymized_at", "=", False)]
            )
            enrollments.with_user(self.env.user).action_training_anonymize_dossier()
            email = email_normalize(partner.email or "")
            if email:
                subscriptions = env["training.session.alert.subscription"].search([("email", "=", email)])
                notices = env["training.session.alert.notice"].search([("subscription_id", "in", subscriptions.ids)])
                env["training.dossier.deletion"]._training_clear_personal([subscriptions, notices])
            values = {name: False for name in CONTACT_FIELDS if name in partner._fields}
            partner.write(
                {
                    **values,
                    "name": self.env._("Anonymized participant %(id)s", id=partner.id),
                    "image_1920": False,
                    "active": False,
                }
            )
        return True
