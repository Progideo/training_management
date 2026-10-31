#!/usr/bin/env python3
"""Lanceur explicite uniquement : base jetable, préparation, navigateur, nettoyage."""

import argparse
from http.client import HTTPException
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
# Réutilise seulement la gestion des ressources jetables ; aucune suite CI n'est appelée.
sys.path.insert(0, str(ROOT / "tests/ci"))
from run_suite import Database, checked  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include", action="append", choices=["portal", "private", "isolation", "submission", "internal"]
    )
    parser.add_argument("--port", type=int, default=18099)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--list", action="store_true", help="Afficher les parcours sans démarrer Docker")
    args = parser.parse_args()
    if args.list:
        print(
            "portal/private : consultation et PDF privé\nisolation/private : refus tiers\nsubmission : dépôt refusé puis corrigé\ninternal : catégorie native"
        )
        return 0
    if not 1024 <= args.port <= 65535:
        parser.error("Le port doit être compris entre 1024 et 65535")
    os.umask(0o077)
    run_id = "browser_" + uuid4().hex[:12]
    folder = ROOT / "test-results" / run_id
    folder.mkdir(parents=True)
    # ID unique interne : aucune réutilisation ou destruction des ressources d'une autre recette.
    os.environ["TM_CI_ID"] = run_id
    os.environ.setdefault("TM_BROWSER_PASSWORD", secrets.token_urlsafe(24))
    os.environ["TM_BASE_URL"] = f"http://127.0.0.1:{args.port}"
    pdf = folder / "fictional-work.pdf"
    pdf.write_bytes(b"%PDF-1.4\nFictional browser work\n%%EOF")
    oversize = folder / "oversize.pdf"
    with oversize.open("wb") as output:
        output.write(b"%PDF-1.4\n")
        output.truncate(20 * 1024 * 1024 + 1)
    with Database("manual", folder) as database:
        checked(
            database.odoo("-i", "website,training_management", "--without-demo", "--stop-after-init"),
            folder / "install.log",
        )
        command = database.odoo("shell", "--no-http")
        command[2:2] = [
            "-e",
            "TM_BROWSER_PASSWORD",
            "-e",
            "TM_BROWSER_PARTICIPANT",
            "-e",
            "TM_BROWSER_OUTSIDER",
            "-e",
            "TM_BROWSER_COORDINATOR",
        ]
        with (HERE / "fixture.py").open() as source:
            result = checked(command, folder / "prepare.log", stdin=source)
        line = next(line for line in result.splitlines() if line.startswith("BROWSER_FIXTURE="))
        values = json.loads(line.split("=", 1)[1])
        values.update(OVERSIZE_FILE=str(oversize), VALID_FILE=str(pdf))
        variables = folder / "variables.json"
        variables.write_text(json.dumps(values))
        command = database.odoo(
            "--smtp=127.0.0.1", "--smtp-port=1", "--db-filter=^tm_suite_test$", "--no-database-list"
        )
        command[2:2] = ["-p", f"127.0.0.1:{args.port}:8069"]
        with (folder / "server.log").open("w") as log:
            server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(90):
                    if server.poll() is not None:
                        raise RuntimeError(f"Odoo arrêté : consulter {folder / 'server.log'}")
                    try:
                        with urlopen(os.environ["TM_BASE_URL"] + "/web/login", timeout=2) as response:
                            if response.status == 200:
                                break
                    except (URLError, TimeoutError, HTTPException):
                        pass
                    time.sleep(1)
                else:
                    raise RuntimeError("Odoo n'est pas prêt après 90 essais")
                command = [sys.executable, "-m", "robot", "--outputdir", str(folder), "--variablefile", str(variables)]
                if args.headed:
                    command += ["--variable", "HEADLESS:False"]
                for tag in args.include or []:
                    command += ["--include", tag]
                command += [str(HERE / "journeys.robot")]
                print(f"Parcours navigateur : {os.environ['TM_BASE_URL']} ; rapports : {folder}", flush=True)
                return subprocess.call(command)
            finally:
                subprocess.run(["docker", "stop", database.name + "_odoo"], stdout=subprocess.DEVNULL, check=False)
                server.wait(timeout=30)
                oversize.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
