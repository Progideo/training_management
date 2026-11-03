"""Install and update native mock definitions without either business application."""

import os
from pathlib import Path

from run_suite import Database, ROOT, assert_tests_ran, checked


def run(results):
    with Database("j1_mock_exam", results) as database:

        def command(*args):
            return ["tm_j1m_ci" if item == "tm_suite_test" else item for item in database.odoo(*args)]

        text = checked(
            command(
                "-i",
                "training_mock_exam",
                "--without-demo",
                "--stop-after-init",
                "--test-enable",
                "--test-tags=/training_mock_exam",
            ),
            results / "install.log",
        )
        assert_tests_ran(text, ["training_mock_exam"])
        for phase in ("prepare", "preserved"):
            if phase == "preserved":
                checked(
                    command("-u", "training_catalog,training_mock_exam", "--stop-after-init"), results / "update.log"
                )
            with (ROOT / "tests/probes/j1_mock_exam_history.py").open() as probe:
                text = checked(command("shell", "--no-http"), results / (phase + ".log"), stdin=probe)
            if "J1_MOCK_WITHOUT_BUSINESS_APPS_CONFIRMED" not in text:
                raise RuntimeError("Missing independent mock library proof")
        if "J1_MOCK_NATIVE_DEFINITIONS_AND_CORRECTIONS_PRESERVED" not in text:
            raise RuntimeError("Missing native mock history proof")


if __name__ == "__main__":
    run(Path(os.environ.get("TM_RESULTS_DIR", ROOT / "test-results/j1-mock-exam")))
