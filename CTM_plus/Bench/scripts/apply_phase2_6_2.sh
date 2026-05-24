#!/usr/bin/env bash
# apply_phase2_6_2.sh — 6c.3C Phase 2.6.2 orchestrator.
#
# Adds packed-V HBM read path to the existing Phase 2.4.1b packed
# kernel. After this lands, when Is_int4kv_packed=true the kernel
# reads BOTH packed K (existing) AND packed V (new).
#
# Build cost: flash_fwd_kernel.h + int4_packed_load.h modified ->
# full splitkv rebuild (~10-15 min cold, ~8 min warm).
#
# Acceptance:
#   1. Build succeeds.
#   2. verify_phase2_6_2.py PASS — cosine >= 0.9995 vs Phase 5A on
#      Qwen2.5-7B shapes with both K and V packed.
#   3. Phase 2.4.1b K-only verify still PASS (template gating
#      isolates V load behind is_int4kv_packed extended check).
#   4. Phase 4 + Phase 5A smoke still PASS.

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

mkdir -p "$LOGDIR"

echo "============================================================"
echo "6c.3C Phase 2.6.2 — packed-V kernel read"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase2_6_2_patches.py"
echo ""

echo "============================================================"
echo "Full rebuild — flash_fwd_kernel.h + int4_packed_load.h"
echo "(all splitkv .cu TUs recompile, ~10-15 min cold)"
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase2_6_2_build_$(date +%Y%m%d_%H%M%S).log"
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
echo "Acceptance 1/3 — verify_phase2_6_2.py (cosine vs Phase 5A)"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase2_6_2.py"
echo ""

echo "============================================================"
echo "Acceptance 2/3 — verify_phase2_4_1b.py still GREEN"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase2_4_1b.py"
echo ""

echo "============================================================"
echo "Acceptance 3/3 — verify_phase5a_smoke.py still GREEN"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase5a.sh"
echo ""
echo "Phase 2.6.2: GREEN."
