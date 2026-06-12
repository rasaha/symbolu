#!/usr/bin/env bash
#
# Rebuild all custom CUDA kernels for the int4_protected project.
#
# Performs in order:
#   0. Enforce the stack pins (vllm==0.7.3, torch==2.5.1+cu121) BEFORE building —
#      install/restore if drifted (a wrong stack builds but won't import / runs
#      garbage). Skip with SKIP_VERSION_CHECK=1.
#   0b. If the fork dev tree is missing, create /workspace/dev and untar the fork
#       tarball — just drop vllm-flash-attn-dev-src.tar.gz under /workspace.
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
#   FA_TARBALL         — default /workspace/vllm-flash-attn-dev-src.tar.gz
#                        (untarred into /workspace/dev when VLLM_FA_DIR is missing)
#   INT4_PROT_C_DIR    — default <symbolu>/CTM_plus/CUDA_int4_protected
#   REQUIRE_VLLM       — default 0.7.3   (enforced before build)
#   REQUIRE_TORCH      — default 2.5.1   (enforced before build, cu121 index)
#   SKIP_VERSION_CHECK=1 — skip the pin enforcement (step 0)
#   SKIP_PATCH=1       — skip the Phase 6K patch step
#   MAX_JOBS           — cmake/nvcc build parallelism. Default: auto-sized from
#                        MemAvailable at ~6 GB per nvcc job, clamped [4, 32]
#                        and <= nproc. The fork's setup.py otherwise defaults
#                        to nproc, and on a 128-256 vCPU pod that many parallel
#                        nvcc jobs (~2-6 GB each) OOMs the box. Pin explicitly
#                        (e.g. MAX_JOBS=8) on RAM-tight or shared pods.
#   NVCC_THREADS       — optional, forwarded to the fork's build if set.
#
# Full build logs land in /workspace/dev/build-logs/ — read THOSE on failure;
# the console shows only the tail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

VLLM_FA_DIR="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
FA_TARBALL="${FA_TARBALL:-/workspace/vllm-flash-attn-dev-src.tar.gz}"
INT4_PROT_C_DIR="${INT4_PROT_C_DIR:-${SYMBOLU_ROOT}/CTM_plus/CUDA_int4_protected}"
SKIP_PATCH="${SKIP_PATCH:-0}"
SKIP_VERSION_CHECK="${SKIP_VERSION_CHECK:-0}"
REQUIRE_VLLM="${REQUIRE_VLLM:-0.7.3}"
REQUIRE_TORCH="${REQUIRE_TORCH:-2.5.1}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu121}"

# Parse flags.
DO_CLEAN=0
DO_VERIFY_SOURCE=0
for arg in "$@"; do
    case "$arg" in
        --clean)         DO_CLEAN=1 ;;
        --verify-source) DO_VERIFY_SOURCE=1 ;;
        -h|--help)
            sed -n '2,44p' "${BASH_SOURCE[0]}"
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

# Sanity: venv active? (Fresh pods may not HAVE /workspace/venv-vllm — that is
# fine as long as the pins below pass: the kernels then install into whichever
# python is printed here, and every bench script uses that same interpreter.)
if [[ "${VIRTUAL_ENV:-}" == "" ]]; then
    echo "WARNING: no virtualenv detected (no /workspace/venv-vllm on this pod?)."
    echo "         Proceeding with: $(command -v python)  ($(python -V 2>&1))"
    echo "         OK if the pin check below passes — kernels target that python."
fi

# ----- Step 0: enforce the stack pins BEFORE building. A kernel built against
# the wrong torch/vllm builds fine but then fails to import (ABI mismatch) or
# runs garbage. Order matters: installing vllm can SWAP torch, so fix vllm
# FIRST, then restore torch. -----
echo
if [[ "${SKIP_VERSION_CHECK}" == "1" ]]; then
    echo "[0/5] Pin enforcement SKIPPED (SKIP_VERSION_CHECK=1)"
else
    echo "[0/5] Enforcing pins: vllm==${REQUIRE_VLLM}, torch==${REQUIRE_TORCH} (cu121)..."
    _pkg_ver() { python -c "import ${1}; print(${1}.__version__)" 2>/dev/null || echo ""; }

    cur_vllm="$(_pkg_ver vllm)"
    if [[ "${cur_vllm}" != "${REQUIRE_VLLM}" ]]; then
        echo "    vllm is '${cur_vllm:-<none>}' != ${REQUIRE_VLLM} -> installing vllm==${REQUIRE_VLLM}..."
        pip install "vllm==${REQUIRE_VLLM}" 2>&1 | tail -5 \
            || { echo "FAIL: could not install vllm==${REQUIRE_VLLM}."; exit 2; }
    else
        echo "    vllm ${cur_vllm}: OK"
    fi

    # torch AFTER vllm (vllm's install can pull a different torch). Compare on the
    # base version (ignore the +cuXXX local tag) so 2.5.1 == 2.5.1+cu121.
    cur_torch="$(_pkg_ver torch)"
    if [[ "${cur_torch%%+*}" != "${REQUIRE_TORCH}" ]]; then
        echo "    torch is '${cur_torch:-<none>}' != ${REQUIRE_TORCH} -> restoring torch==${REQUIRE_TORCH} (--no-deps, cu121)..."
        pip install --no-deps --force-reinstall "torch==${REQUIRE_TORCH}" --index-url "${TORCH_INDEX}" 2>&1 | tail -5 \
            || { echo "FAIL: could not install torch==${REQUIRE_TORCH}."; exit 2; }
    else
        echo "    torch ${cur_torch}: OK"
    fi

    # Assert both are correct now — a mismatch here means the rebuild is unsafe.
    fin_vllm="$(_pkg_ver vllm)"; fin_torch="$(_pkg_ver torch)"
    echo "    -> vllm=${fin_vllm:-<none>}  torch=${fin_torch:-<none>}"
    [[ "${fin_vllm}" == "${REQUIRE_VLLM}" ]] \
        || { echo "FAIL: vllm is ${fin_vllm:-<none>} after fix (want ${REQUIRE_VLLM})."; exit 2; }
    [[ "${fin_torch%%+*}" == "${REQUIRE_TORCH}" ]] \
        || { echo "FAIL: torch is ${fin_torch:-<none>} after fix (want ${REQUIRE_TORCH})."; exit 2; }
fi

# Sanity: GPU visible? (build doesn't require it but bench will.)
if command -v nvidia-smi &>/dev/null; then
    GPU_LINE=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    echo "GPU: ${GPU_LINE:-none detected}"
fi

# ----- Step 0b: ensure the fork dev tree exists; untar it if missing. The fork
# is a vendored working copy (NOT in the GitHub repo) — drop the tarball under
# /workspace and this creates /workspace/dev and unpacks it. -----
echo
if [[ ! -d "${VLLM_FA_DIR}" ]]; then
    if [[ -f "${FA_TARBALL}" ]]; then
        FA_PARENT="$(dirname "${VLLM_FA_DIR}")"
        echo "[0b] ${VLLM_FA_DIR} missing -> creating ${FA_PARENT} and untarring ${FA_TARBALL}..."
        mkdir -p "${FA_PARENT}"
        (cd "${FA_PARENT}" && tar xzf "${FA_TARBALL}") \
            || { echo "FAIL: untar of ${FA_TARBALL} failed."; exit 2; }
        if [[ ! -d "${VLLM_FA_DIR}" ]]; then
            echo "FAIL: ${FA_TARBALL} did not unpack to ${VLLM_FA_DIR}."
            echo "      Either re-pack so it extracts to '$(basename "${VLLM_FA_DIR}")/',"
            echo "      or point VLLM_FA_DIR at the unpacked path."
            exit 2
        fi
    else
        echo "FAIL: ${VLLM_FA_DIR} does not exist and no tarball at ${FA_TARBALL}."
        echo "      Place vllm-flash-attn-dev-src.tar.gz under /workspace (or set FA_TARBALL)."
        exit 2
    fi
else
    echo "[0b] Fork dev tree present: ${VLLM_FA_DIR}"
fi
# The fork must look complete — the patched kernel header has to be there.
if [[ ! -f "${VLLM_FA_DIR}/csrc/flash_attn/src/flash_fwd_kernel.h" ]]; then
    echo "FAIL: fork at ${VLLM_FA_DIR} looks incomplete (missing csrc/flash_attn/src/flash_fwd_kernel.h)."
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

# Parallelism guard. The fork's setup.py passes -j=<MAX_JOBS or nproc> to cmake.
# The binding constraint is RAM, not cores: each parallel nvcc job compiling the
# cutlass-templated FA TUs peaks ~2-6 GB (cicc/ptxas stage), so -j=nproc on a
# 256-vCPU pod asks for ~0.5-1 TB and the OOM killer ends the build. Unless the
# operator pinned MAX_JOBS, size it from MemAvailable at ~6 GB/job, clamped to
# [4, 32] and <= nproc (past ~32 the finite TU count + link contention give
# diminishing returns anyway, single-digit minutes at best).
if [[ -z "${MAX_JOBS:-}" ]]; then
    _NPROC="$(nproc 2>/dev/null || echo 16)"
    _MEM_GB="$(awk '/MemAvailable/ {printf "%d", $2/1048576}' /proc/meminfo 2>/dev/null || echo 0)"
    if [[ "${_MEM_GB}" -gt 0 ]]; then
        MAX_JOBS=$(( _MEM_GB / 6 ))
    else
        MAX_JOBS=16
    fi
    if (( MAX_JOBS > 32 )); then MAX_JOBS=32; fi
    if (( MAX_JOBS > _NPROC )); then MAX_JOBS=${_NPROC}; fi
    if (( MAX_JOBS < 4 )); then MAX_JOBS=4; fi
    echo "      MAX_JOBS=${MAX_JOBS} (auto: MemAvailable=${_MEM_GB}GB at ~6GB/nvcc-job, clamped [4,32], <=nproc=${_NPROC})"
else
    echo "      MAX_JOBS=${MAX_JOBS} (operator-pinned)"
fi
export MAX_JOBS
echo "      (override: MAX_JOBS=N bash ${BASH_SOURCE[0]} ...; leave headroom if other RAM-hungry jobs share the box)"

# Full build logs: the real compiler error is never in the last 12 lines.
LOG_DIR="${LOG_DIR:-/workspace/dev/build-logs}"
mkdir -p "${LOG_DIR}" 2>/dev/null || LOG_DIR="$(mktemp -d)"

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
FA_BUILD_LOG="${LOG_DIR}/fa_wheel_build_$(date +%Y%m%d_%H%M%S).log"
echo "      full build log: ${FA_BUILD_LOG}"
if ! (cd "${VLLM_FA_DIR}" && rm -rf dist && \
        pip wheel --no-build-isolation --no-deps -w dist . >"${FA_BUILD_LOG}" 2>&1); then
    echo "FAIL: vllm-flash-attn wheel build failed. Last 40 log lines:"
    tail -40 "${FA_BUILD_LOG}"
    if grep -qiE "(internal compiler error: )?Killed( signal)?" "${FA_BUILD_LOG}" \
       || (dmesg 2>/dev/null | tail -80 | grep -qiE "out of memory|oom-kill"); then
        echo
        echo "  ^ OOM signature detected: the kernel's OOM killer shot the compilers."
        echo "    Retry with lower parallelism (current MAX_JOBS=${MAX_JOBS}):"
        echo "      MAX_JOBS=8 bash ${BASH_SOURCE[0]} --clean"
        echo "    and keep big jobs (training runs) off the box during the build."
    fi
    echo "  full log: ${FA_BUILD_LOG}"
    exit 3
fi
tail -3 "${FA_BUILD_LOG}"
_guard_torch

# Copy the freshly-built wheel's .so + wrappers over the vendored slot.
echo "  Installing built wheel into the vendored slot..."
bash "${SCRIPT_DIR}/install_dev_vllm_flash_attn.sh" 2>&1 | tail -15
_guard_torch

# ----- Step 4: Rebuild int4_protected_C -----
echo
echo "[4/5] Rebuilding int4_protected_C (Phase 6E fused kernels)..."
echo "      (this takes ~1-2 min)"
I4_BUILD_LOG="${LOG_DIR}/int4C_build_$(date +%Y%m%d_%H%M%S).log"
echo "      full build log: ${I4_BUILD_LOG}"
if ! (cd "${INT4_PROT_C_DIR}" && \
        pip install --no-build-isolation --no-deps -e . >"${I4_BUILD_LOG}" 2>&1); then
    echo "FAIL: int4_protected_C build failed. Last 40 log lines:"
    tail -40 "${I4_BUILD_LOG}"
    echo "  full log: ${I4_BUILD_LOG}"
    exit 3
fi
tail -3 "${I4_BUILD_LOG}"
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
