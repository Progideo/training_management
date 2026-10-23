#!/usr/bin/env bash
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${ODOO_IMAGE:?Use the pinned Community image}"
run_id=${TM_CI_ID:-local_$$}
[[ "$run_id" =~ ^[a-zA-Z0-9_]+$ ]] || exit 2
results=${TM_RESULTS_DIR:-$repo/test-results/catalogue-pdf}
mkdir -p "$results"
results=$(cd "$results" && pwd)
# The image's odoo UID differs from the Linux runner UID. Only this
# disposable, fictional PDF artifact directory is container-writable.
mkdir -p "$results/pdfs"
chmod 0777 "$results/pdfs"
work_dir=$(mktemp -d)
container=tm_catpdf_${run_id}_odoo
volume=tm_catpdf_${run_id}_data
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
  docker run --rm -i --name "$container" --network "${TM_CATPDF_NETWORK:-host}" \
    -e HOST="${TM_CATPDF_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
    -e CATALOGUE_PHASE="${CATALOGUE_PHASE:-}" -e CATALOGUE_PDF_PROOFS=/proofs/pdfs \
    -v "${TM_ADDONS_DIR:-$repo/addons}:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" -v "$results:/proofs" \
    "$ODOO_IMAGE" odoo "$@" -d "${TM_CATPDF_DB:-tm_catpdf_test_upgrade}" --workers=0 --max-cron-threads=0
}
step() {
  local name=$1
  shift
  "$@" > "$results/$name.log" 2>&1 || { tail -60 "$results/$name.log"; return 1; }
  if rg -q ' [1-9][0-9]* failed,| [1-9][0-9]* error\(s\)' "$results/$name.log"; then tail -60 "$results/$name.log"; return 1; fi
  printf '%s OK\n' "$name"
}
git -C "$repo" archive 2d42f8dd1b8431dd25507a494e97cb5df9011504 addons | tar -x -C "$work_dir"
baseline_modules=training_management_sale
if [[ "${TM_CATPDF_WITH_WEBSITE:-false}" == true ]]; then baseline_modules=website,training_management_sale; fi
TM_ADDONS_DIR="$work_dir/addons" step baseline run_odoo -i "$baseline_modules" --without-demo --stop-after-init
TM_ADDONS_DIR="$work_dir/addons" CATALOGUE_PHASE=prepare step prepare run_odoo shell --no-http < "$repo/tests/probes/catalogue_pdf_history.py"
step upgrade run_odoo -u training_management,training_management_sale --stop-after-init --test-enable --test-tags=/training_management:TestProgrammePdf,/training_management:TestProgrammePdfHttp
CATALOGUE_PHASE=verify step history run_odoo shell --no-http < "$repo/tests/probes/catalogue_pdf_history.py"
step repeat_upgrade run_odoo -u training_management,training_management_sale --stop-after-init
CATALOGUE_PHASE=repeat step preserved_pdf run_odoo shell --no-http < "$repo/tests/probes/catalogue_pdf_history.py"
CATALOGUE_PHASE=concurrency step concurrency run_odoo shell --no-http < "$repo/tests/probes/catalogue_pdf_history.py"
