#!/usr/bin/env bash
# Phase 6F — CORRECTNESS ORACLE for the read-path kernel fusion (Test 3).
#
# THE non-negotiable gate. Run this on the pod BEFORE and AFTER any change to
# the fused int4 read-path kernel (gated behind PHASE6F_FUSED_READ=1). It runs
# every correctness check with the flag OFF (reference) and ON (experimental)
# and aggregates PASS/FAIL. A faster-but-wrong gather is a FAILURE, not a win.
#
# Gates (all must be GREEN with the flag ON):
#   1. byte-equivalence       verify_phase6e_fused_byte_eq.py  (token-ID exact)
#   2. hard needle + COLLAPSE phase6k12_hard_needle.py         (no collapse)
#   3. token-agreement        bench_phase6j_quality_gpu.py     (>= 20.4, within noise)
#
# IMPORTANT: this script does NOT implement the kernel. It is the harness that
# proves a (future) fused kernel preserves semantics. Until the kernel exists,
# running it with the flag ON simply re-confirms the baseline (the flag is a
# no-op), which establishes the GREEN reference so regressions are detectable.
#
# Usage (on the pod):
#   source /workspace/venv-vllm/bin/activate
#   bash CTM_plus/Bench/scripts/phase6f_correctness_oracle.sh
#
# Env overrides: MODEL, MML, OUT, FLAG (default PHASE6F_FUSED_READ).
set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KVP_TESTS="$SCRIPTS_DIR/../../KVPolicy/tests"
PYTHON="${PYTHON:-python}"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
MML="${MML:-8192}"
FLAG="${FLAG:-PHASE6F_FUSED_READ}"
OUT="${OUT:-$SCRIPTS_DIR/../bench_out/phase6f}"
mkdir -p "$OUT"

PASS=0; FAIL=0
declare -a RESULTS

run_gate () {
    local label="$1"; shift
    echo
    echo "------------------------------------------------------------------"
    echo ">>> GATE: $label"
    echo "    cmd: $*"
    echo "------------------------------------------------------------------"
    "$@" 2>&1 | tee "$OUT/${label// /_}.log"
    local rc=${PIPESTATUS[0]}
    if [[ $rc -eq 0 ]]; then
        PASS=$((PASS+1)); RESULTS+=("PASS  $label")
        echo ">>> $label: PASS"
    else
        FAIL=$((FAIL+1)); RESULTS+=("FAIL  $label (exit $rc)")
        echo "!!! $label: FAIL (exit $rc)"
    fi
}

echo "=================================================================="
echo "Phase 6F correctness oracle — model=$MODEL mml=$MML flag=$FLAG"
echo "=================================================================="

# --- 1. byte-equivalence (flag OFF reference, then ON) --------------------
# verify_phase6e_fused_byte_eq.py asserts the fused path mutates state
# byte-identically to the inline op chain. It honors PHASE6E_FUSED_WRITER;
# we additionally set the read-path flag so the read fusion is exercised too.
run_gate "byte-eq flag=off" \
    env PHASE6E_FUSED_WRITER=1 "${FLAG}=0" "$PYTHON" \
        "$KVP_TESTS/verify_phase6e_fused_byte_eq.py"
run_gate "byte-eq flag=on" \
    env PHASE6E_FUSED_WRITER=1 "${FLAG}=1" "$PYTHON" \
        "$KVP_TESTS/verify_phase6e_fused_byte_eq.py"

# --- 2. hard needle + COLLAPSE (flag OFF, then ON) ------------------------
# phase6k12 worker honors CELL + ENFORCE_EAGER from the env; we pass the
# read-path flag through. A COLLAPSE>0 in the buckets is a hard fail — the
# worker exit code is 0 on a clean run; we additionally grep the JSON.
run_gate "hard-needle flag=off" \
    env CELL=protected ENFORCE_EAGER=1 PHASE6E_FUSED_WRITER=1 "${FLAG}=0" \
        OUTPUT="$OUT/needle_off.json" \
        "$PYTHON" "$SCRIPTS_DIR/phase6k12_hard_needle.py" --worker --mml "$MML"
run_gate "hard-needle flag=on" \
    env CELL=protected ENFORCE_EAGER=1 PHASE6E_FUSED_WRITER=1 "${FLAG}=1" \
        OUTPUT="$OUT/needle_on.json" \
        "$PYTHON" "$SCRIPTS_DIR/phase6k12_hard_needle.py" --worker --mml "$MML"

# Explicit COLLAPSE=0 assertion on both needle runs.
for tag in off on; do
    j="$OUT/needle_${tag}.json"
    if [[ -f "$j" ]]; then
        c="$($PYTHON -c "import json,sys; d=json.load(open('$j')); print(d.get('totals',{}).get('COLLAPSE',0))" 2>/dev/null || echo "?")"
        if [[ "$c" == "0" ]]; then
            echo ">>> COLLAPSE check ($tag): 0  PASS"
            PASS=$((PASS+1)); RESULTS+=("PASS  COLLAPSE=0 ($tag)")
        else
            echo "!!! COLLAPSE check ($tag): $c  FAIL (must be 0)"
            FAIL=$((FAIL+1)); RESULTS+=("FAIL  COLLAPSE=$c ($tag)")
        fi
    fi
done

# --- 3. token-agreement (flag OFF, then ON) -------------------------------
# bench_phase6j drives the bf16/naive/protected A/B; it honors the env flags.
# Smoke mode keeps it to ~5 min/leg.
run_gate "token-agreement flag=off" \
    env PHASE6E_FUSED_WRITER=1 "${FLAG}=0" "$PYTHON" \
        "$SCRIPTS_DIR/bench_phase6j_quality_gpu.py" --smoke
run_gate "token-agreement flag=on" \
    env PHASE6E_FUSED_WRITER=1 "${FLAG}=1" "$PYTHON" \
        "$SCRIPTS_DIR/bench_phase6j_quality_gpu.py" --smoke

echo
echo "=================================================================="
echo "CORRECTNESS ORACLE SUMMARY  (PASS=$PASS  FAIL=$FAIL)"
echo "=================================================================="
for r in "${RESULTS[@]}"; do echo "  $r"; done
echo
if [[ $FAIL -eq 0 ]]; then
    echo ">>> ALL CORRECTNESS GATES GREEN. (flag-on == flag-off semantics.)"
    echo ">>> Safe to evaluate performance: phase6f_acceptance_ab.sh"
    exit 0
else
    echo "!!! CORRECTNESS REGRESSION with the fused read path. DO NOT SHIP."
    echo "!!! Rollback: revert the kernel commit (the change is isolated behind"
    echo "!!! ${FLAG}); the flag-off path is the known-good reference."
    exit 1
fi
