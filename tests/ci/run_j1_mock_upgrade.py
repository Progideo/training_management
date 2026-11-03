"""The exact preceding J1 generation upgrades without rewriting native exam evidence."""

import os
from pathlib import Path
import subprocess
import tempfile

from run_suite import Database, ROOT, checked

BASELINE = "39ad822c0a2af808cef99a32b41218fab1281308"


def run(results):
    with tempfile.TemporaryDirectory() as archived, Database("j1_mock_upgrade", results) as database:
        archive = Path(archived) / "baseline.tar"
        with archive.open("wb") as output:
            subprocess.run(["git", "archive", BASELINE, "addons"], cwd=ROOT, stdout=output, check=True)
        subprocess.run(["tar", "-xf", str(archive), "-C", archived], check=True)

        def command(*args, baseline=False, phase=None):
            command = ["tm_s01_test_p09" if item == "tm_suite_test" else item for item in database.odoo(*args)]
            if baseline:
                command = [item.replace(str(ROOT / "addons"), str(Path(archived) / "addons")) for item in command]
            if phase:
                position = next(i for i, item in enumerate(command) if item.startswith("odoo@"))
                command[position:position] = ["-e", phase]
            return command

        checked(
            command(
                "-i",
                "training_management_sale,training_management_survey",
                "--without-demo",
                "--stop-after-init",
                baseline=True,
            ),
            results / "baseline.log",
        )
        with (ROOT / "tests/probes/p09_history.py").open() as probe:
            checked(
                command("shell", "--no-http", baseline=True, phase="P09_PHASE=baseline"),
                results / "grant.log",
                stdin=probe,
            )
        with (ROOT / "tests/probes/j1_mock_tm_history.py").open() as probe:
            checked(
                command("shell", "--no-http", baseline=True, phase="J1_RUNTIME_PHASE=prepare"),
                results / "prepare.log",
                stdin=probe,
            )
        checked(
            command(
                "-u",
                "training_mock_exam,training_management,training_management_sale,training_management_survey",
                "--stop-after-init",
            ),
            results / "update.log",
        )
        with (ROOT / "tests/probes/j1_mock_tm_history.py").open() as probe:
            text = checked(
                command("shell", "--no-http", phase="J1_RUNTIME_PHASE=verify"), results / "preserved.log", stdin=probe
            )
        if "J1_TM_NATIVE_ATTEMPTS_REVIEWS_DEADLINES_SCORES_REVISIONS_AND_RESUME_PRESERVED" not in text:
            raise RuntimeError("Missing same-generation evidence preservation")


if __name__ == "__main__":
    run(Path(os.environ.get("TM_RESULTS_DIR", ROOT / "test-results/j1-mock-upgrade")))
