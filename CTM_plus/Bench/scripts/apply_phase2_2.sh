#!/usr/bin/env bash
# apply_phase2_2.sh — 6c.3C Phase 2.2 orchestrator.
#
# Routes the Python call -> new C++ entry -> Int4KvDispatchGuard ->
# run_mha_fwd reads thread-local -> conditional dispatch to
# run_mha_fwd_splitkv_dispatch_int4kv (the Phase 2.1 dead code,
# now LIVE).
#
# The cloned _int4kv kernel template body is still identical to
# stock, so verify_phase1.py's bit-equality test MUST still pass.
# This is the FIRST runtime exercise of the new path.

set -euo pipefail

SYMBOLU=/workspace/symbolu
DEV=/workspace/dev/vllm-flash-attn-dev
LOGDIR=/workspace/dev/build-logs

echo "============================================================"
echo "6c.3C Phase 2.2 — route Python -> new C++ entry -> new dispatch"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/apply_phase2_2_patches.py"
echo ""

echo "============================================================"
echo "Incremental rebuild — flash_api.cpp + .py only"
echo "============================================================"
cd "$DEV"
LOG="$LOGDIR/phase2_2_build_$(date +%Y%m%d_%H%M%S).log"
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
echo "Phase 2.2 acceptance — bit-equality test via the NEW path"
echo "(active route now: Python -> fwd_kvcache_int4 -> Int4KvDispatchGuard"
echo " -> run_mha_fwd -> run_mha_fwd_splitkv_dispatch_int4kv -> kernel)"
echo "============================================================"
python3 "$SYMBOLU/CTM_plus/Bench/scripts/verify_phase1.py"
