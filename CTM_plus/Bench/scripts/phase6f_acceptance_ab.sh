#!/usr/bin/env bash
# Phase 6F — ACCEPTANCE A/B harness for the read-path kernel fusion (Test 3).
#
# Measures whether the (future) fused read-path kernel — gated behind
# PHASE6F_FUSED_READ=1 — actually killed the ~19.5% gather/copy pass. Profiles
# the int4 decode at the saturation operating point with the flag OFF (baseline)
# then ON (experimental), and runs analyze_phase6f_acceptance.py for the verdict.
#
# RUN THE CORRECTNESS ORACLE FIRST (phase6f_correctness_oracle.sh). Performance
# without correctness is meaningless — a faster-but-wrong gather is a FAILURE.
#
# This does NOT implement the kernel. With the flag a no-op (kernel not yet
# built), before≈after and the verdict is NOT ACCEPTED — that is correct: it
# establishes the baseline the real change must beat.
#
# Usage (on the pod):
#   source /workspace/venv-vllm/bin/activate
#   bash CTM_plus/Bench/scripts/phase6f_acceptance_ab.sh
#
# Env overrides: MML, BATCH, MAXTOK, PROMPT_FRAC, OUT, FLAG.
set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROF="$SCRIPTS_DIR/bench_phase6_d_profile_gpu.py"
ACCEPT="$SCRIPTS_DIR/analyze_phase6f_acceptance.py"
CAP="$SCRIPTS_DIR/phase6l_capacity_demo.py"
PYTHON="${PYTHON:-python}"
FLAG="${FLAG:-PHASE6F_FUSED_READ}"
OUT="${OUT:-$SCRIPTS_DIR/../bench_out/phase6f}"
mkdir -p "$OUT"

MML="${MML:-8192}"
BATCH="${BATCH:-48}"
MAXTOK="${MAXTOK:-96}"
PROMPT_FRAC="${PROMPT_FRAC:-0.95}"
PCFG=(--max-model-len "$MML" --batch-size "$BATCH" --max-tokens "$MAXTOK"
      --prompt-frac "$PROMPT_FRAC" --gpu-memory-utilization 0.5 --n-warmup-runs 1)

echo "=================================================================="
echo "Phase 6F acceptance A/B — flag=$FLAG  mml=$MML B=$BATCH frac=$PROMPT_FRAC"
echo "=================================================================="

echo
echo "### Profiling BASELINE (${FLAG}=0) ###"
env "${FLAG}=0" "$PYTHON" "$PROF" --cell int4_captured "${PCFG[@]}" \
    --torch-profile-csv "$OUT/int4_flagoff_kernels.csv"

echo
echo "### Profiling EXPERIMENTAL (${FLAG}=1) ###"
env "${FLAG}=1" "$PYTHON" "$PROF" --cell int4_captured "${PCFG[@]}" \
    --torch-profile-csv "$OUT/int4_flagon_kernels.csv"

echo
echo "### Acceptance verdict (gather/copy A/B) ###"
"$PYTHON" "$ACCEPT" \
    --before "$OUT/int4_flagoff_kernels.csv" \
    --after  "$OUT/int4_flagon_kernels.csv" \
    --out "$OUT/PHASE_6F_acceptance_report.txt"
ACC_RC=$?

echo
echo "### (optional) end-to-end agg-tps move toward the ~0.3x ceiling ###"
echo "# Uncomment to measure cluster throughput off vs on (slower, ~1 pod-hr):"
echo "#   env ${FLAG}=0 $PYTHON $CAP --compare --mml $MML --b-list 96,128 --out-dir $OUT/cap_off"
echo "#   env ${FLAG}=1 $PYTHON $CAP --compare --mml $MML --b-list 96,128 --out-dir $OUT/cap_on"

echo
echo "=================================================================="
echo "DONE. Artifacts (commit with git add -f; bench_out/ is gitignored):"
echo "  $OUT/int4_flagoff_kernels.csv  $OUT/int4_flagon_kernels.csv"
echo "  $OUT/PHASE_6F_acceptance_report.txt"
echo "Acceptance verdict exit code: $ACC_RC (0=ACCEPTED, 1=NOT ACCEPTED)"
echo "REMINDER: acceptance is performance ONLY — correctness is the separate,"
echo "non-negotiable phase6f_correctness_oracle.sh gate."
echo "=================================================================="
exit $ACC_RC
