#!/usr/bin/env bash
# KVPro V3 Step-0 — orchestrate: env gate -> nsys -> ncu -> cuda-events -> parse -> cost -> decision.
# Every stage is allowed to be UNAVAILABLE/BLOCKED; the parser + decision matrix degrade honestly
# (NOT_RUN / FIX_PREREQUISITES_FIRST / INCONCLUSIVE) rather than fabricating a profile.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYBIN="${PYBIN:-python3}"; OUTDIR="${OUTDIR:-$HERE/runs}"; mkdir -p "$OUTDIR"
P8_VERDICT="${P8_VERDICT:-}"        # optional: path to the P8 quality verdict json (Part F)

echo "==== 00 env gate ===================================================="
bash "$HERE/00_env_gate.sh" "$OUTDIR/env_gate.json" || true

echo "==== B  MANDATORY correctness gate (Route-A builder vs CPU oracle) ==="
# Never profile an incorrect kernel (Part J): the builder must round-trip against the writer's reference
# dequant BEFORE any timing. A FAIL aborts the whole pipeline.
if ! "$PYBIN" "$HERE/06_correctness_gate.py" --out "$OUTDIR/correctness.json" ${KVV3_GPU_GATE:+--gpu}; then
  echo "[ABORT] correctness gate FAILED — refusing to profile. See $OUTDIR/correctness.json"
  exit 2
fi

echo "==== 01 nsys ========================================================"
OUTDIR="$OUTDIR" bash "$HERE/01_profile_nsys.sh" || echo "[skip] nsys stage unavailable/blocked"
echo "==== 02 ncu ========================================================="
OUTDIR="$OUTDIR" bash "$HERE/02_profile_ncu.sh"  || echo "[skip] ncu stage unavailable/blocked"
echo "==== 03 cuda events (route-A Triton) ================================"
OUTDIR="$OUTDIR" bash "$HERE/03_profile_cuda_events.sh" || echo "[skip] cuda-events stage unavailable"

# pick the first available nsys kernel-summary CSV + ncu CSV + events json
NSYS_CSV="$(ls -t "$OUTDIR"/*kern_sum*.csv "$OUTDIR"/*gpukernsum*.csv 2>/dev/null | head -1 || true)"
NCU_CSV="$(ls -t "$OUTDIR"/ncu_*.csv 2>/dev/null | head -1 || true)"
EVENTS="$([ -f "$OUTDIR/cuda_events.json" ] && echo "$OUTDIR/cuda_events.json" || true)"

echo "==== 04 parse -> stage summary ======================================"
"$PYBIN" "$HERE/04_parse_profile.py" \
    ${NSYS_CSV:+--nsys-csv "$NSYS_CSV"} ${NCU_CSV:+--ncu-csv "$NCU_CSV"} ${EVENTS:+--events-json "$EVENTS"} \
    --out "$OUTDIR/stage_summary.json" --csv-out "$OUTDIR/stage_summary.csv" || true

echo "==== E cost accounting =============================================="
"$PYBIN" "$HERE/cost_accounting.py" --stages "$OUTDIR/stage_summary.json" \
    --out "$OUTDIR/cost_accounting.json" || true

echo "==== G decision matrix =============================================="
"$PYBIN" "$HERE/05_decision_matrix.py" --env "$OUTDIR/env_gate.json" \
    --stages "$OUTDIR/stage_summary.json" --cost "$OUTDIR/cost_accounting.json" \
    ${P8_VERDICT:+--p8 "$P8_VERDICT"} --out "$OUTDIR/decision.json" || true

echo ""
echo "Artifacts in $OUTDIR : env_gate.json stage_summary.{json,csv} cost_accounting.json decision.json"
echo "Recommendation:"; "$PYBIN" -c "import json;print(' ',json.load(open('$OUTDIR/decision.json'))['recommendation'])" 2>/dev/null || true
