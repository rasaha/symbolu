#!/usr/bin/env bash
#
# Rebuild all custom CUDA kernels for the int4_protected project.
#
# Performs in order:
#   1. Apply the Phase 6K patch to vllm-flash-attn-dev (idempotent).
#   2. (--clean only) Wipe build artifacts: build/ dir, *.so, *.egg-info.
#   3. Rebuild vllm-flash-attn-dev with --no-build-isolation.
#   4. Rebuild int4_protected_C with --no-build-isolation.
#   5. Import both modules to sanity-check.
#   6. (--verify-source only) Confirm patched source matches installed .so
#      by re-reading the file and asserting binfo.actual_seqlen_k appears.
#
# After this, run `verify_phase6k_bisection.sh` to confirm coherent output.
#
# Usage:
#   bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh             # default
#   bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean     # force fresh
#   bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean --verify-source
#
# Env overrides:
#   VLLM_FA_DIR        — default /workspace/dev/vllm-flash-attn-dev
#   INT4_PROT_C_DIR    — default <symbolu>/CTM_plus/CUDA_int4_protected
#   SKIP_PATCH=1       — skip the Phase 6K patch step

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

VLLM_FA_DIR="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
INT4_PROT_C_DIR="${INT4_PROT_C_DIR:-${SYMBOLU_ROOT}/CTM_plus/CUDA_int4_protected}"
SKIP_PATCH="${SKIP_PATCH:-0}"

# Parse flags.
DO_CLEAN=0
DO_VERIFY_SOURCE=0
for arg in "$@"; do
    case "$arg" in
        --clean)         DO_CLEAN=1 ;;
        --verify-source) DO_VERIFY_SOURCE=1 ;;
        -h|--help)
            sed -n '2,30p' "${BASH_SOURCE[0]}"
            exit 0 ;;
        *)
            echo "FAIL: unknown flag '$arg'"
            exit 2 ;;
    esac
done

echo "================================================================"
echo "Rebuild all kernels   (clean=$DO_CLEAN verify_source=$DO_VERIFY_SOURCE)"
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

# Sanity: GPU visible? (build doesn't require it but bench will.)
if command -v nvidia-smi &>/dev/null; then
    GPU_LINE=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    echo "GPU: ${GPU_LINE:-none detected}"
fi

# Sanity: source dirs exist?
if [[ ! -d "${VLLM_FA_DIR}" ]]; then
    echo "FAIL: ${VLLM_FA_DIR} does not exist."
    exit 2
fi
if [[ ! -d "${INT4_PROT_C_DIR}" ]]; then
    echo "FAIL: ${INT4_PROT_C_DIR} does not exist."
    exit 2
fi

# ----- Step 1: Phase 6K patch -----
echo
if [[ "${SKIP_PATCH}" == "1" ]]; then
    echo "[1/5] SKIPPED (SKIP_PATCH=1)"
else
    echo "[1/5] Applying Phase 6K patch to vllm-flash-attn-dev..."
    VLLM_FA_DIR="${VLLM_FA_DIR}" bash "${SCRIPT_DIR}/apply_phase6k_flash_attn_oob_fix.sh"
fi

# ----- Step 2: Clean build artifacts (optional) -----
echo
if [[ "${DO_CLEAN}" == "1" ]]; then
    echo "[2/5] Cleaning build artifacts in BOTH kernel packages..."
    for D in "${VLLM_FA_DIR}" "${INT4_PROT_C_DIR}"; do
        echo "  Cleaning ${D}/build/ + *.egg-info + *.so..."
        rm -rf "${D}/build/" "${D}"/*.egg-info 2>/dev/null || true
        find "${D}" -maxdepth 4 -name "*.so" -delete 2>/dev/null || true
    done
    # Also uninstall the wheel from venv so pip rebuilds from scratch.
    pip uninstall -y vllm-flash-attn int4_protected_C 2>&1 | tail -3 || true
    echo "  Clean done."
else
    echo "[2/5] SKIPPED (no --clean flag)"
fi

# ----- Step 3: Rebuild vllm-flash-attn-dev -----
echo
echo "[3/5] Rebuilding vllm-flash-attn-dev..."
echo "      (this takes ~3-8 min on first build, ~30 sec on cached incremental)"
(cd "${VLLM_FA_DIR}" && pip install --no-build-isolation -e . 2>&1 | tail -10)

# ----- Step 4: Rebuild int4_protected_C -----
echo
echo "[4/5] Rebuilding int4_protected_C (Phase 6E fused kernels)..."
echo "      (this takes ~1-2 min)"
(cd "${INT4_PROT_C_DIR}" && pip install --no-build-isolation -e . 2>&1 | tail -8)

# ----- Step 5: Import sanity -----
echo
echo "[5/5] Import sanity..."
python -c "
import torch
print(f'  torch:   {torch.__version__}  cuda={torch.cuda.is_available()}')
import vllm
print(f'  vllm:    {vllm.__version__}')
import vllm.vllm_flash_attn
print(f'  vllm.vllm_flash_attn:  OK at {vllm.vllm_flash_attn.__file__}')
import int4_protected_C
exports = [s for s in dir(int4_protected_C) if not s.startswith('_')]
print(f'  int4_protected_C:      OK  exports={exports}')
" || {
    echo "FAIL: one of the imports failed; check the build output above."
    exit 3
}

# ----- Optional: Verify patched source -----
if [[ "${DO_VERIFY_SOURCE}" == "1" ]]; then
    echo
    echo "[verify] Confirming patched source on disk..."
    KERNEL_H="${VLLM_FA_DIR}/csrc/flash_attn/src/flash_fwd_kernel.h"
    n_patched=$(grep -c "n_block \* Kernel_traits::kBlockN, binfo.actual_seqlen_k);" "${KERNEL_H}")
    n_unpatched=$(grep -c "n_block \* Kernel_traits::kBlockN, params.seqlen_k);" "${KERNEL_H}" || true)
    if [[ "${n_patched}" -ne 4 || "${n_unpatched}" -ne 0 ]]; then
        echo "FAIL: source not fully patched (patched=${n_patched}, unpatched=${n_unpatched})"
        exit 4
    fi
    echo "  Source verified: 4 patched call sites, 0 unpatched."
fi

echo
echo "================================================================"
echo "Rebuild complete."
echo "Next: bash ${SCRIPT_DIR}/verify_phase6k_bisection.sh"
echo "================================================================"
