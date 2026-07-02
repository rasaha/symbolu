#!/usr/bin/env bash
# ============================================================================
# Track D — Stage D0 REAL pilot: RunPod GPU launcher (EXPLORATORY TRIAGE ONLY)
#
# Runs the real D0 LLM-scored pilot with a LOCAL GPU model. HARD-GATED: refuses
# unless the approval checklist is honored (D0_RUN_APPROVED=yes) and a frozen
# config is provided. Emits only LLM_PILOT_* labels; never EXPERIENTIAL_WEATHER_
# SIGNAL / ONTOLOGICAL_SIGNAL / Sanskrit privilege. Does NOT touch frozen/
# manifest.json, the readiness gate, or Stage A. A positive is triage only:
# "D1 human-blind validation may be worth funding" — never validation.
#
# Usage (on an APPROVED RunPod GPU pod):
#   export D0_RUN_APPROVED=yes
#   export D0_CONFIG=/workspace/d0_config.json        # frozen input bundle
#   export D0_GENERATOR_MODEL=<hf-id-A>               # generator
#   export D0_SCORER_MODEL=<hf-id-B>                  # scorer (must differ from A)
#   bash run_d0_pilot_runpod.sh
# ============================================================================
set -euo pipefail
STAGE_A_BASELINE="2d42bf6"
sec(){ echo; echo "================= $* ================="; }

sec "1. MACHINE IDENTITY"
echo "hostname: $(hostname)"; uname -a; python3 --version
if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi -L; else
  echo "STOP: no GPU (nvidia-smi absent). D0 real pilot needs a GPU pod."; exit 3; fi

sec "2. APPROVAL GATE (refuses unless explicitly approved)"
: "${D0_RUN_APPROVED:?REFUSED: set D0_RUN_APPROVED=yes after completing TRACK_D_D0_RUN_APPROVAL_CHECKLIST.md}"
[ "${D0_RUN_APPROVED,,}" = "yes" ] || { echo "REFUSED: D0_RUN_APPROVED != yes"; exit 3; }
: "${D0_CONFIG:?REFUSED: set D0_CONFIG to the frozen input bundle path}"
[ -f "$D0_CONFIG" ] || { echo "REFUSED: D0_CONFIG not found: $D0_CONFIG"; exit 3; }
: "${D0_GENERATOR_MODEL:?REFUSED: set D0_GENERATOR_MODEL}"
: "${D0_SCORER_MODEL:?REFUSED: set D0_SCORER_MODEL}"
if [ "$D0_GENERATOR_MODEL" = "$D0_SCORER_MODEL" ] && [ "${D0_WAIVE_CROSS_MODEL:-no}" != "yes" ]; then
  echo "REFUSED: generator == scorer; use distinct models or set D0_WAIVE_CROSS_MODEL=yes"; exit 3; fi
echo "approved; generator=$D0_GENERATOR_MODEL  scorer=$D0_SCORER_MODEL  config=$D0_CONFIG"

sec "3. REPO + BRANCH"
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
echo "repo: $(pwd)  HEAD: $(git rev-parse --short HEAD)"
P="experiments/primitive_sequence_recovery"

sec "4. DEPS"
python3 -m pip -q install --upgrade pip >/dev/null
python3 -m pip -q install numpy torch transformers accelerate sentencepiece >/dev/null
python3 -c "import torch;print('cuda available:', torch.cuda.is_available())"

sec "5. HARNESS MECHANICS SANITY (synthetic; no real data)"
python3 "$P/test_track_d_d0_harness.py" >/dev/null && echo "harness dry-run tests PASS" \
  || { echo "harness tests FAILED — aborting"; exit 2; }

sec "6. REAL D0 PILOT (local GPU LLM; exploratory triage)"
python3 "$P/d0_pilot_runner.py" --out "${D0_OUT:-/workspace/d0_report.json}"

sec "7. GUARDRAIL CONFIRMATIONS"
python3 - <<'PY'
import sys, pathlib; P=pathlib.Path("experiments/primitive_sequence_recovery"); sys.path.insert(0,str(P))
import manifest as MF, run_primitive_recovery as RUN
print("manifest readiness:", MF.check_readiness(P/"frozen")["status"])   # NOT_READY
print("psr runner        :", RUN.run()["status"])                        # NOT_RUN
PY
grep -q "ONTOLOGICAL_SIGNAL" "${D0_OUT:-/workspace/d0_report.json}" \
  && { echo "GUARD FAIL: ONTOLOGICAL_SIGNAL in report"; exit 5; } || echo "OK: no ONTOLOGICAL_SIGNAL"
if git diff --quiet "$STAGE_A_BASELINE" HEAD -- symbolu_neural/structural_v1; then
  echo "Stage A: UNTOUCHED"; else echo "Stage A: MODIFIED — ABORT"; exit 5; fi
echo "Track B: BLOCKED (D0 is exploratory triage; not Track B)"

sec "DONE — D0 exploratory triage complete (report at ${D0_OUT:-/workspace/d0_report.json})"
echo "D0 real pilot: exploratory triage only. No validation. Track B remains blocked. Structure, not validated meaning."
