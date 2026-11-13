"""J1: a shared catalogue without business apps, then TM on a separate fresh database."""

import os
from pathlib import Path

from run_suite import Database, ROOT, assert_tests_ran, checked


def run(results):
    for mode, addons in [("catalog", ["training_catalog"]), ("tm", ["training_catalog", "training_management"])]:
        folder = results / mode
        folder.mkdir(parents=True, exist_ok=True)
        with Database("j1_" + mode, folder) as database:

            def command(*args):
                # The shared fixture explicitly rejects non-J1 database names.
                return ["tm_j1_ci" if part == "tm_suite_test" else part for part in database.odoo(*args)]

            tags = (
                "/training_catalog"
                if mode == "catalog"
                else (
                    "/training_catalog,/training_management:TestCatalogue,"
                    "/training_management:TestAttendanceSignatures,/training_management:TestCertificateVerification"
                )
            )
            text = checked(
                command(
                    "-i",
                    ",".join(addons),
                    "--without-demo",
                    "--stop-after-init",
                    "--test-enable",
                    "--test-tags=" + tags,
                ),
                folder / "install.log",
            )
            assert_tests_ran(text, addons)
            with (ROOT / "tests/probes/j1_catalog_history.py").open() as probe:
                checked(command("shell", "--no-http"), folder / "prepare.log", stdin=probe)
            checked(command("-u", ",".join(addons), "--stop-after-init"), folder / "update.log")
            with (ROOT / "tests/probes/j1_catalog_history.py").open() as probe:
                text = checked(command("shell", "--no-http"), folder / "preserved.log", stdin=probe)
            if "J1_IDENTITIES_TEXT_AND_RELATIONS_PRESERVED" not in text:
                raise RuntimeError("Missing J1 preservation proof")


def native_contracts(results):
    folder = results / "native"
    folder.mkdir(parents=True, exist_ok=True)
    with Database("j1_native", folder) as database:

        def command(*args):
            return ["tm_j1_native" if part == "tm_suite_test" else part for part in database.odoo(*args)]

        checked(
            command("-i", "training_catalog,website_slides_survey", "--without-demo", "--stop-after-init"),
            folder / "install.log",
        )
        with (ROOT / "tests/probes/j1_native_contracts.py").open() as probe:
            text = checked(command("shell", "--no-http"), folder / "contracts.log", stdin=probe)
        if "J1_NATIVE_CONTRACTS_OK_NOT_TARGET_ACCESS_OR_OPTIONALITY_PROOF" not in text:
            raise RuntimeError("Missing native contracts proof")


if __name__ == "__main__":
    results = Path(os.environ.get("TM_RESULTS_DIR", ROOT / "test-results/j1"))
    run(results)
    native_contracts(results)
