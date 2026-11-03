"""Install/update the shared package library without either learner application."""

import os
from pathlib import Path

from run_suite import Database, ROOT, assert_tests_ran, checked


def run(results):
    results.mkdir(parents=True, exist_ok=True)
    with Database("j1_interactive", results) as database:

        def command(*args):
            return ["tm_j1i_ci" if item == "tm_suite_test" else item for item in database.odoo(*args)]

        text = checked(
            command(
                "-i",
                "training_interactive",
                "--without-demo",
                "--stop-after-init",
                "--test-enable",
                "--test-tags=/training_interactive",
            ),
            results / "install.log",
        )
        assert_tests_ran(text, ["training_interactive"])
        with (ROOT / "tests/probes/j1_interactive_history.py").open() as probe:
            checked(command("shell", "--no-http"), results / "prepare.log", stdin=probe)
        checked(command("-u", "training_catalog,training_interactive", "--stop-after-init"), results / "update.log")
        with (ROOT / "tests/probes/j1_interactive_history.py").open() as probe:
            text = checked(command("shell", "--no-http"), results / "preserved.log", stdin=probe)
        if (
            "J1_INTERACTIVE_IDENTITIES_VERSIONS_BYTES_AND_WITHDRAWAL_PRESERVED" not in text
            or "J1_INTERACTIVE_WITHOUT_BUSINESS_APPS_CONFIRMED" not in text
        ):
            raise RuntimeError("Missing independent library preservation proof")


if __name__ == "__main__":
    run(Path(os.environ.get("TM_RESULTS_DIR", ROOT / "test-results/j1-interactive")))
