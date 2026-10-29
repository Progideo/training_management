"""Reproduce native P16 coverage in an isolated synthetic database."""

from run_suite import Database, ROOT, checked


if __name__ == "__main__":
    folder = ROOT / "test-results" / "p16-native"
    with Database("p16_native", folder) as database:
        checked(
            database.odoo("-i", "website_event,mass_mailing", "--without-demo", "--stop-after-init"),
            folder / "install.log",
        )
        with (ROOT / "tests/probes/p16_native_coverage.py").open() as source:
            output = checked(database.odoo("shell", "--no-http"), folder / "native-coverage.log", stdin=source)
        for line in output.splitlines():
            if line.startswith("P16_NATIVE_"):
                print(line)
