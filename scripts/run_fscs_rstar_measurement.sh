#!/usr/bin/env bash
# =============================================================================
# scripts/run_fscs_rstar_measurement.sh
#
# Runbook for the Text-FSCS r* measurement on frozen Mistral-7B.
#
# This script is the operator-facing front door to
# scripts/r_star_sweep.py. Its job is to:
#
#   1. Verify the environment has the prerequisites (GPU, dependencies,
#      HuggingFace cache with Mistral-7B weights).
#   2. Run the CPU smoke test on the FSCS core modules first — if those
#      are broken, there is no point firing up an A100.
#   3. A/B wiring check: run the sweep at tau=0.99 (gate effectively off)
#      and verify Delta ppl < 0.1% vs baseline. If the wrapper is not
#      transparent at r=0, the whole sweep is meaningless. Abort on fail.
#   4. Sanity pass: single tau=0.5 on 16 samples (~15 min) to catch
#      wiring bugs before the full sweep.
#   5. Full tau sweep (several hours depending on eval sample count).
#   6. Summarize results and point the operator at the results JSON.
#
# Prerequisites
# -------------
#   - GPU: A100-80GB or equivalent (Mistral-7B in 4-bit fits in ~14GB,
#     but the dual-branch FSCS forward increases peak memory)
#   - CUDA: 12.x with matching PyTorch
#   - Python: 3.10+
#   - Packages: torch, transformers>=4.36, bitsandbytes, accelerate, datasets,
#               pytest (for the smoke test)
#   - HuggingFace cache must contain mistralai/Mistral-7B-v0.3, or the
#     operator must be logged in (`huggingface-cli login`) with access.
#
# Usage
# -----
#   ./scripts/run_fscs_rstar_measurement.sh                          # full run
#   ./scripts/run_fscs_rstar_measurement.sh --smoke                   # smoke only
#   ./scripts/run_fscs_rstar_measurement.sh --sanity                  # sanity only
#   ./scripts/run_fscs_rstar_measurement.sh --skip-smoke              # skip CPU tests
#   ./scripts/run_fscs_rstar_measurement.sh --quantize bf16           # override 4bit
#   ./scripts/run_fscs_rstar_measurement.sh --sanity --quantize bf16  # combined
#
# Quantization options
# --------------------
#   4bit   Default. Requires torch>=2.5 with current transformers versions
#          because of a bitsandbytes integration change (set_submodule).
#          Mistral-7B fits in ~14GB at 4-bit.
#   8bit   Same torch>=2.5 requirement. ~18GB VRAM.
#   bf16   No quantization. ~14GB VRAM. Works with torch 2.4.x. Use this
#          if your environment has torch<2.5 and you cannot upgrade.
#          A100-80GB has ample headroom.
#   none   Alias for bf16.
#
# IMPORTANT: This script has NOT been executed. It is code-complete but
# requires operator execution on appropriate hardware to produce results.
# =============================================================================

set -euo pipefail

MODEL="${MODEL:-mistralai/Mistral-7B-v0.3}"
QUANTIZE="${QUANTIZE:-4bit}"
EVAL_DATASET="${EVAL_DATASET:-wikitext2}"
SEQ_LEN="${SEQ_LEN:-2048}"
MAX_EVAL_SAMPLES="${MAX_EVAL_SAMPLES:-256}"
COARSE_WINDOW="${COARSE_WINDOW:-256}"
# Batched eval: default 8 sequences per forward pass. Safe on A100-80GB
# with Mistral-7B bf16 (peak ~32 GB at seq_len=2048, plenty of headroom).
# Lower to 1 on smaller GPUs or raise toward 16 on larger ones.
EVAL_BATCH_SIZE="${EVAL_BATCH_SIZE:-8}"
OUTPUT_DIR="${OUTPUT_DIR:-results/fscs_rstar}"
OUTPUT_JSON="${OUTPUT_DIR}/results.json"

SMOKE_ONLY=0
SANITY_ONLY=0
SKIP_SMOKE=0
FULL_ONLY=0  # Skip wiring + sanity and go straight to the full sweep.

while [[ $# -gt 0 ]]; do
    case "$1" in
        --smoke) SMOKE_ONLY=1; shift ;;
        --sanity) SANITY_ONLY=1; shift ;;
        --skip-smoke) SKIP_SMOKE=1; shift ;;
        --full-only) FULL_ONLY=1; shift ;;
        --quantize)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --quantize requires an argument (4bit|8bit|bf16|none)" >&2
                exit 2
            fi
            QUANTIZE="$2"; shift 2 ;;
        --quantize=*) QUANTIZE="${1#*=}"; shift ;;
        *) echo "Unknown argument: $1"; exit 2 ;;
    esac
done

# Normalize 'none' -> 'bf16' for display; r_star_sweep.py accepts both.
if [[ "${QUANTIZE}" == "none" ]]; then
    QUANTIZE="bf16"
fi

echo "================================================================"
echo "  Text-FSCS r* measurement"
echo "================================================================"
echo "  Model:           ${MODEL}"
echo "  Quantization:    ${QUANTIZE}"
echo "  Eval dataset:    ${EVAL_DATASET}"
echo "  Sequence len:    ${SEQ_LEN}"
echo "  Eval samples:    ${MAX_EVAL_SAMPLES}"
echo "  Eval batch size: ${EVAL_BATCH_SIZE}"
echo "  Coarse window:   ${COARSE_WINDOW}"
echo "  Output JSON:     ${OUTPUT_JSON}"
echo "================================================================"

# ----- 1. Environment sanity --------------------------------------------
echo
echo "[1/4] Environment check…"

if ! command -v python >/dev/null 2>&1; then
    echo "ERROR: python not found in PATH" >&2
    exit 1
fi

python - <<'PYCHECK'
import sys
missing = []
for pkg in ("torch", "transformers", "datasets", "bitsandbytes", "accelerate"):
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(f"  MISSING dependencies: {', '.join(missing)}", file=sys.stderr)
    print("  Install with: pip install torch transformers datasets bitsandbytes accelerate",
          file=sys.stderr)
    sys.exit(1)

import torch
print(f"  torch:        {torch.__version__}")
print(f"  cuda avail:   {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  device:       {torch.cuda.get_device_name(0)}")
    total_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"  vram:         {total_gb:.1f} GB")
else:
    print("  WARNING: no CUDA available — this will run on CPU and will be slow")
PYCHECK

# ----- 2. CPU smoke test ------------------------------------------------
if [[ "${SKIP_SMOKE}" -eq 0 && "${SANITY_ONLY}" -eq 0 ]]; then
    echo
    echo "[2/4] CPU smoke test on FSCS core modules…"
    python -m pytest tests/test_fscs_core.py -v --tb=short
    if [[ $? -ne 0 ]]; then
        echo "ERROR: smoke test failed. Fix before running the GPU sweep." >&2
        exit 1
    fi
fi

if [[ "${SMOKE_ONLY}" -eq 1 ]]; then
    echo
    echo "Smoke-only mode complete."
    exit 0
fi

# ----- 3. A/B wiring check (tau=0.99, gate effectively off) -------------
# This is the most important validity check: if the FSCS-wrapped Mistral
# does not produce ~baseline ppl when the gate is off, every later number
# is meaningless. Hard-fail the runbook if Delta ppl exceeds 0.1%.
# Skipped if --full-only was passed (wiring has already been validated).
if [[ "${FULL_ONLY}" -eq 0 ]]; then
    echo
    echo "[3/5] A/B wiring check — tau=0.99 should reduce to baseline Mistral…"
    python scripts/r_star_sweep.py \
        --model "${MODEL}" \
        --quantize "${QUANTIZE}" \
        --eval-dataset "${EVAL_DATASET}" \
        --seq-len "${SEQ_LEN}" \
        --max-eval-samples 32 \
        --coarse-window "${COARSE_WINDOW}" \
        --eval-batch-size "${EVAL_BATCH_SIZE}" \
        --single-tau 0.99 \
        --output "${OUTPUT_DIR}/ab_wiring_check.json"

    python - <<PYWIRING
import json, sys
with open("${OUTPUT_DIR}/ab_wiring_check.json") as f:
    r = json.load(f)
delta = r["sweep"][0]["soft"]["delta_pct"]
print(f"  A/B wiring delta: {delta:.4f}%")
if abs(delta) > 0.1:
    print(f"  FAIL: wrapper not transparent at tau=0.99 (delta={delta:.4f}%)",
          file=sys.stderr)
    print(f"  This means the dual-branch FSCS forward is not reducing to",
          file=sys.stderr)
    print(f"  stock Mistral when the gate is off. Fix the wrapper before",
          file=sys.stderr)
    print(f"  trusting any r* number from a real sweep.", file=sys.stderr)
    sys.exit(1)
print(f"  PASS: wrapper is transparent at tau=0.99")
PYWIRING
else
    echo
    echo "[3/5] A/B wiring check — SKIPPED (--full-only)."
fi

# ----- 4. Sanity pass (single tau, small sample) -----------------------
if [[ "${FULL_ONLY}" -eq 0 ]]; then
    echo
    echo "[4/5] Sanity pass — single tau=0.5, 16 samples, should complete in ~15 min…"
    python scripts/r_star_sweep.py \
        --model "${MODEL}" \
        --quantize "${QUANTIZE}" \
        --eval-dataset "${EVAL_DATASET}" \
        --seq-len "${SEQ_LEN}" \
        --max-eval-samples 16 \
        --coarse-window "${COARSE_WINDOW}" \
        --eval-batch-size "${EVAL_BATCH_SIZE}" \
        --single-tau 0.5 \
        --output "${OUTPUT_DIR}/sanity.json"

    if [[ "${SANITY_ONLY}" -eq 1 ]]; then
        echo
        echo "Sanity-only mode complete. Check ${OUTPUT_DIR}/sanity.json"
        exit 0
    fi
else
    echo
    echo "[4/5] Sanity pass — SKIPPED (--full-only)."
fi

# ----- 5. Full tau sweep ------------------------------------------------
echo
echo "[5/5] Full tau sweep — ${MAX_EVAL_SAMPLES} samples × 8 tau × 2 modes at batch=${EVAL_BATCH_SIZE}…"
python scripts/r_star_sweep.py \
    --model "${MODEL}" \
    --quantize "${QUANTIZE}" \
    --eval-dataset "${EVAL_DATASET}" \
    --seq-len "${SEQ_LEN}" \
    --max-eval-samples "${MAX_EVAL_SAMPLES}" \
    --coarse-window "${COARSE_WINDOW}" \
    --eval-batch-size "${EVAL_BATCH_SIZE}" \
    --tau-sweep 0.90 0.80 0.70 0.60 0.50 0.40 0.30 0.20 \
    --output "${OUTPUT_JSON}"

echo
echo "================================================================"
echo "  Full sweep complete."
echo "  Results: ${OUTPUT_JSON}"
echo "================================================================"
python - <<PYSUMMARY
import json
with open("${OUTPUT_JSON}") as f:
    r = json.load(f)
print(f"Baseline PPL:       {r['baseline']['ppl']:.4f}")
print(f"r*:                 {r['r_star']}")
print(f"Verdict:            {r['verdict']['label']}")
print(f"Best wall speedup:  {r['verdict']['best_wall_speedup_pct']:.1f}%")
print(f"Worst Δppl in sweep:{r['verdict']['worst_delta_pct']:.2f}%")
print()
print("Note: wall-clock numbers from this harness do NOT reflect")
print("production savings — see docs/FSCS_IMPLEMENTATION_STATUS.md")
PYSUMMARY
