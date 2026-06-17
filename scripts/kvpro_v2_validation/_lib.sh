#!/usr/bin/env bash
# Shared helpers for the KVPro v2 RunPod validation harness.
# Sourced by every NN_*.sh script. Pure orchestration: it never fabricates a
# result and never prints a projected value as if it were measured.
set -uo pipefail

# --- paths ---------------------------------------------------------------- #
KVPRO_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$KVPRO_LIB_DIR/../.." && pwd)"
export REPO
# kv_policy lives under CTM_plus/KVPolicy; ndol + repo-root scripts under REPO.
export PYTHONPATH="$REPO/CTM_plus/KVPolicy:$REPO:${PYTHONPATH:-}"

# --- run directory (timestamped) ----------------------------------------- #
kvpro_run_dir() {
  if [[ -z "${KVPRO_RUN_DIR:-}" ]]; then
    local ts; ts="$(date -u +%Y%m%dT%H%M%SZ)"
    KVPRO_RUN_DIR="$REPO/runs/kvpro_v2/$ts"
    mkdir -p "$KVPRO_RUN_DIR"
    export KVPRO_RUN_DIR
  fi
  echo "$KVPRO_RUN_DIR"
}

# --- logging -------------------------------------------------------------- #
_c() { printf '%s' "${1:-}"; }              # color stub (kept plain for log files)
log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
ok()   { echo "  [PASS] $*"; }
fail() { echo "  [FAIL] $*" >&2; }
warn() { echo "  [WARN] $*" >&2; }
note() { echo "  [NOTE] $*"; }
hr()   { printf '%.0s=' {1..72}; echo; }
section() { echo; hr; echo "== $*"; hr; }

# Honesty banner reused across scripts that touch throughput.
ceiling_note() {
  note "Decode-throughput recovery has a BOUNDED ceiling (~0.27-0.30x of full"
  note "precision, PROJECTED) and NEVER reaches full-precision parity. The"
  note "numbers below are MEASURED on THIS run; the ceiling is context, not a result."
}

# --- environment probes --------------------------------------------------- #
gpu_count() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l | tr -d ' '
  else
    echo 0
  fi
}

# Hard requirement: the int4 decode fork must import, or no decode/serving test
# may run. Returns 0 if importable, 1 otherwise (prints the exact import).
have_int4_kernel() {
  python3 - <<'PY' 2>/dev/null
import sys
try:
    from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache  # noqa: F401
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
}

mask_path_ok() {
  [[ -n "${PROTECT_MASK_PATH:-}" && -f "${PROTECT_MASK_PATH:-/nonexistent}" ]]
}

# Print the exact command to create a mask for $1 (model) -> $2 (output path).
print_mask_howto() {
  local model="${1:-<MODEL>}" out="${2:-/workspace/dev/build-logs/protect_mask.pt}"
  warn "PROTECT_MASK_PATH is unset or the file does not exist."
  warn "Create one with:"
  echo  "    bash $KVPRO_LIB_DIR/01_calibrate_mask.sh '$model' '$out'"
  echo  "    export PROTECT_MASK_PATH='$out'"
}

# Run the env gate; die on hard failure. Decode/serving scripts call this first.
env_gate_or_die() {
  if ! bash "$KVPRO_LIB_DIR/00_env_gate.sh"; then
    fail "Environment gate FAILED — refusing to run decode/serving tests on a"
    fail "broken environment (would either crash or silently mislead)."
    exit 2
  fi
}

# Run a labeled command, tee to a log, record exit status. Usage:
#   run_step "<label>" "<logfile>" cmd args...
run_step() {
  local label="$1" logf="$2"; shift 2
  log "RUN: $label"
  echo "### $label" >>"$logf"
  echo "### cmd: $*" >>"$logf"
  if "$@" >>"$logf" 2>&1; then
    ok "$label (log: $logf)"; return 0
  else
    local rc=$?
    fail "$label exited $rc (log: $logf)"; return $rc
  fi
}
