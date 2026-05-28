#!/usr/bin/env bash
#
# Phase 6K — apply the int4_packed_load s_curr fix to vllm-flash-attn-dev.
#
# Idempotent: detects "already patched" state and skips reapply.
#
# Usage:
#   bash CTM_plus/Bench/scripts/apply_phase6k_flash_attn_oob_fix.sh
#
# Then rebuild the wheel:
#   cd /workspace/dev/vllm-flash-attn-dev
#   pip install --no-build-isolation -e .
#
# Then verify with the bisection script in PHASE_6K_FLASH_ATTN_OOB_FIX_FINDINGS.md.

set -euo pipefail

VLLM_FA_DIR="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
KERNEL_H="${VLLM_FA_DIR}/csrc/flash_attn/src/flash_fwd_kernel.h"

if [[ ! -f "${KERNEL_H}" ]]; then
    echo "FAIL: ${KERNEL_H} does not exist. Set VLLM_FA_DIR if the fork is at a different path."
    exit 2
fi

# Idempotency check: do all 4 call sites already use binfo.actual_seqlen_k?
n_patched=$(grep -c "n_block \* Kernel_traits::kBlockN, binfo.actual_seqlen_k);" "${KERNEL_H}" || true)
n_unpatched=$(grep -c "n_block \* Kernel_traits::kBlockN, params.seqlen_k);" "${KERNEL_H}" || true)
echo "Pre-state: ${n_patched} already-patched, ${n_unpatched} still-unpatched."

if [[ "${n_unpatched}" -eq 0 && "${n_patched}" -eq 4 ]]; then
    echo "All 4 call sites already patched. Nothing to do."
    exit 0
fi
if [[ "${n_unpatched}" -ne 4 ]]; then
    echo "FAIL: expected exactly 4 unpatched call sites, found ${n_unpatched}."
    echo "      The kernel source may have diverged from the version this patch was built against."
    echo "      Inspect with: grep -n 'n_block \\* Kernel_traits::kBlockN' ${KERNEL_H}"
    exit 3
fi

# Back up before patching (idempotent backup — only create if not present).
if [[ ! -f "${KERNEL_H}.phase6k_backup" ]]; then
    cp "${KERNEL_H}" "${KERNEL_H}.phase6k_backup"
    echo "Backed up to ${KERNEL_H}.phase6k_backup"
fi

# Apply: change all 4 occurrences of "params.seqlen_k" to "binfo.actual_seqlen_k"
# specifically in the trailing arg of int4_packed_load_{K,V}_block calls.
python3 -c "
import re, sys
p = '${KERNEL_H}'
src = open(p).read()
pat = r'(n_block \* Kernel_traits::kBlockN, )params\.seqlen_k(\);)'
new_src, n = re.subn(pat, r'\1binfo.actual_seqlen_k\2', src)
if n != 4:
    sys.exit(f'FAIL: expected 4 substitutions, applied {n}')
open(p, 'w').write(new_src)
print(f'Applied {n} substitutions.')
"

# Verify post-state.
n_patched=$(grep -c "n_block \* Kernel_traits::kBlockN, binfo.actual_seqlen_k);" "${KERNEL_H}")
n_unpatched=$(grep -c "n_block \* Kernel_traits::kBlockN, params.seqlen_k);" "${KERNEL_H}" || true)
echo "Post-state: ${n_patched} patched, ${n_unpatched} unpatched."

if [[ "${n_patched}" -ne 4 || "${n_unpatched}" -ne 0 ]]; then
    echo "FAIL: post-state inconsistent."
    exit 4
fi
echo "OK — Phase 6K patch applied to ${KERNEL_H}."
echo
echo "Next: rebuild the wheel:"
echo "  cd ${VLLM_FA_DIR}"
echo "  pip install --no-build-isolation -e ."
