#!/bin/bash
# =============================================================================
# MASTER TRAINING SCRIPT - SymbolU Sovereign-1 v9.8.0
# =============================================================================
#
# This script integrates ALL training features correctly:
#   - Adaptive Learning Rate with proper bounds and safety
#   - All auxiliary losses with PPL-gated phased introduction
#   - Curriculum learning (PPL-gated + sequence length ramping)
#   - SRK (Sovereign Reasoning Kernel) with layer hooks
#   - Phase-JEPA perceptual learning
#   - Kosha Gyroscope homeostatic regulation
#   - 9:3 hierarchical gradient scaling with PIDv2
#   - CSR phoneme-ontological grounding with SGP cement
#
# HARDWARE REQUIREMENTS:
#   Minimum: 1x A100 40GB (tiny/small models)
#   Recommended: 1x A100 80GB or H100 80GB (medium+ models)
#
# USAGE:
#   ./scripts/run_master_training.sh                    # Default: small model
#   ./scripts/run_master_training.sh --size tiny        # Quick test (~10M params)
#   ./scripts/run_master_training.sh --size medium      # Production (~350M params)
#   ./scripts/run_master_training.sh --size large       # Full scale (~1.3B params)
#   ./scripts/run_master_training.sh --resume PATH      # Resume from checkpoint
#   ./scripts/run_master_training.sh --quick            # Quick 1000-step test
#   ./scripts/run_master_training.sh --help             # Show this help
#
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION DEFAULTS
# =============================================================================

MODEL_SIZE="small"                    # tiny, small, medium, large
MAX_STEPS=50000                       # Total training steps
BATCH_SIZE=8                          # Batch size (will auto-adjust based on VRAM)
LEARNING_RATE="3e-4"                  # Base learning rate
CHECKPOINT_DIR="checkpoints_unified"  # Checkpoint directory
LOG_DIR="logs"                        # Log directory
RESUME_PATH=""                        # Resume from checkpoint
DATASET="fineweb"                     # wikitext103, wikitext2, fineweb
QUICK_MODE=false                      # Quick test mode

# =============================================================================
# PARSE COMMAND LINE ARGUMENTS
# =============================================================================

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --size SIZE        Model size: tiny, small, medium, large (default: small)"
    echo "  --steps N          Maximum training steps (default: 50000)"
    echo "  --batch N          Batch size (default: 8, auto-adjusted)"
    echo "  --lr RATE          Base learning rate (default: 3e-4)"
    echo "  --checkpoint DIR   Checkpoint directory (default: checkpoints_unified)"
    echo "  --resume PATH      Resume from checkpoint"
    echo "  --dataset NAME     Dataset: wikitext103, wikitext2, fineweb (default: fineweb)"
    echo "  --quick            Quick mode: 1000 steps with tiny model"
    echo "  --help             Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 --size medium --steps 100000"
    echo "  $0 --quick  # Fast test run"
    echo "  $0 --resume checkpoints_unified/step_25000.pt"
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
        --checkpoint)
            CHECKPOINT_DIR="$2"
            shift 2
            ;;
        --resume)
            RESUME_PATH="$2"
            shift 2
            ;;
        --dataset)
            DATASET="$2"
            shift 2
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Quick mode overrides
if [ "$QUICK_MODE" = true ]; then
    MODEL_SIZE="tiny"
    MAX_STEPS=1000
    BATCH_SIZE=16
    echo "[QUICK MODE] Running 1000-step test with tiny model"
fi

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Create directories
mkdir -p "$CHECKPOINT_DIR"
mkdir -p "$LOG_DIR"

# Timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/master_training_${MODEL_SIZE}_${TIMESTAMP}.log"

echo "=============================================="
echo "   SymbolU Sovereign-1 Master Training"
echo "   Version 9.8.0"
echo "=============================================="
echo ""
echo "Configuration:"
echo "  Model Size:    $MODEL_SIZE"
echo "  Max Steps:     $MAX_STEPS"
echo "  Batch Size:    $BATCH_SIZE"
echo "  Learning Rate: $LEARNING_RATE"
echo "  Dataset:       $DATASET"
echo "  Checkpoint:    $CHECKPOINT_DIR"
echo "  Log File:      $LOG_FILE"
if [ -n "$RESUME_PATH" ]; then
    echo "  Resume From:   $RESUME_PATH"
fi
echo ""

# Check GPU
echo "Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
    echo "GPU Memory: ${GPU_MEM} MB"

    # Auto-adjust batch size based on GPU memory
    if [ "$GPU_MEM" -lt 20000 ]; then
        echo "WARNING: Low GPU memory. Reducing batch size to 2."
        BATCH_SIZE=2
    elif [ "$GPU_MEM" -lt 45000 ]; then
        if [ "$BATCH_SIZE" -gt 4 ]; then
            echo "Note: Adjusting batch size to 4 for 40GB GPU."
            BATCH_SIZE=4
        fi
    fi
else
    echo "WARNING: nvidia-smi not found. Running on CPU (will be slow)."
fi
echo ""

# =============================================================================
# BUILD TRAINING COMMAND
# =============================================================================

# Build resume argument if specified
RESUME_ARG=""
if [ -n "$RESUME_PATH" ]; then
    RESUME_ARG="--resume $RESUME_PATH"
fi

# ==============================
# TRAINING COMMAND WITH ALL FEATURES
# ==============================

python train_unified_llm.py \
    \
    `# ============================================================` \
    `# CORE MODEL CONFIGURATION` \
    `# ============================================================` \
    --model_type ontological_hybrid \
    --model_size "$MODEL_SIZE" \
    --dataset "$DATASET" \
    --max_seq_len 1024 \
    --untie_embeddings \
    \
    `# ============================================================` \
    `# TRAINING HYPERPARAMETERS` \
    `# ============================================================` \
    --batch_size "$BATCH_SIZE" \
    --learning_rate "$LEARNING_RATE" \
    --max_steps "$MAX_STEPS" \
    --gradient_accumulation 4 \
    \
    `# ============================================================` \
    `# MEMORY OPTIMIZATION` \
    `# ============================================================` \
    --gradient_checkpointing \
    --mixed_precision bf16 \
    --use_8bit_optimizer \
    \
    `# ============================================================` \
    `# ADAPTIVE LEARNING RATE (v9.8.2)` \
    `# - Monitors PPL velocity, plateau, and loss spikes` \
    `# - Automatically adjusts LR within safe bounds` \
    `# - Emergency decay on gradient explosions` \
    `# ============================================================` \
    --enable_adaptive_training \
    --adaptive_lr_min 1e-5 \
    --adaptive_lr_max 1e-3 \
    --adaptive_max_lr_relative 10.0 \
    --adaptive_lr_boost 1.5 \
    --adaptive_lr_decay 0.7 \
    --adaptive_velocity_slow -2.0 \
    --adaptive_velocity_spike 10.0 \
    --adaptive_plateau_window 5 \
    --adaptive_plateau_threshold 1.0 \
    --adaptive_min_interval 200 \
    --adaptive_loss_spike_threshold 5.0 \
    --adaptive_grad_norm_spike 100.0 \
    --adaptive_emergency_decay 0.5 \
    --adaptive_consecutive_spike_limit 3 \
    \
    `# ============================================================` \
    `# PPL-GATED CURRICULUM LEARNING` \
    `# - FOUNDATION (PPL>30): Pure LM loss, no aux losses` \
    `# - REGULARIZATION (30>PPL>15): Light ontological` \
    `# - GROUNDING (15>PPL>10): CSR + Bridge + JEPA` \
    `# - SOVEREIGN (PPL<10): Full auxiliary stack` \
    `# ============================================================` \
    --enable_curriculum \
    --curriculum_ppl_regularization 30.0 \
    --curriculum_ppl_grounding 15.0 \
    --curriculum_ppl_sovereign 10.0 \
    --curriculum_stability_window 5 \
    --curriculum_hysteresis 1.5 \
    \
    `# ============================================================` \
    `# SEQUENCE LENGTH CURRICULUM` \
    `# - Starts short (faster iterations, lower VRAM)` \
    `# - Ramps to full length as training progresses` \
    `# - PPL-gated to ensure mastery before extending` \
    `# ============================================================` \
    --enable_seq_curriculum \
    --seq_len_start 256 \
    --seq_len_end 1024 \
    --seq_len_ramp_steps 10000 \
    --seq_len_ramp_mode linear \
    \
    `# ============================================================` \
    `# HIERARCHICAL 9:3 GRADIENT SCALING` \
    `# - 9 Authority layers (strong gradients)` \
    `# - 3 Sensory layers (scaled gradients)` \
    `# - Prevents sensory-authority imbalance` \
    `# ============================================================` \
    --use_9_3_split \
    --alpha_sens_initial 0.05 \
    --alpha_sens_max 0.7 \
    --gradient_warmup_steps 500 \
    \
    `# ============================================================` \
    `# PIDv2 CONTROLLER` \
    `# - Dynamically balances sensory/authority ratio` \
    `# - Target S/A ratio: 0.6-0.8 for healthy training` \
    `# - Prevents runaway in either direction` \
    `# ============================================================` \
    --controller pidv2 \
    --pidv2_kp_min 0.10 \
    --pidv2_kp_max 0.30 \
    --pidv2_ki 0.02 \
    --pidv2_kd 0.10 \
    --pidv2_a_min 0.40 \
    --pidv2_w_s 0.30 \
    \
    `# ============================================================` \
    `# SOVEREIGN-LAGRANGIAN LOSS` \
    `# - B1: Forward/backward consistency` \
    `# - S3: Global phase coherence` \
    `# - S8: Entropy-based stability anchoring` \
    `# - R-Signal weighted heavily (ontology critical)` \
    `# ============================================================` \
    --enable_sovereign_loss \
    --sovereign_weight_s 2.0 \
    --sovereign_weight_r 5.0 \
    --sovereign_weight_c 0.5 \
    --b1_lambda 0.5 \
    --mu_s3 0.2 \
    --enable_stability_constraint \
    --gc_floor 0.65 \
    \
    `# ============================================================` \
    `# ONTOLOGICAL LOSSES` \
    `# - Bhava: Emotional state consistency` \
    `# - Coherence: State transition smoothness` \
    `# ============================================================` \
    --bhava_lambda 0.1 \
    --coherence_lambda 0.05 \
    \
    `# ============================================================` \
    `# KOSHA GYROSCOPE (v2.2.5)` \
    `# - Homeostatic self-regulation` \
    `# - Prevents looping, fixation, collapse` \
    `# - Golden ratio thresholds (phi=0.618)` \
    `# - VICReg variance regularization` \
    `# ============================================================` \
    --enable_kosha_gyroscope \
    --gyroscope_base_gain 0.15 \
    --gyroscope_max_gain 3.0 \
    --gyroscope_ppl_ceiling 100.0 \
    --gyroscope_target_ppl 30.0 \
    --gyroscope_floor_mental 0.236 \
    --gyroscope_ceiling_mental 0.382 \
    --gyroscope_floor_physical 0.382 \
    --gyroscope_ceiling_physical 0.618 \
    --gyroscope_floor_intellect 0.382 \
    --gyroscope_ceiling_intellect 0.618 \
    --gyroscope_graduation_ppl 30.0 \
    --gyroscope_graduation_variance 1.5 \
    --gyroscope_graduation_window 10 \
    \
    `# ============================================================` \
    `# ENTROPY FLOOR (v9.5.1 - Anti-Repetition)` \
    `# - Breaks "repetition curse"` \
    `# - Penalizes low-entropy outputs` \
    `# ============================================================` \
    --enable_entropy_floor \
    --entropy_floor 0.48 \
    --entropy_floor_weight 0.1 \
    \
    `# ============================================================` \
    `# CSR PHONEME-ONTOLOGICAL GROUNDING` \
    `# - Aligns phonemic patterns with meaning` \
    `# - Layer 7 = concept consolidation layer` \
    `# - Sparse supervision at word boundaries` \
    `# ============================================================` \
    --enable_csr \
    --csr_lambda 0.1 \
    --csr_tau 0.07 \
    --csr_alignment_layer 7 \
    --csr_projector_lr_scale 0.1 \
    --csr_sparse_supervision \
    \
    `# ============================================================` \
    `# SGP (Stochastic Gradient Persistence) - "Cement"` \
    `# - Stabilizes learned ontological structure` \
    `# - Prevents catastrophic forgetting` \
    `# ============================================================` \
    --enable_sgp \
    --sgp_base_rate 200 \
    --sgp_stagnation_rate 100 \
    --sgp_gamma 0.5 \
    \
    `# ============================================================` \
    `# SOVEREIGN REASONING KERNEL (SRK v9.8.0)` \
    `# - Centralized ontological intervention` \
    `# - Layer 4: DNA Bridge (foundational ontology)` \
    `# - Layer 7: CSR Hook (concept consolidation)` \
    `# - Layer 9: Witness (consciousness alignment)` \
    `# - Layer 11: Synthesis (output integration)` \
    `# ============================================================` \
    --enable_srk \
    --srk_hidden_dim 768 \
    --srk_dna_bridge_layer 4 \
    --srk_csr_alignment_layer 7 \
    --srk_witness_layer 9 \
    --srk_synthesis_layer 11 \
    \
    `# ============================================================` \
    `# PHASE-JEPA (Perceptual Learning)` \
    `# - k-step predictive learning` \
    `# - VICReg collapse prevention` \
    `# - Alignment + prediction consistency` \
    `# ============================================================` \
    --enable_jepa \
    --jepa_hidden_dim 256 \
    --jepa_prediction_steps 4 \
    --jepa_vicreg_weight 1.0 \
    --jepa_alignment_weight 1.0 \
    --jepa_prediction_weight 0.5 \
    --jepa_training_phase body \
    --jepa_auto_phase_transition \
    \
    `# ============================================================` \
    `# ONTOLOGICAL BRIDGE (Layer 4)` \
    `# - Projects to 12D ontology at foundational layer` \
    `# - Diversity penalty prevents collapse` \
    `# ============================================================` \
    --enable_onto_bridge \
    --onto_bridge_lambda 0.1 \
    --onto_bridge_diversity 0.1 \
    \
    `# ============================================================` \
    `# EVOLUTIONARY FLOW` \
    `# - Coherence across layer transitions` \
    `# - Metacognitive LR modulation` \
    `# ============================================================` \
    --enable_evolutionary_flow \
    --evo_lambda 0.1 \
    --evo_lr_modulation \
    \
    `# ============================================================` \
    `# DYNAMIC RELAXATION (9:3 -> 6:6)` \
    `# - Automatic architectural transition` \
    `# - Triggered by S/A ratio stability` \
    `# - Careful weight transfer` \
    `# ============================================================` \
    --enable_dynamic_relaxation \
    --relaxation_mode sa_ratio \
    --relaxation_stability_threshold 0.50 \
    --relaxation_stability_window 500 \
    --relaxation_target_authority 6 \
    --relaxation_target_sensory 6 \
    \
    `# ============================================================` \
    `# SATURATION GATE (Auto-Thaw)` \
    `# - Detects when sensory layers saturate` \
    `# - Automatically "thaws" frozen layers` \
    `# - Prevents training collapse` \
    `# ============================================================` \
    --enable_saturation_gate \
    --saturation_coherence_threshold 0.74 \
    --saturation_patience 50 \
    --saturation_thaw_start 0.3 \
    --saturation_thaw_end 0.7 \
    --saturation_thaw_steps 100 \
    \
    `# ============================================================` \
    `# STRESS PROBE (Emergency Recovery)` \
    `# - Detects pathological states` \
    `# - Entropy-based trigger` \
    `# - Rep3 repetition detection` \
    `# ============================================================` \
    --enable_stress_probe \
    --stress_probe_entropy_trigger 0.42 \
    --stress_probe_rep3_trigger 0.18 \
    \
    `# ============================================================` \
    `# LOGGING & CHECKPOINTING` \
    `# ============================================================` \
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
    echo "   TRAINING COMPLETED SUCCESSFULLY"
else
    echo "   TRAINING FAILED (exit code: $TRAIN_EXIT_CODE)"
fi
echo "=============================================="
echo ""
echo "Log file:    $LOG_FILE"
echo "Checkpoints: $CHECKPOINT_DIR"
echo ""

exit $TRAIN_EXIT_CODE
