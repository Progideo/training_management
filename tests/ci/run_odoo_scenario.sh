#!/usr/bin/env bash
# Four independent jobs; operations within a scenario remain sequential.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo"
scenario=${1:?Usage: run_odoo_scenario.sh incremental|fresh|history|website}
case "$scenario" in incremental|fresh|history|website) ;; *) echo "Unknown scenario: $scenario" >&2; exit 2;; esac
: "${ODOO_IMAGE:?Use the pinned Odoo image from the workflow}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/$scenario}
mkdir -p "$results"
results=$(cd "$results" && pwd)
work_dir=$(mktemp -d)
volume=tm_ci_${run_id}_${scenario}
container=${volume}_odoo
printf 'step\texit_code\tduration_seconds\n' > "$results/timings.tsv"
cleanup() {
  rc=$?
  trap - EXIT
  docker rm -f "$container" > "$results/container-cleanup.log" 2>&1 || true
  if ! docker volume rm "$volume" > "$results/volume-cleanup.log" 2>&1; then
    # A failure before the first Docker call creates no volume.
    if docker volume inspect "$volume" > /dev/null 2>&1; then rc=1; fi
  fi
  rm -rf "$work_dir"
  exit "$rc"
}
trap cleanup EXIT
run_odoo() {
  docker run --rm -i --name "$container" --network host \
    -e HOST=127.0.0.1 -e PORT=5432 -e USER=odoo \
    -e PASSWORD=fictional_ci_password \
    -e TM_UPGRADE_PHASE="${TM_UPGRADE_PHASE:-}" \
    -e S03_UPGRADE_PHASE="${S03_UPGRADE_PHASE:-}" \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" \
    -v "$volume:/var/lib/odoo" \
    "$ODOO_IMAGE" odoo "$@" \
    --db_host=127.0.0.1 --db_port=5432 \
    --db_user=odoo --db_password=fictional_ci_password \
    -d "${TM_TEST_DB:-tm_s01_test_ci}" --no-http --http-interface=127.0.0.1 --http-port=0 \
    --workers=0 --max-cron-threads=0
}
run_step() {
  local step=$1 start rc
  local -a pipeline
  shift
  start=$(date +%s)
  set +e
  "$@" 2>&1 | tee "$results/$step.log"
  pipeline=("${PIPESTATUS[@]}")
  set -e
  rc=${pipeline[0]}
  if [ "${pipeline[1]}" != 0 ]; then rc=${pipeline[1]}; fi
  printf '%s\t%s\t%s\n' "$step" "$rc" "$(( $(date +%s) - start ))" >> "$results/timings.tsv"
  return "$rc"
}
case "$scenario" in
  incremental)
    run_step install run_odoo \
      -i training_management --without-demo --stop-after-init --test-enable --test-tags=/training_management
    TM_UPGRADE_PHASE=prepare run_step baseline run_odoo shell < tests/probes/catalogue_upgrade_probe.py
    run_step update run_odoo \
      -u training_management --stop-after-init --test-enable --test-tags=/training_management
    TM_UPGRADE_PHASE=verify run_step history run_odoo shell < tests/probes/catalogue_upgrade_probe.py
    run_step commercial-install run_odoo \
      -i training_management_sale --without-demo --stop-after-init --test-enable --test-tags=/training_management_sale
    run_step commercial-concurrency run_odoo \
      shell < addons/training_management_sale/tests/probes/bank_reference_concurrency.py
    ;;
  fresh)
    TM_TEST_DB=tm_s03_test_fresh_ci run_step commercial-fresh-install run_odoo \
      -i training_management_sale --without-demo --stop-after-init --test-enable --test-tags=/training_management_sale
    TM_TEST_DB=tm_s03_test_fresh_ci run_step s03-concurrency run_odoo shell < tests/probes/s03_concurrency.py
    ;;
  history)
    mkdir -p "$work_dir/s02-baseline"
    git archive a0c95fa5076b3e2177ff9948d9fc0306e729df86 addons | tar -x -C "$work_dir/s02-baseline"
    TM_TEST_DB=tm_s03_test_upgrade_ci TM_ADDONS_DIR="${work_dir}/s02-baseline/addons" run_step s03-old-install run_odoo \
      -i website,website_slides,training_management_sale --without-demo --stop-after-init
    TM_TEST_DB=tm_s03_test_upgrade_ci TM_ADDONS_DIR="${work_dir}/s02-baseline/addons" S03_UPGRADE_PHASE=prepare run_step s03-history-prepare run_odoo \
      shell < tests/probes/s03_history.py
    TM_TEST_DB=tm_s03_test_upgrade_ci run_step s03-view-bootstrap run_odoo \
      shell < tests/probes/s03_view_bootstrap.py
    TM_TEST_DB=tm_s03_test_upgrade_ci run_step s03-upgrade-tests run_odoo \
      -u training_management,training_management_sale --stop-after-init --test-enable --test-tags=/training_management,/training_management_sale
    TM_TEST_DB=tm_s03_test_upgrade_ci S03_UPGRADE_PHASE=verify run_step s03-history-verify run_odoo \
      shell < tests/probes/s03_history.py
    TM_TEST_DB=tm_s03_test_upgrade_ci S03_UPGRADE_PHASE=prepare_s03 run_step s03-update-prepare run_odoo \
      shell < tests/probes/s03_history.py
    TM_TEST_DB=tm_s03_test_upgrade_ci run_step s03-update run_odoo \
      -u training_management,training_management_sale --stop-after-init
    TM_TEST_DB=tm_s03_test_upgrade_ci S03_UPGRADE_PHASE=verify_s03 run_step s03-update-verify run_odoo \
      shell < tests/probes/s03_history.py
    ;;
  website)
    TM_TEST_DB=tm_s01_test_website_ci run_step website-baseline-install run_odoo \
      -i website,website_slides,training_management --without-demo --stop-after-init
    TM_TEST_DB=tm_s01_test_website_ci TM_UPGRADE_PHASE=prepare run_step website-baseline run_odoo \
      shell < tests/probes/catalogue_upgrade_probe.py
    TM_TEST_DB=tm_s01_test_website_ci run_step website-commercial-install run_odoo \
      -i training_management_sale --without-demo --stop-after-init --test-enable --test-tags=/training_management_sale
    TM_TEST_DB=tm_s01_test_website_ci run_step website-commercial-update run_odoo \
      -u training_management_sale --stop-after-init --test-enable --test-tags=/training_management_sale
    TM_TEST_DB=tm_s01_test_website_ci TM_UPGRADE_PHASE=verify run_step website-history run_odoo \
      shell < tests/probes/catalogue_upgrade_probe.py
    ;;
esac
