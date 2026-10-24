"""Orchestration contracts, using a Docker double; Odoo itself runs in CI jobs."""

import csv
import hashlib
import importlib.util
import json
import os
import re
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((ROOT / "tests/ci/coverage.json").read_text())
SCENARIOS = LEDGER["scenarios"]
spec = importlib.util.spec_from_file_location("check_results", ROOT / "tests/ci/check_results.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

FAKE_DOCKER = r"""#!/usr/bin/env python3
import hashlib,json,os,sys
from pathlib import Path
args=sys.argv[1:]
file=Path(os.environ['CI_DOCKER_TRACE'])
previous=[json.loads(x) for x in file.read_text().splitlines()] if file.exists() else []
entry={'args':args}
if args[0]=='run':
 data=sys.stdin.buffer.read() if 'shell' in args else b''
 entry['stdin_sha256']=hashlib.sha256(data).hexdigest()
 count=sum(x['args'][0]=='run' for x in previous)+1
else: count=0
with file.open('a') as stream:stream.write(json.dumps(entry)+'\n')
print('Docker orchestration test double')
if args[0]=='run' and str(count)==os.environ.get('CI_FAIL_CALL'):sys.exit(42)
"""


class ScenarioContracts(unittest.TestCase):
    def run_scenario(self, scenario, fail_call=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        directory = Path(tmp.name)
        docker = directory / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        trace = directory / "trace.jsonl"
        env = dict(
            os.environ,
            PATH=str(directory) + os.pathsep + os.environ["PATH"],
            ODOO_IMAGE="pinned-image-test-double",
            TM_CI_ID="contract",
            CI_DOCKER_TRACE=str(trace),
            TM_RESULTS_DIR=str(directory / "results"),
        )
        # Do not inherit operator settings into the contract tests.
        for key in ("TM_TEST_DB", "TM_ADDONS_DIR", "TM_UPGRADE_PHASE", "S03_UPGRADE_PHASE", "CI_FAIL_CALL"):
            env.pop(key, None)
        if fail_call:
            env["CI_FAIL_CALL"] = str(fail_call)
        result = subprocess.run(
            ["bash", str(ROOT / "tests/ci/run_odoo_scenario.sh"), scenario],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        events = [json.loads(x) for x in trace.read_text().splitlines()] if trace.exists() else []
        return result, events, directory

    def test_all_original_operations_keep_arguments_phases_and_probes(self):
        containers, volumes, databases = set(), set(), set()
        self.assertEqual(sum(map(len, SCENARIOS.values())), 21)
        for scenario, expected in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                result, events, directory = self.run_scenario(scenario)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                calls = [event for event in events if event["args"][0] == "run"]
                self.assertEqual(len(calls), len(expected))
                own_dbs = set()
                for call, step in zip(calls, expected):
                    args = call["args"]
                    start = args.index("pinned-image-test-double") + 2
                    end = args.index("--db_host=127.0.0.1")
                    self.assertEqual(args[start:end], step["args"])
                    db = args[args.index("-d") + 1]
                    self.assertEqual(db, step["database"])
                    own_dbs.add(db)
                    for phase in ("TM_UPGRADE_PHASE", "S03_UPGRADE_PHASE"):
                        self.assertIn(f"{phase}={step['phase'].get(phase, '')}", args)
                    data = (ROOT / step["probe"]).read_bytes() if step["probe"] else b""
                    self.assertEqual(call["stdin_sha256"], hashlib.sha256(data).hexdigest())
                    mount = next(x for x in args if x.endswith(":/mnt/extra-addons:ro"))
                    self.assertEqual("s02-baseline/addons:" in mount, step["baseline"])
                    self.assertEqual("s04-bridge/addons:" in mount, step["step"] == "s03-view-bootstrap")
                    self.assertIn("--no-http", args)
                    self.assertIn("--max-cron-threads=0", args)
                    self.assertIn("--workers=0", args)
                self.assertTrue(databases.isdisjoint(own_dbs))
                databases.update(own_dbs)
                args = calls[0]["args"]
                container = args[args.index("--name") + 1]
                volume = next(x.split(":")[0] for x in args if x.endswith(":/var/lib/odoo"))
                self.assertNotIn(container, containers)
                self.assertNotIn(volume, volumes)
                containers.add(container)
                volumes.add(volume)
                self.assertIn(["rm", "-f", container], [e["args"] for e in events])
                self.assertIn(["volume", "rm", volume], [e["args"] for e in events])
                with (directory / "results/timings.tsv").open() as stream:
                    rows = list(csv.DictReader(stream, delimiter="\t"))
                self.assertEqual([r["step"] for r in rows], [s["step"] for s in expected])
                self.assertTrue(all(r["exit_code"] == "0" for r in rows))

    def test_failure_stops_each_scenario_and_survives_tee(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                result, events, directory = self.run_scenario(scenario, fail_call=2)
                self.assertEqual(result.returncode, 42)
                self.assertEqual(sum(e["args"][0] == "run" for e in events), 2)
                with (directory / "results/timings.tsv").open() as stream:
                    rows = list(csv.DictReader(stream, delimiter="\t"))
                self.assertEqual(rows[-1]["exit_code"], "42")
                self.assertEqual(events[-1]["args"][0:2], ["volume", "rm"])

    def test_unknown_scenario_never_starts_docker(self):
        result, events, _ = self.run_scenario("production")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(events, [])


class FinalGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.results = Path(self.tmp.name)
        self.needs = {name: {"result": "success"} for name in gate.REQUIRED_JOBS}
        for scenario, steps in SCENARIOS.items():
            folder = self.results / f"odoo-{scenario}-results"
            folder.mkdir()
            with (folder / "timings.tsv").open("w") as stream:
                stream.write("step\texit_code\tduration_seconds\n")
                for step in steps:
                    stream.write(step["step"] + "\t0\t1\n")
                    (folder / (step["step"] + ".log")).write_text("Synthetic orchestration evidence\n")

        for job in gate.SPECIALIZED.values():
            for artifact in job["artifacts"]:
                folder = self.results / artifact
                folder.mkdir()
                for step in job["steps"]:
                    (folder / (step + ".log")).write_text("Synthetic specialized evidence\n")

    def test_complete_success(self):
        self.assertEqual(sum(gate.validate(self.needs, self.results).values()), 21)

    def test_every_non_success_job_result_is_rejected(self):
        for job in self.needs:
            for result in ("failure", "cancelled", "skipped", "timed_out", "neutral", "", None):
                with self.subTest(job=job, result=result):
                    needs = {**self.needs, job: {"result": result}}
                    with self.assertRaises(ValueError):
                        gate.validate(needs, self.results)

    def test_absent_job_or_artifact_is_rejected(self):
        with self.assertRaises(ValueError):
            gate.validate({"scenarios": {"result": "success"}}, self.results)
        (self.results / "odoo-fresh-results/timings.tsv").unlink()
        with self.assertRaises(FileNotFoundError):
            gate.validate(self.needs, self.results)

    def test_missing_failed_or_duplicate_step_is_rejected(self):
        path = self.results / "odoo-fresh-results/timings.tsv"
        original = path.read_text()
        for text in (
            original.splitlines()[0] + "\n",
            original.replace("\t0\t", "\t42\t"),
            original + original.splitlines()[1] + "\n",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                path.write_text(text)
                gate.validate(self.needs, self.results)

    def test_specialized_missing_or_empty_evidence_is_rejected(self):
        for job in gate.SPECIALIZED.values():
            for artifact in job["artifacts"]:
                for step in job["steps"]:
                    path = self.results / artifact / (step + ".log")
                    original = path.read_text()
                    for empty in (False, True):
                        with self.subTest(artifact=artifact, step=step, empty=empty):
                            path.write_text("") if empty else path.unlink()
                            with self.assertRaises(ValueError):
                                gate.validate(self.needs, self.results)
                            path.write_text(original)

    def test_failed_job_produces_a_failed_verdict_and_summary(self):
        summary = self.results / "summary.md"
        needs = {**self.needs, "feedback": {"result": "failure"}}
        result = subprocess.run(
            [os.sys.executable, str(ROOT / "tests/ci/check_results.py")],
            cwd=self.results,
            env={**os.environ, "NEEDS_JSON": json.dumps(needs), "GITHUB_STEP_SUMMARY": str(summary)},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Validation Training Management : échec", summary.read_text())
        self.assertIn("feedback", summary.read_text())

    def test_empty_base_evidence_is_rejected(self):
        for scenario, steps in SCENARIOS.items():
            for step in steps:
                path = self.results / f"odoo-{scenario}-results" / (step["step"] + ".log")
                original = path.read_text()
                with self.subTest(scenario=scenario, step=step["step"]):
                    path.write_text("")
                    try:
                        with self.assertRaises(ValueError):
                            gate.validate(self.needs, self.results)
                    finally:
                        path.write_text(original)

    def test_missing_log_is_rejected(self):
        (self.results / "odoo-fresh-results/s03-concurrency.log").unlink()
        with self.assertRaises(ValueError):
            gate.validate(self.needs, self.results)


class WorkflowContract(unittest.TestCase):
    def test_coverage_ledger_matches_the_original_21_commands(self):
        text = subprocess.check_output(
            ["git", "show", LEDGER["source_commit"] + ":.github/workflows/odoo.yml"], cwd=ROOT, text=True
        )
        block = yaml.safe_load(text)["jobs"]["catalogue"]["steps"][1]["run"]
        original = {}
        for line in re.sub(r"\\\n\s*", " ", block).splitlines():
            match = re.search(r"tee test-results/([\w-]+)\.log", line)
            if not match:
                continue
            args = line.split("run_odoo", 1)[1].split("2>&1", 1)[0].strip()
            probe = None
            if "< " in args:
                args, probe = args.split("< ", 1)
                probe = probe.strip()
            db = re.search(r"TM_TEST_DB=([^ ]+)", line)
            phase = re.search(r"(TM_UPGRADE_PHASE|S03_UPGRADE_PHASE)=(\w+)", line)
            original[match.group(1)] = dict(
                step=match.group(1),
                args=shlex.split(args),
                probe=probe,
                database=db.group(1) if db else "tm_s01_test_ci",
                phase={phase.group(1): phase.group(2)} if phase else {},
                baseline="TM_ADDONS_DIR=" in line,
            )
        current = {step["step"]: step for steps in SCENARIOS.values() for step in steps}
        self.assertEqual(len(original), 21)
        self.assertEqual(current, original)

    def test_single_workflow_preserves_all_specialized_execution_contracts(self):
        ledger = json.loads((ROOT / "tests/ci/workflow_coverage.json").read_text())
        jobs = yaml.safe_load((ROOT / ".github/workflows/odoo.yml").read_text())["jobs"]
        self.assertEqual(set(jobs), {*gate.REQUIRED_JOBS, "validation"})
        self.assertEqual(len(ledger["jobs"]), 10)
        for name, contract in ledger["jobs"].items():
            with self.subTest(job=name):
                original = subprocess.check_output(
                    ["git", "show", ledger["source_commit"] + ":" + contract["source_workflow"]],
                    cwd=ROOT,
                    text=True,
                )
                old = yaml.safe_load(original)["jobs"][contract["source_job"]]
                current = dict(jobs[name])
                self.assertTrue(current.pop("name"))
                self.assertEqual(current, old)
                script = ROOT / contract["script"]
                self.assertEqual(
                    script.read_bytes(),
                    subprocess.check_output(
                        ["git", "show", ledger["source_commit"] + ":" + contract["script"]],
                        cwd=ROOT,
                    ),
                )
                steps = re.findall(r"(?m)^(?:[A-Z0-9_]+=[^\n]*? )?step ([a-z0-9_]+) run_odoo", script.read_text())
                self.assertEqual(contract["steps"], steps)
                upload = next(step["with"] for step in old["steps"] if step.get("uses") == "actions/upload-artifact@v4")
                expected = [upload["name"]]
                if "strategy" in old:
                    expected = [
                        upload["name"].replace("${{ matrix.website }}", str(value).lower())
                        for value in old["strategy"]["matrix"]["website"]
                    ]
                self.assertEqual(contract["artifacts"], expected)
                self.assertFalse((ROOT / contract["source_workflow"]).exists())
        # Four base jobs, two catalogue variants, nine specialized jobs, style and verdict.
        self.assertEqual(
            sum(
                len(next(iter(job["strategy"]["matrix"].values()))) if "strategy" in job else 1 for job in jobs.values()
            ),
            17,
        )
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            workflow = yaml.safe_load(path.read_text())
            trigger = workflow.get("on", workflow.get(True))
            if "pull_request" in trigger:
                self.assertEqual(path.name, "odoo.yml")
        gate_job = jobs["validation"]
        self.assertEqual(gate_job["steps"][1]["with"]["pattern"], "*-results*")

    def test_parallelism_is_bounded_and_gate_cannot_be_skipped_by_failure(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/odoo.yml").read_text())
        jobs = workflow["jobs"]
        matrix = jobs["scenarios"]
        self.assertEqual(matrix["strategy"]["matrix"]["scenario"], list(SCENARIOS))
        self.assertFalse(matrix["strategy"]["fail-fast"])
        self.assertEqual(matrix["strategy"]["max-parallel"], 4)
        self.assertNotIn("continue-on-error", matrix)
        self.assertNotIn("if", matrix)
        self.assertEqual(set(jobs["validation"]["needs"]), gate.REQUIRED_JOBS)
        self.assertEqual(jobs["validation"]["if"], "${{ always() }}")
        self.assertEqual(jobs["validation"]["name"], "Validation CI Odoo")
        self.assertNotIn("continue-on-error", jobs["validation"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        old = subprocess.check_output(
            ["git", "show", LEDGER["source_commit"] + ":.github/workflows/odoo.yml"], cwd=ROOT, text=True
        )
        baseline = yaml.safe_load(old)["jobs"]["catalogue"]
        self.assertEqual(matrix["services"], baseline["services"])
        self.assertEqual(matrix["env"]["ODOO_IMAGE"], baseline["env"]["ODOO_IMAGE"])


if __name__ == "__main__":
    unittest.main()
