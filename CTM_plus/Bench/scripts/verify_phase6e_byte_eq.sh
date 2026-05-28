#!/usr/bin/env bash
#
# Phase 6E byte-equivalence verifier wrapper.
#
# Runs the test suite that verifies the Phase 6E fused decode-write
# CUDA kernels produce byte-identical state mutations to the inline
# Python op chain. This is the correctness floor for Phase 6E.
#
# Two modes:
#   - CPU: 15 unit tests covering B=1..32, multi-block boundaries,
#          inactive masks, non-contiguous QKV views. Uses CPU tensors
#          + the Python ref path on both sides; ~1 sec.
#   - CUDA: same suite but on CUDA tensors with the actual fused
#           kernels active. Requires a GPU.
#
# Usage:
#   bash CTM_plus/Bench/scripts/verify_phase6e_byte_eq.sh           # both modes
#   bash CTM_plus/Bench/scripts/verify_phase6e_byte_eq.sh --cpu     # CPU only
#   bash CTM_plus/Bench/scripts/verify_phase6e_byte_eq.sh --cuda    # CUDA only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

export PYTHONPATH="${SYMBOLU_ROOT}/CTM_plus/KVPolicy:${PYTHONPATH:-}"

DO_CPU=1
DO_CUDA=1
for arg in "$@"; do
    case "$arg" in
        --cpu)  DO_CUDA=0 ;;
        --cuda) DO_CPU=0 ;;
        *) echo "FAIL: unknown flag '$arg'"; exit 2 ;;
    esac
done

VERIFIER="${SYMBOLU_ROOT}/CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py"

if [[ ! -f "${VERIFIER}" ]]; then
    echo "FAIL: ${VERIFIER} not found."
    exit 2
fi

echo "================================================================"
echo "Phase 6E byte-equivalence verifier"
echo "================================================================"

if [[ "${DO_CPU}" == "1" ]]; then
    echo
    echo "----- CPU mode -----"
    PHASE6E_FUSED_WRITER=1 python "${VERIFIER}" 2>&1 | tail -20
    EC=${PIPESTATUS[0]}
    if [[ "${EC}" -ne 0 ]]; then
        echo "FAIL: CPU verifier exited code ${EC}"
        exit ${EC}
    fi
fi

if [[ "${DO_CUDA}" == "1" ]]; then
    echo
    echo "----- CUDA mode (requires GPU) -----"
    if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
        echo "SKIP: CUDA not available."
    else
        PHASE6E_FUSED_WRITER=1 python "${VERIFIER}" --device cuda --verbose 2>&1 | tail -25
        EC=${PIPESTATUS[0]}
        if [[ "${EC}" -ne 0 ]]; then
            echo "FAIL: CUDA verifier exited code ${EC}"
            exit ${EC}
        fi
    fi
fi

echo
echo "================================================================"
echo "Phase 6E byte-equivalence: PASS"
echo "================================================================"
