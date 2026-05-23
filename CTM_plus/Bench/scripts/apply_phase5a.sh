#!/usr/bin/env bash
# apply_phase5a.sh — 6c.3C Phase 5A orchestrator.
#
# Phase 5A: native-kernel-routed vLLM decode with BF16-backed KV cache.
#   - Routes vLLM decode through flash_attn_with_int4_kvcache via a
#     monkey-patch on each Attention.forward.
#   - Static top-protect_fraction K-channel mask computed at end of
#     prefill from K magnitudes.
#   - HBM K/V remain BF16 in vLLM's paged cache (real INT4 storage is
#     Phase 2.4). A parallel FP16 sidecar (~2× KV memory at v1) carries
#     the contiguous K/V the kernel reads — a measurement-time cost
#     that does NOT enter the v1 ship claim.
#   - V1 batch=1 only.
#
# This orchestrator just runs the smoke test. No rebuild needed —
# Phase 5A is pure Python on top of the Phase 2.3/3/4/2.5 kernel.

set -euo pipefail

SYMBOLU=/workspace/symbolu

echo "============================================================"
echo "6c.3C Phase 5A — native-kernel-routed vLLM decode (smoke test)"
echo "============================================================"

/workspace/venv-vllm/bin/python3 \
    "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase5a_smoke.py" \
    --model Qwen/Qwen2.5-7B-Instruct \
    --max-model-len 4096 \
    --max-tokens 32 \
    --protect-fraction 0.04 \
    --gpu-memory-utilization 0.5

echo ""
echo "Phase 5A smoke: GREEN."
