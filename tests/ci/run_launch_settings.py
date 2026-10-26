"""Check the actual native localization and launch settings on a disposable database."""

import json
import tempfile

from run_suite import Database, ROOT, checked


def shell(database, folder, name, source):
    with tempfile.TemporaryFile(mode="w+") as stream:
        stream.write(source)
        stream.seek(0)
        return checked(database.odoo("shell", "--no-http"), folder / f"{name}.log", stdin=stream)


def main():
    folder = ROOT / "test-results/launch-settings"
    folder.mkdir(parents=True, exist_ok=True)
    with Database("launch_settings", folder) as database:
        checked(database.odoo("-i", "sale_management", "--without-demo", "--stop-after-init"), folder / "bootstrap.log")
        shell(
            database,
            folder,
            "identity",
            """
company = env.ref('base.main_company')
assert not env['account.move'].search_count([])
company.write({'name': 'Fictional Training Company', 'country_id': env.ref('base.ma').id})
env['ir.cron'].search([]).write({'active': False})
env['ir.mail_server'].search([]).write({'active': False})
env.cr.commit()
""",
        )
        checked(database.odoo("-i", "l10n_ma", "--without-demo", "--stop-after-init"), folder / "localization.log")
        profile = json.loads((ROOT / "deployment/launch-settings.example.json").read_text())
        profile["database"] = "tm_suite_test"
        source = "import json\nPROFILE=json.loads(" + repr(json.dumps(profile)) + ")\n"
        source += (ROOT / "deployment/launch_settings.py").read_text() + "\n"
        source += (ROOT / "tests/probes/launch_configuration.py").read_text()
        for phase in ("application", "replay"):
            text = shell(database, folder, phase, source)
            if "LAUNCH_SETTINGS_NATIVE_SMOKE_OK" not in text:
                raise RuntimeError("Missing native launch proof")
        (folder / "success.json").write_text(json.dumps({"localization": "l10n_ma", "application_and_replay": True}))


if __name__ == "__main__":
    main()
