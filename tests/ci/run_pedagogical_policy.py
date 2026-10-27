"""C06 calendar access, reservation defaults, lifecycle and native sales integration."""

from run_suite import Database, ROOT, checked


def main():
    folder = ROOT / "test-results/c06-pedagogy"
    tags = [
        "TestEnrollment",
        "TestReasonPerAction",
        "TestLifecycleAndAccess",
        "TestReservationDeadlineAndUniqueness",
        "TestChangeDates",
        "TestErgonomics",
        "TestPedagogicalLaunch",
    ]
    with Database("c06_pedagogy", folder) as database:
        checked(
            database.odoo(
                "-i",
                "training_management_sale",
                "--without-demo",
                "--stop-after-init",
                "--test-enable",
                "--test-tags="
                + ",".join("/training_management:" + tag for tag in tags)
                + ",/training_management_sale:TestAllocationCommerce",
            ),
            folder / "pedagogy-tests.log",
        )
        profile = {
            "database": "tm_suite_test",
            "company_xmlid": "base.main_company",
            "expected_company_name": "My Company",
            "access_months": 12,
            "reservation_days": 7,
        }
        source = (ROOT / "deployment/launch_settings.py").read_text()
        source += (
            "\nPROFILE=" + repr(profile) + "\nPROFILE['expected_company_name']=env.ref('base.main_company').name\n"
        )
        source += """
assert env.cr.dbname == 'tm_suite_test'
first = apply_pedagogical(env, PROFILE)
second = apply_pedagogical(env, PROFILE)
assert first == second
values = env['training.delivery'].with_company(env.ref('base.main_company')).default_get(['access_policy','access_months','reservation_days'])
assert values == {'access_policy':'months','access_months':12,'reservation_days':7}, values
other = env['res.company'].create({'name':'Fictional Other Operator'})
other_values = env['training.delivery'].with_company(other).default_get(['access_policy','access_months','reservation_days'])
assert other_values['access_policy']=='fixed' and not other_values.get('access_months') and not other_values.get('reservation_days'), other_values
bad = dict(PROFILE, database='never_this_database')
try:
    apply_pedagogical(env,bad)
except ValueError:
    pass
else:
    raise AssertionError('Wrong database accepted')
env.cr.commit()
print('C06_PEDAGOGY_DEFAULTS_REPLAY_OK')
"""
        import tempfile

        with tempfile.TemporaryFile(mode="w+") as stream:
            stream.write(source)
            stream.seek(0)
            checked(database.odoo("shell", "--no-http"), folder / "defaults-replay.log", stdin=stream)
        checked(database.odoo("-u", "training_management", "--stop-after-init"), folder / "second-update.log")


if __name__ == "__main__":
    main()
