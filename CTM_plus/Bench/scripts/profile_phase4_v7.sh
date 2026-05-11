#!/usr/bin/env bash
# Profile the streaming runner with py-spy to find the source of
# Phase 4's ~20% throughput regression. Captures a flame graph SVG
# that pinpoints which function calls dominate wall time.
#
# Result of the May 2026 v5 run:
#   - −11% swap_out/decode_token vs LRU (good — cache decisions improving)
#   - −20% tokens/sec vs LRU (bad — Python overhead)
#   - 61.8% trig_changed_pick (v6, mechanism dominantly active)
#
# This script answers "where does the 20% live?" Hypotheses ranked
# by likelihood from the audit:
#   1. math.cos calls in trig scoring (2560 ops/evict × ~1300 evicts)
#      — should be GONE after the I1 cache landed (commit pending).
#   2. Per-rotary hook overhead (~67K calls × few µs each).
#   3. CPU↔GPU sync in key.detach().to("cpu").
#   4. Dict updates in _block_pre_rope_keys / _block_trig_score.
#
# Usage on the pod:
#   pip install py-spy
#   bash CTM_plus/Bench/scripts/profile_phase4_v6.sh
#
# Output: phase4_profile.svg in the current directory. Open it in a
# browser. Functions at the bottom of the flame graph are the
# top-of-stack hot spots; functions at the top are their callers.

set -eo pipefail

cd "$(dirname "$0")/.."  # Bench dir

OUTPUT_DIR="bench_out/4cell_phase4_v7_profiled"
PROFILE_SVG="phase4_profile_$(date +%Y%m%d_%H%M%S).svg"

echo "==> py-spy version: $(py-spy --version 2>/dev/null || echo 'NOT INSTALLED — run pip install py-spy')"
echo "==> Output dir: ${OUTPUT_DIR}"
echo "==> Profile flame graph: ${PROFILE_SVG}"
echo

# --rate 100  sample 100Hz (every 10ms) — enough resolution for a
#             60s run without overwhelming overhead.
# --native    include C-extension frames so torch/vllm/numpy hot
#             spots show up, not just Python callers.
# --idle      include time spent waiting in select() / GIL acquire —
#             useful for diagnosing CPU↔GPU sync issues.
py-spy record \
    --output "${PROFILE_SVG}" \
    --rate 100 \
    --native \
    --idle \
    -- python3 -m ctm_bench.scripts.run_streaming \
        --model /workspace/.hf_cache_phase4/qwen2.5-7b \
        --workload chat_32k --seed 42 \
        --gpu-memory-utilization 0.26 --swap-space-gb 16 \
        --arrival-rate 6.0 --arrival-alpha 1.5 \
        --max-requests 30 --max-wall-seconds 60 \
        --max-decode-tokens 2048 \
        --prompt-length-choices "8000,16000,24000,30000" \
        --ctm-plus \
        --phase4-trig-calibration /workspace/.calibration/qwen2.5-7b.qcenters.perlayer.json \
        --phase4-window-interval 128 \
        --phase4-future-offsets "1,2,4,8,16" \
        --phase4-capture-every-n 4 \
        --output-dir "${OUTPUT_DIR}"

echo
echo "==> Profile saved to: ${PROFILE_SVG}"
echo "==> Streaming summary at: ${OUTPUT_DIR}/streaming_summary.json"
echo
echo "Read the result alongside the profile:"
echo "    python3 -m ctm_bench.scripts.read_phase4_v5 \\"
echo "        --phase4-dir ${OUTPUT_DIR} \\"
echo "        --phase2-dir bench_out/4cell_lru_v3"
echo
echo "The streaming run with profiling overhead will be slightly"
echo "slower than the unprofiled v5 baseline. Compare:"
echo "  - phase4_trig_score_computes  (should be small — captures only)"
echo "  - phase4_trig_score_lookups   (should be large — every evict)"
echo "  - cache hit rate (should be ~100%; if not, cache is leaking)"
echo "  - swap_out/decode_token  (should match v5's 0.277)"
echo "  - tokens/sec (with the cache, expect improvement vs v5's 68.26)"
