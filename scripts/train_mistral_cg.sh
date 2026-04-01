#!/bin/bash
# =============================================================================
# MISTRAL CG TRAINING — Full Conscious Generation Pipeline (Stages 0-8)
# =============================================================================
#
# Trains a frozen Mistral-7B backbone with trainable Conscious Generation
# modules, including the Stage 8 Perspective Synthesizer (representation
# conditioning before lm_head).
#
# Architecture:
#   Mistral-7B (frozen, 4-bit quantized) → hidden_states [B, T, 4096]
#       ↓
#   State Projector → 32D Sovereign State (trainable)
#       ↓
#   Phase Adapter + CG Modules (trainable, ~5M params)
#       ↓
#   Stage 8: PerspectiveSynthesizer — conditions hidden via interpretive
#     signals (CSR, Vritti, Kosha, Bhava) before lm_head
#       ↓
#   LM Head (Mistral's, frozen)
#
# REQUIREMENTS:
#   - GPU with ≥24GB VRAM (A100/4090/3090 recommended)
#     For 4-bit: ~14GB VRAM. For 8-bit: ~18GB. For fp16: ~28GB.
#   - pip install transformers bitsandbytes accelerate
#   - pip install datasets (for WikiText/C4)
#   - pip install tensorboard (optional, for monitoring)
#
# USAGE:
#   # Quick smoke test (10 steps, synthetic data, no GPU needed)
#   ./scripts/train_mistral_cg.sh --smoke-test
#
#   # Small run (WikiText-2, 1000 steps, 4-bit quantization)
#   ./scripts/train_mistral_cg.sh --dataset wikitext2 --max-steps 1000
#
#   # Full training (WikiText-103, 50K steps)
#   ./scripts/train_mistral_cg.sh --dataset wikitext103 --max-steps 50000
#
#   # Full training with C4 dataset
#   ./scripts/train_mistral_cg.sh --dataset c4 --max-steps 100000
#
#   # Resume from checkpoint
#   ./scripts/train_mistral_cg.sh --resume checkpoints_mistral_cg/latest.pt
#
# =============================================================================

set -e

# =============================================================================
# DEFAULTS
# =============================================================================

MISTRAL_MODEL="mistralai/Mistral-7B-v0.3"
QUANTIZE="4bit"
DATASET="wikitext2"
MAX_STEPS=50000
BATCH_SIZE=4
GRADIENT_ACCUMULATION=8
LEARNING_RATE="3e-4"
WARMUP_STEPS=500
EVAL_EVERY=500
LOG_EVERY=50
SAVE_EVERY=5000
CHECKPOINT_DIR="checkpoints_mistral_cg"
LOG_DIR="logs_mistral_cg"
MIXED_PRECISION="bf16"
RESUME_PATH=""
SMOKE_TEST=0

# CG Lambda weights (default: conservative start)
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
        --smoke-test)
            SMOKE_TEST=1
            shift
            ;;
        --model)
            MISTRAL_MODEL="$2"
            shift 2
            ;;
        --quantize)
            QUANTIZE="$2"
            shift 2
            ;;
        --dataset)
            DATASET="$2"
            shift 2
            ;;
        --max-steps)
            MAX_STEPS="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --lr)
            LEARNING_RATE="$2"
            shift 2
            ;;
        --resume)
            RESUME_PATH="$2"
            shift 2
            ;;
        --checkpoint-dir)
            CHECKPOINT_DIR="$2"
            shift 2
            ;;
        --no-stage8)
            NO_STAGE8=1
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# SMOKE TEST OVERRIDE
# =============================================================================

if [ "$SMOKE_TEST" -eq 1 ]; then
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  SMOKE TEST MODE — 10 steps, synthetic data, no save   ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    # Check if transformers is installed; fall back to ontological model
    if python -c "import transformers" 2>/dev/null; then
        echo "  Using: mistral_cg (transformers available)"
    else
        echo "  Using: ontological (transformers not installed)"
        echo "  Install transformers + bitsandbytes for Mistral training."
        MODEL_TYPE_OVERRIDE="ontological"
    fi
    DATASET="synthetic"
    MAX_STEPS=10
    BATCH_SIZE=2
    GRADIENT_ACCUMULATION=1
    EVAL_EVERY=999999
    SAVE_EVERY=999999
    WARMUP_STEPS=2
    LOG_EVERY=5
    MIXED_PRECISION="none"
    CHECKPOINT_DIR=""
    EXTRA_ARGS="--no_save --quiet"
    if [ -n "${MODEL_TYPE_OVERRIDE:-}" ]; then
        EXTRA_ARGS="$EXTRA_ARGS --model_size tiny"
    fi
else
    EXTRA_ARGS=""
fi

# =============================================================================
# STAGE 8 FLAGS
# =============================================================================

STAGE8_FLAGS=""
if [ -z "${NO_STAGE8+x}" ]; then
    STAGE8_FLAGS="--enable_perspective_synthesizer"
    STAGE8_FLAGS="$STAGE8_FLAGS --perspective_d_synthesis 64"
    STAGE8_FLAGS="$STAGE8_FLAGS --perspective_gate_init 0.0"
    STAGE8_FLAGS="$STAGE8_FLAGS --perspective_log_interpretive"
fi

# =============================================================================
# RESUME FLAG
# =============================================================================

RESUME_FLAG=""
if [ -n "$RESUME_PATH" ]; then
    RESUME_FLAG="--resume $RESUME_PATH"
fi

# =============================================================================
# LAUNCH TRAINING
# =============================================================================

echo "======================================================================"
echo "  SymbolU — Mistral CG Training (Stages 0-8)"
echo "======================================================================"
echo "  Model:        $MISTRAL_MODEL"
echo "  Quantization: $QUANTIZE"
echo "  Dataset:      $DATASET"
echo "  Max steps:    $MAX_STEPS"
echo "  Batch:        ${BATCH_SIZE} × ${GRADIENT_ACCUMULATION} grad accum"
echo "  LR:           $LEARNING_RATE"
echo "  Stage 8:      $([ -z "${NO_STAGE8+x}" ] && echo 'ENABLED' || echo 'DISABLED')"
echo "  Checkpoints:  $CHECKPOINT_DIR"
echo "======================================================================"

MODEL_TYPE="${MODEL_TYPE_OVERRIDE:-mistral_cg}"

MISTRAL_ARGS=""
if [ "$MODEL_TYPE" = "mistral_cg" ]; then
    MISTRAL_ARGS="--mistral_model_name $MISTRAL_MODEL --mistral_quantize $QUANTIZE"
fi

python train_unified_llm.py \
    --model_type "$MODEL_TYPE" \
    $MISTRAL_ARGS \
    --dataset "$DATASET" \
    --max_steps "$MAX_STEPS" \
    --batch_size "$BATCH_SIZE" \
    --gradient_accumulation "$GRADIENT_ACCUMULATION" \
    --learning_rate "$LEARNING_RATE" \
    --warmup_steps "$WARMUP_STEPS" \
    --eval_every "$EVAL_EVERY" \
    --log_every "$LOG_EVERY" \
    --save_every "$SAVE_EVERY" \
    --mixed_precision "$MIXED_PRECISION" \
    --enable_conscious_generation \
    --lambda_ont "$LAMBDA_ONT" \
    --lambda_kosha_routing "$LAMBDA_KOSHA" \
    --lambda_bliss_token "$LAMBDA_BLISS" \
    --lambda_plausibility_token "$LAMBDA_PLAUSIBILITY" \
    --lambda_csr_token "$LAMBDA_CSR" \
    --lambda_vritti_token "$LAMBDA_VRITTI" \
    --lambda_guna_token "$LAMBDA_GUNA" \
    --enable_embedding_diagnostics \
    --embedding_diag_interval 200 \
    --embedding_diag_no_samples \
    $STAGE8_FLAGS \
    $RESUME_FLAG \
    $EXTRA_ARGS \
    ${CHECKPOINT_DIR:+--checkpoint_dir "$CHECKPOINT_DIR"}
