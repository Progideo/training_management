#!/usr/bin/env bash
# S08 -> S09.1 and repeated update, isolated synthetic fixtures only.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the pinned image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/s091}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
container=tm_s091_${run_id}_odoo
volume=tm_s091_${run_id}_data
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
  docker run --rm -i --name "$container" --network "${TM_S091_NETWORK:-host}" \
    -e HOST="${TM_S091_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e TM_UPGRADE_PHASE="${TM_UPGRADE_PHASE:-}" -e S021_PHASE="${S021_PHASE:-}" \
    -e S052_PHASE="${S052_PHASE:-}" -e S06_PHASE="${S06_PHASE:-}" \
    -e S07_PHASE="${S07_PHASE:-}" -e S08_PHASE="${S08_PHASE:-}" -e S091_PHASE="${S091_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" -d "${TM_S091_DATABASE:-tm_s01_test_s021_s052}" --workers=0 --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -70 "$results/$name.log"; return 1; }
  if rg -q ' CRITICAL | [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -70 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
git -C "$repo" archive 802bc302fce2f647560b6f3d684c9d6935315f9d addons | tar -x -C "$work_dir"
TM_ADDONS_DIR="$work_dir/addons" step baseline run_odoo -i website,website_slides,training_management_sale,training_management_survey --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/addons" TM_UPGRADE_PHASE=prepare step catalogue_prepare run_odoo shell --no-http < "$repo/tests/probes/catalogue_upgrade_probe.py"
TM_ADDONS_DIR="$work_dir/addons" S021_PHASE=prepare step documents_prepare run_odoo shell --no-http < "$repo/tests/probes/s021_history.py"
TM_ADDONS_DIR="$work_dir/addons" S052_PHASE=prepare step learning_prepare run_odoo shell --no-http < "$repo/tests/probes/s052_history.py"
TM_ADDONS_DIR="$work_dir/addons" S06_PHASE=prepare step exam_prepare run_odoo shell --no-http < "$repo/tests/probes/s06_history.py"
TM_ADDONS_DIR="$work_dir/addons" S07_PHASE=prepare step attendance_prepare run_odoo shell --no-http < "$repo/tests/probes/s07_history.py"
TM_ADDONS_DIR="$work_dir/addons" S08_PHASE=prepare step fixture_baseline run_odoo shell --no-http < "$repo/tests/probes/s08_upgrade_baseline.py"
TM_ADDONS_DIR="$work_dir/addons" S08_PHASE=prepare step closure_prepare run_odoo shell --no-http < "$repo/tests/probes/s08_history.py"
step upgrade run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init --test-enable --test-tags=/training_management,/training_management_sale,/training_management_survey
TM_UPGRADE_PHASE=verify step catalogue_preserved run_odoo shell --no-http < "$repo/tests/probes/catalogue_upgrade_probe.py"
S021_PHASE=verify step documents_preserved run_odoo shell --no-http < "$repo/tests/probes/s021_history.py"
S06_PHASE=verify S052_PHASE=verify step learning_preserved run_odoo shell --no-http < "$repo/tests/probes/s052_history.py"
S06_PHASE=verify step exam_preserved run_odoo shell --no-http < "$repo/tests/probes/s06_history.py"
S07_PHASE=verify step attendance_preserved run_odoo shell --no-http < "$repo/tests/probes/s07_history.py"
S08_PHASE=verify step closure_preserved run_odoo shell --no-http < "$repo/tests/probes/s08_history.py"
S08_PHASE=verify step native_schema_preserved run_odoo shell --no-http < "$repo/tests/probes/s08_upgrade_baseline.py"
TM_S091_DATABASE=tm_s091_fresh step fresh run_odoo -i training_management_sale,training_management_survey --without-demo --stop-after-init --test-enable --test-tags=/training_management,/training_management_sale,/training_management_survey
S091_PHASE=prepare step evaluation_prepare run_odoo shell --no-http < "$repo/tests/probes/s091_history.py"
step second_update run_odoo -u training_management,training_management_survey --stop-after-init
S091_PHASE=verify step evaluation_preserved run_odoo shell --no-http < "$repo/tests/probes/s091_history.py"
step concurrency run_odoo shell --no-http < "$repo/tests/probes/s091_concurrency.py"
