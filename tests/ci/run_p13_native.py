"""Reproduce the P13 native coverage evidence in a disposable Calendar database."""

from run_suite import Database, ROOT, checked


if __name__ == "__main__":
    folder = ROOT / "test-results" / "p13-native"
    with Database("p13_native", folder) as database:
        checked(
            database.odoo("-i", "calendar", "--without-demo", "--stop-after-init"),
            folder / "install.log",
        )
        with (ROOT / "tests/probes/p13_native_coverage.py").open() as source:
            output = checked(database.odoo("shell", "--no-http"), folder / "native-coverage.log", stdin=source)
        marker = next(line for line in output.splitlines() if line.startswith("P13_NATIVE_COVERAGE "))
        print(marker)
