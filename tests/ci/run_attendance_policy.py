"""C06 attendance: real roles/HTTP, upgrade preservation and concurrent decisions."""

from run_suite import Database, ROOT, checked


def main():
    folder = ROOT / "test-results/c06-attendance"
    with Database("c06_attendance", folder) as database:
        checked(
            database.odoo(
                "-i",
                "training_management",
                "--without-demo",
                "--stop-after-init",
                "--test-enable",
                "--test-tags=/training_management:TestAttendance,/training_management:TestAttendanceHttp,/training_management:TestAttendanceSignatures,/training_management:TestHalfdayAttendance",
            ),
            folder / "attendance-tests.log",
        )
        for phase in ("prepare", "verify"):
            if phase == "verify":
                checked(database.odoo("-u", "training_management", "--stop-after-init"), folder / "second-update.log")
            command = database.odoo("shell", "--no-http")
            command[3:3] = ["-e", "C06_ATTENDANCE_PHASE=" + phase]
            with (ROOT / "tests/probes/c06_attendance_history.py").open() as stream:
                checked(command, folder / ("history-" + phase + ".log"), stdin=stream)
            command = database.odoo("shell", "--no-http")
            command[3:3] = ["-e", "ATTENDANCE_SIGNATURE_PHASE=" + phase]
            with (ROOT / "tests/probes/attendance_signature_history.py").open() as stream:
                checked(command, folder / ("signature-" + phase + ".log"), stdin=stream)
        command = database.odoo("shell", "--no-http")
        command[3:3] = ["-e", "ATTENDANCE_SIGNATURE_PHASE=concurrency"]
        with (ROOT / "tests/probes/attendance_signature_history.py").open() as stream:
            checked(command, folder / "signature-concurrency.log", stdin=stream, allow_tracebacks=True)
        with (ROOT / "tests/probes/c06_attendance_concurrency.py").open() as stream:
            checked(database.odoo("shell", "--no-http"), folder / "concurrency.log", stdin=stream)


if __name__ == "__main__":
    main()
