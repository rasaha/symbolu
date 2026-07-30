#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# run_rm1_smoke.sh — two actual-model smoke runs (seeds RM1_SEED and
# RM1_SECOND_SEED), stored separately, each hard-verified as a real-model run.
# Skips an already-completed smoke run unless --force is given.
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

run_one_smoke() {
  local seed="$1" limit="$2"
  local run_dir="${RM1_RESULTS_DIR}/smoke_seed_${seed}"
  local marker="${run_dir}/.rm1_complete"
  local logf="${RM1_LOG_DIR}/smoke_seed_${seed}_$(_c_ts).log"

  banner "SMOKE seed=${seed} limit=${limit} -> ${run_dir}"
  if [[ -f "${marker}" && "${FORCE}" -ne 1 ]]; then
    log "already complete (marker present); skipping. Use --force to re-run."
    return 0
  fi
  mkdir -p "${run_dir}"

  rm1_build_common_args "smoke" "${limit}" "${seed}" "${run_dir}"
  log "invoking: python ${RM1_CLI_ARGS[*]}   (HF_TOKEN never shown)"

  set +e
  ( cd "${UGENCE_REPO_DIR}" && "${PY}" "${RM1_CLI_ARGS[@]}" ) 2>&1 | tee "${logf}"
  local rc=${PIPESTATUS[0]}
  set -e
  [[ "${rc}" -eq 0 ]] || die "harness exited ${rc} (expected 0 COMPLETED) for seed ${seed}. See ${logf}"

  rm1_copy_artifacts "${run_dir}"
  rm1_restore_repo_tree

  # hard verification of this smoke run (real-model gates)
  RM1_VERIFY_MODE="smoke" bash "${RM1_DIR}/verify_rm1_results.sh" "${run_dir}" \
    | tee "${run_dir}/verify_smoke.log"
  touch "${marker}"
  log "smoke seed=${seed} VERIFIED -> ${run_dir}"
}

run_one_smoke "${RM1_SEED}" "${RM1_SMOKE_LIMIT}"
run_one_smoke "${RM1_SECOND_SEED}" "20"

banner "both smoke runs complete + verified"
