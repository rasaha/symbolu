#!/usr/bin/env bash
# apply_phase2_1.sh — orchestrator for 6c.3C Phase 2.1.
#
# Phase 2.1 = dispatch arm + cloned kernel scaffolding. NO runtime
# behavior change. The new run_mha_fwd_splitkv_dispatch_int4kv is
# compiled into the .so but unreachable; verify_phase1.py's
# bit-equality test still passes because the active code path is
# untouched.
#
# Acceptance: build succeeds + Phase 1 verify_phase1.py passes.
#
# Phase 2.2 will be the first runtime exercise of the new dispatch.

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

echo "============================================================"
echo "6c.3C Phase 2.1 — dispatch arm + cloned kernel (dead code)"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase2_1_patches.py"
echo ""

echo "============================================================"
echo "Incremental rebuild — one new .cu file instantiation"
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase2_1_build_$(date +%Y%m%d_%H%M%S).log"
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
echo "Phase 2.1 acceptance — Phase 1 bit-equality test still passes"
echo "(new dispatch is dead code, active path unchanged)"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase1.py"
