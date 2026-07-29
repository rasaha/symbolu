#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# run_rm1_full.sh — the full held-out actual-model run. Runs ONLY after both
# smoke runs are verified. Writes to results/full_<UTC>, points latest_full at
# it, and never overwrites an already-completed full run.
# ---------------------------------------------------------------------------
RM1_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${RM1_DIR}/common.sh"

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

rm1_require_model_id
rm1_make_dirs
rm1_export_runtime_env
PY="$(rm1_python)"

# require both smoke runs verified
for s in "${RM1_SEED}" "${RM1_SECOND_SEED}"; do
  [[ -f "${RM1_RESULTS_DIR}/smoke_seed_${s}/.rm1_complete" ]] \
    || die "smoke seed ${s} not verified — run run_rm1_smoke.sh first"
done

# never overwrite a completed full run
LATEST="${RM1_RESULTS_DIR}/latest_full"
if [[ -L "${LATEST}" && -f "${LATEST}/.rm1_complete" && "${FORCE}" -ne 1 ]]; then
  log "a completed full run already exists at $(readlink -f "${LATEST}"); not overwriting."
  log "pass --force to run a new full run into a fresh timestamped directory."
  exit 0
fi

STAMP="$(_c_ts)"
RUN_DIR="${RM1_RESULTS_DIR}/full_${STAMP}"
mkdir -p "${RUN_DIR}"
LOGF="${RM1_LOG_DIR}/full_${STAMP}.log"

banner "FULL run seed=${RM1_SEED} -> ${RUN_DIR}"

# --limit only when RM1_FULL_LIMIT explicitly set
rm1_build_common_args "full" "${RM1_FULL_LIMIT}" "${RM1_SEED}" "${RUN_DIR}"
# use --resume (accepted by the harness); the event architecture is never retrained here
RM1_CLI_ARGS+=( --resume )
log "invoking: python ${RM1_CLI_ARGS[*]}   (HF_TOKEN never shown)"

set +e
( cd "${UGENCE_REPO_DIR}" && "${PY}" "${RM1_CLI_ARGS[@]}" ) 2>&1 | tee "${LOGF}"
rc=${PIPESTATUS[0]}
set -e
[[ "${rc}" -eq 0 ]] || die "full harness exited ${rc} (expected 0 COMPLETED). See ${LOGF}"

rm1_copy_artifacts "${RUN_DIR}"
rm1_restore_repo_tree

# verify the full run
bash "${RM1_DIR}/verify_rm1_results.sh" "${RUN_DIR}" | tee "${RUN_DIR}/verify_full.log"

touch "${RUN_DIR}/.rm1_complete"
ln -sfn "${RUN_DIR}" "${LATEST}"
log "full run complete + verified -> ${RUN_DIR}"
log "latest_full -> ${RUN_DIR}"
banner "FULL run done"
