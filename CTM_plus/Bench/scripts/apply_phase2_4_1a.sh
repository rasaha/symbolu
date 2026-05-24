#!/usr/bin/env bash
# apply_phase2_4_1a.sh — 6c.3C Phase 2.4.1a orchestrator.
#
# Phase 2.4.1a: packed-K data-plumbing only. NO kernel changes.
# Validates that the new Flash_fwd_params fields + Python wrapper
# kwargs + flash_api.cpp guard plumbing build and don't regress
# Phase 5A's smoke or Phase 4's verify.
#
# Prerequisites: Phase 1 + 2.1 + 2.2 + 2.3 + 2.5 + 3 + 4 applied.
#
# Acceptance:
#   1. Build succeeds (only flash_api.cpp TU touched; ~30s incremental).
#   2. verify_phase4.py still GREEN (no kernel-side change).
#   3. verify_phase5a_smoke.py still GREEN (Phase 5A path uses NO
#      packed args — sees the new params fields as NULL).

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

mkdir -p "$LOGDIR"

echo "============================================================"
echo "6c.3C Phase 2.4.1a — packed-K data plumbing (no kernel)"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase2_4_1a_patches.py"
echo ""

echo "============================================================"
echo "Incremental rebuild — flash_api.cpp + flash.h + wrapper only"
echo "(no .cu files touched, ~30s)"
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase2_4_1a_build_$(date +%Y%m%d_%H%M%S).log"
TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 \
    python setup.py bdist_wheel 2>&1 | tee "$LOG"
echo "Build log: $LOG"
echo ""

echo "============================================================"
echo "Install rebuilt wheel"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh" || true
echo ""

echo "============================================================"
echo "Acceptance 1/2 — verify_phase4.py still GREEN"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase4.py"
echo ""

echo "============================================================"
echo "Acceptance 2/2 — verify_phase5a_smoke.py still GREEN"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase5a.sh"
echo ""
echo "Phase 2.4.1a: GREEN."
