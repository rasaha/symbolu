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
#   3. Run a fast single-τ sanity check on Mistral (15 minutes) to catch
#      wiring bugs before the full sweep.
#   4. Run the full τ sweep (several hours depending on eval sample count).
#   5. Summarize results and point the operator at the results JSON.
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
#   ./scripts/run_fscs_rstar_measurement.sh                 # full run
#   ./scripts/run_fscs_rstar_measurement.sh --smoke          # smoke only
#   ./scripts/run_fscs_rstar_measurement.sh --sanity         # sanity only
#   ./scripts/run_fscs_rstar_measurement.sh --skip-smoke     # skip CPU tests
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
OUTPUT_DIR="${OUTPUT_DIR:-results/fscs_rstar}"
OUTPUT_JSON="${OUTPUT_DIR}/results.json"

SMOKE_ONLY=0
SANITY_ONLY=0
SKIP_SMOKE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --smoke) SMOKE_ONLY=1; shift ;;
        --sanity) SANITY_ONLY=1; shift ;;
        --skip-smoke) SKIP_SMOKE=1; shift ;;
        *) echo "Unknown argument: $1"; exit 2 ;;
    esac
done

echo "================================================================"
echo "  Text-FSCS r* measurement"
echo "================================================================"
echo "  Model:           ${MODEL}"
echo "  Quantization:    ${QUANTIZE}"
echo "  Eval dataset:    ${EVAL_DATASET}"
echo "  Sequence len:    ${SEQ_LEN}"
echo "  Eval samples:    ${MAX_EVAL_SAMPLES}"
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

# ----- 3. Sanity pass (single τ, small sample) --------------------------
echo
echo "[3/4] Sanity pass — single τ=0.5, 16 samples, should complete in ~15 min…"
python scripts/r_star_sweep.py \
    --model "${MODEL}" \
    --quantize "${QUANTIZE}" \
    --eval-dataset "${EVAL_DATASET}" \
    --seq-len "${SEQ_LEN}" \
    --max-eval-samples 16 \
    --coarse-window "${COARSE_WINDOW}" \
    --single-tau 0.5 \
    --output "${OUTPUT_DIR}/sanity.json"

if [[ "${SANITY_ONLY}" -eq 1 ]]; then
    echo
    echo "Sanity-only mode complete. Check ${OUTPUT_DIR}/sanity.json"
    exit 0
fi

# ----- 4. Full τ sweep --------------------------------------------------
echo
echo "[4/4] Full τ sweep — ~several hours at ${MAX_EVAL_SAMPLES} samples × 8 τ × 2 modes…"
python scripts/r_star_sweep.py \
    --model "${MODEL}" \
    --quantize "${QUANTIZE}" \
    --eval-dataset "${EVAL_DATASET}" \
    --seq-len "${SEQ_LEN}" \
    --max-eval-samples "${MAX_EVAL_SAMPLES}" \
    --coarse-window "${COARSE_WINDOW}" \
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
