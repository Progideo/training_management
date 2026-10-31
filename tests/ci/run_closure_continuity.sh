#!/usr/bin/env bash
# Review corrections: upgrade merged P20, preserve closed dossiers and exercise continuity.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the workflow pinned image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/closure-continuity}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
container=tm_continuity_${run_id}_odoo
volume=tm_continuity_${run_id}_data
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
  docker run --rm -i --name "$container" --network "${TM_S08_NETWORK:-host}" \
    -e HOST="${TM_S08_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e CONTINUITY_PHASE="${CONTINUITY_PHASE:-}" -e S07_PHASE="${S07_PHASE:-}" -e S08_PHASE="${S08_PHASE:-}" -e S06_PHASE="${S06_PHASE:-}" -e TM_UPGRADE_PHASE="${TM_UPGRADE_PHASE:-}" -e S021_PHASE="${S021_PHASE:-}" -e S052_PHASE="${S052_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" -d "${TM_S08_DATABASE:-tm_s01_test_s021_s052}" --workers=0 --max-cron-threads=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -70 "$results/$name.log"; return 1; }
  if rg -q ' CRITICAL | [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -70 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
git -C "$repo" archive 149a3033e178ea4012e15d37fb105e7e7612d3fa addons | tar -x -C "$work_dir"
TM_ADDONS_DIR="$work_dir/addons" step baseline run_odoo -i website,website_slides,training_management_sale,training_management_survey --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/addons" TM_UPGRADE_PHASE=prepare step catalogue_prepare run_odoo shell --no-http < "$repo/tests/probes/catalogue_upgrade_probe.py"
TM_ADDONS_DIR="$work_dir/addons" S052_PHASE=prepare step learning_prepare run_odoo shell --no-http < "$repo/tests/probes/s052_history.py"
TM_ADDONS_DIR="$work_dir/addons" S07_PHASE=prepare step attendance_prepare run_odoo shell --no-http < "$repo/tests/probes/s07_history.py"
TM_ADDONS_DIR="$work_dir/addons" S08_PHASE=prepare step closure_prepare run_odoo shell --no-http < "$repo/tests/probes/s08_history.py"
TM_ADDONS_DIR="$work_dir/addons" CONTINUITY_PHASE=baseline step exact_prepare run_odoo shell --no-http < "$repo/tests/probes/closure_continuity_history.py"
step upgrade run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
CONTINUITY_PHASE=verify_legacy step legacy_preserved run_odoo shell --no-http < "$repo/tests/probes/closure_continuity_history.py"
CONTINUITY_PHASE=prepare step rectification_prepare run_odoo shell --no-http < "$repo/tests/probes/closure_continuity_history.py"
step second_update run_odoo -u training_management,training_management_survey --stop-after-init
CONTINUITY_PHASE=verify step rectification_preserved run_odoo shell --no-http < "$repo/tests/probes/closure_continuity_history.py"
step concurrency run_odoo shell --no-http < "$repo/tests/probes/closure_continuity_concurrency.py"
