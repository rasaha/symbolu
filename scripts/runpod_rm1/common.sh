#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# common.sh — shared configuration, defaults, directory contract and helpers
# for the RM1 RunPod execution scripts. Sourced by every other script.
#
# It NEVER runs the experiment and NEVER modifies the frozen RM1 harness. It only
# resolves the environment, prepares the persistent /workspace layout, and provides
# logging / verification helpers. HF_TOKEN is never echoed or logged.
# ---------------------------------------------------------------------------

# ---- locate this script directory (works when sourced) --------------------
RM1_COMMON_SOURCE="${BASH_SOURCE[0]}"
RM1_SCRIPT_DIR="$(cd "$(dirname "${RM1_COMMON_SOURCE}")" && pwd)"

# ---- optionally source a local, non-committed env file --------------------
# Precedence: $RUNPOD_ENV_FILE, then scripts/runpod_rm1/env.local
if [[ -n "${RUNPOD_ENV_FILE:-}" && -f "${RUNPOD_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${RUNPOD_ENV_FILE}"
elif [[ -f "${RM1_SCRIPT_DIR}/env.local" ]]; then
  # shellcheck disable=SC1091
  source "${RM1_SCRIPT_DIR}/env.local"
fi

# ---- repository ------------------------------------------------------------
: "${UGENCE_REPO_URL:=}"
: "${UGENCE_REPO_DIR:=/workspace/ugence}"
: "${UGENCE_BRANCH:=claude/rm1-real-model-validation-yfn2gx}"

# ---- model (required; NO fake default) ------------------------------------
: "${UGENCE_REAL_MODEL_ID:=}"
: "${UGENCE_MODEL_REVISION:=}"   # recommended, not required

# ---- output root + persistent layout --------------------------------------
: "${RM1_OUTPUT_ROOT:=/workspace/ugence_rm1}"
RM1_VENV_DIR="${RM1_OUTPUT_ROOT}/venv"
RM1_HF_CACHE_DIR="${RM1_OUTPUT_ROOT}/cache/huggingface"
RM1_LOG_DIR="${RM1_OUTPUT_ROOT}/logs"
RM1_RESULTS_DIR="${RM1_OUTPUT_ROOT}/results"
RM1_PACKAGES_DIR="${RM1_OUTPUT_ROOT}/packages"
RM1_STATE_DIR="${RM1_OUTPUT_ROOT}/state"
RM1_MANIFEST="${RM1_OUTPUT_ROOT}/runtime_manifest.txt"

# ---- run knobs -------------------------------------------------------------
: "${RM1_DEVICE:=cuda}"
: "${RM1_DTYPE:=auto}"
: "${RM1_LOAD_IN_4BIT:=0}"
: "${RM1_MAX_INPUT_TOKENS:=4096}"
: "${RM1_MAX_NEW_TOKENS:=512}"
: "${RM1_SMOKE_LIMIT:=10}"
: "${RM1_FULL_LIMIT:=}"            # empty => full held-out set (harness default)
: "${RM1_SEED:=101}"
: "${RM1_SECOND_SEED:=202}"
: "${RM1_CLARIFICATION_LIMIT:=1}"

# ---- harness locations (frozen; consumed, never modified) -----------------
RM1_MODULE="experiments.hybrid_token_event_attention.real_model.run_real_model"
RM1_REPO_RESULTS_REL="experiments/hybrid_token_event_attention/real_model/results"
RM1_REPO_QUAR_REL="experiments/hybrid_token_event_attention/real_model/quarantine"
RM1_CANONICAL_JSON_REL="experiments/hybrid_token_event_attention/HYBRID_TOKEN_EVENT_ATTENTION_RESULTS.json"
RM1_CANONICAL_JSON2_REL="experiments/hybrid_token_event_attention/results/HYBRID_TOKEN_EVENT_ATTENTION_RESULTS.json"
RM1_CANONICAL_HASH="ea1e8e0202b00bec5bcaabace6ddb9e69c5670ded2d3f4228bbf771cf0ae45de"

# the five generated artifact files the harness writes in-repo
RM1_ARTIFACTS=(
  "REAL_MODEL_RESULTS.json"
  "REAL_MODEL_TRACES.jsonl"
  "REAL_MODEL_VALIDATION_REPORT.md"
  "RESOURCE_MANIFEST.json"
)
RM1_QUAR_ARTIFACT="QUARANTINE.jsonl"

# ---- logging helpers -------------------------------------------------------
_c_ts() { date -u +%Y%m%dT%H%M%SZ; }
log()    { printf '[%s] %s\n' "$(_c_ts)" "$*"; }
banner() {
  printf '\n============================================================\n'
  printf '  %s\n' "$*"
  printf '============================================================\n'
}
die() { printf '\n[FATAL] %s\n' "$*" >&2; exit 1; }

# ---- python resolver -------------------------------------------------------
rm1_python() {
  if [[ -x "${RM1_VENV_DIR}/bin/python" ]]; then
    printf '%s' "${RM1_VENV_DIR}/bin/python"
  else
    command -v python3 || command -v python || die "no python interpreter found"
  fi
}

# ---- directory setup -------------------------------------------------------
rm1_make_dirs() {
  mkdir -p "${RM1_OUTPUT_ROOT}" "${RM1_HF_CACHE_DIR}" "${RM1_LOG_DIR}" \
           "${RM1_RESULTS_DIR}" "${RM1_PACKAGES_DIR}" "${RM1_STATE_DIR}"
}

# ---- runtime environment for the harness ----------------------------------
rm1_export_runtime_env() {
  export PYTHONPATH="${UGENCE_REPO_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
  export HF_HOME="${RM1_HF_CACHE_DIR}"
  export HUGGINGFACE_HUB_CACHE="${RM1_HF_CACHE_DIR}/hub"
  export TRANSFORMERS_CACHE="${RM1_HF_CACHE_DIR}/transformers"
  export TOKENIZERS_PARALLELISM="false"
  # transformers/huggingface_hub read HF_TOKEN / HUGGING_FACE_HUB_TOKEN from the env.
  # We pass it through WITHOUT ever printing it.
  if [[ -n "${HF_TOKEN:-}" ]]; then
    export HF_TOKEN
    export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"
  fi
}

# ---- required-variable validation -----------------------------------------
rm1_require_model_id() {
  [[ -n "${UGENCE_REAL_MODEL_ID}" ]] || die \
    "UGENCE_REAL_MODEL_ID is required (a real Hugging Face model id or local dir). No fake default is provided."
}

# ---- build the common harness CLI args (associative-free, array based) -----
# usage: rm1_build_common_args <mode> <limit-or-empty> <seed> <output-dir>
rm1_build_common_args() {
  local mode="$1" limit="$2" seed="$3" outdir="$4"
  RM1_CLI_ARGS=(
    -m "${RM1_MODULE}"
    --model-id "${UGENCE_REAL_MODEL_ID}"
    --mode "${mode}"
    --seed "${seed}"
    --device "${RM1_DEVICE}"
    --dtype "${RM1_DTYPE}"
    --max-input-tokens "${RM1_MAX_INPUT_TOKENS}"
    --max-new-tokens "${RM1_MAX_NEW_TOKENS}"
    --clarification-limit "${RM1_CLARIFICATION_LIMIT}"
    --output-dir "${outdir}"
  )
  [[ -n "${UGENCE_MODEL_REVISION}" ]] && RM1_CLI_ARGS+=( --revision "${UGENCE_MODEL_REVISION}" )
  [[ -n "${limit}" ]] && RM1_CLI_ARGS+=( --limit "${limit}" )
  [[ "${RM1_LOAD_IN_4BIT}" == "1" ]] && RM1_CLI_ARGS+=( --load-in-4bit )
}

# ---- copy the in-repo artifacts into a run dir ----------------------------
rm1_copy_artifacts() {
  local dest="$1"
  mkdir -p "${dest}"
  local src_results="${UGENCE_REPO_DIR}/${RM1_REPO_RESULTS_REL}"
  local src_quar="${UGENCE_REPO_DIR}/${RM1_REPO_QUAR_REL}"
  local f
  for f in "${RM1_ARTIFACTS[@]}"; do
    [[ -f "${src_results}/${f}" ]] && cp -f "${src_results}/${f}" "${dest}/${f}"
  done
  [[ -f "${src_quar}/${RM1_QUAR_ARTIFACT}" ]] && cp -f "${src_quar}/${RM1_QUAR_ARTIFACT}" "${dest}/${RM1_QUAR_ARTIFACT}"
}

# ---- restore the in-repo generated artifacts to their committed state ------
# keeps the working tree clean so bootstrap's clean-tree invariant holds across runs.
rm1_restore_repo_tree() {
  local git_dir="${UGENCE_REPO_DIR}"
  [[ -d "${git_dir}/.git" ]] || return 0
  local paths=()
  local f
  for f in "${RM1_ARTIFACTS[@]}"; do paths+=( "${RM1_REPO_RESULTS_REL}/${f}" ); done
  paths+=( "${RM1_REPO_QUAR_REL}/${RM1_QUAR_ARTIFACT}" )
  git -C "${git_dir}" checkout -- "${paths[@]}" 2>/dev/null || true
}

# ---- canonical-hash guard --------------------------------------------------
rm1_check_canonical_hash() {
  local git_dir="${UGENCE_REPO_DIR}"
  local jf="${git_dir}/${RM1_CANONICAL_JSON_REL}"
  [[ -f "${jf}" ]] || die "canonical results JSON missing: ${jf}"
  local got
  got="$(sha256sum "${jf}" | awk '{print $1}')"
  [[ "${got}" == "${RM1_CANONICAL_HASH}" ]] || die \
    "canonical controlled-result hash CHANGED: got ${got} expected ${RM1_CANONICAL_HASH}"
  log "canonical controlled-result hash unchanged (${RM1_CANONICAL_HASH})"
}

# ---- git clean-tree guard (ignoring the generated artifact paths) ----------
rm1_require_clean_tree() {
  local git_dir="${UGENCE_REPO_DIR}"
  rm1_restore_repo_tree
  local dirty
  dirty="$(git -C "${git_dir}" status --porcelain)"
  if [[ -n "${dirty}" ]]; then
    printf '%s\n' "${dirty}" >&2
    die "working tree is not clean at ${git_dir} (commit/stash unrelated changes first)"
  fi
}
