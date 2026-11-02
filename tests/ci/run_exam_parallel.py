"""One delivery: exam start, answers and submission in real parallel transactions."""

from run_suite import Database, ROOT, checked


def main():
    folder = ROOT / "test-results/exam-parallel"
    with Database("exam_parallel", folder) as database:
        checked(
            database.odoo("-i", "training_management_survey", "--without-demo", "--stop-after-init"),
            folder / "install.log",
        )
        with (ROOT / "tests/probes/exam_parallel_saves.py").open() as stream:
            text = checked(database.odoo("shell", "--no-http"), folder / "parallel.log", stdin=stream)
        if "EXAM_PARALLEL_OK" not in text:
            raise ValueError("Exam parallel probe did not finish")


if __name__ == "__main__":
    main()
