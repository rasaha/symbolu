#!/usr/bin/env bash
# apply_phase2_4_1b.sh — 6c.3C Phase 2.4.1b orchestrator.
#
# Phase 2.4.1b: kernel-side packed-K HBM read. New CUDA helper +
# Is_int4kv_packed template path + new dispatch arm + new .cu
# instantiation + run_mha_fwd routing.
#
# Prerequisites: Phase 1 + 2.1 + 2.2 + 2.3 + 2.5 + 3 + 4 + 2.4.1a applied.
#
# Build cost: full splitkv rebuild (~10-15 min cold, ~8 min warm).
# flash_fwd_kernel.h + flash_fwd_launch_template.h are included by all
# splitkv .cu TUs, so this is unavoidable.
#
# Acceptance:
#   1. Build succeeds with the new template path + new .cu compiled.
#   2. verify_phase2_4_1b.py PASS — cosine >= 0.9995 vs Phase 5A.
#   3. verify_phase4.py still PASS — non-packed in-register quant path
#      unchanged.
#   4. verify_phase5a_smoke.py still PASS — end-to-end vLLM decode
#      still routes through native kernel.

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

mkdir -p "$LOGDIR"

echo "============================================================"
echo "6c.3C Phase 2.4.1b — kernel-side packed-K HBM read"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase2_4_1b_patches.py"
echo ""

echo "============================================================"
echo "Full rebuild — flash_fwd_kernel.h + flash_fwd_launch_template.h"
echo "+ new .cu (all ~14 splitkv TUs recompile, ~10-15 min cold)"
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase2_4_1b_build_$(date +%Y%m%d_%H%M%S).log"
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
echo "Acceptance 1/3 — verify_phase2_4_1b.py (THE gate, cosine >= 0.9995)"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase2_4_1b.py"
echo ""

echo "============================================================"
echo "Acceptance 2/3 — verify_phase4.py still GREEN"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase4.py"
echo ""

echo "============================================================"
echo "Acceptance 3/3 — verify_phase5a_smoke.py still GREEN"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase5a.sh"
echo ""
echo "Phase 2.4.1b: GREEN."
