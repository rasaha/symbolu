#!/bin/bash
# =============================================================================
# GCT (GATED COHERENCE TRANSFORMER) TRAINING
# =============================================================================
#
# Trains a Gated Coherence Transformer on WikiText-103 or FineWeb.
#
# GCT augments standard O(n²) softmax attention with pre-softmax coherence
# gating and lambda_ladder band insulation. Routes each head at each position
# between full attention (O(n²)) and local-window attention (O(n*w)) based on
# temporal stability signals (output + residual deltas).
#
# ATTENTION ARCHITECTURE:
#   - Full Path:  Standard O(n²) softmax (SDPA/FlashAttention compatible)
#   - Local Path: Sliding-window softmax O(n*w) — same primitive, fewer keys
#   - Routing:    Pre-softmax coherence gate (no QK^T needed to decide)
#   - Insulation: Lambda_ladder prevents band collapse
#
# TRAINING PHASES:
#   Phase 1 (warmup):  Full attention only, coherence predictors observe
#   Phase 2 (anneal):  Soft blend gradually enabled (0 → 1)
#   Phase 3 (full):    Full gated operation, both paths active
#
# MODEL SIZES:
#   tiny   → 6 layers,  256d, 4 heads   (~10M params)
#   small  → 8 layers,  512d, 8 heads   (~45M params)
#   medium → 12 layers, 768d, 12 heads  (~125M params)
#   large  → 16 layers, 1024d, 16 heads (~350M params)
#
# USAGE:
#   ./scripts/run_gct_training.sh                            # Default: small
#   ./scripts/run_gct_training.sh --size tiny                # Quick test
#   ./scripts/run_gct_training.sh --size medium              # Production
#   ./scripts/run_gct_training.sh --quick                    # 1000-step test
#   ./scripts/run_gct_training.sh --window 256               # Larger window (prose)
#   ./scripts/run_gct_training.sh --dataset fineweb          # FineWeb streaming
#   ./scripts/run_gct_training.sh --resume CHECKPOINT        # Resume training
#   ./scripts/run_gct_training.sh --compare                  # Also train baseline
#   ./scripts/run_gct_training.sh --help                     # Show this help
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
DATASET="wikitext103"
CHECKPOINT_DIR="checkpoints_gct"
LOG_DIR="logs_gct"
RESUME_PATH=""
QUICK_MODE=false
COMPARE_MODE=false

# GCT-specific defaults
GCT_WINDOW_SIZE=128
GCT_NUM_BANDS=3
GCT_KAPPA=3.0
GCT_TAU_LADDER=0.15
GCT_WARMUP_STEPS=500
GCT_ANNEAL_STEPS=2000
GCT_GAMMA=5.0
GCT_DELTA=3.0

# =============================================================================
# PARSE COMMAND LINE ARGUMENTS
# =============================================================================

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Train a Gated Coherence Transformer (GCT) model."
    echo "Routes heads between full O(n²) and local-window O(n*w) attention"
    echo "based on pre-softmax coherence gating with band insulation."
    echo ""
    echo "General Options:"
    echo "  --size SIZE        Model size: tiny, small, medium, large (default: small)"
    echo "  --steps N          Maximum training steps (default: 50000)"
    echo "  --batch N          Batch size per GPU (default: 8)"
    echo "  --lr RATE          Base learning rate (default: 3e-4)"
    echo "  --seq-len N        Max sequence length (default: 1024)"
    echo "  --dataset NAME     Dataset: wikitext103, wikitext2, fineweb (default: wikitext103)"
    echo "  --checkpoint DIR   Checkpoint directory (default: checkpoints_gct)"
    echo "  --resume PATH      Resume from checkpoint"
    echo "  --quick            Quick mode: 1000 steps, tiny model"
    echo "  --compare          Also train a standard baseline for comparison"
    echo "  --help             Show this help"
    echo ""
    echo "GCT-Specific Options:"
    echo "  --window N         Local window size for coarse path (default: 128)"
    echo "  --bands N          Number of frequency bands (default: 3)"
    echo "  --kappa N          Lambda_ladder suppression strength (default: 3.0)"
    echo "  --tau-ladder N     Collapse detection threshold (default: 0.15)"
    echo "  --gct-warmup N     Phase 1 warmup steps (default: 500)"
    echo "  --gct-anneal N     Phase 2 anneal steps (default: 2000)"
    echo "  --gamma N          Output delta sensitivity (default: 5.0)"
    echo "  --delta N          Residual delta sensitivity (default: 3.0)"
    echo ""
    echo "Examples:"
    echo "  $0 --size medium --steps 100000"
    echo "  $0 --quick"
    echo "  $0 --window 256 --seq-len 2048     # Larger window for long prose"
    echo "  $0 --compare --size small           # GCT vs Standard comparison"
    echo "  $0 --dataset fineweb --size medium  # Production on FineWeb"
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
        --window)
            GCT_WINDOW_SIZE="$2"
            shift 2
            ;;
        --bands)
            GCT_NUM_BANDS="$2"
            shift 2
            ;;
        --kappa)
            GCT_KAPPA="$2"
            shift 2
            ;;
        --tau-ladder)
            GCT_TAU_LADDER="$2"
            shift 2
            ;;
        --gct-warmup)
            GCT_WARMUP_STEPS="$2"
            shift 2
            ;;
        --gct-anneal)
            GCT_ANNEAL_STEPS="$2"
            shift 2
            ;;
        --gamma)
            GCT_GAMMA="$2"
            shift 2
            ;;
        --delta)
            GCT_DELTA="$2"
            shift 2
            ;;
        --quick)
            QUICK_MODE=true
            MODEL_SIZE="tiny"
            MAX_STEPS=1000
            MAX_SEQ_LEN=512
            GCT_WARMUP_STEPS=100
            GCT_ANNEAL_STEPS=300
            shift
            ;;
        --compare)
            COMPARE_MODE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
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
LOG_FILE="${LOG_DIR}/gct_${MODEL_SIZE}_${TIMESTAMP}.log"

# Build resume argument
RESUME_ARG=""
if [ -n "$RESUME_PATH" ]; then
    RESUME_ARG="--resume $RESUME_PATH"
fi

# =============================================================================
# DISPLAY CONFIGURATION
# =============================================================================

echo "============================================================"
echo "   GCT: Gated Coherence Transformer Training"
echo "   Pre-softmax coherence routing + band insulation"
echo "============================================================"
echo ""
echo "Model Configuration:"
echo "  Model Type:    gct"
echo "  Model Size:    $MODEL_SIZE"
echo "  Dataset:       $DATASET"
echo "  Seq Length:    $MAX_SEQ_LEN"
echo ""
echo "GCT Configuration:"
echo "  Window Size:   $GCT_WINDOW_SIZE (local attention path)"
echo "  Bands:         $GCT_NUM_BANDS (head frequency partition)"
echo "  Coherence:     gamma=$GCT_GAMMA (output), delta=$GCT_DELTA (residual)"
echo "  Lambda_ladder: kappa=$GCT_KAPPA, tau=$GCT_TAU_LADDER"
echo "  Schedule:      warmup=${GCT_WARMUP_STEPS}s, anneal=${GCT_ANNEAL_STEPS}s"
echo ""
echo "Training Configuration:"
echo "  Max Steps:     $MAX_STEPS"
echo "  Batch Size:    $BATCH_SIZE"
echo "  Learning Rate: $LEARNING_RATE"
echo "  Checkpoint:    $CHECKPOINT_DIR"
echo "  Log File:      $LOG_FILE"
if [ -n "$RESUME_PATH" ]; then
    echo "  Resume:        $RESUME_PATH"
fi
if [ "$QUICK_MODE" = true ]; then
    echo "  Mode:          QUICK TEST (1000 steps)"
fi
if [ "$COMPARE_MODE" = true ]; then
    echo "  Comparison:    Will also train standard baseline"
fi
echo ""

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "  (GPU query failed)"
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -n "$GPU_MEM" ]; then
        if [ "$GPU_MEM" -lt 20000 ]; then
            echo "  Low GPU memory detected. Reducing batch size to 2."
            BATCH_SIZE=2
        elif [ "$GPU_MEM" -lt 45000 ] && [ "$BATCH_SIZE" -gt 4 ]; then
            echo "  40GB GPU detected. Adjusting batch size to 4."
            BATCH_SIZE=4
        fi
    fi
else
    echo "GPU: Not detected (running on CPU)"
fi
echo ""

# =============================================================================
# GCT TRAINING
# =============================================================================

echo "Starting GCT training..."
echo ""

python train_unified_llm_clean.py \
    \
    `# ── Core Model ──` \
    --model_type gct \
    --model_size "$MODEL_SIZE" \
    --dataset "$DATASET" \
    --max_seq_len "$MAX_SEQ_LEN" \
    \
    `# ── GCT: Coherence Gating ──` \
    --gct_window_size "$GCT_WINDOW_SIZE" \
    --gct_num_bands "$GCT_NUM_BANDS" \
    --gct_coherence_gamma "$GCT_GAMMA" \
    --gct_coherence_delta "$GCT_DELTA" \
    --gct_ema_decay 0.9 \
    --gct_alpha_sharpness 10.0 \
    --gct_hard_route_threshold 0.5 \
    \
    `# ── GCT: Lambda_Ladder Band Insulation ──` \
    --gct_kappa "$GCT_KAPPA" \
    --gct_tau_ladder "$GCT_TAU_LADDER" \
    \
    `# ── GCT: Training Schedule ──` \
    --gct_warmup_steps "$GCT_WARMUP_STEPS" \
    --gct_anneal_steps "$GCT_ANNEAL_STEPS" \
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

GCT_EXIT_CODE=${PIPESTATUS[0]}

# =============================================================================
# OPTIONAL: STANDARD BASELINE COMPARISON
# =============================================================================

if [ "$COMPARE_MODE" = true ] && [ $GCT_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "   Standard Baseline Training (for comparison)"
    echo "============================================================"
    echo ""

    BASELINE_CHECKPOINT_DIR="${CHECKPOINT_DIR}_baseline"
    BASELINE_LOG_FILE="${LOG_DIR}/standard_${MODEL_SIZE}_${TIMESTAMP}.log"
    mkdir -p "$BASELINE_CHECKPOINT_DIR"

    python train_unified_llm_clean.py \
        \
        `# ── Standard Baseline ──` \
        --model_type standard \
        --model_size "$MODEL_SIZE" \
        --dataset "$DATASET" \
        --max_seq_len "$MAX_SEQ_LEN" \
        \
        `# ── Same Training Hyperparameters ──` \
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
        \
        `# ── Logging & Checkpointing ──` \
        --log_every 50 \
        --eval_every 500 \
        --save_every 2500 \
        --checkpoint_dir "$BASELINE_CHECKPOINT_DIR" \
        --tensorboard \
        --seed 42 \
        \
        2>&1 | tee "$BASELINE_LOG_FILE"

    BASELINE_EXIT_CODE=${PIPESTATUS[0]}

    echo ""
    echo "============================================================"
    echo "   COMPARISON RESULTS"
    echo "============================================================"
    echo "  GCT Log:      $LOG_FILE"
    echo "  Baseline Log:  $BASELINE_LOG_FILE"
    echo "  GCT Ckpt:      $CHECKPOINT_DIR"
    echo "  Baseline Ckpt: $BASELINE_CHECKPOINT_DIR"
    echo ""
    echo "  Compare with TensorBoard:"
    echo "    tensorboard --logdir_spec gct:$CHECKPOINT_DIR,baseline:$BASELINE_CHECKPOINT_DIR"
    echo "============================================================"
fi

# =============================================================================
# POST-TRAINING SUMMARY
# =============================================================================

echo ""
echo "============================================================"
if [ $GCT_EXIT_CODE -eq 0 ]; then
    echo "   GCT TRAINING COMPLETED"
    echo "   Checkpoints: $CHECKPOINT_DIR"
    echo "   Log: $LOG_FILE"
else
    echo "   GCT TRAINING FAILED (exit code: $GCT_EXIT_CODE)"
    echo "   Check log: $LOG_FILE"
fi
echo "============================================================"

exit $GCT_EXIT_CODE
