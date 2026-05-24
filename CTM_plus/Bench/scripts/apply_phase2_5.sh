#!/usr/bin/env bash
# apply_phase2_5.sh — 6c.3C Phase 2.5 orchestrator.
#
# Template-gates the Phase 2.3 INT4 transform behind a `bool Is_int4kv`
# template parameter. After Phase 2.5:
#   - Stock FA path (Is_int4kv=false default): kernel compiles WITHOUT
#     the smem scratchpad or transform body. Per-block smem returns to
#     pre-Phase-2.3 levels (~80 KB) -> 2 blocks/SM occupancy on A100.
#     FA p50 should return to ~67 us (Phase 2.3 had 80 us, +19%).
#   - INT4 path (Is_int4kv=true via run_mha_fwd_splitkv_dispatch_int4kv):
#     same numerics as Phase 2.3 — cosine ~0.997 vs stock on Qwen2.5-7B.
#
# Wheel size also drops materially because the transform body no longer
# instantiates in every splitkv kernel variant (was ~208 MB, expect ~145 MB).
#
# Prerequisite: Phase 2.3 must already be applied (apply_phase2_3.sh).
# Phase 2.5's patcher anchors target Phase 2.3-modified code.
#
# Acceptance:
#   1. verify_phase2_3.py still GREEN (cosine >= 0.995, max-abs <= 1e-2).
#   2. smoke_test_fa_install.sh stock-path FA p50 within ±10% of the
#      pre-Phase-2.3 baseline 67 us (was 80 us at Phase 2.3 — regression
#      should be gone).

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

mkdir -p "$LOGDIR"

echo "============================================================"
echo "6c.3C Phase 2.5 — template-gated INT4 dispatch"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase2_5_patches.py"
echo ""

echo "============================================================"
echo "Incremental rebuild — touched flash_fwd_kernel.h,"
echo "flash_fwd_launch_template.h, int4_inline.h. Every splitkv .cu"
echo "TU recompiles (~14 of them, ~8-12 min hot cache on sm80)."
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase2_5_build_$(date +%Y%m%d_%H%M%S).log"
TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 \
    python setup.py bdist_wheel 2>&1 | tee "$LOG"
echo ""
echo "Build log: $LOG"
echo ""

echo "============================================================"
echo "Install rebuilt wheel"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh" || true
# install_dev_vllm_flash_attn.sh's tail verify uses system python (no vllm
# there). The wheel still copies into venv-vllm correctly. Use venv python
# for downstream verifies.
echo ""

echo "============================================================"
echo "Phase 2.5 acceptance 1/2 — int4 numerics unchanged"
echo "(cosine >= 0.995, max-abs <= 1e-2 on Qwen2.5-7B shapes)"
echo "============================================================"
/workspace/venv-vllm/bin/python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase2_3.py"
echo ""

echo "============================================================"
echo "Phase 2.5 acceptance 2/2 — stock-FA perf regression FIXED"
echo "(FA p50 @ S=16k within ±10% of 67 us baseline; was 80 us"
echo " at Phase 2.3)"
echo "============================================================"
bash "$SYMBOLU/CTM_plus/Bench/scripts/smoke_test_fa_install.sh"
echo ""
echo "Phase 2.5: GREEN."
