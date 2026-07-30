#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# run_all_rm1.sh — the single RunPod command. Runs bootstrap -> smoke ->
# verify smoke -> full -> verify full -> package, stopping on the first failure,
# then prints a consolidated summary.
#
#   nohup bash scripts/runpod_rm1/run_all_rm1.sh \
#     > /workspace/ugence_rm1/logs/run_all.nohup.log 2>&1 &
# ---------------------------------------------------------------------------
RM1_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${RM1_DIR}/common.sh"

FORCE_ARG=()
[[ "${1:-}" == "--force" ]] && FORCE_ARG=( --force )

rm1_require_model_id
rm1_make_dirs

banner "STAGE 1/6 — bootstrap"
bash "${RM1_DIR}/bootstrap_runpod.sh"

banner "STAGE 2/6 — smoke runs"
bash "${RM1_DIR}/run_rm1_smoke.sh" "${FORCE_ARG[@]}"

banner "STAGE 3/6 — verify smoke runs"
bash "${RM1_DIR}/verify_rm1_results.sh" "${RM1_RESULTS_DIR}/smoke_seed_${RM1_SEED}"
bash "${RM1_DIR}/verify_rm1_results.sh" "${RM1_RESULTS_DIR}/smoke_seed_${RM1_SECOND_SEED}"

banner "STAGE 4/6 — full run"
bash "${RM1_DIR}/run_rm1_full.sh" "${FORCE_ARG[@]}"

banner "STAGE 5/6 — verify full run"
bash "${RM1_DIR}/verify_rm1_results.sh" "${RM1_RESULTS_DIR}/latest_full"

banner "STAGE 6/6 — package"
bash "${RM1_DIR}/package_rm1_results.sh"

# ---- consolidated summary --------------------------------------------------
GIT_COMMIT="$(git -C "${UGENCE_REPO_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
GPU="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo unknown)"
LATEST_FULL="$(readlink -f "${RM1_RESULTS_DIR}/latest_full" 2>/dev/null || echo none)"
ARCHIVE="$(ls -t "${RM1_PACKAGES_DIR}"/rm1_results_*.tar.gz 2>/dev/null | head -1 || echo none)"
ARCHIVE_SHA="none"
[[ -f "${ARCHIVE}.sha256" ]] && ARCHIVE_SHA="$(awk '{print $1}' "${ARCHIVE}.sha256")"

smoke_status() {
  local s="$1"
  [[ -f "${RM1_RESULTS_DIR}/smoke_seed_${s}/.rm1_complete" ]] && echo "VERIFIED" || echo "MISSING"
}
FULL_STATUS="MISSING"
[[ -f "${RM1_RESULTS_DIR}/latest_full/.rm1_complete" ]] && FULL_STATUS="VERIFIED"

banner "RM1 RUN COMPLETE — SUMMARY"
echo "repository commit : ${GIT_COMMIT}"
echo "actual model id   : ${UGENCE_REAL_MODEL_ID}"
echo "model revision    : ${UGENCE_MODEL_REVISION:-<unset>}"
echo "GPU               : ${GPU}"
echo "smoke seed ${RM1_SEED}  : $(smoke_status "${RM1_SEED}")"
echo "smoke seed ${RM1_SECOND_SEED}  : $(smoke_status "${RM1_SECOND_SEED}")"
echo "full run          : ${FULL_STATUS}"
echo "latest results    : ${LATEST_FULL}"
echo "archive           : ${ARCHIVE}"
echo "archive sha256    : ${ARCHIVE_SHA}"
echo
echo "acceptance summary (latest full):"
if [[ -f "${RM1_RESULTS_DIR}/latest_full/rm1_scorecard.txt" ]]; then
  sed 's/^/  /' "${RM1_RESULTS_DIR}/latest_full/rm1_scorecard.txt"
else
  echo "  (no scorecard found)"
fi
