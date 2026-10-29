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
pdf_container=tm_p09_${run_id}_pdf
volume=tm_p09_${run_id}_data
report_url="http://$pdf_container:8069"
if [[ "${TM_P09_NETWORK:-host}" == host ]]; then report_url=http://127.0.0.1:8069; fi
cleanup() {
  rc=$?
  trap - EXIT
  docker rm -f "$container" > "$results/container-cleanup.log" 2>&1 || true
  docker rm -f "$pdf_container" > "$results/pdf-container-cleanup.log" 2>&1 || true
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
    -e P09_REPORT_URL="$report_url" \
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
P09_PHASE=portal step portal_readonly run_odoo shell --no-http < "$repo/tests/probes/p09_history.py"
P09_PHASE=commerce_prepare step commerce_baseline run_odoo shell --no-http < "$repo/tests/probes/p093_commerce.py"
step commerce_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=commerce_verify step commerce_preserved run_odoo shell --no-http < "$repo/tests/probes/p093_commerce.py"
# The PDF engine fetches native report assets from a real disposable HTTP
# process, rather than forcing network rendering inside a TransactionCase.
docker run -d --name "$pdf_container" --network "${TM_P09_NETWORK:-host}" \
  -e HOST="${TM_P09_DB_HOST:-127.0.0.1}" -e USER=odoo -e PASSWORD=fictional_ci_password \
  -v "$repo/addons:/mnt/extra-addons:ro" -v "$volume:/var/lib/odoo" \
  "$ODOO_IMAGE" odoo -d "${TM_P09_DATABASE:-tm_s01_test_p09}" --workers=0 --max-cron-threads=0 \
  --http-interface=0.0.0.0 --http-port=8069 > "$results/pdf-server.log"
pdf_ready=false
for _ in $(seq 1 60); do
  if docker exec "$pdf_container" python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8069/web/login', timeout=2)" > /dev/null 2>&1; then pdf_ready=true; break; fi
  sleep 1
done
[[ "$pdf_ready" == true ]] || { docker logs "$pdf_container"; exit 1; }
P09_PHASE=commerce_pdf step commerce_pdf run_odoo shell --no-http < "$repo/tests/probes/p093_commerce.py"
docker cp "$pdf_container:/var/lib/odoo/p093-quotation.pdf" "$results/p093-quotation.pdf"
docker rm -f "$pdf_container" > "$results/pdf-server-stop.log"
P09_PHASE=commerce_concurrency step commerce_concurrency run_odoo shell --no-http < "$repo/tests/probes/p093_commerce.py"
P09_PHASE=orientation_prepare step orientation_baseline run_odoo shell --no-http < "$repo/tests/probes/p10_orientation.py"
step orientation_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=orientation_verify step orientation_preserved run_odoo shell --no-http < "$repo/tests/probes/p10_orientation.py"
P09_PHASE=practice_prepare step practice_baseline run_odoo shell --no-http < "$repo/tests/probes/p11_practice.py"
step practice_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=practice_verify step practice_preserved run_odoo shell --no-http < "$repo/tests/probes/p11_practice.py"
step practice_second_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=practice_verify step practice_repeated_preserved run_odoo shell --no-http < "$repo/tests/probes/p11_practice.py"
P09_PHASE=practice_concurrency step practice_concurrency run_odoo shell --no-http < "$repo/tests/probes/p11_practice.py"
P09_PHASE=project_prepare step project_baseline run_odoo shell --no-http < "$repo/tests/probes/p12_project.py"
step project_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=project_verify step project_preserved run_odoo shell --no-http < "$repo/tests/probes/p12_project.py"
step project_second_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=project_verify step project_repeated_preserved run_odoo shell --no-http < "$repo/tests/probes/p12_project.py"
P09_PHASE=project_concurrency step project_concurrency run_odoo shell --no-http < "$repo/tests/probes/p12_project.py"
P09_PHASE=tutoring_prepare step tutoring_baseline run_odoo shell --no-http < "$repo/tests/probes/p13_tutoring.py"
step tutoring_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=tutoring_verify step tutoring_preserved run_odoo shell --no-http < "$repo/tests/probes/p13_tutoring.py"
step tutoring_second_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=tutoring_verify step tutoring_repeated_preserved run_odoo shell --no-http < "$repo/tests/probes/p13_tutoring.py"
P09_PHASE=tutoring_concurrency step tutoring_concurrency run_odoo shell --no-http < "$repo/tests/probes/p13_tutoring.py"
P09_PHASE=publication_prepare step publication_baseline run_odoo shell --no-http < "$repo/tests/probes/p14_publication.py"
step publication_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=publication_verify step publication_preserved run_odoo shell --no-http < "$repo/tests/probes/p14_publication.py"
step publication_second_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=publication_verify step publication_repeated_preserved run_odoo shell --no-http < "$repo/tests/probes/p14_publication.py"
P09_PHASE=publication_concurrency step publication_concurrency run_odoo shell --no-http < "$repo/tests/probes/p14_publication.py"
P09_PHASE=sessions_prepare step sessions_baseline run_odoo shell --no-http < "$repo/tests/probes/p16_sessions.py"
step sessions_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=sessions_verify step sessions_preserved run_odoo shell --no-http < "$repo/tests/probes/p16_sessions.py"
step sessions_second_update run_odoo -u training_management,training_management_sale,training_management_survey --stop-after-init
P09_PHASE=sessions_verify step sessions_repeated_preserved run_odoo shell --no-http < "$repo/tests/probes/p16_sessions.py"
P09_PHASE=sessions_concurrency step sessions_concurrency run_odoo shell --no-http < "$repo/tests/probes/p16_sessions.py"
