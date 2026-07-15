#!/usr/bin/env bash
# Shared helpers for the KVPro V3 Gate-1 symmetric-residual falsification harness.
# This is a FAKE-QUANT study (quantize->dequantize in fp). It does NOT use the int4 decode kernel,
# so the kernel is reported as INFO, not gated on. Real hard deps: GPU + model + mask (for pod steps).
set -uo pipefail

KVV3_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$KVV3_LIB_DIR/../.." && pwd)"
export REPO
export PYTHONPATH="$KVV3_LIB_DIR:$REPO/CTM_plus/KVPolicy:$REPO:${PYTHONPATH:-}"

log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
ok()   { echo "  [PASS] $*"; }
fail() { echo "  [FAIL] $*" >&2; }
warn() { echo "  [WARN] $*" >&2; }
note() { echo "  [NOTE] $*"; }
info() { echo "  [INFO] $*"; }
section(){ echo; printf '%.0s=' {1..70}; echo; echo "== $*"; printf '%.0s=' {1..70}; echo; }

kvv3_run_dir() {
  if [[ -z "${KVV3_RUN_DIR:-}" ]]; then
    local ts; ts="$(date -u +%Y%m%dT%H%M%SZ)"
    KVV3_RUN_DIR="$REPO/experiments/kvpro_v3_symmetric_residual/runs/$ts"
    mkdir -p "$KVV3_RUN_DIR"; export KVV3_RUN_DIR
  fi
  echo "$KVV3_RUN_DIR"
}

gpu_count() {
  command -v nvidia-smi >/dev/null 2>&1 && \
    nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ' || echo 0
}

have_torch()   { python3 -c "import torch" >/dev/null 2>&1; }
have_cuda()    { python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" >/dev/null 2>&1; }
mask_ok()      { [[ -n "${1:-}" && -f "${1:-/nonexistent}" ]]; }

# int4 fork: INFO ONLY — this fake-quant study does not use it (stated, not a silent fallback).
report_fork() {
  if python3 -c "from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache" >/dev/null 2>&1; then
    info "int4 decode fork present (NOT used by this fake-quant study)."
  else
    info "int4 decode fork absent — OK: this study is fake-quant (fp simulate) and does not need it."
    info "(A future V3 kernel prototype WOULD need it; this Gate-1 study does not.)"
  fi
}

# Hard gate for POD steps (capture / fake-quant): GPU + torch + model-loadable + mask.
pod_gate_or_die() {
  local mask="${1:-}"
  [[ "$(gpu_count)" -ge 1 ]] || { fail "no GPU — capture/fake-quant need a CUDA GPU + model weights."; exit 2; }
  have_torch || { fail "torch not importable."; exit 2; }
  have_cuda  || { fail "torch.cuda.is_available()==False."; exit 2; }
  mask_ok "$mask" || { fail "mask missing: '${mask}'. Build via calibrate_phase5b_protect_mask.py, then pass --mask / \$PROTECT_MASK_PATH."; exit 2; }
  report_fork
}

# CPU gate for offline evals: torch only (synthetic plumbing) or a capture file.
cpu_gate_or_die() {
  have_torch || { fail "torch not importable (needed for the offline quantizers/metrics)."; exit 2; }
}

run_step() {
  local label="$1" logf="$2"; shift 2
  log "RUN: $label"
  { echo "### $label"; echo "### cmd: $*"; } >>"$logf"
  if "$@" >>"$logf" 2>&1; then ok "$label -> $logf"; return 0
  else local rc=$?; fail "$label exited $rc (see $logf)"; return $rc; fi
}
