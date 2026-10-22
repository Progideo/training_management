"""Final CI gate: only complete, successful jobs and all 21 steps may pass."""

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COVERAGE = json.loads((ROOT / "tests/ci/coverage.json").read_text())["scenarios"]


def validate(needs, results):
    if set(needs) != {"orchestration", "scenarios"}:
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
            if not (folder / (row["step"] + ".log")).is_file():
                raise ValueError(f"{scenario}/{row['step']}: missing log")
        durations[scenario] = sum(int(row["duration_seconds"]) for row in rows)
    return durations


def main():
    durations = validate(json.loads(os.environ["NEEDS_JSON"]), Path("test-results"))
    summary = "| Scénario | Étapes | Durée des étapes (s) |\n| --- | ---: | ---: |\n"
    for scenario, seconds in durations.items():
        summary += f"| {scenario} | {len(COVERAGE[scenario])} | {seconds} |\n"
    summary += f"\n21 étapes validées ; cumul des étapes : {sum(durations.values())} s.\n"
    summary += "Ces mesures excluent préparation des runners, services et transferts d’artefacts.\n"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(summary)


if __name__ == "__main__":
    main()
