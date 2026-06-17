#!/usr/bin/env bash
# 01 — Calibrate an int4_protected protect-mask for a model.
# Usage:
#   bash 01_calibrate_mask.sh <MODEL> <OUTPUT_PATH> [PROTECT_FRACTION] [MAX_MODEL_LEN]
# Example:
#   bash 01_calibrate_mask.sh Qwen/Qwen2.5-7B-Instruct \
#        /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
# Then: export PROTECT_MASK_PATH=<OUTPUT_PATH>
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

MODEL="${1:-}"; OUT="${2:-}"; FRAC="${3:-0.04}"; MML="${4:-2048}"
if [[ -z "$MODEL" || -z "$OUT" ]]; then
  fail "usage: 01_calibrate_mask.sh <MODEL> <OUTPUT_PATH> [PROTECT_FRACTION=0.04] [MAX_MODEL_LEN=2048]"
  exit 64
fi

CAL="$REPO/CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py"
[[ -f "$CAL" ]] || { fail "calibration script not found: $CAL"; exit 66; }

section "Calibrate protect-mask: $MODEL -> $OUT (fraction=$FRAC)"
# Calibration runs prefill only; the int4 DECODE kernel is not strictly required
# here, but a CUDA GPU + the model weights are. nvcc/decode-fork are not gated.
[[ "$(gpu_count)" -ge 1 ]] || { fail "no GPU — calibration needs a CUDA GPU + model weights."; exit 2; }
mkdir -p "$(dirname "$OUT")"

LOG="$(dirname "$OUT")/calibrate_$(basename "$OUT" .pt).log"
if python3 "$CAL" --model "$MODEL" --output "$OUT" \
      --protect-fraction "$FRAC" --max-model-len "$MML" 2>&1 | tee "$LOG"; then
  if [[ -f "$OUT" ]]; then
    ok "MASK WRITTEN: $OUT ($(du -h "$OUT" | cut -f1))"
    echo
    note "Export it before running decode/quality/density/throughput:"
    echo  "    export PROTECT_MASK_PATH='$OUT'"
    exit 0
  fi
  fail "calibration exited 0 but output not found at $OUT (see $LOG)."; exit 1
else
  fail "calibration FAILED (see $LOG). Common causes: model not cached / HF unreachable / OOM."
  exit 1
fi
