#!/usr/bin/env bash
# ==========================================================================
# KVPro prot-int8 — END-TO-END decode B vs C benchmark (POD-ONLY, real vLLM path)
# B = INT4 + BF16 protected sidecar (flag off) ; C = INT4 + INT8 protected sidecar (flag on)
# Reuses the existing Mistral model + v2 mask from the prior study. No new download.
# ==========================================================================
set -euo pipefail
cd /workspace/symbolu
P=/workspace/venv-vllm/bin/python3
MODEL=/workspace/models/mistral-7b-instruct-v0.3
export PROTECT_MASK_PATH=/workspace/hf_cache/mistral_v0_3_protect_mask_4pct_v2.pt
export HF_HUB_ENABLE_HF_TRANSFER=0 HF_HUB_DISABLE_XET=1 HF_HOME=/workspace/hf_cache
OUT=artifacts/prot_int8_speed
mkdir -p "$OUT"
BENCH=scripts/kvpro_prot_int8_validation/e2e_decode_bench.py

# Quick smoke first (1 point) to confirm the path fires + guards pass, before the full sweep.
$P "$BENCH" --cell off --model "$MODEL" --mask "$PROTECT_MASK_PATH" \
   --context-lens 2048 --gen-tokens 64 --batch-sizes 1 --iters 5 --warmup 3 \
   --out "$OUT/smoke_B.json"
$P "$BENCH" --cell on  --model "$MODEL" --mask "$PROTECT_MASK_PATH" \
   --context-lens 2048 --gen-tokens 64 --batch-sizes 1 --iters 5 --warmup 3 \
   --out "$OUT/smoke_C.json"
$P "$BENCH" --compare "$OUT/smoke_B.json" "$OUT/smoke_C.json" --outdir "$OUT/smoke"
#   -> check smoke/profiler_summary.json: guard_ok true both, packed>0, 0 fallbacks. If not, STOP.

# Full sweep (one vLLM engine per process; B then C). Default matrix 512/2048/8192 x 64/256 x 1/4/8.
$P "$BENCH" --cell off --model "$MODEL" --mask "$PROTECT_MASK_PATH" \
   --iters 30 --warmup 10 --out "$OUT/raw_B.json"
$P "$BENCH" --cell on  --model "$MODEL" --mask "$PROTECT_MASK_PATH" \
   --iters 30 --warmup 10 --out "$OUT/raw_C.json"
$P "$BENCH" --compare "$OUT/raw_B.json" "$OUT/raw_C.json" --outdir "$OUT"

echo "Primary result: $OUT/profiler_summary.json (overall_verdict, mean_speed_ratio_C_over_B)"
echo "Per-point:      $OUT/benchmark_matrix.csv"
echo "Do NOT commit raw model weights / HF cache. raw_*.json + CSVs are compact and OK to keep."
