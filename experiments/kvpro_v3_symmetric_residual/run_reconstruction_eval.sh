#!/usr/bin/env bash
# Reconstruction-error eval (CPU-runnable). Uses a real capture if given, else a synthetic fixture
# (plumbing only — NOT a quality verdict). CAPTURE=<path> or --synthetic.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"
cpu_gate_or_die
RUN="$(kvv3_run_dir)"
CAPTURE="${CAPTURE:-${1:-}}"
section "Reconstruction eval"
if [[ -n "$CAPTURE" && -f "$CAPTURE" ]]; then
  run_step "reconstruction (MEASURED, real capture)" "$RUN/recon.log" \
    "$PY" "$KVV3_LIB_DIR/reconstruction_eval.py" --capture "$CAPTURE" --out "$RUN/reconstruction_metrics.json"
else
  warn "no capture file — running SYNTHETIC fixture (plumbing only, NOT a verdict)."
  run_step "reconstruction (SYNTHETIC)" "$RUN/recon.log" \
    "$PY" "$KVV3_LIB_DIR/reconstruction_eval.py" --synthetic --out "$RUN/reconstruction_metrics.json"
fi
ok "-> $RUN/reconstruction_metrics.json"
