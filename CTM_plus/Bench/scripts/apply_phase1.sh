#!/usr/bin/env bash
# apply_phase1.sh — orchestrator for 6c.3C Phase 1.
#
# 1. Applies the additive patches (apply_phase1_patches.py).
# 2. Incremental rebuild of the dev wheel (only changed TUs rebuild).
# 3. Installs the new wheel into venv-vllm (overwrites the vendored
#    copy; backup intact).
# 4. Runs verify_phase1.py — the bit-equality acceptance test.
#
# Phase 1 GREEN = verify_phase1 exits 0.
# Phase 1 RED   = patches don't apply OR build fails OR verify fails.
# On RED, restore via restore_vendored_vllm_flash_attn.sh, then debug.

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

echo "============================================================"
echo "6c.3C Phase 1 — apply additive scaffolding patches"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase1_patches.py"
echo ""

echo "============================================================"
echo "Incremental rebuild (only changed TUs)"
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase1_build_$(date +%Y%m%d_%H%M%S).log"
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
echo "Phase 1 acceptance test (bit-equality)"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase1.py"
