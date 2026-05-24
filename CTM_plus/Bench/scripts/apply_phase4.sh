#!/usr/bin/env bash
# apply_phase4.sh — 6c.3C Phase 4 orchestrator.
#
# Adds the §20.4.3 protect-K sidecar in-kernel: top-~4% K channels per
# (B, H_kv) by magnitude are kept BF16 (skip quant), the rest go through
# the Phase 2.3 INT4 cycle. Closes the cosine gap from Phase 3's ~0.99
# toward stock FP16's ~1.0.
#
# Prerequisites: Phase 2.3 + Phase 2.5 + Phase 3 applied.
#
# Acceptance:
#   1. verify_phase4.py: cosine >= 0.9990, max-abs <= 1e-2 with the
#      top-4% protect mask supplied. If it fails, run
#      diagnose_phase4_drift.py to attribute drift to algorithm vs CUDA.
#   2. smoke_test_fa_install.sh: stock FA p50 ~67 us (Is_int4kv=false
#      template variant doesn't compile in the mask logic, just like
#      Phases 2.3/3 didn't compile in the transform).

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

mkdir -p "$LOGDIR"

echo "============================================================"
echo "6c.3C Phase 4 — protect-K BF16 sidecar (in-kernel)"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase4_patches.py"
echo ""

echo "============================================================"
echo "Incremental rebuild — int4_inline.h, flash_fwd_kernel.h,"
echo "flash_api.cpp touched. Every splitkv .cu TU recompiles."
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase4_build_$(date +%Y%m%d_%H%M%S).log"
TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 \
    python setup.py bdist_wheel 2>&1 | tee "$LOG"
echo ""
echo "Build log: $LOG"
echo ""

echo "============================================================"
echo "Install rebuilt wheel"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh" || true
echo ""

echo "============================================================"
echo "Phase 4 acceptance — protect-K closes the cosine gap"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase4.py"
echo ""

echo "============================================================"
echo "Stock FA regression check — Is_int4kv=false untouched by Phase 4"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/smoke_test_fa_install.sh"
echo ""
echo "Phase 4: GREEN."
