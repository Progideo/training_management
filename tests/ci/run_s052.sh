#!/usr/bin/env bash
# Merged S05.1 + Website/eLearning -> S05 complement, preserving histories.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the workflow pinned image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/s052}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
container=tm_s052_${run_id}_odoo
volume=tm_s052_${run_id}_data
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
  docker run --rm -i --name "$container" --network "${TM_S052_NETWORK:-host}" \
    -e HOST="${TM_S052_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e TM_UPGRADE_PHASE="${TM_UPGRADE_PHASE:-}" -e S021_PHASE="${S021_PHASE:-}" -e S052_PHASE="${S052_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" -d tm_s01_test_s021_s052 --workers=0 --max-cron-threads=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -70 "$results/$name.log"; return 1; }
  if rg -q ' [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -70 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
git -C "$repo" archive d7bb4c51c10b108c15a425540b39a790170f7a0f addons | tar -x -C "$work_dir"
TM_ADDONS_DIR="$work_dir/addons" step baseline run_odoo -i website,website_slides,training_management_sale --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/addons" TM_UPGRADE_PHASE=prepare step catalogue_prepare run_odoo shell --no-http < "$repo/tests/probes/catalogue_upgrade_probe.py"
TM_ADDONS_DIR="$work_dir/addons" S021_PHASE=prepare step documents_prepare run_odoo shell --no-http < "$repo/tests/probes/s021_history.py"
TM_ADDONS_DIR="$work_dir/addons" S052_PHASE=prepare step learning_prepare run_odoo shell --no-http < "$repo/tests/probes/s052_history.py"
step upgrade run_odoo -u training_management,training_management_sale --stop-after-init --test-enable --test-tags=/training_management,/training_management_sale
S021_PHASE=verify step documents_preserved run_odoo shell --no-http < "$repo/tests/probes/s021_history.py"
TM_UPGRADE_PHASE=verify step catalogue_preserved run_odoo shell --no-http < "$repo/tests/probes/catalogue_upgrade_probe.py"

S052_PHASE=verify step learning_preserved run_odoo shell --no-http < "$repo/tests/probes/s052_history.py"
step concurrency run_odoo shell --no-http < "$repo/tests/probes/s052_concurrency.py"
step reminder_concurrency run_odoo shell --no-http < "$repo/tests/probes/s052_reminder_concurrency.py"
S052_PHASE=french step french_prepare run_odoo shell --no-http < "$repo/tests/probes/s052_history.py"
step french_http run_odoo -u training_management --stop-after-init --test-enable --test-tags=/training_management:TestLearningHttp,/training_management:TestTrainingMaterialHttp
