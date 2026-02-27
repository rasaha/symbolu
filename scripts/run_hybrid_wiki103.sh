#!/bin/bash
# =============================================================================
# HYBRID MODEL TRAINING - WikiText-103
# =============================================================================
#
# Trains a Hybrid model (Phase + Sliding Window attention) on WikiText-103
# with Phase attention, Quad filters, and Sliding Window (local) attention.
#
# ATTENTION ARCHITECTURE:
#   - Phase Attention: O(n) state-delta attention via learned phase angles
#   - Sliding Window (Local): O(n*w) attention within a fixed window
#   - Quad Filters: Interference-aware proposal scoring for compositionality
#   - Protected Phase: Local cross-attends to Phase memory (not parallel blend)
#
# MODEL SIZES:
#   tiny   → 6 layers,  256d, 4 heads  (~10M params)
#   small  → 8 layers,  512d, 8 heads  (~45M params)
#   medium → 12 layers, 768d, 12 heads (~125M params)
#   large  → 16 layers, 1024d, 16 heads (~350M params)
#
# USAGE:
#   ./scripts/run_hybrid_wiki103.sh                      # Default: small
#   ./scripts/run_hybrid_wiki103.sh --size tiny           # Quick test
#   ./scripts/run_hybrid_wiki103.sh --size medium         # Production
#   ./scripts/run_hybrid_wiki103.sh --resume CHECKPOINT   # Resume
#   ./scripts/run_hybrid_wiki103.sh --quick               # 1000-step test
#
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION DEFAULTS
# =============================================================================

MODEL_SIZE="small"
MAX_STEPS=50000
BATCH_SIZE=8
LEARNING_RATE="3e-4"
MAX_SEQ_LEN=1024
WINDOW_SIZE=256
CHECKPOINT_DIR="checkpoints_hybrid_wiki103"
LOG_DIR="logs_hybrid_wiki103"
RESUME_PATH=""
QUICK_MODE=false

# =============================================================================
# PARSE COMMAND LINE ARGUMENTS
# =============================================================================

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Train a Hybrid (Phase + Sliding Window) model on WikiText-103"
    echo ""
    echo "Options:"
    echo "  --size SIZE        Model size: tiny, small, medium, large (default: small)"
    echo "  --steps N          Maximum training steps (default: 50000)"
    echo "  --batch N          Batch size per GPU (default: 8)"
    echo "  --lr RATE          Base learning rate (default: 3e-4)"
    echo "  --seq-len N        Max sequence length (default: 1024)"
    echo "  --window N         Sliding window size (default: 256)"
    echo "  --checkpoint DIR   Checkpoint directory"
    echo "  --resume PATH      Resume from checkpoint"
    echo "  --quick            Quick mode: 1000 steps, tiny model"
    echo "  --help             Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 --size medium --steps 100000"
    echo "  $0 --quick"
    echo "  $0 --size small --window 512 --seq-len 2048"
}

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
        --seq-len)
            MAX_SEQ_LEN="$2"
            shift 2
            ;;
        --window)
            WINDOW_SIZE="$2"
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
        --quick)
            QUICK_MODE=true
            MODEL_SIZE="tiny"
            MAX_STEPS=1000
            MAX_SEQ_LEN=512
            shift
            ;;
        --help)
            show_help
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
LOG_FILE="${LOG_DIR}/hybrid_${MODEL_SIZE}_${TIMESTAMP}.log"

echo "============================================================"
echo "   SymbolU Hybrid Model Training"
echo "   Dataset: WikiText-103"
echo "   Attention: Phase + Sliding Window + Quad"
echo "============================================================"
echo ""
echo "Configuration:"
echo "  Model Type:    hybrid"
echo "  Model Size:    $MODEL_SIZE"
echo "  Max Steps:     $MAX_STEPS"
echo "  Batch Size:    $BATCH_SIZE"
echo "  Learning Rate: $LEARNING_RATE"
echo "  Seq Length:    $MAX_SEQ_LEN"
echo "  Window Size:   $WINDOW_SIZE"
echo "  Checkpoint:    $CHECKPOINT_DIR"
echo "  Log File:      $LOG_FILE"
if [ -n "$RESUME_PATH" ]; then
    echo "  Resume:        $RESUME_PATH"
fi
if [ "$QUICK_MODE" = true ]; then
    echo "  Mode:          QUICK TEST (1000 steps)"
fi
echo ""

# Build resume argument
RESUME_ARG=$([ -n "$RESUME_PATH" ] && echo "--resume $RESUME_PATH" || echo "")

# =============================================================================
# TRAINING COMMAND
# =============================================================================

python train_unified_llm_clean.py \
    \
    `# ── Core Model ──` \
    --model_type hybrid \
    --model_size "$MODEL_SIZE" \
    --dataset wikitext103 \
    --max_seq_len "$MAX_SEQ_LEN" \
    \
    `# ── Phase Attention ──` \
    --alpha_phase 0.5 \
    --alpha_phase_start 0.6 \
    --alpha_phase_end 0.4 \
    --alpha_decay_steps 10000 \
    --bounded_phase \
    --cosine_mode shifted \
    --phase_ramp_steps 7000 \
    --protected_phase \
    \
    `# ── Sliding Window (Local) Attention ──` \
    --window_size "$WINDOW_SIZE" \
    --local_layers 4 \
    --alpha_local 0.8 \
    \
    `# ── Quad Filters ──` \
    --enable_quad_utilization_checks \
    --quad_utilization_warn_threshold 0.01 \
    --quad_utilization_check_interval 100 \
    --enable_quad_interference \
    --interference_lambda_text 0.02 \
    --interference_min_step 8 \
    --interference_entropy_gate 1.2 \
    --interference_auto_classify \
    \
    `# ── Phase Diversity (anti-collapse) ──` \
    --enable_adaptive_phase_diversity \
    --phase_diversity_target_R 0.25 \
    --phase_diversity_lambda_init 0.0001 \
    --phase_diversity_lambda_max 0.1 \
    --phase_diversity_eta 0.1 \
    \
    `# ── Training Hyperparameters ──` \
    --batch_size "$BATCH_SIZE" \
    --learning_rate "$LEARNING_RATE" \
    --max_steps "$MAX_STEPS" \
    --warmup_steps 500 \
    --weight_decay 0.1 \
    --max_grad_norm 1.0 \
    --gradient_accumulation 4 \
    \
    `# ── Memory Optimization ──` \
    --gradient_checkpointing \
    --mixed_precision bf16 \
    --use_8bit_optimizer \
    \
    `# ── Entropy Floor (anti-repetition) ──` \
    --enable_entropy_floor \
    --entropy_floor 0.48 \
    --entropy_floor_weight 0.1 \
    \
    `# ── Logging & Checkpointing ──` \
    --log_every 50 \
    --eval_every 500 \
    --save_every 2500 \
    --checkpoint_dir "$CHECKPOINT_DIR" \
    --tensorboard \
    --seed 42 \
    \
    $RESUME_ARG \
    2>&1 | tee "$LOG_FILE"

# =============================================================================
# POST-TRAINING
# =============================================================================

TRAIN_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "============================================================"
if [ $TRAIN_EXIT_CODE -eq 0 ]; then
    echo "   HYBRID TRAINING COMPLETED"
    echo "   Checkpoints: $CHECKPOINT_DIR"
    echo "   Log: $LOG_FILE"
else
    echo "   HYBRID TRAINING FAILED (exit code: $TRAIN_EXIT_CODE)"
    echo "   Check log: $LOG_FILE"
fi
echo "============================================================"

exit $TRAIN_EXIT_CODE
