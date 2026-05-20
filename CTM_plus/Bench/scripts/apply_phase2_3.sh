#!/usr/bin/env bash
# apply_phase2_3.sh — 6c.3C Phase 2.3 orchestrator.
#
# Adds the NO-OP INT4 quant->dequant transform on K at the two K-wait
# sites in compute_attn_1rowblock_splitkv. The transform is gated on
# params.is_int4kv (uniform runtime branch), so the stock FA path stays
# bit-identical to the pre-2.3 build.
#
# Steps:
#   1. apply_phase2_3_patches.py — writes int4_inline.h, modifies
#      flash_fwd_kernel.h (idempotent; re-run is a no-op).
#   2. Incremental rebuild — flash_fwd_kernel.h is included by every
#      splitkv .cu TU, so ~14 of them get recompiled. Expect ~8-12 min
#      hot cache on sm80.
#   3. Install the rebuilt wheel via install_dev_vllm_flash_attn.sh.
#   4. Phase 2.3 acceptance gate: verify_phase2_3.py
#        cosine >= 0.9999 AND max-abs <= 1e-2 between
#        flash_attn_with_int4_kvcache and flash_attn_with_kvcache on
#        Qwen2.5-7B shapes (B=1, H_q=28, H_kv=4, D=128, S=16k).
#
# IMPORTANT — verify_phase1.py WILL FAIL after Phase 2.3.
#   verify_phase1.py uses torch.equal between the int4 and stock paths.
#   Phase 2.3 deliberately introduces a small drift on the int4 path
#   (the quant->dequant cycle loses ~5 LSBs of BF16 precision per K
#   element). That's the WHOLE POINT — the transform proves the kernel
#   can do numerical work without breaking. So Phase 2.3 GREEN is
#   gated on verify_phase2_3.py (cosine), NOT verify_phase1.py.
#
#   To regression-check the STOCK FA path post-Phase-2.3, run
#   smoke_test_fa_install.sh — it exercises flash_attn_with_kvcache
#   only and compares against the 2026-05-20 baselines.

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

mkdir -p "$LOGDIR"

echo "============================================================"
echo "6c.3C Phase 2.3 — NO-OP INT4 quant->dequant transform on K"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase2_3_patches.py"
echo ""

echo "============================================================"
echo "Incremental rebuild — flash_fwd_kernel.h touched"
echo "Every .cu TU that includes it recompiles (~14 splitkv TUs)"
echo "Expect ~8-12 min hot cache on sm80"
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase2_3_build_$(date +%Y%m%d_%H%M%S).log"
TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 \
    python setup.py bdist_wheel 2>&1 | tee "$LOG"
echo ""
echo "Build log: $LOG"
echo ""

echo "============================================================"
echo "Install rebuilt wheel"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh"
echo ""

echo "============================================================"
echo "Phase 2.3 acceptance — cosine >= 0.9999 AND max-abs <= 1e-2"
echo "(NOTE: verify_phase1.py is EXPECTED to fail post-2.3 — see the"
echo " header comment in this script. Run smoke_test_fa_install.sh"
echo " separately to regression-check the stock FA path.)"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase2_3.py"
echo ""
echo "Phase 2.3: GREEN."
