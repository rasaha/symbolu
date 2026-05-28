#!/usr/bin/env bash
#
# Rebuild all custom CUDA kernels for the int4_protected project.
#
# Run this on a fresh GPU pod after `git pull` to restore the build
# state from the source tree. Idempotent — if a build is already
# current, the pip install -e is mostly a no-op.
#
# Performs three steps in order:
#   1. Apply the Phase 6K patch to vllm-flash-attn-dev (idempotent).
#   2. Rebuild vllm-flash-attn-dev (compiles the patched kernel).
#   3. Rebuild int4_protected_C (Phase 6E fused decode-write kernels).
#
# After this, run `verify_phase6k_bisection.sh` (sibling script) to
# confirm the Phase 6K fix produces coherent output.
#
# Usage:
#   source /workspace/venv-vllm/bin/activate
#   cd /workspace/symbolu
#   bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh
#
# Env overrides:
#   VLLM_FA_DIR        — path to vllm-flash-attn-dev source
#                        (default: /workspace/dev/vllm-flash-attn-dev)
#   INT4_PROT_C_DIR    — path to int4_protected_C source
#                        (default: <symbolu>/CTM_plus/CUDA_int4_protected)
#   SKIP_PATCH         — set to 1 to skip the Phase 6K patch step
#                        (use if patch is already permanent or merged upstream)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

VLLM_FA_DIR="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
INT4_PROT_C_DIR="${INT4_PROT_C_DIR:-${SYMBOLU_ROOT}/CTM_plus/CUDA_int4_protected}"
SKIP_PATCH="${SKIP_PATCH:-0}"

echo "================================================================"
echo "Rebuild all kernels"
echo "================================================================"
echo "symbolu root:     ${SYMBOLU_ROOT}"
echo "vllm-flash-attn:  ${VLLM_FA_DIR}"
echo "int4_protected_C: ${INT4_PROT_C_DIR}"
echo

# Sanity: venv active?
if [[ "${VIRTUAL_ENV:-}" == "" ]]; then
    echo "WARNING: no virtualenv detected. Did you 'source /workspace/venv-vllm/bin/activate'?"
    echo "         Continuing, but pip install -e may not target the right env."
fi

# Sanity: source dirs exist?
if [[ ! -d "${VLLM_FA_DIR}" ]]; then
    echo "FAIL: ${VLLM_FA_DIR} does not exist. Set VLLM_FA_DIR if the source is elsewhere."
    exit 2
fi
if [[ ! -d "${INT4_PROT_C_DIR}" ]]; then
    echo "FAIL: ${INT4_PROT_C_DIR} does not exist. Set INT4_PROT_C_DIR if the source is elsewhere."
    exit 2
fi

# ----- Step 1: Phase 6K patch -----
if [[ "${SKIP_PATCH}" == "1" ]]; then
    echo "[1/3] SKIPPED (SKIP_PATCH=1)"
else
    echo "[1/3] Applying Phase 6K patch to vllm-flash-attn-dev..."
    VLLM_FA_DIR="${VLLM_FA_DIR}" bash "${SCRIPT_DIR}/apply_phase6k_flash_attn_oob_fix.sh"
    echo
fi

# ----- Step 2: Rebuild vllm-flash-attn-dev -----
echo "[2/3] Rebuilding vllm-flash-attn-dev..."
echo "      (this takes ~3-8 min depending on cache state)"
(cd "${VLLM_FA_DIR}" && pip install --no-build-isolation -e . 2>&1 | tail -8)
echo

# ----- Step 3: Rebuild int4_protected_C -----
echo "[3/3] Rebuilding int4_protected_C (Phase 6E fused kernels)..."
echo "      (this takes ~1-2 min)"
(cd "${INT4_PROT_C_DIR}" && pip install --no-build-isolation -e . 2>&1 | tail -6)
echo

# Sanity: verify both modules importable.
echo "----- Import sanity -----"
python -c "
import torch
print(f'torch: {torch.__version__}, cuda available: {torch.cuda.is_available()}')

import vllm.vllm_flash_attn
print('vllm.vllm_flash_attn imported OK')

import int4_protected_C
print('int4_protected_C imported OK; exports:', [s for s in dir(int4_protected_C) if not s.startswith('_')])
" || {
    echo "FAIL: one of the imports failed; check the build output above."
    exit 3
}

echo
echo "================================================================"
echo "Rebuild complete. Next: verify with the bisection script:"
echo "  bash CTM_plus/Bench/scripts/verify_phase6k_bisection.sh"
echo "================================================================"
