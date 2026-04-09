#!/bin/bash
# =============================================================================
# CRS Phase 3: A vs B Real-Data Comparison
# =============================================================================
#
# Run this on RunPod or any GPU machine with HuggingFace access.
#
# USAGE:
#   # Full A vs B comparison (recommended: ~2 hours on A100/H100)
#   ./scripts/run_crs_ab_comparison.sh
#
#   # Quick mode (300 steps, ~30 min)
#   ./scripts/run_crs_ab_comparison.sh --quick
#
#   # Resume from specific checkpoint
#   ./scripts/run_crs_ab_comparison.sh --resume checkpoints/latest.pt
#
# REQUIREMENTS:
#   pip install torch transformers datasets bitsandbytes accelerate
#
# =============================================================================

set -e

# Ensure repo root is on PYTHONPATH so symbolu_training is importable
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
cd "$REPO_ROOT"

# =============================================================================
# DEFAULTS — tuned for meaningful comparison on limited budget
# =============================================================================

MISTRAL_MODEL="mistralai/Mistral-7B-v0.3"
QUANTIZE="4bit"
DATASET="wikitext2"
MAX_STEPS=500
BATCH_SIZE=4
GRADIENT_ACCUMULATION=4
LEARNING_RATE="3e-4"
WARMUP_STEPS=50
EVAL_EVERY=100
LOG_EVERY=10
SAVE_EVERY=500
MIXED_PRECISION="bf16"
SEED=42
RESUME_PATH=""
QUICK_MODE=0

# CG Lambda weights (same for both modes — must be identical)
LAMBDA_ONT=0.01
LAMBDA_KOSHA=0.01
LAMBDA_BLISS=0.01
LAMBDA_PLAUSIBILITY=0.005
LAMBDA_CSR=0.005
LAMBDA_VRITTI=0.005
LAMBDA_GUNA=0.005

# =============================================================================
# PARSE ARGUMENTS
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=1
            MAX_STEPS=300
            EVAL_EVERY=100
            LOG_EVERY=10
            shift
            ;;
        --steps)
            MAX_STEPS="$2"
            shift 2
            ;;
        --resume)
            RESUME_PATH="$2"
            shift 2
            ;;
        --model)
            MISTRAL_MODEL="$2"
            shift 2
            ;;
        --dataset)
            DATASET="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

CKPT_DIR_A="checkpoints_crs_validation_A"
CKPT_DIR_B="checkpoints_crs_validation_B"
LOG_DIR="logs_crs_validation"

mkdir -p "$LOG_DIR"

echo "============================================================"
echo "CRS Phase 3: A vs B Comparison"
echo "============================================================"
echo "  Model:      $MISTRAL_MODEL"
echo "  Dataset:    $DATASET"
echo "  Steps:      $MAX_STEPS"
echo "  Batch:      ${BATCH_SIZE}×${GRADIENT_ACCUMULATION}"
echo "  Seed:       $SEED"
echo "  Quick mode: $QUICK_MODE"
echo "============================================================"

# Common training args (identical between A and B)
COMMON_ARGS=(
    --model_type mistral_cg
    --model_name "$MISTRAL_MODEL"
    --quantize "$QUANTIZE"
    --dataset "$DATASET"
    --max_steps "$MAX_STEPS"
    --batch_size "$BATCH_SIZE"
    --gradient_accumulation_steps "$GRADIENT_ACCUMULATION"
    --learning_rate "$LEARNING_RATE"
    --warmup_steps "$WARMUP_STEPS"
    --eval_every "$EVAL_EVERY"
    --log_every "$LOG_EVERY"
    --save_every "$SAVE_EVERY"
    --mixed_precision "$MIXED_PRECISION"
    --seed "$SEED"
    --enable_conscious_generation
    --lambda_ont "$LAMBDA_ONT"
    --lambda_kosha_routing "$LAMBDA_KOSHA"
    --lambda_bliss_token "$LAMBDA_BLISS"
    --lambda_plausibility_token "$LAMBDA_PLAUSIBILITY"
    --lambda_csr_token "$LAMBDA_CSR"
    --lambda_vritti_token "$LAMBDA_VRITTI"
    --lambda_guna_token "$LAMBDA_GUNA"
    --enable_cg_diagnostics
)

# Add resume if specified
if [[ -n "$RESUME_PATH" ]]; then
    COMMON_ARGS+=(--resume "$RESUME_PATH")
fi

# =============================================================================
# MODE A: Legacy CSR (baseline)
# =============================================================================

echo ""
echo "============================================================"
echo "MODE A: Legacy CSR (use_crs_combined_scorer=False)"
echo "============================================================"

python symbolu_training/training/unified/train.py \
    "${COMMON_ARGS[@]}" \
    --checkpoint_dir "$CKPT_DIR_A" \
    2>&1 | tee "${LOG_DIR}/mode_A.log"

echo "Mode A complete."

# =============================================================================
# MODE B: Full CRS
# =============================================================================

echo ""
echo "============================================================"
echo "MODE B: Full CRS (use_crs_combined_scorer=True)"
echo "============================================================"

python symbolu_training/training/unified/train.py \
    "${COMMON_ARGS[@]}" \
    --use_crs_combined_scorer \
    --semantic_dim 16 \
    --crs_semantic_threshold 0.45 \
    --crs_gate_sharpness 10.0 \
    --crs_weight_c 0.2 \
    --crs_weight_r 0.2 \
    --crs_weight_s 0.6 \
    --crs_alpha_base 0.5 \
    --checkpoint_dir "$CKPT_DIR_B" \
    2>&1 | tee "${LOG_DIR}/mode_B.log"

echo "Mode B complete."

# =============================================================================
# EXTRACT AND COMPARE KEY METRICS
# =============================================================================

echo ""
echo "============================================================"
echo "EXTRACTING COMPARISON METRICS"
echo "============================================================"

python << 'PYEOF'
import re, sys

def parse_log(path, mode_name):
    """Extract key metrics from training log."""
    metrics = {
        'mode': mode_name,
        'losses': [],
        'crs_C': [], 'crs_R': [], 'crs_S': [],
        'crs_Sg': [], 'crs_ovr': [],
    }

    with open(path) as f:
        for line in f:
            # Training loss: look for "loss=" pattern
            m = re.search(r'loss[=:]\s*([\d.]+)', line)
            if m and 'aux' not in line.lower():
                metrics['losses'].append(float(m.group(1)))

            # CRS diagnostics: "CRS: C=... R=... S=... Sg=... ovr=..."
            m = re.search(r'CRS:\s*C=([\d.-]+)\s*R=([\d.-]+)\s*S=([\d.-]+)\s*Sg=([\d.-]+)\s*ovr=([\d.-]+)', line)
            if m:
                metrics['crs_C'].append(float(m.group(1)))
                metrics['crs_R'].append(float(m.group(2)))
                metrics['crs_S'].append(float(m.group(3)))
                metrics['crs_Sg'].append(float(m.group(4)))
                metrics['crs_ovr'].append(float(m.group(5)))

    return metrics

def summarize(metrics):
    name = metrics['mode']
    losses = metrics['losses']
    print(f"\n  {name}:")
    if losses:
        print(f"    Loss: {losses[0]:.4f} → {losses[-1]:.4f} (n={len(losses)} logged)")
    else:
        print(f"    Loss: NO DATA")

    if metrics['crs_C']:
        n = len(metrics['crs_C'])
        last = min(n, 5)  # last 5 measurements
        print(f"    C_mean (last {last}):  {sum(metrics['crs_C'][-last:])/last:.4f}")
        print(f"    R_mean (last {last}):  {sum(metrics['crs_R'][-last:])/last:.4f}")
        print(f"    S_mean (last {last}):  {sum(metrics['crs_S'][-last:])/last:.4f}")
        print(f"    S_gate (last {last}): {sum(metrics['crs_Sg'][-last:])/last:.4f}")
        print(f"    Override (last {last}): {sum(metrics['crs_ovr'][-last:])/last:.4f}")
    else:
        print(f"    CRS diagnostics: N/A (legacy mode)")

import os
log_dir = "logs_crs_validation"
for mode, fname in [("Mode A (Legacy CSR)", "mode_A.log"), ("Mode B (Full CRS)", "mode_B.log")]:
    path = os.path.join(log_dir, fname)
    if os.path.exists(path):
        m = parse_log(path, mode)
        summarize(m)
    else:
        print(f"\n  {mode}: LOG NOT FOUND ({path})")

print("\n  Done. Review logs_crs_validation/ for full details.")
PYEOF

echo ""
echo "============================================================"
echo "COMPARISON COMPLETE"
echo "============================================================"
echo "Logs:        ${LOG_DIR}/mode_A.log, ${LOG_DIR}/mode_B.log"
echo "Checkpoints: ${CKPT_DIR_A}/, ${CKPT_DIR_B}/"
echo ""
echo "Next steps:"
echo "  1. Review the metric summary above"
echo "  2. Check logs for CRS: C=... R=... S=... Sg=... ovr=... lines"
echo "  3. Compare loss curves between Mode A and Mode B"
echo "  4. Look for R_mean > 0 (R branch alive with real phoneme data)"
echo "  5. Look for S↔base_logit divergence over time"
echo "  6. Decide: GO / TUNE / FIX / ABORT"
