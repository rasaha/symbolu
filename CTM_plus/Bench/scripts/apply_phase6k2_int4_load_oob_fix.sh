#!/usr/bin/env bash
#
# Phase 6K.2 — fix OOB masking bugs inside int4_packed_load_{K,V}_block in
# vllm-flash-attn-dev/csrc/flash_attn/src/int4_packed_load.h.
#
# The original Phase 6K patch fixed the s_curr ARGUMENT at 4 call sites in
# flash_fwd_kernel.h (params.seqlen_k → binfo.actual_seqlen_k).  That is
# necessary but not sufficient: the load functions themselves have two
# additional bugs that produce non-zero K/V values for OOB positions even
# when s_curr is correct.
#
# Root causes (all in int4_packed_load.h):
#
#   K Phase B/C (scales/xmins): the bounds check `global_g < n_groups_total`
#   allows loading HBM for groups whose first token is >= s_curr.  In eager
#   mode those HBM locations contain stale quant params from the previous
#   request → garbage/NaN scales.  NaN scales produce NaN K values; flash
#   attention's -inf masking cannot fix them (nan + (-inf) = nan).
#
#   K Phase F (dequant loop): even after Phase A zeroes the packed nibbles,
#   the formula `x = 0 * scale + xmin = xmin` writes xmin (not 0) for OOB
#   positions within group-0's partial range (tokens s_curr..kGroupSize-1).
#   When flash attention's masking loop doesn't fire (which happens when
#   ceil_div(kBlockM + s_curr - n_block_max*kBlockN, kBlockN) == 0 for
#   short sequences), these non-zero K values corrupt the QK GEMM output.
#
# Fixes applied (3 locations in int4_packed_load.h):
#
#   Fix 1 (K Phase B): add `global_g * kGroupSize < s_curr` to the scale
#           load guard — prevents loading stale/NaN HBM for unwritten groups.
#
#   Fix 2 (K Phase C): same guard for xmin load.
#
#   Fix 3 (K Phase F): after the n/d bounds check, zero tKsK and skip
#           dequant for any position where global_n = n_block_token_start + n
#           >= s_curr.  Ensures K[OOB] = 0 regardless of nibble, scale, xmin.
#
#   Fix 4 (V Phase D): belt-and-suspenders zero guard for tVsV using
#           global_t = n_block_token_start + n.  V Phase B/C already zero
#           per-token scales for OOB tokens, but explicit zero is safer.
#
# Idempotent: detects already-patched state and exits cleanly.
#
# Usage:
#   bash CTM_plus/Bench/scripts/apply_phase6k2_int4_load_oob_fix.sh
#
# Then rebuild the wheel (~1 h; use /workspace/tmp for TMPDIR):
#   cd /workspace/dev/vllm-flash-attn-dev
#   TMPDIR=/workspace/tmp MAX_JOBS=4 pip install --no-build-isolation -e .
#
# Then verify with the bisection script:
#   bash CTM_plus/Bench/scripts/verify_phase6k_bisection.sh

set -euo pipefail

VLLM_FA_DIR="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
TARGET_H="${VLLM_FA_DIR}/csrc/flash_attn/src/int4_packed_load.h"
export TARGET_H

if [[ ! -f "${TARGET_H}" ]]; then
    echo "FAIL: ${TARGET_H} does not exist. Set VLLM_FA_DIR if the fork is at a different path."
    exit 2
fi

# -------------------------------------------------------------------------
# Idempotency: sentinels introduced by each fix.
# -------------------------------------------------------------------------
n_phase_b_fix=$(grep -c "global_g \* kGroupSize < s_curr" "${TARGET_H}" || true)
n_phase_f_fix=$(grep -c "tKsK(i0, i1, i2) = Element(0);" "${TARGET_H}" || true)
n_phase_d_fix=$(grep -c "tVsV(i0, i1, i2) = Element(0);" "${TARGET_H}" || true)
echo "Pre-state:  K-phase-B/C sentinel=${n_phase_b_fix}  K-phase-F sentinel=${n_phase_f_fix}  V-phase-D sentinel=${n_phase_d_fix}"

if [[ "${n_phase_b_fix}" -ge 2 && "${n_phase_f_fix}" -ge 1 && "${n_phase_d_fix}" -ge 1 ]]; then
    echo "All fixes already applied. Nothing to do."
    exit 0
fi

# Verify we can find the original strings.
n_scale_guard=$(grep -c "global_g >= 0 && global_g < n_groups_total) {" "${TARGET_H}" || true)
n_f_guard=$(grep -c 'if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;' "${TARGET_H}" || true)
echo "Pre-state:  un-patched scale/xmin guards=${n_scale_guard}  n/d bounds checks=${n_f_guard}"

if [[ "${n_scale_guard}" -lt 2 ]]; then
    echo "FAIL: expected ≥2 un-patched scale/xmin guard lines; found ${n_scale_guard}."
    echo "      Source may have diverged. Inspect:"
    echo "        grep -n 'global_g < n_groups_total' ${TARGET_H}"
    exit 3
fi
if [[ "${n_f_guard}" -lt 2 ]]; then
    echo "FAIL: expected ≥2 Phase-F/D n/d bounds checks; found ${n_f_guard}."
    echo "      Source may have diverged. Inspect:"
    echo "        grep -n 'n >= kBlockN' ${TARGET_H}"
    exit 3
fi

# Backup (idempotent).
if [[ ! -f "${TARGET_H}.phase6k2_backup" ]]; then
    cp "${TARGET_H}" "${TARGET_H}.phase6k2_backup"
    echo "Backed up to ${TARGET_H}.phase6k2_backup"
fi

# -------------------------------------------------------------------------
# Apply all four fixes via Python string substitution.
# TARGET_H is exported so the heredoc can read it.
# -------------------------------------------------------------------------
python3 << 'PYEOF'
import sys, os

target = os.environ['TARGET_H']
with open(target) as f:
    src = f.read()

changes = 0

# ------------------------------------------------------------------
# Fix 1: K Phase B — add global_g * kGroupSize < s_curr guard on
#         the scale load so unwritten groups get Element(0).
# ------------------------------------------------------------------
OLD1 = (
    '            if (global_g >= 0 && global_g < n_groups_total) {\n'
    '                // (B, n_groups_total, H_kv, D) layout.\n'
    '                val = gmem_k_scale_base[global_g * H_kv * kHeadDim + bidh * kHeadDim + d];\n'
    '            }'
)
NEW1 = (
    '            if (global_g >= 0 && global_g < n_groups_total &&\n'
    '                    global_g * kGroupSize < s_curr) {\n'
    '                // (B, n_groups_total, H_kv, D) layout.\n'
    '                val = gmem_k_scale_base[global_g * H_kv * kHeadDim + bidh * kHeadDim + d];\n'
    '            }'
)
if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1)
    changes += 1
    print('Fix 1 (K Phase B scale guard): applied.')
elif NEW1 in src:
    print('Fix 1 (K Phase B scale guard): already present, skipping.')
else:
    sys.exit('FAIL: could not locate K Phase B scale load for Fix 1. Source may have changed.')

# ------------------------------------------------------------------
# Fix 2: K Phase C — same guard for the xmin load.
# ------------------------------------------------------------------
OLD2 = (
    '            if (global_g >= 0 && global_g < n_groups_total) {\n'
    '                val = gmem_k_xmin_base[global_g * H_kv * kHeadDim + bidh * kHeadDim + d];\n'
    '            }'
)
NEW2 = (
    '            if (global_g >= 0 && global_g < n_groups_total &&\n'
    '                    global_g * kGroupSize < s_curr) {\n'
    '                val = gmem_k_xmin_base[global_g * H_kv * kHeadDim + bidh * kHeadDim + d];\n'
    '            }'
)
if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1)
    changes += 1
    print('Fix 2 (K Phase C xmin guard): applied.')
elif NEW2 in src:
    print('Fix 2 (K Phase C xmin guard): already present, skipping.')
else:
    sys.exit('FAIL: could not locate K Phase C xmin load for Fix 2. Source may have changed.')

# ------------------------------------------------------------------
# Fix 3: K Phase F — zero tKsK for any position global_n >= s_curr.
# ------------------------------------------------------------------
OLD3 = (
    '                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;\n'
    '\n'
    '                Element x_hat;\n'
)
NEW3 = (
    '                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;\n'
    '                {\n'
    '                    const int global_n = n_block_token_start + n;\n'
    '                    if (global_n < 0 || global_n >= s_curr) {\n'
    '                        tKsK(i0, i1, i2) = Element(0);\n'
    '                        continue;\n'
    '                    }\n'
    '                }\n'
    '\n'
    '                Element x_hat;\n'
)
if OLD3 in src:
    src = src.replace(OLD3, NEW3, 1)
    changes += 1
    print('Fix 3 (K Phase F OOB zero): applied.')
elif 'tKsK(i0, i1, i2) = Element(0);' in src:
    print('Fix 3 (K Phase F OOB zero): already present, skipping.')
else:
    sys.exit('FAIL: could not locate K Phase F n/d bounds check for Fix 3. Source may have changed.')

# ------------------------------------------------------------------
# Fix 4: V Phase D — zero tVsV for any position global_t >= s_curr.
# ------------------------------------------------------------------
OLD4 = (
    '                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;\n'
    '\n'
    '                // V is grouped along HEAD_DIM: group = d / kVGroupSize.\n'
)
NEW4 = (
    '                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;\n'
    '                {\n'
    '                    const int global_t = n_block_token_start + n;\n'
    '                    if (global_t < 0 || global_t >= s_curr) {\n'
    '                        tVsV(i0, i1, i2) = Element(0);\n'
    '                        continue;\n'
    '                    }\n'
    '                }\n'
    '\n'
    '                // V is grouped along HEAD_DIM: group = d / kVGroupSize.\n'
)
if OLD4 in src:
    src = src.replace(OLD4, NEW4, 1)
    changes += 1
    print('Fix 4 (V Phase D OOB zero): applied.')
elif 'tVsV(i0, i1, i2) = Element(0);' in src:
    print('Fix 4 (V Phase D OOB zero): already present, skipping.')
else:
    sys.exit('FAIL: could not locate V Phase D n/d bounds check for Fix 4. Source may have changed.')

with open(target, 'w') as f:
    f.write(src)
print(f'Wrote {target} ({changes} new change(s) applied).')
PYEOF

# -------------------------------------------------------------------------
# Post-state verification.
# -------------------------------------------------------------------------
python3 << 'PYEOF'
import sys, os

target = os.environ['TARGET_H']
with open(target) as f:
    src = f.read()

errors = 0
checks = [
    ('K Phase B s_curr guard',  'global_g * kGroupSize < s_curr) {'),
    ('K Phase C s_curr guard',  'global_g * kGroupSize < s_curr) {'),
    ('K Phase F OOB zero',      'tKsK(i0, i1, i2) = Element(0);'),
    ('V Phase D OOB zero',      'tVsV(i0, i1, i2) = Element(0);'),
]
for name, sentinel in checks:
    count = src.count(sentinel)
    if count == 0:
        print(f'FAIL: sentinel not found: {name!r}  ({sentinel!r})')
        errors += 1
    else:
        print(f'OK  ({count}x): {name}')

if errors:
    sys.exit(f'{errors} verification error(s) — patch may be incomplete.')
print('All sentinels verified.')
PYEOF

echo
echo "OK — Phase 6K.2 fixes applied to ${TARGET_H}."
echo
echo "Next: rebuild the wheel (~1 h):"
echo "  cd ${VLLM_FA_DIR}"
echo "  TMPDIR=/workspace/tmp MAX_JOBS=4 pip install --no-build-isolation -e ."
echo
echo "Then verify (eager first, then CUDA graph):"
echo "  bash CTM_plus/Bench/scripts/verify_phase6k_bisection.sh"
