#!/usr/bin/env bash
# V1 99c079a -> P09.1 and repeated update, isolated synthetic fixtures only.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the pinned image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/p09}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
container=tm_p09_${run_id}_odoo
volume=tm_p09_${run_id}_data
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
  docker run --rm -i --name "$container" --network "${TM_P09_NETWORK:-host}" \
    -e HOST="${TM_P09_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e P09_PHASE="${P09_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" -d "${TM_P09_DATABASE:-tm_s01_test_p09}" --workers=0 --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -70 "$results/$name.log"; return 1; }
  if rg -q ' CRITICAL | [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -70 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
git -C "$repo" archive 99c079a6fbc9158c39e6fcbcc907c6cebd45e48b addons | tar -x -C "$work_dir"
TM_ADDONS_DIR="$work_dir/addons" step baseline run_odoo -i training_management_sale,training_management_survey --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/addons" P09_PHASE=baseline step history_baseline run_odoo shell --no-http < "$repo/tests/probes/p09_history.py"
step upgrade run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=verify step history_preserved run_odoo shell --no-http < "$repo/tests/probes/p09_history.py"
step second_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=verify step repeated_history_preserved run_odoo shell --no-http < "$repo/tests/probes/p09_history.py"
P09_PHASE=prepare_path step path_baseline run_odoo shell --no-http < "$repo/tests/probes/p09_history.py"
step path_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=verify_path step path_preserved run_odoo shell --no-http < "$repo/tests/probes/p09_history.py"
P09_PHASE=concurrency step concurrency run_odoo shell --no-http < "$repo/tests/probes/p09_history.py"
