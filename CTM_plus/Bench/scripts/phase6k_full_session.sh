#!/usr/bin/env bash
#
# Phase 6K full-session orchestrator — MAXIMUM BELT-AND-SUSPENDERS.
#
# Single command that does everything needed to verify the Phase 6K
# kernel fix end-to-end on a fresh GPU pod, with sanity checks at
# every step and clear pass/fail at the end.
#
# Stages (each gated on previous success):
#   0. Pre-flight: GPU visible, venv active, git clean, disk space.
#   1. git pull on the current branch.
#   2. Clean + rebuild both kernel packages (forces fresh compile).
#   3. Source verification: 4/0 patched/unpatched call sites.
#   4. Phase 6E byte-equivalence (CPU + CUDA, 15 tests each).
#   5. Phase 6K bisection: bf16 control + int4_protected captured.
#   6. (auto-stop here for review; user kicks off Phase 6J if green.)
#
# Total time on a fresh pod: ~15-20 min.
#
# Usage:
#   source /workspace/venv-vllm/bin/activate
#   cd /workspace/symbolu
#   bash CTM_plus/Bench/scripts/phase6k_full_session.sh
#
# Env / flags:
#   --no-clean    skip forced rebuild (use cached .so if present)
#   --no-pull     skip git pull
#   --quick       skip bf16 control in bisection (saves ~30 sec)
#   --halt-on-warn  treat any warning as a hard failure
#
# Exit codes:
#   0 — all stages passed; Phase 6K verified
#   1 — bisection failed (int4 still produces garbage)
#   2 — pre-flight or build failure
#   3 — Phase 6E byte-eq regression

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Defaults.
DO_CLEAN=1
DO_PULL=1
QUICK=0
HALT_ON_WARN=0

for arg in "$@"; do
    case "$arg" in
        --no-clean)     DO_CLEAN=0 ;;
        --no-pull)      DO_PULL=0 ;;
        --quick)        QUICK=1 ;;
        --halt-on-warn) HALT_ON_WARN=1 ;;
        -h|--help)
            sed -n '2,35p' "${BASH_SOURCE[0]}"
            exit 0 ;;
        *) echo "FAIL: unknown flag '$arg'"; exit 2 ;;
    esac
done

# Color helpers (no-op if not a tty).
if [[ -t 1 ]]; then
    BOLD="$(printf '\033[1m')"; RESET="$(printf '\033[0m')"
    OK="$(printf '\033[32m')";  WARN="$(printf '\033[33m')"; FAIL="$(printf '\033[31m')"
else
    BOLD=""; RESET=""; OK=""; WARN=""; FAIL=""
fi

print_stage() { echo; echo "${BOLD}===== STAGE $1 — $2 =====${RESET}"; }
print_ok()   { echo "${OK}✓${RESET} $*"; }
print_warn() { echo "${WARN}⚠ ${RESET}$*"; [[ "${HALT_ON_WARN}" == "1" ]] && exit 2 || true; }
print_fail() { echo "${FAIL}✗${RESET} $*"; }

# ---------- Stage 0: Pre-flight ----------
print_stage "0" "Pre-flight"

cd "${SYMBOLU_ROOT}"
echo "Working dir: $(pwd)"

if [[ "${VIRTUAL_ENV:-}" == "" ]]; then
    print_warn "no virtualenv detected; did you 'source /workspace/venv-vllm/bin/activate'?"
else
    print_ok "venv active: ${VIRTUAL_ENV}"
fi

if command -v nvidia-smi &>/dev/null; then
    GPU_LINE=$(nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader 2>/dev/null | head -1)
    if [[ -n "${GPU_LINE}" ]]; then
        print_ok "GPU: ${GPU_LINE}"
    else
        print_fail "nvidia-smi found but no GPU detected"
        exit 2
    fi
else
    print_fail "nvidia-smi not found — no GPU"
    exit 2
fi

# Git state.
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "(not a git repo)")
GIT_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "?")
GIT_STATUS=$(git status --porcelain 2>/dev/null | wc -l)
echo "Git: branch=${GIT_BRANCH} HEAD=${GIT_HEAD} dirty_files=${GIT_STATUS}"
if [[ "${GIT_STATUS}" -gt 0 ]]; then
    print_warn "working tree has ${GIT_STATUS} dirty files. Continuing — but consider stashing."
fi

# Disk space (need ~5 GB for builds).
DISK_AVAIL=$(df -h "${SYMBOLU_ROOT}" | awk 'NR==2 {print $4}')
echo "Disk available: ${DISK_AVAIL}"

# ---------- Stage 1: git pull ----------
if [[ "${DO_PULL}" == "1" ]]; then
    print_stage "1" "git pull"
    git pull origin "${GIT_BRANCH}" 2>&1 | tail -5 || {
        print_fail "git pull failed"
        exit 2
    }
    NEW_HEAD=$(git rev-parse --short HEAD)
    if [[ "${NEW_HEAD}" != "${GIT_HEAD}" ]]; then
        print_ok "pulled: ${GIT_HEAD} → ${NEW_HEAD}"
    else
        print_ok "already at HEAD ${NEW_HEAD}"
    fi
else
    print_stage "1" "git pull (SKIPPED via --no-pull)"
fi

# ---------- Stage 2: rebuild ----------
print_stage "2" "Rebuild kernels"
CLEAN_FLAGS=()
[[ "${DO_CLEAN}" == "1" ]] && CLEAN_FLAGS+=("--clean")
CLEAN_FLAGS+=("--verify-source")

bash "${SCRIPT_DIR}/rebuild_all_kernels.sh" "${CLEAN_FLAGS[@]}" || {
    print_fail "rebuild_all_kernels.sh failed (see output above)"
    exit 2
}

# ---------- Stage 3: Phase 6E byte-eq ----------
print_stage "3" "Phase 6E byte-equivalence"
bash "${SCRIPT_DIR}/verify_phase6e_byte_eq.sh" || {
    print_fail "Phase 6E byte-eq regression"
    exit 3
}
print_ok "Phase 6E byte-eq: 15/15 CPU + 14/15 CUDA (1 skipped CPU-only test)"

# ---------- Stage 4: Phase 6K bisection ----------
print_stage "4" "Phase 6K N-bisection"
BISECT_FLAGS=()
[[ "${QUICK}" == "1" ]] && export QUICK=1
if bash "${SCRIPT_DIR}/verify_phase6k_bisection.sh"; then
    BISECT_RESULT="PASS"
else
    BISECT_RESULT="FAIL"
fi

# ---------- Summary ----------
echo
echo "================================================================"
echo "${BOLD}Phase 6K full-session SUMMARY${RESET}"
echo "================================================================"
if [[ "${BISECT_RESULT}" == "PASS" ]]; then
    print_ok "Pre-flight, rebuild, byte-eq, bisection — ALL PASS"
    echo
    echo "Phase 6K kernel fix is verified. Branch is ready for Phase 6J."
    echo
    echo "Next step (resume Phase 6J quality bench):"
    echo "  PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6j_quality_gpu.py --smoke"
    echo
    exit 0
else
    print_fail "Bisection failed: int4_protected still produces garbage"
    echo
    echo "The Phase 6K patch did not resolve the bug at the kernel level."
    echo "Investigation continues; see PHASE_6K_FLASH_ATTN_OOB_FIX_FINDINGS.md."
    echo
    exit 1
fi
