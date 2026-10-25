"""One cumulative Odoo suite per configuration; isolated migration evidence separately."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PLAN = json.loads((ROOT / "tests/ci/suite.json").read_text())
IMAGE = "odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23"
BAD_LOG = re.compile(r" CRITICAL | [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)")


def checked(command, log, *, env=None, stdin=None, allow_tracebacks=False):
    started = time.monotonic()
    with log.open("w") as output:
        result = subprocess.run(command, cwd=ROOT, env=env, stdin=stdin, stdout=output, stderr=subprocess.STDOUT)
    text = log.read_text(errors="replace")
    if (
        result.returncode
        or BAD_LOG.search(text)
        or (not allow_tracebacks and "Traceback (most recent call last):" in text)
    ):
        print(text[-12000:], flush=True)
        raise RuntimeError(f"{log.name}: failed ({result.returncode})")
    print(f"{log.parent.name}/{log.name}: OK ({time.monotonic() - started:.0f}s)", flush=True)
    return text


def resource_id(name):
    run_id = os.environ.get("TM_CI_ID", f"local_{os.getpid()}")
    if not re.fullmatch(r"[A-Za-z0-9_]+", run_id + name):
        raise ValueError("Invalid disposable resource identifier")
    return f"tm_suite_{run_id}_{name}"


class Database:
    """Each path gets its own PostgreSQL and network, including historical fixed DB names."""

    def __init__(self, name, folder):
        self.name = resource_id(name)
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.owns_network = False

    def __enter__(self):
        self.owns_network = False
        try:
            # Claim the network only after refusing pre-existing resources. A
            # second invocation with the same ID must never destroy the first.
            for kind, name in (
                ("network", self.name),
                ("container", self.name + "_pg"),
                ("container", self.name + "_odoo"),
                ("volume", self.name + "_data"),
            ):
                result = subprocess.run(
                    ["docker", kind, "inspect", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                if result.returncode == 0:
                    raise RuntimeError(f"Disposable resource already exists; use another TM_CI_ID: {name}")
            checked(["docker", "network", "create", self.name], self.folder / "network.log")
            self.owns_network = True
            checked(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    self.name + "_pg",
                    "--network",
                    self.name,
                    "--network-alias",
                    "postgres",
                    "-e",
                    "POSTGRES_USER=odoo",
                    "-e",
                    "POSTGRES_PASSWORD=fictional_ci_password",
                    "-e",
                    "POSTGRES_DB=postgres",
                    "--health-cmd",
                    "pg_isready -U odoo -d postgres",
                    "--health-interval=2s",
                    "--health-timeout=5s",
                    "--health-retries=30",
                    "postgres:18.6",
                ],
                self.folder / "postgres.log",
            )
            for _ in range(60):
                status = subprocess.check_output(
                    ["docker", "inspect", "--format={{.State.Health.Status}}", self.name + "_pg"], text=True
                ).strip()
                if status == "healthy":
                    return self
                if status == "unhealthy":
                    break
                time.sleep(1)
            raise RuntimeError("Disposable PostgreSQL did not become healthy")
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, kind, value, traceback):
        if not self.owns_network:
            return
        # Every resource name belongs to this run; never prune global Docker resources.
        failures = []
        commands = [
            ["docker", "rm", "-f", self.name + "_odoo"],
            ["docker", "rm", "-f", "-v", self.name + "_pg"],
            ["docker", "volume", "rm", self.name + "_data"],
            ["docker", "network", "rm", self.name],
        ]
        for index, command in enumerate(commands):
            with (self.folder / f"cleanup-{index}.log").open("w") as output:
                result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
            if result.returncode:
                # An absent container/volume is normal when setup failed or a legacy script cleaned it.
                inspect = (
                    ["docker", command[1], "inspect", command[-1]]
                    if command[1] in {"volume", "network"}
                    else ["docker", "inspect", command[-1]]
                )
                if subprocess.run(inspect, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                    failures.append(command[-1])
        if failures:
            raise RuntimeError(f"Disposable cleanup failed: {failures}")

    def odoo(self, *args):
        return [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            self.name + "_odoo",
            "--network",
            self.name,
            "-e",
            "HOST=postgres",
            "-e",
            "USER=odoo",
            "-e",
            "PASSWORD=fictional_ci_password",
            "-v",
            f"{ROOT / 'addons'}:/mnt/extra-addons:ro",
            "-v",
            self.name + "_data:/var/lib/odoo",
            os.environ.get("ODOO_IMAGE", IMAGE),
            "odoo",
            *args,
            "-d",
            "tm_suite_test",
            "--workers=0",
            "--max-cron-threads=0",
            "--http-interface=0.0.0.0",
            "--http-port=8069",
        ]


def suite(configuration, results):
    config = PLAN["configurations"][configuration]
    folder = results / f"suite-{configuration}"
    prepare_results(folder)
    with Database(configuration, folder) as database:
        bootstrap = "website,website_slides" if config["website"] else "base"
        checked(database.odoo("-i", bootstrap, "--without-demo", "--stop-after-init"), folder / "bootstrap.log")
        if config.get("language") == "fr_FR":
            with (ROOT / "tests/ci/suite_french.py").open() as probe:
                checked(database.odoo("shell", "--no-http"), folder / "french.log", stdin=probe)
        # Module selectors discover all current and future test classes. No class lists or increment tags.
        addons = config["addons"]
        text = checked(
            database.odoo(
                "-i",
                ",".join(addons),
                "--without-demo",
                "--stop-after-init",
                "--test-enable",
                "--test-tags=" + ",".join("/" + addon for addon in addons),
            ),
            folder / "tests.log",
            allow_tracebacks=True,
        )
        assert_tests_ran(text, addons)
    (folder / "success.json").write_text(json.dumps({"configuration": configuration, "addons": addons}))


def assert_tests_ran(text, addons):
    matches = re.findall(r"0 failed, 0 error\(s\) of ([0-9]+) tests", text)
    if not matches or not any(int(count) > 0 for count in matches):
        raise ValueError("No successful, nonempty Odoo test result")
    for addon in addons:
        if not re.search(r"odoo.tests.stats: " + re.escape(addon) + r": [1-9][0-9]* tests", text):
            raise ValueError(f"No executed tests for selected addon: {addon}")


def prepare_results(folder):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "success.json").unlink(missing_ok=True)


def migration(entry, results):
    folder = results / "migrations" / entry["id"]
    prepare_results(folder)
    with Database(entry["id"], folder) as database:
        env = {
            **os.environ,
            **entry.get("env", {}),
            "ODOO_IMAGE": os.environ.get("ODOO_IMAGE", IMAGE),
            "TM_CI_ID": database.name,
            "TM_RESULTS_DIR": str(folder),
        }
        for prefix in (
            "CI",
            "CATPDF",
            "S021",
            "S04",
            "S05",
            "S052",
            "S06",
            "S07",
            "S08",
            "S091",
            "S092",
            "S093",
            "S094",
            "S10",
            "S11",
            "P01P06",
        ):
            env[f"TM_{prefix}_NETWORK"] = database.name
            env[f"TM_{prefix}_DB_HOST"] = "postgres"
        checked(["bash", str(ROOT / entry["script"]), *entry["args"]], folder / "runner.log", env=env)
        for step in entry["steps"]:
            log = folder / f"{step}.log"
            if (
                not log.is_file()
                or not log.stat().st_size
                or BAD_LOG.search(log.read_text(errors="replace"))
                or "Traceback (most recent call last):" in log.read_text(errors="replace")
            ):
                raise ValueError(f"Missing or failed migration evidence: {entry['id']}/{step}")
    (folder / "success.json").write_text(json.dumps({"migration": entry["id"], "steps": entry["steps"]}))


def migrations(results):
    # Parallelism is only a runner implementation detail; every historical path is required.
    # Separate services retain the isolation previously provided by separate Actions jobs.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(migration, entry, results) for entry in PLAN["migrations"]]
        errors = []
        for future in futures:
            try:
                future.result()
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError("\n".join(errors))


if __name__ == "__main__":
    results = Path(os.environ.get("TM_RESULTS_DIR", ROOT / "test-results")).resolve()
    if len(sys.argv) != 2 or sys.argv[1] not in {*PLAN["configurations"], "migrations"}:
        raise SystemExit("Usage: run_suite.py <configuration|migrations>")
    if sys.argv[1] == "migrations":
        if not shutil.which("rg"):
            raise SystemExit("ripgrep (rg) is required to verify migration logs before starting Docker")
        migrations(results)
    else:
        suite(sys.argv[1], results)
