#!/usr/bin/env bash
# Phase 0 smoke tests — confirm the dev install of vllm_flash_attn
# behaves like the original vendored copy. Two checks:
#
# 1. FA microbench at S=16k — p50 within ±10% of the 2026-05-20
#    baseline (67 us).
# 2. Cell-A throughput at S=32k, B=1, decode=128 — tok/s within
#    ±5% of the 2026-05-20 baseline (28.4 tok/s).
#
# Both checks must pass for Phase 0 to be GREEN. If either misses,
# inspect the diff before proceeding to Phase 1; if either crashes,
# run restore_vendored_vllm_flash_attn.sh and investigate.

set -euo pipefail

cd /workspace/symbolu/CTM_plus/Bench

echo "============================================================"
echo "Phase 0 smoke test 1/2 — FA microbench at S in {2k,8k,16k}"
echo "============================================================"
python scripts/kernel_int4_vs_fa_microbench.py \
    --iters 200 --warmup 50 \
    --output bench_out/phase0/kernel_int4_vs_fa_postbuild.json \
    --seqlens 2048 8192 16384

echo ""
echo "============================================================"
echo "Phase 0 smoke test 2/2 — cell A throughput at S=32k, B=1"
echo "============================================================"
python scripts/kernel_6c3a_throughput.py \
    --cell A \
    --num-prompts 1 \
    --prompt-tokens 32000 \
    --decode-tokens 128 \
    --gpu-memory-utilization 0.5 \
    --output bench_out/phase0/cell_A_s32k_postbuild.json

echo ""
echo "============================================================"
echo "Baseline comparison"
echo "============================================================"
python3 - <<'PY'
import json, os
out_dir = "bench_out/phase0"

# Baselines from 2026-05-20 (recorded in §20.6.3).
baselines = {
    "fa_p50_s16k_ms": 0.0673,
    "cell_A_s32k_toks": 28.4,
}

m = json.load(open(f"{out_dir}/kernel_int4_vs_fa_postbuild.json"))
fa_row = [r for r in m["rows"] if r["S"] == 16384][0]
fa_p50 = fa_row["fa"]["p50_ms"]
fa_drift = (fa_p50 - baselines["fa_p50_s16k_ms"]) / baselines["fa_p50_s16k_ms"]

t = json.load(open(f"{out_dir}/cell_A_s32k_postbuild.json"))
cell_a = t["tokens_per_second"]
cell_a_drift = (cell_a - baselines["cell_A_s32k_toks"]) / baselines["cell_A_s32k_toks"]

print(f"FA p50 @ S=16k:      baseline={baselines['fa_p50_s16k_ms']*1000:.1f} us")
print(f"                     post-build={fa_p50*1000:.1f} us")
print(f"                     drift={fa_drift*100:+.1f}%   threshold=±10%   {'PASS' if abs(fa_drift)<=0.10 else 'FAIL'}")
print()
print(f"Cell A @ S=32k:      baseline={baselines['cell_A_s32k_toks']:.2f} tok/s")
print(f"                     post-build={cell_a:.2f} tok/s")
print(f"                     drift={cell_a_drift*100:+.1f}%   threshold=±5%    {'PASS' if abs(cell_a_drift)<=0.05 else 'FAIL'}")

if abs(fa_drift) <= 0.10 and abs(cell_a_drift) <= 0.05:
    print()
    print("Phase 0 smoke: GREEN. Safe to proceed to Phase 1.")
    raise SystemExit(0)
else:
    print()
    print("Phase 0 smoke: drift outside threshold. Investigate before Phase 1.")
    raise SystemExit(1)
PY
