"""Native view bootstrap for the exact Website visibility loading issue.

Run on a disposable S03 upgrade fixture before -u. The full installed registry
supplies Website's required ir.ui.view defaults. No core code, column default
or SQL constraint is modified. See docs/s03-enrollment-access.md.
"""
from odoo.tools.convert import convert_file
if not env.cr.dbname.startswith('tm_s03_test_'):
    raise RuntimeError('Disposable test databases only')
for module, path in (
    ('training_management', 'views/training_delivery_views.xml'),
    ('training_management', 'wizard/training_action_reason_views.xml'),
    ('training_management', 'wizard/training_enrollment_operation_views.xml'),
    ('training_management_sale', 'views/training_allocation_views.xml'),
):
    convert_file(env, module, path, None, mode='update')
env.cr.commit()
print('S03_NATIVE_VIEW_BOOTSTRAP_OK')
