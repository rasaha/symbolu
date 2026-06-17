#!/usr/bin/env bash
# run_all — drive the KVPro v2 validation harness safely.
# Usage:
#   bash run_all.sh                 # env gate -> phase0 -> fusion -> warmtier -> tp
#   bash run_all.sh --phase0-only
#   bash run_all.sh --fusion-only
#   bash run_all.sh --warmtier-only
#   bash run_all.sh --tp-only
# Stops immediately on a HARD environment failure (00 gate). One timestamped run dir
# is shared by all phases. No projected value is ever printed as a measured result.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/_lib.sh"

MODE="all"
case "${1:-}" in
  --phase0-only)   MODE="phase0" ;;
  --fusion-only)   MODE="fusion" ;;
  --warmtier-only) MODE="warmtier" ;;
  --tp-only)       MODE="tp" ;;
  "" )             MODE="all" ;;
  -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
  *) fail "unknown flag: $1 (see --help)"; exit 64 ;;
esac

RUN="$(kvpro_run_dir)"          # fix one run dir for the whole sequence
export KVPRO_RUN_DIR="$RUN"
section "KVPro v2 validation — mode=$MODE — run dir=$RUN"

# --fusion-only can still do the CPU byte-eq even on a broken/GPU-less box, so the
# fusion script itself gates the GPU A/B internally. Every other phase needs the
# full environment, so the gate is a hard stop.
if [[ "$MODE" != "fusion" ]]; then
  log "Running environment gate (hard stop on failure) ..."
  if ! bash "$HERE/00_env_gate.sh"; then
    fail "HARD ENVIRONMENT FAILURE — stopping. Fix the [FAIL] items, then re-run."
    exit 2
  fi
else
  warn "fusion-only: skipping the hard gate (CPU byte-eq runs regardless; GPU A/B self-gates)."
fi

rc=0
case "$MODE" in
  phase0)   bash "$HERE/02_phase0_baseline.sh"   || rc=$? ;;
  fusion)   bash "$HERE/03_phase6f_validate.sh"  || rc=$? ;;
  warmtier) bash "$HERE/04_warmtier_validate.sh" || rc=$? ;;
  tp)       bash "$HERE/05_tp_smoke.sh"          || rc=$? ;;
  all)
    bash "$HERE/02_phase0_baseline.sh"   || rc=$?
    bash "$HERE/03_phase6f_validate.sh"  || rc=$?
    bash "$HERE/04_warmtier_validate.sh" || rc=$?
    bash "$HERE/05_tp_smoke.sh"          || rc=$?
    ;;
esac

section "run_all complete (mode=$MODE)"
ok "All artifacts under: $RUN"
note "Read SUMMARY_*.md / *_summary.csv there. MEASURED = this run measured it;"
note "INCOMPLETE/NOT-MEASURED = a hook is missing (the script printed the exact gap)."
[[ "$rc" -eq 0 ]] && ok "no phase reported a hard error" || warn "a phase exited non-zero ($rc) — see its log/summary"
exit "$rc"
