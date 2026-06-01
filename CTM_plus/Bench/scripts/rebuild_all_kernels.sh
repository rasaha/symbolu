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

# ----- Record torch version BEFORE builds (the kernel setup.py files declare a
# torch dep; pip can silently DOWNGRADE/SWAP torch during -e install even with
# --no-build-isolation. We pin it here and restore if a build clobbers it). -----
TORCH_BEFORE="$(python -c 'import torch; print(torch.__version__)' 2>/dev/null || echo '')"
echo "torch before builds: ${TORCH_BEFORE:-<none>}"

_guard_torch() {
    # If torch changed (or vanished), force-reinstall the original WITHOUT deps.
    local now
    now="$(python -c 'import torch; print(torch.__version__)' 2>/dev/null || echo '')"
    if [[ -n "${TORCH_BEFORE}" && "${now}" != "${TORCH_BEFORE}" ]]; then
        echo "!!! torch changed ${TORCH_BEFORE} -> ${now:-<gone>} during build; restoring..."
        local base="${TORCH_BEFORE%%+*}"   # strip +cu121 suffix for the ==spec
        local idx=""
        [[ "${TORCH_BEFORE}" == *cu121* ]] && idx="--index-url https://download.pytorch.org/whl/cu121"
        pip install --no-deps --force-reinstall "torch==${base}" ${idx} 2>&1 | tail -3
    fi
}

# ----- Step 3: Rebuild vllm-flash-attn-dev + INSTALL INTO VENDORED SLOT -----
# CRITICAL: vLLM *vendors* flash-attn inside site-packages/vllm/vllm_flash_attn/.
# A plain `pip install -e .` builds the fork in-place but does NOT put the custom
# `flash_attn_with_int4_kvcache` symbol into the vendored slot, so the int4 READ
# path fails at runtime with "cannot import name flash_attn_with_int4_kvcache".
# The fix (per PHASE_6K7 findings): build a WHEEL, then copy its .so + wrappers
# OVER the vendored copy via install_dev_vllm_flash_attn.sh.
echo
echo "[3/5] Rebuilding vllm-flash-attn-dev (wheel) + installing into vendored slot..."
echo "      (~10-15 min first build; set TORCH_CUDA_ARCH_LIST=8.0 to scope to A100)"

# nvcc writes temp files under TMPDIR; a fresh/cleaned pod may lack it.
export TMPDIR="${TMPDIR:-/workspace/tmp}"
mkdir -p "${TMPDIR}"

# Back up the CURRENT (stock) vendored copy if no backup exists — the install
# script refuses to run without it, and a fresh pod won't have one.
FA_VENDORED="$(python -c 'import vllm, os; print(os.path.join(os.path.dirname(vllm.__file__), "vllm_flash_attn"))' 2>/dev/null || echo '')"
BACKUP_DIR=/workspace/dev/build-logs/vllm_flash_attn_vendored_backup
if [[ -n "${FA_VENDORED}" && -d "${FA_VENDORED}" && ! -d "${BACKUP_DIR}" ]]; then
    echo "  Creating vendored backup: ${BACKUP_DIR}"
    mkdir -p /workspace/dev/build-logs
    cp -r "${FA_VENDORED}" "${BACKUP_DIR}"
fi

# Build the wheel (--no-deps: do NOT let pip touch torch/other deps).
(cd "${VLLM_FA_DIR}" && rm -rf dist && \
    pip wheel --no-build-isolation --no-deps -w dist . 2>&1 | tail -12)
_guard_torch

# Copy the freshly-built wheel's .so + wrappers over the vendored slot.
echo "  Installing built wheel into the vendored slot..."
bash "${SCRIPT_DIR}/install_dev_vllm_flash_attn.sh" 2>&1 | tail -15
_guard_torch

# ----- Step 4: Rebuild int4_protected_C -----
echo
echo "[4/5] Rebuilding int4_protected_C (Phase 6E fused kernels)..."
echo "      (this takes ~1-2 min)"
(cd "${INT4_PROT_C_DIR}" && pip install --no-build-isolation --no-deps -e . 2>&1 | tail -8)
_guard_torch

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
# The int4 READ path needs this custom symbol in the VENDORED slot. If it's
# missing, the fork built but was not installed over the vendored copy (step 3).
assert hasattr(vllm.vllm_flash_attn, 'flash_attn_with_int4_kvcache'), (
    'flash_attn_with_int4_kvcache MISSING from the vendored vllm_flash_attn — '
    'the fork wheel was not installed into the vendored slot. Re-run step 3 / '
    'install_dev_vllm_flash_attn.sh.')
print('  vllm_flash_attn.flash_attn_with_int4_kvcache:  PRESENT')
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
