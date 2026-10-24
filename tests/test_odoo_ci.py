"""Coverage conservation, isolated orchestration and fail-closed CI evidence."""

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/ci"))
import run_suite as runner  # noqa: E402
import check_results as gate  # noqa: E402

PLAN = runner.PLAN

FAKE_DOCKER = r"""#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
file=Path(os.environ['CI_DOCKER_TRACE'])
data=sys.stdin.buffer.read().decode() if 'shell' in args else ''
with file.open('a') as stream:stream.write(json.dumps({'args':args,'stdin':data})+'\n')
if args[0]=='inspect': print('healthy');sys.exit(0)
if args[:2]==['volume','inspect']:sys.exit(1)
if os.environ.get('CI_FAIL_PATTERN') and any(os.environ['CI_FAIL_PATTERN'] in a for a in args):sys.exit(42)
print('Synthetic Docker orchestration evidence (no Odoo executed)')
if '--test-enable' in args:
 print('0 failed, 0 error(s) of 12 tests')
 for arg in args:
  if arg.startswith('--test-tags='):
   for addon in arg.split('=',1)[1].split(','): print('odoo.tests.stats: '+addon.lstrip('/')+': 12 tests')
if 'CUMULATIVE_FRENCH_WEBSITE_READY' in data: print('CUMULATIVE_FRENCH_WEBSITE_READY')
"""


def original(path):
    return subprocess.check_output(["git", "show", PLAN["source_commit"] + ":" + path], cwd=ROOT, text=True)


def normalize_migration(text):
    # Only redundant addon suite launches move. Every installation/update, probe,
    # historical revision and phase on a persisted database remains unchanged.
    text = (
        "\n".join(
            line
            for line in text.splitlines()
            if not re.search(r"\bstep (fresh|core_without_survey|french_prepare|french_http) run_odoo\b", line)
        )
        + "\n"
    )
    text = re.sub(r" --test-enable| --test-tags=[^\s\\]+", "", text)
    return (
        text.replace("real Odoo tests and concurrent reservations", "migration and concurrent reservations").rstrip()
        + "\n"
    )


class Coverage(unittest.TestCase):
    def test_every_migration_operation_and_probe_is_preserved(self):
        for path in sorted({entry["script"] for entry in PLAN["migrations"]}):
            with self.subTest(path=path):
                self.assertEqual((ROOT / path).read_text(), normalize_migration(original(path)))
        for path in (ROOT / "tests/probes").glob("*.py"):
            self.assertEqual(path.read_text(), original(str(path.relative_to(ROOT))))
        self.assertEqual(len(PLAN["migrations"]), 16)

    def test_migration_phases_match_historical_contracts_except_relocated_tests(self):
        base = json.loads((ROOT / "tests/ci/coverage.json").read_text())["scenarios"]
        specialized = json.loads((ROOT / "tests/ci/workflow_coverage.json").read_text())
        specialized = {**specialized["jobs"], **specialized.get("extensions", {})}
        self.assertEqual({entry["id"] for entry in PLAN["migrations"][:4]}, set(base))
        for entry in PLAN["migrations"]:
            if entry["id"] in base:
                expected = [step["step"] for step in base[entry["id"]]]
            else:
                contract = next(item for item in specialized.values() if item["script"] == entry["script"])
                expected = [step for step in contract["steps"] if step not in PLAN["relocated_steps"]]
            self.assertEqual(entry["steps"], expected)

    def test_all_addon_test_modules_are_imported_and_existing_tests_retained(self):
        # New files must be imported by Odoo; a broad selector alone cannot discover unimported files.
        for tests in (ROOT / "addons").glob("training_management*/tests"):
            tree = ast.parse((tests / "__init__.py").read_text())
            imported = {alias.name for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names}
            for file in tests.glob("test_*.py"):
                self.assertIn(file.stem, imported)
                baseline = ast.parse(original(str(file.relative_to(ROOT))))
                current = ast.parse(file.read_text())

                def methods(tree):
                    return {
                        (node.name, method.name)
                        for node in tree.body
                        if isinstance(node, ast.ClassDef)
                        for method in node.body
                        if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")
                    }

                self.assertTrue(methods(baseline) <= methods(current))

    def test_only_configuration_matrix_and_common_verdict(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/odoo.yml").read_text())
        jobs = workflow["jobs"]
        self.assertEqual(set(jobs), {*gate.REQUIRED_JOBS, "validation"})
        matrix = jobs["suite"]["strategy"]
        self.assertFalse(matrix["fail-fast"])
        self.assertEqual({item["configuration"] for item in matrix["matrix"]["include"]}, set(PLAN["configurations"]))
        for name, job in jobs.items():
            if name != "suite":
                self.assertNotIn("strategy", job)
            self.assertNotIn("continue-on-error", job)
        self.assertEqual(set(jobs["validation"]["needs"]), gate.REQUIRED_JOBS)
        self.assertEqual(jobs["validation"]["if"], "${{ always() }}")
        self.assertEqual(jobs["validation"]["name"], "Validation CI Odoo")
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(len(matrix["matrix"]["include"]), 6)


class Orchestration(unittest.TestCase):
    def run_plan(self, name, fail_pattern=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        docker = folder / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        trace = folder / "trace.jsonl"
        env = {
            **os.environ,
            "PATH": str(folder) + os.pathsep + os.environ["PATH"],
            "CI_DOCKER_TRACE": str(trace),
            "TM_CI_ID": "contract",
            "TM_RESULTS_DIR": str(folder / "results"),
        }
        if fail_pattern:
            env["CI_FAIL_PATTERN"] = fail_pattern
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/ci/run_suite.py"), name], env=env, capture_output=True, text=True
        )
        events = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        return result, events, folder / "results"

    def test_one_complete_suite_per_configuration_with_http_and_french(self):
        for name, config in PLAN["configurations"].items():
            with self.subTest(configuration=name):
                result, events, folder = self.run_plan(name)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                runs = [event for event in events if event["args"][0] == "run" and "odoo" in event["args"]]
                tests = [event for event in runs if "--test-enable" in event["args"]]
                self.assertEqual(len(tests), 1)
                self.assertIn("--test-tags=" + ",".join("/" + addon for addon in config["addons"]), tests[0]["args"])
                self.assertNotIn("--no-http", tests[0]["args"])
                self.assertEqual(
                    any("CUMULATIVE_FRENCH_WEBSITE_READY" in event["stdin"] for event in runs), config["website"]
                )
                self.assertTrue((folder / f"suite-{name}" / "success.json").exists())
                self.assertTrue(any(event["args"][:2] == ["network", "rm"] for event in events))

    def test_every_migration_runs_without_launching_addon_tests(self):
        result, events, folder = self.run_plan("migrations")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any("--test-enable" in event["args"] for event in events))
        networks = [event["args"][-1] for event in events if event["args"][:2] == ["network", "create"]]
        self.assertEqual(len(networks), len(PLAN["migrations"]))
        self.assertEqual(len(set(networks)), len(networks))
        for entry in PLAN["migrations"]:
            self.assertTrue((folder / "migrations" / entry["id"] / "success.json").exists())
            for phase in entry["steps"]:
                self.assertTrue((folder / "migrations" / entry["id"] / f"{phase}.log").stat().st_size)

    def test_failed_suite_has_no_success_marker_and_cleans_resources(self):
        result, events, folder = self.run_plan("full", "--test-enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((folder / "suite-full/success.json").exists())
        self.assertTrue(any(event["args"][:2] == ["network", "rm"] for event in events))

    def test_failed_migration_does_not_hide_other_results_or_publish_success(self):
        result, _, folder = self.run_plan("migrations", "tm_catpdf_test_upgrade")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((folder / "migrations/catalogue/success.json").exists())
        self.assertTrue((folder / "migrations/s093/success.json").exists())

    def test_unknown_configuration_never_starts_docker(self):
        result, events, _ = self.run_plan("S09")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, [])


class FinalGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.results = Path(self.tmp.name)
        self.needs = {job: {"result": "success"} for job in gate.REQUIRED_JOBS}
        for name, config in PLAN["configurations"].items():
            folder = self.results / f"suite-{name}-results"
            folder.mkdir()
            (folder / "success.json").write_text(json.dumps({"configuration": name, "addons": config["addons"]}))
            (folder / "bootstrap.log").write_text("Synthetic install evidence")
            (folder / "french.log").write_text("CUMULATIVE_FRENCH_WEBSITE_READY")
            (folder / "tests.log").write_text(
                "0 failed, 0 error(s) of 12 tests\n"
                + "\n".join(f"odoo.tests.stats: {addon}: 12 tests" for addon in config["addons"])
            )
        for entry in PLAN["migrations"]:
            folder = self.results / "migrations-results" / entry["id"]
            folder.mkdir(parents=True)
            (folder / "success.json").write_text(json.dumps({"migration": entry["id"], "steps": entry["steps"]}))
            for step in entry["steps"]:
                (folder / f"{step}.log").write_text("Synthetic migration evidence")

    def test_complete_success(self):
        gate.validate(self.needs, self.results)

    def test_every_unsuccessful_or_missing_job_is_rejected(self):
        for name in self.needs:
            for state in ("failure", "cancelled", "skipped", "neutral", None):
                with self.subTest(name=name, state=state), self.assertRaises(ValueError):
                    gate.validate({**self.needs, name: {"result": state}}, self.results)
            with self.assertRaises(ValueError):
                gate.validate({key: value for key, value in self.needs.items() if key != name}, self.results)

    def test_missing_empty_and_failed_logs_or_markers_are_rejected(self):
        for path in self.results.rglob("*"):
            if not path.is_file() or path.name == "french.log" and "website" not in str(path):
                continue
            saved = path.read_text()
            for replacement in (None, "", "Traceback (most recent call last):\nAssertionError"):
                with self.subTest(path=path, replacement=replacement):
                    path.unlink() if replacement is None else path.write_text(replacement)
                    with self.assertRaises((ValueError, OSError)):
                        gate.validate(self.needs, self.results)
                    path.write_text(saved)

    def test_zero_tests_and_failed_odoo_results_are_rejected(self):
        path = self.results / "suite-core-results/tests.log"
        for text in ("0 failed, 0 error(s) of 0 tests", "1 failed, 0 error(s) of 12 tests", "Odoo started"):
            path.write_text(text)
            with self.assertRaises(ValueError):
                gate.validate(self.needs, self.results)

    def test_missing_selected_addon_cannot_hide_behind_other_tests(self):
        path = self.results / "suite-full-results/tests.log"
        path.write_text(path.read_text().replace("odoo.tests.stats: training_management_survey: 12 tests", ""))
        with self.assertRaises(ValueError):
            gate.validate(self.needs, self.results)

    def test_failure_produces_failed_summary_and_exit_status(self):
        summary = self.results / "summary.md"
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/ci/check_results.py")],
            cwd=self.results,
            env={**os.environ, "NEEDS_JSON": "{}", "GITHUB_STEP_SUMMARY": str(summary)},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Validation Training Management : échec", summary.read_text())


if __name__ == "__main__":
    unittest.main()
