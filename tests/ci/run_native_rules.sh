#!/usr/bin/env bash
# Native rules: preserve documents, queue and identity through two upgrades.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the workflow pinned image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/s021}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
container=tm_rules_${run_id}_odoo
volume=tm_rules_${run_id}_data
cleanup() {
  rc=$?
  trap - EXIT
  docker rm -f "$container" > "$results/container-cleanup.log" 2>&1 || true
  if ! docker volume rm "$volume" > "$results/volume-cleanup.log" 2>&1; then
    if docker volume inspect "$volume" > /dev/null 2>&1; then rc=1; fi
  fi
  rm -rf "$work_dir"
  exit "$rc"
}
trap cleanup EXIT
run_odoo() {
  docker run --rm -i --name "$container" --network "${TM_S021_NETWORK:-host}" \
    -e HOST="${TM_S021_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e TM_UPGRADE_PHASE="${TM_UPGRADE_PHASE:-}" -e S021_PHASE="${S021_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" -d tm_s01_test_s021_native_rules --workers=0 --max-cron-threads=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -70 "$results/$name.log"; return 1; }
  if rg -q ' [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -70 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
git -C "$repo" archive f8c45919e5f00582dc75003008b26cc888e5ce68 addons | tar -x -C "$work_dir"
TM_ADDONS_DIR="$work_dir/addons" step baseline run_odoo -i website,website_slides,training_management_sale,training_management_survey,sale_invoice_address_fiscal --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/addons" TM_UPGRADE_PHASE=prepare step catalogue_prepare run_odoo shell --no-http < "$repo/tests/probes/catalogue_upgrade_probe.py"
# Reuse the historical fixture with the native payment wizard introduced by #103.
# Its bank-audit fields remain in the snapshot, but are no longer wizard inputs.
python3 - "$repo" "$work_dir" <<'PYFIXTURE'
from pathlib import Path
import sys
source = (Path(sys.argv[1]) / "tests/probes/s021_history.py").read_text()
source = source.replace('            "training_bank_reference": "HISTORICAL-S021",\n', '')
source = source.replace('            "training_bank_verified": True,\n', '')
source = source.replace('[("training_bank_reference", "=", "HISTORICAL-S021")]', '[("reconciled_invoice_ids", "in", invoice.ids)]')
(Path(sys.argv[2]) / "documents.py").write_text(source)
PYFIXTURE
TM_ADDONS_DIR="$work_dir/addons" S021_PHASE=prepare step documents_prepare run_odoo shell --no-http < "$work_dir/documents.py"
TM_ADDONS_DIR="$work_dir/addons" S021_PHASE=prepare step exact_prepare run_odoo shell --no-http < "$repo/tests/probes/native_rules_history.py"
step upgrade run_odoo -u training_management,training_management_sale,training_management_survey,sale_invoice_address_fiscal --stop-after-init
S021_PHASE=verify step documents_preserved run_odoo shell --no-http < "$work_dir/documents.py"
TM_UPGRADE_PHASE=verify step catalogue_preserved run_odoo shell --no-http < "$repo/tests/probes/catalogue_upgrade_probe.py"
S021_PHASE=verify step exact_preserved run_odoo shell --no-http < "$repo/tests/probes/native_rules_history.py"
step repeat_upgrade run_odoo -u training_management,training_management_sale,training_management_survey,sale_invoice_address_fiscal --stop-after-init
S021_PHASE=verify step repeat_preserved run_odoo shell --no-http < "$repo/tests/probes/native_rules_history.py"
