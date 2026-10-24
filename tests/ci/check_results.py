"""Common CI verdict: all jobs and all declared scenario evidence must pass."""

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COVERAGE = json.loads((ROOT / "tests/ci/coverage.json").read_text())["scenarios"]
WORKFLOW_COVERAGE = json.loads((ROOT / "tests/ci/workflow_coverage.json").read_text())
SPECIALIZED = {**WORKFLOW_COVERAGE["jobs"], **WORKFLOW_COVERAGE["extensions"]}
REQUIRED_JOBS = {"orchestration", "scenarios", *SPECIALIZED}


def validate(needs, results):
    if set(needs) != REQUIRED_JOBS:
        raise ValueError("Missing or unexpected prerequisite jobs")
    for name, job in needs.items():
        if job.get("result") != "success":
            raise ValueError(f"{name}: result must be success, got {job.get('result')}")
    durations = {}
    for scenario, expected in COVERAGE.items():
        folder = results / f"odoo-{scenario}-results"
        with (folder / "timings.tsv").open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        if [row["step"] for row in rows] != [step["step"] for step in expected]:
            raise ValueError(f"{scenario}: missing, duplicate or reordered steps")
        for row in rows:
            if row["exit_code"] != "0" or int(row["duration_seconds"]) < 0:
                raise ValueError(f"{scenario}/{row['step']}: unsuccessful step")
            log = folder / (row["step"] + ".log")
            if not log.is_file() or not log.stat().st_size:
                raise ValueError(f"{scenario}/{row['step']}: missing or empty log")
        durations[scenario] = sum(int(row["duration_seconds"]) for row in rows)
    for job in SPECIALIZED.values():
        for artifact in job["artifacts"]:
            for step in job["steps"]:
                log = results / artifact / (step + ".log")
                if not log.is_file() or not log.stat().st_size:
                    raise ValueError(f"{artifact}/{step}: missing or empty log")
    return durations


def main():
    try:
        durations = validate(json.loads(os.environ["NEEDS_JSON"]), Path("test-results"))
    except (ValueError, OSError) as error:
        summary = f"## Validation Training Management : échec\n\n{error}\n"
        print(summary)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
                stream.write(summary)
        raise
    summary = "## Validation Training Management : réussie\n\n"
    summary += "Toutes les tâches requises sont réussies et leurs preuves sont présentes.\n\n"
    summary += "| Scénario du socle | Étapes | Durée des étapes (s) |\n| --- | ---: | ---: |\n"
    for scenario, seconds in durations.items():
        summary += f"| {scenario} | {len(COVERAGE[scenario])} | {seconds} |\n"
    summary += f"\n21 étapes validées ; cumul des étapes : {sum(durations.values())} s.\n"
    summary += "Ces mesures excluent préparation des runners, services et transferts d’artefacts.\n"
    summary += "\n| Scénario spécialisé | Étapes vérifiées |\n| --- | ---: |\n"
    for job in SPECIALIZED.values():
        for artifact in job["artifacts"]:
            summary += f"| {artifact} | {len(job['steps'])} |\n"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(summary)


if __name__ == "__main__":
    main()
