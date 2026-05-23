#!/usr/bin/env bash
# apply_phase6_4_long_sweep.sh — 6c.3C Phase 6.4 LONG-CONTEXT rerun.
#
# Re-runs the protect-fraction sweep at ~30k Qwen2.5-7B tokens (true
# §20.4.3 scale) instead of the ~7k tokens the first sweep hit by
# accident (32000 was CHARS, not TOKENS).
#
# Target: 140000 chars × (6836 tokens / 32000 chars observed) ≈ 29.9k
# tokens. Plus needle insertion (~50 tokens) + 64 decode tokens =
# ~30050 tokens. Qwen2.5-7B max_position_embeddings is 32768, so we
# fit with ~700 tokens of margin.
#
# If the harness skips this context (skipped_context_lengths_over_max_pos
# field non-empty in the output), drop to --context-lengths 130000 and
# re-run.
#
# Output: bench_out/phase6_4_long/  (separate from the 7k-token sweep's
# bench_out/phase6_4/ for direct comparison).
#
# Runtime: ~2-3 hours on A100. Prefill at 30k tokens is ~4x the 7k
# case; cache wrapper quant/dequant per decode token also scales with
# cache size. Resumable — each fraction's JSON is checked before re-run.
#
# Decision rule (per user, applied by aggregate_phase6_4.py):
#   - 4% passes at true ~30k tokens   -> Phase 5 default = 0.04
#   - 4% marginal, needle still 100%  -> Phase 5 default = 0.04 + 0.08 safe-mode
#   - 4% degrades, 8% passes          -> Phase 5 default = 0.08
#   - Neither passes                  -> STOP Phase 5, debug the quality path

set -euo pipefail

SYMBOLU=/workspace/symbolu
OUTDIR="$SYMBOLU/CTM_plus/Bench/bench_out/phase6_4_long"

mkdir -p "$OUTDIR"
cd "$SYMBOLU/CTM_plus/Bench"

FRACTIONS=(0.0 0.02 0.04 0.08)
CONTEXT_CHARS=140000   # ~30k Qwen tokens

echo "============================================================"
echo "6c.3C Phase 6.4 LONG-CONTEXT sweep — Qwen2.5-7B at ~30k tokens"
echo "Context: $CONTEXT_CHARS chars  (target ~30k Qwen tokens)"
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
    echo "[$(date +%H:%M:%S)] Running protect_fraction=$FRACTION at $CONTEXT_CHARS chars"
    echo "============================================================"
    /workspace/venv-vllm/bin/python3 -m ctm_bench.scripts.track_e_long_context \
        --model Qwen/Qwen2.5-7B-Instruct \
        --dtype float16 --device auto \
        --context-lengths "$CONTEXT_CHARS" \
        --needle-depths 0.1,0.5,0.9 \
        --needle-samples 8 \
        --needle-decode-tokens 64 \
        --skip-perplexity \
        --skip-version-check \
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
