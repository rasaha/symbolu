#!/usr/bin/env bash
# Attention-error eval (CPU-runnable) — the decisive offline proxy. Real capture or synthetic fixture.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"
cpu_gate_or_die
RUN="$(kvv3_run_dir)"
CAPTURE="${CAPTURE:-${1:-}}"
section "Attention-error eval (logits -> softmax -> output)"
if [[ -n "$CAPTURE" && -f "$CAPTURE" ]]; then
  run_step "attention error (MEASURED, real capture)" "$RUN/attn.log" \
    "$PY" "$KVV3_LIB_DIR/attention_error_eval.py" --capture "$CAPTURE" --out "$RUN/attention_error_metrics.json"
else
  warn "no capture file — SYNTHETIC fixture (plumbing only, NOT a verdict)."
  run_step "attention error (SYNTHETIC)" "$RUN/attn.log" \
    "$PY" "$KVV3_LIB_DIR/attention_error_eval.py" --synthetic --out "$RUN/attention_error_metrics.json"
fi
ok "-> $RUN/attention_error_metrics.json"
