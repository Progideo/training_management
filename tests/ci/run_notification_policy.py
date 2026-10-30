"""C06 generated identity, staff alerts and recipient revocation; no real transport."""

import tempfile

from run_suite import Database, ROOT, checked


def main():
    folder = ROOT / "test-results/c06-notification-policy"
    core = (
        "TestNotificationAlerts",
        "TestQualityAlerts",
        "TestPreparation",
        "TestLearning",
        "TestDashboard",
        "TestFeedbackAdministration",
        "TestAttendance",
        "TestQuality",
    )
    tags = ["/training_management:" + name for name in core]
    tags += [
        "/training_management_sale:" + name
        for name in ("TestRequestAlerts", "TestPublicRequest", "TestCompanyRequests")
    ]
    with Database("c06_notification_policy", folder) as database:
        checked(
            database.odoo(
                "-i",
                "training_management_sale",
                "--without-demo",
                "--stop-after-init",
                "--test-enable",
                "--test-tags=" + ",".join(tags),
            ),
            folder / "notifications.log",
        )
        source = (
            (ROOT / "deployment/launch_settings.py").read_text()
            + """
from odoo.tests import new_test_user
company=env.ref('base.main_company')
manager=new_test_user(env(context={'no_reset_password':True}),login='fictional_notification_manager',email='manager@example.invalid',groups='training_management.group_training_coordinator')
profile={'database':'tm_suite_test','company_xmlid':'base.main_company','expected_company_name':company.name,'notification_address':'contact@example.invalid','manager_login':manager.login,'manager_alert_address':'alerts@example.invalid'}
before=env['mail.mail'].search_count([])
first=apply_notifications(env,profile)
stamp=company.write_date
assert apply_notifications(env,profile)==first and company.write_date==stamp
assert env['mail.mail'].search_count([])==before
assert company.training_notification_template_id.email_from=='contact@example.invalid'
assert company.training_alert_address=='alerts@example.invalid'
env['res.lang']._activate_lang('fr_FR')
env['ir.module.module']._load_module_terms(['training_management'],['fr_FR'],overwrite=True)
localized=env['training.operator.notice'].new({'company_id':company.id,'role':'manager','recipient_language':'fr_FR','source_model':'training.complaint','source_id':0,'event_key':'translation-check'})
assert localized._content()[0]=='Une action de formation nécessite votre attention'
print('C06_NOTIFICATION_FRENCH_RENDER_OK')
try:
    apply_notifications(env,dict(profile,database='wrong_database'))
except ValueError:
    pass
else:
    raise AssertionError('Wrong database accepted')
env.cr.commit()
print('C06_NOTIFICATION_CONFIG_REPLAY_OK')
"""
        )
        with tempfile.TemporaryFile(mode="w+") as stream:
            stream.write(source)
            stream.seek(0)
            checked(database.odoo("shell", "--no-http"), folder / "configuration-replay.log", stdin=stream)
        checked(
            database.odoo("-u", "training_management,training_management_sale", "--stop-after-init"),
            folder / "second-update.log",
        )
        with (ROOT / "tests/probes/c06_learning_concurrency.py").open() as stream:
            checked(database.odoo("shell", "--no-http"), folder / "learning-concurrency.log", stdin=stream)


if __name__ == "__main__":
    main()
