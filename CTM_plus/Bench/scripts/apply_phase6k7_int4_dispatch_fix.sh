#!/usr/bin/env bash
#
# Phase 6K.7 — route int4kv / int4kv_packed decode to the split-KV kernel.
#
# ROOT CAUSE (proven by 6K.4/6K.5/6K.6 + reading flash_api.cpp):
#   run_mha_fwd()'s dispatch puts the int4 three-way ladder
#   (packed > int4kv > stock) ONLY in the split-KV (else) branch:
#
#       if (params.num_splits <= 1 && !force_split_kernel) {
#           run_mha_fwd_<...>(params, stream);          // STOCK NON-SPLIT kernel
#       } else {
#           if (is_int4kv_packed) run_mha_fwd_splitkv_dispatch_int4kv_packed<...>();
#           else if (is_int4kv)   run_mha_fwd_splitkv_dispatch_int4kv<...>();
#           else                  run_mha_fwd_splitkv_dispatch<...>();
#       }
#
#   The non-split kernel (compute_attn_1rowblock) has NO int4_packed_load
#   wiring. For an int4 decode the backend pre-gathers blocks in Python
#   (=> no paged block_table => paged_KV=false), appends no new k/v
#   (=> k_.has_value()=false), and a short sequence is 1 KV block
#   (=> num_splits=1). So force_split_kernel=false AND num_splits<=1 =>
#   the NON-SPLIT kernel runs => it reads the all-zero bf16 backing stub
#   => Q.K = 0 (softmax_lse = ln(s_curr)), P.V = 0 => attention output is
#   EXACTLY zero on every layer => garbage generation. The split-KV kernel
#   that actually contains int4_packed_load_{K,V}_block is never launched.
#
# FIX:
#   Exclude int4 modes from the non-split branch so they always take the
#   wired split-KV path. Safe because:
#     * set_params_splitkv() (flash_api.cpp:1577 and :582) already sets
#       params.num_splits >= 1, and
#     * run_flash_splitkv_fwd() handles num_splits==1 (Split=false, writes
#       straight to out, skips the combine kernel), and
#     * params.is_int4kv_packed / is_int4kv are assigned at the TOP of
#       run_mha_fwd(), immediately above this dispatch, so they are valid.
#
# Idempotent + self-verifying. Creates a .phase6k7_backup before editing.
#
# Usage:
#   VLLM_FA_DIR=/workspace/dev/vllm-flash-attn-dev \
#     bash CTM_plus/Bench/scripts/apply_phase6k7_int4_dispatch_fix.sh
#
# Then rebuild (~1h) and re-run the zero-output probe:
#   cd $VLLM_FA_DIR && TMPDIR=/workspace/tmp MAX_JOBS=4 pip install --no-build-isolation -e .
#   cd /workspace/symbolu
#   export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:$PYTHONPATH
#   PHASE6E_FUSED_WRITER=0 python CTM_plus/Bench/scripts/phase6k6_zero_output_probe.py
#     -> expect KERNEL norm ~6.3 (was 0.0) and coherent output text.

set -euo pipefail

VLLM_FA_DIR="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
TARGET="${VLLM_FA_DIR}/csrc/flash_attn/flash_api.cpp"
export TARGET

if [[ ! -f "${TARGET}" ]]; then
    echo "FAIL: ${TARGET} not found. Set VLLM_FA_DIR to the fork root."
    exit 2
fi

python3 - <<'PY'
import os, sys, shutil

t = os.environ['TARGET']
src = open(t).read()

# Indentation-agnostic anchor: the if-condition without its trailing comment.
OLD = "if (params.num_splits <= 1 && !force_split_kernel) {"
NEW = ("if (params.num_splits <= 1 && !force_split_kernel\n"
       "                        && !params.is_int4kv_packed && !params.is_int4kv) {")

if "&& !params.is_int4kv_packed && !params.is_int4kv) {" in src:
    print("Phase 6K.7: already applied. Nothing to do.")
    sys.exit(0)

n = src.count(OLD)
if n == 0:
    print("FAIL: anchor not found (source diverged). Inspect:")
    print("  grep -n 'num_splits <= 1 && !force_split_kernel' " + t)
    sys.exit(3)
if n != 1:
    print(f"FAIL: expected exactly 1 anchor, found {n}. Aborting to avoid a wrong edit.")
    sys.exit(3)

bak = t + ".phase6k7_backup"
if not os.path.exists(bak):
    shutil.copy(t, bak)
    print("backup -> " + bak)

open(t, "w").write(src.replace(OLD, NEW, 1))
print("Phase 6K.7: applied (1 change).")
PY

# ---- verify ----
python3 - <<'PY'
import os, sys
t = os.environ['TARGET']
src = open(t).read()
ok = "&& !params.is_int4kv_packed && !params.is_int4kv) {" in src
print("OK: sentinel present." if ok else "FAIL: sentinel missing after write.")
sys.exit(0 if ok else 4)
PY

echo
echo "OK — Phase 6K.7 dispatch fix applied to ${TARGET}."
echo
echo "Rebuild (~1h):"
echo "  cd ${VLLM_FA_DIR} && TMPDIR=/workspace/tmp MAX_JOBS=4 pip install --no-build-isolation -e ."
echo
echo "Verify (expect KERNEL norm ~6.3, coherent text):"
echo "  cd /workspace/symbolu"
echo "  export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:\$PYTHONPATH"
echo "  PHASE6E_FUSED_WRITER=0 python CTM_plus/Bench/scripts/phase6k6_zero_output_probe.py 2>&1 | tee /tmp/phase6k6_postfix.log"
echo "  PHASE6E_FUSED_WRITER=0 python CTM_plus/Bench/scripts/phase6k5_ground_truth.py   2>&1 | tee /tmp/phase6k5_postfix.log"
