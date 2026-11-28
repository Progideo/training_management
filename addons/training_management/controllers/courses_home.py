from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.addons.website.controllers.main import Website
from odoo.http import request

# « My account » cards added by Training Management, shown with the native mechanism.
COUNTERS = {
    "training_course_count": "_has_courses",
    "training_signature_count": "_attends",
}


class TrainingCoursesHome(Website):
    def _login_redirect(self, uid, redirect=None):
        # A portal user with a course lands on « My courses » rather than « My account ».
        if not redirect and not is_user_internal(uid):
            if request.env(user=uid)["training.portal.navigation"]._has_courses():
                redirect = "/my/trainings"
        return super()._login_redirect(uid, redirect=redirect)


class TrainingAccountCards(CustomerPortal):
    def _prepare_portal_counter_values(self, counter):
        navigation = request.env["training.portal.navigation"]
        if counter in COUNTERS:
            shown = getattr(navigation, COUNTERS[counter])()
            return "res.users", [("id", "=", request.env.uid if shown else 0)], "sudo"
        if counter == "training_date_alert_count":
            user = request.env.user
            return (
                "training.session.alert.subscription",
                [("owner_id", "=", user.id), ("owner_partner_id", "=", user.partner_id.id)],
                "sudo",
            )
        return super()._prepare_portal_counter_values(counter)
