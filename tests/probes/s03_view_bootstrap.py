"""Native view bootstrap for the exact Website visibility loading issue.

Run on a disposable S03 upgrade fixture before -u. The full installed registry
supplies Website's required ir.ui.view defaults. No core code, column default
or SQL constraint is modified. See docs/s03-enrollment-access.md.
"""

from odoo.tools.convert import convert_file

if not env.cr.dbname.startswith("tm_s03_test_"):
    raise RuntimeError("Disposable test databases only")
for module, path in (
    ("training_management", "views/training_delivery_views.xml"),
    ("training_management", "wizard/training_action_reason_views.xml"),
    ("training_management", "wizard/training_enrollment_operation_views.xml"),
    ("training_management_sale", "views/training_allocation_views.xml"),
    ("training_management", "views/training_preparation_views.xml"),
    ("training_management", "views/trainer_portal_templates.xml"),
):
    convert_file(env, module, path, None, mode="update")
# These new views must receive Website's native visibility default from the
# full installed registry. Their actual models/fields do not exist in S04 yet:
# create neutral placeholders, then let the normal module update replace them.
# No application records, column defaults or SQL constraints are changed.
for name, values in (
    (
        "view_training_category_list",
        {"model": "training.course", "type": "list", "arch_db": '<list><field name="name"/></list>'},
    ),
    (
        "view_training_category_form",
        {"model": "training.course", "type": "form", "arch_db": '<form><field name="name"/></form>'},
    ),
    (
        "programme_pdf_document",
        {
            "type": "qweb",
            "key": "training_management.programme_pdf_document",
            "arch_db": '<t t-name="training_management.programme_pdf_document"><div/></t>',
        },
    ),
):
    if not env.ref("training_management." + name, raise_if_not_found=False):
        view = env["ir.ui.view"].create({"name": name, **values})
        env["ir.model.data"].create(
            {"module": "training_management", "name": name, "model": "ir.ui.view", "res_id": view.id, "noupdate": False}
        )
env.cr.commit()
print("S03_NATIVE_VIEW_BOOTSTRAP_OK")
