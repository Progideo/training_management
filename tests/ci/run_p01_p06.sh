#!/usr/bin/env bash
# main 1db3b95 -> P01–P06 and repeated update, isolated synthetic fixtures only.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the pinned image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/p01p06}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
container=tm_p01p06_${run_id}_odoo
volume=tm_p01p06_${run_id}_data
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
  docker run --rm -i --name "$container" --network "${TM_P01P06_NETWORK:-host}" \
    -e HOST="${TM_P01P06_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e P01P06_PHASE="${P01P06_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" -d "${TM_P01P06_DATABASE:-tm_s01_test_p01p06}" --workers=0 --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -70 "$results/$name.log"; return 1; }
  if rg -q ' CRITICAL | [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -70 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
git -C "$repo" archive 1db3b95bd789d7b7dacf8e42e7e3053aa5e8e1dd addons | tar -x -C "$work_dir"
TM_ADDONS_DIR="$work_dir/addons" step baseline run_odoo -i website,website_slides,training_management_sale,training_management_survey --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/addons" P01P06_PHASE=baseline step history_baseline run_odoo shell --no-http < "$repo/tests/probes/p01p06_history.py"
step upgrade run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P01P06_PHASE=verify step history_preserved run_odoo shell --no-http < "$repo/tests/probes/p01p06_history.py"
step second_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P01P06_PHASE=verify step repeated_history_preserved run_odoo shell --no-http < "$repo/tests/probes/p01p06_history.py"
P01P06_PHASE=concurrency step concurrency run_odoo shell --no-http < "$repo/tests/probes/p01p06_history.py"
