#!/bin/bash
# =============================================================================
# STAGED TRAINING SCRIPT - SymbolU v9.9.0 (POST-DIAGNOSIS FIX)
# =============================================================================
#
# This script implements the CORRECTED staged training approach based on the
# comprehensive training diagnosis that identified:
#   1. Quality metrics were misleading (fixed: added coherence checks)
#   2. Over-regularization (17 controllers fighting each other)
#   3. Backwards PPL thresholds (fixed: inverted all engagement logic)
#   4. Sattvic controller thrashing (fixed: increased variance threshold 10x)
#
# STAGED APPROACH (Option B - Recommended):
# ─────────────────────────────────────────
#   Stage 1 (0-10k):   Pure Language Modeling → Target PPL < 50
#   Stage 2 (10k-20k): Add Ontological Bridge → Target PPL < 30
#   Stage 3 (20k-30k): Add CSR Grounding     → Target coherent phoneme alignment
#   Stage 4 (30k+):    Full System           → Gradually enable remaining controllers
#
# CRITICAL FIXES APPLIED:
#   ✅ Quality metrics now include semantic coherence (not just diversity)
#   ✅ PPL thresholds inverted (engage when READY, not when STRUGGLING)
#   ✅ Sattvic variance threshold: 0.001 → 0.01 (10x, prevents thrashing)
#
# USAGE:
#   ./scripts/train_staged_fixed.sh                # Run full staged training
#   ./scripts/train_staged_fixed.sh --stage 1      # Run specific stage only
#   ./scripts/train_staged_fixed.sh --stage 2 --resume checkpoints_stage1/step_10000.pt
#
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_SIZE="small"
DATASET="fineweb"
CHECKPOINT_BASE="checkpoints_staged_v9.9"
LOG_DIR="logs_staged_v9.9"
STAGE=0  # 0 = run all stages, 1-4 = specific stage
RESUME_PATH=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --stage)
            STAGE="$2"
            shift 2
            ;;
        --size)
            MODEL_SIZE="$2"
            shift 2
            ;;
        --dataset)
            DATASET="$2"
            shift 2
            ;;
        --resume)
            RESUME_PATH="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "  --stage N       Run specific stage (1-4, default: all)"
            echo "  --size SIZE     Model size (tiny/small/medium/large, default: small)"
            echo "  --dataset NAME  Dataset (wikitext103/fineweb, default: fineweb)"
            echo "  --resume PATH   Resume from checkpoint"
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

mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "=============================================="
echo "   SymbolU Staged Training v9.9.0"
echo "   POST-DIAGNOSIS FIX"
echo "=============================================="
echo ""
echo "Configuration:"
echo "  Model Size:  $MODEL_SIZE"
echo "  Dataset:     $DATASET"
echo "  Stage:       $([ $STAGE -eq 0 ] && echo 'All (1→2→3→4)' || echo $STAGE)"
echo "  Checkpoints: $CHECKPOINT_BASE"
echo "  Logs:        $LOG_DIR"
if [ -n "$RESUME_PATH" ]; then
    echo "  Resume:      $RESUME_PATH"
fi
echo ""

# =============================================================================
# STAGE 1: PURE LANGUAGE MODELING (0-10k steps)
# =============================================================================

run_stage_1() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  STAGE 1: PURE LANGUAGE MODELING"
    echo "  Goal: Learn basic tokenization and grammar (Target: PPL < 50)"
    echo "  Duration: 0 → 10,000 steps"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    CHECKPOINT_DIR="${CHECKPOINT_BASE}_stage1"
    LOG_FILE="${LOG_DIR}/stage1_${TIMESTAMP}.log"
    RESUME_ARG=$([ -n "$RESUME_PATH" ] && echo "--resume $RESUME_PATH" || echo "")

    python train_unified_llm.py \
        \
        --model_type ontological_hybrid \
        --model_size "$MODEL_SIZE" \
        --dataset "$DATASET" \
        --max_seq_len 512 \
        --untie_embeddings \
        \
        --batch_size 8 \
        --learning_rate 3e-4 \
        --max_steps 10000 \
        --gradient_accumulation 4 \
        \
        --gradient_checkpointing \
        --mixed_precision bf16 \
        --use_8bit_optimizer \
        \
        --use_9_3_split \
        --alpha_sens_initial 0.05 \
        --alpha_sens_max 0.7 \
        --gradient_warmup_steps 500 \
        \
        --log_every 50 \
        --eval_every 500 \
        --save_every 2500 \
        --checkpoint_dir "$CHECKPOINT_DIR" \
        --tensorboard \
        \
        $RESUME_ARG \
        2>&1 | tee "$LOG_FILE"

    STAGE1_EXIT_CODE=${PIPESTATUS[0]}

    if [ $STAGE1_EXIT_CODE -ne 0 ]; then
        echo "❌ Stage 1 FAILED (exit code: $STAGE1_EXIT_CODE)"
        exit $STAGE1_EXIT_CODE
    fi

    echo ""
    echo "✅ Stage 1 COMPLETED"
    echo "   Checkpoint: $CHECKPOINT_DIR/step_10000.pt"
    echo "   Next: Stage 2 will add Ontological Bridge"
    echo ""
}

# =============================================================================
# STAGE 2: ADD ONTOLOGICAL BRIDGE (10k-20k steps)
# =============================================================================

run_stage_2() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  STAGE 2: ADD ONTOLOGICAL BRIDGE"
    echo "  Goal: Add 12D ontological structure (Target: PPL < 30)"
    echo "  Duration: 10,000 → 20,000 steps"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    CHECKPOINT_DIR="${CHECKPOINT_BASE}_stage2"
    LOG_FILE="${LOG_DIR}/stage2_${TIMESTAMP}.log"

    # Resume from Stage 1 if no specific resume path provided
    if [ -z "$RESUME_PATH" ]; then
        RESUME_ARG="--resume ${CHECKPOINT_BASE}_stage1/step_10000.pt"
    else
        RESUME_ARG="--resume $RESUME_PATH"
    fi

    python train_unified_llm.py \
        \
        --model_type ontological_hybrid \
        --model_size "$MODEL_SIZE" \
        --dataset "$DATASET" \
        --max_seq_len 768 \
        --untie_embeddings \
        \
        --batch_size 8 \
        --learning_rate 2e-4 \
        --max_steps 20000 \
        --gradient_accumulation 4 \
        \
        --gradient_checkpointing \
        --mixed_precision bf16 \
        --use_8bit_optimizer \
        \
        --use_9_3_split \
        --alpha_sens_initial 0.05 \
        --alpha_sens_max 0.7 \
        --gradient_warmup_steps 500 \
        \
        --enable_onto_bridge \
        --onto_bridge_lambda 0.1 \
        --onto_bridge_diversity 0.1 \
        --onto_engage_ppl 50.0 \
        --onto_disengage_ppl 150.0 \
        \
        --enable_sovereign_loss \
        --sovereign_weight_s 2.0 \
        --sovereign_weight_r 5.0 \
        --sovereign_weight_c 0.5 \
        --b1_lambda 0.5 \
        --mu_s3 0.2 \
        \
        --log_every 50 \
        --eval_every 500 \
        --save_every 2500 \
        --checkpoint_dir "$CHECKPOINT_DIR" \
        --tensorboard \
        \
        $RESUME_ARG \
        2>&1 | tee "$LOG_FILE"

    STAGE2_EXIT_CODE=${PIPESTATUS[0]}

    if [ $STAGE2_EXIT_CODE -ne 0 ]; then
        echo "❌ Stage 2 FAILED (exit code: $STAGE2_EXIT_CODE)"
        exit $STAGE2_EXIT_CODE
    fi

    echo ""
    echo "✅ Stage 2 COMPLETED"
    echo "   Checkpoint: $CHECKPOINT_DIR/step_20000.pt"
    echo "   Next: Stage 3 will add CSR phoneme grounding"
    echo ""
}

# =============================================================================
# STAGE 3: ADD CSR GROUNDING (20k-30k steps)
# =============================================================================

run_stage_3() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  STAGE 3: ADD CSR PHONEME GROUNDING"
    echo "  Goal: Align phonemic patterns with semantics"
    echo "  Duration: 20,000 → 30,000 steps"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    CHECKPOINT_DIR="${CHECKPOINT_BASE}_stage3"
    LOG_FILE="${LOG_DIR}/stage3_${TIMESTAMP}.log"

    # Resume from Stage 2 if no specific resume path provided
    if [ -z "$RESUME_PATH" ]; then
        RESUME_ARG="--resume ${CHECKPOINT_BASE}_stage2/step_20000.pt"
    else
        RESUME_ARG="--resume $RESUME_PATH"
    fi

    python train_unified_llm.py \
        \
        --model_type ontological_hybrid \
        --model_size "$MODEL_SIZE" \
        --dataset "$DATASET" \
        --max_seq_len 1024 \
        --untie_embeddings \
        \
        --batch_size 8 \
        --learning_rate 1e-4 \
        --max_steps 30000 \
        --gradient_accumulation 4 \
        \
        --gradient_checkpointing \
        --mixed_precision bf16 \
        --use_8bit_optimizer \
        \
        --use_9_3_split \
        --alpha_sens_initial 0.05 \
        --alpha_sens_max 0.7 \
        --gradient_warmup_steps 500 \
        \
        --enable_onto_bridge \
        --onto_bridge_lambda 0.1 \
        --onto_bridge_diversity 0.1 \
        --onto_engage_ppl 50.0 \
        --onto_disengage_ppl 150.0 \
        \
        --enable_csr \
        --csr_lambda 0.1 \
        --csr_tau 0.07 \
        --csr_alignment_layer 7 \
        --csr_projector_lr_scale 0.1 \
        --csr_sparse_supervision \
        --csr_engage_ppl 40.0 \
        --csr_disengage_ppl 120.0 \
        \
        --enable_sgp \
        --sgp_base_rate 200 \
        --sgp_stagnation_rate 100 \
        --sgp_gamma 0.5 \
        \
        --enable_sovereign_loss \
        --sovereign_weight_s 2.0 \
        --sovereign_weight_r 5.0 \
        --sovereign_weight_c 0.5 \
        --b1_lambda 0.5 \
        --mu_s3 0.2 \
        \
        --log_every 50 \
        --eval_every 500 \
        --save_every 2500 \
        --checkpoint_dir "$CHECKPOINT_DIR" \
        --tensorboard \
        \
        $RESUME_ARG \
        2>&1 | tee "$LOG_FILE"

    STAGE3_EXIT_CODE=${PIPESTATUS[0]}

    if [ $STAGE3_EXIT_CODE -ne 0 ]; then
        echo "❌ Stage 3 FAILED (exit code: $STAGE3_EXIT_CODE)"
        exit $STAGE3_EXIT_CODE
    fi

    echo ""
    echo "✅ Stage 3 COMPLETED"
    echo "   Checkpoint: $CHECKPOINT_DIR/step_30000.pt"
    echo "   Next: Stage 4 will gradually enable full system"
    echo ""
}

# =============================================================================
# STAGE 4: FULL SYSTEM (30k+ steps)
# =============================================================================

run_stage_4() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  STAGE 4: FULL SYSTEM"
    echo "  Goal: Fine-tune with carefully selected controllers"
    echo "  Duration: 30,000 → 50,000 steps"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    CHECKPOINT_DIR="${CHECKPOINT_BASE}_stage4"
    LOG_FILE="${LOG_DIR}/stage4_${TIMESTAMP}.log"

    # Resume from Stage 3 if no specific resume path provided
    if [ -z "$RESUME_PATH" ]; then
        RESUME_ARG="--resume ${CHECKPOINT_BASE}_stage3/step_30000.pt"
    else
        RESUME_ARG="--resume $RESUME_PATH"
    fi

    python train_unified_llm.py \
        \
        --model_type ontological_hybrid \
        --model_size "$MODEL_SIZE" \
        --dataset "$DATASET" \
        --max_seq_len 1024 \
        --untie_embeddings \
        \
        --batch_size 8 \
        --learning_rate 5e-5 \
        --max_steps 50000 \
        --gradient_accumulation 4 \
        \
        --gradient_checkpointing \
        --mixed_precision bf16 \
        --use_8bit_optimizer \
        \
        --use_9_3_split \
        --alpha_sens_initial 0.05 \
        --alpha_sens_max 0.7 \
        --gradient_warmup_steps 500 \
        \
        --controller pidv2 \
        --pidv2_kp_min 0.10 \
        --pidv2_kp_max 0.30 \
        --pidv2_ki 0.02 \
        --pidv2_kd 0.10 \
        --pidv2_a_min 0.40 \
        --pidv2_w_s 0.30 \
        --controller_engage_ppl 30.0 \
        --controller_disengage_ppl 100.0 \
        \
        --enable_onto_bridge \
        --onto_bridge_lambda 0.1 \
        --onto_bridge_diversity 0.1 \
        --onto_engage_ppl 50.0 \
        --onto_disengage_ppl 150.0 \
        \
        --enable_csr \
        --csr_lambda 0.1 \
        --csr_tau 0.07 \
        --csr_alignment_layer 7 \
        --csr_projector_lr_scale 0.1 \
        --csr_sparse_supervision \
        --csr_engage_ppl 40.0 \
        --csr_disengage_ppl 120.0 \
        \
        --enable_kosha_gyroscope \
        --gyroscope_base_gain 0.15 \
        --gyroscope_max_gain 3.0 \
        --gyroscope_ppl_ceiling 100.0 \
        --gyroscope_target_ppl 30.0 \
        --kosha_engage_ppl 30.0 \
        --kosha_disengage_ppl 100.0 \
        \
        --enable_entropy_floor \
        --entropy_floor 0.48 \
        --entropy_floor_weight 0.1 \
        \
        --enable_sgp \
        --sgp_base_rate 200 \
        --sgp_stagnation_rate 100 \
        --sgp_gamma 0.5 \
        \
        --enable_sovereign_loss \
        --sovereign_weight_s 2.0 \
        --sovereign_weight_r 5.0 \
        --sovereign_weight_c 0.5 \
        --b1_lambda 0.5 \
        --mu_s3 0.2 \
        \
        --log_every 50 \
        --eval_every 500 \
        --save_every 2500 \
        --checkpoint_dir "$CHECKPOINT_DIR" \
        --tensorboard \
        \
        $RESUME_ARG \
        2>&1 | tee "$LOG_FILE"

    STAGE4_EXIT_CODE=${PIPESTATUS[0]}

    if [ $STAGE4_EXIT_CODE -ne 0 ]; then
        echo "❌ Stage 4 FAILED (exit code: $STAGE4_EXIT_CODE)"
        exit $STAGE4_EXIT_CODE
    fi

    echo ""
    echo "✅ Stage 4 COMPLETED"
    echo "   Final checkpoint: $CHECKPOINT_DIR/step_50000.pt"
    echo ""
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

case $STAGE in
    0)
        # Run all stages sequentially
        run_stage_1
        RESUME_PATH=""  # Clear so stages use their defaults
        run_stage_2
        run_stage_3
        run_stage_4
        ;;
    1)
        run_stage_1
        ;;
    2)
        run_stage_2
        ;;
    3)
        run_stage_3
        ;;
    4)
        run_stage_4
        ;;
    *)
        echo "Invalid stage: $STAGE (must be 0-4)"
        exit 1
        ;;
esac

# =============================================================================
# FINAL SUMMARY
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STAGED TRAINING COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Checkpoints:"
if [ $STAGE -eq 0 ] || [ $STAGE -eq 1 ]; then
    echo "  Stage 1: ${CHECKPOINT_BASE}_stage1/step_10000.pt"
fi
if [ $STAGE -eq 0 ] || [ $STAGE -eq 2 ]; then
    echo "  Stage 2: ${CHECKPOINT_BASE}_stage2/step_20000.pt"
fi
if [ $STAGE -eq 0 ] || [ $STAGE -eq 3 ]; then
    echo "  Stage 3: ${CHECKPOINT_BASE}_stage3/step_30000.pt"
fi
if [ $STAGE -eq 0 ] || [ $STAGE -eq 4 ]; then
    echo "  Stage 4: ${CHECKPOINT_BASE}_stage4/step_50000.pt"
fi
echo ""
echo "Logs: $LOG_DIR/"
echo ""
echo "Next steps:"
echo "  1. Review quality samples in logs (check coherence scores)"
echo "  2. Verify PPL progression: Stage 1→<50, Stage 2→<30, Stage 3→coherent"
echo "  3. If quality is good, continue with Stage 4 full system training"
echo ""
