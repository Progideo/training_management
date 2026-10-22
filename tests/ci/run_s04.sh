#!/usr/bin/env bash
# S03.1 -> S04: persisted history, real Odoo tests and concurrent reservations.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the workflow pinned image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/s04}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
container=tm_s04_${run_id}_odoo
volume=tm_s04_${run_id}_data
cleanup() {
  rc=$?
  trap - EXIT
  docker rm -f "$container" > "$results/container-cleanup.log" 2>&1 || true
  docker volume rm "$volume" > "$results/volume-cleanup.log" 2>&1 || true
  rm -rf "$work_dir"
  exit "$rc"
}
trap cleanup EXIT
run_odoo() {
  docker run --rm -i --name "$container" --network "${TM_S04_NETWORK:-host}" \
    -e HOST="${TM_S04_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e S04_PHASE="${S04_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" -d "${TM_S04_DB:-tm_s04_test_upgrade}" --workers=0 --max-cron-threads=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -70 "$results/$name.log"; return 1; }
  if rg -q ' [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -70 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
mkdir -p "$work_dir/s031"
git -C "$repo" archive 7fc2318d1bcfc13bce44be3181d2a1f45c8e33fc addons | tar -x -C "$work_dir/s031"
TM_ADDONS_DIR="$work_dir/s031/addons" step baseline run_odoo -i training_management_sale --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/s031/addons" S04_PHASE=prepare step prepare run_odoo shell --no-http < "$repo/tests/probes/s04_history.py"
step upgrade run_odoo -u training_management,training_management_sale --stop-after-init --test-enable --test-tags=/training_management,/training_management_sale
S04_PHASE=verify step history run_odoo shell --no-http < "$repo/tests/probes/s04_history.py"
step concurrency run_odoo shell --no-http < "$repo/tests/probes/s04_concurrency.py"

# Upgrade a persisted pre-review S04 queue as well as the S03.1 baseline.
mkdir -p "$work_dir/s04_review"
review_ref=70b91ae1ea088c652353009b7f618d58dcc124f0
if ! git -C "$repo" cat-file -e "$review_ref^{commit}" 2>/dev/null; then
  git -C "$repo" fetch --no-tags origin "$review_ref"
fi
git -C "$repo" archive "$review_ref" addons | tar -x -C "$work_dir/s04_review"
TM_S04_DB=tm_s04_test_dispatch TM_ADDONS_DIR="$work_dir/s04_review/addons" step dispatch_baseline run_odoo -i training_management --without-demo --stop-after-init
TM_S04_DB=tm_s04_test_dispatch TM_ADDONS_DIR="$work_dir/s04_review/addons" S04_PHASE=prepare step dispatch_prepare run_odoo shell --no-http < "$repo/tests/probes/s04_dispatch_upgrade.py"
TM_S04_DB=tm_s04_test_dispatch step dispatch_upgrade run_odoo -u training_management --stop-after-init
TM_S04_DB=tm_s04_test_dispatch S04_PHASE=verify step dispatch_history run_odoo shell --no-http < "$repo/tests/probes/s04_dispatch_upgrade.py"
