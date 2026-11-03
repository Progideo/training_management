"""Real TM offer integration without the optional historical interactive adapter."""

import os
from pathlib import Path
from run_suite import Database, ROOT, checked


def run(results):
    with Database("j2_obligations", results) as database:

        def command(*args, phase=None):
            command = ["tm_s01_test_p09" if item == "tm_suite_test" else item for item in database.odoo(*args)]
            if phase:
                position = next(i for i, item in enumerate(command) if item.startswith("odoo@"))
                command[position:position] = ["-e", phase]
            return command

        checked(
            command("-i", "training_management_sale,training_management_survey", "--without-demo", "--stop-after-init"),
            results / "install.log",
        )
        with (ROOT / "tests/probes/p09_history.py").open() as probe:
            checked(command("shell", "--no-http", phase="P09_PHASE=baseline"), results / "baseline.log", stdin=probe)
        with (ROOT / "tests/probes/j2_obligations.py").open() as probe:
            checked(command("shell", "--no-http"), results / "prepare.log", stdin=probe)
        checked(
            command("-u", "training_mock_exam,training_management_survey", "--stop-after-init"), results / "update.log"
        )
        with (ROOT / "tests/probes/j2_obligations.py").open() as probe:
            text = checked(command("shell", "--no-http"), results / "preserved.log", stdin=probe)
        if "J2_SHARED_OFFERS_OBLIGATIONS_NATIVE_CONTEXTS_AND_COMPLETION_PRESERVED" not in text:
            raise RuntimeError("Missing obligation preservation proof")


if __name__ == "__main__":
    run(Path(os.environ.get("TM_RESULTS_DIR", ROOT / "test-results/j2-obligations")))
