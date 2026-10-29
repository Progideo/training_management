"""Reproduce P14 native Rating coverage in an isolated synthetic database."""

from run_suite import Database, ROOT, checked


if __name__ == "__main__":
    folder = ROOT / "test-results" / "p14-native"
    with Database("p14_native", folder) as database:
        checked(
            database.odoo("-i", "portal_rating", "--without-demo", "--stop-after-init"),
            folder / "install.log",
        )
        with (ROOT / "tests/probes/p14_native_coverage.py").open() as source:
            output = checked(database.odoo("shell", "--no-http"), folder / "native-coverage.log", stdin=source)
        for line in output.splitlines():
            if line.startswith("P14_NATIVE_"):
                print(line)
