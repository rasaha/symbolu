#!/usr/bin/env bash
# apply_phase6_4_sweep.sh — 6c.3C Phase 6.4 protect-fraction sweep.
#
# Validates the §20.4.3 protect-K policy at four fractions on real
# Qwen2.5-7B prefill K. Routes through the existing track_e_long_context
# harness (HF native FA + INT4PerChannelCache wrapper). The native-kernel
# path's quality follows by transitivity:
#
#   Phase 2.3/3/4 diagnostics: CUDA kernel == route-B algorithm
#                              (cosine match within 1e-5 on synthetic K)
#   §20.4.3 result:            route-B algorithm passes on real Qwen K
#                              at 4% protect (100% needle accuracy)
#   Therefore:                 CUDA kernel passes on real Qwen K
#                              under the same algorithm + same protect %.
#
# Phase 6.4 sweeps fraction in {0%, 2%, 4%, 8%} to confirm where the
# quality cliff is. Decision rule in aggregate_phase6_4.py applies after
# all four runs complete.
#
# Runtime: ~10-15 min per fraction × 4 = ~45-60 min total on A100.
# Per-fraction model load is ~80 s (Qwen2.5-7B safetensors load).

set -euo pipefail

SYMBOLU=/workspace/symbolu
OUTDIR="$SYMBOLU/CTM_plus/Bench/bench_out/phase6_4"

mkdir -p "$OUTDIR"
cd "$SYMBOLU/CTM_plus/Bench"

FRACTIONS=(0.0 0.02 0.04 0.08)

echo "============================================================"
echo "6c.3C Phase 6.4 — protect-fraction sweep on Qwen2.5-7B"
echo "Fractions: ${FRACTIONS[*]}"
echo "Output:    $OUTDIR/"
echo "============================================================"
echo ""

for FRACTION in "${FRACTIONS[@]}"; do
    OUT="$OUTDIR/protect_${FRACTION}.json"
    if [ -f "$OUT" ]; then
        echo "  SKIP (already exists): $OUT"
        continue
    fi
    echo "============================================================"
    echo "[$(date +%H:%M:%S)] Running protect_fraction=$FRACTION"
    echo "============================================================"
    /workspace/venv-vllm/bin/python3 -m ctm_bench.scripts.track_e_long_context \
        --model Qwen/Qwen2.5-7B-Instruct \
        --dtype float16 --device auto \
        --context-lengths 32000 \
        --needle-depths 0.1,0.5,0.9 \
        --needle-samples 8 \
        --needle-decode-tokens 64 \
        --skip-perplexity \
        --k-bits 4 --v-bits 4 \
        --k-protect-fraction "$FRACTION" --k-protect-static \
        --output "$OUT"
    echo ""
done

echo "============================================================"
echo "Aggregate + decision rule"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/aggregate_phase6_4.py" \
    --indir "$OUTDIR" --output "$OUTDIR/summary.json"
