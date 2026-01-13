#!/bin/bash
# =============================================================================
# MINIMAL TRAINING SCRIPT - SymbolU v9.9.0 (Option A: Quick Fix)
# =============================================================================
#
# This is the minimal intervention approach - disable most regularizers
# and let the model learn basic language modeling first.
#
# Use this for:
#   - Quick testing of the core fixes
#   - Establishing a baseline (target: PPL < 30)
#   - Debugging if staged approach has issues
#
# CRITICAL FIXES APPLIED:
#   ✅ Quality metrics now include semantic coherence
#   ✅ No over-regularization (only essential components)
#   ✅ Sattvic variance threshold: 0.001 → 0.01 (if CSR enabled)
#
# USAGE:
#   ./scripts/train_minimal_fixed.sh
#   ./scripts/train_minimal_fixed.sh --steps 20000
#   ./scripts/train_minimal_fixed.sh --resume checkpoints_minimal/step_10000.pt
#
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_SIZE="small"
MAX_STEPS=50000
BATCH_SIZE=8
LEARNING_RATE="3e-4"
DATASET="fineweb"
CHECKPOINT_DIR="checkpoints_minimal_v9.9"
LOG_DIR="logs_minimal_v9.9"
RESUME_PATH=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --size)
            MODEL_SIZE="$2"
            shift 2
            ;;
        --steps)
            MAX_STEPS="$2"
            shift 2
            ;;
        --batch)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --lr)
            LEARNING_RATE="$2"
            shift 2
            ;;
        --dataset)
            DATASET="$2"
            shift 2
            ;;
        --checkpoint)
            CHECKPOINT_DIR="$2"
            shift 2
            ;;
        --resume)
            RESUME_PATH="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "  --size SIZE       Model size (tiny/small/medium/large, default: small)"
            echo "  --steps N         Max training steps (default: 50000)"
            echo "  --batch N         Batch size (default: 8)"
            echo "  --lr RATE         Learning rate (default: 3e-4)"
            echo "  --dataset NAME    Dataset (wikitext103/fineweb, default: fineweb)"
            echo "  --checkpoint DIR  Checkpoint directory (default: checkpoints_minimal_v9.9)"
            echo "  --resume PATH     Resume from checkpoint"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# SETUP
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

mkdir -p "$CHECKPOINT_DIR"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/minimal_${TIMESTAMP}.log"

echo "=============================================="
echo "   SymbolU Minimal Training v9.9.0"
echo "   Option A: Quick Fix (Baseline)"
echo "=============================================="
echo ""
echo "Configuration:"
echo "  Model Size:  $MODEL_SIZE"
echo "  Max Steps:   $MAX_STEPS"
echo "  Batch Size:  $BATCH_SIZE"
echo "  Learning Rate: $LEARNING_RATE"
echo "  Dataset:     $DATASET"
echo "  Checkpoint:  $CHECKPOINT_DIR"
echo "  Log File:    $LOG_FILE"
if [ -n "$RESUME_PATH" ]; then
    echo "  Resume:      $RESUME_PATH"
fi
echo ""
echo "Philosophy: Learn basic language modeling FIRST,"
echo "            then gradually add controllers in Stage 2+"
echo ""

# Build resume argument
RESUME_ARG=$([ -n "$RESUME_PATH" ] && echo "--resume $RESUME_PATH" || echo "")

# =============================================================================
# MINIMAL TRAINING COMMAND
# =============================================================================

python train_unified_llm.py \
    \
    `# Core model configuration` \
    --model_type ontological_hybrid \
    --model_size "$MODEL_SIZE" \
    --dataset "$DATASET" \
    --max_seq_len 1024 \
    --untie_embeddings \
    \
    `# Training hyperparameters` \
    --batch_size "$BATCH_SIZE" \
    --learning_rate "$LEARNING_RATE" \
    --max_steps "$MAX_STEPS" \
    --gradient_accumulation 4 \
    \
    `# Memory optimization` \
    --gradient_checkpointing \
    --mixed_precision bf16 \
    --use_8bit_optimizer \
    \
    `# Basic 9:3 architecture (no fancy controllers)` \
    --use_9_3_split \
    --alpha_sens_initial 0.05 \
    --alpha_sens_max 0.7 \
    --gradient_warmup_steps 500 \
    \
    `# Logging & checkpointing` \
    --log_every 50 \
    --eval_every 500 \
    --save_every 2500 \
    --checkpoint_dir "$CHECKPOINT_DIR" \
    --tensorboard \
    --quiet \
    \
    $RESUME_ARG \
    2>&1 | tee "$LOG_FILE"

# =============================================================================
# POST-TRAINING SUMMARY
# =============================================================================

TRAIN_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=============================================="
if [ $TRAIN_EXIT_CODE -eq 0 ]; then
    echo "   MINIMAL TRAINING COMPLETED"
    echo ""
    echo "   ✅ SUCCESS"
    echo ""
    echo "   Next Steps:"
    echo "   1. Check final PPL in log: $LOG_FILE"
    echo "   2. Review quality samples (coherence scores)"
    echo "   3. If PPL < 50: Ready for Stage 2 (add Onto Bridge)"
    echo "   4. If PPL < 30: Ready for Stage 3 (add CSR)"
    echo "   5. If quality good: Use staged script for full system"
    echo ""
    echo "   Run staged training:"
    echo "   ./scripts/train_staged_fixed.sh --resume $CHECKPOINT_DIR/step_${MAX_STEPS}.pt"
else
    echo "   MINIMAL TRAINING FAILED"
    echo ""
    echo "   ❌ Exit code: $TRAIN_EXIT_CODE"
    echo ""
    echo "   Check log for errors: $LOG_FILE"
fi
echo "=============================================="
echo ""
echo "Checkpoints: $CHECKPOINT_DIR"
echo "Log file:    $LOG_FILE"
echo ""

exit $TRAIN_EXIT_CODE
