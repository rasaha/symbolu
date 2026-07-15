#!/usr/bin/env bash
# KVPro V3 Gate-1 orchestrator (falsification study).
#   ./run_all.sh --model <model> --mask <path>   # full: capture -> recon -> attn -> e2e -> gate (pod)
#   ./run_all.sh --reconstruction-only           # recon only (real capture if present, else synthetic)
#   ./run_all.sh --quality-only                  # attn + e2e + gate
# Fake-quant study: does NOT use the int4 decode fork. Hard deps for pod steps: GPU + model + mask.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/_lib.sh"

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"; MASK="${MASK:-${PROTECT_MASK_PATH:-}}"; MODE="full"
while [[ $# -gt 0 ]]; do case "$1" in
  --model) MODEL="$2"; shift 2;;
  --mask)  MASK="$2";  shift 2;;
  --reconstruction-only) MODE="recon"; shift;;
  --quality-only) MODE="quality"; shift;;
  -h|--help) sed -n '2,7p' "$0"; exit 0;;
  *) fail "unknown arg: $1"; exit 64;;
esac; done
export MODEL MASK
RUN="$(kvv3_run_dir)"; export KVV3_RUN_DIR="$RUN"
section "KVPro V3 Gate-1 — mode=$MODE — run=$RUN"
note "Falsification study: does symmetric INT4 on the non-protected residual (a) preserve quality and"
note "(b) remove enough decode work to justify a kernel? No production code is modified."

CAP=""
run_capture_if_pod() {
  if [[ "$(gpu_count)" -ge 1 ]] && mask_ok "$MASK"; then
    MODEL="$MODEL" MASK="$MASK" bash "$HERE/run_capture.sh" || true
    [[ -f "$RUN/CAPTURE_PATH" ]] && CAP="$(cat "$RUN/CAPTURE_PATH")"
  else
    warn "no GPU or no mask -> cannot capture real KV; offline evals will use the SYNTHETIC fixture"
    warn "(plumbing only). The GO/NO-GO verdict requires a real capture on a pod."
  fi
}

case "$MODE" in
  recon)
    run_capture_if_pod
    CAPTURE="$CAP" bash "$HERE/run_reconstruction_eval.sh" || true
    ;;
  quality)
    CAPTURE="${CAP:-${CAPTURE:-}}" bash "$HERE/run_attention_error_eval.sh" || true
    if [[ "$(gpu_count)" -ge 1 ]] && mask_ok "$MASK"; then
      run_step "end-to-end fake-quant quality" "$RUN/e2e.log" \
        python3 "$HERE/fakequant_quality.py" --model "$MODEL" --mask "$MASK" --out "$RUN/e2e_quality.json" || true
    else
      note "end-to-end fake-quant NOT RUN (needs GPU + mask)."
    fi
    bash "$HERE/run_quality_gate.sh" || true
    ;;
  full)
    run_capture_if_pod
    CAPTURE="$CAP" bash "$HERE/run_reconstruction_eval.sh" || true
    CAPTURE="$CAP" bash "$HERE/run_attention_error_eval.sh" || true
    if [[ "$(gpu_count)" -ge 1 ]] && mask_ok "$MASK"; then
      run_step "end-to-end fake-quant quality" "$RUN/e2e.log" \
        python3 "$HERE/fakequant_quality.py" --model "$MODEL" --mask "$MASK" --out "$RUN/e2e_quality.json" || true
    else
      note "end-to-end fake-quant NOT RUN (needs GPU + mask)."
    fi
    bash "$HERE/run_quality_gate.sh" || true
    ;;
esac

section "Gate-1 complete"
ok "artifacts under: $RUN"
note "MEASURED = computed this run on real capture; SYNTHETIC/NOT RUN = plumbing or pod-required."
note "A real GO/NO-GO needs a pod capture (run_capture.sh) + the offline evals + (ideally) fake-quant e2e."
