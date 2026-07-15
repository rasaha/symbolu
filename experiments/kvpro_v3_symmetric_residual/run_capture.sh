#!/usr/bin/env bash
# Capture real post-RoPE Q/K/V per layer (POD-ONLY). Needs GPU + model + mask (NOT the int4 fork).
# Usage: MODEL=... MASK=... bash run_capture.sh   (or --model/--mask via env)
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
MASK="${MASK:-${PROTECT_MASK_PATH:-}}"
SEED="${SEED:-0}"
section "Capture KV: $MODEL"
pod_gate_or_die "$MASK"
RUN="$(kvv3_run_dir)"
run_step "capture Q/K/V + frozen mask" "$RUN/capture.log" \
  python3 "$KVV3_LIB_DIR/capture_kv.py" --model "$MODEL" --mask "$MASK" --seed "$SEED" \
    --out "$RUN/captured_kv.pt"
if [[ -f "$RUN/captured_kv.pt" ]]; then
  ok "capture -> $RUN/captured_kv.pt"
  echo "$RUN/captured_kv.pt" > "$RUN/CAPTURE_PATH"
else
  fail "capture produced no file (see capture.log)"; exit 1
fi
