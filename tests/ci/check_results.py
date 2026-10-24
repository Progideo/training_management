"""Common verdict: every configuration, migration path and prerequisite must succeed."""

import json
import os
from pathlib import Path

from run_suite import BAD_LOG, PLAN, assert_tests_ran

REQUIRED_JOBS = {"orchestration", "suite", "migrations"}


def read_log(path, *, allow_tracebacks=False):
    text = path.read_text(errors="replace")
    if (
        not text.strip()
        or BAD_LOG.search(text)
        or (not allow_tracebacks and "Traceback (most recent call last):" in text)
    ):
        raise ValueError(f"Missing or failed evidence: {path}")
    return text


def validate(needs, results):
    if set(needs) != REQUIRED_JOBS:
        raise ValueError("Missing or unexpected prerequisite jobs")
    for name, job in needs.items():
        if job.get("result") != "success":
            raise ValueError(f"{name}: expected success, got {job.get('result')}")
    for name, config in PLAN["configurations"].items():
        folder = results / f"suite-{name}-results"
        expected = {"configuration": name, "addons": config["addons"]}
        if json.loads((folder / "success.json").read_text()) != expected:
            raise ValueError(f"{name}: configuration evidence mismatch")
        read_log(folder / "bootstrap.log")
        if config.get("language") == "fr_FR":
            if "CUMULATIVE_FRENCH_WEBSITE_READY" not in read_log(folder / "french.log"):
                raise ValueError(f"{name}: missing French Website evidence")
        assert_tests_ran(read_log(folder / "tests.log", allow_tracebacks=True), config["addons"])
    for entry in PLAN["migrations"]:
        folder = results / "migrations-results" / entry["id"]
        expected = {"migration": entry["id"], "steps": entry["steps"]}
        if json.loads((folder / "success.json").read_text()) != expected:
            raise ValueError(f"{entry['id']}: migration evidence mismatch")
        for step in entry["steps"]:
            read_log(folder / f"{step}.log")


def main():
    try:
        validate(json.loads(os.environ["NEEDS_JSON"]), Path("test-results"))
        summary = "## Validation Training Management : réussie\n\n"
        summary += "| Configuration | Suite cumulative |\n| --- | --- |\n"
        for config in PLAN["configurations"].values():
            summary += f"| {config['label']} | Réussie |\n"
        summary += f"\n{len(PLAN['migrations'])} parcours de migration/concurrence conservés.\n"
    except (ValueError, OSError) as error:
        summary = f"## Validation Training Management : échec\n\n{error}\n"
        raise
    finally:
        print(summary)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
                stream.write(summary)


if __name__ == "__main__":
    main()
