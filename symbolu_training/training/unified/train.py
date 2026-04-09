#!/usr/bin/env python3
"""
symbolu.training.unified.train — Main training orchestration module.

Contains:
  - train(config): The main training loop (~5,300 lines)
  - evaluate(model, ...): Validation/evaluation loop
  - main(): CLI argument parser → config → train()

This module was extracted from the root train_unified_llm.py to complete
the modular training package. The root script is now a thin wrapper
that imports and calls main() from here.

Usage (via root wrapper):
    python train_unified_llm.py --model_type ontological_hybrid --model_size small \
        --enable_srk --dataset wikitext103 --max_steps 50000

Usage (direct):
    python -m symbolu.training.unified.train --model_type ontological_hybrid ...
"""

import argparse
import collections
import json
import logging
import math
import os
import pickle
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, IterableDataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR

# Hugging Face imports
try:
    from transformers import AutoTokenizer
    from datasets import load_dataset
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False


# _SimpleByteTokenizer → symbolu.training.unified.utilities

# TensorBoard
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False

# Entropy-based logit scale control
from symbolu_training.training.entropy_control import (
    EntropyControlConfig,
    LogitScaleModule,
    AdaptiveEntropyController,
    topk_entropy,
    attach_logit_scale,
    log_entropy_metrics,
)

# BCVF Contrastive Structural Pressure on Representations
try:
    from symbolu_core.ontological.bcvf_contrastive import (
        BCVFContrastiveConfig,
        BCVFContrastiveHead,
        BCVFNegativeSampler,
        HiddenStateCaptureHook,
        compute_bcvf_contrastive_loss,
        log_bcvf_contrastive_diagnostics,
        get_token_embedding_weight,
    )
    BCVF_CONTRASTIVE_AVAILABLE = True
except ImportError:
    BCVF_CONTRASTIVE_AVAILABLE = False

# BCVF Logit-Margin + Entropy Band (perplexity-aligned)
try:
    from symbolu_core.ontological.bcvf_logit_margin import (
        LogitMarginConfig,
        compute_logit_margin_loss,
        log_logit_margin_diagnostics,
    )
    BCVF_LOGIT_MARGIN_AVAILABLE = True
except ImportError:
    BCVF_LOGIT_MARGIN_AVAILABLE = False

# Kosha-Vritti Structured Supervision (Static Compatibility Version)
try:
    from symbolu_training.training.kosha_vritti_supervision import (
        KoshaVrittiSupervisionConfig,
        KoshaVrittiSupervisor,
        log_kv_metrics,
    )
    KV_SUPERVISION_AVAILABLE = True
except ImportError as e:
    KV_SUPERVISION_AVAILABLE = False
    print(f"Warning: Kosha-Vritti Supervision not available: {e}")

# State-Conditional Logit Scale ("Confidence Knob") + Entropy Band Control
try:
    from symbolu_training.training.confidence_scaler import (
        ConfidenceScalerConfig,
        ConfidenceScaler,
        EntropyBandLoss,
        VrittiRiskHead,
        CalibrationDiagnostics,
        ConfidenceInferenceHook,
        log_confidence_metrics,
        fit_constant_temperature,
    )
    CONFIDENCE_SCALER_AVAILABLE = True
except ImportError as e:
    CONFIDENCE_SCALER_AVAILABLE = False
    print(f"Warning: Confidence Scaler not available: {e}")

# Local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from symbolu_core.phase_transformer import (
    PhaseTransformer,
    HybridPhaseTransformer,
    StandardTransformer,  # V9.6.9: O(n²) baseline for comparison
    OntologicalHybridTransformer,  # V9.6.14: Two-Tier AGI Architecture
    BindingCacheTransformer,  # V10.0: Protected Phase + Top-K Query (validated by probes)
    OntologicalBindingCacheTransformer,  # V10.0: AGI Architecture (Binding Cache + 32D Sovereign State)
    # V9.8.0: 32D Sovereign State (replaces 124D CognitiveState)
    SOVEREIGN_STATE_DIM,
    # V11.0.0: Separated state planes
    PHASE_STATE_DIM,       # 12D Bhava-only (phase rotation input)
    CONTROL_STATE_DIM,     # 16D Koshas+Vrittis+Gunas (control plane)
    LEARNING_STATE_DIM,    # 4D Reserved/JEPA (learning plane)
    BHAVA_NAMES,
    KOSHA_NAMES,
    VRITTI_NAMES,
    GUNA_NAMES,
    BHAVA_SLICE,
    KOSHA_SLICE,
    VRITTI_SLICE,
    GUNA_SLICE,
    get_sovereign_state_summary,
    # V9.9.5: Parameter orthogonalization for hybrid attention
    compute_weight_orthogonalization_loss,
    # V9.9.10: Phase diversity loss (combat phase collapse)
    enable_phase_diversity_capture,
    compute_model_phase_diversity_loss,
    # V9.9.12: Adaptive phase diversity controller
    AdaptivePhaseDiversityController,
    # V9.9.12c: Health dashboard (diagnostic only)
    enable_health_diagnostics_capture,
    compute_phase_health_diagnostics,
    # V10.6.2+ Control-Plane Items (Hard Probes Integration)
    # D.5: No-Write Contract Enforcement
    ControlShapeViolation,
    assert_control_shape,
    validate_control_signals,
    # V10.6.3: Alignment signal shape contract
    assert_alignment_signal_shape,
    # D.1: OntoControl formalized interface
    OntoControl,
    onto_control_from_salience,
    # V10.7: TBPTT chunked training + inference cache
    PhaseStateCache,
    forward_chunked_tbptt,
)

# Import ontological models
try:
    from symbolu_core.ontological.symbolu12_bhava import (
        SymbolU12LLMWithBhava,
        SymbolU12OptimizedWithBhava,
        SymbolU12BhavaConfig,
    )
    from symbolu_core.ontological.bhava_relationships import (
        BHAVA_SIGNIFICANCES,
        get_relationship_meaning,
    )
    ONTOLOGICAL_AVAILABLE = True
except ImportError as e:
    ONTOLOGICAL_AVAILABLE = False
    print(f"Warning: Ontological models not available: {e}")

# Import Sovereign-1 components
try:
    from agentic.sovereign import SovereignLoss, SovereignObserver
    from agentic.sovereign.loss import LegacyLossAdapter
    SOVEREIGN_AVAILABLE = True
except ImportError as e:
    SOVEREIGN_AVAILABLE = False
    print(f"Warning: Sovereign-1 modules not available: {e}")

# Import GradientNormThrottle for training stability
try:
    from symbolu_training.training import GradientNormThrottle, clean_wikitext_artifacts
    GRADIENT_THROTTLE_AVAILABLE = True
except ImportError as e:
    GRADIENT_THROTTLE_AVAILABLE = False
    print(f"Warning: GradientNormThrottle not available: {e}")

# Import V9.8.0: Sovereign Reasoning Kernel (SRK)
try:
    from agentic.sovereign import (
        SRKConfig,
        SovereignReasoningKernel,
        SovereignEmbedding,
        PhaseExtractionHook,
        SRKLossConfig,
        SRKLoss,
        SovereignAnnealer,
        TeleologicalOptimizer,
    )
    SRK_AVAILABLE = True
except ImportError as e:
    SRK_AVAILABLE = False
    print(f"Warning: SRK modules not available: {e}")

# Phase-JEPA: Joint Embedding Predictive Architecture
try:
    from symbolu_training.jepa import (
        PhaseJEPATransformer,
        PhaseJEPAConfig,
        create_phase_jepa_transformer,
        TrainingCurriculumOrchestrator,
        LossScheduler,
        create_curriculum_from_config,
        VICRegLoss,
        WeightedAlignmentLoss,
        JEPAPhase,
        MacroPhase,
    )
    JEPA_AVAILABLE = True
except ImportError as e:
    JEPA_AVAILABLE = False
    print(f"Warning: Phase-JEPA modules not available: {e}")

# Import Gen 2 models (Hierarchical Complex Bhava)
try:
    from symbolu_core.ontological.symbolu12_gen2 import (
        SymbolU12Gen2,
        SymbolU12Gen2Config,
        create_symbolu12_gen2_small,
        create_symbolu12_gen2_medium,
        create_symbolu12_gen2_large,
    )
    GEN2_AVAILABLE = True
except ImportError as e:
    GEN2_AVAILABLE = False
    print(f"Warning: Gen 2 models not available: {e}")

# Import PIDv2 Governor from train_pid.py
try:
    from train_pid import (
        AuthorityPIDv2,
        AuthorityPIDv2Config,
        EmergencyPD,
        EmergencyPDConfig,
        compute_semantic_ppl,
        measure_friction,  # V9.4.5: Friction Monitor
        FrictionController,  # V9.4.5: Friction Controller with Corrective Actions
        FrictionControllerConfig,
    )
    from train import cleanup_old_checkpoints
    PIDV2_AVAILABLE = True
except ImportError as e:
    PIDV2_AVAILABLE = False
    print(f"Warning: PIDv2 controller not available: {e}")

# Import utilities from hierarchical_gradient_scaler module
# Note: Main classes (HierarchicalGradientScaler, DynamicRelaxationController) are
# defined locally below for direct integration with training loop
try:
    from agentic.sovereign.hierarchical_gradient_scaler import compute_s_drift
    COMPUTE_S_DRIFT_AVAILABLE = True
except ImportError:
    COMPUTE_S_DRIFT_AVAILABLE = False
    compute_s_drift = None

# Import Kosha Gyroscope (v2.2.1) and Vritti Resonance (v2.3.0) - Homeostatic Self-Regulation
try:
    from symbolu_training.losses import (
        KoshaGyroscopicLoss,
        KoshaGyroscopeConfig,
        InvertedCurriculumController,
        VrittiResonanceLoss,
        VrittiResonanceConfig,
        SovereignStateRegularizer,
        SovereignStateRegularizerConfig,
    )
    from symbolu_training.monitors import (
        GraduationMonitor,
        GraduationConfig,
    )
    from symbolu_training.diagnostics import (
        SovereignDiagnosticLogger,
        RipEvent,
    )
    KOSHA_GYROSCOPE_AVAILABLE = True
except ImportError as e:
    KOSHA_GYROSCOPE_AVAILABLE = False
    print(f"Warning: Kosha Gyroscope modules not available: {e}")

# SGP (Stochastic Gradient Persistence) and Sattvic Controller
try:
    from symbolu_core.resonance.sgp import SGPController, SGPConfig
    from symbolu_core.resonance.controller import SattvicConfig, SattvicController
    SGP_AVAILABLE = True
except ImportError as e:
    SGP_AVAILABLE = False
    print(f"Warning: SGP/Sattvic modules not available: {e}")

# Import CSR Phoneme Provider for phoneme-ontological grounding
try:
    from csr_phoneme_provider import (
        CSREmbeddingProvider,
        CSRConfig,
        EntropySink,
        SynthesisGate,
        create_csr_for_training,
        integrate_csr_into_forward,
        start_background_preload as csr_start_preload,  # V9.5.2 background loading
        wait_for_preload as csr_wait_preload,
    )
    CSR_AVAILABLE = True
    # V9.5.2 Optimization: Start G2P loading in background immediately
    # This loads CMUdict and g2p_en in parallel while other imports happen
    csr_start_preload()
except ImportError as e:
    CSR_AVAILABLE = False
    csr_start_preload = None
    csr_wait_preload = None
    print(f"Warning: CSR Phoneme Provider not available: {e}")


# =============================================================================
# Modular imports from symbolu_training.training.unified
#
# All classes and functions previously defined inline (~13,000 lines) have been
# extracted to symbolu/training/unified/ for better organization. Importing
# them here maintains backward compatibility:
#   from train_unified_llm import SomeClass  # still works
# =============================================================================

from symbolu_training.training.unified import (
    # utilities
    _SimpleByteTokenizer,
    CSR_STOPWORDS,
    WholeWordCSRHelper,
    calculate_sparse_csr_loss,
    SOVEREIGN_R_MATRIX,
    VRTTI_NAMES,
    ONTOLOGICAL_LAYER_NAMES,
    get_layer_vrtti_weights,
    get_pramana_weights,
    get_layer_gradient_scale,
    get_dominant_vrtti,
    # config
    UnifiedTrainingConfig,
    MODEL_PRESETS,
    build_srk_config_from_legacy,
    build_srk_loss_config,
    # data
    TextDataset,
    FineWebStreamingDataset,
    cache_validation_batches,
    load_data,
    # vram_manager
    VRAMGovernor,
    AutoBatchSizer,
    # diagnostics
    compute_layer_gradient_norm,
    apply_kosha_phase_steering,
    compute_kosha_steering_stats,
    compute_kosha_vritti_diagnostics,
    format_kosha_diagnostic,
    compute_csr_diagnostics,
    format_csr_diagnostic,
    compute_onto_bridge_diagnostics,
    format_onto_bridge_diagnostic,
    compute_sovereign_state_diagnostics,
    format_sovereign_state_diagnostic,
    # ontological_flow
    OntologicalBridge,
    create_ontological_bridge,
    compute_rmatrix_loss_weight,
    EvolutionaryBridge,
    ToroidalConsistencyLoss,
    EvolutionaryGate,
    EvolutionaryFlowNetwork,
    EvolutionaryFlowLoss,
    # intelligence_engine
    MetacognitiveTracker,
    HiddenStateExtractor,
    EvolutionaryIntelligenceEngine,
    # gradient_control
    HierarchicalGradientScaler,
    WeightTransfer,
    # training_state
    TrainingStateTracker,
    GradNormEMA,
    TrainingGunas,
    SattvicBrake,
    # phase_controllers
    SovereignPhaseController,
    AdaptiveTrainingController,
    AdaptiveSlotLRController,
    # scheduling
    DynamicWindowScheduler,
    AdaptiveWarmupScheduler,
    PPLAlphaCurriculum,
    ResonanceStateScheduler,
    update_alpha_schedule,
    # curriculum
    CurriculumController,
    SequenceLengthCurriculum,
    dampen_layer_momentum,
    on_seq_len_transition,
    should_sync_curriculum_update,
    ThreePhaseCurriculum,
    InvertedLayerCurriculumController,
    # relaxation
    DynamicRelaxationController,
    # evaluation
    generate_sample,
    compute_sample_metrics,
    run_quality_samples,
    run_factual_eval,
    run_knowledge_probes,
    LRAValidator,
    run_phase_rotation_test,
    print_phase_rotation_results,
    ReadinessIndex,
    # losses
    compute_ontological_loss,
    _build_sovereign_state,
    forward_chunked,
    compute_phase_loss,
    # control_plane
    ArchitectureHealthReport,
    run_architecture_health_check,
    check_quad_utilization,
    LightweightProbeHooks,
    # checkpointing
    save_checkpoint,
    load_checkpoint,
    # model_factory
    create_model,
    PerLayerPhaseController,
)

# Appendix G: Bliss Coherence Functional & Monitoring (Phase 1)
# Imported directly to avoid __init__.py circular dependency
from symbolu_training.training.unified.bliss_coherence import (
    BlissConfig,
    BlissCoherenceFunctional,
    OntologyHealthMonitor,
    GradientVarianceTracker,
)

# =============================================================================
# TRAINING LOOP
# =============================================================================

def _build_training_config_snapshot(config: UnifiedTrainingConfig) -> dict:
    """Build a lightweight config snapshot for checkpoint metadata."""
    return {
        "model_type": config.model_type,
        "model_size": config.model_size,
        "max_seq_len": config.max_seq_len,
        "batch_size": config.batch_size,
        "vocab_size": config.vocab_size,
        "dataset": config.dataset,
        "learning_rate": config.learning_rate,
    }


def train(config: UnifiedTrainingConfig):
    """Main training loop with optional PIDv2 Governor."""

    # Setup
    torch.manual_seed(config.seed)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    print(f"\n{'='*70}")
    print("   UNIFIED SYMBOLU LLM TRAINING V9.5.2")
    print(f"{'='*70}")
    print(f"\n  Model Type: {config.model_type.upper()}")
    print(f"  Model Size: {config.model_size}")
    print(f"  Max Seq Len: {config.max_seq_len:,}")
    print(f"  Dataset: {config.dataset}")
    print(f"  Device: {device}")
    print(f"  Controller: {config.controller.upper() if config.controller != 'none' else 'None'}")
    print(f"  Gradient Checkpointing: {config.gradient_checkpointing}")
    print(f"  Mixed Precision: {config.mixed_precision}")
    print(f"  9:3 Hierarchical Split: {'ENABLED' if config.use_9_3_split else 'Disabled'}")
    if config.enable_dynamic_relaxation:
        print(f"  Dynamic Relaxation: ENABLED ({config.authority_layers}:{config.sensory_layers} → {config.relaxation_target_authority}:{config.relaxation_target_sensory})")
        print(f"    Stability Threshold: {config.relaxation_stability_threshold} for {config.relaxation_stability_window} steps")

    # V9.9.5: Warn if decorr_loss_weight is set but model type doesn't support it
    if hasattr(config, 'decorr_loss_weight') and config.decorr_loss_weight > 0:
        if config.model_type in ('hybrid', 'ontological_hybrid', 'mistral_hybrid'):
            print(f"  Decorrelation Loss: ENABLED (weight={config.decorr_loss_weight})")
        else:
            print(f"\n  ⚠️  WARNING: --decorr_loss_weight={config.decorr_loss_weight} IGNORED!")
            print(f"     Decorrelation loss only works with --model_type hybrid, ontological_hybrid, or mistral_hybrid")
            print(f"     Current model_type: {config.model_type}")
            print(f"     To enable decorrelation loss, use: --model_type hybrid --decorr_loss_weight {config.decorr_loss_weight}\n")

    # Load tokenizer (with offline fallback)
    if HF_AVAILABLE:
        try:
            tokenizer = AutoTokenizer.from_pretrained("gpt2")
            tokenizer.model_max_length = int(1e12)
        except (OSError, Exception) as e:
            print(f"  ⚠️  Cannot load GPT-2 tokenizer ({type(e).__name__}). Using byte-level fallback.")
            tokenizer = _SimpleByteTokenizer()
    else:
        print("  ⚠️  HuggingFace not installed. Using byte-level fallback tokenizer.")
        tokenizer = _SimpleByteTokenizer()

    # Create model BEFORE data loading (needed for AutoBatchSizer)
    model = create_model(config, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"\n  Model Parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # Stage 9: Wire ablation config into all compatible modules
    _ablation_cfg = None
    if (config.ablation_disable_phase_sync or config.ablation_disable_vritti
            or config.ablation_disable_guna_bias or config.ablation_enable_dual_channel_intent
            or config.ablation_log_mechanism_strength_every > 0):
        from symbolu_training.training.conscious_generation.ablation.config import AttentionAblationConfig
        _ablation_cfg = AttentionAblationConfig(
            use_phase_sync=not config.ablation_disable_phase_sync,
            use_vritti_modulation=not config.ablation_disable_vritti,
            use_guna_bias=not config.ablation_disable_guna_bias,
            use_dual_channel_intent=config.ablation_enable_dual_channel_intent,
            log_mechanism_strength_every=config.ablation_log_mechanism_strength_every,
        )
        _ablation_count = 0
        for module in model.modules():
            if hasattr(module, 'ablation_config'):
                module.ablation_config = _ablation_cfg
                _ablation_count += 1
        print(f"  [Stage 9] Ablation config applied to {_ablation_count} module(s): {_ablation_cfg.label()}")

    # For mistral_cg/mistral_hybrid, use the backbone's own tokenizer so token IDs
    # match the Mistral embedding table (GPT-2 vocab=50257 > Mistral vocab=32768)
    if config.model_type in ("mistral_cg", "mistral_hybrid") and hasattr(model, "tokenizer") and model.tokenizer is not None:
        tokenizer = model.tokenizer
        tokenizer.model_max_length = int(1e12)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        config.vocab_size = len(tokenizer)
        print(f"  [{config.model_type}] Using Mistral tokenizer (vocab_size={config.vocab_size})")

    # Knowledge Distillation: Load frozen Mistral teacher
    mistral_teacher = None
    distill_tokenizer = None
    if config.distill_from_mistral:
        if config.model_type in ("mistral_cg", "mistral_hybrid"):
            print(f"  [Distillation] WARNING: distill_from_mistral with model_type={config.model_type} "
                  "is redundant — Mistral is already the backbone. Skipping teacher.")
        else:
            from symbolu_training.training.unified.mistral_teacher import MistralTeacher
            quantize = config.mistral_quantize if config.mistral_quantize != "none" else None
            mistral_teacher = MistralTeacher(
                model_name=config.mistral_model_name,
                quantize=quantize,
                device_map=config.mistral_device_map,
                trust_remote_code=config.mistral_trust_remote_code,
            )
            mistral_teacher.eval()
            mistral_teacher.print_summary()
            distill_tokenizer = mistral_teacher.tokenizer
            if distill_tokenizer.pad_token is None:
                distill_tokenizer.pad_token = distill_tokenizer.eos_token
            print(f"    Temperature: {config.distill_temperature}")
            print(f"    Alpha (KD weight): {config.distill_alpha}")
            if config.distill_warmup_steps > 0:
                print(f"    CE-only warmup: {config.distill_warmup_steps} steps")

    # V11: Disable/reset adaptive constraint relaxation if requested
    if config.global_tokens_enabled:
        _sm = getattr(model, 'slot_memory', None)
        if _sm is None:
            _sm = getattr(getattr(model, 'hybrid', model), 'slot_memory', None)
        if _sm is not None:
            if config.reset_slot_constraints:
                _sm.reset_constraints()
                print(f"  Slot Constraints: RESET to initial defaults")
            if config.disable_slot_adaptive_constraints:
                _sm.enable_adaptive_constraints = False
                print(f"  Slot Adaptive Constraints: DISABLED")
            # V11: Override gate ceiling parameters from CLI
            _gate_overrides = []
            if getattr(config, 'slot_gate_target', None) is not None:
                _sm._gate_target = config.slot_gate_target
                _gate_overrides.append(f"target={config.slot_gate_target}")
            if getattr(config, 'slot_gate_ceil_weight', None) is not None:
                _sm._gate_ceil_weight = config.slot_gate_ceil_weight
                _gate_overrides.append(f"weight={config.slot_gate_ceil_weight}")
            if getattr(config, 'slot_gate_ceil_margin', None) is not None:
                _sm._gate_ceil_margin = config.slot_gate_ceil_margin
                _gate_overrides.append(f"margin={config.slot_gate_ceil_margin}")
            if _gate_overrides:
                print(f"  Gate Ceiling: {', '.join(_gate_overrides)}")
            # V16: Semantic coherence gate floor override
            if getattr(config, 'slot_coherence_floor', None) is not None:
                _sm._coherence_floor = config.slot_coherence_floor
                print(f"  Coherence Floor: {config.slot_coherence_floor}")
            # V16.1: When tied mode is active, set decay steps to infinity so
            # the step-based decay in forward() becomes a no-op — the controller
            # will drive _coherence_floor directly at each eval point.
            if getattr(config, 'slot_coherence_floor_tied', True) and config.slot_lr_eta > 0:
                _sm._coherence_floor_decay_steps = float('inf')

    # V10.6.3: Architecture Health Check (PASS/WARN/FAIL)
    if config.run_architecture_health_check:
        health_report = run_architecture_health_check(model, config, device)
        overall = health_report.print_report()
        if overall == "FAIL" and config.architecture_health_strict:
            print("\n  ❌ ABORTING: Architecture health check FAILED (--architecture_health_strict)")
            print("     Fix the issues above or use --no_architecture_health_check to skip\n")
            return
        elif overall == "WARN":
            print("  ⚠️  Continuing with warnings. Consider reviewing the issues above.\n")

    # V10.6.7: Initialize Lightweight Probe Hooks (if enabled)
    probe_hooks = None
    if config.enable_probe_hooks:
        probe_hooks = LightweightProbeHooks(model, config, device)
        print(f"  🔬 Probe Hooks: ENABLED (interval={config.probe_hook_interval}, types={config.probe_hook_types})")

    # torch.compile() for faster training (PyTorch 2.0+)
    if config.use_compile:
        try:
            print(f"  Compiling model with torch.compile()...")
            model = torch.compile(model, mode="reduce-overhead")
            print(f"  torch.compile: ENABLED (reduce-overhead mode)")
        except Exception as e:
            print(f"  torch.compile: FAILED ({e})")
            print(f"  Continuing without compilation...")
    else:
        print(f"  torch.compile: Disabled (use --use_compile to enable)")

    # Auto Batch Sizing: Probe VRAM at startup to find optimal batch size
    if config.enable_auto_batch:
        print(f"\n  Auto Batch Sizing: ENABLED")

        # V9.5.2: Model size is the PRIMARY factor in batch sizing
        # GPU VRAM is a "zero-sum game":
        #   - FLOOR (static): Model weights + Optimizer states + SGP buffers
        #   - SWING SPACE (dynamic): Activations (batch × seq × layers)
        # Larger models → bigger floor → less swing space → smaller batches
        #
        # Base limits are calibrated for LARGE models (conservative)
        # Smaller models scale UP because they have more swing space
        model_size_scale = {
            "tiny": 4.0,    # ~4x swing space vs large
            "small": 3.0,   # ~3x swing space vs large
            "medium": 2.0,  # ~2x swing space vs large
            "large": 1.0,   # Base limit (tested, conservative)
        }
        size_factor = model_size_scale.get(config.model_size, 1.0)

        # V9.5.2: Sequence length scaling (baseline: 2048)
        # Activations scale linearly with seq len (attention is handled by flash/sdpa)
        seq_baseline = 2048
        if config.max_seq_len < seq_baseline:
            # Shorter sequences: more swing space available
            seq_factor = min(2.0, seq_baseline / config.max_seq_len)
        else:
            # Longer sequences: less swing space
            seq_factor = max(0.5, seq_baseline / config.max_seq_len)

        # Combined scaling factor
        combined_factor = size_factor * seq_factor

        # Sovereign loss requires (B, Seq, Vocab) tensors - massive overhead
        # V9.5.2: BASE LIMITS for LARGE model + 2048 seq (smallest swing space)
        #   - A100 (80GB): 16 max batch for large
        #   - H100 (96GB): 24 max batch for large
        #   - H200 (141GB): 32 max batch for large
        # Smaller models can scale UP from these limits
        if config.enable_sovereign_loss:
            total_vram_gb = torch.cuda.get_device_properties(device).total_memory / 1e9
            if total_vram_gb >= 140:  # H200 class (141GB+)
                base_max_batch = 32   # Large: 32, Medium: 64, Small: 96, Tiny: 128
            elif total_vram_gb >= 90:  # H100 class (96GB)
                base_max_batch = 24   # Large: 24, Medium: 48, Small: 72, Tiny: 96
            elif total_vram_gb >= 70:  # A100 80GB class
                base_max_batch = 16   # Large: 16, Medium: 32, Small: 48, Tiny: 64
            else:  # Smaller GPUs
                base_max_batch = 8
            # Apply scaling (smaller models get more swing space)
            auto_max_batch = max(8, int(base_max_batch * combined_factor))
            print(f"  ⚠️  Sovereign Loss: max_batch={auto_max_batch} (VRAM: {total_vram_gb:.0f}GB, model: {config.model_size}, seq: {config.max_seq_len}, scale: {combined_factor:.2f}x)")
        else:
            auto_max_batch = max(8, int(64 * combined_factor))

        # V9.8.10: Use curriculum start length if enabled, otherwise max_seq_len
        probe_seq_len = config.seq_len_start if config.enable_seq_curriculum else config.max_seq_len
        if config.enable_seq_curriculum:
            print(f"  📐 Seq Curriculum: Probing with START length {probe_seq_len} (will ramp to {config.max_seq_len})")
            # Store probe length for later batch scaling reference
            config.auto_batch_probed_seq_len = probe_seq_len
        else:
            config.auto_batch_probed_seq_len = config.max_seq_len

        auto_sizer = AutoBatchSizer(
            model=model,
            seq_len=probe_seq_len,
            vocab_size=config.vocab_size,
            target_utilization=config.auto_batch_target_utilization,
            safety_margin=config.auto_batch_safety_margin,
            min_batch_size=1,
            max_batch_size=auto_max_batch,
            device=device,
        )

        probed_batch, probed_accum = auto_sizer.find_optimal_batch(
            target_effective_batch=config.auto_batch_target_effective,
            verbose=True,
        )

        # Update config with probed values
        old_batch = config.batch_size
        old_accum = config.gradient_accumulation
        config.batch_size = probed_batch
        config.gradient_accumulation = probed_accum

        print(f"  Auto Batch: {old_batch}×{old_accum} → {probed_batch}×{probed_accum}")
        print(f"  Effective Batch: {probed_batch * probed_accum}")

    # Load data (using potentially updated batch_size from AutoBatchSizer)
    train_loader, val_loader = load_data(config, tokenizer)

    # Pre-cache validation batches for streaming datasets (eliminates 7-min delay)
    cached_val_batches = None
    if config.dataset == "fineweb" and config.cache_val_batches > 0:
        print(f"  Pre-caching {config.cache_val_batches} validation batches...")
        cached_val_batches = cache_validation_batches(val_loader, config.cache_val_batches)
        print(f"  Cached {len(cached_val_batches)} validation batches")

    # Initialize Sovereign-1 loss if available and enabled
    sovereign_loss = None
    if config.use_sovereign_loss and SOVEREIGN_AVAILABLE:
        from agentic.sovereign.loss import SovereignLoss, SovereignLossConfig
        sov_config = SovereignLossConfig(
            weight_guna=config.sovereign_weight_guna,
            weight_s=config.sovereign_weight_s,
            weight_r=config.sovereign_weight_r,
            weight_c=config.sovereign_weight_c,
        )
        sovereign_loss = SovereignLoss(config=sov_config).to(device)
        print(f"  Sovereign-1 Loss: ENABLED (R-weight={config.sovereign_weight_r})")
    else:
        print(f"  Sovereign-1 Loss: Disabled (using legacy loss)")

    # Initialize Sovereign Engine for Patent B1/S3 loss
    sovereign_engine = None
    stability_state = None
    if config.enable_sovereign_loss:
        from agentic.sovereign.metrics import SovereignEngine, SovereignLossConfig as SovEngineConfig, StabilityState
        sov_engine_config = SovEngineConfig(
            lambda_b1=config.b1_lambda,
            mu_s3=config.mu_s3,
            gc_floor=config.gc_floor,
        )
        sovereign_engine = SovereignEngine(config=sov_engine_config)
        print(f"  Sovereign-Lagrangian Loss: ENABLED (λ_B1={config.b1_lambda}, μ_S3={config.mu_s3})")
        if config.enable_stability_constraint:
            stability_state = StabilityState(window_size=5)
            print(f"  Stability Constraint [S8]: ENABLED (entropy anchoring)")
    else:
        print(f"  Sovereign-Lagrangian Loss: Disabled")

    # Initialize Sovereign Alert Monitor for auto-pivot logic
    alert_monitor = None
    if config.enable_sovereign_loss or config.use_9_3_split:
        from agentic.sovereign.metrics import SovereignAlertMonitor, AlertConfig
        alert_config = AlertConfig(
            sa_ratio_danger=0.55,
            gc_danger=0.25,
            # gc_floor is used by SovereignEngine, not AlertConfig
            # AlertConfig uses gc_healthy (0.80) for recovery detection
        )
        alert_monitor = SovereignAlertMonitor(config=alert_config)
        print(f"  Sovereign Alert Monitor: ENABLED (Auto-Pivot)")

    # Initialize S8 Stability Hook for entropy monitoring
    s8_hook = None
    if config.enable_sovereign_loss or config.enable_stability_constraint:
        from agentic.sovereign.metrics import S8StabilityHook, compute_semantic_entropy, format_sovereign_dashboard
        s8_hook = S8StabilityHook(
            window_size=5,
            brake_sensitivity=5.0,
            max_brake=0.5,
            recovery_rate=0.1,
        )
        print(f"  S8 Stability Hook: ENABLED (Entropy Guard)")

    # Initialize CSR Phoneme-Ontological Grounding
    csr_provider = None
    csr_entropy_sink = None
    csr_synthesis_gate = None
    if config.enable_csr and CSR_AVAILABLE:
        # V9.5.2 Optimization: Wait for background G2P preload to complete
        # This ensures CMUdict and g2p_en are ready (should already be loaded by now)
        if csr_wait_preload is not None:
            csr_wait_preload(timeout=30.0)
        # Get correct d_model from model config or preset
        preset = MODEL_PRESETS[config.model_size]
        csr_d_model = preset['embed_dim']
        if hasattr(model, 'config') and hasattr(model.config, 'd_model'):
            csr_d_model = model.config.d_model
        csr_provider, csr_entropy_sink, csr_synthesis_gate = create_csr_for_training(
            model_config=type('Config', (), {'d_model': csr_d_model})(),
            tokenizer=tokenizer,
            lambda_csr=config.csr_lambda,
            use_phase_gating=config.csr_use_phase_gating,
            trainable=config.csr_trainable,
        )
        csr_provider = csr_provider.to(device)
        csr_entropy_sink = csr_entropy_sink.to(device) if config.csr_use_entropy_sink else None
        csr_synthesis_gate = csr_synthesis_gate.to(device) if config.csr_use_synthesis_gate else None
        print(f"  CSR Phoneme Grounding: ENABLED (λ_csr={config.csr_lambda}, τ={config.csr_tau} → {1/config.csr_tau:.1f}x gradient amp)")

        # V9.7.0: Initialize Sparse Supervision helper if enabled
        if config.csr_sparse_supervision:
            print(f"  ⚡ [CSR SPARSE] Whole-Word Supervision: ENABLED at Layer {config.csr_alignment_layer}")
            print(f"     Content-Only: {config.csr_content_word_only} | Stopwords filtered: {len(CSR_STOPWORDS)}")
    elif config.enable_csr and not CSR_AVAILABLE:
        print(f"  CSR Phoneme Grounding: Disabled (module not available)")
    else:
        print(f"  CSR Phoneme Grounding: Disabled")

    # Wire CSR affinity into CG token cache so R_tok gets populated
    if hasattr(model, 'conscious_gen') and 'token_cache' in model.conscious_gen:
        _cg_cache = model.conscious_gen['token_cache']
        _affi_table = None

        # Option 1: Get from existing CSR provider (when enable_csr=True)
        if csr_provider is not None and hasattr(csr_provider, '_token_affinity_table'):
            _affi_table = csr_provider._token_affinity_table

        # Option 2: Build standalone affinity table (when enable_csr=False but CSR module exists)
        elif CSR_AVAILABLE:
            try:
                if csr_wait_preload is not None:
                    csr_wait_preload(timeout=30.0)
                _tmp_provider = CSREmbeddingProvider(CSRConfig(), tokenizer)
                _tmp_provider = _tmp_provider.to(device)
                if hasattr(_tmp_provider, '_token_affinity_table') and _tmp_provider._token_affinity_table is not None:
                    _affi_table = _tmp_provider._token_affinity_table.clone()
                    print(f"  [Conscious Gen] Built standalone CSR affinity table for CG token cache")
                del _tmp_provider
            except Exception as e:
                print(f"  [Conscious Gen] WARNING: Could not build CSR affinity table: {e}")

        if _affi_table is not None:
            _cg_cache._csr_affinity_fn = lambda emb, _t=_affi_table: _t.to(emb.device)
            print(f"  [Conscious Gen] CSR affinity wired into token cache (R_tok will be populated)")
        else:
            print(f"  [Conscious Gen] WARNING: No CSR affinity available — R_tok will stay zeros")

    # V9.8.6: Initialize curriculum state variables (will be populated if resuming)
    # These must be defined before curriculum controllers are created
    resumed_csr_curriculum_state = None
    resumed_kosha_curriculum_state = None
    resumed_onto_curriculum_state = None
    resumed_pidv2_curriculum_state = None
    resumed_kosha_gyroscope_state = None  # V9.8.6: Kosha Gyroscope (InvertedCurriculumController)
    resumed_evoflow_state = None  # V9.8.6: EvoFlow (EvolutionaryIntelligenceEngine)
    resumed_cg_stage_manager_state = None  # CG Curriculum Stage Manager (Stages A-D)
    resumed_kv_supervisor_state = None  # KV Supervision (Kosha-Vritti Structured Supervision)
    resumed_jepa_injection_projector_state = None  # Phase 4: JEPA injection projector

    # V9.8.6: Initialize CSR Three-Phase Curriculum Controller
    csr_curriculum = None
    csr_graduated = False
    if config.enable_csr and csr_provider is not None:
        csr_curriculum = ThreePhaseCurriculum(
            name="CSR",
            engage_ppl=config.csr_engage_ppl,
            disengage_ppl=config.csr_disengage_ppl,
            rampdown_steps=config.csr_rampdown_steps,
        )
        print(f"  🎓 CSR Three-Phase Curriculum:")
        print(f"       CONSTRUCTION: PPL > {config.csr_engage_ppl} (full grounding)")
        print(f"       TRANSITION:   {config.csr_disengage_ppl} < PPL < {config.csr_engage_ppl} (rampdown)")
        print(f"       POLISHING:    PPL < {config.csr_disengage_ppl} (CSR off after {config.csr_rampdown_steps} steps)")

    # ==========================================================================
    # Appendix G: Bliss Coherence Measurement + Monitoring + Gating
    # Phase 1/2: Bliss is computed and LOGGED (no gating)
    # Phase 3:   Bliss gates CSR injection strength via σ(γ·(B−τ))
    # OntologyHealthMonitor tracks 12D projection health.
    # GradientVarianceTracker tracks gradient stability.
    # ==========================================================================
    bliss_functional = None
    ontology_health_monitor = None
    gradient_variance_tracker = None
    bliss_lambda_eff_csr = None  # Phase 3: Bliss-gated CSR lambda (None = use config.csr_lambda)
    bliss_lambda_eff_jepa = None  # Phase 4: Bliss-gated JEPA lambda (None = use config.jepa_injection_lambda)
    jepa_injection_projector = None  # Phase 4: 32D→d_model projector for JEPA prior

    if config.enable_bliss_monitoring:
        bliss_functional = BlissCoherenceFunctional(BlissConfig(
            beta=config.bliss_beta,
            gamma=config.bliss_gate_gamma,
            lambda_min=config.bliss_gate_lambda_min,
            warmup_steps=config.bliss_gate_warmup_steps if config.enable_bliss_gating else 0,
        ))
        if config.enable_jepa_injection:
            print(f"  [Appendix G] Bliss Coherence: ENABLED (Phase 4: CSR + JEPA multi-prior gating)")
            print(f"     β={config.bliss_beta} | γ={config.bliss_gate_gamma} | "
                  f"λ_min={config.bliss_gate_lambda_min} | warmup={config.bliss_gate_warmup_steps}")
            print(f"     λ_CSR={config.csr_lambda} | λ_JEPA={config.jepa_injection_lambda} | "
                  f"JEPA layer={config.jepa_injection_layer}")
        elif config.enable_bliss_gating:
            print(f"  [Appendix G] Bliss Coherence: ENABLED (Phase 3: gating ACTIVE)")
            print(f"     β={config.bliss_beta} | γ={config.bliss_gate_gamma} | "
                  f"λ_min={config.bliss_gate_lambda_min} | warmup={config.bliss_gate_warmup_steps}")
        else:
            print(f"  [Appendix G] Bliss Coherence Monitoring: ENABLED (Phase 1/2: log only, no gating)")
            print(f"     β={config.bliss_beta} | log_interval={config.bliss_log_interval}")

    if config.enable_12d_health_monitor:
        ontology_health_monitor = OntologyHealthMonitor(
            check_every_n_steps=config.health_monitor_interval,
        )
        print(f"  [Appendix G] 12D Health Monitor: ENABLED (every {config.health_monitor_interval} steps)")

    if config.enable_gradient_tracker:
        gradient_variance_tracker = GradientVarianceTracker(
            window_size=100,
            adaptive_dampen=config.enable_variance_dampen,
            dampen_threshold_layers=config.variance_dampen_threshold,
            dampen_min_factor=config.variance_dampen_min,
            dampen_recovery_rate=config.variance_dampen_recovery,
        )
        dampen_str = f", adaptive_dampen={'ON' if config.enable_variance_dampen else 'OFF'}"
        print(f"  [Appendix G] Gradient Variance Tracker: ENABLED (window=100{dampen_str})")

    # Initialize SGP (Stochastic Gradient Persistence) and Sattvic Controller
    sattvic_controller = None
    sgp_controller = None
    if config.enable_sgp and SGP_AVAILABLE:
        # Create Sattvic Controller for dynamic λ_csr regulation
        sattvic_config = SattvicConfig(
            initial_lambda=config.sattvic_initial_lambda,
            floor_lambda=config.sattvic_floor_lambda,
            warmup_steps=config.sattvic_warmup_steps,
            variance_window=config.sattvic_variance_window,
            variance_threshold=config.sattvic_variance_threshold,
        )
        sattvic_controller = SattvicController(sattvic_config)

        # Create SGP Controller synchronized with Sattvic
        sgp_config = SGPConfig(
            base_rate=config.sgp_base_rate,
            stagnation_rate=config.sgp_stagnation_rate,
            gamma=config.sgp_gamma,
        )
        sgp_controller = SGPController(sgp_config)
        sgp_controller.attach_sattvic_controller(sattvic_controller)

        # Register Authority layer parameters (layers 0 to authority_layers-1) for gradient persistence
        authority_params = []
        num_authority_layers = config.authority_layers  # Use configured split, not hardcoded 9
        for name, param in model.named_parameters():
            # Match authority layers (0 to num_authority_layers-1)
            # Support multiple naming conventions: layers.N, layer.N, blocks.N
            layer_match = False
            for i in range(num_authority_layers):
                if f"layers.{i}." in name or f"layer.{i}." in name or f"blocks.{i}." in name:
                    layer_match = True
                    break
            if layer_match and param.requires_grad:
                authority_params.append(param)
        sgp_controller.register_authority_params(authority_params)

        print(f"  SGP Controller: ENABLED (base_rate={config.sgp_base_rate}, stagnation_rate={config.sgp_stagnation_rate}, γ={config.sgp_gamma})")
        print(f"    → Sattvic Controller: λ_init={config.sattvic_initial_lambda}, λ_floor={config.sattvic_floor_lambda}")
        print(f"    → Authority Params Registered: {len(authority_params)}")
    elif config.enable_sgp and not SGP_AVAILABLE:
        print(f"  SGP Controller: Disabled (module not available)")
    else:
        print(f"  SGP Controller: Disabled")

    # VRAM Governor for dynamic batch scaling
    vram_governor = VRAMGovernor(
        initial_batch_size=config.batch_size,
        min_batch_size=4,
        vram_threshold=config.vram_threshold,
        vram_critical=min(0.97, config.vram_threshold + 0.05),  # Critical = threshold + 5%
        vram_recovery_buffer=config.vram_recovery_buffer,
        check_interval=10,
        b1_compensation_rate=0.20,
        enable_accumulation_scaling=True,
        # V9.8.1: Target effective batch should include initial gradient accumulation
        target_effective_batch=config.batch_size * config.gradient_accumulation,
    )
    recovery_threshold = config.vram_threshold - config.vram_recovery_buffer
    print(f"  VRAM Governor: ENABLED (reduce={config.vram_threshold:.0%}, recover={recovery_threshold:.0%})")

    # LRA Validator (Long-Range Retrieval Testing)
    lra_validator = None
    if config.lra_validate_every > 0:
        haystack_lengths = [int(x) for x in config.lra_haystack_lengths.split(',')]
        lra_validator = LRAValidator(
            model=model,
            tokenizer=tokenizer if 'tokenizer' in dir() else None,
            device=device,
            haystack_lengths=haystack_lengths,
            num_samples=config.lra_num_samples,
            vocab_size=config.vocab_size,
        )
        print(f"  LRA Validator: ENABLED (every {config.lra_validate_every} steps, lengths={haystack_lengths})")

    # Checkpoint directory (needed for state tracker)
    ckpt_dir = Path(config.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # v2.7 Training State Tracker (Knowledge State Evolution)
    training_state_tracker = TrainingStateTracker(
        state_path=str(ckpt_dir / "training_state.json"),
        alpha=0.1,  # EMA learning rate
        enabled=True,
    )
    print(f"  v2.7 State Tracker: ENABLED (EMA α=0.1)")

    # V9.8.8: Sovereign Phase Controller (Graduated Phase Interventions)
    sovereign_phase_controller = SovereignPhaseController(
        enable=config.enable_sovereign_phase_controller,
        entropy_critical=config.spc_entropy_critical,
        entropy_warning=config.spc_entropy_warning,
        entropy_recovered=config.spc_entropy_recovered,
        variance_critical=config.spc_variance_critical,
        variance_warning=config.spc_variance_warning,
        variance_recovered=config.spc_variance_recovered,
        min_boost_duration=config.spc_min_boost_duration,
        alpha=config.spc_alpha,
        max_rotation_per_step=config.spc_max_rotation,
        damping_coefficient=config.spc_damping,
        velocity_threshold=config.spc_velocity_threshold,
    )
    if config.enable_sovereign_phase_controller:
        print(f"  🧠 Sovereign Phase Controller: ENABLED")
        print(f"     Thresholds: entropy[{config.spc_entropy_critical:.2f}→{config.spc_entropy_warning:.2f}→{config.spc_entropy_recovered:.2f}]")
        print(f"     Variance: [{config.spc_variance_critical:.4f}→{config.spc_variance_warning:.4f}→{config.spc_variance_recovered:.4f}]")
        print(f"     Damping: α={config.spc_alpha}, max_rotation={config.spc_max_rotation:.2f}rad")
    else:
        print(f"  🧠 Sovereign Phase Controller: DISABLED (diagnostics only)")

    # V9.8.9: Dynamic Window Scheduler (PPL-Adaptive Attention Span)
    # Parse custom schedule if provided
    custom_window_schedule = None
    if config.dws_schedule:
        try:
            custom_window_schedule = {}
            for pair in config.dws_schedule.split(','):
                ppl_str, win_str = pair.strip().split(':')
                custom_window_schedule[float(ppl_str)] = int(win_str)
        except Exception as e:
            print(f"  ⚠️  Invalid DWS schedule format: {e}")
            print(f"     Using default schedule")
            custom_window_schedule = None

    dynamic_window_scheduler = DynamicWindowScheduler(
        enable=config.enable_dynamic_window,
        window_schedule=custom_window_schedule,
        growth_rate_max=config.dws_growth_rate_max,
        shrink_rate_max=config.dws_shrink_rate_max,
        align_to_multiple=config.dws_align_to,
        smooth_transition_steps=config.dws_smooth_steps,
        min_steps_between_changes=config.dws_min_steps_between,
        hysteresis_factor=config.dws_hysteresis,
        vram_shrink_threshold=config.dws_vram_threshold,
    )
    if config.enable_dynamic_window:
        print(f"  📏 Dynamic Window Scheduler: ENABLED")
        print(f"     Start window: {dynamic_window_scheduler.current_window}")
        print(f"     Growth: ≤{config.dws_growth_rate_max:.0%}, Shrink: ≥{config.dws_shrink_rate_max:.0%}")
        print(f"     Smooth: {config.dws_smooth_steps} steps, Cooldown: {config.dws_min_steps_between} steps")
        if custom_window_schedule:
            print(f"     Custom schedule: {len(custom_window_schedule)} thresholds")
        else:
            print(f"     Default schedule: {len(dynamic_window_scheduler.schedule)} thresholds (128→1024)")
    else:
        print(f"  📏 Dynamic Window Scheduler: DISABLED (diagnostics only)")

    # Sattvic Brake (Lightweight Confidence via Phase Variance)
    sattvic_brake = SattvicBrake(
        model=model,
        authority_layers=config.authority_layers if hasattr(config, 'authority_layers') else 9,
        confidence_threshold=0.5,
        lr_reduction=0.8,
    )
    print(f"  Sattvic Brake: ENABLED (threshold=0.5, LR×0.8)")

    # Training Gunas (Bridge Training Physics to Cognitive Philosophy)
    training_gunas = TrainingGunas(
        grad_ema_alpha=0.1,  # Gradient norm EMA smoothing
        loss_ema_alpha=0.05,  # Loss velocity tracking
    )
    print(f"  Training Qualia: ENABLED (L/A/S tracking)")

    # Gradient Norm Throttle (Physical Safety Layer)
    # Reduces LR when gradient norms spike to prevent destructive weight updates
    gradient_throttle = None
    if GRADIENT_THROTTLE_AVAILABLE:
        gradient_throttle = GradientNormThrottle(
            ema_decay=0.99,           # Slow adaptation to gradient baseline
            spike_threshold=2.0,       # Trigger if gradient > 2x average
            min_factor=0.05,          # Allow deeper damping on severe spikes
            warmup_steps=config.warmup_steps,  # Skip throttling during warmup
        )
        print(f"  Gradient Throttle: ENABLED (spike>2x → LR×0.05 min)")

    # Toroidal Evolutionary Bridge (O12 → O1 Recursive Intelligence)
    evolutionary_bridge = None
    toroidal_loss_fn = None
    metacognitive_tracker = None
    if config.enable_toroidal_bridge:
        # Get model dimension - check multiple possible attribute locations
        model_dim = (
            getattr(model, 'embed_dim', None) or
            getattr(model, 'd_model', None) or
            getattr(getattr(model, 'config', None), 'embed_dim', None) or
            getattr(getattr(model, 'config', None), 'd_model', None) or
            512  # Fallback default
        )
        evolutionary_bridge = EvolutionaryBridge(
            dim=model_dim,
            num_layers=12,
            bridge_dropout=config.toroidal_dropout,
            use_gating=config.toroidal_use_gating,
            truncated_bptt_steps=config.toroidal_truncated_bptt,
            enable_sgp=config.enable_sgp,
            sgp_rate=config.sgp_base_rate,  # Use new SGP base rate
        ).to(device)
        toroidal_loss_fn = ToroidalConsistencyLoss(
            lambda_toroid=config.toroidal_lambda,
            min_coherence_threshold=config.toroidal_coherence_threshold,
        )
        metacognitive_tracker = MetacognitiveTracker(
            coherence_alarm_threshold=config.toroidal_coherence_threshold,
        )
        print(f"  Toroidal Bridge: ENABLED (λ={config.toroidal_lambda}, gate={config.toroidal_use_gating})")
        if config.enable_sgp:
            print(f"    → SGP (Stochastic Gradient Persistence): ENABLED (rate=1/{config.sgp_base_rate})")
        print(f"    → O12 (Absolving) feeds O1 (Potential) for recursive intelligence")

    # Full Evolutionary Flow System (Phase 2: All Layer Transitions with Delayed Resonance)
    evolutionary_engine = None
    hidden_state_extractor = None
    if config.enable_evolutionary_flow:
        # Get model dimension - check multiple possible attribute locations
        model_dim = (
            getattr(model, 'embed_dim', None) or
            getattr(model, 'd_model', None) or
            getattr(getattr(model, 'config', None), 'embed_dim', None) or
            getattr(getattr(model, 'config', None), 'd_model', None) or
            512  # Fallback default
        )
        evolutionary_engine = EvolutionaryIntelligenceEngine(
            dim=model_dim,
            num_layers=12,
            enable_backward_resonance=True,
            learning_rate_modulation=config.evo_lr_modulation,
            resonance_alpha=config.evo_resonance_alpha,
            lr_slowdown_factor=config.evo_lr_slowdown,
            lr_accelerate_factor=config.evo_lr_accelerate,
            dropout=config.evo_dropout,
            use_rmatrix=config.evo_use_rmatrix,
            coherence_window=config.evo_coherence_window,
            device=device,
        )
        # Update flow loss weights
        evolutionary_engine.flow_loss.lambda_micro = config.evo_micro_weight
        evolutionary_engine.flow_loss.lambda_meso = config.evo_meso_weight
        evolutionary_engine.flow_loss.lambda_macro = config.evo_macro_weight
        evolutionary_engine.flow_loss.min_coherence = config.toroidal_coherence_threshold

        print(f"  Evolutionary Flow: ENABLED (λ={config.evo_lambda}, dim={model_dim})")
        print(f"    → Micro:{config.evo_micro_weight} Meso:{config.evo_meso_weight} Macro:{config.evo_macro_weight}")
        print(f"    → Delayed Resonance α={config.evo_resonance_alpha}")
        print(f"    → LR Modulation: SLOW={config.evo_lr_slowdown}x ACCEL={config.evo_lr_accelerate}x")
        if config.evo_fluency_gate:
            print(f"    🚦 Fluency Gate: ENABLED (engage when step>{config.evo_fluency_min_steps} AND PPL<{config.evo_fluency_ppl_threshold})")
            print(f"       → EvoFlow gradients DORMANT until fluency achieved")

        # Create HiddenStateExtractor for models that don't return hidden_states
        hidden_state_extractor = HiddenStateExtractor(model, num_layers=12)
        print(f"    → Hidden State Extractor: ENABLED ({len(hidden_state_extractor.hooks)} hooks registered)")
        # V9.8.6: Restore EvoFlow state from checkpoint
        if resumed_evoflow_state is not None:
            evolutionary_engine.load_state(resumed_evoflow_state)
            print(f"  ✓ EvoFlow Restored: history={len(evolutionary_engine.evolution_history)}, gunas={evolutionary_engine.current_gunas}")

        if config.enable_toroidal_bridge:
            print(f"    ⚠️  Note: Toroidal Bridge superseded by Evolutionary Flow")

    # Also create HiddenStateExtractor for CSR safety layers if needed (and not already created)
    csr_needs_extractor = (
        config.enable_csr and CSR_AVAILABLE and
        (config.csr_use_entropy_sink or config.csr_use_synthesis_gate)
    )
    if csr_needs_extractor and hidden_state_extractor is None:
        hidden_state_extractor = HiddenStateExtractor(model, num_layers=12)
        print(f"  CSR Hidden State Extractor: ENABLED ({len(hidden_state_extractor.hooks)} hooks registered)")

    # ==========================================================================
    # V9.8.0: Sovereign Reasoning Kernel (SRK) Initialization
    # Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md
    # ==========================================================================
    srk = None
    srk_loss_fn = None
    srk_annealer = None
    srk_phase_hook = None
    srk_karma_state = None  # O12→O1 carryover buffer

    if config.enable_srk and SRK_AVAILABLE:
        # Get model dimensions
        preset = MODEL_PRESETS.get(config.model_size, MODEL_PRESETS['small'])
        model_dim = preset['embed_dim']
        num_heads = preset['num_heads']
        num_layers = preset['num_layers']

        # Build SRKConfig from training config
        srk_config = SRKConfig(
            state_dim=SOVEREIGN_STATE_DIM,
            hidden_dim=model_dim,
            num_heads=num_heads,
            dna_bridge_layer=config.srk_dna_bridge_layer,
            csr_alignment_layer=config.srk_csr_alignment_layer,
            witness_layer=config.srk_witness_layer,
            synthesis_layer=config.srk_synthesis_layer,
            enable_dna_bridge=config.srk_enable_dna_bridge,
            enable_witness=config.srk_enable_witness,
            enable_synthesis=config.srk_enable_synthesis,
            enable_imr=config.srk_enable_imr,
            isomorphism_threshold=config.srk_isomorphism_threshold,
            karma_decay=config.srk_karma_decay,
            enable_mauna=config.srk_enable_mauna,
            mauna_confidence_threshold=config.srk_mauna_confidence_threshold,
            mauna_consistency_threshold=config.srk_mauna_consistency_threshold,
        )

        # Create SRK instance
        srk = SovereignReasoningKernel(srk_config).to(device)

        # Create SRK Loss
        srk_loss_config = SRKLossConfig(
            hidden_dim=model_dim,  # Must match model's embed_dim
            state_dim=SOVEREIGN_STATE_DIM,
            lambda_f=config.srk_lambda_f,
            lambda_b=config.srk_lambda_b,
            lambda_c=config.srk_lambda_c,
            lambda_coherence=config.srk_lambda_coherence,
            lambda_entropy=config.srk_lambda_entropy,
            lambda_task=config.srk_lambda_task,
            enable_nidra_penalty=config.srk_enable_nidra_penalty,
            nidra_penalty_weight=config.srk_nidra_penalty_weight,
        )
        srk_loss_fn = SRKLoss(srk_loss_config).to(device)

        # Create SRK Annealer (Lambda Warmup/Rampdown)
        srk_annealer = SovereignAnnealer(
            total_steps=config.srk_total_steps,
            warmup_steps=config.srk_warmup_steps,
            invert=config.srk_invert_annealing,
        )

        # Create Phase Extraction Hook for Layer 7 (CSR alignment)
        srk_phase_hook = PhaseExtractionHook(
            target_layer=config.srk_csr_alignment_layer,
            num_heads=num_heads,
        )

        # Register hook on model if not already using HiddenStateExtractor
        # The hook will be called during forward pass to extract attention phases
        if hidden_state_extractor is None:
            hidden_state_extractor = HiddenStateExtractor(model, num_layers=num_layers)
            print(f"  SRK Hidden State Extractor: ENABLED ({len(hidden_state_extractor.hooks)} hooks registered)")

        # Initialize karma buffer (O12→O1 carryover)
        srk_karma_state = torch.zeros(config.batch_size, SOVEREIGN_STATE_DIM, device=device)

        print(f"\n  ╔══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V9.8.0: SOVEREIGN REASONING KERNEL (SRK) ENABLED                ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Layer Interventions:                                            ║")
        print(f"  ║    L{config.srk_dna_bridge_layer}: DNA Bridge (Ontology)     {'ACTIVE' if config.srk_enable_dna_bridge else 'OFF':>6}                      ║")
        print(f"  ║    L{config.srk_csr_alignment_layer}: Phase Hook (CSR)        ACTIVE                      ║")
        print(f"  ║    L{config.srk_witness_layer}: Witness Arbitrator     {'ACTIVE' if config.srk_enable_witness else 'OFF':>6}                      ║")
        print(f"  ║    L{config.srk_synthesis_layer}: Synthesis Gate         {'ACTIVE' if config.srk_enable_synthesis else 'OFF':>6}                      ║")
        print(f"  ║  IMR (Logic Templates):           {'ACTIVE' if config.srk_enable_imr else 'OFF':>6}                      ║")
        print(f"  ║  Mauna Protocol:                  {'ACTIVE' if config.srk_enable_mauna else 'OFF':>6}                      ║")
        print(f"  ║  Karma Decay (O12→O1):            {config.srk_karma_decay:.2f}                        ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Loss Configuration (B1/U2/S8):                                  ║")
        print(f"  ║    λ_task={config.srk_lambda_task:.1f}  λ_c={config.srk_lambda_c:.1f}  λ_ent={config.srk_lambda_entropy:.1f}  λ_coh={config.srk_lambda_coherence:.1f}         ║")
        anneal_mode = "INVERTED (phase-first)" if config.srk_invert_annealing else "NORMAL (ramp-up)"
        print(f"  ║  Annealing: {anneal_mode:<20} ({config.srk_total_steps:,} steps)    ║")
        print(f"  ╚══════════════════════════════════════════════════════════════════╝\n")
    elif config.enable_srk and not SRK_AVAILABLE:
        print(f"\n  ⚠️  SRK REQUESTED but module not available!")
        print(f"      Check: symbolu/sovereign/reasoning_kernel.py exists and imports correctly")
        print(f"      Falling back to legacy training without SRK.\n")

    # ==========================================================================
    # Phase-JEPA: Joint Embedding Predictive Architecture Initialization
    # Reference: docs/design/HYBRID_PHASE_JEPA_DESIGN.md
    # ==========================================================================
    jepa_model = None
    jepa_curriculum = None
    jepa_loss_scheduler = None

    if config.enable_jepa and JEPA_AVAILABLE:
        # Get model dimensions
        preset = MODEL_PRESETS.get(config.model_size, MODEL_PRESETS['small'])
        model_dim = preset['embed_dim']
        num_heads = preset['num_heads']
        num_layers = preset['num_layers']

        # V9.8.1: Set model dimensions on config for JEPA to pick up
        # Without this, JEPA defaults to 768 which fails for small model (512)
        config.embed_dim = model_dim
        config.num_heads = num_heads
        config.num_layers = num_layers

        # Create JEPA transformer (wraps the existing model as context encoder)
        jepa_model = create_phase_jepa_transformer(
            config,
            context_encoder=model,  # Use existing model as encoder
        ).to(device)

        # Create curriculum orchestrator if auto-transition enabled
        if config.jepa_auto_phase_transition:
            jepa_curriculum = create_curriculum_from_config(config)
            jepa_loss_scheduler = LossScheduler(jepa_curriculum)
            jepa_model.set_curriculum(jepa_curriculum)

        print(f"\n  ╔══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  PHASE-JEPA: Joint Embedding Predictive Architecture ENABLED     ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Predictor Configuration:                                        ║")
        print(f"  ║    Hidden Dim: {config.jepa_hidden_dim:4}    Heads: {config.jepa_num_heads}    k-Steps: {config.jepa_prediction_steps}             ║")
        print(f"  ║    Cosine Mode: {config.jepa_cosine_mode:8}                                     ║")
        print(f"  ║  Target Encoder:                                                 ║")
        print(f"  ║    EMA Momentum: {config.jepa_target_momentum:.3f}    Schedule: {config.jepa_momentum_schedule:8}           ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Loss Weights:                                                   ║")
        print(f"  ║    VICReg: {config.jepa_vicreg_weight:.1f}  Align: {config.jepa_alignment_weight:.1f}  Pred: {config.jepa_prediction_weight:.1f}  Ortho: {config.jepa_orthogonality_weight:.2f}   ║")
        print(f"  ║  Alignment Weights (Bhava/Semantic/Guna):                        ║")
        print(f"  ║    {config.jepa_bhava_weight:.1f} / {config.jepa_semantic_weight:.1f} / {config.jepa_guna_weight:.1f}                                        ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Training Curriculum:                                            ║")
        print(f"  ║    Phase: {config.jepa_training_phase.upper():6}    Auto-Transition: {'ON ' if config.jepa_auto_phase_transition else 'OFF'}              ║")
        print(f"  ║    Body Steps: {config.jepa_phase_body_steps:,}    Soul Steps: {config.jepa_phase_soul_steps:,}          ║")
        if config.jepa_enable_dynamic_graduation and config.jepa_auto_phase_transition:
            print(f"  ║  🎓 Dynamic Graduation: ENABLED                                   ║")
            print(f"  ║    Loss < {config.jepa_graduation_loss_threshold:.1f}  AND  Alignment > {config.jepa_graduation_alignment_threshold:.1f}                  ║")
        if config.jepa_enable_vritti_validation:
            print(f"  ║  Vritti Validation: ACTIVE                                       ║")
            print(f"  ║    Viparyaya: {config.jepa_viparyaya_threshold:.2f}    Vikalpa: {config.jepa_vikalpa_threshold:.2f}                      ║")
        if config.jepa_enable_karma_injection:
            print(f"  ║  Karma Injection (SRK→JEPA): ACTIVE                             ║")
        print(f"  ╚══════════════════════════════════════════════════════════════════╝\n")

        # Phase 4: Initialize JEPA→d_model projector for weak prior injection
        # Projects 32D Sovereign State predictions to hidden dimension
        if config.enable_jepa_injection:
            # SOVEREIGN_STATE_DIM (32) already imported at module level
            jepa_injection_projector = torch.nn.Sequential(
                torch.nn.Linear(SOVEREIGN_STATE_DIM, model_dim // 2, bias=False),
                torch.nn.GELU(),
                torch.nn.Linear(model_dim // 2, model_dim, bias=False),
            ).to(device)
            # Small init: std=0.01 per G.5.2 (Injection Discipline)
            for m in jepa_injection_projector:
                if isinstance(m, torch.nn.Linear):
                    torch.nn.init.normal_(m.weight, std=0.01)
            # Apply gradient scaling for slow learning
            lr_scale = config.jepa_injection_projector_lr_scale
            if lr_scale != 1.0:
                for p in jepa_injection_projector.parameters():
                    p.register_hook(lambda grad, s=lr_scale: grad * s)
            print(f"  [Appendix G Phase 4] JEPA Injection Projector: {SOVEREIGN_STATE_DIM}D → {model_dim}D")
            print(f"     λ_JEPA={config.jepa_injection_lambda} | layer={config.jepa_injection_layer} | "
                  f"LR_scale={lr_scale}")

    elif config.enable_jepa and not JEPA_AVAILABLE:
        print(f"\n  ⚠️  JEPA REQUESTED but module not available!")
        print(f"      Check: symbolu/jepa/__init__.py exists and imports correctly")
        print(f"      Falling back to training without JEPA.\n")

    # Entropy-Based Logit Scale Control (attach BEFORE optimizer so params are included)
    entropy_scale_module = None
    if config.enable_entropy_control_train:
        entropy_cfg = EntropyControlConfig(
            enable_entropy_control_train=True,
            enable_entropy_control_infer=config.enable_entropy_control_infer,
            entropy_topk=config.entropy_topk,
            entropy_h_min=config.entropy_h_min,
            entropy_h_max=config.entropy_h_max,
            entropy_lambda=config.entropy_control_lambda,
            logit_scale_min=config.logit_scale_min,
            logit_scale_max=config.logit_scale_max,
            infer_h_target=config.infer_h_target,
            infer_eta=config.infer_eta,
            infer_delta_clip=config.infer_delta_clip,
            log_every=config.log_every,
        )
        entropy_scale_module = attach_logit_scale(model, entropy_cfg)
        print(f"  Entropy Logit Scale Control: ENABLED (train)")
        print(f"    H_band=[{config.entropy_h_min}, {config.entropy_h_max}], lambda={config.entropy_control_lambda}")
        print(f"    Scale clamp=[{config.logit_scale_min}, {config.logit_scale_max}]")

    # State-Conditional Logit Scale ("Confidence Knob") + Entropy Band
    confidence_scaler = None
    entropy_band_loss = None
    vritti_risk_head = None
    confidence_scaler_config = None

    if config.enable_confidence_scaler and CONFIDENCE_SCALER_AVAILABLE:
        # Determine hidden dimension from model preset
        _cs_embed_dim = (
            config.n_embd if config.n_embd is not None
            else MODEL_PRESETS.get(config.model_size, {}).get('embed_dim', 512)
        )

        confidence_scaler_config = ConfidenceScalerConfig(
            enable=True,
            s_min=config.confidence_s_min,
            s_max=config.confidence_s_max,
            epsilon=config.confidence_epsilon,
            enable_risk_gating=config.confidence_enable_risk_gating,
            alpha_risk=config.confidence_alpha_risk,
            entropy_band_ratio_min=config.confidence_entropy_band_min,
            entropy_band_ratio_max=config.confidence_entropy_band_max,
            lambda_entropy_band=config.confidence_lambda_band,
            lambda_scale_penalty=config.confidence_lambda_scale,
            enable_vritti_head=config.confidence_enable_risk_gating,
            vritti_kl_weight=config.confidence_vritti_kl_weight,
            log_every=config.log_every,
        )

        confidence_scaler = ConfidenceScaler(_cs_embed_dim, confidence_scaler_config).to(device)
        entropy_band_loss = EntropyBandLoss(config.vocab_size, confidence_scaler_config).to(device)

        # Register as submodule on model so parameters are in state_dict
        model.confidence_scaler = confidence_scaler
        model.entropy_band_loss = entropy_band_loss

        cs_param_count = sum(p.numel() for p in confidence_scaler.parameters())

        if config.confidence_enable_risk_gating:
            vritti_risk_head = VrittiRiskHead(_cs_embed_dim, confidence_scaler_config).to(device)
            model.vritti_risk_head = vritti_risk_head
            cs_param_count += sum(p.numel() for p in vritti_risk_head.parameters())

        import math as _math
        _log_v = _math.log(config.vocab_size)
        print(f"\n  [CONFIDENCE] Per-Token Logit Scale: ENABLED")
        print(f"     Params: {cs_param_count:,} | s_range=[{config.confidence_s_min}, {config.confidence_s_max}]")
        print(f"     Entropy band: [{config.confidence_entropy_band_min * _log_v:.2f}, "
              f"{config.confidence_entropy_band_max * _log_v:.2f}] "
              f"(ratios [{config.confidence_entropy_band_min}, {config.confidence_entropy_band_max}] * log(V)={_log_v:.2f})")
        print(f"     lambda_band={config.confidence_lambda_band}, lambda_scale={config.confidence_lambda_scale}")
        if config.confidence_enable_risk_gating:
            print(f"     Risk gating: ENABLED (alpha={config.confidence_alpha_risk})")

    elif config.enable_confidence_scaler and not CONFIDENCE_SCALER_AVAILABLE:
        print("  [CONFIDENCE] WARNING: enable_confidence_scaler=True but module not available")

    # Optimizer
    # V10.15: Separate param groups for slot memory (configurable LR scale)
    # to prevent gradient variance explosions from cosine-similarity key matching
    _slot_memory_lr_scale = config.slot_memory_lr_scale
    _slot_param_ids = set()
    _slot_params = []
    _slot_no_wd_params = []  # V10.27: Params that receive zero gradient (exclude from WD)
    _main_params = []
    if hasattr(model, 'slot_memory') and model.slot_memory is not None:
        _sm = model.slot_memory
        # V10.27: slot_keys_init receives zero gradient (all uses detach slot_keys).
        # Weight decay on a zero-grad param just shrinks it pointlessly.
        _no_wd_names = {'slot_keys_init'}
        for name, p in _sm.named_parameters():
            _slot_param_ids.add(id(p))
            if name in _no_wd_names:
                _slot_no_wd_params.append(p)
            else:
                _slot_params.append(p)
        for p in model.parameters():
            if id(p) not in _slot_param_ids:
                _main_params.append(p)
        print(f"  [V10.15] Slot memory: separate param group ({len(_slot_params)} params + "
              f"{len(_slot_no_wd_params)} no-WD, LR={config.learning_rate * _slot_memory_lr_scale:.2e})")
    else:
        _main_params = list(model.parameters())

    _param_groups = [
        {'params': _main_params, 'lr': config.learning_rate,
         'weight_decay': config.weight_decay, 'betas': (config.beta1, config.beta2)},
    ]
    if _slot_params:
        _param_groups.append({
            'params': _slot_params, 'lr': config.learning_rate * _slot_memory_lr_scale,
            'weight_decay': config.weight_decay, 'betas': (config.beta1, config.beta2),
        })
    if _slot_no_wd_params:
        # V10.27: slot_keys_init gets zero gradient from all losses (every use
        # detaches slot_keys). Weight decay on a zero-grad param only shrinks
        # its magnitude, which is harmless (write path renormalizes) but wasteful.
        _param_groups.append({
            'params': _slot_no_wd_params, 'lr': config.learning_rate * _slot_memory_lr_scale,
            'weight_decay': 0.0, 'betas': (config.beta1, config.beta2),
        })

    if config.use_8bit_optimizer:
        try:
            import bitsandbytes as bnb
            optimizer = bnb.optim.AdamW8bit(
                _param_groups,
            )
            print(f"  8-bit Optimizer: ENABLED (bitsandbytes AdamW8bit)")
        except ImportError:
            print("  WARNING: bitsandbytes not installed, falling back to standard AdamW")
            print("           Install with: pip install bitsandbytes")
            optimizer = AdamW(_param_groups)
    else:
        optimizer = AdamW(_param_groups)

    # Phase 4: Add JEPA injection projector params to optimizer
    if jepa_injection_projector is not None:
        optimizer.add_param_group({
            'params': jepa_injection_projector.parameters(),
            'lr': config.learning_rate * config.jepa_injection_projector_lr_scale,
            'weight_decay': 0.01,
        })

    # Scheduler with warmup
    use_adaptive_warmup = config.warmup_until_ppl > 0
    if use_adaptive_warmup:
        # PPL-based adaptive warmup: ends when PPL < threshold OR max_warmup_steps reached
        scheduler = AdaptiveWarmupScheduler(
            optimizer=optimizer,
            base_lr=config.learning_rate,
            max_steps=config.max_steps,
            max_warmup_steps=config.warmup_steps,
            warmup_until_ppl=config.warmup_until_ppl,
            start_factor=0.1,
            eta_min_factor=0.1,
        )
        print(f"  LR Schedule: Adaptive warmup (until PPL < {config.warmup_until_ppl:.0f} or {config.warmup_steps} steps)")
    else:
        # Fixed-step warmup using SequentialLR
        # Note: PyTorch _LRScheduler.__init__ calls self.step() internally to set
        # the initial LR. This happens before any optimizer.step() has been called,
        # which triggers a spurious "lr_scheduler.step() before optimizer.step()"
        # warning. This is a known PyTorch quirk (not a real ordering bug).
        # Suppress only during scheduler construction.
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Detected call of `lr_scheduler.step\\(\\)` before")
            warmup_scheduler = LinearLR(
                optimizer,
                start_factor=0.1,
                end_factor=1.0,
                total_iters=config.warmup_steps,
            )
            cosine_scheduler = CosineAnnealingLR(
                optimizer,
                T_max=config.max_steps - config.warmup_steps,
                eta_min=config.learning_rate * 0.1,
            )
            scheduler = SequentialLR(
                optimizer,
                schedulers=[warmup_scheduler, cosine_scheduler],
                milestones=[config.warmup_steps],
            )
        print(f"  LR Schedule: Fixed warmup ({config.warmup_steps} steps) + cosine decay")

    # Resume from checkpoint if specified
    resume_step = 0
    best_val_loss = float('inf')
    resumed_hgs_state = None
    resumed_drc_state = None
    resumed_sgp_state = None
    resumed_sattvic_state = None
    resumed_srk_state = None
    resumed_scaler_state = None  # V9.8.1: AMP GradScaler state
    resumed_experiential_controller_state = None
    if config.resume:
        resume_path = Path(config.resume)
        # Check both single-file and split-file format existence
        split_model_path = Path(f"{resume_path.parent / resume_path.stem}_model.pt")
        if resume_path.exists() or split_model_path.exists():
            try:
                resume_result = load_checkpoint(
                    path=resume_path,
                    model=model,
                    optimizer=optimizer if not config.resume_weights_only else None,
                    scheduler=scheduler if not config.resume_weights_only else None,
                    weights_only=config.resume_weights_only,
                    device=device,
                )
                resume_step = resume_result["step"]
                best_val_loss = resume_result["best_val_loss"]
                resumed_hgs_state = resume_result.get("hgs_state")
                resumed_drc_state = resume_result.get("drc_state")
                resumed_sgp_state = resume_result.get("sgp_state")
                resumed_sattvic_state = resume_result.get("sattvic_state")
                resumed_srk_state = resume_result.get("srk_state")
                resumed_scaler_state = resume_result.get("scaler_state")  # V9.8.1
                # V9.8.6: Extract curriculum states
                resumed_csr_curriculum_state = resume_result.get("csr_curriculum_state")
                resumed_kosha_curriculum_state = resume_result.get("kosha_curriculum_state")
                resumed_onto_curriculum_state = resume_result.get("onto_curriculum_state")
                resumed_pidv2_curriculum_state = resume_result.get("pidv2_curriculum_state")
                resumed_kosha_gyroscope_state = resume_result.get("kosha_gyroscope_state")
                resumed_evoflow_state = resume_result.get("evoflow_state")
                resumed_kv_supervisor_state = resume_result.get("kv_supervisor_state")
                resumed_jepa_injection_projector_state = resume_result.get("jepa_injection_projector_state")
                resumed_cg_stage_manager_state = resume_result.get("cg_stage_manager_state")
                resumed_experiential_controller_state = resume_result.get("experiential_controller_state")
            except RuntimeError as e:
                # Checkpoint is corrupted - start from scratch
                print(f"\n  ⚠️  Failed to load checkpoint due to corruption")
                print(f"      Starting training from scratch instead...")
                # Keep default values (resume_step=0, etc.)
        else:
            print(f"\n  ⚠️  Checkpoint not found: {resume_path}")
            print(f"      (also checked split format: {split_model_path})")
            print(f"      Starting training from scratch...")

    # V9.8.6: Restore CSR curriculum state (CSR is already initialized above)
    if resumed_csr_curriculum_state is not None and csr_curriculum is not None:
        csr_curriculum.load_state(resumed_csr_curriculum_state)
        print(f"  ✓ CSR Curriculum Restored: Phase={csr_curriculum.phase}, Scale={csr_curriculum.scale:.3f}")
    # NOTE: Onto, Kosha, and PIDv2 curriculum restoration happens after their initialization below

    # V9.8.9: Initialize DWS window from resumed PPL if resuming
    if config.resume and best_val_loss < float('inf') and dynamic_window_scheduler is not None:
        resumed_ppl = math.exp(min(best_val_loss, 20))
        initial_window = dynamic_window_scheduler.set_initial_window_from_ppl(resumed_ppl)
        print(f"  ✓ DWS Window Initialized: {initial_window} (PPL={resumed_ppl:.1f})")

    # Formula [1331]: Hierarchical Gradient Scaling (9:3, 6:6, or any split)
    gradient_scaler_hgs = None
    if config.use_9_3_split or config.enable_gradient_scaling:
        gradient_scaler_hgs = HierarchicalGradientScaler(
            model=model,
            authority_layers=config.authority_layers,
            sensory_layers=config.sensory_layers,
            alpha_sens_min=config.alpha_sens_initial,
            alpha_sens_max=config.alpha_sens_max,
            warmup_steps=config.gradient_warmup_steps,
            layer_attr="blocks",  # Common attribute name for transformer layers
            # V9.6.8: Layer-wise alpha dampening
            enable_layerwise_alpha=config.enable_layerwise_alpha,
            alpha_output_scale=config.alpha_output_scale,
            alpha_reasoning_scale=config.alpha_reasoning_scale,
            authority_floor=config.authority_floor,
        )
        # Validate layer count matches configuration
        expected_layers = config.authority_layers + config.sensory_layers
        try:
            found_layers = len(gradient_scaler_hgs._get_layers())
            if found_layers < expected_layers:
                print(f"  ⚠️  WARNING: Found {found_layers} layers but 9:3 split expects {expected_layers}")
                print(f"      This may cause incorrect gradient scaling behavior!")
            else:
                print(f"  ✓ Layer count validation passed: {found_layers} layers for {config.authority_layers}:{config.sensory_layers} split")
        except Exception as e:
            print(f"  ⚠️  Could not validate layer count: {e}")

    # Dynamic Relaxation Controller: 9:3 → 6:6 transition
    relaxation_controller = None
    if config.enable_dynamic_relaxation and gradient_scaler_hgs is not None:
        # V9.4.7: Auto-scale saturation_patience based on GPU VRAM
        # Larger VRAM → larger batches → faster convergence → lower patience needed
        # H200 (141GB+): 50 steps | H100 (80GB): 200 steps | A100 (40GB): 400 steps
        auto_saturation_patience = config.saturation_patience  # Default from CLI
        if device.type == "cuda":
            total_vram_gb = torch.cuda.get_device_properties(device).total_memory / 1e9
            if total_vram_gb >= 140:      # H200 class (141GB+)
                auto_saturation_patience = 50
            elif total_vram_gb >= 90:     # 96GB class
                auto_saturation_patience = 100
            elif total_vram_gb >= 70:     # H100/A100-80GB class
                auto_saturation_patience = 200
            elif total_vram_gb >= 35:     # A100-40GB class
                auto_saturation_patience = 400
            else:                          # Smaller GPUs
                auto_saturation_patience = 500

            if auto_saturation_patience != config.saturation_patience:
                print(f"  📊 [VRAM-AUTO] Saturation patience scaled: {config.saturation_patience} → {auto_saturation_patience} (based on {total_vram_gb:.0f}GB VRAM)")

        relaxation_controller = DynamicRelaxationController(
            gradient_scaler=gradient_scaler_hgs,
            model=model,
            stability_threshold=config.relaxation_stability_threshold,
            stability_window=config.relaxation_stability_window,
            streak_target=config.relaxation_streak_target,
            mode=config.relaxation_mode,
            authority_split=(config.authority_layers, config.sensory_layers),
            balanced_split=(config.relaxation_target_authority, config.relaxation_target_sensory),
            authority_alpha_max=config.alpha_sens_max,
            balanced_alpha_max=config.alpha_sens_max,  # Same ceiling for balanced phase
            thaw_alpha_start=config.relaxation_thaw_alpha,
            thaw_warmup_steps=config.relaxation_thaw_steps,
            ppl_spike_threshold=config.relaxation_ppl_spike_threshold,
            recovery_steps=config.relaxation_recovery_steps,
            # Weight Transfer settings
            guna_lock_steps=config.guna_lock_steps,
            enable_weight_transfer=config.enable_weight_transfer,
            # Force relaxation at specific step
            force_relaxation_step=config.force_relaxation_step,
            # Sovereign Saturation Gate
            enable_saturation_gate=config.enable_saturation_gate,
            saturation_coherence_threshold=config.saturation_coherence_threshold,
            saturation_patience=auto_saturation_patience,
            saturation_thaw_start=config.saturation_thaw_start,
            saturation_thaw_end=config.saturation_thaw_end,
            saturation_thaw_steps=config.saturation_thaw_steps,
        )

        # V9.9.1 Configure Multi-Stage Evolution
        if config.enable_multi_stage_evolution:
            relaxation_controller.configure_evolution(
                trigger_mode=config.evolution_trigger_mode,
                ppl_triggers=config.evolution_ppl_triggers,
                step_triggers=config.evolution_step_triggers,
                custom_stages=config.custom_evolution_stages,
                patience=config.evolution_patience,
                coherence_min=config.evolution_coherence_min,
                entropy_floor=config.evolution_entropy_floor,
                ppl_window=config.evolution_ppl_window,
                thaw_alpha=config.evolution_thaw_alpha,
                thaw_steps=config.evolution_thaw_steps,
            )

        # V9.5.1 Force Evolution: Manual intervention to specific stage
        if config.force_evolution_stage is not None:
            target_stage = config.force_evolution_stage
            if 1 <= target_stage <= 4:
                relaxation_controller.current_stage_idx = target_stage
                new_split = relaxation_controller.evolution_stages[target_stage]
                relaxation_controller.current_split = new_split
                relaxation_controller.saturation_triggered = True  # Skip 9:3→6:6 check
                relaxation_controller.state = relaxation_controller.STATE_BALANCED
                print(f"\n  🔧 [FORCE EVOLUTION] Manually set to stage {target_stage}: {new_split[0]}:{new_split[1]}")
                print(f"      Stages: 0=9:3, 1=6:6, 2=5:7, 3=4:8, 4=3:9")

    # V9.9.2 Inverted Layer Curriculum Controller
    # Note: Full initialization happens after seq_len_curriculum is created (see below)
    inverted_layer_curriculum = None
    _enable_inverted_curriculum = config.enable_inverted_curriculum  # Store for later init

    # Adaptive Training Controller (dynamic hyperparameter tuning)
    adaptive_controller = None
    if config.enable_adaptive_training:
        adaptive_controller = AdaptiveTrainingController(
            optimizer=optimizer,
            base_lr=config.learning_rate,
            lr_min=config.adaptive_lr_min,
            lr_max=config.adaptive_lr_max,
            lr_boost_factor=config.adaptive_lr_boost,
            lr_decay_factor=config.adaptive_lr_decay,
            velocity_slow_threshold=config.adaptive_velocity_slow,
            velocity_spike_threshold=config.adaptive_velocity_spike,
            plateau_window=config.adaptive_plateau_window,
            plateau_threshold=config.adaptive_plateau_threshold,
            kp_min=config.pidv2_kp_min,
            kp_max=config.pidv2_kp_max,
            min_steps_between_adjustments=config.adaptive_min_interval,
            # V9.8.2: Safeguards to prevent runaway LR
            max_lr_relative=config.adaptive_max_lr_relative,
            loss_spike_threshold=config.adaptive_loss_spike_threshold,
            grad_norm_spike_threshold=config.adaptive_grad_norm_spike,
            emergency_decay_factor=config.adaptive_emergency_decay,
            consecutive_spike_limit=config.adaptive_consecutive_spike_limit,
            # V10.23: Spike-aware boost dampening
            max_boost_from_base=config.adaptive_max_boost_from_base,
            spike_dampen_threshold=config.adaptive_spike_dampen_threshold,
            boost_cooldown_steps=config.adaptive_boost_cooldown_steps,
        )
        # V9.9.1: Link scheduler to controller so LR boosts/decays persist
        adaptive_controller.set_scheduler(scheduler)
        # V10.23: Link gradient variance tracker for spike-aware boost dampening
        if gradient_variance_tracker is not None:
            adaptive_controller.set_grad_variance_tracker(gradient_variance_tracker)

        # V9.8.3: Immediately enforce LR bounds after checkpoint restore
        # This catches runaway LR from corrupted checkpoint state before training starts
        if config.resume and not config.resume_weights_only:
            current_lr = optimizer.param_groups[0]['lr']
            max_allowed = config.learning_rate * config.adaptive_max_lr_relative
            if current_lr > max_allowed:
                print(f"\n  🚨 [V9.8.3] CHECKPOINT LR OVERRIDE: {current_lr:.2e} → {max_allowed:.2e}")
                print(f"      Restored LR exceeded {config.adaptive_max_lr_relative}x base ({config.learning_rate:.2e})")
                for pg in optimizer.param_groups:
                    pg['lr'] = max_allowed
                adaptive_controller.emergency_count += 1
                adaptive_controller.boost_blocked = True

    # V10.23: Three-phase proportional Slot LR Controller (auto-enabled)
    adaptive_slot_lr = None
    if _slot_params and config.slot_lr_eta > 0:
        # V16.1: Pass coherence floor initial so controller can derive floor from scale
        _coh_floor_init = config.slot_coherence_floor if config.slot_coherence_floor is not None else 0.3
        adaptive_slot_lr = AdaptiveSlotLRController(
            optimizer=optimizer,
            initial_scale=config.slot_memory_lr_scale,
            scale_min=config.slot_lr_scale_min,
            scale_max=config.slot_lr_scale_max,
            eta=config.slot_lr_eta,
            stabilize_after_steps=config.slot_lr_stabilize_after,
            coherence_floor_initial=_coh_floor_init if config.slot_coherence_floor_tied else 0.0,
        )
        print(f"  [V10.23] Slot LR Controller: Phase 1 (until warmup_complete + signal) "
              f"→ Phase 2 (eta={config.slot_lr_eta}, scale=[{config.slot_lr_scale_min}, {config.slot_lr_scale_max}]) "
              f"→ Phase 3 (auto-stabilize)")
        if config.slot_coherence_floor_tied:
            print(f"  [V16.1] Coherence floor tied to slot LR scale (initial={_coh_floor_init})")

    # Restore HGS/DRC state from checkpoint if available
    if resumed_hgs_state is not None and gradient_scaler_hgs is not None:
        try:
            gradient_scaler_hgs.set_state(resumed_hgs_state)
            print(f"    ✓ HGS state restored from checkpoint")
        except Exception as e:
            print(f"    ⚠️  Could not restore HGS state: {e}")

    if resumed_drc_state is not None and relaxation_controller is not None:
        try:
            relaxation_controller.set_state(resumed_drc_state)
            print(f"    ✓ DRC state restored from checkpoint")
        except Exception as e:
            print(f"    ⚠️  Could not restore DRC state: {e}")

    # Restore SGP/Sattvic state from checkpoint if available
    if resumed_sattvic_state is not None and sattvic_controller is not None:
        try:
            sattvic_controller.load_state(resumed_sattvic_state)
        except Exception as e:
            print(f"    ⚠️  Could not restore Sattvic state: {e}")

    if resumed_sgp_state is not None and sgp_controller is not None:
        try:
            sgp_controller.load_state(resumed_sgp_state)
        except Exception as e:
            print(f"    ⚠️  Could not restore SGP state: {e}")

    # V9.8.0: Restore SRK state from checkpoint if available
    if resumed_srk_state is not None and srk is not None:
        try:
            missing, _ = srk.load_checkpoint_state(resumed_srk_state, strict=False)
            if missing:
                print(f"    ℹ️  SRK: Re-initialized {len(missing)} components: {missing[:3]}...")
            else:
                print(f"    ✓ SRK state fully restored")
        except Exception as e:
            print(f"    ⚠️  Could not restore SRK state: {e}")

    # Mixed precision
    scaler = torch.amp.GradScaler('cuda') if config.mixed_precision != "none" else None
    autocast_dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

    # Set autocast dtype on probe hooks (created earlier, before autocast_dtype was available)
    if probe_hooks is not None and config.mixed_precision != "none":
        probe_hooks.autocast_dtype = autocast_dtype
        probe_hooks._use_ac = True

    # V9.8.1: Restore AMP GradScaler state from checkpoint if available
    if resumed_scaler_state is not None and scaler is not None:
        try:
            scaler.load_state_dict(resumed_scaler_state)
            print(f"    ✓ AMP GradScaler state restored from checkpoint")
        except Exception as e:
            print(f"    ⚠️  Could not restore AMP GradScaler state: {e}")

    # Training state (use resume_step if resuming from checkpoint)
    global_step = resume_step
    best_val_loss = best_val_loss if resume_step > 0 else float("inf")
    best_ppl = float("inf")
    spike_count = 0
    train_losses = []
    current_sa_ratio = 0.0  # Track S/A ratio for relaxation controller

    # Save config (ckpt_dir already created above)
    with open(ckpt_dir / "config.json", "w") as f:
        json.dump(asdict(config), f, indent=2)

    # Initialize PIDv2 Controller (V9.4.4)
    authority_controller = None
    if config.controller == "pidv2" and PIDV2_AVAILABLE:
        pidv2_config = AuthorityPIDv2Config(
            Kp_min=config.pidv2_kp_min,
            Kp_max=config.pidv2_kp_max,
            Kp_sensitivity=config.pidv2_kp_sensitivity,
            Ki=config.pidv2_ki,
            Kd=config.pidv2_kd,
            A_min=config.pidv2_a_min,
            C_floor=config.pidv2_c_floor,
            C_good=config.pidv2_c_good,
            W_s=config.pidv2_w_s,
            semantic_ppl_scale=config.pidv2_semantic_scale,
            handshake_Kd_dampen=config.pidv2_handshake_dampen,
            # V9.7.0: Dynamic Batch Sizing
            enable_batch_resize=config.pidv2_batch_resize,
            batch_min=config.pidv2_batch_min,
            batch_max=config.pidv2_batch_max,
            batch_velocity_threshold=config.pidv2_batch_velocity_threshold,
            batch_stable_streak=config.pidv2_batch_stable_streak,
            # V9.8.6: Three-Phase Curriculum
            engage_ppl=config.pidv2_engage_ppl,
            disengage_ppl=config.pidv2_disengage_ppl,
            rampdown_steps=config.pidv2_rampdown_steps,
        )
        authority_controller = AuthorityPIDv2(pidv2_config)
        authority_controller.set_batch_size(config.batch_size)  # Initialize with current batch
        print(f"\n  PIDv2 Governor ENABLED")
        print(f"    Dynamic Kp: [{config.pidv2_kp_min}, {config.pidv2_kp_max}]")
        print(f"    Coherence Gate: C_floor={config.pidv2_c_floor}, C_good={config.pidv2_c_good}")
        print(f"    Semantic Weight (W_s): {config.pidv2_w_s:.0%}")
        print(f"    Authority floor: {config.pidv2_a_min}")
        # V9.8.6: Three-Phase Curriculum info
        print(f"    🎓 Three-Phase Curriculum:")
        print(f"       CONSTRUCTION: PPL > {config.pidv2_engage_ppl} (full PID)")
        print(f"       TRANSITION:   {config.pidv2_disengage_ppl} < PPL < {config.pidv2_engage_ppl} (rampdown)")
        print(f"       POLISHING:    PPL < {config.pidv2_disengage_ppl} (PID off after {config.pidv2_rampdown_steps} steps)")
        # V9.8.6: Restore PIDv2 curriculum state from checkpoint
        if resumed_pidv2_curriculum_state is not None:
            authority_controller.load_curriculum_state(resumed_pidv2_curriculum_state)
            print(f"       ✓ Restored: Phase={authority_controller.phase}, Scale={authority_controller.phase_scale:.3f}")
        if config.pidv2_batch_resize:
            print(f"    🔄 Batch Resize: ENABLED (min={config.pidv2_batch_min}, max={config.pidv2_batch_max})")
            print(f"       Reduce when: PPL vel > {config.pidv2_batch_velocity_threshold}%")
            print(f"       Increase after: {config.pidv2_batch_stable_streak} stable evals")
        # V9.8.7: Three-phase PID engagement
        if config.pidv2_engagement_enabled:
            print(f"    📊 Three-Phase Engagement: ENABLED")
            print(f"       CONSTRUCTION (PID ON):  Val PPL > {config.pidv2_engage_ppl:.1f}")
            print(f"       TRANSITION:             {config.pidv2_disengage_ppl:.1f} < Val PPL < {config.pidv2_engage_ppl:.1f}")
            print(f"       POLISHING (PID OFF):    Val PPL < {config.pidv2_disengage_ppl:.1f}")
    elif config.controller == "emergency_pd" and PIDV2_AVAILABLE:
        pd_config = EmergencyPDConfig(A_min=0.25)
        authority_controller = EmergencyPD(pd_config)
        print(f"\n  Emergency PD Controller ENABLED")
    elif config.controller != "none":
        print(f"\n  Warning: Controller '{config.controller}' not available")

    # V9.4.5: Initialize Friction Controller with Corrective Actions
    friction_controller = None
    # V9.8.10: Support both "hybrid" and "ontological_hybrid" models
    has_hybrid_attention = "hybrid" in config.model_type
    if PIDV2_AVAILABLE and has_hybrid_attention and not config.disable_friction:
        friction_config = FrictionControllerConfig(
            dom_high=config.friction_dom_high,
            dom_low=config.friction_dom_low,
            align_critical=config.friction_align_critical,
        )
        friction_controller = FrictionController(friction_config)
        print(f"\n  V9.4.5: Friction Controller ENABLED")
        print(f"    Alignment thresholds: warn={friction_controller.config.align_warning}, crit={friction_controller.config.align_critical}")
        print(f"    Dominance range: [{friction_controller.config.dom_low}, {friction_controller.config.dom_high}]")
    elif config.disable_friction:
        print(f"\n  V9.4.5: Friction Controller DISABLED (Sanskrit dominance allowed)")

    # V9.5.2 Emergency Stress-Probe configuration display (ChatGPT Guardrails)
    if config.enable_stress_probe:
        print(f"\n  V9.5.2: Emergency Stress-Probe ENABLED (ChatGPT Guardrails)")
        print(f"    Compound Trigger (2 consecutive evals):")
        print(f"      Ent < {config.stress_probe_entropy_trigger} AND (REP-3 > {config.stress_probe_rep3_trigger} OR UTR < {config.stress_probe_utr_trigger} OR DRS > {config.stress_probe_drs_trigger})")
        print(f"    Safety: Coherence > {config.stress_probe_coherence_min} (stiff, not dying)")
        print(f"    Patience: {config.stress_probe_patience} consecutive evals")
        print(f"    Authority Scale: {config.stress_probe_authority_scale} (nearly frozen)")
        print(f"    LR Factor: {config.stress_probe_lr_factor*100:.0f}%")
        print(f"    Duration: {config.stress_probe_min_steps}-{config.stress_probe_max_steps} steps")
        print(f"    Exit: Ent > {config.stress_probe_exit_entropy} for 2 evals AND REP-3 < {config.stress_probe_exit_rep3}")
        print(f"    LR Restore: Gradual over {config.stress_probe_lr_restore_steps} steps")

    if config.force_stress_probe:
        print(f"\n  ⚡ FORCE STRESS-PROBE: Activated at first step")

    # Track previous state for S-drift computation
    previous_state = None
    current_s_drift = 0.0

    # TensorBoard
    tb_writer = None
    if config.tensorboard and TENSORBOARD_AVAILABLE:
        tb_log_dir = ckpt_dir / "logs"
        tb_writer = SummaryWriter(log_dir=str(tb_log_dir))
        print(f"  TensorBoard: {tb_log_dir}")

    # Kosha-Vritti Diagnostic System
    if config.enable_kosha_diagnostics:
        kosha_interval = config.kosha_log_every if config.kosha_log_every > 0 else config.log_every
        print(f"\n  🧭 Sheath-State Diagnostics: ENABLED (every {kosha_interval} steps)")
        print(f"     Axes: Reality (r: +Unmanifest/-Manifest) | Time (t: -Past/+Future)")
        print(f"     Sheaths: Q1=BLISSFUL | Q2=INTELLECTUAL | Q3=MATERIAL | Q4=MENTAL")
        print(f"     States: FACT | ERROR | IMAGINATION | VOID | MEMORY | BALANCED")

    # V9.7.0: Ontological Bridge (Layer 4 - Foundational Structure)
    # Moved BEFORE Kosha: Ontology grounds structure early, Kosha witnesses later
    onto_bridge = None
    if config.enable_onto_bridge:
        # Get hidden_dim from model or preset (not config)
        onto_hidden_dim = (
            getattr(model, 'd_model', None) or
            getattr(getattr(model, 'config', None), 'd_model', None) or
            preset['embed_dim']
        )
        onto_bridge = create_ontological_bridge(hidden_dim=onto_hidden_dim, device=device)
        layer_desc = {4: "Foundational Structure", 2: "Raw Embeddings", 6: "Semantic"}.get(config.onto_bridge_layer, "Custom")
        print(f"\n  🌉 Ontological Bridge: ENABLED (Layer {config.onto_bridge_layer} = {layer_desc})")
        print(f"     12D projection: {onto_hidden_dim}D → 12 Ontological Aspects")
        print(f"     Lambda: {config.onto_bridge_lambda:.2f} | Diversity: {config.onto_bridge_diversity:.2f} | Pramāṇa: {config.onto_bridge_pramana:.2f}")
        print(f"     Aspects: O1-O12 (Potential → Absolving)")
        print(f"     ⚠️  FOUNDATIONAL - establishes ontological DNA early")

    # V9.8.6: Initialize Onto Bridge Three-Phase Curriculum Controller
    onto_curriculum = None
    if config.enable_onto_bridge and onto_bridge is not None:
        onto_curriculum = ThreePhaseCurriculum(
            name="Onto",
            engage_ppl=config.onto_engage_ppl,
            disengage_ppl=config.onto_disengage_ppl,
            rampdown_steps=config.onto_rampdown_steps,
        )
        print(f"  🎓 Onto Three-Phase Curriculum:")
        print(f"       CONSTRUCTION: PPL > {config.onto_engage_ppl} (full ontological grounding)")
        print(f"       TRANSITION:   {config.onto_disengage_ppl} < PPL < {config.onto_engage_ppl} (rampdown)")
        print(f"       POLISHING:    PPL < {config.onto_disengage_ppl} (Onto off after {config.onto_rampdown_steps} steps)")
        # V9.8.6: Restore Onto curriculum state from checkpoint
        if resumed_onto_curriculum_state is not None:
            onto_curriculum.load_state(resumed_onto_curriculum_state)
            print(f"       ✓ Restored: Phase={onto_curriculum.phase}, Scale={onto_curriculum.scale:.3f}")

    # Kosha Phase Steering (Active Intervention) - Layer 9 = O9_WITNESSES
    if config.enable_kosha_steering:
        print(f"\n  🎯 Kosha Phase Steering: ENABLED")
        print(f"     Force: {config.kosha_steering_force:.2f} (0=off, 1=full)")
        print(f"     Warmup: {config.kosha_steering_warmup} steps")
        print(f"     Target: Geometric Truth from atan2(t, r)")
        layer_desc = {9: "O9_WITNESSES (Consciousness)", 4: "Grammar Forming", 2: "Raw Embeddings"}.get(config.kosha_steering_layer, "Custom")
        print(f"     Layer: {config.kosha_steering_layer} ({layer_desc})")
        print(f"     ⚠️  WITNESS POINT - consciousness/awareness alignment")

    # ==========================================================================
    # v2.3.0: Kosha Gyroscope + Vritti Resonance - Homeostatic Self-Regulation
    # Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md
    # ==========================================================================
    kosha_gyroscope = None
    kosha_graduation_monitor = None
    kosha_rip_logger = None
    kosha_curriculum = None  # V9.8.6: Three-Phase Curriculum
    kosha_curriculum_controller = None  # V9.8.6: InvertedCurriculumController
    kosha_graduated = False  # Track graduation state
    vritti_resonance = None  # v2.3.0: Kosha-Vritti Resonance Loss
    # V9.8.7: Three-phase gyroscope engagement tracking
    # Phase 1: CONSTRUCTION (PPL > 50) - Gyroscope OFF
    # Phase 2: REFINEMENT (30 < PPL < 50) - Gyroscope RELAXED
    # Phase 3: POLISHING (PPL < 30) - Gyroscope ACTIVE
    gyroscope_phase = "CONSTRUCTION"  # Current phase

    # V9.8.7: Three-phase PID engagement tracking
    # Phase 1: CONSTRUCTION (PPL > engage_ppl) - PID ON (aggressive correction)
    # Phase 2: TRANSITION (disengage_ppl < PPL < engage_ppl) - PID continues if already on
    # Phase 3: POLISHING (PPL < disengage_ppl) - PID OFF (natural convergence)
    pid_engaged = True  # Start with PID engaged (will check PPL at first eval)
    pid_phase = "CONSTRUCTION"

    if config.enable_kosha_gyroscope and KOSHA_GYROSCOPE_AVAILABLE:
        # Initialize KoshaGyroscopicLoss with Harmonic Pentad (v2.3.0)
        kosha_gyroscope = KoshaGyroscopicLoss(
            # v2.3.0: Complete Harmonic Pentad - Floors and Ceilings
            floor_mental=config.gyroscope_floor_mental,
            ceiling_mental=config.gyroscope_ceiling_mental,
            floor_physical=config.gyroscope_floor_physical,
            ceiling_physical=config.gyroscope_ceiling_physical,
            floor_intellect=config.gyroscope_floor_intellect,
            ceiling_intellect=config.gyroscope_ceiling_intellect,
            floor_vital=config.gyroscope_floor_vital,
            ceiling_vital=config.gyroscope_ceiling_vital,
            floor_bliss=config.gyroscope_floor_bliss,
            ceiling_bliss=config.gyroscope_ceiling_bliss,
            # v2.3.0: Correction factors
            floor_push_factor=config.gyroscope_floor_push_factor,
            ceiling_clamp_factor=config.gyroscope_ceiling_clamp_factor,
            # v2.3.2: Reflexive Domain Morph
            domain_morph_enabled=config.gyroscope_domain_morph_enabled,
            domain_morph_ema_decay=config.gyroscope_domain_morph_ema_decay,
            domain_morph_internal_weight=config.gyroscope_domain_morph_internal_weight,
            domain_morph_external_weight=config.gyroscope_domain_morph_external_weight,
            # Legacy thresholds (backward compatibility)
            trap_threshold=config.gyroscope_trap_threshold,
            gate_threshold=config.gyroscope_gate_threshold,
            balance_target=config.gyroscope_balance_target,
            gate_temperature=config.gyroscope_gate_temperature,
            # v2.2.4: Three-Stage Hybrid Logic (Damping + Gate + Rip)
            damper_steepness=config.gyroscope_damper_steepness,
            gate_steepness=config.gyroscope_gate_steepness,
            rip_multiplier=config.gyroscope_rip_multiplier,
            steepness=config.gyroscope_steepness,  # Legacy, backward compat
            # Dynamic Weight Scheduler (v2.2.1)
            base_gain=config.gyroscope_base_gain,
            max_gain=config.gyroscope_max_gain,
            ppl_ceiling=config.gyroscope_ppl_ceiling,
            target_ppl=config.gyroscope_target_ppl,
            # Refinements (v2.2.0)
            temporal_window=config.gyroscope_temporal_window,
            vital_momentum_enabled=config.gyroscope_vital_momentum,
        ).to(device)

        # Initialize Graduation Monitor (PPL stability check)
        kosha_graduation_monitor = GraduationMonitor(
            target_ppl=config.gyroscope_graduation_ppl,
            stability_window=config.gyroscope_graduation_window,
            variance_threshold=config.gyroscope_graduation_variance,
        )

        # Initialize Inverted Curriculum Controller
        gyro_config = KoshaGyroscopeConfig(
            enable_gyroscope=True,
            gyroscope_disengage_ppl=config.gyroscope_target_ppl,
            gyroscope_warmup_steps=config.gyroscope_warmup_steps,
            gain_rampdown_steps=config.kosha_rampdown_steps,
            # v2.3.0: Complete Harmonic Pentad - Floors and Ceilings
            floor_mental=config.gyroscope_floor_mental,
            ceiling_mental=config.gyroscope_ceiling_mental,
            floor_physical=config.gyroscope_floor_physical,
            ceiling_physical=config.gyroscope_ceiling_physical,
            floor_intellect=config.gyroscope_floor_intellect,
            ceiling_intellect=config.gyroscope_ceiling_intellect,
            floor_vital=config.gyroscope_floor_vital,
            ceiling_vital=config.gyroscope_ceiling_vital,
            floor_bliss=config.gyroscope_floor_bliss,
            ceiling_bliss=config.gyroscope_ceiling_bliss,
            floor_push_factor=config.gyroscope_floor_push_factor,
            ceiling_clamp_factor=config.gyroscope_ceiling_clamp_factor,
            # v2.3.2: Reflexive Domain Morph
            domain_morph_enabled=config.gyroscope_domain_morph_enabled,
            domain_morph_ema_decay=config.gyroscope_domain_morph_ema_decay,
            domain_morph_internal_weight=config.gyroscope_domain_morph_internal_weight,
            domain_morph_external_weight=config.gyroscope_domain_morph_external_weight,
            # Legacy thresholds
            trap_threshold=config.gyroscope_trap_threshold,
            gate_threshold=config.gyroscope_gate_threshold,
            balance_target=config.gyroscope_balance_target,
            # v2.2.4: Three-Stage Hybrid Logic
            damper_steepness=config.gyroscope_damper_steepness,
            gate_steepness=config.gyroscope_gate_steepness,
            rip_multiplier=config.gyroscope_rip_multiplier,
            steepness=config.gyroscope_steepness,  # Legacy
            base_gain=config.gyroscope_base_gain,
            max_gain=config.gyroscope_max_gain,
            ppl_ceiling=config.gyroscope_ppl_ceiling,
            target_ppl=config.gyroscope_target_ppl,
        )
        kosha_curriculum_controller = InvertedCurriculumController(config=gyro_config)
        # V9.8.6: Restore Kosha Gyroscope curriculum controller state from checkpoint
        if resumed_kosha_gyroscope_state is not None:
            kosha_curriculum_controller.load_state(resumed_kosha_gyroscope_state)
            print(f"  ✓ Kosha Gyroscope Restored: graduated={kosha_curriculum_controller.graduated}, disengage_step={kosha_curriculum_controller.disengage_step}")

        # V9.8.6: Three-Phase Kosha Curriculum (unified with CSR/PID pattern)
        kosha_curriculum = ThreePhaseCurriculum(
            name="Kosha",
            engage_ppl=config.kosha_engage_ppl,
            disengage_ppl=config.kosha_disengage_ppl,
            rampdown_steps=config.kosha_rampdown_steps,
        )
        print(f"  🎓 Kosha Three-Phase Curriculum:")
        print(f"       CONSTRUCTION: PPL > {config.kosha_engage_ppl} (full Kosha loss)")
        print(f"       TRANSITION:   {config.kosha_disengage_ppl} < PPL < {config.kosha_engage_ppl} (rampdown)")
        print(f"       POLISHING:    PPL < {config.kosha_disengage_ppl} (Kosha off after {config.kosha_rampdown_steps} steps)")
        # V9.8.6: Restore Kosha curriculum state from checkpoint
        if resumed_kosha_curriculum_state is not None:
            kosha_curriculum.load_state(resumed_kosha_curriculum_state)
            print(f"       ✓ Restored: Phase={kosha_curriculum.phase}, Scale={kosha_curriculum.scale:.3f}")

        # Initialize Reality Rip Logger (diagnostic)
        if config.enable_rip_logger:
            kosha_rip_logger = SovereignDiagnosticLogger(
                log_dir=config.rip_logger_dir,
                mental_threshold=0.8,  # "Insanity" detection threshold
                intellect_threshold=0.2,
            )

        print(f"\n  ╔══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  KOSHA GYROSCOPE v2.3.2: Reflexive Domain Morph                 ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Sattvic Bands (Floor → Ceiling):                               ║")
        print(f"  ║    Mental:    {config.gyroscope_floor_mental:.1%} → {config.gyroscope_ceiling_mental:.1%}  (Spark → Damper)          ║")
        print(f"  ║    Physical:  {config.gyroscope_floor_physical:.1%} → {config.gyroscope_ceiling_physical:.1%}  (Ground → Trap)  ×3-5   ║")
        print(f"  ║    Intellect: {config.gyroscope_floor_intellect:.1%} → {config.gyroscope_ceiling_intellect:.1%}  (Logic → Hubris) ×1.5  ║")
        print(f"  ║    Vital:     {config.gyroscope_floor_vital:.1%} → {config.gyroscope_ceiling_vital:.1%}  (Boost → Brake)          ║")
        print(f"  ║    Bliss:     {config.gyroscope_floor_bliss:.1%} → {config.gyroscope_ceiling_bliss:.1%}  (Spark → Tether)         ║")
        print(f"  ║  Correction: Floor Push×{config.gyroscope_floor_push_factor:.1f} | Ceiling Clamp×{config.gyroscope_ceiling_clamp_factor:.1f}           ║")
        morph_status = "ENABLED" if config.gyroscope_domain_morph_enabled else "DISABLED"
        print(f"  ║  Domain Morph: {morph_status} (EMA:{config.gyroscope_domain_morph_ema_decay:.1f})                       ║")
        print(f"  ║    Internal:{config.gyroscope_domain_morph_internal_weight:.1f} | External:{config.gyroscope_domain_morph_external_weight:.1f} | Phys:38.2→50% | Bliss:61.8→38.2%║")
        print(f"  ║  Dynamic Weight Scheduler:                                       ║")
        print(f"  ║    Base Gain: {config.gyroscope_base_gain:.2f} (PPL > {config.gyroscope_ppl_ceiling:.0f})                                ║")
        print(f"  ║    Max Gain:  {config.gyroscope_max_gain:.2f} (PPL → {config.gyroscope_target_ppl:.0f})                                 ║")
        print(f"  ║  Three-Stage Hybrid Logic (v2.2.4):                             ║")
        print(f"  ║    Damper Steepness: {config.gyroscope_damper_steepness:.1f}  Gate Steepness: {config.gyroscope_gate_steepness:.1f}              ║")
        print(f"  ║    Rip Multiplier: {config.gyroscope_rip_multiplier:.1f} (circuit breaker strength)            ║")
        print(f"  ║  Refinements:                                                    ║")
        print(f"  ║    Temporal Window: {config.gyroscope_temporal_window}  Vital Momentum: {'ON' if config.gyroscope_vital_momentum else 'OFF'}              ║")
        print(f"  ║  Graduation Criteria:                                            ║")
        print(f"  ║    Mean PPL < {config.gyroscope_graduation_ppl:.1f}  AND  σ < {config.gyroscope_graduation_variance:.1f}  (window: {config.gyroscope_graduation_window})          ║")
        if config.enable_rip_logger:
            print(f"  ║  Reality Rip Logger: ENABLED → {config.rip_logger_dir}")
        print(f"  ╚══════════════════════════════════════════════════════════════════╝")

        # v2.3.0: Initialize Vritti Resonance Loss (Phase 2 only - activates at graduation)
        vritti_resonance = VrittiResonanceLoss(
            config=VrittiResonanceConfig(
                resonance_lambda=0.1,       # Weight for resonance loss
                require_graduation=True,     # Only activate after graduation
            )
        ).to(device)
        print(f"  🔱 [VRITTI RESONANCE] Initialized (dormant until graduation)")
        print(f"     Phase 1: Diagnostic logging only (Kosha-Vritti alignment)")
        print(f"     Phase 2: Loss active at λ=0.1 after PPL < {config.gyroscope_graduation_ppl}")

    # v2.3.3: Initialize 32D Sovereign State Regularizer
    state_regularizer = None
    if config.enable_state_regularizer and KOSHA_GYROSCOPE_AVAILABLE:
        state_reg_config = SovereignStateRegularizerConfig(
            anti_saturation_weight=config.state_reg_anti_sat_weight,
            variance_weight=config.state_reg_variance_weight,
            saturation_threshold_high=config.state_reg_sat_thresh_high,
            saturation_threshold_low=config.state_reg_sat_thresh_low,
            target_std_kosha=config.state_reg_target_std_kosha,
            kosha_weights=(
                1.0,  # MATERIAL
                config.state_reg_vital_weight,  # VITAL
                1.0,  # MENTAL
                1.0,  # INTELLECTUAL
                config.state_reg_bliss_weight,  # BLISS
            ),
        )
        state_regularizer = SovereignStateRegularizer(config=state_reg_config).to(device)
        print(f"\n  ╔══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  32D STATE REGULARIZER v2.3.3: Anti-Saturation + VICReg         ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Anti-Saturation: λ={state_reg_config.anti_saturation_weight:.1f}                                      ║")
        print(f"  ║    High threshold: {state_reg_config.saturation_threshold_high:.0%} | Low threshold: {state_reg_config.saturation_threshold_low:.0%}             ║")
        print(f"  ║  Variance Maintenance: λ={state_reg_config.variance_weight:.1f} (target σ={state_reg_config.target_std_kosha:.2f})              ║")
        print(f"  ║  Kosha Weights: MAT×1.0 VIT×{state_reg_config.kosha_weights[1]:.1f} MEN×1.0 INT×1.0 BLI×{state_reg_config.kosha_weights[4]:.1f}  ║")
        print(f"  ║  Target: Prevent Sheath:VIT(100%)>BLI(100%) collapse             ║")
        print(f"  ╚══════════════════════════════════════════════════════════════════╝")

    elif config.enable_kosha_gyroscope and not KOSHA_GYROSCOPE_AVAILABLE:
        print(f"\n  ⚠️  KOSHA GYROSCOPE REQUESTED but module not available!")
        print(f"      Check: symbolu/losses/kosha_gyroscope.py exists and imports correctly")

    print(f"\n{'='*70}")
    print("   STARTING TRAINING")
    print(f"{'='*70}\n", flush=True)

    model.train()

    # V9.9.10/V9.9.12: Phase diversity loss setup
    # Check if adaptive mode (V9.9.12) or fixed mode (V9.9.10) is enabled
    adaptive_phase_diversity = getattr(config, 'enable_adaptive_phase_diversity', False)
    fixed_phase_diversity = (
        hasattr(config, 'phase_diversity_weight') and
        config.phase_diversity_weight > 0
    )
    phase_diversity_enabled = (
        (adaptive_phase_diversity or fixed_phase_diversity) and
        config.model_type in ('phase', 'hybrid', 'ontological_hybrid')
    )

    # Initialize adaptive controller if enabled
    phase_diversity_controller = None
    if phase_diversity_enabled:
        num_phase_layers = enable_phase_diversity_capture(model, enable=True)

        if adaptive_phase_diversity:
            # V9.9.12/V9.9.12b: Adaptive controller (ChatGPT Universal Proposal)
            task_scaling = getattr(config, 'phase_diversity_task_scaling', True)
            task_alpha = getattr(config, 'phase_diversity_task_alpha', 0.01)
            phase_diversity_controller = AdaptivePhaseDiversityController(
                warmup_steps=config.warmup_steps,
                target_R=getattr(config, 'phase_diversity_target_R', 0.25),
                lambda_init=getattr(config, 'phase_diversity_lambda_init', 0.0001),
                lambda_max=getattr(config, 'phase_diversity_lambda_max', 0.1),
                eta=getattr(config, 'phase_diversity_eta', 0.1),
                ramp_multiplier=getattr(config, 'phase_diversity_ramp_multiplier', 5.0),
                task_loss_scaling=task_scaling,
                task_loss_alpha=task_alpha,
            )
            mode_str = "TASK-SCALED" if task_scaling else "R-ADAPTIVE"
            print(f"\n  🌀 [PHASE DIVERSITY V9.9.12] {mode_str} Controller enabled on {num_phase_layers} layers")
            print(f"     ├─ Target R: {phase_diversity_controller.target_R} (mean resultant length)")
            print(f"     ├─ Ramp steps: {phase_diversity_controller.ramp_steps} ({config.phase_diversity_ramp_multiplier}× warmup)")
            if task_scaling:
                print(f"     ├─ Mode: Task-loss scaling (Lagrange multiplier, α={task_alpha})")
                print(f"     └─ λ = α × task_loss × collapse_pressure × ramp (self-normalizing)")
            else:
                print(f"     ├─ λ range: [{phase_diversity_controller.lambda_min:.0e}, {phase_diversity_controller.lambda_max:.0e}]")
                print(f"     └─ Control: λ adapts via exp(η×(R-R_target)), η={phase_diversity_controller.eta}")
        else:
            # V9.9.10: Fixed weight mode
            print(f"\n  🌀 [PHASE DIVERSITY V9.9.10] Fixed mode on {num_phase_layers} layers")
            print(f"     ├─ Weight: {config.phase_diversity_weight} (ramps over {config.phase_diversity_ramp_steps} steps)")
            print(f"     └─ Losses: Uniformity |E[e^{{iφ}}]|² + Entropy Proxy R")

    train_iter = iter(train_loader)
    step_start_time = time.time()
    running_loss = 0.0
    accumulation_step = 0
    _retr_loss_val = None  # V11.3: Init for post-optimizer slot adaptive calls
    _lm_loss_val = 0.0
    _skip_next_step = False  # V9.9.3: Sovereign Reset Protocol - skip step after seq_len transition

    # Toroidal Bridge tracking
    toroidal_coherence = 0.5  # Neutral initial coherence
    toroidal_loss_value = 0.0
    toroidal_seed = None  # Will be populated after first forward pass

    # Training Gunas: Initialize before loop (used by Evolutionary Flow and Metacognitive Tracker)
    guna_s, guna_r, guna_t = 0.33, 0.33, 0.34  # Default balanced state

    # Sensory flow tracking for Saturation Gate (used by DynamicRelaxationController)
    last_sensory_flow = 0.5  # Default value, updated each step from EvoFlow

    # V9.7.0: EvoFlow Fluency Gate - track engagement state
    evo_fluency_engaged = False  # Once True, stays True (no disengagement)
    last_val_ppl = float('inf')  # Track validation PPL for fluency check

    # V11.3: Val PPL Stagnation Detector — reduce auxiliary loss weights
    # when val PPL plateaus, redirecting gradient capacity to CE loss.
    # Tracks last N val PPL values; when no improvement for `patience` evals,
    # scales down SRK non-task lambdas and phase diversity weight.
    _aux_loss_scale = 1.0           # Multiplier for SRK non-task lambdas + phase div
    _val_ppl_best = float('inf')    # Best val PPL seen so far
    _val_ppl_no_improve_count = 0   # Consecutive evals without improvement
    _AUX_STAGNATION_PATIENCE = 5    # Evals without improvement before first reduction
    _AUX_STAGNATION_DECAY = 0.5     # Multiply scale by this each trigger
    _AUX_STAGNATION_FLOOR = 0.05    # Minimum auxiliary loss scale
    _AUX_STAGNATION_IMPROVE_PCT = 0.5  # % improvement needed to reset counter

    # V9.8.0: RSS (Rational Sovereign Sequence) Controller
    rss_controller = None
    if config.enable_rss:
        rss_controller = ResonanceStateScheduler(
            evoflow_ppl_threshold=config.rss_evoflow_ppl,
            toroidal_ppl_threshold=config.rss_toroidal_ppl,
            csr_ppl_threshold=config.rss_csr_ppl,
            kosha_ppl_threshold=config.rss_kosha_ppl,
            csr_warmup_steps=config.rss_csr_warmup_steps,
            use_val_ppl=config.rss_use_val_ppl,
        )
        print(f"\n  👑 [RSS] Rational Sovereign Sequence ENABLED")
        print(f"     ├─ EvoFlow:  PPL < {config.rss_evoflow_ppl}")
        print(f"     ├─ Toroidal: PPL < {config.rss_toroidal_ppl}")
        print(f"     ├─ CSR:      PPL < {config.rss_csr_ppl} (warmup: {config.rss_csr_warmup_steps} steps)")
        print(f"     └─ Kosha:    PPL < {config.rss_kosha_ppl} (after CSR > 50%)")
        print(f"     Using {'validation' if config.rss_use_val_ppl else 'training'} PPL for thresholds\n")

    # PPL-Gated Curriculum Controller
    curriculum_controller = None
    if config.enable_curriculum:
        curriculum_controller = CurriculumController(
            ppl_regularization=config.curriculum_ppl_regularization,
            ppl_grounding=config.curriculum_ppl_grounding,
            ppl_sovereign=config.curriculum_ppl_sovereign,
            stability_window=config.curriculum_stability_window,
            hysteresis=config.curriculum_hysteresis,
        )
        print(f"\n  📚 [CURRICULUM] PPL-Gated Curriculum Learning ENABLED")
        print(f"     Phase Transitions (based on Val PPL):")
        print(f"     ├─ FOUNDATION:     PPL > {config.curriculum_ppl_regularization} (pure cross-entropy)")
        print(f"     ├─ REGULARIZATION: PPL < {config.curriculum_ppl_regularization} (light bhava/coherence)")
        print(f"     ├─ GROUNDING:      PPL < {config.curriculum_ppl_grounding} (CSR + Bridge + JEPA)")
        print(f"     └─ SOVEREIGN:      PPL < {config.curriculum_ppl_sovereign} (full auxiliary stack)")
        print(f"     Stability window: {config.curriculum_stability_window} evals")
        print(f"     Hysteresis: {config.curriculum_hysteresis}x (prevents oscillation)")
        print(f"\n     ⚠️  Starting in FOUNDATION phase - pure LM training")
        print(f"     ⚠️  Auxiliary systems will engage automatically as PPL improves\n")

    # Conscious Generation Curriculum (Phase 5: Stage A→D with PPL-gated progression)
    cg_stage_manager = None
    cg_governance_diag = None
    if config.enable_conscious_generation and config.enable_cg_curriculum:
        try:
            from symbolu_training.training.conscious_generation.curriculum.stages import CurriculumStageManager
            from symbolu_training.training.conscious_generation.diagnostics.governance_diagnostics import GovernanceDiagnostics

            _cg_stage_proportions = tuple(
                float(x) for x in config.cg_curriculum_stage_proportions.split(",")
            )
            if len(_cg_stage_proportions) != 4:
                raise ValueError(
                    f"cg_curriculum_stage_proportions must have 4 values (A,B,C,D), "
                    f"got {len(_cg_stage_proportions)}: {_cg_stage_proportions}"
                )
            _cg_target_lambdas = {
                "lambda_ont": config.lambda_ont,
                "lambda_kosha_routing": config.lambda_kosha_routing,
                "lambda_bliss_token": config.lambda_bliss_token,
                "lambda_plausibility_token": config.lambda_plausibility_token,
                "lambda_csr_token": config.lambda_csr_token,
                "lambda_vritti_token": config.lambda_vritti_token,
                "lambda_guna_token": config.lambda_guna_token,
            }
            cg_stage_manager = CurriculumStageManager(
                target_lambdas=_cg_target_lambdas,
                total_steps=config.max_steps,
                stage_proportions=_cg_stage_proportions,
                ppl_var_threshold=config.cg_curriculum_ppl_var_threshold,
                stability_window=config.cg_curriculum_stability_window,
                ramp_mode=config.cg_curriculum_ramp_mode,
            )
            print(f"\n  [Conscious Gen Phase 5] Staged Curriculum ENABLED")
            print(f"    Stages: A(backbone) -> B(ontology) -> C(primitives) -> D(integrated)")
            print(f"    Proportions: {_cg_stage_proportions}")
            print(f"    Ramp mode: {config.cg_curriculum_ramp_mode}")
            print(f"    PPL var threshold: {config.cg_curriculum_ppl_var_threshold}")

            # Restore CG Stage Manager state from checkpoint
            if resumed_cg_stage_manager_state is not None:
                cg_stage_manager.load_state(resumed_cg_stage_manager_state)
                print(f"  ✓ CG Stage Manager Restored: Stage={cg_stage_manager.current_stage}, "
                      f"FieldIntegrated={cg_stage_manager._field_integrated_active}")

            if config.enable_cg_diagnostics:
                cg_governance_diag = GovernanceDiagnostics(
                    window_size=100,
                    enable_sensitivity_probes=getattr(config, 'enable_governance_probes', False),
                )
                print(f"    Governance diagnostics: ENABLED (probes={'ON' if getattr(config, 'enable_governance_probes', False) else 'OFF'})")
        except ImportError as e:
            print(f"  [Conscious Gen Phase 5] Curriculum import failed: {e}")

    # Embedding Diagnostics — verify CG auxiliaries are changing representations
    cg_embedding_diag = None
    if config.enable_conscious_generation and config.enable_embedding_diagnostics:
        try:
            from symbolu_training.training.conscious_generation.diagnostics.embedding_diagnostics import EmbeddingDiagnostics
            cg_embedding_diag = EmbeddingDiagnostics(
                interval=config.embedding_diag_interval,
                vocab_sample_size=config.embedding_diag_vocab_sample,
                neighbor_k=config.embedding_diag_neighbors,
                no_samples=config.embedding_diag_no_samples,
                start_step=config.embedding_diag_start_step,
            )
            print(f"\n  [Embedding Diagnostics] ENABLED")
            print(f"    Snapshot interval: every {config.embedding_diag_interval} steps")
            if config.embedding_diag_no_samples:
                print(f"    Vocab sampling: DISABLED (grad norms + adapter gate only)")
            else:
                print(f"    Vocab sample: {config.embedding_diag_vocab_sample} tokens")
                print(f"    Neighbor tracking: top-{config.embedding_diag_neighbors}")
            if config.embedding_diag_start_step > 0:
                print(f"    Start step: {config.embedding_diag_start_step} (dormant until then)")
        except ImportError as e:
            print(f"  [Embedding Diagnostics] Import failed: {e}")

    # Stage 7B: Adaptive Diagnostic Controller — threshold-based responses
    cg_adaptive_diag_controller = None
    if cg_embedding_diag is not None:
        try:
            from symbolu_training.training.conscious_generation.diagnostics.adaptive_diagnostic_controller import (
                AdaptiveDiagnosticController,
            )
            cg_adaptive_diag_controller = AdaptiveDiagnosticController()
            print(f"  [Adaptive Diagnostics] ENABLED (Stage 7B)")
        except ImportError as e:
            print(f"  [Adaptive Diagnostics] Import failed: {e}")

    # Factual Eval — verify CG primitives distinguish facts from hallucinations
    cg_factual_eval = None
    if config.enable_conscious_generation and config.enable_factual_eval:
        try:
            from symbolu_training.training.conscious_generation.diagnostics.factual_eval import FactualEval
            cg_factual_eval = FactualEval(
                interval=config.factual_eval_interval,
                num_probes=config.factual_eval_probes,
                start_step=config.factual_eval_start_step,
            )
            print(f"\n  [Factual Eval] ENABLED")
            print(f"    Eval interval: every {config.factual_eval_interval} steps")
            print(f"    Probe pairs: {cg_factual_eval.num_probes} (fact vs hallucination)")
            if config.factual_eval_start_step > 0:
                print(f"    Start step: {config.factual_eval_start_step}")
        except ImportError as e:
            print(f"  [Factual Eval] Import failed: {e}")

    # Appendix F Stage 0: Binding Cache + CTM+ Generation Tracer
    generation_tracer = None
    if config.model_type == "mistral_cg" and (
        config.enable_binding_cache_tracer or config.enable_ctm_plus_tracer
    ):
        try:
            from agentic.inference.generation_tracer import MistralCGGenerationTracer
            generation_tracer = MistralCGGenerationTracer(
                model=model,
                binding_cache_top_k=config.binding_cache_top_k,
                ctm_num_layers=config.ctm_plus_num_layers,
                ctm_gpu_budget=config.ctm_plus_gpu_budget,
            )
            print(f"\n  [Stage 0 Tracer] ENABLED — Observation only, no generation modification")
            if config.enable_binding_cache_tracer:
                print(f"    Binding Cache: top_k={config.binding_cache_top_k}, "
                      f"confidence_threshold={config.binding_cache_confidence_threshold}")
            if config.enable_ctm_plus_tracer:
                print(f"    CTM+: gpu_budget={config.ctm_plus_gpu_budget}/{config.ctm_plus_num_layers} layers")
            print(f"    Trace output: {config.generation_trace_output}")
            print(f"    Snapshot interval: every {config.generation_trace_interval} steps")
        except ImportError as e:
            print(f"  [Stage 0 Tracer] Import failed: {e}")

    # Experiential Controller (training-time plasticity modulation)
    experiential_controller = None
    if config.enable_experiential_controller:
        try:
            from symbolu_training.training.conscious_generation.experiential.minimal_controller import (
                ExperientialController,
                ExperientialControllerConfig,
            )
            _exp_cfg = ExperientialControllerConfig(
                d_model=config.experiential_d_model,
                num_regions=config.experiential_num_regions,
                lambda_temporal=config.experiential_lambda_temporal,
                lambda_coherence=config.experiential_lambda_coherence,
                lambda_latent=config.experiential_lambda_latent,
                k_r=config.experiential_k_r,
                k_m=config.experiential_k_m,
                b_p=config.experiential_b_p,
                G_base=config.experiential_G_base,
                G_min=config.experiential_G_min,
                G_max=config.experiential_G_max,
                k_dv=config.experiential_k_dv,
                k_dc=config.experiential_k_dc,
                alpha_base=config.experiential_alpha_base,
            )
            experiential_controller = ExperientialController(_exp_cfg).to(device)

            # Add controller's learnable projections to optimizer
            _exp_params = list(experiential_controller.parameters())
            _exp_param_count = sum(p.numel() for p in _exp_params)
            if _exp_params:
                optimizer.add_param_group({
                    'params': _exp_params,
                    'lr': config.learning_rate,
                    'weight_decay': 0.01,
                })

            print(f"\n  [Experiential Controller] ENABLED — 12-parameter plasticity modulation")
            print(f"    d_model={_exp_cfg.d_model}, regions={_exp_cfg.num_regions}, "
                  f"learnable params={_exp_param_count:,}")
            print(f"    Loss weights: λ_temp={_exp_cfg.lambda_temporal}, "
                  f"λ_coh={_exp_cfg.lambda_coherence}, λ_lat={_exp_cfg.lambda_latent}")
            print(f"    Plasticity: k_r={_exp_cfg.k_r}, k_m={_exp_cfg.k_m}, b_p={_exp_cfg.b_p}")
            print(f"    Gain: G_base={_exp_cfg.G_base}, G_min={_exp_cfg.G_min}, G_max={_exp_cfg.G_max}")
            print(f"    Damping: k_dv={_exp_cfg.k_dv}, k_dc={_exp_cfg.k_dc}")
            print(f"    Identity: α_base={_exp_cfg.alpha_base}")
            print(f"    Loops: replay every {config.experiential_replay_interval}, "
                  f"consolidation every {config.experiential_consolidation_interval}")

            # Restore from checkpoint if available
            if resumed_experiential_controller_state is not None:
                experiential_controller.load_full_state(
                    resumed_experiential_controller_state, device=device
                )
                _restored_step = experiential_controller.step.item()
                print(f"    ✓ Experiential Controller restored from checkpoint (step {_restored_step})")
            elif resume_step > 0:
                print(f"    ⚠ Experiential Controller initialized fresh (no state in checkpoint)")
                print(f"      Loss warmup will ramp from 0 over {config.experiential_warmup_steps} steps")
        except ImportError as e:
            print(f"  [Experiential Controller] Import failed: {e}")

    # PPL-Gated Alpha Curriculum (phase dominates early, local refines later)
    ppl_alpha_curriculum = None
    if config.enable_ppl_alpha_curriculum:
        ppl_alpha_curriculum = PPLAlphaCurriculum(
            alpha_high=config.alpha_phase_ppl_high,
            alpha_low=config.alpha_phase_ppl_low,
            ppl_high=config.ppl_high_threshold,
            ppl_low=config.ppl_low_threshold,
            enable_adaptive_window=config.enable_adaptive_window,
            window_size_high_ppl=config.window_size_high_ppl,
            window_size_low_ppl=config.window_size_low_ppl,
            enable_adaptive_alpha=config.enable_adaptive_alpha,
            adaptive_alpha_min=config.adaptive_alpha_min,
            adaptive_alpha_max=config.adaptive_alpha_max,
        )
        print(f"\n  🔄 [PPL-Window] Adaptive Window Curriculum ENABLED (alpha values are DIAGNOSTIC ONLY — not used in Protected Phase mode)")
        print(f"     ├─ PPL >= {config.ppl_high_threshold:.0f}: window={config.window_size_high_ppl} (α_phase={config.alpha_phase_ppl_high:.2f} diagnostic)")
        print(f"     ├─ PPL <= {config.ppl_low_threshold:.0f}:  window={config.window_size_low_ppl} (α_phase={config.alpha_phase_ppl_low:.2f} diagnostic)")
        print(f"     └─ NOTE: In Protected Phase mode, α does NOT gate outputs. Gradient flow via architecture + aux losses.")
        if config.enable_adaptive_window:
            print(f"     📐 Adaptive Window: {config.window_size_high_ppl} (high PPL) → {config.window_size_low_ppl} (low PPL)")
        if config.enable_adaptive_alpha:
            print(f"     🎛️  Adaptive Alpha: ENABLED (post-curriculum, ablation-driven)")
            print(f"        α_phase bounds: [{config.adaptive_alpha_min:.2f}, {config.adaptive_alpha_max:.2f}]")
            print(f"        Dead zone: -0.5% to +1.0% (hysteresis)")
        print()

    # V2.3.4: Sequence Length Curriculum Controller
    seq_len_curriculum = None
    current_seq_len = config.max_seq_len
    seq_curriculum_ref_batch = config.batch_size  # Reference batch size at probed seq_len
    seq_curriculum_ref_seq_len = getattr(config, 'auto_batch_probed_seq_len', config.max_seq_len)  # Probed reference
    if config.enable_seq_curriculum:
        seq_len_curriculum = SequenceLengthCurriculum(
            seq_len_start=config.seq_len_start,
            seq_len_end=config.seq_len_end,
            ramp_steps=config.seq_len_ramp_steps,
            ramp_mode=config.seq_len_ramp_mode,
            ppl_gate=config.seq_len_ppl_gate,
        )
        current_seq_len = config.seq_len_start  # Start with short sequences

        # V9.8.10: Calculate scaled batch size for initial short sequence length
        # AutoBatchSizer already probed at seq_len_start, so use that as reference
        # Memory scales ~linearly with seq_len, so batch can scale inversely
        seq_curriculum_ref_batch = config.batch_size  # Probed at seq_len_start
        seq_curriculum_ref_seq_len = getattr(config, 'auto_batch_probed_seq_len', config.seq_len_start)
        # If we're at the probed length, use probed batch directly (no scaling needed)
        if current_seq_len == seq_curriculum_ref_seq_len:
            scaled_batch = seq_curriculum_ref_batch
        else:
            # Scale inversely with sequence length (longer seq = smaller batch)
            scaled_batch = int(seq_curriculum_ref_batch * (seq_curriculum_ref_seq_len / current_seq_len))
            scaled_batch = min(scaled_batch, config.batch_size_max)  # Cap at configurable max
        config.batch_size = scaled_batch

        print(f"\n  📏 [SEQ CURRICULUM] Sequence Length Curriculum ENABLED")
        print(f"     Ramping: {config.seq_len_start} → {config.seq_len_end} tokens")
        print(f"     Ramp steps: {config.seq_len_ramp_steps}")
        print(f"     Mode: {config.seq_len_ramp_mode.upper()}")
        print(f"     Probed batch: {seq_curriculum_ref_batch} @ {seq_curriculum_ref_seq_len}tok (AutoBatchSizer)")
        print(f"     Starting batch: {scaled_batch} @ {current_seq_len}tok (max: {config.batch_size_max})")
        if config.seq_len_ppl_gate > 0:
            print(f"     PPL Gate: Only ramp when PPL < {config.seq_len_ppl_gate}")
        print(f"\n     ✅ Starting with {current_seq_len}-token sequences (batch={scaled_batch})")
        print(f"     📈 Batch will scale DOWN as sequences lengthen (memory-adaptive)\n")

        # Reload data with initial short sequence length and scaled batch
        train_loader, val_loader = load_data(config, tokenizer, seq_len_override=current_seq_len)
        train_iter = iter(train_loader)
        seq_len_curriculum.mark_data_reloaded()

    # V9.9.2: Initialize Inverted Layer Curriculum with seq_len delegation
    if _enable_inverted_curriculum:
        inverted_layer_curriculum = InvertedLayerCurriculumController.from_config(
            config,
            seq_len_curriculum=seq_len_curriculum,  # Delegate seq_len to SequenceLengthCurriculum
        )
        # Apply initial per-layer weights to model
        inverted_layer_curriculum.apply_to_model(model)

        # V9.9.3: CRITICAL - Reconfigure HGS to match inverted curriculum's initial split!
        # Without this, HGS would use config's 9:3 while model is actually 3:9
        if gradient_scaler_hgs is not None:
            init_auth, init_sens = inverted_layer_curriculum.current_split
            gradient_scaler_hgs.reconfigure(
                new_authority_layers=init_auth,
                new_sensory_layers=init_sens,
                alpha_range=(config.alpha_sens_initial, config.alpha_sens_max),
                new_warmup_steps=config.gradient_warmup_steps,
            )
            print(f"  🔧 [HGS] Synchronized with inverted curriculum: {init_auth}:{init_sens} split")

        print(f"\n  🎓 [INVERTED CURRICULUM] Controller enabled (V9.9.3)")
        print(f"      Initial split: {inverted_layer_curriculum.current_split[0]}:{inverted_layer_curriculum.current_split[1]}")
        status = inverted_layer_curriculum.get_status()
        print(f"      Seq len mode: {status['seq_len_mode']} ({status['seq_len']} tokens)")

    # =========================================================================
    # V10.2.1: Run Chunk Continuity Diagnostic (if requested)
    # =========================================================================
    if config.run_chunk_diagnostic and config.model_type == "hybrid":
        print(f"\n  🔍 [CHUNK DIAGNOSTIC] Running chunk continuity diagnostic...")
        print(f"      Test sequence length: {config.chunk_diagnostic_seq_len}")
        print(f"      Chunk size: {config.chunk_size}")
        try:
            # Create test input
            test_ids = torch.randint(
                0, config.vocab_size,
                (1, config.chunk_diagnostic_seq_len),
                device=device
            )
            # Run diagnostic
            diag_result = model.diagnose_chunk_continuity(
                test_ids,
                chunk_size=config.chunk_size,
                verbose=True
            )
            if not diag_result['healthy']:
                print(f"\n  ⚠️  [CHUNK DIAGNOSTIC] WARNING: Chunk continuity issues detected!")
                print(f"      Check the diagnostic output above for details.")
                print(f"      Training will continue, but chunking may not work correctly.\n")
            else:
                print(f"\n  ✅ [CHUNK DIAGNOSTIC] All checks passed - chunking is healthy!\n")
        except Exception as e:
            print(f"\n  ❌ [CHUNK DIAGNOSTIC] Failed to run diagnostic: {e}")
            print(f"      Training will continue without diagnostic validation.\n")

    # ==========================================================================
    # BCVF Contrastive Structural Pressure — Initialization
    # ==========================================================================
    bcvf_contrastive_head = None
    bcvf_contrastive_sampler = None
    bcvf_contrastive_config = None
    bcvf_hidden_hook = None

    if config.use_bcvf_contrastive and BCVF_CONTRASTIVE_AVAILABLE:
        # Determine model hidden dimension
        _bcvf_embed_dim = getattr(config, 'n_embd', None) or MODEL_PRESETS.get(config.model_size, {}).get('embed_dim', 512)

        bcvf_contrastive_config = BCVFContrastiveConfig(
            use_bcvf_contrastive=True,
            lambda_rep=config.bcvf_contrastive_lambda,
            K=config.bcvf_contrastive_K,
            K_pool=min(config.bcvf_contrastive_K_pool, config.vocab_size),
            margin=config.bcvf_contrastive_margin,
            alpha=config.bcvf_contrastive_alpha,
            eta=config.bcvf_contrastive_eta,
            d_r=config.bcvf_contrastive_d_r,
            T_sample=config.bcvf_contrastive_T_sample,
            projector_type=config.bcvf_contrastive_projector,
        )

        bcvf_contrastive_head = BCVFContrastiveHead(
            hidden_dim=_bcvf_embed_dim,
            proj_dim=bcvf_contrastive_config.d_r,
            projector_type=bcvf_contrastive_config.projector_type,
        ).to(device)

        # Add contrastive head params to optimizer
        optimizer.add_param_group({
            'params': bcvf_contrastive_head.parameters(),
            'lr': config.learning_rate,
            'weight_decay': 0.01,
        })

        bcvf_contrastive_sampler = BCVFNegativeSampler(
            K=bcvf_contrastive_config.K,
            K_pool=bcvf_contrastive_config.K_pool,
            top_p=bcvf_contrastive_config.top_p,
        )

        # Register hidden state capture hook
        bcvf_hidden_hook = HiddenStateCaptureHook()
        hook_ok = bcvf_hidden_hook.register(model)

        print(f"\n  [BCVF-REP] Contrastive Structural Pressure ENABLED")
        print(f"     lambda_rep={bcvf_contrastive_config.lambda_rep}, "
              f"K={bcvf_contrastive_config.K}, "
              f"margin={bcvf_contrastive_config.margin}")
        print(f"     d_r={bcvf_contrastive_config.d_r}, "
              f"T_sample={bcvf_contrastive_config.T_sample}, "
              f"projector={bcvf_contrastive_config.projector_type}")
        print(f"     Hidden hook registered: {hook_ok}")
        print(f"     Head params: {sum(p.numel() for p in bcvf_contrastive_head.parameters()):,}")

    elif config.use_bcvf_contrastive and not BCVF_CONTRASTIVE_AVAILABLE:
        print("  [BCVF-REP] WARNING: use_bcvf_contrastive=True but module not available")

    # ==========================================================================
    # BCVF Logit-Margin + Entropy Band — Initialization
    # ==========================================================================
    logit_margin_config = None

    if config.use_logit_margin and BCVF_LOGIT_MARGIN_AVAILABLE:
        logit_margin_config = LogitMarginConfig(
            use_logit_margin=True,
            lambda_margin=config.logit_margin_lambda,
            lambda_entropy=config.logit_margin_entropy_lambda,
            margin=config.logit_margin_m,
            H_min=config.logit_margin_H_min,
            H_max=config.logit_margin_H_max,
            top_k_neg=config.logit_margin_top_k_neg,
        )
        print(f"\n  [BCVF-LM] Logit-Margin + Entropy Band ENABLED")
        print(f"     lambda_m={logit_margin_config.lambda_margin}, "
              f"lambda_H={logit_margin_config.lambda_entropy}, "
              f"margin={logit_margin_config.margin}")
        print(f"     H_band=[{logit_margin_config.H_min}, {logit_margin_config.H_max}], "
              f"top_k_neg={logit_margin_config.top_k_neg}")

    elif config.use_logit_margin and not BCVF_LOGIT_MARGIN_AVAILABLE:
        print("  [BCVF-LM] WARNING: use_logit_margin=True but module not available")

    # ==========================================================================
    # KOSHA-VRITTI STRUCTURED SUPERVISION Initialization
    # Reference: symbolu/training/kosha_vritti_supervision.py
    # ==========================================================================
    kv_supervisor = None

    if config.enable_kv_supervision and KV_SUPERVISION_AVAILABLE:
        # Determine hidden dimension from model preset
        _kv_embed_dim = (
            config.n_embd if config.n_embd is not None
            else MODEL_PRESETS.get(config.model_size, {}).get('embed_dim', 512)
        )

        kv_config = KoshaVrittiSupervisionConfig(
            enable=True,
            weight_kosha_kl=config.kv_weight_kosha_kl,
            weight_vritti_kl=config.kv_weight_vritti_kl,
            weight_entropy_floor=config.kv_weight_entropy_floor,
            weight_compatibility=config.kv_weight_compatibility,
            weight_prior=config.kv_weight_prior,
            entropy_floor_ratio=config.kv_entropy_floor_ratio,
            compatibility_prior_path=config.kv_compatibility_prior_path or None,
            curriculum_exclude_epochs=config.kv_curriculum_exclude_epochs,
            curriculum_ramp_epochs=config.kv_curriculum_ramp_epochs,
            default_kosha_dist=config.kv_teacher_mode,
            default_vritti_dist=config.kv_teacher_mode,
            collapse_check_interval=config.kv_collapse_check_interval,
            kl_clamp_max=config.kv_kl_clamp_max,
        )

        kv_supervisor = KoshaVrittiSupervisor(
            config=kv_config,
            hidden_dim=_kv_embed_dim,
            device=device,
            tokenizer=tokenizer if 'tokenizer' in dir() else None,
        )

        # Add KV supervisor params to optimizer
        optimizer.add_param_group({
            'params': list(kv_supervisor.parameters()),
            'lr': config.learning_rate,
            'weight_decay': 0.01,
        })

        kv_param_count = sum(p.numel() for p in kv_supervisor.parameters())
        print(f"\n  [KV-SUPERVISION] Kosha-Vritti Structured Supervision ENABLED")
        print(f"     Kosha: 4 classes | Vritti: 5 classes | Params: {kv_param_count:,}")
        print(f"     Weights: KL(K)={config.kv_weight_kosha_kl} KL(V)={config.kv_weight_vritti_kl} "
              f"H={config.kv_weight_entropy_floor} Compat={config.kv_weight_compatibility}")
        print(f"     Curriculum: exclude={config.kv_curriculum_exclude_epochs} epochs, "
              f"ramp={config.kv_curriculum_ramp_epochs} epochs")
        print(f"     Teacher: {config.kv_teacher_mode} | Entropy floor: {config.kv_entropy_floor_ratio}")

    elif config.enable_kv_supervision and not KV_SUPERVISION_AVAILABLE:
        print("  [KV-SUPERVISION] WARNING: enable_kv_supervision=True but module not available")

    # Restore KV Supervision state from checkpoint
    if kv_supervisor is not None and resumed_kv_supervisor_state is not None:
        kv_supervisor.load_state_dict(resumed_kv_supervisor_state)
        print(f"  ✓ KV Supervision state restored from checkpoint")

    # Phase 4: Restore JEPA injection projector state
    if jepa_injection_projector is not None and resumed_jepa_injection_projector_state is not None:
        jepa_injection_projector.load_state_dict(resumed_jepa_injection_projector_state)
        print(f"  ✓ JEPA injection projector restored from checkpoint")

    # V10.7.1: Track first iteration for diagnostic logging (works with resumed training)
    _first_iter_logged = False
    _mem_baseline = 0.0  # V10.7.1: Memory baseline for first-iter diagnostics

    while global_step < config.max_steps:
        # V9.9.3: Sovereign Reset Protocol - skip one step after seq_len transition
        # This allows VRAM to stabilize after memory reallocation
        if _skip_next_step:
            print(f"  ⏭️  [SOVEREIGN RESET] Skipping step {global_step} for VRAM stabilization")
            _skip_next_step = False
            # Still need to get a batch to advance the iterator
            try:
                _ = next(train_iter)
            except StopIteration:
                train_iter = iter(train_loader)
                _ = next(train_iter)
            continue

        # Get batch
        try:
            batch = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch = next(train_iter)

        # Handle different batch formats (tuple for WikiText, dict for FineWeb)
        if isinstance(batch, dict):
            x = batch["input_ids"].to(device)
            y = batch["labels"].to(device)
        else:
            x, y = batch
            x, y = x.to(device), y.to(device)

        # Forward pass
        # Clear hidden state extractor before forward pass so hooks capture fresh states
        if 'hidden_state_extractor' in dir() and hidden_state_extractor is not None:
            hidden_state_extractor.clear()

        with torch.amp.autocast('cuda', dtype=autocast_dtype):
            # V9.9.6: Initialize decorr variables before model-type branching
            # These may be set by hybrid/ontological_hybrid and used later by SRK
            enable_decorr = False
            decorr_loss_tensor = None
            ortho_loss_tensor = None
            # V9.9.12c: Phase diversity loss tensor for re-adding after SRK
            phase_div_loss_tensor = None
            phase_div_weight_for_srk = 0.0
            # V10.7: TBPTT backward tracking
            tbptt_backward_done = False

            if config.model_type == "ontological":
                outputs = model(x)
                # Extract logits for downstream consumers (SRK, KV supervision, etc.)
                logits = outputs.get('logits', outputs.get('output'))
                # Extract phase angles if available (for U1/U2 coherence)
                phase_angles = outputs.get('phase_angles', None)
                loss, metrics = compute_ontological_loss(
                    outputs, y, config,
                    sovereign_loss=sovereign_loss,
                    sovereign_engine=sovereign_engine,
                    phase_angles=phase_angles,
                    epoch=global_step // len(train_loader),
                )
                # Entropy control for ontological models
                if entropy_scale_module is not None:
                    onto_logits = logits
                    if onto_logits is not None:
                        scaled_onto_logits = entropy_scale_module(onto_logits)
                        loss, ec_metrics = entropy_scale_module.compute_loss(scaled_onto_logits, loss)
                        metrics.update({f'ec_{k}': v for k, v in ec_metrics.items() if isinstance(v, (int, float))})
            elif config.model_type == "gen2":
                outputs = model(x, labels=y)
                logits = outputs.get('logits', outputs.get('output'))
                loss = outputs['loss']
                metrics = {
                    'coherence': outputs['coherence'].mean().item(),
                    'level_1_coh': outputs['level_coherences'][:, 0].mean().item(),
                    'level_2_coh': outputs['level_coherences'][:, 1].mean().item(),
                    'level_3_coh': outputs['level_coherences'][:, 2].mean().item(),
                }
            else:
                # Phase or Hybrid - handle both tensor and dict returns
                # Enable decorrelation loss for hybrid/ontological_hybrid models

                # DEBUG: Diagnose decorr_loss_weight issue
                if global_step == 1:
                    has_attr = hasattr(config, 'decorr_loss_weight')
                    decorr_val = getattr(config, 'decorr_loss_weight', 'NOT_FOUND')
                    model_type = config.model_type
                    is_valid_type = model_type in ('hybrid', 'ontological_hybrid')
                    print(f"DEBUG CONFIG: hasattr={has_attr}, value={decorr_val}, "
                          f"model_type={model_type}, is_valid_type={is_valid_type}")

                enable_decorr = (
                    hasattr(config, 'decorr_loss_weight') and
                    config.decorr_loss_weight > 0 and
                    config.model_type in ('hybrid', 'ontological_hybrid', 'mistral_hybrid')
                )

                # V10.2.2: Chunked training for long sequences
                # When enable_chunking is True, process sequence in chunks
                # Phase state persists across chunks, Local resets per chunk
                _has_chunking_attr = hasattr(config, 'enable_chunking')
                _chunking_or_tbptt = (config.enable_chunking or getattr(config, 'enable_tbptt', False)) if _has_chunking_attr else False
                _is_hybrid = config.model_type == 'hybrid'
                _seq_exceeds_chunk = x.shape[1] > config.chunk_size
                use_chunking = _has_chunking_attr and _chunking_or_tbptt and _is_hybrid and _seq_exceeds_chunk

                # V10.7.1: Log chunking decision on first iteration (works with resumed training)
                if not _first_iter_logged and accumulation_step == 0:
                    _tbptt_requested = getattr(config, 'enable_tbptt', False)
                    print(f"  [CHUNK DEBUG] enable_chunking={getattr(config, 'enable_chunking', 'N/A')}, "
                          f"enable_tbptt={_tbptt_requested}, model_type={config.model_type}, "
                          f"seq_len={x.shape[1]}, chunk_size={config.chunk_size}, "
                          f"use_chunking={use_chunking}")

                # V10.7: TBPTT flag — backward happens inside forward_chunked_tbptt
                tbptt_backward_done = False

                if use_chunking and getattr(config, 'enable_tbptt', False):
                    # V10.7: TBPTT chunked training — forward+backward per chunk
                    # Memory: O(C) instead of O(N). Backward is done inside.
                    if not _first_iter_logged and accumulation_step == 0:
                        print(f"  [TBPTT] ACTIVE: seq={x.shape[1]}, chunk={config.chunk_size}, "
                              f"chunks={((x.shape[1] + config.chunk_size - 1) // config.chunk_size)}")
                    if device.type == 'cuda':
                        _mem_baseline = torch.cuda.memory_allocated() / (1024**3)
                        torch.cuda.reset_peak_memory_stats()
                    # V10.14.10: Build aux_loss_fn for slot retrieval loss in TBPTT
                    _tbptt_aux_loss_fn = None
                    if config.global_tokens_enabled and config.global_update_mode == "slots":
                        _tbptt_sm = getattr(model, 'slot_memory', None)
                        if _tbptt_sm is None:
                            _tbptt_inner = getattr(model, 'hybrid', model)
                            _tbptt_sm = getattr(_tbptt_inner, 'slot_memory', None)
                        _tbptt_lm_head = getattr(model, 'lm_head', None)
                        if _tbptt_lm_head is None:
                            _tbptt_inner = getattr(model, 'hybrid', model)
                            _tbptt_lm_head = getattr(_tbptt_inner, 'lm_head', None)
                        if _tbptt_sm is not None and _tbptt_lm_head is not None:
                            def _tbptt_aux_loss_fn(result_dict, chunk_targets,
                                                   _sm=_tbptt_sm, _lm=_tbptt_lm_head,
                                                   _cfg=config):
                                _sk = result_dict.get('_slot_keys')
                                _sv = result_dict.get('_slot_vals')
                                _sh = result_dict.get('_slot_hidden')
                                if _sk is None or _sv is None or _sh is None:
                                    return None
                                # Router loss
                                _aux = _sm.compute_sharpness_loss()
                                # V10.21: Densified retrieval supervision (half-window threshold)
                                _valid = (chunk_targets != -100)
                                _B, _N = chunk_targets.shape
                                _win = getattr(_cfg, 'window_size', 0)
                                _retr_start = max(_win // 2, 1)
                                if _retr_start > 0 and _N > _retr_start:
                                    _pos_mask = torch.zeros(_B, _N, dtype=torch.bool,
                                                            device=chunk_targets.device)
                                    _pos_mask[:, _retr_start:] = True
                                    _qmask = _valid & _pos_mask
                                else:
                                    _qmask = _valid
                                _retr = _sm.compute_retrieval_loss(
                                    x=_sh, slot_keys=_sk, slot_vals=_sv,
                                    query_mask=_qmask, target_ids=chunk_targets,
                                    lm_head=_lm,
                                )
                                # V11.4: Slot-only prediction loss (TBPTT path)
                                _slot_pred = torch.tensor(0.0, device=_sh.device)
                                if _cfg.slot_prediction_loss_weight > 0:
                                    _slot_pred = _sm.compute_slot_prediction_loss(
                                        x=_sh, slot_keys=_sk, slot_vals=_sv,
                                        query_mask=_qmask, target_ids=chunk_targets,
                                    )
                                _sm._router_step += 1
                                _sm.maybe_unfreeze_read_gate()
                                return (_aux + _cfg.retrieval_loss_weight * _retr
                                        + _cfg.slot_prediction_loss_weight * _slot_pred)

                    tbptt_result = forward_chunked_tbptt(
                        model=model,
                        input_ids=x,
                        targets=y,
                        chunk_size=config.chunk_size,
                        loss_fn=lambda logits, targets: compute_phase_loss(logits, targets, config),
                        accumulate_grad=True,
                        grad_scaler=scaler,
                        autocast_dtype=autocast_dtype if config.mixed_precision != "none" else None,
                        gradient_accumulation=config.gradient_accumulation,
                        aux_loss_fn=_tbptt_aux_loss_fn,
                    )
                    # Create synthetic outputs/loss for downstream logging
                    loss = torch.tensor(tbptt_result['total_loss'], device=device)
                    metrics = tbptt_result['metrics']
                    logits = None  # Not available in TBPTT (freed per-chunk)
                    outputs = {'logits': None}
                    tbptt_backward_done = True
                    # Log peak allocated memory on first iteration (actual tensor memory, not pool)
                    if not _first_iter_logged and accumulation_step == 0 and device.type == 'cuda':
                        peak_alloc = torch.cuda.max_memory_allocated() / (1024**3)
                        _tbptt_delta = peak_alloc - _mem_baseline
                        print(f"  [TBPTT] Memory: baseline={_mem_baseline:.2f} GB (model+optim), "
                              f"peak={peak_alloc:.2f} GB, delta={_tbptt_delta:.2f} GB (activations)")
                        _mem_baseline = 0.0  # cleanup
                elif use_chunking:
                    # Chunked forward: splits sequence, maintains Phase state
                    outputs = forward_chunked(
                        model, x,
                        chunk_size=config.chunk_size,
                        return_decorr_loss=enable_decorr,
                    )
                else:
                    # Standard forward: process full sequence at once
                    if not _first_iter_logged and accumulation_step == 0 and device.type == 'cuda':
                        _mem_baseline = torch.cuda.memory_allocated() / (1024**3)
                        torch.cuda.reset_peak_memory_stats()
                    # Phase 3/4 governance needs hidden states for primitive scoring + routing
                    # Stage 0 tracer also needs hidden states for binding cache metrics
                    _need_hidden = (config.enable_conscious_generation
                                    and hasattr(model, 'conscious_gen')
                                    and 'integrated_scorer' in model.conscious_gen)
                    _need_hidden = _need_hidden or (generation_tracer is not None)
                    if enable_decorr or _need_hidden:
                        outputs = model(x, return_decorr_loss=enable_decorr,
                                        return_last_hidden=_need_hidden)
                    else:
                        outputs = model(x)

                if not tbptt_backward_done:
                    if isinstance(outputs, dict):
                        logits = outputs.get('logits', outputs.get('output', outputs.get('last_hidden_state')))
                    else:
                        logits = outputs

                # DEBUG: Check logits on step 50 (matches first log output)
                if global_step == 50 and accumulation_step == 0 and logits is not None:
                    print(f"\n[DEBUG LOGITS] Step 50 diagnostic:")
                    print(f"  logits shape: {logits.shape}")
                    print(f"  logits dtype: {logits.dtype}")
                    print(f"  logits min/max: {logits.min().item():.4f} / {logits.max().item():.4f}")
                    print(f"  logits mean/std: {logits.mean().item():.4f} / {logits.std().item():.4f}")
                    print(f"  logits has NaN: {torch.isnan(logits).any().item()}")
                    print(f"  logits has Inf: {torch.isinf(logits).any().item()}")
                    # Check expected loss for uniform logits
                    expected_loss = math.log(logits.shape[-1])
                    print(f"  expected random loss: {expected_loss:.4f}")
                    # Sample some logits
                    sample_logits = logits[0, 0, :10].tolist()
                    print(f"  sample logits[0,0,:10]: {[f'{x:.2f}' for x in sample_logits]}")
                    # Check softmax distribution
                    probs = torch.softmax(logits[0, 0], dim=-1)
                    print(f"  softmax max prob: {probs.max().item():.6f}")
                    print(f"  softmax entropy: {-(probs * torch.log(probs + 1e-9)).sum().item():.4f}")
                    # Compute loss manually to verify
                    manual_loss = F.cross_entropy(logits.view(-1, logits.shape[-1]), y.view(-1), ignore_index=-100)
                    print(f"  manual CE loss: {manual_loss.item():.4f}")

                if not tbptt_backward_done:
                    loss, metrics = compute_phase_loss(logits, y, config)

                # Knowledge Distillation from frozen Mistral teacher
                if (mistral_teacher is not None
                        and not tbptt_backward_done
                        and logits is not None
                        and global_step >= config.distill_warmup_steps):
                    from symbolu_training.training.unified.mistral_teacher import compute_distillation_loss
                    # Re-tokenize with Mistral's tokenizer if vocabs differ
                    # For simplicity: use same input_ids if tokenizers match,
                    # otherwise decode + re-encode (slow but correct)
                    _kd_input_ids = x  # assume shared tokenizer by default
                    if distill_tokenizer is not None and tokenizer is not None:
                        # Check if vocabs match (fast path)
                        if getattr(tokenizer, 'vocab_size', -1) != mistral_teacher.vocab_size:
                            # Different tokenizers: decode student tokens, re-encode for teacher
                            _kd_texts = tokenizer.batch_decode(x, skip_special_tokens=False)
                            _kd_enc = distill_tokenizer(
                                _kd_texts, return_tensors="pt",
                                truncation=True, max_length=x.shape[1],
                                padding="max_length", pad_to_multiple_of=None,
                            )
                            _kd_input_ids = _kd_enc["input_ids"].to(x.device)
                    with torch.no_grad():
                        _teacher_logits = mistral_teacher(_kd_input_ids)
                    # Replace CE loss with combined KD + CE loss
                    loss, _kd_metrics = compute_distillation_loss(
                        student_logits=logits,
                        teacher_logits=_teacher_logits,
                        labels=y,
                        temperature=config.distill_temperature,
                        alpha=config.distill_alpha,
                    )
                    metrics.update(_kd_metrics)

                # Entropy-Based Logit Scale Control (train-time)
                if entropy_scale_module is not None and not tbptt_backward_done:
                    scaled_logits = entropy_scale_module(logits)
                    loss, entropy_metrics = entropy_scale_module.compute_loss(scaled_logits, loss)
                    metrics.update({f'ec_{k}': v for k, v in entropy_metrics.items() if isinstance(v, (int, float))})
                    # Log periodically
                    if global_step % config.log_every == 0 and global_step > 0:
                        log_msg = log_entropy_metrics(entropy_metrics, global_step, writer=writer)
                        if 'entropy_warning' in entropy_metrics:
                            print(log_msg)

                # Add decorrelation loss if enabled
                # V9.9.6: Store tensor for re-adding after SRK (which replaces loss)
                decorr_loss_tensor = None
                ortho_loss_tensor = None

                if enable_decorr and isinstance(outputs, dict) and 'decorr_loss' in outputs:
                    decorr_loss_tensor = outputs['decorr_loss']
                    # V11.3: Scale decorrelation by _aux_loss_scale when val PPL stagnates
                    _decorr_w = config.decorr_loss_weight * _aux_loss_scale
                    loss = loss + _decorr_w * decorr_loss_tensor
                    metrics['decorr_loss'] = decorr_loss_tensor.item()
                    metrics['decorr_weight'] = _decorr_w

                # V9.9.5: Weight orthogonalization loss (parameter-level decorrelation)
                # This directly regularizes attention weights, guaranteeing gradient flow
                # Unlike output decorrelation, this cannot be blocked by detach()
                if enable_decorr and config.decorr_loss_weight > 0:
                    # Debug on first step only
                    ortho_loss_tensor = compute_weight_orthogonalization_loss(model, debug=(global_step == 1))
                    # V11.3: Scale by _aux_loss_scale when val PPL stagnates
                    loss = loss + _decorr_w * ortho_loss_tensor
                    metrics['ortho_loss'] = ortho_loss_tensor.item()

                # V9.9.10/V9.9.12: Phase diversity loss (combat phase collapse)
                # Uses uniformity loss |E[e^{iφ}]|² and entropy proxy R = |E[e^{iφ}]|
                if phase_diversity_enabled:
                    # Capture task loss BEFORE adding phase diversity (for self-scaling)
                    task_loss_for_scaling = loss.detach().item()

                    # First compute loss with weight=1 to get R metric
                    phase_div_loss_raw, phase_div_metrics = compute_model_phase_diversity_loss(
                        model,
                        lambda_uniform=1.0,
                        lambda_entropy=1.0,
                    )

                    # Get current R (entropy proxy) for adaptive controller
                    current_R = phase_div_metrics['phase_entropy_proxy']

                    # Determine weight: adaptive (V9.9.12) or fixed (V9.9.10)
                    if phase_diversity_controller is not None:
                        # V9.9.12/V9.9.12b: Adaptive controller with optional task-loss scaling
                        # Pass task_loss for self-normalized scaling (ChatGPT's Lagrange approach)
                        current_weight = phase_diversity_controller.get_weight(
                            global_step, current_R, task_loss=task_loss_for_scaling
                        )
                        controller_status = phase_diversity_controller.get_status()
                        metrics['phase_div_R_ema'] = controller_status['phase_div_R_ema']
                        metrics['phase_div_target_R'] = controller_status['phase_div_target_R']
                        metrics['phase_div_collapse_pressure'] = controller_status.get('phase_div_collapse_pressure', 0.0)
                    else:
                        # V9.9.10: Fixed ramped weight
                        ramp_progress = min(1.0, global_step / max(1, config.phase_diversity_ramp_steps))
                        current_weight = config.phase_diversity_weight * (0.1 + 0.9 * ramp_progress)

                    # Scale the loss by the computed weight
                    # V11.3.1: Phase diversity is EXEMPT from aux_loss_scale — it's therapeutic
                    # (fixing key collapse), not parasitic. Scaling it down worsens R_k.
                    phase_div_loss = phase_div_loss_raw * current_weight

                    if phase_div_loss.requires_grad:
                        loss = loss + phase_div_loss
                        # V9.9.12c: Store tensor for re-adding after SRK (which replaces loss)
                        phase_div_loss_tensor = phase_div_loss_raw  # Store raw (unweighted)
                        phase_div_weight_for_srk = current_weight   # Store weight separately
                        metrics['phase_uniform_loss'] = phase_div_metrics['phase_uniform_loss']
                        metrics['phase_entropy_proxy'] = current_R
                        metrics['phase_uniform_loss_q'] = phase_div_metrics.get('phase_uniform_loss_q', 0.0)
                        metrics['phase_entropy_proxy_q'] = phase_div_metrics.get('phase_entropy_proxy_q', 0.0)
                        metrics['phase_diversity_loss'] = phase_div_loss.item()
                        metrics['phase_diversity_weight'] = current_weight

                        # One-time log when loss activates
                        if global_step == 1:
                            mode = "TASK-SCALED" if (phase_diversity_controller and phase_diversity_controller.task_loss_scaling) else \
                                   "ADAPTIVE" if phase_diversity_controller else "FIXED"
                            print(f"\n  🌀 [PHASE DIVERSITY] {mode} mode active!")
                            print(f"     ├─ Uniform Loss: {phase_div_metrics['phase_uniform_loss']:.4f}")
                            print(f"     ├─ Entropy Proxy R: {current_R:.4f}")
                            print(f"     ├─ λ: {current_weight:.6f}")
                            if phase_diversity_controller and phase_diversity_controller.task_loss_scaling:
                                print(f"     ├─ Task Loss (for scaling): {task_loss_for_scaling:.4f}")
                            print(f"     └─ Layers captured: {phase_div_metrics['num_layers_captured']}")

            # =================================================================
            # V9.8.0: RSS (Rational Sovereign Sequence) Weight Calculation
            # =================================================================
            rss_weights = {'evoflow': 0.0, 'toroidal': 0.0, 'csr': 0.0, 'kosha': 0.0}
            if rss_controller is not None:
                # Use metrics["ppl"] from LM loss, not total loss (which includes auxiliary terms)
                train_ppl = metrics.get("ppl", float("inf"))
                rss_weights = rss_controller.get_gate_weights(
                    current_ppl=train_ppl,
                    global_step=global_step,
                    val_ppl=last_val_ppl if last_val_ppl < float('inf') else None,
                )
                # Log phase transitions
                phase_msg = rss_controller.get_phase_transition_message()
                if phase_msg:
                    print(phase_msg)
                # Store weights for metrics
                metrics['rss_evoflow'] = rss_weights['evoflow']
                metrics['rss_toroidal'] = rss_weights['toroidal']
                metrics['rss_csr'] = rss_weights['csr']
                metrics['rss_kosha'] = rss_weights['kosha']
                metrics['rss_phase'] = rss_controller.current_phase

            # =================================================================
            # V9.8.0: Sovereign Reasoning Kernel (SRK) Integration
            # Reference: SOVEREIGN_REASONING_KERNEL_DESIGN.md Section 6.2
            # =================================================================
            srk_metrics = {}
            if srk is not None and hidden_state_extractor is not None:
                # Get hidden states from all layers
                layer_hidden_states = hidden_state_extractor.get_hidden_states(outputs, x)

                if layer_hidden_states is not None and len(layer_hidden_states) > 0:
                    # Handle batch size changes (VRAM governor may resize)
                    current_batch_size = x.shape[0]
                    if srk_karma_state.shape[0] != current_batch_size:
                        srk_karma_state = torch.zeros(current_batch_size, SOVEREIGN_STATE_DIM, device=device)

                    # Extract hidden states for SRK processing
                    # Use last layer hidden states for state computation
                    final_hidden = layer_hidden_states[-1]  # [B, N, D]

                    # Compute current 32D sovereign state from hidden states
                    current_state = srk.compute_state_from_hidden(final_hidden)

                    # SRK forward pass with layer interventions (diagnostic mode)
                    # During training, SRK observes and computes losses but doesn't modify hiddens
                    srk_result = srk.forward_pass(
                        hidden_states=final_hidden,
                        layer_idx=11,  # Use final layer for synthesis
                        current_state=current_state,
                        karma_state=srk_karma_state,
                        task_type='factual',  # Default task type
                    )
                    srk_diagnostics = srk_result.get('diagnostics', {})

                    # Update lambda values via annealer
                    # V11.3: Apply _aux_loss_scale to non-task lambdas when val PPL stagnates
                    if srk_annealer is not None:
                        annealed_lambdas = srk_annealer.get_lambdas(global_step)
                        srk_loss_fn.config.lambda_f = annealed_lambdas['lambda_f']
                        srk_loss_fn.config.lambda_b = annealed_lambdas['lambda_b']
                        srk_loss_fn.config.lambda_c = annealed_lambdas['lambda_c'] * _aux_loss_scale
                        srk_loss_fn.config.lambda_entropy = annealed_lambdas['lambda_entropy'] * _aux_loss_scale
                        srk_loss_fn.config.lambda_coherence = annealed_lambdas['lambda_coherence'] * _aux_loss_scale
                        srk_diagnostics['annealer_phase'] = srk_annealer.get_phase_name(global_step)
                        srk_diagnostics['aux_loss_scale'] = _aux_loss_scale

                    # Compute SRK loss (B1/U2/S8 patent formulas)
                    # V10.7: Skip when logits are None (TBPTT frees per-chunk logits)
                    if logits is not None:
                        srk_loss, srk_loss_metrics = srk_loss_fn(
                            logits=logits,
                            targets=y,
                            hidden_states=final_hidden,
                            karma_state=srk_karma_state,
                            srk_diagnostics=srk_diagnostics,
                            attention_phases=None,  # Phase extraction from hook if available
                            mask=None,
                        )
                    else:
                        # TBPTT: logits freed per-chunk, use task loss already computed
                        srk_loss = loss
                        srk_loss_metrics = {}

                    # Replace or augment loss with SRK loss
                    # SRK loss includes task loss (cross-entropy) + B1/U2/S8 terms
                    # V9.9.6: Preserve decorr_loss and ortho_loss tensors (for gradient flow)
                    # by re-adding them after SRK replaces the loss
                    loss = srk_loss
                    if enable_decorr and config.decorr_loss_weight > 0:
                        # V11.3: Use scaled decorr weight when val PPL stagnates
                        _decorr_w_srk = config.decorr_loss_weight * _aux_loss_scale
                        if decorr_loss_tensor is not None:
                            loss = loss + _decorr_w_srk * decorr_loss_tensor
                        if ortho_loss_tensor is not None:
                            loss = loss + _decorr_w_srk * ortho_loss_tensor

                    # V9.9.12c: Re-add phase diversity loss (for gradient flow to W_k_phase)
                    # V11.3.1: Phase diversity EXEMPT from aux_loss_scale (therapeutic)
                    if phase_div_loss_tensor is not None and phase_div_weight_for_srk > 0:
                        loss = loss + phase_div_weight_for_srk * phase_div_loss_tensor

                    # Update karma state for O12→O1 carryover (Toroidal Loop)
                    with torch.no_grad():
                        srk_karma_state = current_state.detach() * config.srk_karma_decay

                    # Collect SRK metrics
                    srk_metrics = srk_loss_metrics.copy()
                    srk_metrics.update({
                        'srk_state_norm': current_state.norm(dim=-1).mean().item(),
                        'srk_karma_norm': srk_karma_state.norm(dim=-1).mean().item(),
                    })
                    srk_metrics.update({f'srk_{k}': v for k, v in srk_diagnostics.items() if isinstance(v, (int, float))})

                    # Log SRK diagnostics periodically (only at end of accumulation to avoid duplicates)
                    if (global_step % config.log_every == 0 and global_step > 0 and
                        (accumulation_step + 1) % config.gradient_accumulation == 0):
                        phase_name = srk_diagnostics.get('annealer_phase', 'UNKNOWN')
                        _aux_scale_str = f" | aux_scale={_aux_loss_scale:.3f}" if _aux_loss_scale < 1.0 else ""
                        print(f"  [SRK] Step {global_step} | Phase: {phase_name} | "
                              f"L_total={srk_metrics.get('L_total', 0):.4f} | "
                              f"L_B1={srk_metrics.get('L_lagrangian', 0):.4f} | "
                              f"s_f={srk_metrics.get('s_f', 0):.3f} s_b={srk_metrics.get('s_b', 0):.3f}"
                              f"{_aux_scale_str}")

            # Phase-JEPA: Joint Embedding Predictive Loss Integration
            jepa_metrics = {}
            if jepa_model is not None and JEPA_AVAILABLE:
                try:
                    # Get karma state from SRK if available (for karma injection)
                    external_karma = srk_karma_state if (
                        config.jepa_enable_karma_injection and srk_karma_state is not None
                    ) else None

                    # JEPA forward pass with loss computation
                    jepa_output = jepa_model(
                        input_ids=x,
                        attention_mask=None,  # Full attention for JEPA
                        external_karma=external_karma,
                        compute_loss=True,
                        return_states=False,
                    )

                    # Extract JEPA loss
                    jepa_loss = jepa_output.get('loss', torch.tensor(0.0, device=device))
                    jepa_loss_components = jepa_output.get('loss_components', {})

                    # Get curriculum weight based on current phase
                    if jepa_curriculum is not None:
                        phase_progress = jepa_curriculum.get_progress()
                        macro_phase = phase_progress.get('macro_phase', 'BODY')

                        # During SOUL phase, reduce JEPA loss weight
                        if macro_phase == 'SOUL':
                            jepa_weight = 0.1  # Minimal JEPA during SRK-focused phase
                        elif macro_phase == 'UNION':
                            jepa_weight = 0.5  # Balanced during integration
                        else:  # BODY
                            jepa_weight = 1.0  # Full JEPA during perceptual learning

                        jepa_loss = jepa_weight * jepa_loss
                    else:
                        jepa_weight = config.jepa_prediction_weight

                    # Add JEPA loss to total loss
                    loss = loss + jepa_weight * jepa_loss

                    # Update target encoder (EMA) and curriculum step
                    # Pass jepa_loss and alignment for dynamic graduation
                    jepa_loss_value = jepa_loss.item() if isinstance(jepa_loss, torch.Tensor) else jepa_loss
                    phase_changed, new_phase = jepa_model.training_step_update(
                        metrics={
                            'variance': jepa_loss_components.get('variance', 0.0),
                            'jepa_loss': jepa_loss_value,
                            'alignment': jepa_loss_components.get('alignment', 0.0),
                        }
                    )

                    # Collect JEPA metrics
                    jepa_metrics = {
                        'jepa_loss': jepa_loss.item() if isinstance(jepa_loss, torch.Tensor) else jepa_loss,
                        'jepa_vicreg': jepa_loss_components.get('vicreg', 0.0),
                        'jepa_alignment': jepa_loss_components.get('alignment', 0.0),
                        'jepa_ortho': jepa_loss_components.get('orthogonality', 0.0),
                    }

                    if jepa_curriculum is not None:
                        progress = jepa_curriculum.get_progress()
                        jepa_metrics['jepa_phase'] = progress.get('macro_phase', 'BODY')
                        jepa_metrics['jepa_k_steps'] = jepa_curriculum.get_k_steps()

                    # Log phase transitions (only at end of accumulation)
                    if phase_changed and new_phase and (accumulation_step + 1) % config.gradient_accumulation == 0:
                        print(f"\n  🔄 [JEPA] Phase Transition → {new_phase} at step {global_step}")

                    # Log JEPA diagnostics periodically (only at end of accumulation to avoid duplicates)
                    if (global_step % config.log_every == 0 and global_step > 0 and
                        (accumulation_step + 1) % config.gradient_accumulation == 0):
                        phase_str = jepa_metrics.get('jepa_phase', 'BODY')
                        print(f"  [JEPA] Step {global_step} | Phase: {phase_str} | "
                              f"Loss={jepa_metrics.get('jepa_loss', 0):.4f} | "
                              f"VICReg={jepa_metrics.get('jepa_vicreg', 0):.4f} | "
                              f"Align={jepa_metrics.get('jepa_alignment', 0):.4f}")

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  ⚠️ [JEPA] Error: {e}")

            # CSR Phoneme-Ontological Grounding Integration
            csr_metrics = {}
            if csr_provider is not None:
                # V9.5.2 Performance: CSR provider uses precomputed token affinity table
                # No need to decode tokens here - the table maps token_id → affinity directly
                # This eliminates O(B*T) tokenizer.decode() calls that caused Step 10 stall
                csr_output = csr_provider(x, token_strings=None)
                csr_emb = csr_output['csr_emb']
                csr_affinity = csr_output['csr_affinity']
                csr_confidence = csr_output['csr_confidence']

                # V9.6.0 FIX: Use EARLY layer (not Layer 11) for CSR alignment
                # CRITICAL: Layer 11 is the LM Head input - pushing it toward Sanskrit
                # corrupts token prediction and causes "@ = <" aphasia.
                # Early layers (2-3) influence concept formation without hijacking output.
                csr_hidden = None
                if hidden_state_extractor is not None:
                    layer_hidden_states = hidden_state_extractor.get_hidden_states(outputs, x)
                    if layer_hidden_states is not None and len(layer_hidden_states) > 0:
                        # V9.6.0: Configurable CSR alignment layer
                        # - Layer 0-1: Raw token processing
                        # - Layer 2-3: Abstract concept formation ← DEFAULT for Sanskrit ontology
                        # - Layer 4-8: Reasoning and structure
                        # - Layer 9-11: Output preparation ← AVOID (causes aphasia)
                        csr_layer_idx = min(config.csr_alignment_layer, len(layer_hidden_states) - 1)
                        csr_hidden = layer_hidden_states[csr_layer_idx]

                        # V9.6.7: One-time diagnostic log to confirm layer selection and gradient isolation
                        if not hasattr(model, '_csr_layer_logged'):
                            model._csr_layer_logged = True
                            print(f"  ✅ [V9.6.7] Using Layer {csr_layer_idx} for CSR alignment (config: {config.csr_alignment_layer})")
                            print(f"     Hidden states available: {len(layer_hidden_states)} layers")
                            print(f"  🛡️ [V9.6.7] COMPLETE gradient isolation ACTIVE:")
                            print(f"     ├─ CSR alignment:  detached (no gradient to model)")
                            print(f"     ├─ EntropySink:    detached (no gradient to Layer 0)")
                            print(f"     ├─ SynthesisGate:  detached (no gradient to Layer 11)")
                            print(f"     ├─ Toroidal O1/O12: detached (no gradient to model)")
                            print(f"     └─ EvoFlow states: detached (no gradient to model)")
                            print(f"     All auxiliary systems are now MONITOR-ONLY - LM loss is the ONLY training signal")

                if csr_hidden is not None:
                    # V9.5.4 DIMENSION FIX: Project CSR embeddings to match model hidden size
                    # CSR embeddings are 512-dim, model hidden states may be 768-dim (or other)
                    if csr_emb.shape[-1] != csr_hidden.shape[-1]:
                        # Create projector on first mismatch (lazy initialization)
                        if not hasattr(model, '_csr_projector') or model._csr_projector is None:
                            csr_dim = csr_emb.shape[-1]
                            hidden_dim = csr_hidden.shape[-1]
                            model._csr_projector = torch.nn.Linear(csr_dim, hidden_dim, bias=False).to(csr_emb.device)
                            # Initialize with small weights for stable training
                            torch.nn.init.xavier_uniform_(model._csr_projector.weight)
                            print(f"  ⚡ [CSR] Created projector: {csr_dim}D → {hidden_dim}D (Phoneme→Model space)")

                            # V9.6.8: Apply gradient scaling hook for 0.1x LR effect (Gemini recommendation)
                            # This ensures the projector learns slowly and stably
                            lr_scale = config.csr_projector_lr_scale
                            if lr_scale != 1.0:
                                def csr_proj_grad_hook(grad):
                                    return grad * lr_scale
                                model._csr_projector.weight.register_hook(csr_proj_grad_hook)
                                print(f"  ⚡ [CSR] Projector LR scale: {lr_scale}x (stable foundation)")

                        # Project CSR embeddings to model dimension
                        csr_emb = model._csr_projector(csr_emb)

                    # V9.5.5: Temperature-sharpened contrastive loss (InfoNCE-style)
                    # Dividing by tau amplifies gradient signal: tau=0.07 → 14x stronger gradients
                    # This makes Sanskrit phoneme ontology a mathematical CONSTRAINT, not a gentle suggestion
                    #
                    # V9.6.5 CRITICAL FIX: Detach csr_hidden to prevent gradient flow to embeddings!
                    # Without detach, CSR gradients flow: csr_hidden → Layer 2 → Layer 1 → Layer 0 → token_embed
                    # This corrupts the INPUT embeddings, causing "@ = <" garbage output.
                    # With detach, CSR becomes a forward-only alignment signal - the model READS the Sanskrit
                    # target but doesn't corrupt its own vocabulary trying to chase it.
                    # Sovereign Loss and EvoFlow provide the actual ontological training signal.
                    #
                    # V9.6.8: Optional gradient warmup - re-enable after model learns grammar (Gemini recommendation)
                    # Once PPL < 800 or step > csr_gradient_warmup_steps, allow CSR to subtly reshape Layer 2
                    if config.csr_gradient_warmup_steps > 0 and global_step > config.csr_gradient_warmup_steps:
                        # Re-enable gradient flow after warmup (model has learned basic grammar)
                        csr_hidden_for_loss = csr_hidden  # Allow gradients to flow
                        if not hasattr(model, '_csr_warmup_logged'):
                            model._csr_warmup_logged = True
                            print(f"  🔓 [CSR V9.6.8] Gradient warmup complete at step {global_step}")
                            print(f"     CSR gradients now flow to Layer {csr_layer_idx} for ontological shaping")
                    else:
                        csr_hidden_for_loss = csr_hidden.detach()  # CRITICAL: Break gradient flow!

                    # V9.6.9: Also detach csr_emb to make CSR purely observational
                    # Previously, gradients flowed: loss → csr_emb → CSR provider
                    # This trained CSR's projection/confidence_head to align with model states,
                    # creating an indirect Sanskrit influence on the loss landscape.
                    # With both sides detached, CSR becomes monitor-only - no training signal flows.
                    csr_emb_for_loss = csr_emb.detach()
                    csr_confidence_for_loss = csr_confidence.detach()

                    # V9.8.1: Align sequence lengths if they differ
                    # This can happen if model internally truncates sequences
                    # Store aligned length for use with EntropySink/SynthesisGate too
                    csr_aligned_seq_len = None
                    if csr_hidden_for_loss.shape[1] != csr_emb_for_loss.shape[1]:
                        min_len = min(csr_hidden_for_loss.shape[1], csr_emb_for_loss.shape[1])
                        csr_aligned_seq_len = min_len
                        csr_hidden_for_loss = csr_hidden_for_loss[:, :min_len, :]
                        csr_emb_for_loss = csr_emb_for_loss[:, :min_len, :]
                        csr_confidence_for_loss = csr_confidence_for_loss[:, :min_len, :]

                    # V9.7.0: Choose between Sparse (Whole-Word) and Dense (Per-Token) supervision
                    if config.csr_sparse_supervision:
                        # =====================================================================
                        # SPARSE DELAYED SUPERVISION: Only apply loss at word boundaries
                        # Uses whole-word varna lookup instead of per-subtoken
                        # This fixes the "word salad" problem where grammar gets destroyed
                        # =====================================================================

                        # Create helper for this batch (lazy init with caching)
                        if not hasattr(model, '_whole_word_csr_helper'):
                            model._whole_word_csr_helper = WholeWordCSRHelper(tokenizer, csr_provider)

                        # Compute word boundaries and whole-word varna targets
                        word_end_mask, content_weight, whole_word_varna = \
                            model._whole_word_csr_helper.compute_word_boundaries(x)

                        # Create projector for hidden → 12D varna space if needed
                        if not hasattr(model, '_csr_varna_projector') or model._csr_varna_projector is None:
                            hidden_dim = csr_hidden_for_loss.shape[-1]
                            model._csr_varna_projector = torch.nn.Linear(hidden_dim, 12, bias=False).to(device)
                            torch.nn.init.xavier_uniform_(model._csr_varna_projector.weight)
                            print(f"  ⚡ [CSR SPARSE] Created varna projector: {hidden_dim}D → 12D")

                        # Phase 3: Use Bliss-gated λ if available (one-step lag)
                        _csr_lambda = bliss_lambda_eff_csr if bliss_lambda_eff_csr is not None else config.csr_lambda

                        # Calculate sparse CSR loss
                        csr_loss, sparse_metrics = calculate_sparse_csr_loss(
                            hidden_states=csr_hidden_for_loss,
                            whole_word_varna=whole_word_varna,
                            word_end_mask=word_end_mask,
                            content_weight=content_weight,
                            csr_projector=model._csr_varna_projector,
                            tau=config.csr_tau,
                            lambda_csr=_csr_lambda,
                            content_word_only=config.csr_content_word_only,
                        )

                        # V9.8.6: Apply three-phase curriculum scaling
                        csr_scale = csr_curriculum.scale if csr_curriculum is not None else 1.0
                        csr_loss_scaled = csr_loss * csr_scale
                        loss = loss + csr_loss_scaled
                        csr_metrics.update(sparse_metrics)
                        csr_metrics['csr_loss'] = csr_loss.item()
                        csr_metrics['csr_loss_scaled'] = csr_loss_scaled.item()
                        csr_metrics['csr_curriculum_scale'] = csr_scale
                        csr_metrics['csr_confidence'] = csr_confidence.mean().item()
                        csr_metrics['csr_lambda_used'] = _csr_lambda
                        # Use sparse similarity metric
                        csr_metrics['csr_similarity'] = sparse_metrics.get('csr_sparse_similarity', 0.0)

                    else:
                        # =====================================================================
                        # DENSE PER-TOKEN SUPERVISION: Original method
                        # Apply loss at every token position
                        # =====================================================================
                        csr_hidden_norm = torch.nn.functional.normalize(csr_hidden_for_loss, dim=-1)
                        csr_emb_norm = torch.nn.functional.normalize(csr_emb_for_loss, dim=-1)
                        csr_similarity = (csr_hidden_norm * csr_emb_norm).sum(dim=-1)
                        # Temperature sharpening: (1 - sim) / tau creates steep gradient landscape
                        # When alignment is poor (sim ≈ 0): loss = (1-0)/0.07 ≈ 14.3 → STRONG pressure
                        # When alignment is good (sim ≈ 0.9): loss = (1-0.9)/0.07 ≈ 1.4 → mild pressure
                        # V9.6.9/V9.8.1: csr_confidence_for_loss already detached and aligned above
                        # Phase 3: Use Bliss-gated λ if available (one-step lag)
                        _csr_lambda = bliss_lambda_eff_csr if bliss_lambda_eff_csr is not None else config.csr_lambda
                        csr_alignment_loss = ((1 - csr_similarity) / config.csr_tau) * csr_confidence_for_loss.squeeze(-1)
                        csr_loss = csr_alignment_loss.mean() * _csr_lambda

                        # V9.8.0: RSS scales CSR loss with linear warmup to prevent 14x gradient shock
                        if config.enable_rss and rss_weights['csr'] > 0:
                            csr_loss = csr_loss * rss_weights['csr']
                            csr_metrics['rss_csr_weight'] = rss_weights['csr']

                        # V9.6.9: CSR loss is now purely observational (no gradients flow)
                        # We still track it for metrics, but it doesn't influence training
                        # The cross-entropy LM loss is the ONLY training signal
                        # V9.8.6: Apply three-phase curriculum scaling
                        csr_scale = csr_curriculum.scale if csr_curriculum is not None else 1.0
                        csr_loss_scaled = csr_loss * csr_scale
                        loss = loss + csr_loss_scaled
                        csr_metrics['csr_loss'] = csr_loss.item()
                        csr_metrics['csr_loss_scaled'] = csr_loss_scaled.item()
                        csr_metrics['csr_curriculum_scale'] = csr_scale
                        csr_metrics['csr_confidence'] = csr_confidence.mean().item()
                        csr_metrics['csr_similarity'] = csr_similarity.mean().item()
                        csr_metrics['csr_lambda_used'] = _csr_lambda
                else:
                    csr_metrics['csr_loss'] = 0.0
                    csr_metrics['csr_confidence'] = csr_confidence.mean().item() if csr_confidence is not None else 0.0

            # =================================================================
            # Appendix G Phase 4: JEPA Weak Prior Injection
            # Projects JEPA s_pred (32D Sovereign State) → d_model space,
            # then computes alignment loss between JEPA prior and hidden state
            # at the configured injection layer. Uses Bliss-gated λ_eff.
            # Multi-prior norm stacking: total injection (CSR + JEPA) is capped
            # at ε_layer × rms(H) per Trap 3 guardrail (G.4a).
            # =================================================================
            jepa_injection_metrics = {}
            if (config.enable_jepa_injection
                    and jepa_injection_projector is not None
                    and jepa_model is not None
                    and hidden_state_extractor is not None):
                try:
                    # Get JEPA state prediction (already computed in JEPA forward pass)
                    _jepa_out = jepa_output if 'jepa_output' in dir() else None
                    _s_pred = _jepa_out.get('s_pred', None) if _jepa_out is not None else None

                    if _s_pred is not None:
                        # Project 32D → d_model (with gradients for projector training)
                        # s_pred may be [B, 32] (summary) or [B, T_pred, 32] (per-token)
                        jepa_prior_vec = jepa_injection_projector(_s_pred.detach())

                        # Get injection layer hidden state
                        layer_hs_for_jepa = hidden_state_extractor.get_hidden_states(outputs, x)
                        if layer_hs_for_jepa is not None and len(layer_hs_for_jepa) > 0:
                            jepa_inj_layer = min(
                                config.jepa_injection_layer, len(layer_hs_for_jepa) - 1
                            )
                            jepa_hidden = layer_hs_for_jepa[jepa_inj_layer]  # [B, T, d_model]

                            # Expand/align JEPA prior to [B, T, d_model]
                            T_jepa = jepa_hidden.shape[1]
                            if jepa_prior_vec.dim() == 3:
                                # Per-token: [B, T_pred, d_model] → truncate/pad to T
                                T_pred = jepa_prior_vec.shape[1]
                                if T_pred >= T_jepa:
                                    jepa_prior_expanded = jepa_prior_vec[:, :T_jepa, :]
                                else:
                                    pad = jepa_prior_vec[:, -1:, :].expand(-1, T_jepa - T_pred, -1)
                                    jepa_prior_expanded = torch.cat([jepa_prior_vec, pad], dim=1)
                            else:
                                # Summary: [B, d_model] → broadcast to all positions
                                jepa_prior_expanded = jepa_prior_vec.unsqueeze(1).expand(-1, T_jepa, -1)

                            # DETACH hidden state: JEPA injection is observational
                            # (projector learns, model does not backprop through this)
                            jepa_hidden_detached = jepa_hidden.detach()

                            # Compute contrastive alignment loss (same pattern as CSR)
                            jepa_hidden_norm = torch.nn.functional.normalize(
                                jepa_hidden_detached, dim=-1
                            )
                            jepa_prior_norm = torch.nn.functional.normalize(
                                jepa_prior_expanded, dim=-1
                            )
                            jepa_similarity = (jepa_hidden_norm * jepa_prior_norm).sum(dim=-1)

                            # Use Bliss-gated λ if available (one-step lag from previous iteration)
                            _jepa_lambda = (
                                bliss_lambda_eff_jepa
                                if bliss_lambda_eff_jepa is not None
                                else config.jepa_injection_lambda
                            )

                            # Alignment loss: push hidden states toward JEPA prior
                            jepa_injection_loss = ((1 - jepa_similarity) * _jepa_lambda).mean()

                            # Apply injection discipline: norm cap (Trap 3)
                            # Total injection from ALL priors must be bounded
                            jepa_prior_rms = jepa_prior_expanded.norm(dim=-1).mean().item()
                            h_rms = jepa_hidden_detached.norm(dim=-1).mean().item()
                            eps_layer = bliss_functional.get_eps_layer(global_step) if bliss_functional else 0.05
                            max_inj_norm = eps_layer * h_rms

                            # Log cap status
                            jepa_injection_metrics['jepa_inj_loss'] = jepa_injection_loss.item()
                            jepa_injection_metrics['jepa_inj_similarity'] = jepa_similarity.mean().item()
                            jepa_injection_metrics['jepa_inj_lambda'] = _jepa_lambda
                            jepa_injection_metrics['jepa_inj_prior_rms'] = jepa_prior_rms
                            jepa_injection_metrics['jepa_inj_eps_cap'] = max_inj_norm
                            jepa_injection_metrics['jepa_inj_layer'] = jepa_inj_layer

                            # Only add loss if prior norm is within cap
                            # (prevents runaway injection that violates Trap 3)
                            if jepa_prior_rms * _jepa_lambda < max_inj_norm:
                                loss = loss + jepa_injection_loss
                                jepa_injection_metrics['jepa_inj_active'] = 1.0
                            else:
                                # Cap violated — scale down injection to fit within budget
                                cap_scale = max_inj_norm / (jepa_prior_rms * _jepa_lambda + 1e-8)
                                loss = loss + jepa_injection_loss * cap_scale
                                jepa_injection_metrics['jepa_inj_active'] = cap_scale
                                jepa_injection_metrics['jepa_inj_cap_violated'] = 1.0

                            # One-time diagnostic
                            if not hasattr(model, '_jepa_inj_logged'):
                                model._jepa_inj_logged = True
                                print(f"  ✅ [Phase 4] JEPA injection active at layer {jepa_inj_layer}")
                                print(f"     s_pred shape: {_s_pred.shape} → prior shape: {jepa_prior_expanded.shape}")
                                print(f"     λ_JEPA={_jepa_lambda:.4f} | ε_cap={eps_layer:.4f}")

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  ⚠️ [Phase 4 JEPA Injection] Error: {e}", flush=True)

            # Merge JEPA injection metrics into main metrics dict
            if jepa_injection_metrics:
                metrics.update(jepa_injection_metrics)

                # Periodic console logging for JEPA injection
                if global_step % config.bliss_log_interval == 0 and global_step > 0:
                    _jlam = jepa_injection_metrics.get('jepa_inj_lambda', 0)
                    _jsim = jepa_injection_metrics.get('jepa_inj_similarity', 0)
                    _jact = jepa_injection_metrics.get('jepa_inj_active', 0)
                    _jcap = '⚠️CAP' if 'jepa_inj_cap_violated' in jepa_injection_metrics else ''
                    print(f"  [JEPA Inj] sim={_jsim:.4f} | λ={_jlam:.4f} | "
                          f"active={_jact:.2f} {_jcap}", flush=True)

            if csr_provider is not None:
                # CSR Safety Layers: EntropySink (Layer 0) and SynthesisGate (Layer 11)
                # These enforce ontological safety at the boundaries of the 12D structure
                #
                # V9.6.6 CRITICAL FIX: DETACH hidden states for EntropySink and SynthesisGate!
                # Without detach, their trainable projections create gradient flow:
                #   - EntropySink: entropy_proj(layer_0) → Layer 0 → token embeddings (CORRUPTION!)
                #   - SynthesisGate: gate_proj(layer_11) → Layer 11 → ... → token embeddings (CORRUPTION!)
                # This was the REMAINING source of aphasia after V9.6.5 CSR alignment fix.
                #
                # With detach, these become monitor-only modules that track metrics without corrupting.
                if hidden_state_extractor is not None:
                    layer_hidden_states = hidden_state_extractor.get_hidden_states(outputs, x)

                    if layer_hidden_states is not None and len(layer_hidden_states) >= 12:
                        # EntropySink: Layer 0 (O1_Potential) safety - prevents mode collapse
                        if csr_entropy_sink is not None:
                            # V9.6.6: DETACH to prevent gradient flow to token embeddings!
                            layer_0_hidden = layer_hidden_states[0].detach()
                            # V9.8.1: Align csr_affinity to match hidden state sequence length
                            csr_affinity_aligned = csr_affinity
                            if csr_aligned_seq_len is not None and csr_affinity.shape[1] != layer_0_hidden.shape[1]:
                                seq_len = min(csr_affinity.shape[1], layer_0_hidden.shape[1])
                                csr_affinity_aligned = csr_affinity[:, :seq_len]
                                layer_0_hidden = layer_0_hidden[:, :seq_len, :]
                            if layer_0_hidden.shape[-1] == csr_emb.shape[-1]:
                                _, sink_metrics = csr_entropy_sink(layer_0_hidden, csr_affinity_aligned)
                                csr_metrics['entropy_sink_entropy'] = sink_metrics.get('entropy', 0.0)
                                csr_metrics['entropy_sink_anchor'] = sink_metrics.get('anchor_strength', 0.0)
                                # Note: With detach, this loss only trains EntropySink's projection,
                                # NOT the main model. This is intentional - monitoring, not corrupting.
                                if 'entropy' in sink_metrics:
                                    entropy_val = sink_metrics['entropy']
                                    if isinstance(entropy_val, torch.Tensor):
                                        entropy_floor_loss = torch.clamp(0.1 - entropy_val.mean(), min=0) * 0.1
                                        # V9.6.6: Still add loss but now only affects entropy_proj, not model
                                        loss = loss + entropy_floor_loss
                                        csr_metrics['entropy_floor_loss'] = entropy_floor_loss.item()

                        # SynthesisGate: Layer 11 (O11_Integration) safety - reconciles structure with flow
                        if csr_synthesis_gate is not None:
                            # V9.6.6: DETACH to prevent gradient flow through entire model!
                            layer_11_hidden = layer_hidden_states[11].detach()
                            # V9.8.1: Align csr_emb and csr_affinity to match hidden state sequence length
                            csr_emb_aligned = csr_emb
                            csr_affinity_aligned_11 = csr_affinity
                            if csr_aligned_seq_len is not None and csr_emb.shape[1] != layer_11_hidden.shape[1]:
                                seq_len = min(csr_emb.shape[1], layer_11_hidden.shape[1])
                                csr_emb_aligned = csr_emb[:, :seq_len, :]
                                csr_affinity_aligned_11 = csr_affinity[:, :seq_len]
                                layer_11_hidden = layer_11_hidden[:, :seq_len, :]
                            if layer_11_hidden.shape[-1] == csr_emb_aligned.shape[-1]:
                                synthesized, gate_metrics = csr_synthesis_gate(layer_11_hidden, csr_emb_aligned, csr_affinity_aligned_11)
                                csr_metrics['synthesis_gate_value'] = gate_metrics.get('gate_value', 0.0)
                                csr_metrics['synthesis_coherence'] = gate_metrics.get('coherence', 0.0)
                                # Note: With detach, this loss only trains SynthesisGate's projection,
                                # NOT the main model. This is intentional - monitoring, not corrupting.
                                if 'coherence' in gate_metrics:
                                    coherence_val = gate_metrics['coherence']
                                    if isinstance(coherence_val, torch.Tensor):
                                        synthesis_loss = (1 - coherence_val.mean()) * 0.05
                                        loss = loss + synthesis_loss
                                        csr_metrics['synthesis_loss'] = synthesis_loss.item()

                        # V9.7.0: Ontological Bridge - Layer 4 (Foundational Structure) projection to 12D
                        # Establishes ontological "DNA" early - 12 Aspects ground all subsequent processing
                        onto_layer = config.onto_bridge_layer
                        if onto_bridge is not None and len(layer_hidden_states) > onto_layer:
                            # DETACH to train only the bridge, not the main model
                            onto_hidden = layer_hidden_states[onto_layer].detach()
                            onto_repr, onto_metrics = onto_bridge(onto_hidden)
                            onto_loss, onto_loss_metrics = onto_bridge.compute_loss(
                                onto_repr,
                                lambda_diversity=config.onto_bridge_diversity,
                                lambda_pramana=config.onto_bridge_pramana,
                            )
                            # Scale by lambda and add to total loss
                            scaled_onto_loss = config.onto_bridge_lambda * onto_loss

                            # V9.8.6: Apply three-phase curriculum scaling
                            onto_scale = onto_curriculum.scale if onto_curriculum is not None else 1.0
                            scaled_onto_loss = scaled_onto_loss * onto_scale

                            loss = loss + scaled_onto_loss
                            # Store metrics
                            metrics['onto_bridge_loss'] = scaled_onto_loss.item()
                            metrics['onto_bridge_loss_unscaled'] = (config.onto_bridge_lambda * onto_loss).item()
                            metrics['onto_curriculum_scale'] = onto_scale
                            metrics['onto_diversity'] = onto_metrics.get('onto_diversity', 0.0)
                            metrics['onto_pramana_corr'] = onto_metrics.get('onto_pramana_corr', 0.0)
                            metrics['onto_bridge_layer'] = onto_layer

            # =================================================================
            # Appendix G: Bliss Coherence Measurement + Gating
            # Computes B = mean(B_A) - β·B_B over detached hidden states.
            # Phase 3: Computes λ_eff to gate CSR injection strength.
            # Phase 4: Also gates JEPA injection + multi-prior norm stacking.
            # =================================================================
            if bliss_functional is not None and hidden_state_extractor is not None:
                try:
                    layer_hs = hidden_state_extractor.get_hidden_states(outputs, x)
                    if layer_hs is not None and len(layer_hs) > 0:
                        # Build priors dict from available weak priors
                        bliss_priors = {}
                        if csr_provider is not None and 'csr_emb' in dir() and csr_emb is not None:
                            bliss_priors['csr'] = csr_emb.detach()

                        # Phase 4: Add JEPA predictions as a second prior
                        # JEPA s_pred may be [B, 32D] or [B, T_pred, 32D]
                        # Project to d_model and align to [B, T, d_model] for Bliss cosine agreement
                        jepa_prior_projected = None
                        if (config.enable_jepa_injection
                                and jepa_injection_projector is not None
                                and 'jepa_output' in dir()
                                and jepa_output is not None):
                            _jepa_s_pred = jepa_output.get('s_pred', None)
                            if _jepa_s_pred is not None:
                                # Project 32D → d_model (detach state for Bliss measurement)
                                jepa_prior_projected = jepa_injection_projector(
                                    _jepa_s_pred.detach()
                                )
                                # Align to [B, T, d_model] matching hidden state seq len
                                _T = layer_hs[0].shape[1]
                                if jepa_prior_projected.dim() == 3:
                                    # Per-token: truncate/pad to match T
                                    _T_pred = jepa_prior_projected.shape[1]
                                    if _T_pred >= _T:
                                        jepa_prior_expanded = jepa_prior_projected[:, :_T, :]
                                    else:
                                        _pad = jepa_prior_projected[:, -1:, :].expand(-1, _T - _T_pred, -1)
                                        jepa_prior_expanded = torch.cat([jepa_prior_projected, _pad], dim=1)
                                else:
                                    # Summary: broadcast to all positions
                                    jepa_prior_expanded = jepa_prior_projected.unsqueeze(1).expand(
                                        -1, _T, -1
                                    )
                                bliss_priors['jepa'] = jepa_prior_expanded.detach()

                        # Build Kosha router weights if available
                        bliss_router_weights = None
                        try:
                            if 'kosha_means' in dir() and kosha_means:
                                # Map Kosha sheath activations to prior routing weights
                                # Physical/Material sheath → acoustic/CSR affinity
                                # Intellectual/Vijnana sheath → predictive/JEPA affinity
                                _csr_kosha_w = kosha_means.get('physical', 0.5)
                                bliss_router_weights = {'csr': _csr_kosha_w}
                                if 'jepa' in bliss_priors:
                                    _jepa_kosha_w = kosha_means.get('intellectual', 0.5)
                                    bliss_router_weights['jepa'] = _jepa_kosha_w
                        except (NameError, AttributeError):
                            pass

                        if bliss_priors:
                            bliss_metrics = bliss_functional.compute(
                                [h.detach() for h in layer_hs],
                                bliss_priors,
                                router_weights=bliss_router_weights,
                            )
                            metrics['bliss_B'] = bliss_metrics.B
                            metrics['bliss_B_A'] = bliss_metrics.B_A_mean
                            metrics['bliss_B_B'] = bliss_metrics.B_B

                            # Phase 3/4: Compute gated λ_eff for all active priors
                            # Uses sigmoid gate: λ_eff = λ · (λ_min + (1-λ_min) · σ(γ·(B−τ)))
                            # Dead channel alerts are logged automatically by compute_lambda_eff
                            if config.enable_bliss_gating:
                                base_lambdas = {'csr': config.csr_lambda}
                                if config.enable_jepa_injection and 'jepa' in bliss_priors:
                                    base_lambdas['jepa'] = config.jepa_injection_lambda

                                lambda_eff = bliss_functional.compute_lambda_eff(
                                    bliss_metrics.B,
                                    base_lambdas,
                                )
                                bliss_lambda_eff_csr = lambda_eff.get('csr', config.csr_lambda)
                                metrics['bliss_lambda_eff_csr'] = bliss_lambda_eff_csr

                                if config.enable_jepa_injection:
                                    bliss_lambda_eff_jepa = lambda_eff.get(
                                        'jepa', config.jepa_injection_lambda
                                    )
                                    metrics['bliss_lambda_eff_jepa'] = bliss_lambda_eff_jepa

                            # Log at interval
                            if global_step % config.bliss_log_interval == 0 and global_step > 0:
                                cos_str = ', '.join(
                                    f'{k}={v:.4f}' for k, v in bliss_metrics.cosine_per_prior.items()
                                )
                                if config.enable_bliss_gating and bliss_lambda_eff_csr is not None:
                                    gate_ratio = bliss_lambda_eff_csr / max(config.csr_lambda, 1e-8)
                                    _bliss_log = (
                                        f"  [Bliss] B={bliss_metrics.B:.4f} "
                                        f"(A={bliss_metrics.B_A_mean:.4f}, B={bliss_metrics.B_B:.4f}) "
                                        f"tau={bliss_functional.tau:.4f} | {cos_str} | "
                                        f"csr={bliss_lambda_eff_csr:.4f} ({gate_ratio:.1%})"
                                    )
                                    if bliss_lambda_eff_jepa is not None:
                                        jepa_gate_ratio = bliss_lambda_eff_jepa / max(
                                            config.jepa_injection_lambda, 1e-8
                                        )
                                        _bliss_log += f" | jepa={bliss_lambda_eff_jepa:.4f} ({jepa_gate_ratio:.1%})"
                                    print(_bliss_log, flush=True)
                                else:
                                    print(f"  [Bliss] B={bliss_metrics.B:.4f} "
                                          f"(A={bliss_metrics.B_A_mean:.4f}, B={bliss_metrics.B_B:.4f}) "
                                          f"tau={bliss_functional.tau:.4f} | {cos_str}", flush=True)

                        # 12D Health Monitor: check onto_bridge projection weight
                        if ontology_health_monitor is not None and onto_bridge is not None:
                            proj_weight = None
                            if hasattr(onto_bridge, 'projection'):
                                proj_weight = onto_bridge.projection.weight
                            elif hasattr(onto_bridge, 'layer_proj'):
                                proj_weight = onto_bridge.layer_proj.weight

                            if proj_weight is not None:
                                # Get 12D output for variance check
                                onto_12d = None
                                if 'onto_repr' in dir() and onto_repr is not None:
                                    onto_12d = onto_repr.get('layer_scores') if isinstance(onto_repr, dict) else onto_repr

                                health = ontology_health_monitor.check(proj_weight, onto_12d)
                                if health and health.get('alerts'):
                                    for alert in health['alerts']:
                                        print(f"  [12D ALERT] {alert}", flush=True)
                                if health and global_step % config.bliss_log_interval == 0 and global_step > 0:
                                    min_sv = health.get('min_sv', 0)
                                    metrics['12d_min_sv'] = min_sv
                                    if 'axis_variance' in health:
                                        min_var = min(health['axis_variance'])
                                        metrics['12d_min_var'] = min_var
                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  [Bliss] Measurement error: {e}", flush=True)

            # Initialize default guna values for first iteration
            # (actual values computed later in the loop, but needed here for evolutionary bridge)
            try:
                _ = guna_s
            except NameError:
                guna_s, guna_r, guna_t = 0.33, 0.33, 0.34

            # Toroidal Evolutionary Bridge: O12 → O1 state carryover
            #
            # V9.6.7 CRITICAL FIX: DETACH hidden states for Toroidal bridge!
            # Without detach, toroid_loss gradients flow: o12_state → Layer 11 → ... → token embeddings
            # This was ANOTHER source of vocabulary corruption alongside CSR!
            if evolutionary_bridge is not None:
                # Extract hidden states for O1 (first layer) and O12 (last layer)
                # Different model types store hidden states differently
                hidden_states = None
                if isinstance(outputs, dict):
                    hidden_states = outputs.get('hidden_states', outputs.get('all_hidden_states'))
                    if hidden_states is None and 'last_hidden_state' in outputs:
                        # Use last hidden state as O12 approximation
                        hidden_states = outputs['last_hidden_state']

                if hidden_states is not None:
                    # V9.8.0: RSS controls Toroidal gradient engagement
                    toroidal_should_engage = False
                    if config.enable_rss:
                        toroidal_should_engage = rss_weights['toroidal'] > 0

                    # Get O12 (harvest) - either last element of list or the tensor itself
                    if isinstance(hidden_states, (list, tuple)) and len(hidden_states) > 0:
                        if toroidal_should_engage:
                            # RSS engaged - let gradients flow
                            o12_state = hidden_states[-1]
                            o1_state = hidden_states[0] if len(hidden_states) > 1 else o12_state
                        else:
                            # V9.6.7: DETACH to prevent gradient flow to model!
                            o12_state = hidden_states[-1].detach()
                            o1_state = hidden_states[0].detach() if len(hidden_states) > 1 else o12_state
                    else:
                        if toroidal_should_engage:
                            o12_state = hidden_states
                            o1_state = hidden_states
                        else:
                            # V9.6.7: DETACH to prevent gradient flow!
                            o12_state = hidden_states.detach()
                            o1_state = hidden_states.detach()

                    # Compute toroidal coherence if we have a prior seed
                    if toroidal_seed is not None:
                        toroidal_coherence = evolutionary_bridge.compute_toroidal_coherence(
                            o1_state, toroidal_seed
                        )

                        # Compute toroidal loss
                        # V9.6.7: With detached states, this loss only trains the bridge, not the model
                        toroid_loss, toroid_metrics = toroidal_loss_fn(
                            seed=toroidal_seed,
                            harvest=o12_state,
                            o1_current=o1_state,
                        )
                        loss = loss + toroid_loss
                        toroidal_loss_value = toroid_metrics['toroid_loss']

                        # V9.4.6: Shadow Mirror Alignment (SMA) - Lite Meta-Learning
                        # Trains bridge weights (seed_proj, seed_gate) to predict actual O1 state
                        # Uses active_projection (non-detached) for proper gradient flow to bridge
                        # Zero VRAM overhead, achieves meta-learning without BPTT risks
                        sma_weight = 0.05
                        o1_target = o1_state  # Already detached above in V9.6.7
                        if o1_target.dim() == 3:
                            o1_target = o1_target.mean(dim=1)  # [B, N, dim] → [B, dim]

                        # Use active_projection for gradient flow (not detached toroidal_seed)
                        seed_for_sma = evolutionary_bridge.active_projection
                        if seed_for_sma is not None:
                            if seed_for_sma.dim() == 3:
                                seed_for_sma = seed_for_sma.mean(dim=1)
                            # MSE loss: bridge learns to project O12 → O1 accurately
                            sma_loss = F.mse_loss(seed_for_sma, o1_target) * sma_weight
                            loss = loss + sma_loss
                            metrics['sma_loss'] = sma_loss.item()

                        # Update metacognitive tracker
                        if metacognitive_tracker is not None:
                            meta_assessment = metacognitive_tracker.update(
                                coherence=toroidal_coherence,
                                gunas=(guna_s, guna_r, guna_t) if training_gunas else None,
                            )

                    # Store harvest for next cycle (becomes next seed)
                    # V9.4.7: Pass global_step for SGP rate calculation
                    is_sgp_heavy_step = evolutionary_bridge.store_harvest(o12_state, global_step=global_step)
                    toroidal_seed = evolutionary_bridge.get_seed()

                    # Log SGP heavy step (recursive gradient pulse)
                    if is_sgp_heavy_step and global_step % config.log_every == 0:
                        print(f"  🌀 [SGP-HEAVY] Recursive Gradient Pulse at Step {global_step}")
                    metrics['sgp_heavy_step'] = is_sgp_heavy_step

            # Full Evolutionary Flow System: All Layer Transitions with Delayed Resonance
            #
            # V9.6.7 CRITICAL FIX: DETACH hidden states for EvoFlow!
            # Without detach, evo_loss gradients flow: hidden_states → all layers → token embeddings
            # This was a MAJOR source of vocabulary corruption alongside CSR and Toroidal!
            evo_result = None
            evo_lr_multiplier = 1.0
            # Note: guna_s/r/t initialized earlier in the loop (before evolutionary_bridge section)
            if evolutionary_engine is not None and hidden_state_extractor is not None:
                # Extract hidden states using HiddenStateExtractor (handles models without hidden_states output)
                # Note: clear() was called before forward pass, hooks captured states during model(x)
                hidden_states = hidden_state_extractor.get_hidden_states(outputs, x)

                if hidden_states is not None and len(hidden_states) > 0:
                    # V9.8.0: RSS takes precedence over individual fluency gate
                    evo_should_engage = False
                    if config.enable_rss:
                        # RSS mode: Use RSS weight for engagement decision
                        evo_should_engage = rss_weights['evoflow'] > 0
                        if evo_should_engage and not evo_fluency_engaged:
                            evo_fluency_engaged = True
                            print(f"🔄 [RSS] EvoFlow Gradients ENGAGED! (Phase: {rss_controller.current_phase})")
                    else:
                        # V9.7.0: Legacy EvoFlow Fluency Gate
                        if config.evo_fluency_gate and not evo_fluency_engaged:
                            if global_step >= config.evo_fluency_min_steps and last_val_ppl < config.evo_fluency_ppl_threshold:
                                evo_fluency_engaged = True
                                print(f"🚀 [FLUENCY GATE] EvoFlow Gradients ENGAGED! (Step {global_step}, PPL {last_val_ppl:.2f} < {config.evo_fluency_ppl_threshold})")
                        evo_should_engage = config.evo_fluency_gate and evo_fluency_engaged

                    # V9.6.7/V9.7.0/V9.8.0: Conditionally detach hidden states
                    if evo_should_engage:
                        # Fluency achieved - let gradients flow to main model
                        hidden_states_detached = hidden_states  # No detach - gradients flow
                    else:
                        # V9.6.7: DETACH all hidden states to prevent gradient flow!
                        # This ensures EvoFlow only monitors layer coherence, doesn't corrupt the model
                        hidden_states_detached = [h.detach() if h is not None else None for h in hidden_states]

                    # V9.4.6: Sensory Noise Injection (SNI) - DISABLED in V9.6.7
                    # SNI modifies hidden states in-place which can cause gradient issues
                    # With detached states, SNI would have no effect anyway
                    current_entropy = metrics.get("onto_entropy", 1.0)
                    metrics['sni_triggered'] = False  # Disabled

                    # Update Gunas in engine for metacognitive decisions
                    evolutionary_engine.update_gunas(guna_s, guna_r, guna_t)

                    # Process through evolutionary system with delayed resonance
                    # V9.6.7: Use detached states - EvoFlow becomes monitor-only
                    evo_result = evolutionary_engine.process(
                        layer_states=hidden_states_detached,
                        compute_loss=True,
                        apply_resonance=True,
                    )

                    # Add evolutionary loss to total
                    # V9.6.7: With detached states, this only trains EvoFlow's internal weights, not the model
                    if 'loss' in evo_result:
                        evo_loss = config.evo_lambda * evo_result['loss']
                        loss = loss + evo_loss

                    # Get LR multiplier from metacognitive assessment
                    evo_lr_multiplier = evo_result.get('lr_multiplier', 1.0)

                    # Store metrics for logging
                    metrics['evo_micro'] = evo_result['flow_result']['micro_coherence_mean']
                    metrics['evo_auth'] = evo_result['flow_result']['authority_coherence']
                    metrics['evo_sens'] = evo_result['flow_result']['sensory_coherence']
                    metrics['evo_toroid'] = evo_result['flow_result']['toroidal_coherence']
                    metrics['evo_rec'] = evo_result['metacognitive']['recommendation']

            # V9.5.1 Entropy Floor Penalty (breaks repetition curse)
            if config.enable_entropy_floor and 'onto_entropy' in metrics:
                current_entropy = metrics['onto_entropy']
                if current_entropy < config.entropy_floor:
                    # Penalize low entropy to encourage diversity
                    entropy_deficit = config.entropy_floor - current_entropy
                    entropy_floor_loss = config.entropy_floor_weight * entropy_deficit
                    loss = loss + entropy_floor_loss
                    metrics['entropy_floor_penalty'] = entropy_floor_loss

            # =====================================================================
            # KOSHA PHASE STEERING: Active Intervention for Mind-Body Alignment
            # Couples Entity State (Entropy/Gradients) to Representation (Embeddings)
            # =====================================================================
            kosha_steering_loss = 0.0
            # V9.8.0: RSS controls Kosha engagement based on PPL thresholds
            kosha_should_engage = config.enable_kosha_steering and global_step >= config.kosha_steering_warmup
            if config.enable_rss:
                # RSS mode: Only engage when RSS says so (after CSR settles)
                kosha_should_engage = kosha_should_engage and rss_weights['kosha'] > 0
            if kosha_should_engage:
                try:
                    # Compute Reality (r) and Time (t) axes from current state
                    if config.model_type in ("ontological", "ontological_hybrid"):
                        kosha_logits_for_steering = outputs.get("logits", None) if isinstance(outputs, dict) else None
                    else:
                        kosha_logits_for_steering = logits if 'logits' in dir() else None

                    if kosha_logits_for_steering is not None:
                        # Compute entropy (Reality axis)
                        with torch.no_grad():
                            steering_probs = F.softmax(kosha_logits_for_steering.float(), dim=-1)
                            steering_log_probs = torch.log(steering_probs + 1e-10)
                            steering_entropy = -(steering_probs * steering_log_probs).sum(dim=-1).mean()
                            r_axis = 1.0 - (2.0 * steering_entropy.item() / 10.0)
                            r_axis = max(-1.0, min(1.0, r_axis))

                        # Get gradient norm (Time axis) - use captured value
                        # V9.8.5: SIGN FIX - Documentation states:
                        #   High gradient → Future (-T) = Dynamic, projecting
                        #   Low gradient  → Past (+T)   = Static, repeating
                        # Original code had this inverted. Negating to match doc.
                        t_axis_grad = captured_grad_norm if 'captured_grad_norm' in dir() else 1.0
                        if t_axis_grad > 0:
                            t_axis = -math.log(t_axis_grad + 1e-8) / 2.3  # Negated!
                            t_axis = max(-1.0, min(1.0, t_axis))
                        else:
                            t_axis = 0.0

                        # Compute target angle in radians
                        target_angle_rad = math.atan2(t_axis, r_axis)

                        # Get embeddings to steer (use configurable hidden state layer)
                        if hidden_state_extractor is not None:
                            steering_hidden_states = hidden_state_extractor.get_hidden_states(outputs, x)
                            steer_layer = config.kosha_steering_layer
                            if steering_hidden_states is not None and len(steering_hidden_states) > steer_layer:
                                # V9.7.0: Use configurable layer (default 4 = grammar forming)
                                layer_to_steer = steering_hidden_states[steer_layer]

                                # Compute phase alignment loss
                                # Penalize deviation from target angle
                                D = layer_to_steer.shape[-1]
                                if D % 2 == 0:
                                    emb_pairs = layer_to_steer.view(*layer_to_steer.shape[:-1], D // 2, 2)
                                    real = emb_pairs[..., 0]
                                    imag = emb_pairs[..., 1]
                                    current_phase = torch.atan2(imag, real)

                                    # Phase error: distance from target
                                    phase_error = target_angle_rad - current_phase
                                    # Wrap to [-π, π]
                                    phase_error = torch.atan2(torch.sin(phase_error), torch.cos(phase_error))

                                    # Steering loss: encourage phase alignment
                                    # Use L2 loss scaled by steering force
                                    kosha_steering_loss = (phase_error ** 2).mean() * config.kosha_steering_force

                                    # V9.8.6: Apply three-phase curriculum scaling
                                    kosha_scale = kosha_curriculum.scale if kosha_curriculum is not None else 1.0
                                    kosha_steering_scaled = kosha_steering_loss * kosha_scale

                                    # Add to total loss (this creates gradient pressure toward target angle)
                                    loss = loss + kosha_steering_scaled

                                    # Log steering metrics
                                    metrics['kosha_steering_loss'] = kosha_steering_loss.item()
                                    metrics['kosha_steering_scaled'] = kosha_steering_scaled.item()
                                    metrics['kosha_curriculum_scale'] = kosha_scale
                                    metrics['kosha_target_angle'] = math.degrees(target_angle_rad)
                                    metrics['kosha_mean_phase'] = math.degrees(current_phase.mean().item())
                                    metrics['kosha_phase_error'] = math.degrees(phase_error.abs().mean().item())

                                    # One-time log when steering activates
                                    if not hasattr(model, '_kosha_steering_logged'):
                                        model._kosha_steering_logged = True
                                        layer_desc = {2: "Raw Embeddings", 4: "Grammar Forming", 6: "Semantic", 7: "Consolidation"}.get(steer_layer, "Custom")
                                        print(f"\n  🎯 [KOSHA STEERING] Activated at step {global_step}")
                                        print(f"     Force: {config.kosha_steering_force:.2f}")
                                        print(f"     Layer: {steer_layer} ({layer_desc})")
                                        print(f"     Target: Geometric Truth from atan2(t, r)")

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  ⚠️ [KOSHA STEERING] Error: {e}")

            # =====================================================================
            # v2.2.1: KOSHA GYROSCOPE - Homeostatic Self-Regulation Loss
            # Enforces balance across Kosha dimensions to prevent pathological states
            # Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md
            # =====================================================================
            gyroscope_loss = 0.0
            gyroscope_components = {}
            if kosha_gyroscope is not None and not kosha_graduated:
                try:
                    # Get warmup scale (ramps from 0 to 1 over warmup_steps)
                    if kosha_curriculum_controller is not None:
                        warmup_scale = kosha_curriculum_controller.get_gyroscope_scale(global_step)
                    else:
                        warmup_scale = min(1.0, global_step / config.gyroscope_warmup_steps)

                    if warmup_scale > 0:
                        # Extract Kosha states from model outputs
                        kosha_states_for_gyro = None

                        if config.model_type in ("ontological", "ontological_hybrid"):
                            sovereign_state = outputs.get('state', None) if isinstance(outputs, dict) else None
                            if sovereign_state is not None:
                                # Extract Kosha [12:17] from 32D sovereign state
                                # Handle both 2D [batch, 32] and 3D [batch, seq, 32] shapes
                                if sovereign_state.dim() == 2:
                                    # Shape: [batch, 32] -> [batch, 1, 5]
                                    kosha_states_for_gyro = sovereign_state[:, KOSHA_SLICE].unsqueeze(1)
                                else:
                                    # Shape: [batch, seq, 32] -> [batch, seq, 5]
                                    kosha_states_for_gyro = sovereign_state[:, :, KOSHA_SLICE]

                        if kosha_states_for_gyro is not None:
                            # Compute gyroscope loss with dynamic gain based on current PPL
                            current_ppl = best_ppl if best_ppl < float('inf') else None

                            # v2.2.4: Get authority factor from PIDv2 controller if available
                            # This enables real-time feedback control of gyroscope gain
                            auth_factor = authority_controller.A if authority_controller is not None else None

                            # V9.8.5: Pass toroidal coherence for Vital-Coherence coupling
                            coherence_for_gyro = toroidal_coherence if 'toroidal_coherence' in dir() else None

                            gyro_loss, gyroscope_components = kosha_gyroscope(
                                kosha_states_for_gyro,
                                current_ppl=current_ppl,
                                return_components=True,
                                authority_factor=auth_factor,
                                coherence=coherence_for_gyro,
                            )

                            # Apply warmup scaling
                            gyroscope_loss = gyro_loss * warmup_scale

                            # V9.8.6: Apply three-phase curriculum scaling
                            kosha_gyro_scale = kosha_curriculum.scale if kosha_curriculum is not None else 1.0
                            gyroscope_loss_scaled = gyroscope_loss * kosha_gyro_scale

                            # Add to total loss
                            loss = loss + gyroscope_loss_scaled

                            # Log gyroscope metrics
                            metrics['gyroscope_loss'] = gyroscope_loss_scaled.item()
                            metrics['gyroscope_loss_unscaled'] = gyroscope_loss.item()
                            metrics['gyroscope_curriculum_scale'] = kosha_gyro_scale
                            metrics['gyroscope_effective_gain'] = gyroscope_components.get('effective_gain', 0.0)
                            metrics['gyroscope_base_gain'] = gyroscope_components.get('base_dynamic_gain', 0.0)
                            metrics['gyroscope_authority_factor'] = gyroscope_components.get('authority_factor', 1.0)
                            metrics['gyroscope_axis1_loss'] = gyroscope_components.get('axis1_loss', 0.0)
                            metrics['gyroscope_axis2_loss'] = gyroscope_components.get('axis2_loss', 0.0)
                            metrics['gyroscope_warmup_scale'] = warmup_scale
                            # v2.2.4 diagnostic: trap detection values
                            metrics['gyroscope_mental_trap'] = gyroscope_components.get('mental_trap_mean', 0.0)
                            metrics['gyroscope_physical_trap'] = gyroscope_components.get('physical_trap_mean', 0.0)
                            # v2.2.5: Capture all 5 Kosha values for Fibonacci Pentad logging
                            kosha_means = gyroscope_components.get('kosha_means', {})
                            metrics['gyroscope_mental_val'] = kosha_means.get('mental', 0.0)
                            metrics['gyroscope_physical_val'] = kosha_means.get('physical', 0.0)
                            metrics['gyroscope_intellect_val'] = kosha_means.get('intellect', 0.0)
                            metrics['gyroscope_vital_val'] = kosha_means.get('vital', 0.0)
                            metrics['gyroscope_bliss_val'] = kosha_means.get('bliss', 0.0)
                            # v2.3.0: Harmonic Pentad metrics
                            metrics['gyroscope_floor_violations'] = gyroscope_components.get('floor_violations_count', 0)
                            metrics['gyroscope_ceiling_violations'] = gyroscope_components.get('ceiling_violations_count', 0)
                            metrics['gyroscope_ceiling_clamp_scalar'] = gyroscope_components.get('ceiling_clamp_scalar', 1.0)
                            metrics['gyroscope_floor_push_loss'] = gyroscope_components.get('floor_push_loss', 0.0)
                            metrics['gyroscope_intellect_hubris_loss'] = gyroscope_components.get('intellect_hubris_loss', 0.0)
                            metrics['gyroscope_vital_momentum_boost'] = gyroscope_components.get('vital_momentum_boost', 1.0)
                            # v2.3.2: Reflexive Domain Morph metrics
                            metrics['gyroscope_domain_label'] = gyroscope_components.get('domain_label', 'LANG')
                            metrics['gyroscope_morph_factor'] = gyroscope_components.get('morph_factor', 0.0)
                            metrics['gyroscope_curr_phys_floor'] = gyroscope_components.get('curr_phys_floor', config.gyroscope_floor_physical)
                            metrics['gyroscope_curr_bliss_ceil'] = gyroscope_components.get('curr_bliss_ceil', config.gyroscope_ceiling_bliss)
                            metrics['gyroscope_curr_push_weight'] = gyroscope_components.get('curr_push_weight', 3.0)

                            # Capture Reality Rips for diagnostic logging
                            if kosha_rip_logger is not None:
                                rip_captured = kosha_rip_logger.capture_rip(
                                    step=global_step,
                                    tokens=x,
                                    kosha_states=kosha_states_for_gyro,
                                    loss_value=gyroscope_loss.item(),
                                    loss_components=gyroscope_components,
                                )
                                if rip_captured and global_step % 100 == 0:
                                    status = kosha_rip_logger.format_status_line()
                                    print(f"  ⚡ [REALITY RIP] {status}")

                            # Log activation periodically
                            if global_step == config.gyroscope_warmup_steps:
                                print(f"\n  ⚖️ [KOSHA GYROSCOPE] Fully active at step {global_step}")
                                print(f"     Dynamic Gain: {gyroscope_components.get('effective_gain', 0):.3f}")
                                print(f"     PPL: {current_ppl if current_ppl else 'N/A'}")

                            # v2.3.0: Compute Vritti Resonance (Phase 2 loss + Phase 1 diagnostics)
                            if vritti_resonance is not None:
                                # Extract Vritti states from 32D sovereign state [17:22]
                                vritti_states_for_res = None
                                if sovereign_state is not None:
                                    if sovereign_state.dim() == 2:
                                        vritti_states_for_res = sovereign_state[:, VRITTI_SLICE].unsqueeze(1)
                                    else:
                                        vritti_states_for_res = sovereign_state[:, :, VRITTI_SLICE]

                                if vritti_states_for_res is not None:
                                    # Compute Kosha-Vritti alignment (diagnostic logging)
                                    alignment = vritti_resonance.compute_alignment_scores(
                                        kosha_states_for_gyro, vritti_states_for_res
                                    )
                                    metrics['vritti_alignment'] = alignment

                                    # Phase 2: Apply resonance loss if graduated
                                    if vritti_resonance.active:
                                        res_loss, res_components = vritti_resonance(
                                            kosha_states_for_gyro, vritti_states_for_res,
                                            return_components=True
                                        )
                                        loss = loss + res_loss
                                        metrics['vritti_resonance_loss'] = res_loss.item()
                                        metrics['vritti_components'] = res_components

                                    # === DIFFERENTIABLE ALIGNMENT LOSS (P-Pram Fix) ===
                                    # Fixes inverted Kosha-Vritti correlations (e.g., P-Pram at -0.98)
                                    # by adding gradient flow through Pearson correlation
                                    alignment_loss, alignment_diag = vritti_resonance.compute_alignment_loss(
                                        kosha_states_for_gyro, vritti_states_for_res,
                                        lambda_scale=0.3,  # Moderate pressure to fix inversion
                                    )
                                    loss = loss + alignment_loss
                                    metrics['alignment_loss'] = alignment_diag.get('alignment_loss_total', 0.0)
                                    metrics['p_pram_corr'] = alignment_diag.get('p_pram_corr', 0.0)
                                    metrics['p_pram_loss'] = alignment_diag.get('p_pram_loss', 0.0)

                                    # Log other alignment correlations
                                    metrics['intellect_smriti_corr'] = alignment_diag.get('intellect_smriti_corr', 0.0)
                                    metrics['bliss_viparyaya_corr'] = alignment_diag.get('bliss_viparyaya_corr', 0.0)
                                    metrics['mental_vikalpa_corr'] = alignment_diag.get('mental_vikalpa_corr', 0.0)
                                    metrics['vital_nidra_corr'] = alignment_diag.get('vital_nidra_corr', 0.0)

                                # V10.3.7: Vritti entropy regularization to prevent collapse
                                if config.vritti_entropy_reg and vritti_states_for_res is not None:
                                    # vritti_states_for_res shape: [B, seq, 5] or [B, 1, 5]
                                    # Apply softmax if not already normalized
                                    vritti_probs = F.softmax(vritti_states_for_res, dim=-1)
                                    eps = 1e-8
                                    # Compute entropy: H = -Σ p*log(p)
                                    vritti_entropy = -(vritti_probs * torch.log(vritti_probs + eps)).sum(dim=-1)
                                    # Average over batch and sequence
                                    mean_entropy = vritti_entropy.mean()
                                    # We want to MAXIMIZE entropy, so subtract from loss (or add negative)
                                    entropy_loss = -config.vritti_entropy_lambda * mean_entropy
                                    loss = loss + entropy_loss
                                    # Log metrics
                                    max_entropy = math.log(5)  # log(5) ≈ 1.609
                                    metrics['vritti_entropy'] = mean_entropy.item()
                                    metrics['vritti_entropy_norm'] = mean_entropy.item() / max_entropy
                                    metrics['vritti_entropy_loss'] = entropy_loss.item()

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  ⚠️ [KOSHA GYROSCOPE] Error: {e}")

            # =====================================================================
            # v2.3.3: 32D SOVEREIGN STATE REGULARIZER - Anti-Saturation
            # Prevents VIT(100%)>BLI(100%) collapse in 32D space
            # The 5D Gyroscope can't fix this - it operates on extracted projections
            # =====================================================================
            state_reg_loss = 0.0
            if state_regularizer is not None:
                try:
                    # Get 32D sovereign state (already extracted for gyroscope above)
                    sovereign_state_for_reg = None
                    if config.model_type in ("ontological", "ontological_hybrid"):
                        sovereign_state_for_reg = outputs.get('state', None) if isinstance(outputs, dict) else None

                    if sovereign_state_for_reg is not None:
                        # Compute regularization loss
                        reg_loss, reg_diagnostics = state_regularizer(
                            sovereign_state_for_reg,
                            return_components=True,
                        )
                        state_reg_loss = reg_loss

                        # Add to total loss
                        loss = loss + state_reg_loss

                        # Log regularizer metrics
                        metrics['state_reg_loss'] = state_reg_loss.item()
                        metrics['state_reg_anti_sat_kosha'] = reg_diagnostics.get('anti_saturation', {}).get('kosha', 0.0)
                        metrics['state_reg_variance_kosha'] = reg_diagnostics.get('variance', {}).get('kosha', 0.0)
                        metrics['state_reg_saturation_alerts'] = reg_diagnostics.get('saturation_alerts', [])

                        # One-time log when regularizer activates
                        if global_step == 1 and not hasattr(model, '_state_reg_logged'):
                            model._state_reg_logged = True
                            summary = state_regularizer.get_summary(sovereign_state_for_reg)
                            print(f"\n  🛡️ [32D REGULARIZER] Active: {summary}")

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  ⚠️ [32D REGULARIZER] Error: {e}")

            # =====================================================================
            # BCVF Contrastive Structural Pressure on Representations
            # Adds L_rep to total loss — shapes hidden-state geometry
            # =====================================================================
            if bcvf_contrastive_head is not None and bcvf_contrastive_config is not None:
                try:
                    # Get hidden states
                    bcvf_h = None
                    if bcvf_hidden_hook is not None:
                        bcvf_h = bcvf_hidden_hook.get()

                    # Get logits
                    bcvf_logits = None
                    if isinstance(outputs, dict):
                        bcvf_logits = outputs.get('logits', outputs.get('output'))
                    elif isinstance(outputs, torch.Tensor):
                        bcvf_logits = outputs
                    # Handle case where logits was separately extracted
                    if bcvf_logits is None and 'logits' in dir():
                        bcvf_logits = logits

                    if bcvf_h is not None and bcvf_logits is not None and bcvf_h.dim() == 3 and bcvf_logits.dim() == 3:
                        # Get token embeddings
                        bcvf_tok_emb = get_token_embedding_weight(model)
                        if bcvf_tok_emb is None:
                            # Fallback: try lm_head weight (tied embeddings)
                            for _n, _m in model.named_modules():
                                if 'lm_head' in _n and isinstance(_m, nn.Linear):
                                    bcvf_tok_emb = _m.weight.detach()
                                    break

                        if bcvf_tok_emb is not None:
                            rep_loss, rep_diag = compute_bcvf_contrastive_loss(
                                h_all=bcvf_h,
                                logits_all=bcvf_logits.detach() if bcvf_logits.requires_grad else bcvf_logits,
                                labels=y,
                                contrastive_head=bcvf_contrastive_head,
                                token_embeddings=bcvf_tok_emb,
                                config=bcvf_contrastive_config,
                                sampler=bcvf_contrastive_sampler,
                            )

                            # Add weighted contrastive loss
                            loss = loss + bcvf_contrastive_config.lambda_rep * rep_loss

                            # Log diagnostics
                            for k, v in rep_diag.items():
                                if isinstance(v, (int, float)):
                                    metrics[k] = v

                            log_bcvf_contrastive_diagnostics(
                                rep_diag, global_step,
                                writer=writer if TENSORBOARD_AVAILABLE and 'writer' in dir() else None,
                                print_every=config.log_every,
                            )

                    # Clear hook state for next step
                    if bcvf_hidden_hook is not None:
                        bcvf_hidden_hook.clear()

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  [BCVF-REP] Error at step {global_step}: {e}")

            # =====================================================================
            # BCVF Logit-Margin + Entropy Band (perplexity-aligned)
            # Directly improves token likelihood via logit gap pressure
            # =====================================================================
            if logit_margin_config is not None:
                try:
                    # Get logits for this step
                    lm_logits = None
                    if isinstance(outputs, dict):
                        lm_logits = outputs.get('logits', outputs.get('output'))
                    elif isinstance(outputs, torch.Tensor):
                        lm_logits = outputs
                    if lm_logits is None and 'logits' in dir():
                        lm_logits = logits

                    if lm_logits is not None and lm_logits.dim() == 3:
                        lm_margin_loss, lm_entropy_loss, lm_diag = compute_logit_margin_loss(
                            logits=lm_logits,
                            targets=y,
                            config=logit_margin_config,
                        )

                        # Add to total loss
                        loss = loss + logit_margin_config.lambda_margin * lm_margin_loss
                        loss = loss + logit_margin_config.lambda_entropy * lm_entropy_loss

                        # Log diagnostics
                        for k, v in lm_diag.items():
                            if isinstance(v, (int, float)):
                                metrics[k] = v

                        log_logit_margin_diagnostics(
                            lm_diag, global_step,
                            writer=writer if TENSORBOARD_AVAILABLE and 'writer' in dir() else None,
                            print_every=config.log_every,
                        )

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  [BCVF-LM] Error at step {global_step}: {e}")

            # =====================================================================
            # KOSHA-VRITTI STRUCTURED SUPERVISION
            # Adds auxiliary KL + entropy floor + compatibility losses
            # Does NOT modify transformer blocks
            # =====================================================================
            if kv_supervisor is not None:
                try:
                    # Extract hidden states for KV supervision
                    kv_hidden = None
                    if hidden_state_extractor is not None:
                        kv_layer_states = hidden_state_extractor.get_hidden_states(outputs, x)
                        if kv_layer_states is not None and len(kv_layer_states) > 0:
                            kv_hidden = kv_layer_states[-1]  # Last layer hidden states

                    # Fallback: try to get from model outputs dict
                    if kv_hidden is None and isinstance(outputs, dict):
                        kv_hidden = outputs.get('hidden_states', None)
                        if kv_hidden is None:
                            kv_hidden = outputs.get('last_hidden_state', None)

                    if kv_hidden is not None and kv_hidden.dim() == 3:
                        # Compute epoch for curriculum
                        kv_epoch = global_step // max(len(train_loader), 1)

                        # DDP info
                        kv_rank = int(os.environ.get('RANK', 0))
                        kv_world_size = int(os.environ.get('WORLD_SIZE', 1))

                        # Detach hidden states — KV supervision is auxiliary-only,
                        # it should NOT backprop through the transformer backbone
                        kv_hidden_detached = kv_hidden.detach()

                        kv_loss, kv_metrics = kv_supervisor.step(
                            hidden_states=kv_hidden_detached,
                            input_ids=x,
                            epoch=kv_epoch,
                            global_step=global_step,
                            rank=kv_rank,
                            world_size=kv_world_size,
                        )

                        # Add to total loss (only auxiliary head gradients flow)
                        loss = loss + kv_loss

                        # Merge metrics
                        metrics.update(kv_metrics)

                        # Log periodically
                        if KV_SUPERVISION_AVAILABLE:
                            writer_ref = writer if TENSORBOARD_AVAILABLE and 'writer' in dir() else None
                            log_kv_metrics(
                                kv_metrics, global_step,
                                writer=writer_ref,
                                print_every=config.log_every,
                                rank=kv_rank,
                            )

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  [KV-SUPERVISION] Error at step {global_step}: {e}")

            # =====================================================================
            # STATE-CONDITIONAL LOGIT SCALE ("Confidence Knob") + ENTROPY BAND
            # Per-token s_t scales logits to eliminate calibration artifacts.
            # Does NOT modify transformer blocks -- emission path only.
            # =====================================================================
            if confidence_scaler is not None:
                try:
                    # Extract hidden states and logits
                    cs_hidden = None
                    cs_logits = None

                    if isinstance(outputs, dict):
                        cs_hidden = outputs.get('last_hidden_state', outputs.get('hidden_states', None))
                        cs_logits = outputs.get('logits', outputs.get('output', None))
                    elif isinstance(outputs, torch.Tensor):
                        cs_logits = outputs  # For models that return logits directly

                    # If we have both hidden states and logits, apply confidence scaling
                    if cs_hidden is not None and cs_logits is not None and cs_hidden.dim() == 3:
                        # Compute risk probability from Vritti head (if enabled)
                        cs_risk_prob = None
                        cs_vritti_loss = torch.tensor(0.0, device=device)
                        if vritti_risk_head is not None:
                            vritti_out = vritti_risk_head(cs_hidden.detach())
                            cs_risk_prob = vritti_out['risk_prob']

                            # If KV supervision provides teacher labels, train Vritti head
                            if kv_supervisor is not None and 'kv_vritti_freq_Viparyaya' in metrics:
                                # Use KV supervisor's teacher as reference (if available)
                                pass  # Vritti head trains from its own gradient through risk gating

                        # Scale logits
                        cs_logits_scaled, cs_s, cs_diag = confidence_scaler.scale_logits(
                            cs_logits, cs_hidden, cs_risk_prob,
                        )

                        # Compute entropy band + scale penalty losses
                        cs_band_loss, cs_band_metrics = entropy_band_loss(
                            cs_logits_scaled, cs_s,
                            targets=y,
                        )

                        # Add auxiliary losses to total
                        loss = loss + cs_band_loss

                        # Compute and log calibration diagnostics
                        if global_step % config.log_every == 0:
                            cs_calib = CalibrationDiagnostics.compute(
                                logits_raw=cs_logits,
                                logits_scaled=cs_logits_scaled,
                                s=cs_s,
                                targets=y,
                            )
                            cs_calib.update(cs_band_metrics)

                            # DDP reduce if needed
                            cs_rank = int(os.environ.get('RANK', 0))
                            cs_world = int(os.environ.get('WORLD_SIZE', 1))
                            if cs_world > 1:
                                cs_calib = CalibrationDiagnostics.ddp_reduce(cs_calib, cs_world)

                            metrics.update({f'cs_{k}': v for k, v in cs_calib.items()
                                          if isinstance(v, (int, float))})

                            log_confidence_metrics(
                                cs_calib, global_step,
                                writer=writer if TENSORBOARD_AVAILABLE and 'writer' in dir() else None,
                                print_every=config.log_every,
                                rank=cs_rank,
                            )

                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  [CONFIDENCE] Error at step {global_step}: {e}")

            # V10.14: Slot memory auxiliary losses (retrieval + router balancing)
            if config.global_tokens_enabled and config.global_update_mode == "slots":
                _out_dict = outputs if isinstance(outputs, dict) else {}
                # V10.29: Capture LM loss before aux losses for adaptive ratio tracking
                _lm_loss_val = loss.item() if isinstance(loss, torch.Tensor) else float(loss)
                # Get slot_memory from model (handles OntologicalHybrid wrapper)
                _sm = getattr(model, 'slot_memory', None)
                if _sm is None:
                    _inner = getattr(model, 'hybrid', model)
                    _sm = getattr(_inner, 'slot_memory', None)
                if _sm is not None:
                    # Router loss (L_sharp + L_bal + L_ortho)
                    _router_loss = _sm.compute_sharpness_loss()
                    loss = loss + _router_loss
                    # Retrieval loss (auxiliary slot readout → lm_head)
                    _lm_head = getattr(model, 'lm_head', None)
                    if _lm_head is None:
                        _inner = getattr(model, 'hybrid', model)
                        _lm_head = getattr(_inner, 'lm_head', None)
                    _sk = _out_dict.get('_slot_keys')
                    _sv = _out_dict.get('_slot_vals')
                    _sh = _out_dict.get('_slot_hidden')
                    _retr_loss_val = 0.0
                    _slot_pred_loss_val = 0.0
                    # V10.14.10: Warn on first occurrence when slot tensors are missing
                    if (_sk is None or _sv is None or _sh is None) and global_step <= 1:
                        _missing = [k for k, v in [('_slot_keys', _sk), ('_slot_vals', _sv),
                                                    ('_slot_hidden', _sh)] if v is None]
                        print(f"  [SLOTS WARNING] Slot memory enabled but forward output "
                              f"missing: {_missing}. Retrieval loss will be 0 — "
                              f"slots receive no auxiliary learning signal!")
                    if _lm_head is not None and _sk is not None and _sv is not None and _sh is not None:
                        # V10.16.1: Use explicit query_mask from batch if available
                        # (e.g. AssociativeRecallDataset provides True only at answer positions).
                        # V10.21: Densified retrieval supervision. V10.17 only supervised
                        # positions beyond window_size, reasoning that within-window tokens
                        # "don't need slots." But the retrieval loss gradient also teaches
                        # write_val_proj WHAT to store — excluding within-window positions
                        # starved that signal. Now supervise from window_size//2 onward:
                        # positions 0..win/2 are pure local context (excluded), positions
                        # win/2..win are "can predict locally but slot content is useful
                        # training signal", positions win+ are "genuinely need long-range."
                        _retr_query_mask = None
                        if isinstance(batch, dict) and 'query_mask' in batch:
                            _retr_query_mask = batch['query_mask'].to(device)
                        if _retr_query_mask is None:
                            _valid = (y != -100)  # [B, N]
                            _B, _N = y.shape
                            _win = getattr(config, 'window_size', 0)
                            _retr_start = max(_win // 2, 1)  # V10.21: half-window threshold
                            if _retr_start > 0 and _N > _retr_start:
                                _pos_mask = torch.zeros(_B, _N, dtype=torch.bool, device=y.device)
                                _pos_mask[:, _retr_start:] = True
                                _retr_query_mask = _valid & _pos_mask
                            else:
                                _retr_query_mask = _valid
                        _retr_loss = _sm.compute_retrieval_loss(
                            x=_sh,
                            slot_keys=_sk,
                            slot_vals=_sv,
                            query_mask=_retr_query_mask,
                            target_ids=y,
                            lm_head=_lm_head,
                        )
                        # V10.29.1: Use adaptive retrieval loss weight (replaces
                        # config weight when adaptive is active, not compounded).
                        _adaptive_rw = getattr(_sm, '_adaptive_retr_loss_weight', None)
                        _effective_retr_weight = _adaptive_rw if _adaptive_rw is not None else config.retrieval_loss_weight
                        loss = loss + _effective_retr_weight * _retr_loss
                        _retr_loss_val = _retr_loss.item()

                        # V11.4: Slot-only prediction loss — separate head tests
                        # whether slot content is predictively useful for next-token.
                        # This is NOT another self-consistency loop: it uses a separate
                        # prediction head that can only succeed if slots contain
                        # LM-relevant information. The arbiter is still ablation delta.
                        if config.slot_prediction_loss_weight > 0:
                            _slot_pred_loss = _sm.compute_slot_prediction_loss(
                                x=_sh,
                                slot_keys=_sk,
                                slot_vals=_sv,
                                query_mask=_retr_query_mask,
                                target_ids=y,
                            )
                            loss = loss + config.slot_prediction_loss_weight * _slot_pred_loss
                            _slot_pred_loss_val = _slot_pred_loss.item()
                        else:
                            _slot_pred_loss_val = 0.0

                        # V10.27/V11.3: Adaptive gate + constraint calls moved to
                        # post-optimizer-step (once per global step, not per micro-step)
                        # to avoid interval counters firing grad_accum× too fast.
                    # Step the router noise counter
                    _sm._router_step += 1
                    _sm.maybe_unfreeze_read_gate()
                    # Log slot diagnostics periodically (only on last accumulation step)
                    if global_step % config.log_every == 0 and (accumulation_step + 1) % config.gradient_accumulation == 0:
                        _wr_scale = math.exp(float(_sm._write_log_scale.data.clamp(min=math.log(1.5), max=math.log(getattr(_sm, '_wr_scale_max', 2.0)))))
                        _mask_frac = _retr_query_mask.float().mean().item() if _retr_query_mask is not None else 0.0
                        print(f"  [SLOTS] retr_loss={_retr_loss_val:.4f} "
                              f"qmask={_mask_frac:.4f} "
                              f"L_sharp={getattr(_sm, '_diag_L_sharp', 0):.4f} "
                              f"L_bal={getattr(_sm, '_diag_L_bal', 0):.4f} "
                              f"write_gate={getattr(_sm, '_diag_write_gate_mean', 0):.3f} "
                              f"marginal_H={getattr(_sm, '_diag_marginal_entropy', 0):.3f} "
                              f"read_H={getattr(_sm, '_diag_read_attn_entropy', 0):.3f} "
                              f"wr_scale={_wr_scale:.3f} "
                              f"rd_scale={getattr(_sm, '_diag_read_scale', 0):.3f} "
                              f"gate_ceil={getattr(_sm, '_gate_target', 0.35):.2f} "
                              f"retr_w={getattr(_sm, '_adaptive_retr_loss_weight', 1.0):.2f} "
                              f"gate_floor={getattr(_sm, '_novelty_gate_floor', 0.15):.2f} "
                              f"leak={getattr(_sm, '_soft_detach_leak', 0.1):.2f} "
                              f"L_bal_w={getattr(_sm, '_L_bal_weight', 1.0):.2f} "
                              f"q_norm={getattr(_sm, '_diag_retr_query_norm', 0):.2f} "
                              f"retr_norm={getattr(_sm, '_diag_retr_retrieved_norm', 0):.2f} "
                              f"rd_gate={getattr(_sm, '_diag_read_gate_mean', 0):.3f} "
                              f"coh={getattr(_sm, '_diag_coherence_mean', 0):.3f} "
                              f"rd_max_w={getattr(_sm, '_diag_read_max_weight', 0):.3f} "
                              f"key_cos_var={getattr(_sm, '_diag_slot_key_cos_var', 0):.4f} "
                              f"val_norm={getattr(_sm, '_diag_slot_val_mean_norm', 0):.2f}")
                        # V11.4: Log slot-only prediction diagnostics
                        if _slot_pred_loss_val > 0:
                            _sp_ppl = math.exp(min(_slot_pred_loss_val, 20.0))  # Cap to avoid overflow
                            _sp_acc = getattr(_sm, '_diag_slot_pred_acc', 0.0)
                            print(f"  [SLOT-PRED] loss={_slot_pred_loss_val:.4f} "
                                  f"ppl={_sp_ppl:.1f} "
                                  f"acc={_sp_acc:.4f} "
                                  f"w={config.slot_prediction_loss_weight:.2f}")
                        # V10.22: Feed signals to adaptive slot LR controller
                        if adaptive_slot_lr is not None:
                            adaptive_slot_lr.record_retr_loss(_retr_loss_val)
                            adaptive_slot_lr.record_write_gate(getattr(_sm, '_diag_write_gate_mean', 0))

            # =====================================================================
            # CONSCIOUS GENERATION Phase 1+2: Token Ontology Cache + L_ont Loss
            # Refreshes O_tok + Phase 2 buffers (P_tok, R_tok, V_tok, G_tok)
            # periodically, computes ontological structure loss for 32D manifold.
            # =====================================================================
            if config.enable_conscious_generation and hasattr(model, 'conscious_gen'):
                try:
                    # Phase 5: Apply curriculum lambda overrides for this step
                    if cg_stage_manager is not None:
                        _cg_lambdas = cg_stage_manager.step(global_step)
                        for _lk, _lv in _cg_lambdas.items():
                            if hasattr(config, _lk):
                                setattr(config, _lk, _lv)
                        # Dynamic Phase 4 toggle based on curriculum stage
                        config.use_field_integrated_softmax = cg_stage_manager.use_field_integrated_softmax

                    # Get embedding weight (need non-detached for gradient flow through projector)
                    _cg_emb_weight = None
                    _cg_inner = getattr(model, 'hybrid', model)
                    _cg_tok_emb = getattr(_cg_inner, 'token_embed', None)
                    if _cg_tok_emb is None:
                        _cg_tok_emb = getattr(_cg_inner, 'embed_tokens', None)
                    if _cg_tok_emb is None:
                        _cg_tok_emb = getattr(_cg_inner, 'wte', None)
                    # Fallback: use get_input_embeddings() (supports MistralCGWrapper)
                    if _cg_tok_emb is None and hasattr(model, 'get_input_embeddings'):
                        _cg_tok_emb = model.get_input_embeddings()
                    if _cg_tok_emb is not None and hasattr(_cg_tok_emb, 'weight'):
                        _cg_emb_weight = _cg_tok_emb.weight

                    if _cg_emb_weight is not None:
                        # Refresh token primitive cache periodically
                        _cg_cache = model.conscious_gen['token_cache']
                        _cg_cache.maybe_refresh(_cg_emb_weight.detach(), global_step)

                        # Compute L_ont: ontological structure loss
                        if config.lambda_ont > 0 and 'ontology_loss' in model.conscious_gen:
                            _cg_projector = model.conscious_gen['token_projector']
                            _cg_loss_fn = model.conscious_gen['ontology_loss']

                            # Project target tokens through the projector (with gradients)
                            _cg_target_emb = _cg_tok_emb(y)
                            _cg_target_codes = _cg_projector(_cg_target_emb)

                            _cg_result = _cg_loss_fn(_cg_target_codes, y)
                            _cg_ont_loss = _cg_result['loss']

                            if torch.isfinite(_cg_ont_loss):
                                loss = loss + config.lambda_ont * _cg_ont_loss
                                metrics['cg_ont_loss'] = _cg_ont_loss.item()
                                metrics['cg_ont_pos_sim'] = _cg_result['avg_pos_sim'].item()
                                metrics['cg_ont_neg_sim'] = _cg_result['avg_neg_sim'].item()

                        # =========================================================
                        # Phase 3/4: Governance — Kosha routing, Bliss gating, losses
                        # Phase 3: aux losses only (Z* computed but not used for LM)
                        # Phase 4: Z* replaces base logits for L_LM (end-to-end)
                        # Requires: logits, hidden states, sovereign state
                        # =========================================================
                        _cg_has_p3 = 'integrated_scorer' in model.conscious_gen
                        _cg_any_p3_loss = (config.lambda_kosha_routing > 0
                                          or config.lambda_bliss_token > 0
                                          or config.lambda_plausibility_token > 0
                                          or config.lambda_csr_token > 0
                                          or config.lambda_vritti_token > 0
                                          or config.lambda_guna_token > 0)
                        _cg_phase4 = config.use_field_integrated_softmax

                        if _cg_has_p3 and (_cg_any_p3_loss or _cg_phase4) and logits is not None:
                            # Extract hidden states and sovereign state from outputs
                            _cg_hidden = None
                            _cg_sov_state = None
                            if isinstance(outputs, dict):
                                _cg_hidden = outputs.get('last_hidden_state', None)
                                _cg_sov_state = outputs.get('state', None)

                            # Diagnostic: check gradient prerequisites
                            if global_step <= resume_step + 3 and accumulation_step == 0:
                                _h_ok = _cg_hidden is not None
                                _s_ok = _cg_sov_state is not None
                                _s_rg = _cg_sov_state.requires_grad if _s_ok else False
                                _s_gf = _cg_sov_state.grad_fn is not None if _s_ok else False
                                _h_rg = _cg_hidden.requires_grad if _h_ok else False
                                print(f"  [P3-DIAG] Step {global_step}: "
                                      f"hidden={'OK' if _h_ok else 'NONE'}(rg={_h_rg}) "
                                      f"state={'OK' if _s_ok else 'NONE'}(rg={_s_rg},gf={_s_gf}) "
                                      f"phase4={_cg_phase4} any_p3={_cg_any_p3_loss}")

                            if _cg_hidden is not None and _cg_sov_state is not None:
                                # Build T_t via TokenEvaluationTensor
                                # Phase 3: Detach logits but keep hidden/o_ctx live
                                #   (primitive scorers train via aux losses only).
                                # Phase 4: Keep ALL inputs live for end-to-end gradients
                                #   through Z* -> B -> α -> S_f -> h_t -> transformer.
                                _cg_tet = model.conscious_gen['token_eval_tensor']
                                if _cg_phase4:
                                    # End-to-end: gradients flow through everything
                                    _cg_tet_result = _cg_tet(
                                        logits=logits,
                                        hidden=_cg_hidden,
                                        o_ctx=_cg_sov_state,
                                        cache=_cg_cache,
                                    )
                                else:
                                    _cg_tet_result = _cg_tet(
                                        logits=logits.detach(),
                                        hidden=_cg_hidden,
                                        o_ctx=_cg_sov_state,
                                        cache=_cg_cache,
                                    )
                                _cg_T = _cg_tet_result['T']              # (B, T, K, 6)
                                _cg_cand_ids = _cg_tet_result['candidate_ids']  # (B, T, K)

                                # CRS Phase 2: Log branch diagnostics when CRS is active
                                _crs_bd = _cg_tet_result.get('crs_branch_data')
                                if _crs_bd is not None:
                                    with torch.no_grad():
                                        metrics['crs_C_mean'] = _crs_bd['C'].mean().item()
                                        metrics['crs_R_mean'] = _crs_bd['R'].mean().item()
                                        metrics['crs_S_mean'] = _crs_bd['S'].mean().item()
                                        metrics['crs_S_prob_mean'] = _crs_bd['S_prob'].mean().item()
                                        metrics['crs_S_gate_mean'] = _crs_bd['S_gate'].mean().item()
                                        metrics['crs_col3_mean'] = _crs_bd['crs_score'].mean().item()
                                        # semantic_override_rate: fraction of positions where
                                        # top-CRS candidate differs from top-R (pure resonance)
                                        _crs_top1 = _crs_bd['crs_score'].argmax(dim=-1)  # (...,)
                                        _r_top1 = _crs_bd['R'].argmax(dim=-1)
                                        metrics['crs_semantic_override_rate'] = (_crs_top1 != _r_top1).float().mean().item()

                                # Build domain signal from Gyroscope detection
                                # Soft mapping: LANG/MATH/CODE → 8-dim distribution
                                _cg_domain = None
                                try:
                                    from symbolu_training.training.conscious_generation.governance.domain_bridge import map_gyro_to_domain
                                    _cg_domain_label = metrics.get('gyroscope_domain_label', 'LANG')
                                    _cg_domain = map_gyro_to_domain(
                                        domain_label=_cg_domain_label,
                                        batch_size=_cg_hidden.shape[0],
                                        seq_len=_cg_hidden.shape[1] if _cg_hidden.dim() == 3 else None,
                                        device=_cg_hidden.device,
                                        dtype=_cg_hidden.dtype,
                                    )
                                except ImportError:
                                    pass

                                # Run IntegratedTokenScorer (Kosha + Bliss)
                                # Phase 3: Detach hidden/o_ctx (router trains its MLP
                                #   only, no backbone gradients from governance).
                                # Phase 4: Keep live for end-to-end training.
                                _cg_integ = model.conscious_gen['integrated_scorer']
                                if _cg_phase4:
                                    _cg_integ_result = _cg_integ(
                                        T=_cg_T,
                                        hidden=_cg_hidden,
                                        o_ctx=_cg_sov_state,
                                        domain=_cg_domain,
                                        candidate_ids=_cg_cand_ids,
                                    )
                                else:
                                    # Phase 3: detach hidden (no backbone grads from
                                    # governance), but keep o_ctx LIVE so CG losses
                                    # (kosha routing, bliss, primitives) can train the
                                    # state projector.  Backbone is already frozen
                                    # (requires_grad=False) so no weight updates leak.
                                    _cg_integ_result = _cg_integ(
                                        T=_cg_T,
                                        hidden=_cg_hidden.detach(),
                                        o_ctx=_cg_sov_state,
                                        domain=_cg_domain,
                                        candidate_ids=_cg_cand_ids,
                                    )
                                _cg_alpha = _cg_integ_result['alpha']    # (B, T, 6)
                                _cg_B = _cg_integ_result['B']            # (B, T, K)
                                _cg_D = _cg_integ_result['D']            # (B, T, K)

                                # Alpha entropy regularization — prevent routing collapse.
                                # Without this, softmax saturation makes one-hot alpha
                                # self-reinforcing and unrecoverable.
                                _cg_alpha_ent = -((_cg_alpha + 1e-8).log() * _cg_alpha).sum(dim=-1).mean()
                                _cg_alpha_ent_weight = 0.1
                                loss = loss - _cg_alpha_ent_weight * _cg_alpha_ent  # maximize entropy
                                metrics['cg_alpha_entropy'] = _cg_alpha_ent.item()
                                metrics['cg_alpha_ent_loss'] = (_cg_alpha_ent_weight * _cg_alpha_ent).item()

                                # Phase 4: Replace L_LM with field-integrated cross-entropy
                                # Strategy: subtract old LM CE, add field-integrated CE.
                                # This preserves all aux losses accumulated between
                                # compute_phase_loss() and this point (~40 loss terms).
                                if _cg_phase4 and 'field_softmax' in model.conscious_gen:
                                    _cg_Z_star = _cg_integ_result['Z_star']  # (B, T, K)
                                    _cg_fs = model.conscious_gen['field_softmax']
                                    _cg_fs_result = _cg_fs(
                                        Z_star=_cg_Z_star,
                                        candidate_ids=_cg_cand_ids,
                                        T=_cg_T,
                                        Z=_cg_integ_result.get('Z'),
                                        B=_cg_B,
                                    )
                                    _cg_log_probs = _cg_fs_result['log_probs']  # (B, T, V)

                                    # Mask positions where target is NOT in shortlist
                                    # (log_prob = -inf → nll = inf). Only compute loss
                                    # over positions where re-ranking is meaningful.
                                    _cg_target_in_shortlist = (
                                        _cg_cand_ids == y.unsqueeze(-1)
                                    ).any(dim=-1)  # (B, T) bool
                                    _cg_field_targets = y.clone()
                                    _cg_field_targets[~_cg_target_in_shortlist] = -100

                                    _cg_lm_loss = F.nll_loss(
                                        _cg_log_probs.reshape(-1, _cg_log_probs.shape[-1]),
                                        _cg_field_targets.reshape(-1),
                                        ignore_index=-100,
                                    )
                                    if torch.isfinite(_cg_lm_loss):
                                        # Recompute old LM CE (detached) to subtract it
                                        with torch.no_grad():
                                            _cg_V = logits.shape[-1]
                                            _cg_old_lm = F.cross_entropy(
                                                logits.reshape(-1, _cg_V),
                                                y.reshape(-1),
                                                ignore_index=-100,
                                            )
                                        # Swap: remove old LM loss, add field-integrated
                                        loss = loss - _cg_old_lm + _cg_lm_loss
                                        metrics['cg_field_lm_loss'] = _cg_lm_loss.item()
                                        metrics['cg_phase4_active'] = 1.0
                                        # Track shortlist coverage
                                        _cg_coverage = _cg_target_in_shortlist.float().mean()
                                        metrics['cg_shortlist_coverage'] = _cg_coverage.item()
                                    else:
                                        # Non-finite field loss — fall back to standard LM
                                        metrics['cg_phase4_fallback'] = 1.0

                                # Kosha routing loss
                                if config.lambda_kosha_routing > 0 and 'kosha_routing_loss' in model.conscious_gen:
                                    _cg_kr_fn = model.conscious_gen['kosha_routing_loss']
                                    _cg_kr_result = _cg_kr_fn(
                                        router_result=_cg_integ_result.get('router_result', {'alpha': _cg_alpha, 'policy_logits': torch.zeros_like(_cg_alpha)}),
                                        T=_cg_T,
                                        target_ids=y,
                                        candidate_ids=_cg_cand_ids,
                                    )
                                    _cg_kr_loss = _cg_kr_result['loss']
                                    if torch.isfinite(_cg_kr_loss):
                                        loss = loss + config.lambda_kosha_routing * _cg_kr_loss
                                        metrics['cg_kosha_routing_loss'] = _cg_kr_loss.item()

                                # Bliss coherence loss
                                if config.lambda_bliss_token > 0 and 'bliss_coherence_loss' in model.conscious_gen:
                                    _cg_bl_fn = model.conscious_gen['bliss_coherence_loss']
                                    _cg_bl_result = _cg_bl_fn(
                                        B=_cg_B,
                                        D=_cg_D,
                                        target_ids=y,
                                        candidate_ids=_cg_cand_ids,
                                    )
                                    _cg_bl_loss = _cg_bl_result['loss']
                                    if torch.isfinite(_cg_bl_loss):
                                        loss = loss + config.lambda_bliss_token * _cg_bl_loss
                                        metrics['cg_bliss_loss'] = _cg_bl_loss.item()
                                        metrics['cg_bliss_pos'] = _cg_bl_result['pos_bliss'].item()
                                        metrics['cg_bliss_neg'] = _cg_bl_result['neg_bliss'].item()

                                # Primitive auxiliary losses
                                _cg_prim_lambdas = {
                                    'jepa': config.lambda_plausibility_token,
                                    'csr': config.lambda_csr_token,
                                    'vritti': config.lambda_vritti_token,
                                    'guna': config.lambda_guna_token,
                                }
                                if any(v > 0 for v in _cg_prim_lambdas.values()) and 'primitive_aux_losses' in model.conscious_gen:
                                    _cg_pa_fn = model.conscious_gen['primitive_aux_losses']
                                    _cg_pa_result = _cg_pa_fn(
                                        T=_cg_T,
                                        target_ids=y,
                                        candidate_ids=_cg_cand_ids,
                                    )
                                    for _prim_name, _prim_lam in _cg_prim_lambdas.items():
                                        if _prim_lam > 0:
                                            _prim_loss_key = f"L_{_prim_name}"
                                            _prim_loss = _cg_pa_result.get(_prim_loss_key, None)
                                            if _prim_loss is not None and torch.isfinite(_prim_loss):
                                                loss = loss + _prim_lam * _prim_loss
                                                metrics[f'cg_{_prim_loss_key}'] = _prim_loss.item()

                                # Ontology → Vritti directional prior (cognitive axis alignment)
                                # KL regularizer encouraging v_ctx toward ontology-derived prior.
                                _vritti_prior_lam = getattr(config, 'lambda_vritti_ontology_prior', 0.0)
                                if _vritti_prior_lam > 0 and 'ontology_vritti_prior' in model.conscious_gen:
                                    _cg_ovp = model.conscious_gen['ontology_vritti_prior']
                                    _cg_vritti_scorer = model.conscious_gen['vritti_scorer']
                                    _cg_v_ctx = _cg_vritti_scorer.compute_context_repr(
                                        _cg_hidden, _cg_sov_state
                                    )
                                    _cg_ovp_loss = _cg_ovp(_cg_v_ctx, _cg_sov_state)
                                    if torch.isfinite(_cg_ovp_loss):
                                        loss = loss + _vritti_prior_lam * _cg_ovp_loss
                                        metrics['cg_L_vritti_ont_prior'] = _cg_ovp_loss.item()

                                # --- CG Primitive Loss Attribution ---
                                # Track weighted contribution of each primitive to total CG loss.
                                # This tells you which primitive is driving adapter weight changes.
                                _cg_contribs = {}
                                if 'cg_ont_loss' in metrics and config.lambda_ont > 0:
                                    _cg_contribs['ont'] = config.lambda_ont * metrics['cg_ont_loss']
                                if 'cg_kosha_routing_loss' in metrics and config.lambda_kosha_routing > 0:
                                    _cg_contribs['kosha'] = config.lambda_kosha_routing * metrics['cg_kosha_routing_loss']
                                if 'cg_bliss_loss' in metrics and config.lambda_bliss_token > 0:
                                    _cg_contribs['bliss'] = config.lambda_bliss_token * metrics['cg_bliss_loss']
                                for _pn in ('jepa', 'csr', 'vritti', 'guna'):
                                    _pk = f'cg_L_{_pn}'
                                    _lam = getattr(config, f'lambda_{_pn}_token', 0)
                                    if _pk in metrics and _lam > 0:
                                        _cg_contribs[_pn] = _lam * metrics[_pk]
                                if 'cg_L_vritti_ont_prior' in metrics and _vritti_prior_lam > 0:
                                    _cg_contribs['vritti_ont_prior'] = _vritti_prior_lam * metrics['cg_L_vritti_ont_prior']
                                _cg_total_contrib = sum(_cg_contribs.values()) if _cg_contribs else 0.0
                                if _cg_total_contrib > 0:
                                    for _cn, _cv in _cg_contribs.items():
                                        metrics[f'cg_attr_{_cn}'] = _cv / _cg_total_contrib
                                    metrics['cg_total_aux_loss'] = _cg_total_contrib

                                # Log Kosha routing diagnostics
                                if global_step % config.log_every == 0 and global_step > 0:
                                    _cg_alpha_mean = _cg_alpha.mean(dim=(0, 1))
                                    metrics['cg_alpha_entropy'] = -(
                                        _cg_alpha * (_cg_alpha + 1e-8).log()
                                    ).sum(dim=-1).mean().item()
                                    metrics['cg_bliss_mean'] = _cg_B.mean().item()
                                    metrics['cg_disagree_mean'] = _cg_D.mean().item()
                                    if _cg_domain is not None:
                                        metrics['cg_domain_label'] = metrics.get('gyroscope_domain_label', 'LANG')
                                        _cg_domain_ent = -(
                                            _cg_domain[0] * (_cg_domain[0] + 1e-8).log()
                                        ).sum(dim=-1).mean().item()
                                        metrics['cg_domain_entropy'] = _cg_domain_ent

                                # Phase 5: Update governance diagnostics tracker
                                if cg_governance_diag is not None:
                                    cg_governance_diag.update(
                                        alpha=_cg_alpha,
                                        B=_cg_B,
                                        D=_cg_D,
                                        T=_cg_T,
                                        Z_star=_cg_integ_result.get('Z_star'),
                                        target_ids=y,
                                        candidate_ids=_cg_cand_ids,
                                        base_logits=logits.detach(),
                                        # Governance causality signals
                                        router_result=_cg_integ_result.get('router_result'),
                                        lambda_eff=_cg_integ_result.get('lambda_eff'),
                                        kosha=_cg_integ_result.get('kosha'),
                                        router=model.conscious_gen.get('kosha_router'),
                                        hidden=_cg_hidden.detach(),
                                        o_ctx=_cg_sov_state.detach(),
                                        domain=_cg_domain,
                                    )

                        # Log diagnostics periodically
                        if (global_step % config.log_every == 0 and global_step > 0 and
                            (accumulation_step + 1) % config.gradient_accumulation == 0):
                            _cg_diag = _cg_cache.get_diagnostics()
                            if _cg_diag.get('initialized', False):
                                _cg_msg = (f"  [Conscious Gen] Step {global_step} | "
                                          f"O_tok refresh={_cg_diag['step']}")
                                if 'cg_ont_loss' in metrics:
                                    _cg_msg += (f" | L_ont={metrics['cg_ont_loss']:.4f}"
                                               f" | pos_sim={metrics.get('cg_ont_pos_sim', 0):.3f}"
                                               f" | neg_sim={metrics.get('cg_ont_neg_sim', 0):.3f}")
                                # Phase 2 buffer norms
                                _p2_norms = []
                                for _buf_name in ('P_tok', 'R_tok', 'V_tok', 'G_tok'):
                                    _norm_key = f"{_buf_name}_mean_norm"
                                    if _norm_key in _cg_diag and _cg_diag[_norm_key] > 0:
                                        _p2_norms.append(f"{_buf_name}={_cg_diag[_norm_key]:.3f}")
                                if _p2_norms:
                                    _cg_msg += f" | norms: {', '.join(_p2_norms)}"
                                # Phase 3 governance metrics
                                if 'cg_alpha_entropy' in metrics:
                                    _cg_msg += f" | α_H={metrics['cg_alpha_entropy']:.3f}"
                                if 'cg_bliss_mean' in metrics:
                                    _cg_msg += f" | B={metrics['cg_bliss_mean']:.3f}"
                                # Phase 4 field-integrated generation
                                if 'cg_field_lm_loss' in metrics:
                                    _cg_msg += f" | L_field={metrics['cg_field_lm_loss']:.4f}"
                                # Curriculum stage + key lambdas (diagnose sp_grad=0)
                                if cg_stage_manager is not None:
                                    _cg_msg += (f" | stage={cg_stage_manager.current_stage}"
                                               f" λ_k={config.lambda_kosha_routing:.5f}"
                                               f" λ_b={config.lambda_bliss_token:.5f}"
                                               f" λ_j={config.lambda_plausibility_token:.5f}"
                                               f" λ_c={config.lambda_csr_token:.5f}")
                                # CRS branch diagnostics (appended when active)
                                if 'crs_S_gate_mean' in metrics:
                                    _cg_msg += (f" | CRS: C={metrics.get('crs_C_mean', 0):.3f}"
                                                f" R={metrics.get('crs_R_mean', 0):.3f}"
                                                f" S={metrics.get('crs_S_mean', 0):.3f}"
                                                f" Sg={metrics.get('crs_S_gate_mean', 0):.2f}"
                                                f" ovr={metrics.get('crs_semantic_override_rate', 0):.2f}")
                                # Phase 3 entry diagnostic
                                _p3_entered = 'cg_alpha_entropy' in metrics or 'cg_kosha_routing_loss' in metrics
                                _cg_msg += f" | P3={'Y' if _p3_entered else 'N'}"
                                print(_cg_msg)

                            # TensorBoard logging
                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                if 'cg_ont_loss' in metrics:
                                    writer.add_scalar('conscious_gen/L_ont', metrics['cg_ont_loss'], global_step)
                                    writer.add_scalar('conscious_gen/ont_pos_sim', metrics.get('cg_ont_pos_sim', 0), global_step)
                                    writer.add_scalar('conscious_gen/ont_neg_sim', metrics.get('cg_ont_neg_sim', 0), global_step)
                                writer.add_scalar('conscious_gen/O_tok_std', _cg_diag.get('O_tok_std', 0), global_step)
                                writer.add_scalar('conscious_gen/bhava_entropy', _cg_diag.get('bhava_entropy', 0), global_step)
                                # Phase 2 buffer norms
                                for _buf_name in ('P_tok', 'R_tok', 'V_tok', 'G_tok'):
                                    _norm_key = f"{_buf_name}_mean_norm"
                                    if _norm_key in _cg_diag:
                                        writer.add_scalar(f'conscious_gen/{_norm_key}', _cg_diag[_norm_key], global_step)
                                # Phase 3 governance metrics
                                if 'cg_alpha_entropy' in metrics:
                                    writer.add_scalar('conscious_gen/alpha_entropy', metrics['cg_alpha_entropy'], global_step)
                                if 'cg_bliss_mean' in metrics:
                                    writer.add_scalar('conscious_gen/bliss_mean', metrics['cg_bliss_mean'], global_step)
                                if 'cg_disagree_mean' in metrics:
                                    writer.add_scalar('conscious_gen/disagree_mean', metrics['cg_disagree_mean'], global_step)
                                if 'cg_kosha_routing_loss' in metrics:
                                    writer.add_scalar('conscious_gen/L_kosha_routing', metrics['cg_kosha_routing_loss'], global_step)
                                if 'cg_bliss_loss' in metrics:
                                    writer.add_scalar('conscious_gen/L_bliss', metrics['cg_bliss_loss'], global_step)
                                for _pn in ('jepa', 'csr', 'vritti', 'guna'):
                                    _pk = f'cg_L_{_pn}'
                                    if _pk in metrics:
                                        writer.add_scalar(f'conscious_gen/L_{_pn}_token', metrics[_pk], global_step)

                            # Phase 5: Log governance diagnostics summary
                            if cg_governance_diag is not None:
                                _cg_gov_summary = cg_governance_diag.get_summary()
                                for _gk, _gv in _cg_gov_summary.items():
                                    metrics[_gk] = _gv
                                if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                    for _gk, _gv in _cg_gov_summary.items():
                                        writer.add_scalar(f'conscious_gen/{_gk}', _gv, global_step)

                            # Phase 5: Log curriculum stage info
                            if cg_stage_manager is not None:
                                _cg_stage_diag = cg_stage_manager.get_diagnostics()
                                for _sk, _sv in _cg_stage_diag.items():
                                    if isinstance(_sv, (int, float)):
                                        metrics[_sk] = _sv

                            # Embedding diagnostics: snapshot and log drift metrics
                            if cg_embedding_diag is not None:
                                _ed_cache = model.conscious_gen['token_cache'] if (hasattr(model, 'conscious_gen') and 'token_cache' in model.conscious_gen) else None
                                _ed_model = getattr(model, 'module', model)  # unwrap DDP if needed
                                _ed_metrics = cg_embedding_diag.snapshot(
                                    model=_ed_model,
                                    global_step=global_step,
                                    token_cache=_ed_cache,
                                )
                                if _ed_metrics is not None:
                                    print(cg_embedding_diag.format_console_log(_ed_metrics))
                                    # TensorBoard logging
                                    if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                        for _ek, _ev in _ed_metrics.items():
                                            if isinstance(_ev, (int, float)) and _ek != 'step':
                                                writer.add_scalar(f'embedding_diag/{_ek}', _ev, global_step)
                                    # Stage 7B: Feed metrics into adaptive controller
                                    if cg_adaptive_diag_controller is not None:
                                        _diag_signals = cg_embedding_diag.to_diagnostic_signals(
                                            _ed_metrics, global_step=global_step,
                                        )
                                        if _diag_signals is not None:
                                            _adaptive_responses = cg_adaptive_diag_controller.check(_diag_signals)
                                            for _ar in _adaptive_responses:
                                                print(f"  [ADAPTIVE-7B] {_ar.severity}: {_ar.action} "
                                                      f"(signal={_ar.signal_name}, value={_ar.signal_value:.4f})")
                                                if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                                    writer.add_scalar(
                                                        f'adaptive_diag/{_ar.action}', _ar.signal_value, global_step,
                                                    )

                                    # Trend summary every 5 snapshots
                                    if len(cg_embedding_diag.history) % 5 == 0 and len(cg_embedding_diag.history) >= 2:
                                        _ed_trend = cg_embedding_diag.get_trend_summary()
                                        _ed_trend_parts = [f"  [EMBED-TREND]"]
                                        for _tk, _tv in _ed_trend.items():
                                            _ed_trend_parts.append(f"    {_tk}: {_tv}")
                                        print("\n".join(_ed_trend_parts))

                            # Stage 8: Perspective Synthesizer metrics
                            if (isinstance(outputs, dict) and 'synth_result' in outputs
                                    and outputs['synth_result'] is not None):
                                _sr = outputs['synth_result']
                                metrics['stage8_gate'] = _sr.get('gate_value', 0.0)
                                metrics['stage8_cond_norm'] = _sr.get('conditioning_norm', 0.0)
                                if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                    writer.add_scalar('stage8/synthesis_gate', _sr.get('gate_value', 0.0), global_step)
                                    writer.add_scalar('stage8/conditioning_norm', _sr.get('conditioning_norm', 0.0), global_step)
                                    _s8_log = _sr.get('log_dict', {})
                                    if 'vritti_dominant' in _s8_log:
                                        _vritti_idx = ['pramana', 'viparyaya', 'vikalpa', 'nidra', 'smrti'].index(
                                            _s8_log['vritti_dominant']
                                        ) if _s8_log['vritti_dominant'] in ['pramana', 'viparyaya', 'vikalpa', 'nidra', 'smrti'] else -1
                                        if _vritti_idx >= 0:
                                            writer.add_scalar('stage8/vritti_dominant_idx', _vritti_idx, global_step)
                                    if 'csr_signal_norm' in _s8_log:
                                        writer.add_scalar('stage8/csr_signal_norm', _s8_log['csr_signal_norm'], global_step)

                            # Stage 9: Mechanism strength logging (F.14.5)
                            if (_ablation_cfg is not None
                                    and _ablation_cfg.log_mechanism_strength_every > 0
                                    and global_step % _ablation_cfg.log_mechanism_strength_every == 0
                                    and global_step > 0):
                                from symbolu_training.training.conscious_generation.ablation.metrics import (
                                    collect_mechanism_strength_log, collect_gradient_norms,
                                )
                                _mech_log = collect_mechanism_strength_log(model)
                                if _mech_log:
                                    _mech_parts = [f"  [Stage 9 MechStrength Step {global_step}]"]
                                    for _mk, _mv in _mech_log.items():
                                        _mech_parts.append(f" {_mk}={_mv:.4f}")
                                        if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                            writer.add_scalar(f'stage9/{_mk}', _mv, global_step)
                                    print("".join(_mech_parts))

                except Exception as e:
                    if global_step % 500 == 0 or global_step <= resume_step + 3:
                        import traceback
                        print(f"  [Conscious Gen] ERROR at step {global_step}: {e}")
                        traceback.print_exc()

            # =====================================================================
            # Experiential Controller: resistance-modulated plasticity
            # Sits after forward + CG loss, before backward. Scales loss by g_eff.
            # =====================================================================
            if experiential_controller is not None:
                try:
                    # Get hidden states from model outputs
                    _exp_hidden = None
                    if isinstance(outputs, dict):
                        _exp_hidden = outputs.get('last_hidden_state', None)
                    if _exp_hidden is None and logits is not None:
                        # Use logits as proxy hidden states (projected space)
                        _exp_hidden = logits

                    if _exp_hidden is not None and _exp_hidden.dim() == 3:
                        B_exp, T_exp, D_exp = _exp_hidden.shape

                        # Project to controller d_model if dimensions differ
                        _exp_d = experiential_controller.config.d_model
                        if D_exp != _exp_d:
                            # Pool feature dimension: [B, T, D] → [B, T, d_model]
                            # adaptive_avg_pool1d pools the last dim, so reshape
                            # [B, T, D] → [B*T, 1, D] → pool → [B*T, 1, d_model] → [B, T, d_model]
                            _exp_flat = _exp_hidden.reshape(B_exp * T_exp, 1, D_exp)
                            _exp_input = F.adaptive_avg_pool1d(
                                _exp_flat, _exp_d
                            ).reshape(B_exp, T_exp, _exp_d)
                        else:
                            _exp_input = _exp_hidden

                        # Target: use shifted hidden as target (next-step prediction)
                        _exp_target = _exp_input.detach().clone()

                        # Extract coherence signals from model outputs or CG metrics
                        _exp_coherence = None
                        if isinstance(outputs, dict) and 'coherence' in outputs:
                            # Gen2 models provide coherence directly
                            _c_val = outputs['coherence'].mean().item()
                            _exp_coherence = {
                                'c_tok': _c_val,
                                'c_lat': _c_val,
                                'c_conv': _c_val,
                            }
                        else:
                            # Derive coherence from available CG signals:
                            # c_tok: ontology margin (pos_sim - neg_sim), higher = more coherent
                            # c_lat: 1 - normalized loss (higher = model converging)
                            # c_conv: adapter gate (how much CG is engaged)
                            _c_tok = 0.5  # default
                            if 'cg_ont_pos_sim' in metrics and 'cg_ont_neg_sim' in metrics:
                                _c_tok = min(1.0, max(0.0,
                                    metrics['cg_ont_pos_sim'] - metrics['cg_ont_neg_sim']))
                            _c_lat = min(1.0, max(0.0, 1.0 - loss.item() / 3.0))  # normalize ~[0,3] → [0,1]
                            _c_conv = metrics.get('adapter_gate', 0.5)
                            _exp_coherence = {
                                'c_tok': _c_tok,
                                'c_lat': _c_lat,
                                'c_conv': _c_conv,
                            }

                        # Forward through controller
                        # Input NOT detached: gradients flow through controller's
                        # temporal_proj and latent_proj for learning.
                        # base_loss detached: controller doesn't backprop through main CE.
                        _exp_result = experiential_controller(
                            _exp_input,
                            _exp_target,
                            base_loss=loss.detach(),
                            coherence_signals=_exp_coherence,
                        )

                        # Scale original loss by g_eff (detached: no second-order grads)
                        _exp_scale = _exp_result['g_eff'].detach().mean()

                        # Experiential loss weight with warmup ramp:
                        # Ramp from 0 → configured weight over warmup_steps.
                        # This prevents freshly initialized (or un-checkpointed) controller
                        # projections from injecting huge loss into a mid-training model.
                        _exp_base_weight = config.experiential_loss_weight
                        _exp_warmup = config.experiential_warmup_steps
                        if _exp_warmup > 0 and experiential_controller.step.item() < _exp_warmup:
                            _exp_progress = experiential_controller.step.item() / _exp_warmup
                            _exp_loss_weight = _exp_base_weight * _exp_progress
                        else:
                            _exp_loss_weight = _exp_base_weight

                        # Clamp experiential loss to prevent divergence
                        _exp_raw_loss = _exp_result['total_loss']
                        _exp_clamped_loss = torch.clamp(_exp_raw_loss, max=config.experiential_loss_clamp)

                        loss = _exp_scale * loss + _exp_loss_weight * _exp_clamped_loss

                        # Track metrics
                        metrics['exp_g_eff'] = _exp_scale.item()
                        metrics['exp_plasticity'] = _exp_result['plasticity'].mean().item()
                        metrics['exp_gain'] = _exp_result['gain'].item()
                        metrics['exp_damping'] = _exp_result['damping'].item()
                        metrics['exp_total_loss'] = _exp_result['total_loss'].item()
                        metrics['exp_loss_weight'] = _exp_loss_weight
                        metrics['exp_loss_contrib'] = (_exp_loss_weight * _exp_clamped_loss).item()
                        for _lk in ('L_token', 'L_temporal', 'L_coherence', 'L_latent'):
                            metrics[f'exp_{_lk}'] = _exp_result['loss_components'][_lk].item()

                        # Medium loop: replay
                        if (global_step > 0 and
                                global_step % config.experiential_replay_interval == 0):
                            _exp_replay = experiential_controller.get_replay_items(k=4)

                        # Slow loop: identity consolidation
                        if (global_step > 0 and
                                global_step % config.experiential_consolidation_interval == 0):
                            _exp_consolidated = experiential_controller.consolidate_identity()
                            if _exp_consolidated:
                                print(f"  [Experiential] Step {global_step}: Identity consolidated")

                        # Periodic diagnostics
                        if (global_step % config.experiential_log_interval == 0 and
                                global_step > 0 and
                                (accumulation_step + 1) % config.gradient_accumulation == 0):
                            _exp_wstr = f" w={_exp_loss_weight:.4f}" if _exp_loss_weight < _exp_base_weight else ""
                            print(f"  [Experiential] Step {global_step} | "
                                  f"g_eff={_exp_scale.item():.3f} | "
                                  f"P={metrics['exp_plasticity']:.3f} | "
                                  f"G={metrics['exp_gain']:.3f} | "
                                  f"d={metrics['exp_damping']:.3f} | "
                                  f"L_exp={metrics['exp_total_loss']:.4f} | "
                                  f"contrib={metrics['exp_loss_contrib']:.4f}{_exp_wstr}")

                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                for _ek, _ev in metrics.items():
                                    if _ek.startswith('exp_') and isinstance(_ev, (int, float)):
                                        writer.add_scalar(f'experiential/{_ek[4:]}', _ev, global_step)

                except Exception as _exp_err:
                    if global_step % 500 == 0:
                        print(f"  [Experiential] Error at step {global_step}: {_exp_err}")

            # Stage 0: Binding Cache + CTM+ generation tracer (observation only)
            if generation_tracer is not None and logits is not None:
                try:
                    _gt_intent = outputs.get('intent_phase', None) if isinstance(outputs, dict) else None
                    _gt_hidden = outputs.get('last_hidden_state', None) if isinstance(outputs, dict) else None

                    # Record layer accesses for CTM+ (all backbone layers used in forward)
                    if config.enable_ctm_plus_tracer:
                        for _layer_idx in range(config.ctm_plus_num_layers):
                            generation_tracer.record_layer_access(_layer_idx)

                    # Record token-level metrics (using last token in sequence)
                    _gt_logits = logits[:, -1, :] if logits.dim() == 3 else logits
                    _gt_token_id = _gt_logits.argmax(dim=-1)[0].item()
                    _gt_hidden_last = _gt_hidden[:, -1, :] if _gt_hidden is not None and _gt_hidden.dim() == 3 else _gt_hidden
                    generation_tracer.record_token(
                        token_id=_gt_token_id,
                        logits=_gt_logits[0] if _gt_logits.dim() == 2 else _gt_logits,
                        hidden_state=_gt_hidden_last[0] if _gt_hidden_last is not None else torch.zeros(1),
                        intent_phase=_gt_intent,
                        input_ids=x,
                    )

                    # Periodic trace export
                    if global_step > 0 and global_step % config.generation_trace_interval == 0:
                        generation_tracer.export(config.generation_trace_output)
                        _gt_summary = generation_tracer.summary()
                        print(f"  [Stage 0 Trace] Step {global_step} | "
                              f"tokens={_gt_summary.get('num_tokens', 0)} | "
                              f"H={_gt_summary.get('mean_logit_entropy', 0):.3f} | "
                              f"intent_drift={_gt_summary.get('mean_intent_drift', 0):.4f} | "
                              f"cache_hit={_gt_summary.get('mean_cache_hit_rate', 0):.3f}")
                        if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                            for _gk, _gv in _gt_summary.items():
                                if isinstance(_gv, (int, float)):
                                    writer.add_scalar(f'stage0_tracer/{_gk}', _gv, global_step)
                except Exception as _gt_err:
                    if global_step % 1000 == 0:
                        print(f"  [Stage 0 Tracer] Error at step {global_step}: {_gt_err}")

            # Scale for gradient accumulation
            loss = loss / config.gradient_accumulation

            # --- DEBUG: KOSHA STEERING HEARTBEAT ---
            # Shows steering is active on "in-between" steps (e.g., 810, 820, 830)
            # Only prints when steering IS active (non-zero) and once per global step
            if config.enable_kosha_steering and global_step % 100 != 0 and global_step % 10 == 0:
                steer_val = kosha_steering_loss.item() if isinstance(kosha_steering_loss, torch.Tensor) else kosha_steering_loss
                # Only print if steering is actually active AND at end of accumulation
                if steer_val > 0 and (accumulation_step + 1) % config.gradient_accumulation == 0:
                    print(f"  🕵️ [STEER DEBUG Step {global_step}] Loss: {loss.item() * config.gradient_accumulation:.4f} | Steering: ✓ | Val: {steer_val:.6f}", flush=True)
            # --- END DEBUG ---

        # Backward pass (skip if TBPTT already did backward per-chunk)
        if not tbptt_backward_done:
            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()
            # V10.7.1: Report peak allocated on first iteration for standard path
            if not _first_iter_logged and accumulation_step == 0 and device.type == 'cuda':
                peak_alloc = torch.cuda.max_memory_allocated() / (1024**3)
                _std_delta = peak_alloc - _mem_baseline
                print(f"  [Standard] Memory: baseline={_mem_baseline:.2f} GB (model+optim), "
                      f"peak={peak_alloc:.2f} GB, delta={_std_delta:.2f} GB (activations)")
                _mem_baseline = 0.0  # cleanup

        running_loss += loss.item() * config.gradient_accumulation
        accumulation_step += 1
        # V10.7.1: Mark first iteration as logged (for diagnostic messages)
        if not _first_iter_logged:
            _first_iter_logged = True

        # Update weights
        if accumulation_step % config.gradient_accumulation == 0:
            if scaler is not None:
                scaler.unscale_(optimizer)

            # Note: Gradient scaling via hooks happens automatically during backward()
            # We'll call step() after optimizer.step() to update warmup schedule

            # V9.7.0: Capture RAW gradient norm BEFORE clipping for Kosha Time axis
            # This gives meaningful t values instead of always 0 (post-clip is always ~1.0)
            # Fix: compute true global L2 norm = sqrt(sum(||p.grad||²))
            # Previous code used sum(||p.grad||) which is L1-of-L2-norms and
            # overestimates the true norm, causing the throttle to trigger
            # too aggressively and crush LR unnecessarily.
            raw_grad_norm = (sum(
                p.grad.norm().item() ** 2 for p in model.parameters()
                if p.grad is not None
            )) ** 0.5

            # State projector gradient norm — confirms CG losses reach the projector
            _sp_model = getattr(model, 'module', model)  # unwrap DDP
            if hasattr(_sp_model, 'state_projector'):
                _sp_params = list(_sp_model.state_projector.parameters())
                _sp_has_grad = sum(1 for p in _sp_params if p.grad is not None)
                _sp_nonzero = sum(1 for p in _sp_params if p.grad is not None and p.grad.abs().max().item() > 0)
                _sp_grad_norm = (sum(
                    p.grad.norm().item() ** 2
                    for p in _sp_params
                    if p.grad is not None
                )) ** 0.5
                metrics['cg_state_proj_grad_norm'] = _sp_grad_norm

            # Per-component CG gradient diagnostic
            if hasattr(_sp_model, 'conscious_gen') and global_step <= resume_step + 3:
                _cg_grad_parts = {}
                # Router + bliss (via integrated_scorer)
                if 'integrated_scorer' in _sp_model.conscious_gen:
                    _integ = _sp_model.conscious_gen['integrated_scorer']
                    if hasattr(_integ, 'kosha_router'):
                        _cg_grad_parts['router'] = _integ.kosha_router
                    if hasattr(_integ, 'bliss_gate'):
                        _cg_grad_parts['bliss'] = _integ.bliss_gate
                # Individual scorers (via token_eval_tensor)
                if 'token_eval_tensor' in _sp_model.conscious_gen:
                    _tet = _sp_model.conscious_gen['token_eval_tensor']
                    for _sname in ('jepa_scorer', 'csr_scorer', 'vritti_scorer', 'guna_scorer'):
                        if hasattr(_tet, _sname):
                            _cg_grad_parts[_sname.replace('_scorer', '')] = getattr(_tet, _sname)
                # Wrapper-level components
                for _wname in ('intent_projector', 'phase_adapter'):
                    if hasattr(_sp_model, _wname):
                        _cg_grad_parts[_wname.replace('_projector', '').replace('_adapter', '')] = getattr(_sp_model, _wname)
                # Compute norms
                _cg_grad_strs = []
                for _cname, _cmod in _cg_grad_parts.items():
                    _cparams = [p for p in _cmod.parameters() if p.requires_grad]
                    _cnorm = (sum(p.grad.norm().item() ** 2 for p in _cparams if p.grad is not None)) ** 0.5
                    _chas = sum(1 for p in _cparams if p.grad is not None)
                    _cfmt = f"{_cnorm:.2e}" if _cnorm < 0.0001 else f"{_cnorm:.4f}"
                    _cg_grad_strs.append(f"{_cname}={_cfmt}({_chas}/{len(_cparams)})")
                if _cg_grad_strs:
                    print(f"  [CG-GRAD] Step {global_step}: {' | '.join(_cg_grad_strs)}")

            # Appendix G: Record gradient variance (after unscale, before clip)
            # Phase 4: Also tracks JEPA injection projector gradients
            if gradient_variance_tracker is not None:
                grad_health = gradient_variance_tracker.record(model, global_step=global_step)
                metrics['grad_total_norm'] = grad_health.get('total_grad_norm', 0.0)
                if grad_health.get('alerts') and global_step % config.log_every == 0:
                    for alert in grad_health['alerts']:
                        print(f"  [GRAD ALERT] {alert}", flush=True)

                # Phase 4: Track JEPA projector gradients separately
                # update_dampen=False: JEPA projector is a tiny auxiliary model —
                # its spike count must not corrupt the main model's dampening state.
                if jepa_injection_projector is not None:
                    jepa_proj_grad_health = gradient_variance_tracker.record(
                        jepa_injection_projector, update_dampen=False,
                    )
                    if jepa_proj_grad_health.get('alerts') and global_step % config.log_every == 0:
                        for alert in jepa_proj_grad_health['alerts']:
                            print(f"  [GRAD ALERT JEPA-Proj] {alert}", flush=True)

            # Gradient Norm Throttle: Reduce LR on gradient spikes
            # This physical safety layer prevents destructive weight updates
            throttle_factor = 1.0
            if gradient_throttle is not None:
                throttle_factor, _ = gradient_throttle.step(
                    model, optimizer, config.learning_rate,
                    precomputed_norm=raw_grad_norm,
                )
                if throttle_factor < 1.0 and global_step % config.log_every == 0:
                    print(f"  ⚡ [GRAD THROTTLE] norm={raw_grad_norm:.1f} | LR×{throttle_factor:.2f}")

            # V10.24: Adaptive variance dampening — when the GradientVarianceTracker
            # detects sustained oscillation across multiple layers (not just a one-off
            # norm spike), scale down LR proportionally. The throttle catches acute
            # spikes; this catches chronic instability that the throttle misses.
            # Applied temporarily: LR is scaled down before optimizer.step(), then
            # restored after, so the throttle's _unthrottled_lr tracking isn't corrupted.
            variance_dampen = 1.0
            _pre_dampen_lrs = None
            if gradient_variance_tracker is not None and grad_health is not None:
                variance_dampen = grad_health.get('variance_dampen_factor', 1.0)
                if variance_dampen < 1.0:
                    _pre_dampen_lrs = [pg['lr'] for pg in optimizer.param_groups]
                    for pg in optimizer.param_groups:
                        pg['lr'] *= variance_dampen
                    metrics['variance_dampen'] = variance_dampen
                    if global_step % config.log_every == 0:
                        spiking = grad_health.get('spiking_layers', 0)
                        tracked = grad_health.get('tracked_layers', 0)
                        print(f"  [GRAD VARIANCE] {spiking}/{tracked} layers spiking | LR x{variance_dampen:.2f}")

            # V10.15/V10.17: Clip slot memory gradients with per-element capping.
            # Slot keys live on the unit hypersphere — even a single large gradient
            # element can push keys off-manifold and trigger 8M× variance cascades.
            # Norm clipping (V10.15) was insufficient: it scales all elements
            # proportionally, so with many params individual elements stay large.
            # Per-element value clipping caps EACH gradient independently.
            if hasattr(model, 'slot_memory') and model.slot_memory is not None:
                _slot_params_with_grad = [
                    p for p in model.slot_memory.parameters()
                    if p.grad is not None
                ]
                if _slot_params_with_grad:
                    # V12.6: Scalar params (log-scales) need looser clip — 0.01 × slot_lr
                    # ≈ 2.8e-7 per step makes them effectively frozen. Forward-pass
                    # .clamp() on scales provides safety bounds regardless.
                    _scalar_params = [p for p in _slot_params_with_grad if p.numel() == 1]
                    _matrix_params = [p for p in _slot_params_with_grad if p.numel() > 1]
                    # Per-element cap for high-dimensional matrices (stability)
                    if _matrix_params:
                        torch.nn.utils.clip_grad_value_(_matrix_params, 0.01)
                    # Looser clip for scalars (wr/rd log-scale)
                    if _scalar_params:
                        torch.nn.utils.clip_grad_value_(_scalar_params, 1.0)
                    # Second: norm clip as safety net — matrix params only.
                    # V12.7: Including scalars in the group norm clip meant matrix
                    # params (thousands of elements) dominated the norm budget,
                    # leaving scalar params with ~0 effective gradient. Scalars
                    # are already bounded by value clip (1.0) + forward-pass clamp.
                    if _matrix_params:
                        torch.nn.utils.clip_grad_norm_(
                            _matrix_params, config.max_grad_norm * 0.01
                        )

            # V10.17/V10.18: Clip phase attention OV circuit params separately.
            # The v_proj (741x spike) and W_k_fused (2183x spike at step 1270) are
            # the primary gradient explosion sources — sin/cos backprop and division
            # by small normalizer create amplification cascades.
            # V10.18: Group norm clip alone was insufficient — with ~10 blocks × 3
            # params, the per-parameter budget was too large and cross-layer cascading
            # caused norms to escalate 5.9→117.1 over 150 steps despite throttle.
            # Per-element value clipping (same approach that stabilized slot memory)
            # caps EACH gradient element independently before norm clipping.
            _phase_attn_ov_params = [
                p for n, p in model.named_parameters()
                if p.grad is not None and 'phase_attn' in n
                and any(k in n for k in ('v_proj', 'W_k_fused', 'W_q_fused'))
            ]
            if _phase_attn_ov_params:
                # First: per-element cap (prevents cross-layer cascade buildup)
                torch.nn.utils.clip_grad_value_(_phase_attn_ov_params, 0.005)
                # Second: group norm clip as safety net (tightened from 0.1x)
                torch.nn.utils.clip_grad_norm_(
                    _phase_attn_ov_params, config.max_grad_norm * 0.05
                )

            # Gradient clipping: per-layer or global
            if config.use_per_layer_clipping and gradient_scaler_hgs is not None:
                # Clip authority and sensory layers separately to respect 9:3 design
                gradient_scaler_hgs.clip_grad_norm_by_layer(config.max_grad_norm)
            else:
                torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)

            if scaler is not None:
                scaler.step(optimizer)
                scaler.update()
            else:
                optimizer.step()

            # V10.24: Restore LR after variance dampening (temporary per-step reduction)
            if _pre_dampen_lrs is not None:
                for pg, orig_lr in zip(optimizer.param_groups, _pre_dampen_lrs):
                    pg['lr'] = orig_lr
                    # Also update throttle's tracking so it doesn't snapshot the dampened LR
                    if '_throttle_applied_lr' in pg:
                        pg['_throttle_applied_lr'] = orig_lr

            # Formula [1331] 9:3 Split: Update gradient scaler warmup schedule
            hgs_metrics = {}
            if gradient_scaler_hgs is not None:
                hgs_metrics = gradient_scaler_hgs.step()

            # V9.4.5: Measure friction and apply corrective actions
            friction_alignment = 0.0
            friction_dominance = 1.0
            friction_penalty = 1.0
            if PIDV2_AVAILABLE and global_step % 10 == 0:  # Every 10 steps to save compute
                try:
                    # V9.8.10: Use config.local_layers instead of hardcoded value
                    friction_alignment, friction_dominance = measure_friction(model, local_layers=config.local_layers)
                    # Update friction controller with corrective actions
                    if friction_controller is not None:
                        friction_penalty = friction_controller.update(friction_alignment, friction_dominance)
                except Exception as e:
                    if global_step % 100 == 0:  # Log warning every 100 steps to avoid spam
                        print(f"  Warning: Friction measurement failed at step {global_step}: {e}")

            # V9.5.6 FIX: Capture gradient norm BEFORE zero_grad for Rajas computation (6:6 mode)
            # In 6:6 mode without HGS, we need to compute this before gradients are cleared
            captured_grad_norm = 0.0
            if gradient_scaler_hgs is None:
                captured_grad_norm = sum(
                    p.grad.norm().item() for p in model.parameters()
                    if p.grad is not None
                )

            optimizer.zero_grad()

            # V11.3: Slot adaptive calls — once per global step (not per micro-step).
            # Moved from accumulation loop so interval counters count global steps.
            _sm = locals().get('_sm')
            _retr_loss_val = locals().get('_retr_loss_val')
            _lm_loss_val = locals().get('_lm_loss_val')
            if _sm is not None and _retr_loss_val is not None:
                _sm.update_write_gate_target(_retr_loss_val)
                _sm.update_constraint_relaxation(_retr_loss_val, lm_loss=_lm_loss_val)

            # Update scheduler - warmup ALWAYS runs, even with adaptive training
            # Adaptive training only takes over AFTER warmup ends
            current_ppl = metrics.get('ppl', float('inf'))
            warmup_complete = False

            if use_adaptive_warmup:
                # PPL-based adaptive warmup
                scheduler.step(current_ppl)
                warmup_complete = scheduler.warmup_ended
            else:
                # Fixed-step warmup using SequentialLR
                scheduler.step()
                warmup_complete = global_step >= config.warmup_steps

            # V9.8.4: Adaptive training only kicks in AFTER warmup
            # During warmup, we use the scheduler's LR ramp
            if config.enable_adaptive_training and warmup_complete:
                # Adaptive controller can now adjust LR
                pass  # Controller will adjust in its own step below
            elif config.enable_adaptive_training and not warmup_complete:
                # During warmup, override adaptive controller's LR with scheduler's LR
                # This ensures proper warmup ramp even with adaptive training enabled
                current_lr = scheduler.get_last_lr()[0]
                for param_group in optimizer.param_groups:
                    param_group['lr'] = current_lr

            # V9.8.3: Enforce LR bounds EVERY STEP (catches scheduler/checkpoint runaway)
            # Only enforce after warmup to not interfere with warmup ramp
            if adaptive_controller is not None and warmup_complete:
                adaptive_controller.enforce_lr_bounds(global_step)

            # V10.22: Sync slot LR ratio after any global LR change
            if adaptive_slot_lr is not None:
                adaptive_slot_lr.sync_slot_lr()

            # Update alpha schedule for phase/hybrid models
            # V9.9.8: Skip global alpha schedule when per-layer phase weights are enabled
            if not getattr(config, 'enable_per_layer_phase', False):
                # PPL-gated alpha curriculum takes precedence over step-based decay
                if ppl_alpha_curriculum is not None:
                    # Use PPL to determine alpha_phase/alpha_local
                    alpha_phase, alpha_local = ppl_alpha_curriculum.update(current_ppl)
                    # Update all HybridAttentionLayer modules
                    for module in model.modules():
                        if hasattr(module, 'alpha_phase') and isinstance(module.alpha_phase, nn.Parameter):
                            module.alpha_phase.data.fill_(alpha_phase)
                            if hasattr(module, 'alpha_local'):
                                module.alpha_local.data.fill_(alpha_local)
                    current_alpha = alpha_phase

                    # Update window size if adaptive window is enabled
                    if ppl_alpha_curriculum.enable_adaptive_window:
                        new_window_size = ppl_alpha_curriculum.get_window_size()
                        for module in model.modules():
                            if hasattr(module, 'window_size'):
                                module.window_size = new_window_size
                else:
                    # Fall back to step-based decay
                    current_alpha = update_alpha_schedule(model, global_step, config)
            else:
                # Per-layer weights are managed by InvertedLayerCurriculumController
                current_alpha = config.alpha_phase  # Just for logging

            global_step += 1
            avg_loss = running_loss / config.gradient_accumulation
            train_losses.append(avg_loss)
            running_loss = 0.0

            # =====================================================================
            # SATTVIC BRAKE: Lightweight Confidence via Phase Variance
            # Apply LR modulation if confidence < threshold
            # =====================================================================
            sattvic_confidence = 0.5
            sattvic_lr_mult = 1.0
            if sattvic_brake is not None:
                sattvic_confidence = sattvic_brake.compute_confidence()
                brake_active, sattvic_lr_mult = sattvic_brake.should_brake(sattvic_confidence)
                if brake_active:
                    # Apply graduated LR reduction based on confidence
                    for pg in optimizer.param_groups:
                        pg['lr'] *= sattvic_lr_mult

            # =====================================================================
            # EVOLUTIONARY FLOW: Apply metacognitive LR modulation
            # =====================================================================
            if evolutionary_engine is not None and config.evo_lr_modulation:
                if evo_result is not None and evo_lr_multiplier != 1.0:
                    for pg in optimizer.param_groups:
                        pg['lr'] *= evo_lr_multiplier

            # =====================================================================
            # v2.7 TRAINING STATE TRACKER: Update knowledge state EMA
            # Maps current metrics to observables and evolves state
            # =====================================================================
            if training_state_tracker is not None and training_state_tracker.enabled:
                state_metrics = {
                    'loss': avg_loss,
                    'coherence': metrics.get('coherence', 0.5),
                    'entropy': metrics.get('onto_entropy', metrics.get('entropy', 0.5)),
                    'ppl': metrics.get('ppl', math.exp(min(avg_loss, 20))),
                    'sa_deviation': abs(current_sa_ratio - 0.15) if current_sa_ratio > 0 else 0.0,
                    'sa_ratio': current_sa_ratio,
                }
                training_state_tracker.update(state_metrics, global_step)

            # =====================================================================
            # TRAINING GUNAS: Compute Sattva/Rajas/Tamas from training dynamics
            # Bridges training physics to cognitive philosophy
            # =====================================================================
            guna_s, guna_r, guna_t = 0.33, 0.33, 0.34  # Default balanced
            guna_action = "CONTINUE"
            if training_gunas is not None:
                # Get gradient norm from HGS metrics or use captured value (6:6 mode)
                if hgs_metrics:
                    grad_norm = hgs_metrics.get('a_grad_norm', 0.0) + hgs_metrics.get('s_grad_norm', 0.0)
                else:
                    # V9.5.6 FIX: Use captured_grad_norm (computed before zero_grad)
                    grad_norm = captured_grad_norm

                # Get coherence and entropy from metrics
                coherence = float(metrics.get('coherence', metrics.get('gc', 0.5)))
                entropy = float(metrics.get('onto_entropy', metrics.get('entropy', 0.5)))

                # Compute Training Gunas
                guna_s, guna_r, guna_t = training_gunas.compute(
                    coherence=coherence,
                    entropy=entropy,
                    grad_norm=grad_norm,
                    loss=avg_loss,
                )

                # Get action recommendation
                guna_action = training_gunas.get_action_recommendation(guna_s, guna_r, guna_t)

                # Update TrainingStateTracker with Gunas (semantic bridge)
                if training_state_tracker is not None and training_state_tracker.enabled:
                    training_state_tracker.update_with_gunas(guna_s, guna_r, guna_t, global_step)

            # SGP Metabolic Step and Sattvic Controller Update
            if sattvic_controller is not None and sgp_controller is not None:
                # Update Sattvic Controller with current entropy
                knowledge = float(metrics.get('coherence', 0.5))  # Use coherence as knowledge proxy
                lambda_csr = sattvic_controller.update(global_step, {
                    'ent': entropy,
                    'know': knowledge,
                })

                # V9.8.8: Sovereign Phase Controller Update
                if sovereign_phase_controller is not None:
                    # Gather diagnostics from metrics
                    spc_diagnostics = {
                        'vritti': {
                            'P_Pram': float(metrics.get('vritti_pram', 0.0)),
                            'M_Vikal': float(metrics.get('vritti_vikal', 0.0)),
                            'I_Smrit': float(metrics.get('vritti_smrit', 0.0)),
                        },
                        'bhava': {k: float(v) for k, v in metrics.items() if k.startswith('bhava_')},
                        'kosha': {k: float(v) for k, v in metrics.items() if k.startswith('kosha_')},
                    }

                    # Update SPC with current state
                    spc_result = sovereign_phase_controller.update(
                        step=global_step,
                        entropy=entropy,
                        variance=sattvic_controller.entropy_variance,
                        diagnostics=spc_diagnostics,
                    )

                    # Log SPC status at validation steps (or when actively triggering if enabled)
                    # Diagnostic mode (disabled): only log at eval intervals to avoid spam
                    should_log = global_step % config.eval_every == 0
                    if config.enable_sovereign_phase_controller and spc_result['would_trigger']:
                        should_log = True  # When enabled, also log on triggers

                    if should_log:
                        level_icon = {'normal': '🟢', 'caution': '🟡', 'warning': '🟠', 'critical': '🔴'}
                        icon = level_icon.get(spc_result['level'], '⚪')
                        status_str = "ACTIVE" if spc_result['boost_active'] else "MONITORING"
                        if config.enable_sovereign_phase_controller:
                            log_msg = f"  {icon} [SPC] {status_str} | Level:{spc_result['level'].upper()} | Force:{spc_result['steering_force']:.2f}"
                        else:
                            # SPC disabled — skip diagnostic noise
                            log_msg = None

                        if log_msg is not None:
                            if spc_result['rotations']:
                                rotation_strs = [f"{k}:{v:.2f}rad" for k, v in list(spc_result['rotations'].items())[:3]]
                                log_msg += f" | Rotations:[{','.join(rotation_strs)}]"
                            print(log_msg)

                # SGP Metabolic Step: Inject persisted gradients to Authority layers
                pulse_applied = sgp_controller.sgp_metabolic_step({
                    'entropy': entropy,
                    'variance': sattvic_controller.entropy_variance,
                })

                # V9.5.2 H200 Optimization: Clear SGP temporary buffers after heavy pulses
                # This prevents memory fragmentation stalls on high-VRAM GPUs
                if pulse_applied and device.type == "cuda":
                    torch.cuda.synchronize()  # Ensure kernels finished before clearing
                    torch.cuda.empty_cache()  # Free up H200 'Swing Space'

                # Log SGP status periodically
                if global_step % 500 == 0:
                    status = sgp_controller.get_status()
                    print(f"  🔨 [SGP] step={global_step} rate={status['rate']} λ_csr={lambda_csr:.3f} stag={'Y' if status['stagnation_active'] else 'N'}")

            # V9.4.9 Per-step updates: Both metabolic flip AND stability streak count every gradient step
            if relaxation_controller is not None:
                # Update stability streak every step (not just at validation)
                current_coherence = metrics.get('coherence', 0.75)
                sa_ratio = hgs_metrics.get("s_a_ratio", 0.5) if hgs_metrics else 0.5
                relaxation_controller.update_stability_per_step(
                    coherence=current_coherence,
                    sa_ratio=sa_ratio,
                )

                # Metabolic Flip check (when saturation gate is enabled)
                if relaxation_controller.enable_saturation_gate:
                    # Get current VRAM usage (0.0 to 1.0)
                    if device.type == "cuda":
                        vram_used = torch.cuda.memory_allocated(device)
                        vram_total = torch.cuda.get_device_properties(device).total_memory
                        vram_usage = vram_used / vram_total
                    else:
                        vram_usage = 0.0

                    # Check metabolic flip criteria every step
                    flip_result = relaxation_controller.check_metabolic_flip(
                        metrics=metrics,
                        vram_usage=vram_usage,
                        global_step=global_step,
                    )

                    if flip_result == "TRIGGER_FLIP":
                        # Metabolic flip triggered! Execute 9:3 → 6:6 relaxation
                        relaxation_controller.execute_relaxation(current_step=global_step)
                        relaxation_controller.current_stage_idx = 1  # Now at 6:6
                        print(f"  🔄 [RELAXATION] 9:3 → 6:6 transition initiated")

                    # V9.9.1 Multi-Stage Evolution: Check for further evolution (6:6 → 5:7 → 4:8 → 3:9)
                    # Supports PPL, step, or metrics-based triggers
                    evolution_result = relaxation_controller.check_evolution_triggers(
                        metrics=metrics,
                        vram_usage=vram_usage,
                        global_step=global_step,
                        current_ppl=last_val_ppl if last_val_ppl != float('inf') else None,
                    )

                    if evolution_result.startswith("EVOLVE_TO_"):
                        # Execute granular evolution
                        new_split = relaxation_controller.execute_granular_evolution(global_step)
                        # Reconfigure gradient scaler for new split
                        if gradient_scaler_hgs is not None:
                            gradient_scaler_hgs.reconfigure(
                                new_authority_layers=new_split[0],
                                new_sensory_layers=new_split[1],
                                alpha_range=(0.05, 0.70),
                            )
                            print(f"  ✓ [HGS] Reconfigured for {new_split[0]}:{new_split[1]} split")

                    # V9.5.2 Emergency Stress-Probe (Phase A: 3:9 Rajas)
                    if relaxation_controller.stress_probe_active:
                        # Already in stress-probe: check for exit
                        exit_result = relaxation_controller.check_stress_probe_exit(
                            metrics=metrics,
                            config=config,
                            global_step=global_step,
                        )

                        if exit_result in ("EXIT_SUCCESS", "EXIT_FORCED"):
                            # Exit stress-probe (starts gradual LR restore)
                            new_split, initial_lr = relaxation_controller.exit_stress_probe(
                                global_step=global_step,
                                exit_reason=exit_result,
                                config=config,
                            )
                            # Set initial LR (will be gradually restored)
                            for param_group in optimizer.param_groups:
                                param_group['lr'] = initial_lr
                            # Reconfigure gradient scaler for 6:6
                            if gradient_scaler_hgs is not None:
                                gradient_scaler_hgs.reconfigure(
                                    new_authority_layers=new_split[0],
                                    new_sensory_layers=new_split[1],
                                    alpha_range=(0.05, 0.70),
                                )
                                print(f"  ✓ [HGS] Reconfigured for {new_split[0]}:{new_split[1]} split")

                    # ChatGPT Guardrail: Gradual LR restore after stress-probe exit
                    if relaxation_controller.stress_probe_lr_restoring:
                        restore_lr = relaxation_controller.get_stress_probe_restore_lr(
                            global_step=global_step,
                            config=config,
                        )
                        for param_group in optimizer.param_groups:
                            param_group['lr'] = restore_lr

                    if not relaxation_controller.stress_probe_active:
                        # Not in stress-probe: check for trigger
                        stress_result = relaxation_controller.check_stress_probe(
                            metrics=metrics,
                            config=config,
                            global_step=global_step,
                        )

                        # Also check for force_stress_probe CLI flag
                        if config.force_stress_probe and not relaxation_controller.stress_probe_active:
                            stress_result = "TRIGGER_STRESS_PROBE"
                            config.force_stress_probe = False  # Only trigger once

                        if stress_result == "TRIGGER_STRESS_PROBE":
                            # Get current LR
                            current_lr = optimizer.param_groups[0]['lr']
                            # Execute stress-probe
                            new_split, new_lr = relaxation_controller.execute_stress_probe(
                                config=config,
                                current_lr=current_lr,
                                global_step=global_step,
                            )
                            # Update optimizer LR
                            for param_group in optimizer.param_groups:
                                param_group['lr'] = new_lr
                            # Reconfigure gradient scaler for 3:9 with frozen authority
                            if gradient_scaler_hgs is not None:
                                gradient_scaler_hgs.reconfigure(
                                    new_authority_layers=new_split[0],
                                    new_sensory_layers=new_split[1],
                                    alpha_range=(config.stress_probe_authority_scale, 0.70),
                                )
                                print(f"  ✓ [HGS] Reconfigured for 3:9 stress-probe (α_authority={config.stress_probe_authority_scale})")

            # Periodic CUDA memory cleanup to prevent fragmentation
            if device.type == "cuda" and global_step % 500 == 0:
                torch.cuda.empty_cache()

            # VRAM Governor - Check and resize batch if needed
            if vram_governor is not None:
                old_batch = vram_governor.current_batch_size
                new_batch, vram_actions = vram_governor.check_and_resize(
                    global_step,
                    sovereign_engine=sovereign_engine,
                )
                # Print any VRAM actions
                for action in vram_actions:
                    print(action)

                # Reinitialize DataLoader if batch size changed
                if new_batch != old_batch:
                    print(f"  🔄 Reinitializing DataLoader with batch_size={new_batch}")
                    # Get dataset from existing DataLoader (train_dataset may not be in scope)
                    dataset = train_loader.dataset
                    # IterableDataset (streaming) doesn't support shuffle
                    is_iterable = isinstance(dataset, IterableDataset)
                    train_loader = DataLoader(
                        dataset,
                        batch_size=new_batch,
                        shuffle=False if is_iterable else True,
                        num_workers=config.num_workers,
                        pin_memory=True,
                        drop_last=True,
                        prefetch_factor=2 if config.num_workers > 0 else None,
                        persistent_workers=config.num_workers > 0,
                    )
                    train_iter = iter(train_loader)
                    # Update config for logging
                    config.batch_size = new_batch
                    # Update gradient accumulation if needed
                    if vram_governor.accumulation_steps != config.gradient_accumulation:
                        config.gradient_accumulation = vram_governor.accumulation_steps

            # Logging
            if global_step % config.log_every == 0:
                elapsed = time.time() - step_start_time
                tokens_per_sec = (
                    config.log_every * config.batch_size * config.max_seq_len *
                    config.gradient_accumulation
                ) / elapsed
                lr = optimizer.param_groups[0]["lr"]

                # Quiet mode: Only print Critical 5 (Loss, PPL, S/A, GC, Conf)
                if config.quiet:
                    # Extract Critical 5 metrics
                    sa_ratio = hgs_metrics.get("s_a_ratio", 0.0) if hgs_metrics else 0.0
                    gc = metrics.get('coherence', 0.0)
                    conf = sattvic_confidence if sattvic_brake is not None else 0.0

                    # Status indicators
                    sa_ind = "+" if sa_ratio < 0.3 else ("~" if sa_ratio < 0.5 else "!")
                    gc_ind = "+" if gc > 0.76 else ("~" if gc > 0.68 else "!")
                    conf_icon = sattvic_brake.get_status_icon(conf) if sattvic_brake else ""

                    log_msg = (
                        f"Step {global_step:>6} | "
                        f"Loss:{avg_loss:.4f} | "
                        f"PPL:{metrics['ppl']:.1f} | "
                        f"S/A:{sa_ratio:.2f}{sa_ind} | "
                        f"GC:{gc:.2f}{gc_ind} | "
                        f"Conf:{conf:.2f}{conf_icon}"
                    )
                else:
                    # Verbose mode: Full logging (default)
                    # V10.7.2: Show true total peak (no reset between steps)
                    # mem_alloc = current allocated (model+optim+residual)
                    # mem_peak = all-time peak (captures forward+backward max)
                    if device.type == "cuda":
                        mem_alloc = torch.cuda.memory_allocated() / (1024**3)
                        mem_peak = torch.cuda.max_memory_allocated() / (1024**3)
                        mem_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                        mem_str = f" | Mem: {mem_alloc:.1f}GB, Peak: {mem_peak:.1f}GB/{mem_total:.1f}GB"
                    else:
                        mem_str = ""

                    # Timestamp for each log line
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    # Log message with timestamp
                    log_msg = (
                        f"[{timestamp}] Step {global_step:>6} | "
                        f"Loss: {avg_loss:.4f} | "
                        f"PPL: {metrics['ppl']:.2f} | "
                        f"LR: {lr:.2e} | "
                        f"Tok/s: {tokens_per_sec:.0f}{mem_str}"
                    )

                    # Gradient norm (tracked every step, logged every log_every)
                    if 'grad_total_norm' in metrics:
                        log_msg += f" | GradN: {metrics['grad_total_norm']:.2f}"

                    # Add decorr_loss if enabled
                    if 'decorr_loss' in metrics:
                        log_msg += f" | Decorr: {metrics['decorr_loss']:.4f}"

                    # Add ortho_loss if enabled (weight orthogonalization)
                    if 'ortho_loss' in metrics:
                        log_msg += f" | Ortho: {metrics['ortho_loss']:.4f}"

                    # Check if this is a validation step (show verbose metrics)
                    is_verbose_step = (global_step % config.eval_every == 0)

                    # Add ontological metrics
                    if config.model_type == "ontological":
                        if "coherence" in metrics:
                            log_msg += f" | Coh: {metrics['coherence']:.3f}"
                        if "onto_entropy" in metrics:
                            log_msg += f" | Ent: {metrics['onto_entropy']:.2f}"
                        # Sovereign-1 metrics
                        if "onto_phoneme_ratio" in metrics and metrics["onto_phoneme_ratio"] > 0:
                            ratio = metrics["onto_phoneme_ratio"]
                            health = "OK" if metrics.get("semantic_healthy") else "WARN"
                            log_msg += f" | R/C: {ratio:.2f} [{health}]"

                    # Add Gen 2 hierarchical metrics
                    if config.model_type == "gen2":
                        if "coherence" in metrics:
                            log_msg += f" | Coh: {metrics['coherence']:.3f}"
                        if "level_3_coh" in metrics:
                            log_msg += f" | L3: {metrics['level_3_coh']:.2f}"

                    # Add alpha for phase/hybrid models (including ontological_hybrid)
                    # V9.8.10: Check if model type contains "phase" or "hybrid"
                    if "phase" in config.model_type or "hybrid" in config.model_type:
                        log_msg += f" | α(diag): {current_alpha:.2f}"

                    # Mistral adapter diagnostics: gate value, adapter output norm, state norm
                    if config.model_type in ("mistral_cg", "mistral_hybrid"):
                        _cg_model = getattr(model, 'module', model)  # unwrap DDP
                        if hasattr(_cg_model, 'adapter_gate'):
                            _gate_val = torch.sigmoid(_cg_model.adapter_gate).item()
                            metrics['adapter_gate'] = _gate_val
                            log_msg += f" | Gate:{_gate_val:.4f}"
                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                writer.add_scalar('cg_adapter/gate', _gate_val, global_step)
                        if hasattr(_cg_model, 'phase_adapter') and is_verbose_step:
                            _adapter_norm = sum(
                                p.data.norm().item() ** 2 for p in _cg_model.phase_adapter.parameters()
                            ) ** 0.5
                            metrics['adapter_weight_norm'] = _adapter_norm
                            log_msg += f" | AdpN:{_adapter_norm:.1f}"
                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                writer.add_scalar('cg_adapter/weight_norm', _adapter_norm, global_step)
                        # Capture adapter output norm from model forward outputs
                        if isinstance(outputs, dict) and 'adapter_output_norm' in outputs:
                            _aon = outputs['adapter_output_norm']
                            metrics['adapter_output_norm'] = _aon
                            # Effective influence = gate × adapter_output_norm
                            _eff_inf = metrics.get('adapter_gate', 0) * _aon
                            metrics['cg_effective_influence'] = _eff_inf
                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                writer.add_scalar('cg_adapter/output_norm', _aon, global_step)
                                writer.add_scalar('cg_adapter/effective_influence', _eff_inf, global_step)
                        if isinstance(outputs, dict) and 'state' in outputs and outputs['state'] is not None:
                            _state_norm = outputs['state'].detach().norm(dim=-1).mean().item()
                            metrics['state_norm'] = _state_norm
                            if is_verbose_step:
                                log_msg += f" | StN:{_state_norm:.2f}"
                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                writer.add_scalar('cg_adapter/state_norm', _state_norm, global_step)
                        # State projector gradient norm (computed post-backward at ~L5579)
                        if 'cg_state_proj_grad_norm' in metrics:
                            _sp_g = metrics['cg_state_proj_grad_norm']
                            log_msg += f" | sp_grad={_sp_g:.2e}" if _sp_g < 0.001 else f" | sp_grad={_sp_g:.6f}"

                    # Phase layer training metrics (mistral_hybrid specific)
                    if config.model_type == "mistral_hybrid" and isinstance(outputs, dict):
                        _ph_corr = outputs.get('phase_correction_norm', 0.0)
                        _ph_rel = outputs.get('phase_relative_correction', 0.0)
                        _ph_cos = outputs.get('phase_cosine_sim', 0.0)
                        metrics['phase_correction_norm'] = _ph_corr
                        metrics['phase_relative_correction'] = _ph_rel
                        metrics['phase_cosine_sim'] = _ph_cos
                        log_msg += f" | PhCorr:{_ph_corr:.4f} Rel:{_ph_rel:.4f} Cos:{_ph_cos:.3f}"
                        if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                            writer.add_scalar('phase/correction_norm', _ph_corr, global_step)
                            writer.add_scalar('phase/relative_correction', _ph_rel, global_step)
                            writer.add_scalar('phase/cosine_similarity', _ph_cos, global_step)

                        # Phase PPL delta: measure every phase_ppl_delta_interval steps
                        _ppl_interval = getattr(config, 'phase_ppl_delta_interval', 500)
                        if _ppl_interval > 0 and global_step % _ppl_interval == 0 and global_step > 0:
                            # Re-run forward with measure_phase_delta=True to get backbone logits
                            with torch.no_grad():
                                _delta_out = model(x, attention_mask=None, measure_phase_delta=True)
                            if 'backbone_logits' in _delta_out:
                                _bb_logits = _delta_out['backbone_logits']
                                _ph_logits = _delta_out['logits']
                                # Compute per-token CE loss for both
                                _shift_bb = _bb_logits[:, :-1, :].contiguous().view(-1, _bb_logits.size(-1))
                                _shift_ph = _ph_logits[:, :-1, :].contiguous().view(-1, _ph_logits.size(-1))
                                _shift_y = y[:, 1:].contiguous().view(-1)
                                _bb_ce = F.cross_entropy(_shift_bb, _shift_y, reduction='mean')
                                _ph_ce = F.cross_entropy(_shift_ph, _shift_y, reduction='mean')
                                _bb_ppl = _bb_ce.exp().item()
                                _ph_ppl = _ph_ce.exp().item()
                                _ppl_delta = _bb_ppl - _ph_ppl  # positive = Phase helps
                                metrics['backbone_ppl'] = _bb_ppl
                                metrics['phase_ppl'] = _ph_ppl
                                metrics['phase_ppl_delta'] = _ppl_delta
                                _delta_pct = 100.0 * _ppl_delta / max(_bb_ppl, 1e-8)
                                print(f"  [Phase PPL] backbone={_bb_ppl:.2f} | +phase={_ph_ppl:.2f} | "
                                      f"delta={_ppl_delta:+.2f} ({_delta_pct:+.1f}%)")
                                if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                    writer.add_scalar('phase/backbone_ppl', _bb_ppl, global_step)
                                    writer.add_scalar('phase/adapted_ppl', _ph_ppl, global_step)
                                    writer.add_scalar('phase/ppl_delta', _ppl_delta, global_step)

                    # V9.4.5: Add friction metrics (for 6/6 hybrid architecture)
                    if friction_alignment != 0.0 or friction_dominance != 1.0:
                        # Color-code alignment
                        if friction_alignment > 0.1:
                            align_ind = "+"  # Synergy
                        elif friction_alignment < -0.1:
                            align_ind = "!"  # Friction
                        else:
                            align_ind = "~"  # Neutral
                        log_msg += f" | Align:{friction_alignment:+.2f}{align_ind} Dom:{friction_dominance:.2f}"

                    # Formula [1331]: 9:3 Split metrics
                    if hgs_metrics:
                        current_sa_ratio = hgs_metrics.get("s_a_ratio", 0.0)
                        alpha_sens = hgs_metrics.get("alpha_sens", 0.0)
                        # Color-code S/A ratio (< 0.5 is good, Authority dominating)
                        if current_sa_ratio < 0.3:
                            sa_ind = "+"  # Authority strongly dominant
                        elif current_sa_ratio < 0.5:
                            sa_ind = "~"  # Balanced
                        else:
                            sa_ind = "!"  # Sensory may be overriding
                        log_msg += f" | S/A:{current_sa_ratio:.2f}{sa_ind} α_s:{alpha_sens:.2f}"

                    # Sattvic Brake: Confidence score with status icon (only every 100 steps)
                    if sattvic_brake is not None and is_verbose_step:
                        conf_icon = sattvic_brake.get_status_icon(sattvic_confidence)
                        log_msg += f" | Conf:{sattvic_confidence:.2f}{conf_icon}"
                        if sattvic_lr_mult < 1.0:
                            log_msg += f" [BRAKE×{sattvic_lr_mult:.2f}]"

                    # v2.7 Training State Tracker: Knowledge state (only every 100 steps)
                    if training_state_tracker is not None and training_state_tracker.enabled and is_verbose_step:
                        know_state = training_state_tracker.state['cognitive_state']
                        log_msg += f" | Know:{know_state:.2f}"

                    # Training Qualia: L/A/S (Lucidity/Activity/Stability) with dominant state icon
                    if training_gunas is not None:
                        # Determine dominant Qualia and icon
                        if guna_s > guna_r and guna_s > guna_t:
                            guna_icon = "☀️"  # Lucidity - clarity/learning
                        elif guna_r > guna_t:
                            guna_icon = "🔥"  # Activity - dynamism/turbulence
                        else:
                            guna_icon = "🌙"  # Stability - inertia/plateau
                        log_msg += f" | L:{guna_s:.2f} A:{guna_r:.2f} S:{guna_t:.2f}{guna_icon}"

                    # Toroidal Bridge: Coherence and metacognitive status (only every 100 steps)
                    if evolutionary_bridge is not None and is_verbose_step:
                        log_msg += f" | {evolutionary_bridge.get_coherence_status()}"
                        if metacognitive_tracker is not None:
                            log_msg += f" {metacognitive_tracker.get_status()}"

                    # Full Evolutionary Flow: Multi-scale coherence and metacognitive status
                    # Only log when EvoFlow is engaged (rss_weights['evoflow'] > 0)
                    if evolutionary_engine is not None and evo_result is not None and rss_weights.get('evoflow', 0) > 0:
                        evo_micro = metrics.get('evo_micro', 0.0)
                        evo_auth = metrics.get('evo_auth', 0.0)
                        evo_sens = metrics.get('evo_sens', 0.0)
                        evo_toroid = metrics.get('evo_toroid', 0.0)
                        evo_rec = metrics.get('evo_rec', 'CONTINUE')

                        # Update last_sensory_flow for Saturation Gate
                        last_sensory_flow = evo_sens

                        # Metacognitive status icon
                        evo_icons = {
                            "BRAKE": "🛑", "SLOW_DOWN": "🐢", "RECOVER": "🔄",
                            "ACCELERATE": "🚀", "STABILIZE": "⚓", "CONTINUE": "➡️",
                        }
                        evo_icon = evo_icons.get(evo_rec, "➡️")

                        # Meso-scale delta indicator (Authority should be >= Sensory)
                        meso_delta = evo_auth - evo_sens
                        if meso_delta > 0.1:
                            meso_ind = "+"  # Authority dominant (good for 9:3)
                        elif meso_delta < -0.1:
                            meso_ind = "!"  # Sensory dominant (warning)
                        else:
                            meso_ind = "~"  # Balanced

                        log_msg += f"\n    --> [EvoFlow] Micro:{evo_micro:.2f} | Auth:{evo_auth:.2f} Sens:{evo_sens:.2f}{meso_ind} | Toroid:{evo_toroid:.2f} | {evo_rec[:4]}{evo_icon}"
                        if evo_lr_multiplier != 1.0:
                            log_msg += f" [LR×{evo_lr_multiplier:.2f}]"

                # V9.4.6: Log SNI activation
                if metrics.get('sni_triggered', False):
                    log_msg += f"\n    --> [SNI] Low entropy ({metrics.get('onto_entropy', 0):.2f}) - injecting sensory noise"

                # V9.8.0: Log RSS phase and weights
                if rss_controller is not None:
                    # Only log RSS when at least one component is engaged
                    any_engaged = any(w > 0 for w in rss_weights.values())
                    if any_engaged:
                        phase_icons = {
                            'FOUNDATION': '🏗️', 'COHERENCE': '🔄', 'FEEDBACK': '🌀',
                            'ONTOLOGY': '📜', 'SOVEREIGN': '👑'
                        }
                        phase = rss_controller.current_phase
                        icon = phase_icons.get(phase, '❓')
                        csr_pct = int(rss_weights['csr'] * 100)
                        log_msg += f"\n    {icon} [RSS] Phase: {phase} | Evo:{int(rss_weights['evoflow']*100)}% Tor:{int(rss_weights['toroidal']*100)}% CSR:{csr_pct}% Kosh:{int(rss_weights['kosha']*100)}%"

                # v2.2.1: Kosha Gyroscope Status (Homeostatic Self-Regulation)
                # Only log when Kosha is engaged (kosha_curriculum.scale > 0 or RSS kosha > 0)
                kosha_inline_engaged = (kosha_curriculum is None) or (kosha_curriculum.scale > 0) or (rss_weights.get('kosha', 0) > 0)
                if kosha_gyroscope is not None and 'gyroscope_loss' in metrics and kosha_inline_engaged:
                    gyro_loss = metrics.get('gyroscope_loss', 0.0)
                    gyro_gain = metrics.get('gyroscope_effective_gain', 0.0)
                    gyro_base_gain = metrics.get('gyroscope_base_gain', 0.0)
                    gyro_auth = metrics.get('gyroscope_authority_factor', 1.0)
                    gyro_scale = metrics.get('gyroscope_warmup_scale', 1.0)
                    # Show graduation status
                    if kosha_graduated:
                        gyro_status = "🎓GRAD"
                    elif gyro_scale < 1.0:
                        gyro_status = f"⏳{gyro_scale*100:.0f}%"
                    else:
                        gyro_status = "⚖️ON"
                    # v2.3.2: Complete Harmonic Pentad with Reflexive Domain Morph
                    gyro_mental = metrics.get('gyroscope_mental_val', 0.0)
                    gyro_physical = metrics.get('gyroscope_physical_val', 0.0)
                    gyro_intellect = metrics.get('gyroscope_intellect_val', 0.0)
                    gyro_vital = metrics.get('gyroscope_vital_val', 0.0)
                    gyro_bliss = metrics.get('gyroscope_bliss_val', 0.0)
                    # v2.3.2: Domain Morph metrics
                    domain_label = metrics.get('gyroscope_domain_label', 'LANG')
                    morph_factor = metrics.get('gyroscope_morph_factor', 0.0)
                    # v2.3.2: Use MORPHED thresholds for Physical Floor and Bliss Ceiling
                    # These are dynamically adjusted based on domain detection
                    fl_m, cl_m = config.gyroscope_floor_mental, config.gyroscope_ceiling_mental
                    # Physical floor: base + morph * (max - base)
                    fl_p = metrics.get('gyroscope_curr_phys_floor', config.gyroscope_floor_physical)
                    cl_p = config.gyroscope_ceiling_physical
                    fl_i, cl_i = config.gyroscope_floor_intellect, config.gyroscope_ceiling_intellect
                    fl_v, cl_v = config.gyroscope_floor_vital, config.gyroscope_ceiling_vital
                    fl_b = config.gyroscope_floor_bliss
                    # Bliss ceiling: base - morph * (base - min)
                    cl_b = metrics.get('gyroscope_curr_bliss_ceil', config.gyroscope_ceiling_bliss)
                    # v2.3.0: Clamp status
                    ceiling_clamp = metrics.get('gyroscope_ceiling_clamp_scalar', 1.0)
                    floor_violations = metrics.get('gyroscope_floor_violations', 0)
                    ceiling_violations = metrics.get('gyroscope_ceiling_violations', 0)
                    # Format: Kosha%[floor-ceiling] with indicator
                    # _ = below floor (push), ! = above ceiling (clamp), ✓ = in Sattvic band
                    def kosha_fmt_v23(val, floor, ceiling, name):
                        if val < floor:
                            return f"{name}:{val:.0%}_"  # Below floor - push
                        elif val > ceiling:
                            return f"{name}:{val:.0%}!"  # Above ceiling - clamp
                        else:
                            return f"{name}:{val:.0%}✓"  # In Sattvic band
                    # v2.3.2: Include MODE indicator (LANG/MATH/CODE) and morph factor (μ)
                    mode_indicator = f"MODE:{domain_label} (μ:{morph_factor:.0%})"
                    kosha_pentad = (
                        f"{mode_indicator} | "
                        f"{kosha_fmt_v23(gyro_mental, fl_m, cl_m, 'M')} "
                        f"{kosha_fmt_v23(gyro_physical, fl_p, cl_p, 'P')} "
                        f"{kosha_fmt_v23(gyro_intellect, fl_i, cl_i, 'I')} "
                        f"{kosha_fmt_v23(gyro_vital, fl_v, cl_v, 'V')} "
                        f"{kosha_fmt_v23(gyro_bliss, fl_b, cl_b, 'B')}"
                    )
                    # v2.3.0: Show clamp status with violation counts
                    if ceiling_clamp < 1.0:
                        clamp_status = f" 🔒×{ceiling_clamp:.2f}"
                    else:
                        clamp_status = ""
                    if authority_controller is not None:
                        log_msg += f"\n    {gyro_status} [GYRO] Loss:{gyro_loss:.4f} | Gain:{gyro_gain:.2f} (Base:{gyro_base_gain:.2f}×A:{gyro_auth:.2f}){clamp_status}"
                        log_msg += f"\n         [PENTAD] {kosha_pentad}"
                    else:
                        log_msg += f"\n    {gyro_status} [GYRO] Loss:{gyro_loss:.4f} | Gain:{gyro_gain:.2f}{clamp_status}"
                        log_msg += f"\n         [PENTAD] {kosha_pentad}"

                # v2.3.0: Vritti Resonance diagnostic logging (Phase 1 = read-only)
                # Only log when Kosha is engaged
                if vritti_resonance is not None and 'vritti_alignment' in metrics and kosha_inline_engaged:
                    align = metrics['vritti_alignment']
                    res_status = "🎓ACT" if vritti_resonance.active else "👁️OBS"
                    log_msg += f"\n    {res_status} [VRITTI] P-Pram:{align.get('physical_pramana', 0):.2f} | M-Vikal:{align.get('mental_vikalpa', 0):.2f} | I-Smrit:{align.get('intellect_smriti', 0):.2f}"

                # Experiential controller metrics on main step line
                if experiential_controller is not None and 'exp_g_eff' in metrics:
                    _eg = metrics['exp_g_eff']
                    _ep = metrics['exp_plasticity']
                    _eG = metrics['exp_gain']
                    _ed = metrics['exp_damping']
                    log_msg += f" | g_eff:{_eg:.2f} P:{_ep:.2f} G:{_eG:.2f} d:{_ed:.2f}"

                print(log_msg, flush=True)  # V9.7.0: Flush for real-time output when piped to tee

                # Kosha-Vritti Diagnostic System (Read-Only)
                # Only log when Kosha is engaged (kosha_curriculum.scale > 0 or RSS kosha > 0)
                kosha_log_interval = config.kosha_log_every if config.kosha_log_every > 0 else config.log_every
                kosha_engaged = (kosha_curriculum is None) or (kosha_curriculum.scale > 0) or (rss_weights.get('kosha', 0) > 0)
                if config.enable_kosha_diagnostics and global_step % kosha_log_interval == 0 and kosha_engaged:
                    try:
                        # Get logits for entropy calculation
                        kosha_logits = None
                        if config.model_type in ("ontological", "ontological_hybrid"):
                            kosha_logits = outputs.get("logits", None) if isinstance(outputs, dict) else None
                        else:
                            kosha_logits = logits if 'logits' in dir() else None

                        # Get hidden states if available
                        kosha_hidden = None
                        if hidden_state_extractor is not None:
                            kosha_hidden = hidden_state_extractor.get_hidden_states(outputs, x)

                        # V9.7.0: Use RAW gradient norm (before clipping) for meaningful Time axis
                        kosha_grad_norm = raw_grad_norm if 'raw_grad_norm' in dir() else 0.0

                        # V9.7.0: Layer-specific diagnostics - use kosha_steering_layer
                        # This ensures diagnostics measure the same layer that steering operates on
                        diag_layer = config.kosha_steering_layer
                        # V9.7.0: Skip expensive layer gradient norm in lightweight mode
                        layer_grad = 0.0
                        if not config.lightweight_diagnostics and diag_layer < 12:
                            layer_grad = compute_layer_gradient_norm(model, diag_layer)

                        # Compute diagnostics with layer-specific data
                        kosha_diag = compute_kosha_vritti_diagnostics(
                            logits=kosha_logits,
                            grad_norm=kosha_grad_norm,
                            hidden_states=kosha_hidden,
                            metrics=metrics,
                            diagnostic_layer=diag_layer,
                            layer_grad_norm=layer_grad if layer_grad > 0 else None,
                        )

                        # Format and print (include steering metrics if available) - only when Kosha is engaged
                        steering_metrics = {k: v for k, v in metrics.items() if k.startswith('kosha_')}
                        kosha_output = format_kosha_diagnostic(
                            kosha_diag,
                            include_phase=True,
                            steering_metrics=steering_metrics if steering_metrics else None,
                        )
                        print(kosha_output, flush=True)
                    except Exception as e:
                        if global_step % 100 == 0:  # Limit error spam
                            print(f"    ⚠️ [KOSHA] Diagnostic error: {e}", flush=True)

                # V9.7.0: CSR Diagnostics (Layer 7 - Concept Consolidation)
                # Only log when CSR is engaged (rss_weights['csr'] > 0)
                if csr_provider is not None and global_step % kosha_log_interval == 0 and rss_weights.get('csr', 0) > 0:
                    try:
                        # Get hidden states for CSR layer
                        csr_diag_hidden = None
                        if hidden_state_extractor is not None:
                            csr_diag_hidden = hidden_state_extractor.get_hidden_states(outputs, x)

                        # Layer-specific gradient for CSR (skip in lightweight mode)
                        csr_diag_layer = config.csr_alignment_layer
                        csr_layer_grad = 0.0
                        if not config.lightweight_diagnostics and csr_diag_layer < 12:
                            csr_layer_grad = compute_layer_gradient_norm(model, csr_diag_layer)

                        # Compute CSR diagnostics
                        csr_diag = compute_csr_diagnostics(
                            hidden_states=csr_diag_hidden,
                            csr_metrics=csr_metrics if 'csr_metrics' in dir() else None,
                            diagnostic_layer=csr_diag_layer,
                            layer_grad_norm=csr_layer_grad if csr_layer_grad > 0 else None,
                            grad_norm=raw_grad_norm if 'raw_grad_norm' in dir() else 0.0,
                        )

                        # Format and print - only when CSR is engaged
                        csr_output = format_csr_diagnostic(csr_diag)
                        print(csr_output, flush=True)
                    except Exception as e:
                        if global_step % 100 == 0:
                            print(f"    ⚠️ [CSR] Diagnostic error: {e}", flush=True)

                # V9.7.0: Ontological Bridge Diagnostics (Layer 4 - Foundational Structure)
                # Only log when Onto is engaged (onto_curriculum.scale > 0)
                onto_engaged = (onto_curriculum is None) or (onto_curriculum.scale > 0)
                if config.enable_onto_bridge and global_step % kosha_log_interval == 0 and onto_engaged:
                    try:
                        # Get hidden states for Onto Bridge layer (skip in lightweight mode)
                        onto_diag_hidden = None
                        if not config.lightweight_diagnostics and hidden_state_extractor is not None:
                            onto_diag_hidden = hidden_state_extractor.get_hidden_states(outputs, x)

                        # Layer-specific gradient for Onto Bridge (skip in lightweight mode)
                        onto_diag_layer = config.onto_bridge_layer
                        onto_layer_grad = 0.0
                        if not config.lightweight_diagnostics and onto_diag_layer < 12:
                            onto_layer_grad = compute_layer_gradient_norm(model, onto_diag_layer)

                        # Get onto_bridge module (skip forward pass in lightweight mode)
                        onto_bridge_module = None
                        if not config.lightweight_diagnostics:
                            onto_bridge_module = onto_bridge if 'onto_bridge' in dir() else None

                        # Get onto metrics from training step (always available, no extra computation)
                        onto_diag_metrics = {k: v for k, v in metrics.items() if k.startswith('onto_')}

                        # Compute Onto Bridge diagnostics
                        onto_diag = compute_onto_bridge_diagnostics(
                            hidden_states=onto_diag_hidden,
                            onto_metrics=onto_diag_metrics if onto_diag_metrics else None,
                            onto_bridge=onto_bridge_module,
                            diagnostic_layer=onto_diag_layer,
                            layer_grad_norm=onto_layer_grad if onto_layer_grad > 0 else None,
                            grad_norm=raw_grad_norm if 'raw_grad_norm' in dir() else 0.0,
                        )

                        # Format and print - only when Onto is engaged
                        onto_output = format_onto_bridge_diagnostic(onto_diag)
                        print(onto_output, flush=True)
                    except Exception as e:
                        if global_step % 100 == 0:
                            print(f"    ⚠️ [ONTO] Diagnostic error: {e}", flush=True)

                # V9.8.0: Sovereign State Diagnostics for ontological_hybrid model
                # Only log when Kosha is engaged (since Bhava/Kosha/Vritti are part of sovereign synthesis)
                sovereign_state_engaged = (kosha_curriculum is None) or (kosha_curriculum.scale > 0) or (rss_weights.get('kosha', 0) > 0)
                if config.model_type == "ontological_hybrid" and sovereign_state_engaged:
                    try:
                        # Extract state and delta_S from outputs dict
                        sovereign_state = None
                        sovereign_delta = None
                        if isinstance(outputs, dict):
                            sovereign_state = outputs.get('state', None)
                            sovereign_delta = outputs.get('delta_S', None)

                        if sovereign_state is not None:
                            sovereign_diag = compute_sovereign_state_diagnostics(
                                state=sovereign_state,
                                delta_S=sovereign_delta,
                                grad_norm=raw_grad_norm if 'raw_grad_norm' in dir() else 0.0,
                            )
                            sovereign_output = format_sovereign_state_diagnostic(sovereign_diag)
                            print(sovereign_output, flush=True)
                    except Exception as e:
                        if global_step % 100 == 0:
                            print(f"    ⚠️ [SOVEREIGN] Diagnostic error: {e}", flush=True)

                # TensorBoard: Log gradient norm at log_every cadence for variance visibility
                if tb_writer is not None and 'grad_total_norm' in metrics:
                    tb_writer.add_scalar("grad/total_norm", metrics['grad_total_norm'], global_step)
                    if 'raw_grad_norm' in dir() and raw_grad_norm is not None:
                        tb_writer.add_scalar("grad/raw_norm_pre_clip", raw_grad_norm, global_step)
                    if 'variance_dampen' in metrics:
                        tb_writer.add_scalar("grad/variance_dampen", metrics['variance_dampen'], global_step)
                    if 'cg_state_proj_grad_norm' in metrics:
                        tb_writer.add_scalar("conscious_gen/state_proj_grad_norm", metrics['cg_state_proj_grad_norm'], global_step)

                step_start_time = time.time()

            # Evaluation
            if global_step % config.eval_every == 0:
                val_loss, val_metrics = evaluate(
                    model, val_loader, device, config, autocast_dtype,
                    sovereign_loss=sovereign_loss,
                    sovereign_engine=sovereign_engine,
                    cached_val_batches=cached_val_batches,
                )
                val_ppl = val_metrics['ppl']
                last_val_ppl = val_ppl  # V9.7.0: Update for EvoFlow Fluency Gate

                # V11.3: Val PPL Stagnation Detector — auto-reduce auxiliary losses
                # when val PPL plateaus to redirect gradient capacity to CE loss.
                # V11.3.3: Fix inf initialization — first eval seeds the baseline
                if _val_ppl_best == float('inf'):
                    _val_ppl_best = val_ppl
                    print(f"  📊 [AUX-SCALE] Baseline val PPL set to {val_ppl:.2f}")
                _improvement = (_val_ppl_best - val_ppl) / max(_val_ppl_best, 1.0) * 100
                if _improvement > _AUX_STAGNATION_IMPROVE_PCT:
                    # Meaningful improvement — reset counter, restore scale slowly
                    _val_ppl_best = val_ppl
                    _val_ppl_no_improve_count = 0
                    if _aux_loss_scale < 1.0:
                        _aux_loss_scale = min(1.0, _aux_loss_scale * 1.5)
                        print(f"  📈 [AUX-SCALE] Val PPL improved to {val_ppl:.2f}! "
                              f"Restoring aux scale → {_aux_loss_scale:.3f}")
                else:
                    _val_ppl_no_improve_count += 1
                    if _val_ppl_no_improve_count >= _AUX_STAGNATION_PATIENCE:
                        old_scale = _aux_loss_scale
                        _aux_loss_scale = max(
                            _AUX_STAGNATION_FLOOR,
                            _aux_loss_scale * _AUX_STAGNATION_DECAY,
                        )
                        if old_scale != _aux_loss_scale:
                            print(f"  ⚠️ [AUX-SCALE] Val PPL stagnant for "
                                  f"{_val_ppl_no_improve_count} evals "
                                  f"(best={_val_ppl_best:.2f}, current={val_ppl:.2f}). "
                                  f"Reducing auxiliary loss scale: {old_scale:.3f} → "
                                  f"{_aux_loss_scale:.3f}")
                        _val_ppl_no_improve_count = 0  # Reset for next patience window

                # V9.9.12c: PhaseAttention Health Dashboard (diagnostic only)
                # Runs at --phase_health_interval (default 500) to reduce log noise
                # V20: Auto-scaling overrides phase_health_interval from _slot_scaling
                _ph_interval = getattr(config, 'phase_health_interval', 500)
                if hasattr(config, '_slot_scaling') and 'phase_health_interval' in config._slot_scaling:
                    _ph_interval = config._slot_scaling['phase_health_interval']
                if config.model_type in ('phase', 'hybrid', 'ontological_hybrid') and global_step % _ph_interval == 0:
                    try:
                        enable_health_diagnostics_capture(model, True)
                        # Run a single forward pass to capture phase tensors
                        with torch.no_grad():
                            if cached_val_batches and len(cached_val_batches) > 0:
                                # Rotate through cached batches so R_k isn't frozen
                                # on the same input every eval step
                                health_batch_idx = (global_step // config.log_every) % len(cached_val_batches)
                                health_batch = cached_val_batches[health_batch_idx]
                            else:
                                health_batch = next(iter(val_loader))
                            # V11.2: Truncate to avoid OOM — full seq_len forward
                            # pass without TBPTT allocates [B,H,N,N] attention
                            # (~25 GiB at N=32768). 512 tokens is plenty for
                            # phase health metrics (collapse, drift, redundancy).
                            health_x = health_batch[0][:1, :512].to(device)
                            if config.mixed_precision != "none":
                                with torch.amp.autocast('cuda', dtype=autocast_dtype):
                                    _ = model(health_x)
                            else:
                                _ = model(health_x)
                        health_metrics = compute_phase_health_diagnostics(model)
                        enable_health_diagnostics_capture(model, False)

                        # Log health metrics
                        print(f"\n  📊 [PHASE HEALTH] Step {global_step}")
                        print(f"     ├─ R_k (key collapse):    {health_metrics['R_k']:.4f} {'⚠️' if health_metrics['R_k'] > 0.5 else '✓'}")
                        print(f"     ├─ R_q (query collapse):  {health_metrics['R_q']:.4f} {'⚠️' if health_metrics['R_q'] > 0.5 else '✓'}")
                        print(f"     ├─ Amp-Phase Corr:        {health_metrics['amp_phase_corr']:.4f} {'⚠️' if abs(health_metrics['amp_phase_corr']) > 0.5 else '✓'}")
                        print(f"     ├─ Head Redundancy:       {health_metrics['head_redundancy']:.4f} {'⚠️' if health_metrics['head_redundancy'] > 0.8 else '✓'}")
                        print(f"     ├─ Phase Drift Mean:      {health_metrics['phase_drift_mean']:.4f} {'⚠️' if health_metrics['phase_drift_mean'] < 0.01 else '✓'}")
                        print(f"     ├─ Phase Drift Std:       {health_metrics['phase_drift_std']:.4f}")
                        # Show phase diversity loss status if active
                        if phase_diversity_enabled and phase_diversity_controller is not None:
                            pd_status = phase_diversity_controller.get_status()
                            esc = pd_status.get('phase_div_escalation', 0)
                            esc_str = f" esc={esc}x" if esc > 0 else ""
                            surr_str = " SURRENDERED" if phase_diversity_controller._surrendered else ""
                            print(f"     └─ Phase Diversity:       λ={pd_status['phase_div_lambda']:.4f} R_ema={pd_status['phase_div_R_ema']:.4f} target={pd_status['phase_div_target_R']:.2f}{esc_str}{surr_str}")
                        else:
                            print(f"     └─ Phase Diversity:       OFF")

                        # Add to metrics for tensorboard/wandb logging
                        for k, v in health_metrics.items():
                            metrics[f'health_{k}'] = v

                        # V11.3: Auto-enable phase diversity when R_k or R_q collapse detected
                        # If R_k > 0.5 OR R_q > 0.5 (collapsed) and phase diversity is not active,
                        # automatically enable adaptive phase diversity to push phases apart.
                        # V11.x: Now also triggers on R_q collapse (symmetric regularization).
                        # This is a self-healing mechanism — no restart needed.
                        _rk_collapsed = health_metrics['R_k'] > 0.5
                        _rq_collapsed = health_metrics['R_q'] > 0.5
                        if ((_rk_collapsed or _rq_collapsed) and
                                not phase_diversity_enabled and
                                config.model_type in ('phase', 'hybrid', 'ontological_hybrid')):
                            # Seed with whichever R is worse
                            _seed_R = max(health_metrics['R_k'], health_metrics['R_q'])
                            num_phase_layers = enable_phase_diversity_capture(model, enable=True)
                            phase_diversity_controller = AdaptivePhaseDiversityController(
                                warmup_steps=config.warmup_steps,
                                target_R=0.45,    # V11.4c: raised from 0.30 — prevent collapse without starving LM
                                lambda_init=0.01,
                                lambda_max=0.5,   # V11.4c: lowered from 2.0 — less aggressive ceiling
                                eta=0.3,
                                ramp_multiplier=0.0,  # No ramp — collapse is already severe
                                task_loss_scaling=True,
                                task_loss_alpha=0.40,
                            )
                            # Seed R_ema with worst R to avoid warmup lag
                            phase_diversity_controller.R_ema = _seed_R
                            phase_diversity_enabled = True
                            _rk_above_threshold_count = 0  # V11.3.1: Track for emergency escalation
                            _trigger = "R_k" if _rk_collapsed else "R_q"
                            _trigger_val = health_metrics['R_k'] if _rk_collapsed else health_metrics['R_q']
                            print(f"\n  🚨 [AUTO-PHASE-DIVERSITY] {_trigger}={_trigger_val:.4f} > 0.5 — enabling adaptive phase diversity")
                            print(f"     ├─ Target R: 0.45 (current R_k: {health_metrics['R_k']:.4f}, R_q: {health_metrics['R_q']:.4f})")
                            print(f"     ├─ Mode: TASK-SCALED+STALL-DETECT (α=0.40, log-scaled)")
                            print(f"     ├─ λ_max: 0.5, η: 0.3 (collapse guard, not diversity maximizer)")
                            print(f"     └─ Layers: {num_phase_layers}")

                        # V11.3.3: R_k/R_q Emergency Escalation (robust)
                        # V11.3.2 required 5 CONSECUTIVE checks above 0.5, but R_k
                        # oscillates right at the boundary (0.499→0.501→0.499), so the
                        # counter kept resetting and the emergency never fired.
                        # Fix: lower threshold to 0.45, reduce patience to 3, and
                        # only decrement (not reset) when R dips below threshold.
                        # V11.x: Also triggers on R_q > 0.45 (symmetric monitoring).
                        elif (phase_diversity_enabled and
                                phase_diversity_controller is not None and
                                (health_metrics['R_k'] > 0.45 or health_metrics['R_q'] > 0.45)):
                            if not hasattr(phase_diversity_controller, '_rk_emergency_count'):
                                phase_diversity_controller._rk_emergency_count = 0
                            phase_diversity_controller._rk_emergency_count += 1

                            if (phase_diversity_controller._rk_emergency_count >= 3 and
                                    phase_diversity_controller.current_lambda < phase_diversity_controller.lambda_max * 0.5):
                                old_lambda = phase_diversity_controller.current_lambda
                                floor_val = phase_diversity_controller.lambda_max * 0.5
                                phase_diversity_controller.current_lambda = floor_val
                                phase_diversity_controller.lambda_floor = floor_val
                                phase_diversity_controller.eta = min(0.5, phase_diversity_controller.eta * 2)
                                phase_diversity_controller._rk_emergency_count = 0
                                _worst_R_label = "R_k" if health_metrics['R_k'] >= health_metrics['R_q'] else "R_q"
                                _worst_R_val = max(health_metrics['R_k'], health_metrics['R_q'])
                                print(f"\n  🔴 [PHASE-DIV EMERGENCY] {_worst_R_label}={_worst_R_val:.4f} stuck above 0.45 "
                                      f"for 3+ evals — force-escalating (R_k={health_metrics['R_k']:.4f}, R_q={health_metrics['R_q']:.4f}):")
                                print(f"     ├─ λ: {old_lambda:.4f} → {floor_val:.4f} "
                                      f"(jumped to λ_max/2, floor set)")
                                print(f"     ├─ η: {phase_diversity_controller.eta:.2f} (doubled for faster response)")
                                print(f"     └─ λ_floor={floor_val:.4f} prevents task-loss formula from overriding")
                        else:
                            # Both R_k and R_q below 0.45 — decrement counter (don't hard-reset)
                            # Only fully clear floor once both R values drop well below threshold
                            if (phase_diversity_enabled and
                                    phase_diversity_controller is not None and
                                    hasattr(phase_diversity_controller, '_rk_emergency_count')):
                                # Decrement by 1 instead of resetting to 0
                                phase_diversity_controller._rk_emergency_count = max(
                                    0, phase_diversity_controller._rk_emergency_count - 1)
                                # Only clear floor when both R_k and R_q are genuinely healthy (< 0.35)
                                if (health_metrics['R_k'] < 0.35 and
                                        health_metrics['R_q'] < 0.35 and
                                        hasattr(phase_diversity_controller, 'lambda_floor')):
                                    if phase_diversity_controller.lambda_floor > 0:
                                        print(f"  ✅ [PHASE-DIV] R_k={health_metrics['R_k']:.4f}, R_q={health_metrics['R_q']:.4f} healthy — clearing emergency λ_floor")
                                    phase_diversity_controller.lambda_floor = 0.0

                    except Exception as e:
                        print(f"\n  ⚠️ [PHASE HEALTH] Diagnostic failed: {e}")
                        enable_health_diagnostics_capture(model, False)  # Ensure cleanup

                # V10.6.6: Quad Utilization Sanity Check (periodic)
                if config.enable_quad_utilization_checks and global_step % config.quad_utilization_check_interval == 0:
                    try:
                        # Use first validation batch for quick check
                        if cached_val_batches and len(cached_val_batches) > 0:
                            quad_check_batch = cached_val_batches[0][0][:2].to(device)
                        else:
                            quad_check_batch = next(iter(val_loader))[0][:2].to(device)
                        passed, contrib, msg = check_quad_utilization(
                            model, quad_check_batch, device, config.quad_utilization_warn_threshold,
                            autocast_dtype=autocast_dtype if config.mixed_precision != "none" else None,
                        )
                        if not passed:
                            print(f"\n  ⚠️  [QUAD CHECK] Step {global_step}: {msg}")
                    except Exception as e:
                        if global_step % 500 == 0:  # Limit spam
                            print(f"\n  ⚠️  [QUAD CHECK] Error: {e}")

                # V10.6.7: Lightweight Probe Hooks (periodic diagnostic)
                if probe_hooks is not None and global_step % config.probe_hook_interval == 0:
                    try:
                        probe_results = probe_hooks.run_probes(global_step)
                        warnings = [(n, m) for n, (p, m) in probe_results.items() if not p]
                        if warnings:
                            print(f"\n  🔬 [PROBE] Step {global_step}:")
                            for name, msg in warnings:
                                print(f"     ⚠️  {name}: {msg}")
                    except Exception as e:
                        if global_step % 1000 == 0:  # Limit spam
                            print(f"\n  ⚠️  [PROBE] Error: {e}")

                # V9.9.1: Inverted Layer Curriculum Update
                # V9.9.3: With Sovereign Reset Protocol (Gemini's "Soft-Reset" recommendations)
                # V9.9.4: Now with composite ReadinessIndex (ChatGPT's insight)
                if inverted_layer_curriculum is not None:
                    # V9.9.4: Try to extract geometry metrics for composite readiness check
                    # These come from val_metrics if available (phase coherence, state-delta)
                    _phase_coherence = val_metrics.get('phase_coherence', None)
                    _state_delta_norm = val_metrics.get('state_delta_norm', None)

                    # Also try to get from sovereign diagnostics if computed
                    if _state_delta_norm is None and 'sovereign_diag' in dir() and sovereign_diag:
                        _state_delta_norm = sovereign_diag.get('delta_magnitude', None)

                    ilc_result = inverted_layer_curriculum.update(
                        step=global_step,
                        current_ppl=val_ppl,
                        phase_coherence=_phase_coherence,
                        state_delta_norm=_state_delta_norm,
                    )

                    # Apply updated per-layer weights to model
                    inverted_layer_curriculum.apply_to_model(model)

                    # V9.9.3: Momentum Dampening for completed layer transitions
                    # When a layer completes its transition (α reaches target), dampen its
                    # optimizer momentum to allow it to find its new "ontological direction"
                    if ilc_result['completed_transitions']:
                        dampen_layer_momentum(
                            optimizer=optimizer,
                            model=model,
                            layer_indices=ilc_result['completed_transitions'],
                            dampen_factor=0.5,  # 50% decay per Gemini's recommendation
                            verbose=True,
                        )

                    # Handle split change - reconfigure gradient scaler
                    # V9.9.3: CRITICAL - Must call reconfigure() to re-register hooks!
                    # Just setting properties causes Gradient Stagnation (Gemini's warning)
                    if ilc_result['split_changed'] and gradient_scaler_hgs is not None:
                        new_auth, new_sens = ilc_result['current_split']
                        gradient_scaler_hgs.reconfigure(
                            new_authority_layers=new_auth,
                            new_sensory_layers=new_sens,
                            alpha_range=(0.1, 0.7),  # Standard range for inverted curriculum
                            new_warmup_steps=100,    # Quick re-warmup after split change
                        )
                        print(f"  🔧 [HGS] Re-registered hooks for {new_auth}:{new_sens} split")

                    # Handle seq_len change (when using delegated seq_len_curriculum)
                    # V9.9.2: If seq_len is delegated, handle reload here instead of separate block
                    # V9.9.3: Now with Sovereign Reset Protocol
                    if ilc_result['seq_len_changed'] and inverted_layer_curriculum.seq_len_curriculum is not None:
                        old_seq_len = current_seq_len
                        current_seq_len = ilc_result['current_seq_len']

                        print(inverted_layer_curriculum.seq_len_curriculum.get_transition_message(
                            global_step, old_seq_len, current_seq_len
                        ))

                        # V9.9.3: Sovereign Reset Protocol - clear buffers before reload
                        reset_result = on_seq_len_transition(
                            optimizer=optimizer,
                            device=device,
                            old_seq_len=old_seq_len,
                            new_seq_len=current_seq_len,
                            grad_accum_counter=accumulation_step,
                            verbose=True,
                        )

                        # Recalculate batch size for new sequence length
                        old_batch = config.batch_size
                        new_batch = int(seq_curriculum_ref_batch * (seq_curriculum_ref_seq_len / current_seq_len))
                        new_batch = max(1, min(new_batch, config.batch_size_max))
                        config.batch_size = new_batch

                        print(f"  📏 [INVERTED CURRICULUM] Reloading dataloader:")
                        print(f"     seq_len: {old_seq_len} → {current_seq_len}")
                        print(f"     batch:   {old_batch} → {new_batch}")

                        # Reload data with new sequence length
                        train_loader, val_loader = load_data(config, tokenizer, seq_len_override=current_seq_len)
                        train_iter = iter(train_loader)
                        inverted_layer_curriculum.seq_len_curriculum.mark_data_reloaded()

                        # V9.9.3: Set skip flag for VRAM stabilization
                        _skip_next_step = reset_result['skip_step']
                        print(f"  ✅ Dataloader reloaded. All buffers synchronized.")

                    # Log curriculum status periodically
                    if global_step % (config.eval_every * 5) == 0:
                        status = inverted_layer_curriculum.get_status()
                        print(f"  🎓 [CURRICULUM] Stage {status['stage']}/{status['total_stages']-1} | "
                              f"Split: {status['split']} | Seq: {status['seq_len']} | "
                              f"Transitioning: {status['transitioning_layers']} layers")

                # V9.8.9: Dynamic Window Scheduler Update
                if dynamic_window_scheduler is not None:
                    # Get VRAM usage for pressure override
                    vram_usage = 0.0
                    if device.type == "cuda":
                        vram_used = torch.cuda.memory_allocated(device)
                        vram_total = torch.cuda.get_device_properties(device).total_memory
                        vram_usage = vram_used / vram_total

                    # Update window size based on PPL
                    dws_result = dynamic_window_scheduler.update(
                        step=global_step,
                        val_ppl=val_ppl,
                        vram_usage=vram_usage,
                    )

                    # Log window changes (or diagnostic info)
                    if dws_result['changed'] or dws_result['would_change']:
                        progress_pct = int(dws_result['interpolation_progress'] * 100)
                        if config.enable_dynamic_window:
                            log_msg = f"  📏 [DWS] Window: {dws_result['window']} → {dws_result['target']} ({progress_pct}% interpolated)"
                            log_msg += f" | Reason: {dws_result['reason']}"
                            if dws_result['cooldown_active']:
                                log_msg += f" | Cooldown: {dws_result['steps_until_cooldown']} steps"
                            print(log_msg)

                            # Apply window size to model if it supports it
                            if hasattr(model, 'window_size'):
                                old_window = model.window_size
                                model.window_size = dws_result['window']
                                if old_window != dws_result['window']:
                                    print(f"     Updated model window: {old_window} → {dws_result['window']}")
                            elif hasattr(model, 'config') and hasattr(model.config, 'window_size'):
                                old_window = model.config.window_size
                                model.config.window_size = dws_result['window']
                                if old_window != dws_result['window']:
                                    print(f"     Updated model.config window: {old_window} → {dws_result['window']}")
                        else:
                            # Diagnostic mode (disabled)
                            if dws_result['would_change']:
                                log_msg = f"  📏 [DWS-DIAGNOSTIC] WOULD CHANGE: {dws_result['window']} → {dws_result['target']}"
                                log_msg += f" | Reason: {dws_result['reason']}"
                                if dws_result['cooldown_active']:
                                    log_msg += f" | (cooldown: {dws_result['steps_until_cooldown']} steps)"
                                print(log_msg)

                # V9.8.7: Dynamic Three-Phase Gyroscope Engagement
                # Phase 1: CONSTRUCTION (PPL > 50) - Gyroscope OFF, freedom to learn
                # Phase 2: REFINEMENT (30 < PPL < 50) - Gyroscope RELAXED, gentle guidance
                # Phase 3: POLISHING (PPL < 30) - Gyroscope ACTIVE, firm homeostasis
                # Only activates when explicitly enabled via --enable_kosha_gyroscope
                if config.enable_kosha_gyroscope and kosha_gyroscope is None and KOSHA_GYROSCOPE_AVAILABLE:

                    # Phase transition: CONSTRUCTION -> REFINEMENT
                    if (gyroscope_phase == "CONSTRUCTION" and
                        val_ppl < config.gyroscope_engage_ppl):

                        gyroscope_phase = "REFINEMENT"
                        print(f"\n  {'='*60}")
                        print(f"  🎯 PHASE 2: REFINEMENT at step {global_step}")
                        print(f"     Val PPL {val_ppl:.2f} < threshold {config.gyroscope_engage_ppl}")
                        print(f"     Gyroscope: RELAXED (gentle guidance)")
                        print(f"       ceiling_clamp: {config.gyroscope_relaxed_ceiling_clamp}")
                        print(f"       floor_push: {config.gyroscope_relaxed_floor_push}")
                        print(f"  {'='*60}\n")

                        # Initialize with RELAXED settings
                        kosha_gyroscope = KoshaGyroscopicLoss(
                            floor_mental=config.gyroscope_floor_mental,
                            ceiling_mental=config.gyroscope_ceiling_mental,
                            floor_physical=config.gyroscope_floor_physical,
                            ceiling_physical=config.gyroscope_ceiling_physical,
                            floor_intellect=config.gyroscope_floor_intellect,
                            ceiling_intellect=config.gyroscope_ceiling_intellect,
                            floor_vital=config.gyroscope_floor_vital,
                            ceiling_vital=config.gyroscope_ceiling_vital,
                            floor_bliss=config.gyroscope_floor_bliss,
                            ceiling_bliss=config.gyroscope_ceiling_bliss,
                            # RELAXED settings
                            floor_push_factor=config.gyroscope_relaxed_floor_push,
                            ceiling_clamp_factor=config.gyroscope_relaxed_ceiling_clamp,
                            domain_morph_enabled=config.gyroscope_domain_morph_enabled,
                            domain_morph_ema_decay=config.gyroscope_domain_morph_ema_decay,
                            domain_morph_internal_weight=config.gyroscope_domain_morph_internal_weight,
                            domain_morph_external_weight=config.gyroscope_domain_morph_external_weight,
                            trap_threshold=config.gyroscope_trap_threshold,
                            gate_threshold=config.gyroscope_gate_threshold,
                            balance_target=config.gyroscope_balance_target,
                            gate_temperature=config.gyroscope_gate_temperature,
                            damper_steepness=config.gyroscope_damper_steepness,
                            gate_steepness=config.gyroscope_gate_steepness,
                            rip_multiplier=config.gyroscope_rip_multiplier,
                            steepness=config.gyroscope_steepness,
                            base_gain=config.gyroscope_base_gain,
                            max_gain=config.gyroscope_max_gain,
                            ppl_ceiling=config.gyroscope_ppl_ceiling,
                            target_ppl=config.gyroscope_target_ppl,
                            temporal_window=config.gyroscope_temporal_window,
                            vital_momentum_enabled=config.gyroscope_vital_momentum,
                        ).to(device)

                        kosha_graduation_monitor = GraduationMonitor(
                            target_ppl=config.gyroscope_graduation_ppl,
                            stability_window=config.gyroscope_graduation_window,
                            variance_threshold=config.gyroscope_graduation_variance,
                        )

                        if tb_writer is not None:
                            tb_writer.add_scalar("gyro/phase", 2.0, global_step)
                            tb_writer.add_scalar("gyro/refinement_start_ppl", val_ppl, global_step)

                    # Phase transition: REFINEMENT -> POLISHING
                    elif (gyroscope_phase == "REFINEMENT" and
                          val_ppl < config.gyroscope_active_ppl and
                          kosha_gyroscope is not None):

                        gyroscope_phase = "POLISHING"
                        print(f"\n  {'='*60}")
                        print(f"  🔱 PHASE 3: POLISHING at step {global_step}")
                        print(f"     Val PPL {val_ppl:.2f} < threshold {config.gyroscope_active_ppl}")
                        print(f"     Gyroscope: ACTIVE (firm homeostasis)")
                        print(f"       ceiling_clamp: {config.gyroscope_active_ceiling_clamp}")
                        print(f"       floor_push: {config.gyroscope_active_floor_push}")
                        print(f"  {'='*60}\n")

                        # Reinitialize with ACTIVE settings
                        kosha_gyroscope = KoshaGyroscopicLoss(
                            floor_mental=config.gyroscope_floor_mental,
                            ceiling_mental=config.gyroscope_ceiling_mental,
                            floor_physical=config.gyroscope_floor_physical,
                            ceiling_physical=config.gyroscope_ceiling_physical,
                            floor_intellect=config.gyroscope_floor_intellect,
                            ceiling_intellect=config.gyroscope_ceiling_intellect,
                            floor_vital=config.gyroscope_floor_vital,
                            ceiling_vital=config.gyroscope_ceiling_vital,
                            floor_bliss=config.gyroscope_floor_bliss,
                            ceiling_bliss=config.gyroscope_ceiling_bliss,
                            # ACTIVE settings
                            floor_push_factor=config.gyroscope_active_floor_push,
                            ceiling_clamp_factor=config.gyroscope_active_ceiling_clamp,
                            domain_morph_enabled=config.gyroscope_domain_morph_enabled,
                            domain_morph_ema_decay=config.gyroscope_domain_morph_ema_decay,
                            domain_morph_internal_weight=config.gyroscope_domain_morph_internal_weight,
                            domain_morph_external_weight=config.gyroscope_domain_morph_external_weight,
                            trap_threshold=config.gyroscope_trap_threshold,
                            gate_threshold=config.gyroscope_gate_threshold,
                            balance_target=config.gyroscope_balance_target,
                            gate_temperature=config.gyroscope_gate_temperature,
                            damper_steepness=config.gyroscope_damper_steepness,
                            gate_steepness=config.gyroscope_gate_steepness,
                            rip_multiplier=config.gyroscope_rip_multiplier,
                            steepness=config.gyroscope_steepness,
                            base_gain=config.gyroscope_base_gain,
                            max_gain=config.gyroscope_max_gain,
                            ppl_ceiling=config.gyroscope_ppl_ceiling,
                            target_ppl=config.gyroscope_target_ppl,
                            temporal_window=config.gyroscope_temporal_window,
                            vital_momentum_enabled=config.gyroscope_vital_momentum,
                        ).to(device)

                        if tb_writer is not None:
                            tb_writer.add_scalar("gyro/phase", 3.0, global_step)
                            tb_writer.add_scalar("gyro/polishing_start_ppl", val_ppl, global_step)

                # V9.8.5: Use REAL toroidal coherence for PID, not hardcoded default
                # The evaluate() function discards coherence metrics, so we use the
                # training loop's toroidal_coherence which measures actual cognitive
                # continuity (O1↔O12 cosine similarity).
                # Fallback to val_metrics only if toroidal_coherence not yet computed.
                if 'toroidal_coherence' in dir() and toroidal_coherence is not None:
                    current_coh = toroidal_coherence
                else:
                    current_coh = val_metrics.get('coherence', 0.75)

                # v2.2.1: Kosha Gyroscope Graduation Check
                # Model graduates when PPL is stable below threshold
                if kosha_graduation_monitor is not None and not kosha_graduated:
                    if kosha_graduation_monitor.check(val_ppl, global_step):
                        kosha_graduated = True
                        if kosha_curriculum_controller is not None:
                            kosha_curriculum_controller.check_graduation(val_ppl, global_step)

                        # Graduation ceremony!
                        print(f"\n  {'='*60}")
                        print(f"  🎓 KOSHA GYROSCOPE GRADUATION at step {global_step}")
                        grad_info = kosha_graduation_monitor.graduation_info
                        print(f"     Mean PPL: {grad_info['avg_ppl']:.2f} < {config.gyroscope_graduation_ppl}")
                        print(f"     PPL σ:    {grad_info['std_ppl']:.3f} < {config.gyroscope_graduation_variance}")
                        print(f"     Model has learned to self-regulate!")
                        print(f"     Gyroscope transitioning to ramp-down phase...")

                        # v2.3.0: Activate Vritti Resonance Loss for Phase 2
                        if vritti_resonance is not None:
                            vritti_resonance.activate()
                            print(f"  🔱 [VRITTI RESONANCE] Activated for Phase 2!")
                            print(f"     Loss will now enforce Kosha-Vritti alignment")
                        print(f"  {'='*60}\n")

                        # Save rip logger summary if enabled
                        if kosha_rip_logger is not None:
                            summary_path = kosha_rip_logger.save_session_summary()
                            health, health_msg = kosha_rip_logger.get_health_assessment()
                            print(f"  📊 Rip Statistics: {kosha_rip_logger.format_status_line()}")
                            print(f"     Health: {health.upper()} - {health_msg}")
                            print(f"     Summary saved: {summary_path}")

                        # TensorBoard logging for graduation
                        if tb_writer is not None:
                            tb_writer.add_scalar("gyro/graduated", 1.0, global_step)
                            tb_writer.add_scalar("gyro/graduation_step", global_step, global_step)

                    # TensorBoard logging for gyroscope during training
                    if tb_writer is not None and not kosha_graduated and kosha_graduation_monitor is not None:
                        grad_status = kosha_graduation_monitor.get_status()
                        if 'avg_ppl' in grad_status:
                            tb_writer.add_scalar("gyro/mean_ppl", grad_status['avg_ppl'], global_step)
                            tb_writer.add_scalar("gyro/ppl_variance", grad_status['std_ppl'], global_step)

                # Conscious Generation Curriculum: PPL-gated stage transitions
                if cg_stage_manager is not None:
                    _cg_transition = cg_stage_manager.update(val_ppl, global_step)
                    if _cg_transition:
                        print(_cg_transition)
                        print(f"  [CG Curriculum] Current lambdas: {cg_stage_manager.step(global_step)}")
                        print(f"  [CG Curriculum] Field-integrated softmax: {cg_stage_manager.use_field_integrated_softmax}")

                # Curriculum Controller Update - check for phase transitions
                if curriculum_controller is not None:
                    transition_msg = curriculum_controller.update(val_ppl, global_step)
                    if transition_msg:
                        print(transition_msg)
                        # Apply config overrides for new phase
                        overrides = curriculum_controller.get_config_overrides()
                        for key, value in overrides.items():
                            if hasattr(config, key):
                                setattr(config, key, value)
                        # Log new weights
                        weights = curriculum_controller.get_loss_weights()
                        active = [k for k, v in weights.items() if isinstance(v, bool) and v]
                        print(f"  [CURRICULUM] Active systems: {', '.join(active) if active else 'None (pure LM)'}")
                        print(f"  [CURRICULUM] Loss weights: bhava={weights['bhava']:.3f} csr={weights['csr']:.3f} "
                              f"evo={weights['evo']:.3f} b1={weights['b1_lambda']:.3f}")

                    # Log curriculum status periodically
                    if global_step % (config.eval_every * 5) == 0:
                        status = curriculum_controller.get_status()
                        avg_ppl_str = f"{status['avg_recent_ppl']:.2f}" if status['avg_recent_ppl'] else "N/A"
                        print(f"  📚 [CURRICULUM] Phase: {status['phase']} | "
                              f"Avg PPL: {avg_ppl_str} | "
                              f"Steps in phase: {status['steps_in_phase']}")

                # V9.8.6: Onto Bridge Three-Phase Curriculum Update (Layer 4 - Foundation)
                if onto_curriculum is not None:
                    old_phase = onto_curriculum.phase
                    onto_curriculum.update(val_ppl, global_step)
                    # Log graduation event
                    if onto_curriculum.graduated and old_phase != onto_curriculum.phase:
                        print(f"  🎓 [Onto] Graduated from POLISHING phase - Onto loss weight = 0.0")
                    # Periodic logging - only when engaged (scale > 0)
                    if global_step % (config.eval_every * 5) == 0 and onto_curriculum.scale > 0:
                        print(f"  🌉 [Onto] Phase: {onto_curriculum.phase} | Scale: {onto_curriculum.scale:.3f}")

                # V9.8.6: CSR Three-Phase Curriculum Update
                if csr_curriculum is not None:
                    old_phase = csr_curriculum.phase
                    csr_curriculum.update(val_ppl, global_step)
                    # Log graduation event
                    if csr_curriculum.graduated and old_phase != csr_curriculum.phase:
                        print(f"  🎓 [CSR] Graduated from POLISHING phase - CSR loss weight = 0.0")
                    # Periodic logging - only when engaged (scale > 0)
                    if global_step % (config.eval_every * 5) == 0 and csr_curriculum.scale > 0:
                        print(f"  🔤 [CSR] Phase: {csr_curriculum.phase} | Scale: {csr_curriculum.scale:.3f}")

                # V9.8.6: Kosha Three-Phase Curriculum Update
                if kosha_curriculum is not None:
                    old_phase = kosha_curriculum.phase
                    kosha_curriculum.update(val_ppl, global_step)
                    # Log graduation event
                    if kosha_curriculum.graduated and old_phase != kosha_curriculum.phase:
                        print(f"  🎓 [Kosha] Graduated from POLISHING phase - Kosha loss weight = 0.0")
                    # Periodic logging - only when engaged (scale > 0)
                    if global_step % (config.eval_every * 5) == 0 and kosha_curriculum.scale > 0:
                        print(f"  🧘 [Kosha] Phase: {kosha_curriculum.phase} | Scale: {kosha_curriculum.scale:.3f}")

                # V2.3.4: Sequence Length Curriculum Update
                # V9.9.3: Now with Sovereign Reset Protocol
                # Skip if inverted_layer_curriculum is handling seq_len via delegation
                _ilc_handles_seq = (inverted_layer_curriculum is not None and
                                   inverted_layer_curriculum.seq_len_curriculum is not None)
                if seq_len_curriculum is not None and not _ilc_handles_seq:
                    old_seq_len = current_seq_len
                    current_seq_len = seq_len_curriculum.get_seq_len(global_step, val_ppl)

                    # Check if we need to reload dataloader
                    if seq_len_curriculum.should_reload_data():
                        print(seq_len_curriculum.get_transition_message(global_step, old_seq_len, current_seq_len))

                        # V9.9.3: Sovereign Reset Protocol - clear buffers before reload
                        reset_result = on_seq_len_transition(
                            optimizer=optimizer,
                            device=device,
                            old_seq_len=old_seq_len,
                            new_seq_len=current_seq_len,
                            grad_accum_counter=accumulation_step,
                            verbose=True,
                        )

                        # V2.3.4: Recalculate batch size for new sequence length
                        # Memory scales ~linearly with seq_len, so batch scales inversely
                        old_batch = config.batch_size
                        new_batch = int(seq_curriculum_ref_batch * (seq_curriculum_ref_seq_len / current_seq_len))
                        new_batch = max(1, min(new_batch, config.batch_size_max))  # Clamp to configurable max
                        config.batch_size = new_batch

                        print(f"  📏 [SEQ CURRICULUM] Reloading dataloader:")
                        print(f"     seq_len: {old_seq_len} → {current_seq_len}")
                        print(f"     batch:   {old_batch} → {new_batch} (max: {config.batch_size_max})")

                        # Reload data with new sequence length and batch size
                        train_loader, val_loader = load_data(config, tokenizer, seq_len_override=current_seq_len)
                        train_iter = iter(train_loader)
                        seq_len_curriculum.mark_data_reloaded()

                        # V9.9.3: Set skip flag for VRAM stabilization
                        _skip_next_step = reset_result['skip_step']
                        print(f"  ✅ Dataloader reloaded. Progress: {seq_len_curriculum.get_progress():.1%} | All buffers synchronized.")

                    # Log sequence curriculum status periodically
                    elif global_step % (config.eval_every * 5) == 0:
                        status = seq_len_curriculum.get_status()
                        print(f"  📏 [SEQ CURRICULUM] Length: {status['current_seq_len']}/{status['target_seq_len']} | "
                              f"Progress: {status['progress']:.1%}")

                # V9.8.7: Three-phase PID engagement logic (INVERTED CURRICULUM)
                # Lower PPL → PID engages (model is competent, apply control)
                if config.pidv2_engagement_enabled and authority_controller is not None:
                    old_pid_phase = pid_phase
                    old_pid_engaged = pid_engaged

                    if val_ppl > config.pidv2_engage_ppl:
                        # Phase 1: FOUNDATION - High PPL, PID OFF (learning basics)
                        pid_phase = "FOUNDATION"
                        pid_engaged = False
                    elif val_ppl <= config.pidv2_disengage_ppl:
                        # Phase 3: CONSTRUCTION - Low PPL, PID ON (apply control)
                        pid_phase = "CONSTRUCTION"
                        pid_engaged = True
                    else:
                        # Phase 2: TRANSITION - Keep current engagement state
                        pid_phase = "TRANSITION"
                        # pid_engaged stays as-is (hysteresis)

                    # Log phase transitions
                    if pid_phase != old_pid_phase or pid_engaged != old_pid_engaged:
                        status_emoji = "🟢" if pid_engaged else "🔴"
                        print(f"\n  {'='*60}")
                        print(f"  📊 PID ENGAGEMENT PHASE CHANGE at step {global_step}")
                        print(f"     {old_pid_phase} → {pid_phase}")
                        print(f"     Val PPL: {val_ppl:.2f} | Engage>{config.pidv2_engage_ppl:.1f} | Disengage<{config.pidv2_disengage_ppl:.1f}")
                        print(f"     PID Controller: {status_emoji} {'ENGAGED' if pid_engaged else 'DISENGAGED'}")
                        print(f"  {'='*60}\n")

                        if tb_writer is not None:
                            tb_writer.add_scalar("ctrl/pid_engaged", 1.0 if pid_engaged else 0.0, global_step)
                            phase_num = {"CONSTRUCTION": 1, "TRANSITION": 2, "POLISHING": 3}.get(pid_phase, 0)
                            tb_writer.add_scalar("ctrl/pid_phase", phase_num, global_step)

                # PIDv2 Controller Update (V9.4.4)
                # Skip if PID is disengaged (POLISHING phase)
                if authority_controller is not None and (not config.pidv2_engagement_enabled or pid_engaged):
                    old_A = authority_controller.A
                    new_A = authority_controller.update(
                        val_ppl, current_coh,
                        step=global_step,
                        phase_ramp_steps=config.phase_ramp_steps,
                    )

                    # V9.4.6: PIDv2 Relaxation Sensitivity
                    # Dampen Kp during post-relaxation recovery to let sensory layers stabilize
                    relaxation_dampening_active = False
                    if relaxation_controller is not None and relaxation_controller.relaxation_step is not None:
                        steps_since_relaxation = global_step - relaxation_controller.relaxation_step
                        ppl_derivative = getattr(authority_controller, 'last_v', 0.0)
                        # If within 100 steps of swap AND PPL is rising, dampen authority
                        if 0 < steps_since_relaxation <= 100 and ppl_derivative > 0:
                            # Force minimum authority to let sensory layers re-anchor
                            new_A = config.pidv2_a_min
                            relaxation_dampening_active = True

                    print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f} | {authority_controller.get_status_string()}", end="", flush=True)
                    if relaxation_dampening_active:
                        print(f" [RELAX_DAMP]", flush=True)
                    else:
                        print(flush=True)

                    # V9.4.5: Log Friction Controller status (with corrective actions)
                    if friction_controller is not None:
                        print(f"  --> {friction_controller.get_status_string()}")
                        if friction_controller.correction_active:
                            print(f"  ⚠️ FRICTION CORRECTION: LR reduced by {(1-friction_controller.friction_penalty)*100:.0f}%")

                    # V9.7.0: PIDv2 Dynamic Batch Sizing Check
                    if hasattr(authority_controller, 'check_batch_action') and config.pidv2_batch_resize:
                        # Get current VRAM usage for headroom check
                        # Use memory_allocated() for actual tensor memory, not memory_reserved()
                        vram_usage = 0.0
                        if torch.cuda.is_available():
                            vram_allocated = torch.cuda.memory_allocated()
                            vram_reserved = torch.cuda.memory_reserved()
                            vram_total = torch.cuda.get_device_properties(0).total_memory
                            # Use actual allocated, but consider reserved if much higher (fragmentation)
                            vram_used = max(vram_allocated, vram_reserved * 0.7)
                            vram_usage = vram_used / vram_total

                        batch_action, new_batch, batch_reason = authority_controller.check_batch_action(
                            vram_usage=vram_usage,
                            vram_threshold=config.vram_threshold - 0.10  # Leave 10% headroom
                        )

                        if batch_action != "HOLD":
                            old_batch = config.batch_size
                            config.batch_size = new_batch
                            print(f"  🔄 [BATCH RESIZE] {batch_action}: {old_batch} → {new_batch}")
                            print(f"     Reason: {batch_reason}", flush=True)

                            # Reinitialize dataloader with new batch size
                            # Note: This is a simplified approach - full implementation would
                            # need to properly reinit the dataloader
                            if tb_writer is not None:
                                tb_writer.add_scalar("ctrl/batch_size", new_batch, global_step)

                    # Apply authority factor AND friction penalty to learning rate
                    effective_factor = new_A * friction_penalty
                    for pg in optimizer.param_groups:
                        pg['lr'] *= effective_factor

                    # TensorBoard logging
                    if tb_writer is not None:
                        tb_writer.add_scalar("ctrl/authority_A", new_A, global_step)
                        tb_writer.add_scalar("ctrl/ppl_velocity", authority_controller.last_v, global_step)
                        if hasattr(authority_controller, 'last_Kp'):
                            tb_writer.add_scalar("ctrl/dynamic_Kp", authority_controller.last_Kp, global_step)
                        # V9.4.5: Friction Controller metrics (with corrective actions)
                        if friction_controller is not None:
                            tb_writer.add_scalar("fric/alignment", friction_controller.align_ema, global_step)
                            tb_writer.add_scalar("fric/dominance", friction_controller.dom_ema, global_step)
                            tb_writer.add_scalar("fric/penalty", friction_controller.friction_penalty, global_step)
                            tb_writer.add_scalar("fric/correction_active", 1.0 if friction_controller.correction_active else 0.0, global_step)
                        elif friction_alignment != 0.0:
                            # Legacy: raw metrics without controller
                            tb_writer.add_scalar("ctrl/friction_alignment", friction_alignment, global_step)
                            tb_writer.add_scalar("ctrl/friction_dominance", friction_dominance, global_step)
                        # Gradient Throttle metrics
                        if gradient_throttle is not None:
                            throttle_stats = gradient_throttle.get_stats()
                            tb_writer.add_scalar("throttle/factor", throttle_stats['last_factor'], global_step)
                            tb_writer.add_scalar("throttle/grad_norm", throttle_stats['last_grad_norm'], global_step)
                            tb_writer.add_scalar("throttle/ema_norm", throttle_stats['ema_grad_norm'], global_step)
                            tb_writer.add_scalar("throttle/events_total", throttle_stats['throttle_events'], global_step)
                        # Toroidal Bridge metrics
                        if evolutionary_bridge is not None:
                            tb_writer.add_scalar("toroid/coherence", toroidal_coherence, global_step)
                            tb_writer.add_scalar("toroid/loss", toroidal_loss_value, global_step)
                            # V9.4.6: Shadow Mirror Alignment loss
                            if 'sma_loss' in metrics:
                                tb_writer.add_scalar("toroid/sma_loss", metrics['sma_loss'], global_step)
                            # V9.4.7: Stochastic Gradient Persistence tracking
                            if 'sgp_heavy_step' in metrics:
                                tb_writer.add_scalar("toroid/sgp_active", 1.0 if metrics['sgp_heavy_step'] else 0.0, global_step)
                            if metacognitive_tracker is not None:
                                tb_writer.add_scalar("toroid/velocity", metacognitive_tracker.coherence_history[-1] - metacognitive_tracker.coherence_history[-2] if len(metacognitive_tracker.coherence_history) >= 2 else 0.0, global_step)

                        # Full Evolutionary Flow metrics
                        if evolutionary_engine is not None and evo_result is not None:
                            # Multi-scale coherence
                            tb_writer.add_scalar("evo/coherence_micro", metrics.get('evo_micro', 0.0), global_step)
                            tb_writer.add_scalar("evo/coherence_authority", metrics.get('evo_auth', 0.0), global_step)
                            tb_writer.add_scalar("evo/coherence_sensory", metrics.get('evo_sens', 0.0), global_step)
                            tb_writer.add_scalar("evo/coherence_toroidal", metrics.get('evo_toroid', 0.0), global_step)

                            # Meso-scale delta (Authority - Sensory)
                            meso_delta = metrics.get('evo_auth', 0.0) - metrics.get('evo_sens', 0.0)
                            tb_writer.add_scalar("evo/meso_delta", meso_delta, global_step)

                            # Metacognitive recommendation as numeric
                            rec_map = {"BRAKE": 0, "SLOW_DOWN": 1, "RECOVER": 2, "STABILIZE": 3, "CONTINUE": 4, "ACCELERATE": 5}
                            rec_num = rec_map.get(metrics.get('evo_rec', 'CONTINUE'), 4)
                            tb_writer.add_scalar("evo/metacog_state", rec_num, global_step)

                            # LR multiplier from evolutionary engine
                            tb_writer.add_scalar("evo/lr_multiplier", evo_lr_multiplier, global_step)

                            # Loss components
                            if 'loss_metrics' in evo_result:
                                loss_m = evo_result['loss_metrics']
                                tb_writer.add_scalar("evo/loss_total", loss_m.get('evo_loss_total', 0.0), global_step)
                                tb_writer.add_scalar("evo/loss_micro", loss_m.get('evo_loss_micro', 0.0), global_step)
                                tb_writer.add_scalar("evo/loss_meso", loss_m.get('evo_loss_meso', 0.0), global_step)
                                tb_writer.add_scalar("evo/loss_macro", loss_m.get('evo_loss_macro', 0.0), global_step)

                            # Coherence heatmap (for TensorBoard visualization)
                            # Log gate-level coherence as histogram every 100 evals
                            if global_step % (config.eval_every * 10) == 0:
                                coherence_summary = evo_result.get('coherence_summary', {})
                                if 'gate_coherences' in coherence_summary:
                                    gate_coh = coherence_summary['gate_coherences']
                                    if len(gate_coh) > 0:
                                        tb_writer.add_histogram("evo/gate_coherence_dist", torch.tensor(gate_coh), global_step)

                        # CSR Phoneme-Ontological Metrics
                        if csr_metrics:
                            tb_writer.add_scalar("csr/loss", csr_metrics.get('csr_loss', 0.0), global_step)
                            tb_writer.add_scalar("csr/confidence", csr_metrics.get('csr_confidence', 0.0), global_step)
                            tb_writer.add_scalar("csr/similarity", csr_metrics.get('csr_similarity', 0.0), global_step)

                        # Appendix G: Bliss Coherence + Phase 3/4 Gating
                        if 'bliss_B' in metrics:
                            tb_writer.add_scalar("bliss/B", metrics['bliss_B'], global_step)
                            tb_writer.add_scalar("bliss/B_A", metrics['bliss_B_A'], global_step)
                            tb_writer.add_scalar("bliss/B_B", metrics['bliss_B_B'], global_step)
                            if 'bliss_lambda_eff_csr' in metrics:
                                tb_writer.add_scalar("bliss/lambda_eff_csr", metrics['bliss_lambda_eff_csr'], global_step)
                            if 'bliss_lambda_eff_jepa' in metrics:
                                tb_writer.add_scalar("bliss/lambda_eff_jepa", metrics['bliss_lambda_eff_jepa'], global_step)

                        # Phase 4: JEPA Injection metrics
                        if 'jepa_inj_loss' in metrics:
                            tb_writer.add_scalar("jepa_injection/loss", metrics['jepa_inj_loss'], global_step)
                            tb_writer.add_scalar("jepa_injection/similarity", metrics['jepa_inj_similarity'], global_step)
                            tb_writer.add_scalar("jepa_injection/lambda", metrics['jepa_inj_lambda'], global_step)
                            tb_writer.add_scalar("jepa_injection/prior_rms", metrics['jepa_inj_prior_rms'], global_step)
                            if 'jepa_inj_cap_violated' in metrics:
                                tb_writer.add_scalar("jepa_injection/cap_violated", 1.0, global_step)
                else:
                    _aux_str = f" | aux_scale={_aux_loss_scale:.2f}" if _aux_loss_scale < 1.0 else ""
                    print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f}{_aux_str}", flush=True)

                # Sovereign Alert Monitor - Auto-Pivot Logic
                if alert_monitor is not None:
                    # Build metrics dict for alert check
                    alert_metrics = {
                        'sa_ratio': current_sa_ratio,
                        'guna_coherence': val_metrics.get('coherence', val_metrics.get('gc', 0.5)),
                        'gc': val_metrics.get('gc', val_metrics.get('coherence', 0.5)),
                        'l_consistency': val_metrics.get('l_consistency', 0.0),
                        'entropy': val_metrics.get('entropy', 0.0),
                    }

                    # Check for alerts and apply corrections
                    alert_state, actions = alert_monitor.check(
                        metrics=alert_metrics,
                        step=global_step,
                        controller=authority_controller,
                        gradient_scaler=gradient_scaler_hgs,
                    )

                    # Log any actions taken
                    for action_msg in actions:
                        print(f"  {action_msg}")

                    # TensorBoard logging for alerts
                    if tb_writer is not None:
                        state_map = {"STABLE": 0, "ALERT": 1, "LOCKDOWN_ACTIVE": 2, "RECOVERING": 3}
                        tb_writer.add_scalar("alert/state", state_map.get(alert_state, 0), global_step)
                        tb_writer.add_scalar("alert/lockdown_count", alert_monitor.lockdown_count, global_step)

                # S8 Stability Hook - Entropy Guard
                if s8_hook is not None:
                    # Compute semantic entropy from validation outputs
                    semantic_ent = val_metrics.get('entropy', val_metrics.get('onto_entropy', 0.5))
                    brake_intensity = s8_hook.update(semantic_ent)

                    # [S5/S8] Apply alpha_sens adjustment based on entropy state
                    alpha_sens_factor = s8_hook.get_alpha_sens_adjustment(semantic_ent)
                    if alpha_sens_factor < 1.0 and gradient_scaler_hgs is not None:
                        # Temporarily reduce alpha_sens_max to dampen sensory learning
                        old_alpha = gradient_scaler_hgs.alpha_sens_max
                        gradient_scaler_hgs.alpha_sens_max = old_alpha * alpha_sens_factor
                        print(f"  --> [S5] Entropy rising - α_sens reduced: {old_alpha:.2f} → {gradient_scaler_hgs.alpha_sens_max:.2f}")

                    # Log S8 status (always log when brake active or entropy high)
                    if brake_intensity < 0.99 or semantic_ent > 0.60:
                        from agentic.sovereign.metrics import get_entropy_status
                        ent_icon, ent_status = get_entropy_status(semantic_ent)
                        print(f"  --> [S8] Ent:{semantic_ent:.2f}{ent_icon} | {s8_hook.format_log()}")

                    # TensorBoard logging for S8
                    if tb_writer is not None:
                        tb_writer.add_scalar("s8/entropy", semantic_ent, global_step)
                        tb_writer.add_scalar("s8/brake_intensity", brake_intensity, global_step)
                        tb_writer.add_scalar("s8/delta_h", s8_hook.state.last_delta_h, global_step)
                        tb_writer.add_scalar("s8/alpha_sens_factor", alpha_sens_factor, global_step)

                # Dynamic Relaxation Controller Update
                if relaxation_controller is not None:
                    # Get Guna Coherence from metrics (or default)
                    guna_coherence = val_metrics.get('coherence', 0.75)

                    # Get S-Drift EMA from metrics (or estimate from PPL stability)
                    # If not available, estimate from recent PPL variance
                    s_drift_ema = val_metrics.get('s_drift_ema', 0.3)
                    if 's_drift_ema' not in val_metrics:
                        # Fallback: estimate drift from PPL stability
                        # Lower PPL variance = lower drift
                        recent_losses = train_losses[-50:] if len(train_losses) >= 50 else train_losses
                        if len(recent_losses) > 1:
                            loss_std = torch.tensor(recent_losses).std().item()
                            s_drift_ema = min(1.0, loss_std * 2.0)  # Scale to [0, 1]
                        else:
                            s_drift_ema = 0.5

                    # Get entropy for gating (from S8 hook or val_metrics)
                    current_entropy = val_metrics.get('entropy', val_metrics.get('onto_entropy', 0.5))

                    # Update relaxation controller with entropy gate and saturation gate
                    state_changed, action = relaxation_controller.update(
                        guna_coherence=guna_coherence,
                        s_drift_ema=s_drift_ema,
                        val_ppl=val_ppl,
                        global_step=global_step,
                        sa_ratio=current_sa_ratio,
                        entropy=current_entropy,
                        sensory_flow=last_sensory_flow,  # For Saturation Gate
                    )

                    # Execute actions
                    if action == "RELAX":
                        relaxation_controller.execute_relaxation(current_step=global_step)
                        print(f"  🎯 StabilityIndex achieved! Transitioning to balanced mode.")
                    elif action == "RECOVER":
                        relaxation_controller.execute_recovery()

                    # Log status
                    print(f"  --> [Relaxation] {relaxation_controller.get_status_string()}")

                    # TensorBoard logging for relaxation
                    if tb_writer is not None:
                        stability = relaxation_controller.compute_stability_index(guna_coherence, s_drift_ema)
                        tb_writer.add_scalar("relax/stability_index", stability, global_step)
                        tb_writer.add_scalar("relax/stability_streak", relaxation_controller.stability_streak, global_step)
                        tb_writer.add_scalar("relax/is_balanced", 1.0 if relaxation_controller.state == "BALANCED" else 0.0, global_step)
                        tb_writer.add_scalar("relax/guna_coherence", guna_coherence, global_step)
                        tb_writer.add_scalar("relax/s_drift_ema", s_drift_ema, global_step)
                        # Saturation Gate metrics
                        tb_writer.add_scalar("relax/sensory_flow", last_sensory_flow, global_step)
                        tb_writer.add_scalar("relax/saturation_flat_count", relaxation_controller.saturation_flat_count, global_step)
                        tb_writer.add_scalar("relax/saturation_triggered", 1.0 if relaxation_controller.saturation_triggered else 0.0, global_step)

                # Adaptive Training Controller (dynamic LR/Kp adjustment)
                # Only active AFTER warmup completes (warmup uses scheduler's LR ramp)
                if adaptive_controller is not None:
                    # Check if warmup is complete
                    warmup_done = (
                        (use_adaptive_warmup and scheduler.warmup_ended) or
                        (not use_adaptive_warmup and global_step >= config.warmup_steps)
                    )

                    if not warmup_done:
                        # During warmup, skip LR adjustments (let scheduler handle it)
                        if global_step == config.eval_every:  # Log once at first eval
                            print(f"  [AdaptiveTraining] Waiting for warmup (PPL: {val_ppl:.1f}, target: <{config.warmup_until_ppl:.0f})")
                        adaptive_adjustments = {"actions": []}
                    else:
                        # Get recent train loss (average of last 10 steps)
                        recent_train_loss = sum(train_losses[-10:]) / len(train_losses[-10:]) if train_losses else 0.0

                        adaptive_adjustments = adaptive_controller.update(
                            train_loss=recent_train_loss,
                            val_loss=val_loss,
                            val_ppl=val_ppl,
                            coherence=val_metrics.get('coherence', 0.75),
                            global_step=global_step,
                            authority_controller=authority_controller,  # Pass PIDv2 for Kp adjustment
                        )

                    # Log adaptive controller status
                    if adaptive_adjustments.get("actions"):
                        # Already logged by the controller
                        pass

                    # Notify gradient variance tracker of LR changes to prevent
                    # false-positive spike alerts (variance scales ~factor²)
                    if gradient_variance_tracker is not None and adaptive_adjustments.get("actions"):
                        for action in adaptive_adjustments["actions"]:
                            if action.startswith("LR_BOOST"):
                                gradient_variance_tracker.notify_lr_change(config.adaptive_lr_boost)
                            elif action.startswith("LR_DECAY"):
                                gradient_variance_tracker.notify_lr_change(config.adaptive_lr_decay)
                    # V10.22: Sync slot LR after adaptive controller may have changed main LR
                    if adaptive_slot_lr is not None:
                        adaptive_slot_lr.sync_slot_lr()

                    # TensorBoard logging for adaptive controller
                    if tb_writer is not None:
                        telemetry = adaptive_controller.get_telemetry()
                        tb_writer.add_scalar("adaptive/lr", telemetry["current_lr"], global_step)
                        tb_writer.add_scalar("adaptive/velocity", telemetry["velocity"], global_step)
                        tb_writer.add_scalar("adaptive/boost_count", telemetry["boost_count"], global_step)
                        tb_writer.add_scalar("adaptive/decay_count", telemetry["decay_count"], global_step)
                        tb_writer.add_scalar("adaptive/plateau_count", telemetry["plateau_count"], global_step)
                else:
                    # Legacy: Adaptive LR on PPL spike (only if no adaptive controller)
                    if val_ppl < best_ppl:
                        best_ppl = val_ppl
                    elif global_step > config.warmup_steps:
                        if val_ppl > best_ppl * 1.5:
                            spike_count += 1
                            old_lr = optimizer.param_groups[0]['lr']
                            new_lr = old_lr * 0.7
                            for pg in optimizer.param_groups:
                                pg['lr'] = new_lr
                            print(f"  ⚠️ PPL spike! LR: {old_lr:.2e} → {new_lr:.2e}")

                # TensorBoard val metrics
                if tb_writer is not None:
                    tb_writer.add_scalar("val/loss", val_loss, global_step)
                    tb_writer.add_scalar("val/ppl", val_ppl, global_step)

                    # Sattvic Brake metrics
                    if sattvic_brake is not None:
                        tb_writer.add_scalar("sattvic/confidence", sattvic_confidence, global_step)
                        tb_writer.add_scalar("sattvic/lr_mult", sattvic_lr_mult, global_step)
                        tb_writer.add_scalar("sattvic/brake_count", sattvic_brake.brake_applied_count, global_step)

                    # v2.7 Training State Tracker metrics
                    if training_state_tracker is not None and training_state_tracker.enabled:
                        tb_writer.add_scalar("v27/cognitive_state", training_state_tracker.state['cognitive_state'], global_step)
                        tb_writer.add_scalar("v27/confidence", training_state_tracker.state['confidence'], global_step)
                        tb_writer.add_scalar("v27/stability", training_state_tracker.state['stability'], global_step)
                        tb_writer.add_scalar("v27/tone_ema", training_state_tracker.state['tone_ema'], global_step)

                # Log HGS status (only if relaxation controller not active, to avoid duplicate logging)
                if gradient_scaler_hgs is not None and relaxation_controller is None:
                    print(f"  --> {gradient_scaler_hgs.get_status_string()}")

                # Log Adaptive Training Controller status
                if adaptive_controller is not None and len(adaptive_controller.val_ppl_history) >= 2:
                    print(f"  --> {adaptive_controller.get_status_string()}")
                if adaptive_slot_lr is not None:
                    adaptive_slot_lr.update(global_step, warmup_complete=warmup_complete)
                    # V16.1: Propagate tied coherence floor to slot memory
                    if config.slot_coherence_floor_tied and adaptive_slot_lr.coherence_floor_initial > 0:
                        _sm_eval = getattr(model, 'slot_memory', None)
                        if _sm_eval is None:
                            _sm_eval = getattr(getattr(model, 'hybrid', model), 'slot_memory', None)
                        if _sm_eval is not None:
                            _sm_eval._coherence_floor = adaptive_slot_lr.get_coherence_floor()
                    print(f"  --> {adaptive_slot_lr.get_status_string()}")

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    if not config.no_save:
                        # V9.8.10: Restore scheduled alpha before saving checkpoint
                        # (InvertedLayerCurriculum may have modified it during validation)
                        update_alpha_schedule(model, global_step, config)
                        save_checkpoint(
                            model, optimizer, scheduler, global_step, best_val_loss,
                            ckpt_dir / "best.pt",
                            hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
                            drc_state=relaxation_controller.get_state() if relaxation_controller else None,
                            sgp_state=sgp_controller.get_state() if sgp_controller else None,
                            sattvic_state=sattvic_controller.get_state() if sattvic_controller else None,
                            srk_state=srk.get_checkpoint_state() if srk else None,
                            scaler_state=scaler.state_dict() if scaler else None,
                            # V9.8.6: Three-Phase Curriculum states
                            csr_curriculum_state=csr_curriculum.get_state() if csr_curriculum else None,
                            kosha_curriculum_state=kosha_curriculum.get_state() if kosha_curriculum else None,
                            onto_curriculum_state=onto_curriculum.get_state() if onto_curriculum else None,
                            pidv2_curriculum_state=authority_controller.get_curriculum_state() if authority_controller and hasattr(authority_controller, 'get_curriculum_state') else None,
                            kosha_gyroscope_state=kosha_curriculum_controller.get_state() if kosha_curriculum_controller else None,
                            evoflow_state=evolutionary_engine.get_state() if evolutionary_engine else None,
                            kv_supervisor_state=kv_supervisor.state_dict() if kv_supervisor else None,
                            jepa_injection_projector_state=jepa_injection_projector.state_dict() if jepa_injection_projector else None,
                            cg_stage_manager_state=cg_stage_manager.get_state() if cg_stage_manager else None,
                            experiential_controller_state=experiential_controller.get_full_state() if experiential_controller is not None else None,
                            training_config=_build_training_config_snapshot(config),
                        )
                        print(f"  --> New best! Saved to {ckpt_dir / 'best_*.pt'}", flush=True)

                # LRA Validation (Long-Range Retrieval)
                if lra_validator is not None and global_step % config.lra_validate_every == 0:
                    lra_results = lra_validator.run_validation(step=global_step)
                    lra_score = lra_validator.get_retrieval_score()

                    # TensorBoard logging for LRA
                    if tb_writer is not None:
                        tb_writer.add_scalar("lra/retrieval_score", lra_score, global_step)
                        tb_writer.add_scalar("lra/mean_accuracy", lra_results["summary"]["mean_accuracy"], global_step)
                        tb_writer.add_scalar("lra/decay_rate", lra_results["summary"]["decay_rate"], global_step)
                        tb_writer.add_scalar("lra/mean_entropy", lra_results["summary"]["mean_entropy"], global_step)

                model.train()


            # V10.21/V11.2b: Slot ablation eval — independent clock from eval.
            # Runs every 200 steps: temporarily disables slot read output,
            # runs its own mini-eval, and prints the PPL delta.
            # Uses last_val_ppl (cached from most recent eval) as the with-slots baseline.
            if (
                global_step % 200 == 0
                and hasattr(model, 'slot_memory')
                and model.slot_memory is not None
                and last_val_ppl < float('inf')  # Need at least one eval first
            ):
                _sm = model.slot_memory
                # Save original warmstart state and force alpha=0
                _orig_step = _sm._router_step
                _orig_center = _sm._read_warmstart_center
                _sm._read_warmstart_center = float('inf')  # Forces alpha → 0
                model.eval()
                with torch.no_grad():
                    _no_slot_loss, _no_slot_metrics = evaluate(
                        model, val_loader, device, config, autocast_dtype,
                        sovereign_loss=sovereign_loss,
                        sovereign_engine=sovereign_engine,
                        cached_val_batches=cached_val_batches,
                    )
                _no_slot_ppl = _no_slot_metrics['ppl']
                _slot_delta = _no_slot_ppl - last_val_ppl
                _slot_pct = (_slot_delta / max(last_val_ppl, 1.0)) * 100
                _sign = "+" if _slot_delta > 0 else ""
                print(f"  🧩 [SLOT ABLATION] With slots: {last_val_ppl:.2f} | "
                      f"Without: {_no_slot_ppl:.2f} | "
                      f"Delta: {_sign}{_slot_delta:.2f} ({_sign}{_slot_pct:.1f}%)"
                      f"{' ✓ slots helping' if _slot_delta > 1.0 else ' ○ slots neutral' if _slot_delta > -1.0 else ' ✗ slots hurting'}")
                # V11.2: Feed ablation delta to SlotMemory for retr_weight guard
                _sm._last_ablation_delta = _slot_delta
                # V10.22: Feed ablation delta and trigger adaptive slot LR update
                if adaptive_slot_lr is not None:
                    adaptive_slot_lr.record_ablation_delta(_slot_delta)
                    _slot_lr_actions = adaptive_slot_lr.update(global_step, warmup_complete=warmup_complete)
                    # V16.1: Propagate tied coherence floor after ablation-triggered update
                    if config.slot_coherence_floor_tied and adaptive_slot_lr.coherence_floor_initial > 0:
                        _sm._coherence_floor = adaptive_slot_lr.get_coherence_floor()
                # Post-curriculum adaptive alpha: feed ablation % to curriculum
                if ppl_alpha_curriculum is not None:
                    ppl_alpha_curriculum.update_from_ablation(_slot_pct)
                # Restore
                _sm._read_warmstart_center = _orig_center
                _sm._router_step = _orig_step
                model.train()

            # Quality Sampling (OUTSIDE eval block - runs independently of eval_every)
            if config.sample_every > 0 and global_step % config.sample_every == 0:
                if tokenizer is not None:
                    model.eval()
                    run_quality_samples(model, tokenizer, config, device, global_step)
                    # V11.x: Factual eval with ground-truth scoring
                    _amp_dt = autocast_dtype if config.mixed_precision != "none" else None
                    factual_metrics = run_factual_eval(
                        model, tokenizer, device, global_step, amp_dtype=_amp_dt
                    )
                    for k, v in factual_metrics.items():
                        metrics[k] = v
                    # TensorBoard: factual accuracy CG ON vs CG OFF
                    if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                        writer.add_scalar('factual/accuracy_cg_on',
                                          factual_metrics.get('factual_accuracy', 0), global_step)
                        if 'factual_accuracy_cg_off' in factual_metrics:
                            writer.add_scalar('factual/accuracy_cg_off',
                                              factual_metrics['factual_accuracy_cg_off'], global_step)
                            _delta = factual_metrics['factual_accuracy'] - factual_metrics['factual_accuracy_cg_off']
                            writer.add_scalar('factual/cg_delta', _delta, global_step)
                    model.train()
                else:
                    print(f"  [Sampling] Skipped - tokenizer not available")

            # Knowledge Probes (factual accuracy, slot retrieval, phase coherence)
            if config.knowledge_probe_every > 0 and global_step % config.knowledge_probe_every == 0:
                if tokenizer is not None:
                    model.eval()
                    run_knowledge_probes(model, tokenizer, config, device, global_step)
                    model.train()

            # =============================================================
            # Conscious Generation Progress Snapshot
            # Independent of text quality samples. Controlled by --cg_sample_every.
            # Shows all active CG phases, governance, and experiential state.
            # =============================================================
            if config.cg_sample_every > 0 and global_step % config.cg_sample_every == 0 and global_step > 0:
                _cg_snapshot_active = (
                    config.enable_conscious_generation
                    or experiential_controller is not None
                )
                if _cg_snapshot_active:
                    try:
                        print("")
                        print("=" * 70)
                        print(f"  CONSCIOUS GENERATION PROGRESS (Step {global_step})")
                        print("=" * 70)
                        _cg_sections = 0

                        # --- Phase 1: Ontological Foundation ---
                        if metrics.get('cg_ont_loss') is not None:
                            _cg_sections += 1
                            _ont_loss = metrics['cg_ont_loss']
                            _ont_pos = metrics.get('cg_ont_pos_sim', 0)
                            _ont_neg = metrics.get('cg_ont_neg_sim', 0)
                            _ont_margin = _ont_pos - _ont_neg
                            print(f"  Phase 1 - Ontology:")
                            print(f"    L_ont={_ont_loss:.4f}  "
                                  f"pos_sim={_ont_pos:.3f}  neg_sim={_ont_neg:.3f}  "
                                  f"margin={_ont_margin:.3f}")
                            if _ont_margin > 0.3:
                                print(f"    -> GOOD: clear separation between similar/dissimilar tokens")
                            elif _ont_margin > 0.1:
                                print(f"    -> DEVELOPING: ontological structure emerging")
                            else:
                                print(f"    -> EARLY: margin too small, structure not yet learned")

                        # --- Phase 2: Primitive Scoring Heads ---
                        _p2_norms = {}
                        if hasattr(model, 'conscious_gen') and 'token_cache' in getattr(model, 'conscious_gen', {}):
                            _p2_diag = model.conscious_gen['token_cache'].get_diagnostics()
                            for _buf in ('P_tok', 'R_tok', 'V_tok', 'G_tok'):
                                _nk = f"{_buf}_mean_norm"
                                if _nk in _p2_diag and _p2_diag[_nk] > 0:
                                    _p2_norms[_buf] = _p2_diag[_nk]
                        if _p2_norms:
                            _cg_sections += 1
                            _p2_str = "  ".join([f"{k}={v:.3f}" for k, v in _p2_norms.items()])
                            print(f"  Phase 2 - Primitive Buffers:")
                            print(f"    {_p2_str}")
                            _active_bufs = sum(1 for v in _p2_norms.values() if v > 0.01)
                            print(f"    -> {_active_bufs}/{len(_p2_norms)} buffers active")

                        # --- Phase 3: Governance Integration ---
                        _has_p3 = any(metrics.get(k) is not None for k in
                                      ['cg_alpha_entropy', 'cg_bliss_mean', 'cg_kosha_routing_loss'])
                        if _has_p3:
                            _cg_sections += 1
                            print(f"  Phase 3 - Governance:")
                            _p3_parts = []
                            if metrics.get('cg_alpha_entropy') is not None:
                                _p3_parts.append(f"alpha_H={metrics['cg_alpha_entropy']:.3f}")
                            if metrics.get('cg_bliss_mean') is not None:
                                _p3_parts.append(f"B={metrics['cg_bliss_mean']:.3f}")
                            if metrics.get('cg_disagree_mean') is not None:
                                _p3_parts.append(f"D={metrics['cg_disagree_mean']:.3f}")
                            if metrics.get('cg_kosha_routing_loss') is not None:
                                _p3_parts.append(f"L_kosha={metrics['cg_kosha_routing_loss']:.4f}")
                            if metrics.get('cg_bliss_loss') is not None:
                                _p3_parts.append(f"L_bliss={metrics['cg_bliss_loss']:.4f}")
                            print(f"    {' | '.join(_p3_parts)}")
                            # Primitive aux losses
                            _prim_parts = []
                            for _pn in ('jepa', 'csr', 'vritti', 'guna'):
                                _pk = f'cg_L_{_pn}'
                                if metrics.get(_pk) is not None:
                                    _prim_parts.append(f"L_{_pn}={metrics[_pk]:.4f}")
                            if _prim_parts:
                                print(f"    Primitives: {' | '.join(_prim_parts)}")
                            # Interpret governance health
                            _alpha_h = metrics.get('cg_alpha_entropy', 0)
                            if _alpha_h > 1.5:
                                print(f"    -> HEALTHY: high routing entropy (exploring all koshas)")
                            elif _alpha_h > 0.5:
                                print(f"    -> SPECIALIZING: koshas differentiating")
                            elif _alpha_h > 0:
                                print(f"    -> COLLAPSED: one kosha dominating, check routing")

                        # --- Sovereign State Projector Health ---
                        # Quick forward pass to show 32D slice distributions.
                        # Reveals whether Bhava/Vritti/Guna are structured
                        # (state projector learning) or near-init (still flat).
                        try:
                            _sp_model = getattr(model, 'module', model)
                            if hasattr(_sp_model, 'state_projector') and tokenizer is not None:
                                _sp_prompt = "The meaning of"
                                _sp_ids = tokenizer.encode(_sp_prompt, return_tensors="pt").to(device)
                                _sp_autocast = config.mixed_precision != "none"
                                with torch.no_grad(), torch.amp.autocast('cuda', dtype=autocast_dtype, enabled=_sp_autocast):
                                    _sp_out = model(_sp_ids)
                                if isinstance(_sp_out, dict) and 'state' in _sp_out:
                                    _cg_sections += 1
                                    _sp_s = _sp_out['state'][0]  # [32]
                                    _sp_bhava = _sp_s[0:12]
                                    _sp_vritti = _sp_s[17:22]
                                    _sp_guna = _sp_s[22:28]
                                    _sp_bh_ent = -((_sp_bhava + 1e-8).log() * _sp_bhava).sum().item()
                                    _sp_vr_ent = -((_sp_vritti + 1e-8).log() * _sp_vritti).sum().item()
                                    _sp_gu_mid = (_sp_guna - 0.5).abs().mean().item()
                                    _sp_bh_spread = (_sp_bhava.max() - _sp_bhava.min()).item()
                                    _sp_vr_spread = (_sp_vritti.max() - _sp_vritti.min()).item()
                                    print(f"  State Projector Health:")
                                    print(f"    Bhava:  entropy={_sp_bh_ent:.3f}/2.485"
                                          f"  spread={_sp_bh_spread:.3f}"
                                          f"  dominant=[{_sp_bhava.argmax().item()}]={_sp_bhava.max().item():.3f}"
                                          f"  {'(structured)' if _sp_bh_ent < 2.485 * 0.85 else '(near-uniform)'}")
                                    print(f"    Vritti: entropy={_sp_vr_ent:.3f}/1.609"
                                          f"  spread={_sp_vr_spread:.3f}"
                                          f"  dominant=[{_sp_vritti.argmax().item()}]={_sp_vritti.max().item():.3f}"
                                          f"  {'(peaked)' if _sp_vr_ent < 1.609 * 0.75 else '(near-uniform)'}")
                                    _sp_gu_vals = " ".join([f"[{i}]={_sp_guna[i].item():.3f}" for i in range(min(6, _sp_guna.shape[0]))])
                                    print(f"    Guna:   {_sp_gu_vals}"
                                          f"  dist_mid={_sp_gu_mid:.3f}"
                                          f"  {'(active)' if _sp_gu_mid > 0.1 else '(near-init)'}")
                                    if metrics.get('cg_state_proj_grad_norm') is not None:
                                        print(f"    sp_grad_norm={metrics['cg_state_proj_grad_norm']:.6f}")
                        except Exception as _sp_err:
                            print(f"  State Projector Health: skipped ({_sp_err})")

                        # --- Phase 4: Field-Integrated Generation ---
                        if metrics.get('cg_field_lm_loss') is not None:
                            _cg_sections += 1
                            print(f"  Phase 4 - Field Integration:")
                            _f_loss = metrics['cg_field_lm_loss']
                            _f_active = metrics.get('cg_phase4_active', 0)
                            _f_coverage = metrics.get('cg_shortlist_coverage', 0)
                            _f_fallback = metrics.get('cg_phase4_fallback', 0)
                            print(f"    L_field={_f_loss:.4f}  active={_f_active:.0f}  "
                                  f"coverage={_f_coverage:.3f}  fallback={_f_fallback:.0f}")
                            if _f_coverage > 0.8:
                                print(f"    -> GOOD: field covers target tokens well")
                            elif _f_coverage > 0.5:
                                print(f"    -> PARTIAL: field missing some targets")
                            else:
                                print(f"    -> WEAK: field not yet capturing target distribution")

                        # --- Phase 5: Curriculum Stage ---
                        if cg_stage_manager is not None:
                            _cg_sections += 1
                            _cs_diag = cg_stage_manager.get_diagnostics()
                            _cs_stage = _cs_diag.get('cg_curriculum_stage', '?')
                            _cs_idx = _cs_diag.get('cg_curriculum_stage_idx', 0)
                            _cs_entry = _cs_diag.get('cg_curriculum_stage_entry_step', 0)
                            _cs_steps_in = global_step - _cs_entry
                            print(f"  Phase 5 - Curriculum:")
                            print(f"    Stage={_cs_stage} ({_cs_idx+1}/4)  "
                                  f"steps_in_stage={_cs_steps_in}  "
                                  f"field_integrated={cg_stage_manager.use_field_integrated_softmax}")

                        # --- Governance Diagnostics Summary ---
                        if cg_governance_diag is not None:
                            _gov_sum = cg_governance_diag.get_summary()
                            if _gov_sum:
                                _cg_sections += 1
                                print(f"  Governance Diagnostics:")
                                _gov_parts = []
                                for _gk, _gv in _gov_sum.items():
                                    if isinstance(_gv, float):
                                        _gov_parts.append(f"{_gk}={_gv:.3f}")
                                    elif isinstance(_gv, int):
                                        _gov_parts.append(f"{_gk}={_gv}")
                                if _gov_parts:
                                    # Show in rows of 4
                                    for i in range(0, len(_gov_parts), 4):
                                        print(f"    {' | '.join(_gov_parts[i:i+4])}")

                        # --- Stage 0: Generation Tracer ---
                        if generation_tracer is not None:
                            _gt_sum = generation_tracer.summary()
                            if _gt_sum.get('num_tokens', 0) > 0:
                                _cg_sections += 1
                                print(f"  Stage 0 - Binding Cache Tracer:")
                                print(f"    tokens={_gt_sum.get('num_tokens', 0)}  "
                                      f"H={_gt_sum.get('mean_logit_entropy', 0):.3f}  "
                                      f"intent_drift={_gt_sum.get('mean_intent_drift', 0):.4f}  "
                                      f"cache_hit={_gt_sum.get('mean_cache_hit_rate', 0):.3f}")

                        # --- Stage 8: Perspective Synthesizer ---
                        if metrics.get('stage8_gate') is not None:
                            _cg_sections += 1
                            print(f"  Stage 8 - Perspective Synthesizer:")
                            print(f"    gate={metrics['stage8_gate']:.4f}  "
                                  f"cond_norm={metrics.get('stage8_cond_norm', 0):.4f}")
                            if metrics['stage8_gate'] < 0.01:
                                print(f"    -> COLD START: gate near zero (safe, no modification)")
                            elif metrics['stage8_gate'] > 0.5:
                                print(f"    -> ACTIVE: perspective conditioning influencing output")
                            else:
                                print(f"    -> WARMING: gate opening gradually")

                        # --- Experiential Controller ---
                        if experiential_controller is not None:
                            _cg_sections += 1
                            _ec = experiential_controller
                            _ec_ids = _ec.identity.get_state()
                            _ec_resist = _ec.plasticity_gate.persistent_resistance
                            _ec_replay_len = len(_ec.replay)

                            print(f"  Experiential Controller:")

                            # Resistance
                            _r_mean = _ec_resist.mean().item()
                            _r_std = _ec_resist.std().item() if _ec_resist.numel() > 1 else 0.0
                            print(f"    Resistance: mean={_r_mean:.4f}  std={_r_std:.4f}")

                            # g_eff breakdown
                            _exp_geff = metrics.get('exp_g_eff', None)
                            if _exp_geff is not None:
                                print(f"    g_eff={_exp_geff:.4f}  "
                                      f"(P={metrics.get('exp_plasticity', 0):.3f} x "
                                      f"G={metrics.get('exp_gain', 0):.3f} x "
                                      f"d={metrics.get('exp_damping', 0):.3f})")
                                if _exp_geff < 0.5:
                                    print(f"    -> CAUTIOUS: high resistance or instability")
                                elif _exp_geff > 2.0:
                                    print(f"    -> AGGRESSIVE: learning fast")
                                else:
                                    print(f"    -> BALANCED: moderate plasticity")

                            # Loss components
                            _lt = metrics.get('exp_L_token', None)
                            if _lt is not None:
                                print(f"    L_tok={_lt:.4f}  L_temp={metrics.get('exp_L_temporal', 0):.4f}  "
                                      f"L_coh={metrics.get('exp_L_coherence', 0):.4f}  "
                                      f"L_lat={metrics.get('exp_L_latent', 0):.4f}")

                            # Identity
                            _id_norm = _ec_ids['identity_norm']
                            _id_count = _ec_ids['accumulator_count']
                            _id_consol = _ec_ids.get('consolidation_count', 0)
                            print(f"    Identity: norm={_id_norm:.4f}  accum={_id_count}  "
                                  f"consol={_id_consol}", end="")
                            if _id_norm < 0.01:
                                print(f" (COLD)")
                            elif _id_norm > 0.5:
                                print(f" (STABLE)")
                            else:
                                print(f" (FORMING)")

                            # Replay + per-region
                            print(f"    Replay: {_ec_replay_len} items")
                            if _ec_resist.dim() >= 1 and _ec_resist.shape[0] > 1:
                                _r_vals = _ec_resist.detach().cpu().tolist()
                                _r_str = " ".join([f"{v:.2f}" for v in _r_vals[:12]])
                                print(f"    Regions: [{_r_str}]")

                            # TensorBoard
                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                writer.add_scalar('experiential/resistance_mean', _r_mean, global_step)
                                writer.add_scalar('experiential/resistance_std', _r_std, global_step)
                                writer.add_scalar('experiential/identity_norm', _id_norm, global_step)
                                writer.add_scalar('experiential/replay_buffer_size', _ec_replay_len, global_step)

                        # --- CG Primitive Loss Attribution ---
                        _cg_attr_keys = [k for k in metrics if k.startswith('cg_attr_')]
                        if _cg_attr_keys:
                            _cg_sections += 1
                            _cg_total_aux = metrics.get('cg_total_aux_loss', 0)
                            print(f"  CG Primitive Attribution (weighted loss %):")
                            _attr_parts = []
                            for _ak in sorted(_cg_attr_keys):
                                _name = _ak.replace('cg_attr_', '')
                                _pct = metrics[_ak] * 100
                                _attr_parts.append(f"{_name}={_pct:.1f}%")
                            print(f"    {' | '.join(_attr_parts)}")
                            print(f"    total_aux_loss={_cg_total_aux:.4f}")
                            # Identify dominant primitive
                            _dom = max(_cg_attr_keys, key=lambda k: metrics[k])
                            _dom_name = _dom.replace('cg_attr_', '')
                            _dom_pct = metrics[_dom] * 100
                            if _dom_pct > 60:
                                print(f"    -> DOMINATED by {_dom_name} ({_dom_pct:.0f}%) — "
                                      f"other primitives have weak influence")
                            elif _dom_pct > 40:
                                print(f"    -> LED by {_dom_name} ({_dom_pct:.0f}%)")
                            else:
                                print(f"    -> BALANCED: no single primitive dominates")
                            # TensorBoard
                            if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                                for _ak in _cg_attr_keys:
                                    _name = _ak.replace('cg_attr_', '')
                                    writer.add_scalar(f'cg_attribution/{_name}',
                                                      metrics[_ak], global_step)
                                writer.add_scalar('cg_attribution/total_aux_loss',
                                                  _cg_total_aux, global_step)

                        # --- CG Adapter Influence Diagnostics ---
                        _cg_model = getattr(model, 'module', model)
                        if hasattr(_cg_model, 'adapter_gate'):
                            _cg_sections += 1
                            _gate_val = torch.sigmoid(_cg_model.adapter_gate).item()
                            _gate_raw = _cg_model.adapter_gate.item()
                            _adp_norm = metrics.get('adapter_output_norm', 0)
                            _adp_wnorm = 0.0
                            if hasattr(_cg_model, 'phase_adapter'):
                                _adp_wnorm = sum(
                                    p.detach().norm().item()
                                    for p in _cg_model.phase_adapter.parameters()
                                )
                            print(f"  CG Adapter Diagnostics:")
                            print(f"    gate={_gate_val:.4f} (raw={_gate_raw:.3f})  "
                                  f"adapter_out_norm={_adp_norm:.3f}  "
                                  f"adapter_weight_norm={_adp_wnorm:.1f}")
                            # Effective influence: gate * adapter_output_norm
                            _eff_influence = _gate_val * _adp_norm if _adp_norm > 0 else 0.0
                            print(f"    effective_influence={_eff_influence:.4f} "
                                  f"(gate × adapter_norm)")
                            if _eff_influence < 5.0:
                                print(f"    -> SUBTLE: small CG perturbation")
                            elif _eff_influence < 20.0:
                                print(f"    -> MODERATE: CG actively shaping representations")
                            elif _eff_influence < 50.0:
                                print(f"    -> STRONG: CG significantly modifying hidden states")
                            else:
                                print(f"    -> DOMINANT: CG overwhelming residual stream — check gate")
                            # Damping health
                            _d_val = metrics.get('exp_damping', None)
                            if _d_val is not None:
                                if _d_val < 0.05:
                                    print(f"    ⚠ Damping collapsed (d={_d_val:.3f}) — "
                                          f"controller effectively OFF")
                                elif _d_val < 0.3:
                                    print(f"    ⚡ Damping suppressed (d={_d_val:.3f}) — "
                                          f"recovering from variance spike")

                        # --- Embedding Diagnostics Trend ---
                        if 'cg_embedding_diag' in dir() and cg_embedding_diag is not None:
                            if len(cg_embedding_diag.history) >= 2:
                                _cg_sections += 1
                                _ed_trend = cg_embedding_diag.get_trend_summary()
                                print(f"  Embedding Diagnostics:")
                                for _tk, _tv in _ed_trend.items():
                                    print(f"    {_tk}: {_tv}")

                        # Footer
                        if _cg_sections == 0:
                            print(f"  (No CG modules active yet — check lambda weights)")
                        else:
                            print(f"  ----")
                            print(f"  Active CG sections: {_cg_sections}")
                        print("=" * 70)
                        print("")
                    except Exception as _cg_snap_err:
                        print(f"  [CG Snapshot] Error: {_cg_snap_err}")

            # CG Factual Eval — verify JEPA/Vritti distinguish facts from hallucinations
            if cg_factual_eval is not None and tokenizer is not None:
                _fe_cache = None
                if hasattr(model, 'conscious_gen'):
                    _fe_cache = model.conscious_gen['token_cache'] if 'token_cache' in model.conscious_gen else None
                _fe_metrics = cg_factual_eval.evaluate(
                    model=model,
                    tokenizer=tokenizer,
                    global_step=global_step,
                    token_cache=_fe_cache,
                )
                if _fe_metrics is not None:
                    print(cg_factual_eval.format_console_log(_fe_metrics))
                    for _fk, _fv in _fe_metrics.items():
                        if isinstance(_fv, (int, float)) and _fk != 'step':
                            metrics[f'factual_eval/{_fk}'] = _fv
                    if TENSORBOARD_AVAILABLE and 'writer' in dir() and writer is not None:
                        for _fk, _fv in _fe_metrics.items():
                            if isinstance(_fv, (int, float)) and _fk != 'step':
                                writer.add_scalar(f'factual_eval/{_fk}', _fv, global_step)
                    # Trend summary every 5 evals
                    if len(cg_factual_eval.history) % 5 == 0 and len(cg_factual_eval.history) >= 2:
                        _fe_trend = cg_factual_eval.get_trend_summary()
                        _fe_trend_parts = ["  [FACTUAL-TREND]"]
                        for _tk, _tv in _fe_trend.items():
                            _fe_trend_parts.append(f"    {_tk}: {_tv}")
                        print("\n".join(_fe_trend_parts))

            # Save checkpoint (overwrites last.pt each time)
            if global_step % config.save_every == 0 and not config.no_save:
                # V9.8.10: Ensure scheduled alpha is applied before saving
                update_alpha_schedule(model, global_step, config)
                save_checkpoint(
                    model, optimizer, scheduler, global_step, best_val_loss,
                    ckpt_dir / "last.pt",
                    hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
                    drc_state=relaxation_controller.get_state() if relaxation_controller else None,
                    sgp_state=sgp_controller.get_state() if sgp_controller else None,
                    sattvic_state=sattvic_controller.get_state() if sattvic_controller else None,
                    srk_state=srk.get_checkpoint_state() if srk else None,
                    scaler_state=scaler.state_dict() if scaler else None,
                    # V9.8.6: Three-Phase Curriculum states
                    csr_curriculum_state=csr_curriculum.get_state() if csr_curriculum else None,
                    kosha_curriculum_state=kosha_curriculum.get_state() if kosha_curriculum else None,
                    onto_curriculum_state=onto_curriculum.get_state() if onto_curriculum else None,
                    pidv2_curriculum_state=authority_controller.get_curriculum_state() if authority_controller and hasattr(authority_controller, 'get_curriculum_state') else None,
                    kosha_gyroscope_state=kosha_curriculum_controller.get_state() if kosha_curriculum_controller else None,
                    evoflow_state=evolutionary_engine.get_state() if evolutionary_engine else None,
                    kv_supervisor_state=kv_supervisor.state_dict() if kv_supervisor else None,
                    jepa_injection_projector_state=jepa_injection_projector.state_dict() if jepa_injection_projector else None,
                    cg_stage_manager_state=cg_stage_manager.get_state() if cg_stage_manager else None,
                    experiential_controller_state=experiential_controller.get_full_state() if experiential_controller is not None else None,
                    training_config=_build_training_config_snapshot(config),
                )
                print(f"  💾 Checkpoint saved: last_*.pt (step {global_step})")
                # v2.7 Training State Tracker: Save state on checkpoint
                if training_state_tracker is not None and training_state_tracker.enabled:
                    training_state_tracker.save_state()

    # Final save
    if not config.no_save:
        # V9.8.10: Ensure scheduled alpha is applied before final checkpoint
        update_alpha_schedule(model, global_step, config)
        save_checkpoint(
            model, optimizer, scheduler, global_step, best_val_loss,
            ckpt_dir / "final.pt",
            hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
            drc_state=relaxation_controller.get_state() if relaxation_controller else None,
            sgp_state=sgp_controller.get_state() if sgp_controller else None,
            sattvic_state=sattvic_controller.get_state() if sattvic_controller else None,
            srk_state=srk.get_checkpoint_state() if srk else None,
            scaler_state=scaler.state_dict() if scaler else None,
            # V9.8.6: Three-Phase Curriculum states
            csr_curriculum_state=csr_curriculum.get_state() if csr_curriculum else None,
            kosha_curriculum_state=kosha_curriculum.get_state() if kosha_curriculum else None,
            onto_curriculum_state=onto_curriculum.get_state() if onto_curriculum else None,
            pidv2_curriculum_state=authority_controller.get_curriculum_state() if authority_controller and hasattr(authority_controller, 'get_curriculum_state') else None,
            kosha_gyroscope_state=kosha_curriculum_controller.get_state() if kosha_curriculum_controller else None,
            evoflow_state=evolutionary_engine.get_state() if evolutionary_engine else None,
            kv_supervisor_state=kv_supervisor.state_dict() if kv_supervisor else None,
            jepa_injection_projector_state=jepa_injection_projector.state_dict() if jepa_injection_projector else None,
            cg_stage_manager_state=cg_stage_manager.get_state() if cg_stage_manager else None,
            experiential_controller_state=experiential_controller.get_full_state() if experiential_controller is not None else None,
            training_config=_build_training_config_snapshot(config),
        )
        # v2.7 Training State Tracker: Save final state
        if training_state_tracker is not None and training_state_tracker.enabled:
            training_state_tracker.save_state()

    # Export final Stage 0 trace
    if generation_tracer is not None:
        generation_tracer.export(config.generation_trace_output)
        _final_summary = generation_tracer.summary()
        print(f"\n  [Stage 0 Tracer] Final export: {config.generation_trace_output}")
        print(f"    Total tokens traced: {_final_summary.get('num_tokens', 0)}")
        if 'mean_intent_drift' in _final_summary:
            print(f"    Mean intent drift: {_final_summary['mean_intent_drift']:.4f}")
        if 'mean_cache_hit_rate' in _final_summary:
            print(f"    Mean cache hit rate: {_final_summary['mean_cache_hit_rate']:.3f}")
        if 'ctm_dominant_workload' in _final_summary:
            print(f"    CTM+ dominant workload: {_final_summary['ctm_dominant_workload']}")
            print(f"    CTM+ mode stability: {_final_summary.get('ctm_mode_stability', 0):.3f}")

    # Close TensorBoard
    if tb_writer is not None:
        tb_writer.close()

    print(f"\n{'='*70}")
    print("   TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"  Total Steps: {global_step:,}")
    print(f"  Best Val Loss: {best_val_loss:.4f}")
    print(f"  Best Val PPL: {math.exp(min(best_val_loss, 20)):.2f}")
    if authority_controller is not None:
        print(f"  Final Authority: {authority_controller.A:.3f}")
    if not config.no_save:
        print(f"  Final Checkpoint: {ckpt_dir / 'final_*.pt'}")
    else:
        print(f"  Checkpoints: skipped (--no_save)")

    # ==========================================================================
    # Phase Rotation Test (if enabled)
    # ==========================================================================
    if config.phase_rotation:
        print(f"\n{'='*70}")
        print("PHASE ROTATION TEST")
        print(f"{'='*70}")
        print("\nRunning phase rotation test to verify phase encodes relations...")

        # Parse rotation angles
        rotation_angles = [float(x) for x in config.phase_rotation_angles.split(",")]
        print(f"Testing angles: {rotation_angles}")

        # Run rotation test
        rotation_results = run_phase_rotation_test(
            model=model,
            val_loader=val_loader,
            device=device,
            config=config,
            autocast_dtype=autocast_dtype,
            angles_degrees=rotation_angles,
            cached_val_batches=cached_val_batches if 'cached_val_batches' in dir() else None,
        )

        # Print results
        model_name = config.model_type.replace("_", " ").title()
        print_phase_rotation_results(rotation_results, model_name)


def evaluate(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    config: UnifiedTrainingConfig,
    autocast_dtype: torch.dtype,
    sovereign_loss: Optional['SovereignLoss'] = None,
    sovereign_engine: Optional['SovereignEngine'] = None,
    cached_val_batches: Optional[list] = None,
) -> Tuple[float, Dict[str, float]]:
    """Evaluate model on validation set.

    Args:
        cached_val_batches: Optional pre-cached validation batches (for streaming datasets)
    """
    model.eval()
    total_loss = 0.0
    total_batches = 0

    with torch.no_grad():
        # Use cached batches if available (streaming datasets), otherwise use dataloader
        if cached_val_batches is not None:
            batch_iter = cached_val_batches
        else:
            batch_iter = val_loader

        for batch in batch_iter:
            # Handle different batch formats
            if isinstance(batch, dict):
                x = batch["input_ids"].to(device)
                y = batch["labels"].to(device)
            else:
                x, y = batch
                x, y = x.to(device), y.to(device)

            with torch.amp.autocast('cuda', dtype=autocast_dtype):
                if config.model_type == "ontological":
                    outputs = model(x)
                    phase_angles = outputs.get('phase_angles', None)
                    loss, metrics = compute_ontological_loss(
                        outputs, y, config,
                        sovereign_loss=sovereign_loss,
                        sovereign_engine=sovereign_engine,
                        phase_angles=phase_angles,
                    )
                elif config.model_type == "gen2":
                    outputs = model(x, labels=y)
                    loss = outputs['loss']
                    metrics = {'coherence': outputs['coherence'].mean().item()}
                else:
                    # Phase or Hybrid - handle both tensor and dict returns
                    # V10.2.2: Support chunked evaluation
                    # V10.7.2: Also chunk when TBPTT is enabled (long sequences)
                    # Chunked eval computes loss per-chunk to avoid OOM on full [B,N,V] logits
                    use_eval_chunking = (
                        config.model_type == 'hybrid' and
                        x.shape[1] > getattr(config, 'chunk_size', 256) and
                        (
                            (hasattr(config, 'enable_chunking') and config.enable_chunking) or
                            (hasattr(config, 'enable_tbptt') and config.enable_tbptt)
                        )
                    )

                    if use_eval_chunking:
                        # V10.7.2: Chunked eval — compute loss per-chunk, never materialize full logits
                        eval_chunk_size = getattr(config, 'chunk_size', 256)
                        B_eval, N_eval = x.shape
                        chunk_loss_sum = 0.0
                        chunk_entropy_sum = 0.0
                        chunk_token_count = 0
                        layer_states_eval = None
                        V_eval = None

                        for cs in range(0, N_eval, eval_chunk_size):
                            ce = min(cs + eval_chunk_size, N_eval)
                            chunk_ids = x[:, cs:ce]
                            chunk_targets = y[:, cs:ce]
                            result, layer_states_eval = model.forward_chunk(
                                chunk_ids, chunk_offset=cs, prev_layer_states=layer_states_eval,
                            )
                            chunk_logits = result['logits']  # [B, chunk, V]
                            if V_eval is None:
                                V_eval = chunk_logits.shape[-1]
                            n_tokens = (chunk_targets != -100).sum().item()
                            if n_tokens > 0:
                                chunk_ce = F.cross_entropy(
                                    chunk_logits.reshape(-1, V_eval),
                                    chunk_targets.reshape(-1),
                                    ignore_index=-100,
                                    reduction='sum',
                                )
                                chunk_loss_sum += chunk_ce.item()
                                # Entropy per chunk (for Sattvic controller)
                                with torch.no_grad():
                                    probs = F.softmax(chunk_logits, dim=-1)
                                    ent = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
                                    chunk_entropy_sum += ent.sum().item()
                                chunk_token_count += n_tokens
                            del chunk_logits, result

                        avg_ce = chunk_loss_sum / max(chunk_token_count, 1)
                        max_ent = math.log(V_eval) if V_eval else 1.0
                        avg_entropy = (chunk_entropy_sum / max(chunk_token_count, 1)) / max_ent
                        loss = torch.tensor(avg_ce, device=device)
                        metrics = {
                            "lm_loss": avg_ce,
                            "ppl": math.exp(min(avg_ce, 20)),
                            "total_loss": avg_ce,
                            "onto_entropy": avg_entropy,
                        }
                    else:
                        output = model(x)

                        if isinstance(output, dict):
                            logits = output.get('logits', output.get('output', output.get('last_hidden_state')))
                        else:
                            logits = output
                        loss, metrics = compute_phase_loss(logits, y, config)

            total_loss += loss.item()
            total_batches += 1

            if total_batches >= 50:  # Limit eval batches
                break

    avg_loss = total_loss / total_batches
    return avg_loss, {"ppl": math.exp(min(avg_loss, 20))}


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified SymbolU LLM Training",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Model
    parser.add_argument("--model_type", type=str, default="ontological",
                       choices=["ontological", "phase", "hybrid", "gen2", "standard", "gct", "ontological_hybrid", "binding_cache", "ontological_binding_cache", "mistral_cg", "mistral_hybrid"],
                       help="Model architecture type (standard = O(n²) baseline, "
                            "gct = Gated Coherence Transformer [pre-softmax coherence routing], "
                            "ontological_hybrid = Two-Tier AGI, "
                            "binding_cache = Protected Phase + Top-K Query [V10.0], "
                            "ontological_binding_cache = AGI Architecture [Binding Cache + 32D Sovereign State], "
                            "mistral_cg = Frozen Mistral backbone + trainable CG modules, "
                            "mistral_hybrid = Frozen Mistral backbone + trainable Phase layers [no CG])")
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large"],
                       help="Model size preset")
    parser.add_argument("--max_seq_len", type=int, default=2048,
                       help="Maximum sequence length")

    # Architecture overrides (optional - override model_size preset)
    parser.add_argument("--n_layer", type=int, default=None,
                       help="Number of transformer layers (overrides model_size)")
    parser.add_argument("--n_head", type=int, default=None,
                       help="Number of attention heads (overrides model_size)")
    parser.add_argument("--n_embd", type=int, default=None,
                       help="Embedding dimension (overrides model_size)")
    parser.add_argument("--n_kv_heads", type=int, default=None,
                       help="Number of KV heads for GQA (if None, uses n_head)")
    parser.add_argument("--dropout", type=float, default=0.1,
                       help="Dropout rate")
    parser.add_argument("--attention_dropout", type=float, default=0.1,
                       help="Attention dropout rate")

    # GCT (Gated Coherence Transformer) arguments
    parser.add_argument("--gct_window_size", type=int, default=128,
                       help="GCT local window size for coarse attention path")
    parser.add_argument("--gct_coherence_gamma", type=float, default=5.0,
                       help="GCT output delta sensitivity in coherence score")
    parser.add_argument("--gct_coherence_delta", type=float, default=3.0,
                       help="GCT residual delta sensitivity in coherence score")
    parser.add_argument("--gct_ema_decay", type=float, default=0.9,
                       help="GCT EMA smoothing decay for coherence scores")
    parser.add_argument("--gct_num_bands", type=int, default=3,
                       help="GCT number of frequency bands for head partitioning")
    parser.add_argument("--gct_alpha_sharpness", type=float, default=10.0,
                       help="GCT sigmoid sharpness for routing probability")
    parser.add_argument("--gct_hard_route_threshold", type=float, default=0.5,
                       help="GCT hard routing threshold for inference")
    parser.add_argument("--gct_kappa", type=float, default=3.0,
                       help="GCT lambda_ladder suppression strength")
    parser.add_argument("--gct_tau_ladder", type=float, default=0.15,
                       help="GCT collapse detection threshold for lambda_ladder")
    parser.add_argument("--gct_warmup_steps", type=int, default=500,
                       help="GCT Phase 1: full-attention-only warmup steps")
    parser.add_argument("--gct_anneal_steps", type=int, default=2000,
                       help="GCT Phase 2: anneal from full to gated attention over N steps")

    # Training
    parser.add_argument("--batch_size", type=int, default=8,
                       help="Batch size per GPU (reference batch for seq len curriculum)")
    parser.add_argument("--batch_size_max", type=int, default=512,
                       help="Max batch size for dynamic scaling (seq len curriculum). Higher = more VRAM utilization")
    parser.add_argument("--gradient_accumulation", type=int, default=1,
                       help="Gradient accumulation steps")
    parser.add_argument("--vram_threshold", type=float, default=0.95,
                       help="VRAM usage %% to trigger batch reduction (0.95=95%%, higher=more aggressive)")
    parser.add_argument("--vram_recovery_buffer", type=float, default=0.12,
                       help="Recovery buffer: batch increases when VRAM < (threshold - buffer). 0.12=80%% recovery with 92%% threshold")
    parser.add_argument("--max_steps", type=int, default=10000,
                       help="Maximum training steps")
    parser.add_argument("--learning_rate", type=float, default=3e-4,
                       help="Peak learning rate")
    parser.add_argument("--warmup_steps", type=int, default=500,
                       help="Max warmup steps (fallback if PPL doesn't drop)")
    parser.add_argument("--warmup_until_ppl", type=float, default=500.0,
                       help="End warmup when PPL < this (0 = disabled, use fixed steps)")
    parser.add_argument("--weight_decay", type=float, default=0.1,
                       help="Weight decay (L2 regularization)")
    parser.add_argument("--max_grad_norm", type=float, default=1.0,
                       help="Maximum gradient norm for clipping")
    parser.add_argument("--use_per_layer_clipping", action="store_true",
                       help="Clip authority/sensory gradients separately (respects 9:3 design)")
    parser.add_argument("--use_8bit_optimizer", action="store_true",
                       help="Use bitsandbytes 8-bit AdamW (saves ~50%% optimizer memory)")
    parser.add_argument("--use_compile", action="store_true",
                       help="Use torch.compile() for faster training (PyTorch 2.0+)")
    parser.add_argument("--no_compile", action="store_true",
                       help="Disable torch.compile() (use if seeing compilation errors)")

    # Dataset
    parser.add_argument("--dataset", type=str, default="wikitext103",
                       choices=["wikitext103", "wikitext2", "fineweb", "mixed", "reasoning_hf", "reasoning", "synthetic"],
                       help="Training dataset: wikitext103, wikitext2, fineweb, mixed (interleaved), reasoning_hf, reasoning, or synthetic")
    parser.add_argument("--dataset_name", type=str, default="HuggingFaceFW/fineweb",
                       help="HuggingFace dataset name for fineweb/reasoning_hf mode (e.g., meta-math/MetaMathQA, nvidia/OpenMathInstruct-2)")
    parser.add_argument("--dataset_subset", type=str, default="sample-10BT",
                       help="Dataset subset/config for fineweb mode")
    parser.add_argument("--mix_datasets", type=str, default="",
                       help="For --dataset mixed: comma-separated sources with weights, e.g. 'wikitext103:0.7,reasoning_hf:0.3'")
    parser.add_argument("--cache_val_batches", type=int, default=20,
                       help="Pre-cache N validation batches for streaming datasets (0=disable)")
    parser.add_argument("--cache_dataset", action="store_true",
                       help="Download and cache FineWeb dataset locally (slower first run, faster subsequent)")

    # Memory optimization
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing")
    parser.add_argument("--checkpoint_offload_cpu", action="store_true",
                       help="Offload checkpointed activations to CPU (metabolic tuning for large models)")
    parser.add_argument("--mixed_precision", type=str, default="bf16",
                       choices=["none", "fp16", "bf16"],
                       help="Mixed precision training")
    parser.add_argument("--use_amp", action="store_true",
                       help="Enable Automatic Mixed Precision training with bf16 (convenience flag, equivalent to --mixed_precision bf16)")

    # Hybrid-specific
    parser.add_argument("--local_backend", type=str, default="auto",
                       choices=["auto", "flash", "sdpa", "unfold"],
                       help="LocalAttention backend")
    parser.add_argument("--window_size", type=int, default=256,
                       help="Local attention window size")
    parser.add_argument("--local_layers", type=int, default=4,
                       help="Number of local-only attention layers (hybrid mode)")
    parser.add_argument("--alpha_local", type=float, default=0.8,
                       help="Weight for local attention in hybrid layers")
    parser.add_argument("--alpha_phase", type=float, default=0.2,
                       help="Weight for phase attention in hybrid layers")

    # ==========================================================================
    # V10.14: GLOBAL TOKENS / SLOT MEMORY (GCT)
    # ==========================================================================
    parser.add_argument("--global_tokens", action="store_true",
                       help="Enable SlotMemoryGCT for long-range associative retrieval")
    parser.add_argument("--num_global_tokens", type=int, default=64,
                       help="Number of memory slots (default: 64)")
    parser.add_argument("--global_update_mode", type=str, default="slots",
                       choices=["pool", "attn-lite", "slots"],
                       help="Global token update mode (default: slots)")
    parser.add_argument("--slots_write_lr", type=float, default=0.15,
                       help="EMA learning rate for slot writes (default: 0.15)")
    parser.add_argument("--retrieval_loss_weight", type=float, default=2.0,
                       help="Weight for auxiliary slot retrieval loss (default: 2.0)")
    parser.add_argument("--slot_auto_scale", action="store_true",
                       help="V20: Auto-derive slot hyperparameters from model size, training budget, and context length")
    parser.add_argument("--slot_prediction_loss_weight", type=float, default=0.1,
                       help="V11.4: Weight for slot-only prediction loss (default: 0.1)")
    parser.add_argument("--slot_memory_lr_scale", type=float, default=0.1,
                       help="Slot param LR multiplier vs main LR (default: 0.1)")
    # V11: Slot memory experiment — read interval and late-layer writes
    parser.add_argument("--global_read_interval", type=int, default=1,
                       help="Read slots every N layers (default: 1 = every layer)")
    parser.add_argument("--global_write_start_layer", type=int, default=0,
                       help="Only write to slots from this layer onward (default: 0)")
    parser.add_argument("--disable_slot_adaptive_constraints", action="store_true",
                       help="Disable adaptive constraint relaxation controller for slot memory")
    parser.add_argument("--reset_slot_constraints", action="store_true",
                       help="Reset adaptive constraints to initial defaults on resume (undo drift from prior runs)")
    parser.add_argument("--slot_gate_target", type=float, default=None,
                       help="Write gate soft ceiling target (default: 0.35)")
    parser.add_argument("--slot_gate_ceil_weight", type=float, default=None,
                       help="Gate ceiling penalty weight (default: 5.0, 0=disable ceiling)")
    parser.add_argument("--slot_gate_ceil_margin", type=float, default=None,
                       help="Free exploration zone above gate target before penalty (default: 0.05)")
    # V16: Semantic coherence gate
    parser.add_argument("--slot_coherence_floor", type=float, default=None,
                       help="Initial coherence floor for semantic write gate (default: 0.3, decays to 0)")
    parser.add_argument("--slot_coherence_floor_tied", action="store_true", default=True,
                       help="V16.1: Tie coherence floor to slot LR scale schedule (default: on)")
    parser.add_argument("--no_slot_coherence_floor_tied", dest="slot_coherence_floor_tied",
                       action="store_false",
                       help="V16.1: Disable tied coherence floor, use independent step-based decay")
    # V10.23: Three-phase proportional slot LR controller (auto-enabled with slot memory)
    # Phase 1 ends automatically when warmup_complete + sufficient signal history
    parser.add_argument("--slot_lr_scale_min", type=float, default=0.1,
                       help="Floor for slot LR scale (default: 0.1)")
    parser.add_argument("--slot_lr_scale_max", type=float, default=0.8,
                       help="Ceiling for slot LR scale (default: 0.8)")
    parser.add_argument("--slot_lr_eta", type=float, default=0.03,
                       help="Proportional controller gain; 0 disables adaptation (default: 0.03)")
    parser.add_argument("--slot_lr_stabilize_after", type=int, default=None,
                       help="Hard step limit to freeze slot LR (default: None = auto-detect convergence)")

    # ==========================================================================
    # V10.2.1: CHUNKING FOR LONG SEQUENCES
    # ==========================================================================
    # Enables processing sequences longer than max_seq_len by chunking
    # Phase attention persists state across chunks (temporal memory)
    # Local attention resets per chunk (spatial reasoning)
    parser.add_argument("--enable_chunking", action="store_true",
                       help="Enable chunked training for long sequences. "
                            "Phase state persists across chunks, Local resets per chunk.")
    parser.add_argument("--chunk_size", type=int, default=512,
                       help="Size of each chunk when chunking is enabled. "
                            "Should be <= max_seq_len. Smaller = less memory, more chunks.")
    parser.add_argument("--protected_phase", action="store_true", default=True,
                       help="Use Protected Phase pattern (RECOMMENDED). "
                            "Local cross-attends to Phase memory instead of parallel blending. "
                            "Ensures Phase learns useful representations.")
    parser.add_argument("--no_protected_phase", action="store_true",
                       help="Disable Protected Phase (use legacy parallel blending). "
                            "NOT recommended for chunking - causes gradient competition.")
    parser.add_argument("--run_chunk_diagnostic", action="store_true",
                       help="Run chunk continuity diagnostic at start of training. "
                            "Verifies: Phase continuity, attention source, amplitude health.")
    parser.add_argument("--chunk_diagnostic_seq_len", type=int, default=2048,
                       help="Sequence length for chunk diagnostic test")
    parser.add_argument("--enable_tbptt", action="store_true",
                       help="V10.7: Use Truncated BPTT for chunked training. "
                            "Detaches state between chunks to reduce training memory from O(N) to O(C). "
                            "Implies --enable_chunking. Slight compute overhead (~10-20%%) but "
                            "dramatic memory reduction for long sequences.")

    # Alpha decay schedule (for phase/hybrid attention)
    parser.add_argument("--alpha_phase_start", type=float, default=0.6,
                       help="Initial alpha_phase value (decays over time)")
    parser.add_argument("--alpha_phase_end", type=float, default=0.4,
                       help="Final alpha_phase value after decay")
    parser.add_argument("--alpha_decay_steps", type=int, default=10000,
                       help="Steps over which alpha_phase decays from start to end")

    # ==========================================================================
    # PHASE-FIRST CURRICULUM (unified inverse curriculum)
    # ==========================================================================
    parser.add_argument("--phase_first_curriculum", action="store_true",
                       help="Enable phase-first learning: SRK strong→weak, alpha high→low, window small→large")

    # PPL-gated alpha curriculum (phase dominates early, local refines later)
    parser.add_argument("--enable_ppl_alpha_curriculum", action="store_true",
                       help="Adjust alpha_phase based on PPL (phase dominates when PPL high)")
    parser.add_argument("--alpha_phase_ppl_high", type=float, default=0.8,
                       help="alpha_phase when PPL >= ppl_high_threshold")
    parser.add_argument("--alpha_phase_ppl_low", type=float, default=0.3,
                       help="alpha_phase when PPL <= ppl_low_threshold")
    parser.add_argument("--ppl_high_threshold", type=float, default=1000.0,
                       help="PPL threshold for max phase weight")
    parser.add_argument("--ppl_low_threshold", type=float, default=100.0,
                       help="PPL threshold for min phase weight")
    # Adaptive window size (small early for fast phase, large later for local context)
    parser.add_argument("--enable_adaptive_window", action="store_true",
                       help="Adapt window size based on PPL (small when high, large when low)")
    parser.add_argument("--window_size_high_ppl", type=int, default=128,
                       help="Window size when PPL >= ppl_high_threshold (fast phase learning)")
    parser.add_argument("--window_size_low_ppl", type=int, default=256,
                       help="Window size when PPL <= ppl_low_threshold (better local context)")
    # Post-curriculum adaptive alpha (slot ablation-driven)
    parser.add_argument("--enable_adaptive_alpha", action="store_true",
                       help="After PPL curriculum settles, adapt alpha_phase based on slot ablation delta")
    parser.add_argument("--adaptive_alpha_min", type=float, default=0.20,
                       help="Floor for adaptive alpha_phase (default: 0.20)")
    parser.add_argument("--adaptive_alpha_max", type=float, default=0.60,
                       help="Ceiling for adaptive alpha_phase (default: 0.60)")

    # Decorrelation loss (to force phase and local to learn different features)
    parser.add_argument("--decorr_loss_weight", type=float, default=0.0,
                       help="Weight for decorrelation loss (0=disabled, 0.1=recommended)")

    # V9.9.10: Phase diversity loss (combat phase collapse)
    parser.add_argument("--phase_diversity_weight", type=float, default=0.0,
                       help="Weight for phase diversity loss (0=disabled, 0.001=start, ramp to 0.01)")
    parser.add_argument("--phase_diversity_ramp_steps", type=int, default=5000,
                       help="Steps to ramp phase diversity weight linearly (ignored if adaptive)")

    # V9.9.12: Adaptive Phase Diversity Controller (ChatGPT Universal Proposal)
    parser.add_argument("--enable_adaptive_phase_diversity", action="store_true",
                       help="Use adaptive controller instead of fixed weight. "
                            "Automatically adjusts λ based on R (mean resultant length).")
    parser.add_argument("--phase_diversity_target_R", type=float, default=0.25,
                       help="Target R for adaptive controller (0.25 = healthy diversity)")
    parser.add_argument("--phase_diversity_lambda_init", type=float, default=0.0001,
                       help="Initial λ value after ramp")
    parser.add_argument("--phase_diversity_lambda_max", type=float, default=0.1,
                       help="Maximum λ ceiling")
    parser.add_argument("--phase_diversity_eta", type=float, default=0.1,
                       help="Control gain (how fast λ adapts to R)")
    parser.add_argument("--phase_diversity_ramp_multiplier", type=float, default=5.0,
                       help="ramp_steps = multiplier * warmup_steps (universal ramp)")
    # V9.9.12b: Task-loss scaling (ChatGPT's Lagrange multiplier approach)
    parser.add_argument("--phase_diversity_task_scaling", action="store_true", default=True,
                       help="Scale λ by task loss (self-normalizing, ChatGPT's Lagrange approach)")
    parser.add_argument("--no_phase_diversity_task_scaling", action="store_true",
                       help="Disable task-loss scaling (use pure R-adaptive mode)")
    parser.add_argument("--phase_diversity_task_alpha", type=float, default=0.01,
                       help="Base coefficient for task-loss scaling mode")

    # V9.9.1 Per-Layer Phase Control (for Inverted Curriculum)
    parser.add_argument("--enable_per_layer_phase", action="store_true",
                       help="Enable per-layer phase weight control (for inverted curriculum)")
    parser.add_argument("--per_layer_phase_weights", type=str, default="",
                       help="Initial per-layer phase weights, comma-separated 12 values (e.g., '0,0,0,0,0,0,0,0,0,0,0,0' for all Sensory)")
    parser.add_argument("--layer_transition_steps", type=int, default=500,
                       help="Steps for soft layer transitions during evolution")

    # V9.9.1 Inverted Curriculum Controller
    parser.add_argument("--enable_inverted_curriculum", action="store_true",
                       help="Enable full inverted curriculum (3:9→9:3 with seq length growth)")
    parser.add_argument("--inverted_curriculum_stages", type=str, default="",
                       help="Custom curriculum stages: '3:9@256,5:7@512,6:6@768,9:3@2048' (split@seq_len)")
    parser.add_argument("--inverted_curriculum_ppl_triggers", type=str, default="",
                       help="PPL triggers for stage advancement: '300,200,120,75,45,25'")
    # V9.9.4: PPL Stability Check (ChatGPT's Readiness Index)
    parser.add_argument("--inverted_curriculum_stability_threshold", type=float, default=5.0,
                       help="Max PPL slope to consider 'stable' for stage advancement (lower=stricter)")
    parser.add_argument("--inverted_curriculum_stability_stages", type=str, default="2,3,4",
                       help="Stages requiring PPL stability check: '2,3,4' (geometry shift zone)")

    # V9.6.12: Cosine mode for phase attention
    parser.add_argument("--cosine_mode", type=str, default="standard",
                       choices=["standard", "shifted", "complex"],
                       help="Cosine interaction mode: 'standard' (cos, range [-1,1]), "
                            "'shifted' (1+cos, range [0,2], no negative cancellation), "
                            "'complex' (uses both cos and sin for directional asymmetry)")

    # V9.6.13: State decay factor for phase attention
    parser.add_argument("--decay_gamma", type=float, default=1.0,
                       help="State decay factor for phase attention (1.0=infinite memory, "
                            "<1.0=local focus like Mamba/RWKV). "
                            "Example: 0.9 = ~10 token memory, 0.95 = ~20 token memory")
    # V9.9.7: Learned per-head decay (Mamba/S4-style)
    parser.add_argument("--learned_decay", action="store_true",
                       help="Enable per-head learned decay (Mamba/S4-style). "
                            "Each attention head learns its own decay rate [0.5, 1.0] via gradient descent. "
                            "Adds 1 learnable parameter per head. Allows model to learn optimal attention span.")

    # V9.9.11: Phase collapse fixes (ChatGPT mandatory fixes)
    parser.add_argument("--bounded_phase", action="store_true", default=True,
                       help="Constrain phase to [-π, π] via π*sin() for proper S¹ manifold geometry. "
                            "Prevents raw linear phase projections from drifting unbounded and causing collapse. (default: True)")
    parser.add_argument("--no-bounded-phase", dest="bounded_phase", action="store_false",
                       help="Disable bounded phase (use raw linear projection). "
                            "WARNING: May cause phase collapse and decorative phase behavior.")
    parser.add_argument("--zero_mean_cosine", action="store_true",
                       help="Center cosine per head to force selectivity. "
                            "Without this, cosine is always positive-biased and collapse is inevitable.")

    # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
    parser.add_argument("--dual_channel_mode", action="store_true",
                       help="Enable dual-channel attention: separates content similarity from intent alignment. "
                            "s_content = cos(φ_q - φ_k) (what matches), "
                            "s_align = cos(θ_JEPA - θ_SRK) (intent agreement), "
                            "score = s_content * (1 + α * s_align). "
                            "Prevents intent from dominating content selectivity.")
    parser.add_argument("--alignment_authority", type=float, default=0.1,
                       help="α: Weight for alignment term in dual-channel mode (default: 0.1). "
                            "0.0 = pure content matching (intent ignored), "
                            "0.1 = mild intent influence (recommended), "
                            "1.0 = strong intent influence.")

    # ==========================================================================
    # V10.6+ CONTROL-PLANE ITEMS (Hard Probes Integration)
    # ==========================================================================
    # V10.6.1: Alignment Clamp (ChatGPT caveat - prevents over-constraint collapse)
    parser.add_argument("--alignment_clamp_min", type=float, default=0.8,
                       help="Lower clamp bound for alignment modulator (default: 0.8). "
                            "Prevents over-suppression from sustained misalignment.")
    parser.add_argument("--alignment_clamp_max", type=float, default=1.2,
                       help="Upper clamp bound for alignment modulator (default: 1.2). "
                            "Prevents over-amplification from sustained alignment.")

    # V10.6.2 D.5: No-Write Contract Enforcement
    parser.add_argument("--strict_control_contract", action="store_true", default=True,
                       help="Enable strict mode for D.5 no-write contract (violations raise exceptions)")
    parser.add_argument("--no_strict_control_contract", dest="strict_control_contract",
                       action="store_false",
                       help="Warn-only mode for D.5 no-write contract (violations logged, not raised)")

    # V10.6.3: Architecture Health Summary
    parser.add_argument("--run_architecture_health_check", action="store_true", default=True,
                       help="Run architecture health check at training start (PASS/WARN/FAIL)")
    parser.add_argument("--no_architecture_health_check", dest="run_architecture_health_check",
                       action="store_false",
                       help="Skip architecture health check at training start")
    parser.add_argument("--architecture_health_strict", action="store_true",
                       help="Abort training if architecture health check returns FAIL")

    # V10.6.5: Parameter-Matched Baseline Enforcement
    parser.add_argument("--enforce_baseline_param_match", action="store_true", default=True,
                       help="Validate that baseline comparisons use parameter-matched models")
    parser.add_argument("--no_baseline_param_match", dest="enforce_baseline_param_match",
                       action="store_false",
                       help="Skip parameter-match validation for baseline comparisons")

    # V10.6.6: Quad Utilization Sanity Checks
    parser.add_argument("--enable_quad_utilization_checks", action="store_true",
                       help="Enable periodic quad utilization sanity checks during training")
    parser.add_argument("--quad_utilization_warn_threshold", type=float, default=0.01,
                       help="Warn if quad contributes less than this fraction (default: 0.01 = 1%%)")
    parser.add_argument("--quad_utilization_check_interval", type=int, default=100,
                       help="Check quad utilization every N steps (default: 100)")

    # V10.6.7: Lightweight Probe Hooks
    parser.add_argument("--enable_probe_hooks", action="store_true",
                       help="Enable lightweight diagnostic probes during training (not full datasets)")
    parser.add_argument("--probe_hook_interval", type=int, default=500,
                       help="Run lightweight probes every N steps (default: 500)")
    parser.add_argument("--probe_hook_types", type=str, default="phase_rotation,chunk_continuity",
                       help="Comma-separated probe types: phase_rotation, chunk_continuity, control_contract")

    # Phase Rotation Test (validates phase encodes relational structure)
    parser.add_argument("--phase_rotation", action="store_true",
                       help="Run phase rotation test after training to verify phase encodes relations. "
                            "Rotates φ_k by various angles and measures accuracy/perplexity change.")
    parser.add_argument("--phase_rotation_angles", type=str, default="0,45,90,135,180,270",
                       help="Comma-separated rotation angles in degrees for --phase_rotation test. "
                            "(default: 0,45,90,135,180,270)")
    parser.add_argument("--phase_rotation_as_diagnostic", action="store_true",
                       help="Run phase rotation as periodic diagnostic during training, "
                            "not just at the end.")

    # V10.0: Binding Cache architecture (validated by diagnostic probes)
    parser.add_argument("--binding_cache_top_k", type=int, default=64,
                       help="Top-K cache size per head for binding_cache model. "
                            "Reduces O(n²) attention to O(nk). Use 0 for full attention.")
    parser.add_argument("--binding_cache_use_cache", action="store_true", default=True,
                       help="Use Top-K cache in binding_cache model (default: True)")
    parser.add_argument("--no_binding_cache", action="store_true",
                       help="Disable Top-K cache in binding_cache model (use full O(n²) attention)")

    # V10.5: Interference-Aware Proposal Scoring (compositional creativity)
    # Applied AFTER BCVF, BEFORE phase integration. Task-conditional, entropy-gated.
    parser.add_argument("--enable_quad_interference", action="store_true",
                       help="Enable interference-aware proposal scoring for compositional tasks. "
                            "Boosts mutually consistent proposals. OFF by default.")
    parser.add_argument("--interference_lambda_text", type=float, default=0.02,
                       help="Interference strength for text (0.01-0.03). Lower than vision.")
    parser.add_argument("--interference_min_step", type=int, default=8,
                       help="Only apply interference after N decoding steps (late decoding).")
    parser.add_argument("--interference_entropy_gate", type=float, default=1.2,
                       help="Only apply interference if proposal entropy > threshold.")
    parser.add_argument("--interference_auto_classify", action="store_true", default=True,
                       help="Auto-detect compositional tasks and enable interference accordingly.")
    parser.add_argument("--no_interference_auto_classify", action="store_true",
                       help="Disable auto-classification (manual control only).")
    parser.add_argument("--interference_modes", type=str, default="compose,reason,write",
                       help="Comma-separated interference modes: compose,reason,write")

    # V10.0: Ontological Binding Annotator (CSR/Kosha/SRK as SELECTORS, not attention modifiers)
    # Clean separation: Attention = physics, Annotator = semantics
    parser.add_argument("--use_binding_annotator", action="store_true", default=True,
                       help="Enable OntologicalBindingAnnotator for binding salience (Top-K selection bias)")
    parser.add_argument("--no_binding_annotator", action="store_true",
                       help="Disable OntologicalBindingAnnotator (pure attention, no semantic selection)")
    parser.add_argument("--use_csr_annotation", action="store_true", default=True,
                       help="Enable CSR (phonological grounding) in binding annotation")
    parser.add_argument("--no_csr_annotation", action="store_true",
                       help="Disable CSR in binding annotation")
    parser.add_argument("--use_kosha_annotation", action="store_true", default=True,
                       help="Enable Kosha (consciousness sheaths) in binding annotation")
    parser.add_argument("--no_kosha_annotation", action="store_true",
                       help="Disable Kosha in binding annotation")
    parser.add_argument("--use_srk_annotation", action="store_true", default=True,
                       help="Enable SRK (Sovereign State) in binding annotation")
    parser.add_argument("--no_srk_annotation", action="store_true",
                       help="Disable SRK in binding annotation")

    # V9.8.0: Ontological Hybrid (Two-Tier AGI) with 32D Sovereign State
    parser.add_argument("--state_dim", type=int, default=SOVEREIGN_STATE_DIM,
                       help="Sovereign State dimension for ontological_hybrid model "
                            "(default 32 = 12 Bhava + 5 Kosha + 5 Vritti + 6 Guna + 4 Reserved). "
                            "V9.8.0: Replaces arbitrary 124D with principled ontology.")
    parser.add_argument("--project_per_head_dim", action="store_true",
                       help="Project state delta to [H, D_h] instead of [H] for finer control")

    # Mistral CG Wrapper (--model_type mistral_cg)
    parser.add_argument("--mistral_model_name", type=str, default="mistralai/Mistral-7B-v0.3",
                       help="HuggingFace model ID for Mistral backbone")
    parser.add_argument("--mistral_quantize", type=str, default="none",
                       choices=["none", "4bit", "8bit"],
                       help="Quantization mode for Mistral backbone (4bit saves most VRAM)")
    parser.add_argument("--mistral_device_map", type=str, default="auto",
                       help="Device placement strategy for Mistral backbone")
    parser.add_argument("--mistral_trust_remote_code", action="store_true",
                       help="Trust remote code when loading Mistral model")
    parser.add_argument("--mistral_phase_adapter_hidden", type=int, default=1024,
                       help="Hidden dimension for phase-conditioned adapter MLP")

    # Mistral Hybrid Wrapper (--model_type mistral_hybrid)
    parser.add_argument("--mistral_hybrid_num_phase_layers", type=int, default=4,
                       help="Number of Phase attention layers on top of Mistral backbone")
    parser.add_argument("--mistral_hybrid_local_layers", type=int, default=2,
                       help="First N Phase layers use local attention only (rest are hybrid)")
    parser.add_argument("--phase_ppl_delta_interval", type=int, default=500,
                       help="Steps between Phase PPL delta measurement (0=disable)")

    # Knowledge Distillation from Mistral
    parser.add_argument("--distill_from_mistral", action="store_true",
                       help="Use frozen Mistral as teacher for knowledge distillation")
    parser.add_argument("--distill_temperature", type=float, default=2.0,
                       help="Softmax temperature for soft targets (higher = softer)")
    parser.add_argument("--distill_alpha", type=float, default=0.5,
                       help="Weight for KD loss vs CE loss (1.0 = pure KD)")
    parser.add_argument("--distill_warmup_steps", type=int, default=0,
                       help="Steps of CE-only training before KD kicks in")

    # Ontological-specific
    parser.add_argument("--bhava_lambda", type=float, default=0.1,
                       help="Bhava relationship loss weight")
    parser.add_argument("--coherence_lambda", type=float, default=0.05,
                       help="Coherence loss weight")

    # Sovereign-Lagrangian Loss [Patent B1/S3]
    parser.add_argument("--b1_lambda", type=float, default=0.5,
                       help="Consistency Lagrangian weight [B1] (forward/backward alignment)")
    parser.add_argument("--mu_s3", type=float, default=0.2,
                       help="Global Coherence weight [S3] (phase-lock penalty)")
    parser.add_argument("--enable_sovereign_loss", action="store_true",
                       help="Enable Sovereign-Lagrangian loss (B1+S3) instead of standard CE")
    parser.add_argument("--sovereign_weight_r", type=float, default=5.0,
                       help="R-Signal (ontology) weight for Sovereign-1 loss (default 5.0)")
    parser.add_argument("--sovereign_weight_s", type=float, default=2.0,
                       help="S-Signal (referent) weight for Sovereign-1 loss (default 2.0)")
    parser.add_argument("--sovereign_weight_c", type=float, default=0.5,
                       help="C-Signal (phoneme) weight for Sovereign-1 loss (default 0.5)")
    parser.add_argument("--enable_stability_constraint", action="store_true",
                       help="Enable S8 Stability Constraint (entropy-based anchoring)")
    parser.add_argument("--gc_floor", type=float, default=0.65,
                       help="Minimum Guna Coherence before PIDv2 intervention")

    # V9.5.1 Entropy Floor (breaks repetition curse)
    parser.add_argument("--enable_entropy_floor", action="store_true",
                       help="Enable entropy floor penalty (prevents stiffness)")
    parser.add_argument("--entropy_floor", type=float, default=0.48,
                       help="Minimum entropy target (default 0.48)")
    parser.add_argument("--entropy_floor_weight", type=float, default=0.1,
                       help="Weight for entropy floor penalty")

    # Entropy-Based Logit Scale Control
    parser.add_argument("--enable_entropy_control_train", action="store_true",
                       help="Enable train-time entropy-based logit scale control")
    parser.add_argument("--enable_entropy_control_infer", action="store_true",
                       help="Enable inference-time adaptive entropy control")
    parser.add_argument("--entropy_topk", type=int, default=50,
                       help="K for top-K entropy computation (default: 50)")
    parser.add_argument("--entropy_h_min", type=float, default=0.15,
                       help="Lower bound of target entropy band (default: 0.15)")
    parser.add_argument("--entropy_h_max", type=float, default=0.35,
                       help="Upper bound of target entropy band (default: 0.35)")
    parser.add_argument("--entropy_control_lambda", type=float, default=0.01,
                       help="Weight for entropy band penalty (default: 0.01)")
    parser.add_argument("--logit_scale_min", type=float, default=-4.0,
                       help="Minimum logit scale clamp (default: -4.0)")
    parser.add_argument("--logit_scale_max", type=float, default=4.0,
                       help="Maximum logit scale clamp (default: 4.0)")
    parser.add_argument("--infer_h_target", type=float, default=0.25,
                       help="Target entropy midpoint for inference (default: 0.25)")
    parser.add_argument("--infer_eta", type=float, default=0.02,
                       help="Inference adaptation learning rate (default: 0.02)")
    parser.add_argument("--infer_delta_clip", type=float, default=0.05,
                       help="Inference error clipping bound (default: 0.05)")

    # V9.5.1 Force Evolution (manual intervention)
    parser.add_argument("--force_evolution_stage", type=int, default=None,
                       help="Force evolution to specific stage: 1=6:6, 2=5:7, 3=4:8, 4=3:9")

    # V9.9.1 Multi-Stage Evolution Configuration
    parser.add_argument("--enable_multi_stage_evolution", action="store_true", default=True,
                       help="Enable automatic multi-stage evolution (9:3→6:6→5:7→4:8→3:9)")
    parser.add_argument("--disable_multi_stage_evolution", action="store_true",
                       help="Disable multi-stage evolution (stay at initial split)")
    parser.add_argument("--evolution_trigger_mode", type=str, default="auto",
                       choices=["auto", "metrics", "ppl", "step"],
                       help="Evolution trigger mode: auto (detect), metrics (coherence/entropy), ppl (perplexity), step (fixed steps)")
    parser.add_argument("--evolution_ppl_triggers", type=str, default="",
                       help="PPL thresholds to trigger evolution, comma-separated (e.g., '100,50,25,15')")
    parser.add_argument("--evolution_step_triggers", type=str, default="",
                       help="Step numbers to trigger evolution, comma-separated (e.g., '10000,30000,50000,70000')")
    parser.add_argument("--custom_evolution_stages", type=str, default="",
                       help="Custom evolution stages, comma-separated (e.g., '9:3,6:6,4:8,3:9')")
    parser.add_argument("--evolution_patience", type=int, default=200,
                       help="Steps of stable metrics before evolution (metrics mode)")
    parser.add_argument("--evolution_coherence_min", type=float, default=0.82,
                       help="Minimum coherence to evolve (metrics mode)")
    parser.add_argument("--evolution_entropy_floor", type=float, default=0.42,
                       help="Minimum entropy to evolve (metrics mode)")
    parser.add_argument("--evolution_ppl_window", type=int, default=10,
                       help="Steps to average PPL for smoother triggers")
    parser.add_argument("--evolution_thaw_alpha", type=float, default=0.1,
                       help="Initial gradient scale for newly sensory layers after evolution")
    parser.add_argument("--evolution_thaw_steps", type=int, default=300,
                       help="Steps to ramp newly sensory layer gradients after evolution")

    # V9.5.2 Emergency Stress-Probe (Phase A: 3:9 Rajas)
    # ChatGPT Guardrails: Compound trigger, strict duration, gradual LR restore
    parser.add_argument("--enable_stress_probe", action="store_true",
                       help="Enable automatic stress-probe detection for stiffness")
    parser.add_argument("--stress_probe_entropy_trigger", type=float, default=0.42,
                       help="Trigger when entropy < this (ChatGPT: 0.42)")
    parser.add_argument("--stress_probe_rep3_trigger", type=float, default=0.18,
                       help="Trigger when REP-3 > this (ChatGPT: 0.18)")
    parser.add_argument("--stress_probe_utr_trigger", type=float, default=0.55,
                       help="Trigger when UTR < this (ChatGPT: 0.55)")
    parser.add_argument("--stress_probe_drs_trigger", type=float, default=12.0,
                       help="Trigger when DRS > this (ChatGPT: 12)")
    parser.add_argument("--stress_probe_coherence_min", type=float, default=0.80,
                       help="Only trigger if coherence > this (stiff, not dying)")
    parser.add_argument("--stress_probe_patience", type=int, default=2,
                       help="Consecutive evals of degeneracy before triggering (ChatGPT: 2)")
    parser.add_argument("--stress_probe_authority_scale", type=float, default=0.05,
                       help="Authority layer gradient scale during stress-probe (nearly frozen)")
    parser.add_argument("--stress_probe_lr_factor", type=float, default=0.60,
                       help="LR reduction factor during stress-probe (ChatGPT: 0.6)")
    parser.add_argument("--stress_probe_exit_entropy", type=float, default=0.55,
                       help="Exit when entropy > this for 2 consecutive evals")
    parser.add_argument("--stress_probe_exit_rep3", type=float, default=0.12,
                       help="Exit when REP-3 < this")
    parser.add_argument("--stress_probe_min_steps", type=int, default=100,
                       help="Minimum steps in stress-probe (ChatGPT: 100)")
    parser.add_argument("--stress_probe_max_steps", type=int, default=300,
                       help="Maximum steps in stress-probe (ChatGPT: 300)")
    parser.add_argument("--stress_probe_lr_restore_steps", type=int, default=50,
                       help="Steps to gradually restore LR after exit (ChatGPT: 50)")
    parser.add_argument("--force_stress_probe", action="store_true",
                       help="Force immediate stress-probe activation")

    # Logging
    parser.add_argument("--log_every", type=int, default=10,
                       help="Log every N steps")
    parser.add_argument("--quiet", action="store_true",
                       help="Quiet mode: only print Critical 5 (Loss, PPL, S/A, GC, Conf)")
    parser.add_argument("--enable_kosha_diagnostics", action="store_true",
                       help="Enable Sheath-State diagnostic output (Reality/Time axes, cognitive states)")
    parser.add_argument("--kosha_log_every", type=int, default=0,
                       help="Log Kosha diagnostics every N steps (0 = use log_every)")
    parser.add_argument("--lightweight_diagnostics", action="store_true", default=True,
                       help="Skip expensive gradient norm computation in diagnostics (default: True)")
    parser.add_argument("--full_diagnostics", action="store_true",
                       help="Enable full diagnostics with gradient norms (slower but more detailed)")
    parser.add_argument("--enable_kosha_steering", action="store_true",
                       help="Enable Kosha phase coupling steering (active intervention)")
    parser.add_argument("--kosha_steering_force", type=float, default=0.15,
                       help="Steering strength 0.0-1.0 (default: 0.15 = gentle nudge)")
    parser.add_argument("--kosha_steering_warmup", type=int, default=100,
                       help="Steps before steering activates (default: 100)")
    parser.add_argument("--kosha_steering_layer", type=int, default=9,
                       help="Layer for phase steering (9=O9_WITNESSES consciousness, default: 9)")

    # ==========================================================================
    # v2.2.1: Kosha Gyroscope - Homeostatic Self-Regulation Loss
    # Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md
    # ==========================================================================
    parser.add_argument("--enable_kosha_gyroscope", action="store_true",
                       help="Enable Kosha Gyroscope homeostatic self-regulation loss")
    # V9.8.7: Dynamic three-phase engagement
    parser.add_argument("--gyroscope_engage_ppl", type=float, default=50.0,
                       help="V9.8.7: Phase 2 - Auto-engage gyroscope with RELAXED settings when Val PPL < this")
    parser.add_argument("--gyroscope_active_ppl", type=float, default=30.0,
                       help="V9.8.7: Phase 3 - Switch to ACTIVE settings when Val PPL < this")
    parser.add_argument("--gyroscope_relaxed_ceiling_clamp", type=float, default=0.90,
                       help="V9.8.7: Relaxed phase ceiling clamp factor (gentle)")
    parser.add_argument("--gyroscope_relaxed_floor_push", type=float, default=0.30,
                       help="V9.8.7: Relaxed phase floor push factor (gentle)")
    parser.add_argument("--gyroscope_active_ceiling_clamp", type=float, default=0.65,
                       help="V9.8.7: Active phase ceiling clamp factor (firm)")
    parser.add_argument("--gyroscope_active_floor_push", type=float, default=0.75,
                       help="V9.8.7: Active phase floor push factor (firm)")
    # Dynamic Weight Scheduler (v2.2.1)
    parser.add_argument("--gyroscope_base_gain", type=float, default=0.15,
                       help="Base gain when PPL > ceiling (gentle observation)")
    parser.add_argument("--gyroscope_max_gain", type=float, default=3.0,
                       help="Max gain when PPL approaches target (strict enforcement)")
    parser.add_argument("--gyroscope_ppl_ceiling", type=float, default=100.0,
                       help="PPL above which gain stays at base")
    parser.add_argument("--gyroscope_target_ppl", type=float, default=30.0,
                       help="PPL at which gain reaches max (graduation threshold)")
    # Trap detection thresholds (v2.2.5: Golden Ratio φ)
    parser.add_argument("--gyroscope_trap_threshold", type=float, default=0.618,
                       help="Kosha activation above this is 'trapped' (Golden Ratio φ)")
    parser.add_argument("--gyroscope_gate_threshold", type=float, default=0.30,
                       help="Minimum activation for gate to be open")
    parser.add_argument("--gyroscope_balance_target", type=float, default=0.25,
                       help="Required opposite activation to avoid punishment")
    parser.add_argument("--gyroscope_gate_temperature", type=float, default=10.0,
                       help="Gate sigmoid temperature (higher = sharper)")
    # v2.3.0: Complete Harmonic Pentad - Floor and Ceiling for each Kosha
    # Mental: Sattvic Band 23.6% - 38.2%
    parser.add_argument("--gyroscope_floor_mental", type=float, default=0.236,
                       help="v2.3.0: Mental floor (23.6%% Spark Abstraction)")
    parser.add_argument("--gyroscope_ceiling_mental", type=float, default=0.382,
                       help="v2.3.0: Mental ceiling (38.2%% Bliss Damper/Rip)")
    # Physical: Sattvic Band 38.2% - 61.8%
    parser.add_argument("--gyroscope_floor_physical", type=float, default=0.382,
                       help="v2.3.0: Physical floor (38.2%% Grounding Push)")
    parser.add_argument("--gyroscope_ceiling_physical", type=float, default=0.618,
                       help="v2.3.0: Physical ceiling (61.8%% Data Trap)")
    # Intellect: Sattvic Band 25.0% - 61.8%
    parser.add_argument("--gyroscope_floor_intellect", type=float, default=0.250,
                       help="v2.3.0: Intellect floor (25.0%% Logic Pressure)")
    parser.add_argument("--gyroscope_ceiling_intellect", type=float, default=0.618,
                       help="v2.3.0: Intellect ceiling (61.8%% Hubris Tax)")
    # Vital: Sattvic Band 23.6% - 78.6%
    parser.add_argument("--gyroscope_floor_vital", type=float, default=0.236,
                       help="v2.3.0: Vital floor (23.6%% Wake-up Boost)")
    parser.add_argument("--gyroscope_ceiling_vital", type=float, default=0.786,
                       help="v2.3.0: Vital ceiling (78.6%% Momentum Brake)")
    # Bliss: Sattvic Band 23.6% - 61.8%
    parser.add_argument("--gyroscope_floor_bliss", type=float, default=0.236,
                       help="v2.3.0: Bliss floor (23.6%% Spark Creativity)")
    parser.add_argument("--gyroscope_ceiling_bliss", type=float, default=0.618,
                       help="v2.3.0: Bliss ceiling (61.8%% Delusion Tether)")
    # Correction factors
    parser.add_argument("--gyroscope_floor_push_factor", type=float, default=0.5,
                       help="v2.3.0: Loss weight for floor violations (push toward Sattvic)")
    parser.add_argument("--gyroscope_ceiling_clamp_factor", type=float, default=0.5,
                       help="v2.3.0: Gain reduction for ceiling violations (clamp toward Sattvic)")
    # v2.3.2: Reflexive Domain Morph
    parser.add_argument("--gyroscope_domain_morph_enabled", action="store_true", default=True,
                       help="v2.3.2: Enable reflexive domain morphing (token heuristics + Kosha state)")
    parser.add_argument("--disable_gyroscope_domain_morph", action="store_true",
                       help="v2.3.2: Disable reflexive domain morphing")
    parser.add_argument("--gyroscope_domain_morph_ema_decay", type=float, default=0.9,
                       help="v2.3.2: EMA decay for token heuristics (0.9 = slow, 0.5 = fast)")
    parser.add_argument("--gyroscope_domain_morph_internal_weight", type=float, default=0.5,
                       help="v2.3.2: Weight for internal (Kosha state) signal")
    parser.add_argument("--gyroscope_domain_morph_external_weight", type=float, default=0.5,
                       help="v2.3.2: Weight for external (token heuristics) signal")
    # v2.2.4: Three-Stage Hybrid Logic (Damping + Gate + Rip)
    parser.add_argument("--gyroscope_damper_steepness", type=float, default=5.0,
                       help="v2.2.4: Sigmoid steepness for Bliss/Physical damper")
    parser.add_argument("--gyroscope_gate_steepness", type=float, default=5.0,
                       help="v2.2.4: Sigmoid steepness for Physical/Mental gate")
    parser.add_argument("--gyroscope_rip_multiplier", type=float, default=2.0,
                       help="v2.2.4: Multiplier for Reality Rip signal (circuit breaker strength)")
    # Legacy: steepness (deprecated in v2.2.4)
    parser.add_argument("--gyroscope_steepness", type=float, default=5.0,
                       help="[DEPRECATED] Use damper_steepness/gate_steepness instead")
    # Refinements
    parser.add_argument("--gyroscope_temporal_window", type=int, default=3,
                       help="Physical history window size for temporal grounding")
    parser.add_argument("--gyroscope_vital_momentum", action="store_true", default=True,
                       help="Enable dynamic gain via Vital (Pranamaya) energy")
    parser.add_argument("--disable_gyroscope_vital_momentum", action="store_true",
                       help="Disable Vital momentum for gyroscope")
    parser.add_argument("--gyroscope_warmup_steps", type=int, default=100,
                       help="Steps before gyroscope fully active")
    parser.add_argument("--kosha_rampdown_steps", type=int, default=500,
                       help="Steps to ramp gain to 0 at graduation")
    # V9.8.6: Three-Phase Kosha Curriculum
    parser.add_argument("--kosha_engage_ppl", type=float, default=100.0,
                       help="Kosha fully ON above this PPL (construction phase)")
    parser.add_argument("--kosha_disengage_ppl", type=float, default=30.0,
                       help="Kosha OFF below this PPL (polishing phase)")
    # Graduation criteria (legacy - kept for stability check)
    parser.add_argument("--gyroscope_graduation_ppl", type=float, default=30.0,
                       help="PPL threshold for graduation (mean)")
    parser.add_argument("--gyroscope_graduation_variance", type=float, default=1.5,
                       help="Max PPL variance for stability check")
    parser.add_argument("--gyroscope_graduation_window", type=int, default=10,
                       help="Window for graduation stability check")
    # Diagnostic logging
    parser.add_argument("--enable_rip_logger", action="store_true",
                       help="Enable Reality Rip diagnostic logging")
    parser.add_argument("--rip_logger_dir", type=str, default="diagnostics/rips",
                       help="Directory for rip event files")

    # v2.3.3: 32D Sovereign State Regularizer
    parser.add_argument("--enable_state_regularizer", action="store_true",
                       help="Enable 32D Sovereign State anti-saturation regularizer")
    parser.add_argument("--state_reg_anti_sat_weight", type=float, default=0.5,
                       help="Weight for anti-saturation loss (prevents VIT/BLI → 100%%)")
    parser.add_argument("--state_reg_variance_weight", type=float, default=0.2,
                       help="Weight for VICReg variance maintenance")
    parser.add_argument("--state_reg_sat_thresh_high", type=float, default=0.95,
                       help="Penalize activations above this threshold")
    parser.add_argument("--state_reg_sat_thresh_low", type=float, default=0.05,
                       help="Penalize activations below this threshold")
    parser.add_argument("--state_reg_target_std_kosha", type=float, default=0.15,
                       help="Target std for Kosha dimensions")
    parser.add_argument("--state_reg_vital_weight", type=float, default=1.5,
                       help="Extra penalty multiplier for VITAL dimension")
    parser.add_argument("--state_reg_bliss_weight", type=float, default=1.5,
                       help="Extra penalty multiplier for BLISS dimension")

    # V9.7.0: Ontological Bridge (Layer 4 - Foundational Structure)
    parser.add_argument("--enable_onto_bridge", action="store_true",
                       help="Enable 12D ontological projection at Layer 4 (foundational grounding)")
    parser.add_argument("--onto_bridge_lambda", type=float, default=0.1,
                       help="Weight for ontological bridge loss (default: 0.1)")
    parser.add_argument("--onto_bridge_diversity", type=float, default=0.1,
                       help="Weight for diversity component - prevents dimension collapse (default: 0.1)")
    parser.add_argument("--onto_bridge_pramana", type=float, default=0.1,
                       help="Weight for Pramāṇa alignment - truth prioritization (default: 0.1)")
    parser.add_argument("--onto_bridge_layer", type=int, default=4,
                       help="Layer for ontological bridge (4=foundational structure, default: 4)")
    # V9.8.6: Three-Phase Onto Bridge Curriculum
    parser.add_argument("--onto_engage_ppl", type=float, default=150.0,
                       help="Onto fully ON above this PPL (construction phase)")
    parser.add_argument("--onto_disengage_ppl", type=float, default=50.0,
                       help="Onto OFF below this PPL (polishing phase)")
    parser.add_argument("--onto_rampdown_steps", type=int, default=500,
                       help="Steps to ramp onto loss to 0 after disengage")
    parser.add_argument("--eval_every", type=int, default=100,
                       help="Evaluate every N steps")
    parser.add_argument("--phase_health_interval", type=int, default=500,
                       help="Log phase health diagnostics every N steps (default: 500)")
    parser.add_argument("--save_every", type=int, default=1000,
                       help="Save checkpoint every N steps")
    parser.add_argument("--no_save", action="store_true",
                       help="Skip all checkpoint saving (useful for benchmark runs with limited disk)")
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints_unified",
                       help="Checkpoint directory")

    # Other
    parser.add_argument("--no_coherence_loss", action="store_true",
                       help="Disable coherence loss")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")

    # Resume
    parser.add_argument("--resume", type=str, default="",
                       help="Path to checkpoint to resume from")
    parser.add_argument("--resume_weights_only", action="store_true",
                       help="Only load model weights, reset optimizer")

    # PIDv2 Controller (V9.4.4)
    parser.add_argument("--controller", type=str, default="none",
                       choices=["none", "pidv2", "emergency_pd"],
                       help="Authority controller: none, pidv2, emergency_pd")
    parser.add_argument("--pidv2_kp_min", type=float, default=0.10,
                       help="PIDv2 minimum Kp (when noisy)")
    parser.add_argument("--pidv2_kp_max", type=float, default=0.30,
                       help="PIDv2 maximum Kp (when clean)")
    parser.add_argument("--pidv2_kp_sensitivity", type=float, default=5.0,
                       help="PIDv2 volatility sensitivity")
    parser.add_argument("--pidv2_ki", type=float, default=0.02,
                       help="PIDv2 integral gain")
    parser.add_argument("--pidv2_kd", type=float, default=0.10,
                       help="PIDv2 derivative gain")
    parser.add_argument("--pidv2_a_min", type=float, default=0.40,
                       help="PIDv2 minimum authority factor (sensory floor)")
    parser.add_argument("--pidv2_c_floor", type=float, default=0.45,
                       help="PIDv2 coherence floor - below this, gate is at minimum (0.5). V9.8.6: Relaxed for Phase 1")
    parser.add_argument("--pidv2_c_good", type=float, default=0.65,
                       help="PIDv2 coherence good - above this, gate is at full (1.0). V9.8.6: Auto-disable PID at 0.75")
    parser.add_argument("--pidv2_w_s", type=float, default=0.30,
                       help="Semantic weight (0.30 = 30%% prompt-based)")
    # V9.7.0: PIDv2 Dynamic Batch Sizing
    parser.add_argument("--pidv2_batch_resize", action="store_true",
                       help="Enable PPL-driven batch resizing in PIDv2")
    parser.add_argument("--pidv2_batch_min", type=int, default=4,
                       help="Minimum batch size for PIDv2 resize")
    parser.add_argument("--pidv2_batch_max", type=int, default=64,
                       help="Maximum batch size for PIDv2 resize")
    parser.add_argument("--pidv2_batch_velocity_threshold", type=float, default=5.0,
                       help="PPL velocity %% to trigger batch reduction")
    parser.add_argument("--pidv2_batch_stable_streak", type=int, default=5,
                       help="Consecutive stable evals before batch increase")
    # V9.8.7: Three-phase PID engagement
    parser.add_argument("--pidv2_engage_ppl", type=float, default=100.0,
                       help="PID turns ON when Val PPL > this (construction phase)")
    parser.add_argument("--pidv2_disengage_ppl", type=float, default=30.0,
                       help="PID turns OFF when Val PPL < this (polishing phase)")
    parser.add_argument("--pidv2_rampdown_steps", type=int, default=500,
                       help="Steps to ramp down PID after disengagement")
    parser.add_argument("--no_pidv2_engagement", action="store_true",
                       help="Disable dynamic PID engagement (PID behavior unchanged)")
    parser.add_argument("--phase_ramp_steps", type=int, default=7000,
                       help="Steps for phase LR ramp (handshake dampening)")
    parser.add_argument("--tensorboard", action="store_true", default=True,
                       help="Enable TensorBoard logging")
    parser.add_argument("--no_tensorboard", action="store_true",
                       help="Disable TensorBoard logging")

    # Quality Sampling
    parser.add_argument("--sample_every", type=int, default=50,
                       help="Generate quality samples every N steps (0 = disabled)")

    # Knowledge Probes (factual accuracy, slot retrieval, phase coherence)
    parser.add_argument("--knowledge_probe_every", type=int, default=0,
                       help="Run knowledge probes every N steps (0 = disabled). "
                            "Measures factual accuracy, slot retrieval precision, "
                            "and phase coherence — signals orthogonal to PPL.")
    parser.add_argument("--knowledge_probe_top_k", type=int, default=10,
                       help="Top-K predictions to check for factual probes")
    parser.add_argument("--knowledge_probe_coherence_tokens", type=int, default=256,
                       help="Max tokens to generate for coherence measurement")
    parser.add_argument("--knowledge_probe_chunk_size", type=int, default=64,
                       help="Chunk size for coherence similarity measurement")

    # LRA Validation (Long-Range Retrieval)
    parser.add_argument("--lra_validate_every", type=int, default=0,
                       help="Run LRA validation every N steps (0 = disabled)")
    parser.add_argument("--lra_haystack_lengths", type=str, default="256,512,1024",
                       help="Comma-separated haystack lengths for LRA tests")
    parser.add_argument("--lra_num_samples", type=int, default=50,
                       help="Number of samples per LRA test")

    # Formula [1331]: 9:3 Hierarchical Split
    parser.add_argument("--use_9_3_split", action="store_true",
                       help="Enable 9:3 Authority/Sensory gradient scaling")
    parser.add_argument("--enable_gradient_scaling", action="store_true",
                       help="Enable gradient scaling for ANY split (use with --authority_layers and --sensory_layers)")
    parser.add_argument("--authority_layers", type=int, default=9,
                       help="Number of Authority (State-Delta) layers")
    parser.add_argument("--sensory_layers", type=int, default=3,
                       help="Number of Sensory (Quadratic) layers")
    parser.add_argument("--alpha_sens_initial", type=float, default=0.05,
                       help="Initial sensory gradient scale (balanced start to prevent S/A spikes)")
    parser.add_argument("--alpha_sens_max", type=float, default=0.7,
                       help="Maximum sensory gradient scale (after warmup/relaxation)")
    parser.add_argument("--gradient_warmup_steps", type=int, default=500,
                       help="Steps to ramp sensory gradient scale from initial to max")
    # V9.6.8: Layer-wise alpha dampening (Gemini recommendation)
    parser.add_argument("--enable_layerwise_alpha", action="store_true", default=True,
                       help="Enable per-layer alpha scaling (output layers more stable)")
    parser.add_argument("--disable_layerwise_alpha", action="store_true",
                       help="Disable per-layer alpha scaling")
    parser.add_argument("--alpha_output_scale", type=float, default=0.5,
                       help="Scale for output layers 9-11 (default 0.5 = more stable)")
    parser.add_argument("--alpha_reasoning_scale", type=float, default=1.0,
                       help="Scale for reasoning layers 6-8 (default 1.0 = more expressive)")
    parser.add_argument("--authority_floor", type=float, default=1.0,
                       help="Alpha floor for authority layers (1.0 = full gradients, 0.3 = dampen to 30%%)")

    # Dynamic Relaxation: 9:3 → 6:6 transition
    parser.add_argument("--enable_dynamic_relaxation", action="store_true", default=True,
                       help="Enable automatic 9:3 → 6:6 split transition (default: enabled)")
    parser.add_argument("--disable_dynamic_relaxation", action="store_true",
                       help="Disable automatic 9:3 → 6:6 split transition")
    parser.add_argument("--relaxation_mode", type=str, default="sa_ratio",
                       choices=["consecutive", "average", "sa_ratio"],
                       help="Trigger mode: 'sa_ratio' (S/A ratio, recommended), 'average' (SSI rolling mean), 'consecutive' (SSI streak)")
    parser.add_argument("--relaxation_stability_threshold", type=float, default=0.50,
                       help="S/A ratio threshold to trigger 9:3 → 6:6 relaxation")
    parser.add_argument("--relaxation_stability_window", type=int, default=500,
                       help="Rolling window size for stability check")
    parser.add_argument("--relaxation_streak_target", type=int, default=5,
                       help="Consecutive stable evals for 'consecutive' mode")
    parser.add_argument("--force_relaxation_step", type=int, default=None,
                       help="Force 9:3→6:6 swap at this step (bypasses stability check)")
    # Sovereign Saturation Gate
    parser.add_argument("--enable_saturation_gate", action="store_true", default=True,
                       help="Enable automatic saturation detection for 9:3→6:6 transition")
    parser.add_argument("--disable_saturation_gate", action="store_true",
                       help="Disable automatic saturation gate")
    parser.add_argument("--saturation_coherence_threshold", type=float, default=0.74,
                       help="Coherence threshold for saturation gate trigger")
    parser.add_argument("--saturation_patience", type=int, default=50,
                       help="Steps where sensory derivative must be flat to trigger")
    parser.add_argument("--saturation_thaw_start", type=float, default=0.3,
                       help="Starting α for new sensory layers during Dampened Thaw")
    parser.add_argument("--saturation_thaw_end", type=float, default=0.7,
                       help="Ending α for new sensory layers during Dampened Thaw")
    parser.add_argument("--saturation_thaw_steps", type=int, default=100,
                       help="Steps to ramp new sensory layers from start to end α")
    parser.add_argument("--relaxation_target_authority", type=int, default=6,
                       help="Target authority layers after relaxation")
    parser.add_argument("--relaxation_target_sensory", type=int, default=6,
                       help="Target sensory layers after relaxation")
    parser.add_argument("--relaxation_thaw_alpha", type=float, default=0.05,
                       help="Dampened Thaw starting α for new sensory layers")
    parser.add_argument("--relaxation_thaw_steps", type=int, default=500,
                       help="Steps to ramp new sensory layers during Dampened Thaw")
    parser.add_argument("--relaxation_ppl_spike_threshold", type=float, default=0.20,
                       help="PPL increase %% to trigger Viparyaya recovery")
    parser.add_argument("--relaxation_recovery_steps", type=int, default=100,
                       help="Steps to stay in Viparyaya recovery before resuming")

    # Weight Transfer (9:3 → 6:6 transition)
    parser.add_argument("--enable_weight_transfer", action="store_true", default=True,
                       help="Enable weight transfer from Authority to Sensory layers during relaxation")
    parser.add_argument("--disable_weight_transfer", action="store_true",
                       help="Disable weight transfer (overrides --enable_weight_transfer)")
    parser.add_argument("--guna_lock_steps", type=int, default=50,
                       help="Steps to freeze W_q/W_k after relaxation (Guna-Lock)")

    # Toroidal Evolutionary Bridge (O12 → O1 Recursive Intelligence)
    parser.add_argument("--enable_toroidal_bridge", action="store_true",
                       help="Enable O12→O1 state carryover for recursive intelligence")
    parser.add_argument("--toroidal_lambda", type=float, default=0.1,
                       help="Weight for toroidal consistency loss")
    parser.add_argument("--toroidal_dropout", type=float, default=0.1,
                       help="Dropout in seed projection")
    parser.add_argument("--toroidal_use_gating", action="store_true", default=True,
                       help="Use gated projection for selective carryover")
    parser.add_argument("--toroidal_truncated_bptt", type=int, default=0,
                       help="Steps of gradient flow (0 = full detach)")
    parser.add_argument("--toroidal_coherence_threshold", type=float, default=0.3,
                       help="Alarm threshold for cognitive discontinuity")

    # Full Evolutionary Flow System (Phase 2-5)
    parser.add_argument("--enable_evolutionary_flow", action="store_true", default=False,
                       help="Enable full evolutionary flow across all layer transitions")
    parser.add_argument("--disable_evolutionary_flow", action="store_true",
                       help="Disable evolutionary flow system")
    parser.add_argument("--evo_lambda", type=float, default=0.1,
                       help="Overall evolutionary loss weight")
    parser.add_argument("--evo_micro_weight", type=float, default=0.3,
                       help="Weight for per-gate coherence loss")
    parser.add_argument("--evo_meso_weight", type=float, default=0.3,
                       help="Weight for cluster coherence loss (Auth/Sens)")
    parser.add_argument("--evo_macro_weight", type=float, default=0.4,
                       help="Weight for toroidal coherence loss")
    parser.add_argument("--evo_dropout", type=float, default=0.1,
                       help="Dropout in evolutionary gates")
    parser.add_argument("--evo_use_rmatrix", action="store_true", default=True,
                       help="Use R-Matrix for evolutionary weights")
    parser.add_argument("--evo_coherence_window", type=int, default=100,
                       help="Steps for coherence history tracking")
    parser.add_argument("--evo_resonance_alpha", type=float, default=0.1,
                       help="Strength of O12→O1 delayed resonance injection")
    parser.add_argument("--evo_lr_modulation", action="store_true", default=True,
                       help="Enable metacognitive LR adjustment")
    parser.add_argument("--evo_lr_slowdown", type=float, default=0.5,
                       help="LR multiplier when SLOW_DOWN/BRAKE")
    parser.add_argument("--evo_lr_accelerate", type=float, default=1.2,
                       help="LR multiplier when ACCELERATE")
    # V9.7.0: EvoFlow Fluency Gate
    parser.add_argument("--evo_fluency_gate", action="store_true",
                       help="Enable automatic EvoFlow gradient engagement when fluent")
    parser.add_argument("--evo_fluency_min_steps", type=int, default=2000,
                       help="Minimum steps before EvoFlow engagement (warmup)")
    parser.add_argument("--evo_fluency_ppl_threshold", type=float, default=100.0,
                       help="PPL threshold for 'fluent' - engage EvoFlow when PPL < this")

    # V9.8.0: RSS (Rational Sovereign Sequence) - Staged gradient engagement
    parser.add_argument("--enable_rss", action="store_true",
                       help="Enable RSS phase controller for staged gradient engagement")
    parser.add_argument("--rss_evoflow_ppl", type=float, default=100.0,
                       help="PPL threshold for EvoFlow engagement")
    parser.add_argument("--rss_toroidal_ppl", type=float, default=60.0,
                       help="PPL threshold for Toroidal engagement")
    parser.add_argument("--rss_csr_ppl", type=float, default=45.0,
                       help="PPL threshold for CSR engagement (with warmup)")
    parser.add_argument("--rss_kosha_ppl", type=float, default=35.0,
                       help="PPL threshold for Kosha engagement (after CSR settles)")
    parser.add_argument("--rss_csr_warmup_steps", type=int, default=2500,
                       help="Steps for CSR to reach full strength (prevents 14x shock)")
    parser.add_argument("--rss_use_val_ppl", action="store_true", default=True,
                       help="Use validation PPL for RSS thresholds (more stable)")

    # PPL-Gated Curriculum Learning - Phased auxiliary loss introduction
    parser.add_argument("--enable_curriculum", action="store_true",
                       help="Enable PPL-gated curriculum learning (phases: FOUNDATION→REGULARIZATION→GROUNDING→SOVEREIGN)")
    parser.add_argument("--curriculum_ppl_regularization", type=float, default=30.0,
                       help="PPL threshold to enter REGULARIZATION phase (light bhava/coherence)")
    parser.add_argument("--curriculum_ppl_grounding", type=float, default=15.0,
                       help="PPL threshold to enter GROUNDING phase (CSR + Bridge + JEPA)")
    parser.add_argument("--curriculum_ppl_sovereign", type=float, default=10.0,
                       help="PPL threshold to enter SOVEREIGN phase (full auxiliary stack)")
    parser.add_argument("--curriculum_stability_window", type=int, default=5,
                       help="Consecutive evals below threshold before phase transition")
    parser.add_argument("--curriculum_hysteresis", type=float, default=1.5,
                       help="PPL must exceed threshold * hysteresis to regress to earlier phase")

    # V2.3.4: Sequence Length Curriculum
    parser.add_argument("--enable_seq_curriculum", action="store_true",
                       help="Enable sequence length ramping (start short, ramp to full length)")
    parser.add_argument("--seq_len_start", type=int, default=256,
                       help="Starting sequence length for curriculum")
    parser.add_argument("--seq_len_end", type=int, default=1024,
                       help="Target sequence length (0 = use max_seq_len)")
    parser.add_argument("--seq_len_ramp_steps", type=int, default=5000,
                       help="Steps to ramp from start to end length")
    parser.add_argument("--seq_len_ramp_mode", type=str, default="linear",
                       choices=["linear", "exponential"],
                       help="Ramping mode: linear or exponential")
    parser.add_argument("--seq_len_ppl_gate", type=float, default=0.0,
                       help="Only ramp when PPL < this (0 = step-based only)")

    # CSR Phoneme-Ontological Grounding
    parser.add_argument("--enable_csr", action="store_true", default=False,
                       help="Enable CSR phoneme grounding")
    parser.add_argument("--disable_csr", action="store_true",
                       help="Disable CSR phoneme grounding")
    parser.add_argument("--csr_lambda", type=float, default=0.1,
                       help="CSR injection strength")
    parser.add_argument("--csr_tau", type=float, default=0.07,
                       help="InfoNCE temperature for CSR alignment (lower = sharper gradients)")
    parser.add_argument("--csr_use_phase_gating", action="store_true", default=True,
                       help="Gate Phase Attention with CSR confidence")
    parser.add_argument("--csr_trainable", action="store_true", default=True,
                       help="Allow CSR projection to train")

    # V9.6.0: Embedding configuration
    parser.add_argument("--untie_embeddings", action="store_true",
                       help="Untie input/output embeddings (CRITICAL when using CSR to prevent vocabulary corruption)")
    parser.add_argument("--csr_use_entropy_sink", action="store_true", default=True,
                       help="Apply Layer 0 entropy floor")
    parser.add_argument("--csr_use_synthesis_gate", action="store_true", default=True,
                       help="Apply Layer 11 synthesis reconciliation")
    parser.add_argument("--csr_alignment_layer", type=int, default=7,
                       help="Which layer to use for CSR alignment (7=concept consolidation, 2=early concept, 11=output - AVOID)")
    # V9.6.8: CSR Projector LR Scale (Gemini recommendation)
    parser.add_argument("--csr_projector_lr_scale", type=float, default=0.1,
                       help="CSR projector learns at this fraction of main LR (0.1 = 10x slower)")
    # V9.6.8: CSR Gradient Warmup (Gemini recommendation)
    parser.add_argument("--csr_gradient_warmup_steps", type=int, default=0,
                       help="Steps before re-enabling CSR gradients (0=always detached, 1000=re-enable after 1000 steps)")
    # V9.7.0: CSR Sparse Delayed Supervision (Whole Word Alignment)
    parser.add_argument("--csr_sparse_supervision", action="store_true",
                       help="Enable word-boundary-only supervision (fixes 'word salad' problem)")
    parser.add_argument("--csr_content_word_only", action="store_true",
                       help="Only apply CSR to content words, skip stopwords (requires --csr_sparse_supervision)")
    # V9.8.6: CSR Three-Phase Curriculum
    parser.add_argument("--csr_engage_ppl", type=float, default=120.0,
                       help="CSR fully ON above this PPL (construction phase)")
    parser.add_argument("--csr_disengage_ppl", type=float, default=40.0,
                       help="CSR OFF below this PPL (polishing phase)")
    parser.add_argument("--csr_rampdown_steps", type=int, default=500,
                       help="Steps to ramp down CSR after disengage trigger")

    # Appendix G Phase 3: Bliss Gating (adaptive λ_eff for CSR)
    parser.add_argument("--enable_bliss_gating", action="store_true",
                       help="Phase 3: Bliss modulates csr_lambda via sigmoid gate σ(γ·(B−τ))")
    parser.add_argument("--bliss_gate_gamma", type=float, default=5.0,
                       help="Bliss gate sharpness (higher = sharper transition)")
    parser.add_argument("--bliss_gate_lambda_min", type=float, default=0.1,
                       help="Floor: λ_eff never drops below this fraction of λ_base")
    parser.add_argument("--bliss_gate_warmup_steps", type=int, default=1000,
                       help="Steps before Bliss gating activates (full λ during warmup)")

    # Appendix G Phase 4: JEPA Injection (CSR + Bliss + JEPA multi-prior)
    parser.add_argument("--enable_jepa_injection", action="store_true",
                       help="Phase 4: Enable JEPA state delta as weak prior alongside CSR")
    parser.add_argument("--jepa_injection_lambda", type=float, default=0.03,
                       help="Base JEPA injection strength λ_JEPA (Appendix G.3.4 default)")
    parser.add_argument("--jepa_injection_layer", type=int, default=3,
                       help="Layer index to inject JEPA prior (2-3 = concept formation)")
    parser.add_argument("--jepa_injection_projector_lr_scale", type=float, default=0.1,
                       help="LR scale for JEPA 32D→d_model projector (slow learning)")

    # SGP (Stochastic Gradient Persistence) - "Cement" for CSR structure
    # V9.6.8: Updated defaults per Gemini recommendation (stronger cement, less frequent)
    parser.add_argument("--enable_sgp", action="store_true", default=False,
                       help="Enable SGP synchronized with Sattvic Controller (requires CSR)")
    parser.add_argument("--disable_sgp", action="store_true",
                       help="Disable SGP")
    parser.add_argument("--sgp_base_rate", type=int, default=200,
                       help="SGP base rate (Toroidal Refresh Rate) - every N steps")
    parser.add_argument("--sgp_stagnation_rate", type=int, default=100,
                       help="SGP rate when stagnation detected (halved from base)")
    parser.add_argument("--sgp_gamma", type=float, default=0.5,
                       help="SGP persistence coefficient (gamma) - was 0.3, now 0.5 per Gemini (stronger cement)")

    # Sattvic Controller (Dynamic λ_csr regulation)
    parser.add_argument("--sattvic_initial_lambda", type=float, default=0.5,
                       help="Initial λ_csr during warmup")
    parser.add_argument("--sattvic_floor_lambda", type=float, default=0.1,
                       help="Minimum λ_csr after decay")
    parser.add_argument("--sattvic_warmup_steps", type=int, default=500,
                       help="Steps for warmup phase")
    parser.add_argument("--sattvic_variance_window", type=int, default=50,
                       help="Window for entropy variance detection")
    parser.add_argument("--sattvic_variance_threshold", type=float, default=0.00001,
                       help="Variance threshold for stagnation (lowered to 1e-5)")

    # Adaptive Training Controller (dynamic hyperparameter tuning)
    parser.add_argument("--enable_adaptive_training", action="store_true", default=True,
                       help="Enable automatic LR/Kp adjustment based on training dynamics")
    parser.add_argument("--disable_adaptive_training", action="store_true",
                       help="Disable adaptive training controller")
    parser.add_argument("--adaptive_lr_min", type=float, default=1e-5,
                       help="Minimum learning rate floor for adaptive adjustment")
    parser.add_argument("--adaptive_lr_max", type=float, default=1e-3,
                       help="Maximum learning rate ceiling for adaptive adjustment")
    parser.add_argument("--adaptive_lr_boost", type=float, default=1.5,
                       help="LR boost multiplier when plateau or slow learning detected")
    parser.add_argument("--adaptive_lr_decay", type=float, default=0.7,
                       help="LR decay multiplier when PPL spike detected")
    parser.add_argument("--adaptive_velocity_slow", type=float, default=-2.0,
                       help="PPL velocity threshold (%%) for 'too slow' detection")
    parser.add_argument("--adaptive_velocity_spike", type=float, default=10.0,
                       help="PPL velocity threshold (%%) for 'spike' detection")
    parser.add_argument("--adaptive_plateau_window", type=int, default=5,
                       help="Number of evaluations to check for plateau")
    parser.add_argument("--adaptive_plateau_threshold", type=float, default=1.0,
                       help="Minimum improvement (%%) to avoid plateau detection")
    parser.add_argument("--adaptive_min_interval", type=int, default=200,
                       help="Minimum steps between adaptive adjustments")
    # V9.8.2: Safeguards to prevent runaway LR
    parser.add_argument("--adaptive_max_lr_relative", type=float, default=10.0,
                       help="Max LR multiplier relative to base_lr (prevents runaway)")
    parser.add_argument("--adaptive_loss_spike_threshold", type=float, default=5.0,
                       help="Loss increase %% that triggers emergency LR decay")
    parser.add_argument("--adaptive_grad_norm_spike", type=float, default=100.0,
                       help="Gradient norm above this triggers emergency decay")
    parser.add_argument("--adaptive_emergency_decay", type=float, default=0.5,
                       help="Aggressive LR decay factor for emergencies")
    parser.add_argument("--adaptive_consecutive_spike_limit", type=int, default=3,
                       help="After N consecutive loss spikes, block LR boosts")
    parser.add_argument("--adaptive_max_boost_from_base", type=float, default=2.0,
                       help="Max LR = base_lr * this (caps compounding boosts)")
    parser.add_argument("--adaptive_boost_cooldown_steps", type=int, default=400,
                       help="Minimum steps between consecutive LR boosts")

    # Auto Batch Sizing (VRAM-based startup probing)
    parser.add_argument("--enable_auto_batch", action="store_true",
                       help="Enable automatic batch size detection at startup based on VRAM")
    parser.add_argument("--auto_batch_target_utilization", type=float, default=0.80,
                       help="Target VRAM utilization for auto batch sizing (0.80 = 80%%)")
    parser.add_argument("--auto_batch_safety_margin", type=float, default=0.05,
                       help="Extra VRAM headroom below target (0.05 = 5%%)")
    parser.add_argument("--auto_batch_target_effective", type=int, default=0,
                       help="Target effective batch size (0 = just find max batch, no accumulation)")

    # Friction Controller (V9.4.5)
    parser.add_argument("--disable_friction", action="store_true",
                       help="Disable friction controller (allows high dominance ratios)")
    parser.add_argument("--friction_dom_high", type=float, default=3.0,
                       help="Friction dominance 'riot' threshold (default 3.0, set higher to allow Sanskrit dominance)")
    parser.add_argument("--friction_dom_low", type=float, default=0.3,
                       help="Friction dominance 'lock' threshold (default 0.3)")
    parser.add_argument("--friction_align_critical", type=float, default=-0.10,
                       help="Friction alignment critical threshold (default -0.10)")

    # ==========================================================================
    # V9.8.0: Sovereign Reasoning Kernel (SRK)
    # Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md
    # ==========================================================================
    parser.add_argument("--enable_srk", action="store_true",
                       help="Enable Sovereign Reasoning Kernel (replaces scattered ontological flags)")
    parser.add_argument("--srk_hidden_dim", type=int, default=768,
                       help="Hidden dimension for SRK projections")
    parser.add_argument("--srk_dna_bridge_layer", type=int, default=4,
                       help="Layer for DNA Bridge (foundational ontology)")
    parser.add_argument("--srk_csr_alignment_layer", type=int, default=7,
                       help="Layer for CSR Alignment / Phase Extraction Hook")
    parser.add_argument("--srk_witness_layer", type=int, default=9,
                       help="Layer for Witness Arbitrator (consciousness)")
    parser.add_argument("--srk_synthesis_layer", type=int, default=11,
                       help="Layer for Synthesis Gate (output integration)")
    parser.add_argument("--srk_disable_dna_bridge", action="store_true",
                       help="Disable DNA Bridge at Layer 4")
    parser.add_argument("--srk_disable_witness", action="store_true",
                       help="Disable Witness Arbitrator at Layer 9")
    parser.add_argument("--srk_disable_synthesis", action="store_true",
                       help="Disable Synthesis Gate at Layer 11")
    parser.add_argument("--srk_disable_imr", action="store_true",
                       help="Disable Isomorphic Mapping Router")
    parser.add_argument("--srk_isomorphism_threshold", type=float, default=0.75,
                       help="Threshold for IMR template matching")
    parser.add_argument("--srk_karma_decay", type=float, default=0.9,
                       help="O12→O1 karma decay factor")
    parser.add_argument("--srk_disable_mauna", action="store_true",
                       help="Disable Mauna Protocol (inference safety)")
    parser.add_argument("--srk_mauna_confidence_threshold", type=float, default=0.6,
                       help="Minimum confidence for Mauna Protocol output")
    parser.add_argument("--srk_mauna_consistency_threshold", type=float, default=0.5,
                       help="Minimum backward score for Mauna Protocol")
    # SRK Loss (B1/U2/S8)
    parser.add_argument("--srk_lambda_f", type=float, default=1.0,
                       help="SRK forward score weight (linguistic coherence)")
    parser.add_argument("--srk_lambda_b", type=float, default=1.0,
                       help="SRK backward score weight (ontological alignment)")
    parser.add_argument("--srk_lambda_c", type=float, default=0.5,
                       help="SRK consistency divergence penalty (B1)")
    parser.add_argument("--srk_lambda_coherence", type=float, default=0.2,
                       help="SRK phase coherence weight (U2)")
    parser.add_argument("--srk_lambda_entropy", type=float, default=0.1,
                       help="SRK stability constraint weight (S8)")
    parser.add_argument("--srk_lambda_task", type=float, default=1.0,
                       help="SRK task loss weight (cross-entropy)")
    parser.add_argument("--srk_disable_nidra_penalty", action="store_true",
                       help="Disable VOID/dormancy penalty")
    parser.add_argument("--srk_nidra_penalty_weight", type=float, default=0.05,
                       help="VOID penalty weight")
    # SRK Annealing
    parser.add_argument("--srk_total_steps", type=int, default=50000,
                       help="Total training steps for SRK annealing")
    parser.add_argument("--srk_warmup_steps", type=int, default=5000,
                       help="Steps for System 1 warmup phase (Learn to Speak)")
    parser.add_argument("--srk_invert_annealing", action="store_true",
                       help="Invert SRK annealing: start STRONG, ramp DOWN (phase-first learning)")

    # ==========================================================================
    # V9.8.8: Sovereign Phase Controller (SPC)
    # Reference: docs/SOVEREIGN_PHASE_CONTROLLER_DESIGN.md
    # ==========================================================================
    parser.add_argument("--enable_sovereign_phase_controller", action="store_true",
                       help="Enable Sovereign Phase Controller (graduated, damped phase interventions)")
    parser.add_argument("--spc_entropy_critical", type=float, default=0.4,
                       help="SPC critical entropy threshold (red alert)")
    parser.add_argument("--spc_entropy_warning", type=float, default=0.5,
                       help="SPC warning entropy threshold (yellow alert)")
    parser.add_argument("--spc_entropy_recovered", type=float, default=0.55,
                       help="SPC recovered entropy threshold (exit boost - hysteresis)")
    parser.add_argument("--spc_variance_critical", type=float, default=0.0005,
                       help="SPC critical variance threshold (stagnation detection)")
    parser.add_argument("--spc_variance_warning", type=float, default=0.001,
                       help="SPC warning variance threshold")
    parser.add_argument("--spc_variance_recovered", type=float, default=0.002,
                       help="SPC recovered variance threshold (exit boost)")
    parser.add_argument("--spc_min_boost_duration", type=int, default=100,
                       help="Minimum steps to stay in boost mode (prevents oscillation)")
    parser.add_argument("--spc_alpha", type=float, default=0.2,
                       help="SPC EMA smoothing coefficient for rotation damping")
    parser.add_argument("--spc_max_rotation", type=float, default=0.3,
                       help="SPC maximum rotation per step in radians (~17 degrees)")
    parser.add_argument("--spc_damping", type=float, default=0.9,
                       help="SPC velocity damping coefficient")
    parser.add_argument("--spc_velocity_threshold", type=float, default=0.2,
                       help="SPC velocity threshold for applying damping")

    # ==========================================================================
    # V9.8.9: Dynamic Window Scheduler (DWS)
    # Reference: Curriculum learning for receptive field dimension
    # ==========================================================================
    parser.add_argument("--enable_dynamic_window", action="store_true",
                       help="Enable dynamic window sizing (PPL-adaptive attention span)")
    parser.add_argument("--dws_schedule", type=str, default=None,
                       help="Custom window schedule as 'ppl1:win1,ppl2:win2,...' (default: built-in smooth schedule)")
    parser.add_argument("--dws_growth_rate_max", type=float, default=1.25,
                       help="Maximum growth rate per transition (1.25 = 25%% max increase)")
    parser.add_argument("--dws_shrink_rate_max", type=float, default=0.80,
                       help="Maximum shrink rate per transition (0.80 = 20%% max decrease)")
    parser.add_argument("--dws_align_to", type=int, default=32,
                       help="Align windows to multiples (32 for GPU efficiency, 0 = no alignment)")
    parser.add_argument("--dws_smooth_steps", type=int, default=100,
                       help="Interpolate window transitions over N steps (prevents jumps)")
    parser.add_argument("--dws_min_steps_between", type=int, default=200,
                       help="Minimum steps between target changes (cooldown for stability)")
    parser.add_argument("--dws_hysteresis", type=float, default=0.15,
                       help="PPL hysteresis factor (15%% gap prevents thrashing)")
    parser.add_argument("--dws_vram_threshold", type=float, default=0.85,
                       help="VRAM threshold for emergency window shrink (85%%)")

    # ==========================================================================
    # Phase-JEPA: Joint Embedding Predictive Architecture
    # Reference: docs/design/HYBRID_PHASE_JEPA_DESIGN.md
    # ==========================================================================
    parser.add_argument("--enable_jepa", action="store_true",
                       help="Enable Phase-JEPA training (Sensor model for perception)")
    parser.add_argument("--jepa_hidden_dim", type=int, default=256,
                       help="Hidden dimension for JEPA predictor MLP")
    parser.add_argument("--jepa_prediction_steps", type=int, default=4,
                       help="Number of k-step lookahead predictions")
    parser.add_argument("--jepa_num_heads", type=int, default=4,
                       help="Number of attention heads in JEPA predictor")
    parser.add_argument("--jepa_cosine_mode", type=str, default="complex",
                       choices=["standard", "shifted", "complex"],
                       help="Phase attention cosine mode (complex preserves full phasor)")

    # JEPA Loss Weights
    parser.add_argument("--jepa_vicreg_weight", type=float, default=1.0,
                       help="VICReg loss weight (prevents representation collapse)")
    parser.add_argument("--jepa_alignment_weight", type=float, default=1.0,
                       help="Alignment loss weight (matches predictor to target)")
    parser.add_argument("--jepa_prediction_weight", type=float, default=0.5,
                       help="Prediction loss weight (forward/backward consistency)")
    parser.add_argument("--jepa_orthogonality_weight", type=float, default=0.01,
                       help="Orthogonality regularization weight")

    # JEPA Weighted Alignment (Per-Component)
    parser.add_argument("--jepa_bhava_weight", type=float, default=10.0,
                       help="Bhava (identity) component alignment weight")
    parser.add_argument("--jepa_semantic_weight", type=float, default=1.0,
                       help="Kosha/Vritti (semantic) component alignment weight")
    parser.add_argument("--jepa_guna_weight", type=float, default=0.1,
                       help="Guna (loosely coupled) component alignment weight")

    # JEPA Target Encoder (EMA)
    parser.add_argument("--jepa_target_momentum", type=float, default=0.996,
                       help="EMA momentum for target encoder (higher = slower update)")
    parser.add_argument("--jepa_momentum_schedule", type=str, default="cosine",
                       choices=["constant", "cosine", "linear"],
                       help="Momentum schedule (cosine anneals 0.996->1.0)")

    # JEPA Training Curriculum (Body→Soul→Union)
    parser.add_argument("--jepa_training_phase", type=str, default="body",
                       choices=["body", "soul", "union"],
                       help="Current training phase (body=JEPA, soul=SRK, union=joint)")
    parser.add_argument("--jepa_phase_body_steps", type=int, default=20000,
                       help="Steps for Body phase (JEPA perceptual learning)")
    parser.add_argument("--jepa_phase_soul_steps", type=int, default=30000,
                       help="Steps for Soul phase (SRK reasoning)")
    parser.add_argument("--jepa_auto_phase_transition", action="store_true",
                       help="Automatically transition phases based on step count")

    # JEPA Dynamic Graduation (metric-based phase transitions)
    parser.add_argument("--jepa_enable_dynamic_graduation", action="store_true", default=True,
                       help="Enable metric-based graduation (graduate when loss < threshold)")
    parser.add_argument("--jepa_graduation_loss_threshold", type=float, default=20.0,
                       help="Graduate to Soul phase when JEPA loss falls below this")
    parser.add_argument("--jepa_graduation_alignment_threshold", type=float, default=25.0,
                       help="Graduate to Soul phase when alignment rises above this (V9.6.8: was 72.0)")

    # JEPA Vritti Validation
    parser.add_argument("--jepa_enable_vritti_validation", action="store_true",
                       help="Enable Vritti gate validation (rejects error-prone predictions)")
    parser.add_argument("--jepa_viparyaya_threshold", type=float, default=0.4,
                       help="Max error (Viparyaya) before damping predictions")
    parser.add_argument("--jepa_vikalpa_threshold", type=float, default=0.6,
                       help="Max imagination (Vikalpa) for factual tasks")
    parser.add_argument("--jepa_damping_factor", type=float, default=0.5,
                       help="How much to dampen rejected predictions")

    # JEPA-SRK Integration (Master/Sensor)
    parser.add_argument("--jepa_enable_karma_injection", action="store_true",
                       help="Enable karma state injection from SRK (Master) to JEPA (Sensor)")
    parser.add_argument("--jepa_karma_gate_bias", type=float, default=0.5,
                       help="Initial gate bias for karma blending (0=internal, 1=external)")

    # V10.3.7: Vritti Entropy Regularization
    parser.add_argument("--vritti_entropy_reg", action="store_true",
                       help="Enable entropy regularization to prevent vritti collapse")
    parser.add_argument("--vritti_entropy_lambda", type=float, default=0.1,
                       help="Weight for vritti entropy regularization (higher = more balanced)")

    # BCVF Contrastive Structural Pressure on Representations
    parser.add_argument("--use_bcvf_contrastive", action="store_true",
                       help="Enable BCVF contrastive structural pressure on representations")
    parser.add_argument("--bcvf_contrastive_lambda", type=float, default=0.1,
                       help="Weight for contrastive representation loss L_rep")
    parser.add_argument("--bcvf_contrastive_K", type=int, default=16,
                       help="Number of negatives per sampled position")
    parser.add_argument("--bcvf_contrastive_K_pool", type=int, default=256,
                       help="Candidate pool size for Stage A negative sampling")
    parser.add_argument("--bcvf_contrastive_margin", type=float, default=0.15,
                       help="Margin for contrastive ranking loss")
    parser.add_argument("--bcvf_contrastive_alpha", type=float, default=2.0,
                       help="Temperature for BCVF-based negative weighting")
    parser.add_argument("--bcvf_contrastive_eta", type=float, default=0.3,
                       help="Token embedding injection scale for proxy r_neg")
    parser.add_argument("--bcvf_contrastive_d_r", type=int, default=128,
                       help="Projection output dimensionality")
    parser.add_argument("--bcvf_contrastive_T_sample", type=int, default=4,
                       help="Number of positions per sequence to sample for contrastive loss")
    parser.add_argument("--bcvf_contrastive_projector", type=str, default="mlp",
                       choices=["linear", "mlp"],
                       help="Projection head type for contrastive representations")

    # BCVF Logit-Margin + Entropy Band (perplexity-aligned)
    parser.add_argument("--use_logit_margin", action="store_true",
                       help="Enable logit-margin BCVF + entropy band (perplexity-aligned)")
    parser.add_argument("--logit_margin_lambda", type=float, default=0.05,
                       help="Weight for logit margin loss")
    parser.add_argument("--logit_margin_entropy_lambda", type=float, default=0.01,
                       help="Weight for entropy band loss")
    parser.add_argument("--logit_margin_m", type=float, default=0.7,
                       help="Minimum logit gap z_pos - z_neg")
    parser.add_argument("--logit_margin_H_min", type=float, default=1.5,
                       help="Entropy band lower bound")
    parser.add_argument("--logit_margin_H_max", type=float, default=4.0,
                       help="Entropy band upper bound")
    parser.add_argument("--logit_margin_top_k_neg", type=int, default=1,
                       help="Number of hard negatives to average (1 = hardest only)")

    # Kosha-Vritti Structured Supervision
    parser.add_argument("--enable_kv_supervision", action="store_true",
                       help="Enable Kosha-Vritti structured auxiliary supervision")
    parser.add_argument("--kv_weight_kosha_kl", type=float, default=0.1,
                       help="Weight for Kosha KL divergence loss")
    parser.add_argument("--kv_weight_vritti_kl", type=float, default=0.1,
                       help="Weight for Vritti KL divergence loss")
    parser.add_argument("--kv_weight_entropy_floor", type=float, default=0.01,
                       help="Weight for entropy floor anti-collapse penalty")
    parser.add_argument("--kv_weight_compatibility", type=float, default=0.05,
                       help="Weight for static joint compatibility loss")
    parser.add_argument("--kv_weight_prior", type=float, default=0.001,
                       help="Weight for W_kv prior regularization")
    parser.add_argument("--kv_entropy_floor_ratio", type=float, default=0.4,
                       help="Entropy floor = ratio * log(num_classes)")
    parser.add_argument("--kv_compatibility_prior_path", type=str, default="",
                       help="Path to W0 compatibility prior matrix")
    parser.add_argument("--kv_curriculum_exclude_epochs", type=int, default=2,
                       help="Epochs to exclude Viparyaya/Nidra samples")
    parser.add_argument("--kv_curriculum_ramp_epochs", type=int, default=1,
                       help="Epochs to linearly ramp Viparyaya/Nidra inclusion")
    parser.add_argument("--kv_teacher_mode", type=str, default="heuristic",
                       choices=["uniform", "heuristic"],
                       help="Teacher label generation mode")
    parser.add_argument("--kv_collapse_check_interval", type=int, default=100,
                       help="Steps between collapse detection checks")
    parser.add_argument("--kv_kl_clamp_max", type=float, default=100.0,
                       help="Maximum clamp value for individual KL terms")

    # State-Conditional Logit Scale ("Confidence Knob") + Entropy Band
    parser.add_argument("--enable_confidence_scaler", action="store_true",
                       help="Enable per-token confidence logit scaling with entropy band")
    parser.add_argument("--confidence_s_min", type=float, default=0.3,
                       help="Minimum scale value (prevents over-sharpening)")
    parser.add_argument("--confidence_s_max", type=float, default=10.0,
                       help="Maximum scale value (prevents trivial uncertainty)")
    parser.add_argument("--confidence_epsilon", type=float, default=1e-4,
                       help="Numerical floor for softplus output")
    parser.add_argument("--confidence_entropy_band_min", type=float, default=0.10,
                       help="Entropy band lower bound as fraction of log(V)")
    parser.add_argument("--confidence_entropy_band_max", type=float, default=0.35,
                       help="Entropy band upper bound as fraction of log(V)")
    parser.add_argument("--confidence_lambda_band", type=float, default=1e-3,
                       help="Weight for entropy band penalty loss")
    parser.add_argument("--confidence_lambda_scale", type=float, default=1e-4,
                       help="Weight for log(s) scale regulariser")
    parser.add_argument("--confidence_enable_risk_gating", action="store_true",
                       help="Enable Vritti risk gating (Viparyaya+Nidra → uncertainty)")
    parser.add_argument("--confidence_alpha_risk", type=float, default=0.5,
                       help="Risk scaling coefficient for s' = s * (1 + alpha * r)")
    parser.add_argument("--confidence_vritti_kl_weight", type=float, default=0.1,
                       help="Weight for Vritti KL auxiliary loss in risk gating")

    # ==========================================================================
    # Conscious Generation (Phase 1+): Token-Side Ontological Foundation
    # Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix D
    # ==========================================================================
    parser.add_argument("--enable_conscious_generation", action="store_true",
                       help="Enable conscious generation modules (token-side ontological projection)")
    parser.add_argument("--token_ontology_dim", type=int, default=32,
                       help="Ontological code dimension (must match SOVEREIGN_STATE_DIM)")
    parser.add_argument("--ontology_cache_refresh_interval", type=int, default=100,
                       help="Steps between O_tok cache refresh")
    parser.add_argument("--lambda_ont", type=float, default=0.0,
                       help="Ontological structure loss weight (0 = disabled)")
    parser.add_argument("--ontology_loss_type", type=str, default="contrastive",
                       choices=["contrastive", "prototype"],
                       help="Ontological structure loss formulation")
    parser.add_argument("--ontology_loss_temperature", type=float, default=0.1,
                       help="Temperature for contrastive ontological structure loss")
    parser.add_argument("--ontology_scorer_use_low_rank", action="store_true", default=True,
                       help="Use low-rank M_ont = A B^T factorization")
    parser.add_argument("--ontology_scorer_rank", type=int, default=8,
                       help="Rank for low-rank bilinear factorization")

    # Conscious Generation Phase 2: Primitive Scoring Heads
    parser.add_argument("--plausibility_token_dim", type=int, default=16,
                       help="Plausibility token representation dimension (d_j)")
    parser.add_argument("--jepa_token_dim", type=int, default=None,
                       help="(Deprecated) Alias for --plausibility_token_dim")
    parser.add_argument("--csr_token_dim", type=int, default=16,
                       help="CSR token representation dimension (d_c)")
    parser.add_argument("--primitive_shortlist_k", type=int, default=128,
                       help="Top-K base logits for primitive evaluation")
    parser.add_argument("--use_low_rank_primitives", action="store_true", default=True,
                       help="Use low-rank factorization for primitive bilinear forms")
    parser.add_argument("--primitive_rank", type=int, default=8,
                       help="Rank for primitive low-rank factorization")
    parser.add_argument("--use_shared_token_basis", action="store_true", default=False,
                       help="Share intermediate projection across primitives")

    # Conscious Generation Phase 3: Governance Integration
    parser.add_argument("--lambda_kosha_routing", type=float, default=0.0,
                       help="Kosha routing loss weight")
    parser.add_argument("--lambda_bliss_token", type=float, default=0.0,
                       help="Bliss token-level coherence loss weight")
    parser.add_argument("--lambda_plausibility_token", type=float, default=0.0,
                       help="Plausibility token-level loss")
    parser.add_argument("--lambda_jepa_token", type=float, default=None,
                       help="(Deprecated) Alias for --lambda_plausibility_token")
    parser.add_argument("--lambda_csr_token", type=float, default=0.0,
                       help="CSR token-level resonance loss")
    parser.add_argument("--lambda_vritti_token", type=float, default=0.0,
                       help="Vritti token-level cognitive mode loss")
    parser.add_argument("--lambda_guna_token", type=float, default=0.0,
                       help="Guna token-level energetic loss")
    parser.add_argument("--lambda_vritti_ontology_prior", type=float, default=0.0,
                       help="Ontology→Vritti directional prior KL regularizer weight")
    parser.add_argument("--vritti_ontology_prior_alpha", type=float, default=0.1,
                       help="Mixing strength of ontology-derived Vritti prior (capped at 0.4)")
    parser.add_argument("--vritti_ontology_prior_tau", type=float, default=1.0,
                       help="Temperature for ontology-derived Vritti prior softmax")
    parser.add_argument("--bliss_lambda_B", type=float, default=1.0,
                       help="Lambda_B temperature for Bliss gate")
    parser.add_argument("--kosha_routing_init", type=str, default="uniform",
                       choices=["uniform", "base_dominant"],
                       help="Kosha router initialization mode")

    # Conscious Generation Phase 3+: Governance plane (Pranamaya) — Domain × Kosha
    parser.add_argument("--kosha_num_domains", type=int, default=8,
                       help="Number of domain categories for governance routing")
    parser.add_argument("--kosha_interaction_rank", type=int, default=16,
                       help="Low-rank dimension for k ⊗ d interaction term")
    parser.add_argument("--kosha_initial_policy_scale", type=float, default=0.10,
                       help="Starting policy blend strength (structured vs residual)")
    parser.add_argument("--kosha_bliss_scale", type=float, default=2.0,
                       help="How much BLISSFUL Kosha activation increases gate lambda")
    parser.add_argument("--kosha_use_kosha", action="store_true", default=True,
                       help="Enable Kosha slice contribution (disable for ablation)")
    parser.add_argument("--kosha_no_kosha", action="store_true",
                       help="Ablation: disable Kosha slice contribution")
    parser.add_argument("--kosha_use_domain", action="store_true", default=True,
                       help="Enable domain contribution (disable for ablation)")
    parser.add_argument("--kosha_no_domain", action="store_true",
                       help="Ablation: disable domain contribution")
    parser.add_argument("--kosha_use_interaction", action="store_true", default=True,
                       help="Enable k ⊗ d interaction term (disable for ablation)")
    parser.add_argument("--kosha_no_interaction", action="store_true",
                       help="Ablation: disable k ⊗ d interaction term")
    parser.add_argument("--kosha_use_dynamic_bliss", action="store_true", default=True,
                       help="Enable BLISSFUL Kosha → gate lambda modulation")
    parser.add_argument("--kosha_no_dynamic_bliss", action="store_true",
                       help="Ablation: disable dynamic Bliss gate lambda")
    parser.add_argument("--enable_governance_probes", action="store_true",
                       help="Enable sensitivity probes in governance diagnostics")

    # Conscious Generation Phase 4: Field-Integrated Generation
    parser.add_argument("--use_field_integrated_softmax", action="store_true",
                       help="Replace standard logits with Z*(w) for L_LM")
    parser.add_argument("--field_softmax_temperature", type=float, default=1.0,
                       help="Temperature scaling for integrated softmax")
    parser.add_argument("--use_agreement_energy", action="store_true",
                       help="Enable pairwise agreement term A_t(w)")
    parser.add_argument("--agreement_energy_weight", type=float, default=0.1,
                       help="Beta weight for agreement-energy synergy term")

    # Conscious Generation Phase 5: Curriculum, Validation, and Ablation
    parser.add_argument("--enable_cg_curriculum", action="store_true",
                       help="Enable staged curriculum (A->D) for conscious generation")
    parser.add_argument("--cg_curriculum_ramp_mode", type=str, default="cosine",
                       choices=["linear", "cosine", "step"],
                       help="Lambda ramp mode for curriculum stages")
    parser.add_argument("--cg_curriculum_ppl_var_threshold", type=float, default=0.5,
                       help="Max PPL variance for stage transition")
    parser.add_argument("--cg_curriculum_stability_window", type=int, default=5,
                       help="Eval steps for PPL stability check")
    parser.add_argument("--cg_curriculum_stage_proportions", type=str,
                       default="0.30,0.20,0.25,0.25",
                       help="Stage A,B,C,D proportions (comma-separated, must sum to 1.0)")
    parser.add_argument("--enable_cg_diagnostics", action="store_true",
                       help="Enable governance diagnostics tracking")

    # Embedding diagnostics — verify CG auxiliaries are changing representations
    parser.add_argument("--enable_embedding_diagnostics", action="store_true",
                       help="Track embedding drift to verify CG auxiliaries change the model meaningfully")
    parser.add_argument("--embedding_diag_interval", type=int, default=200,
                       help="Steps between embedding diagnostic snapshots")
    parser.add_argument("--embedding_diag_vocab_sample", type=int, default=1000,
                       help="Number of vocab tokens to sample for drift metrics")
    parser.add_argument("--embedding_diag_neighbors", type=int, default=20,
                       help="Nearest neighbors to track for embedding stability")
    parser.add_argument("--embedding_diag_no_samples", action="store_true",
                       help="Disable vocab sampling (only track grad norms + adapter gate)")
    parser.add_argument("--embedding_diag_start_step", type=int, default=0,
                       help="Delay embedding diagnostics until this training step")

    # Factual eval — verify CG primitives distinguish facts from hallucinations
    parser.add_argument("--enable_factual_eval", action="store_true",
                       help="Run CG-aware factual probes to verify JEPA/Vritti distinguish facts from hallucinations")
    parser.add_argument("--factual_eval_interval", type=int, default=500,
                       help="Steps between factual evaluation runs")
    parser.add_argument("--factual_eval_probes", type=int, default=50,
                       help="Number of fact/hallucination probe pairs per evaluation")
    parser.add_argument("--factual_eval_start_step", type=int, default=0,
                       help="Delay factual evaluation until this training step")

    # CG Progress Snapshot (separate from text quality samples)
    parser.add_argument("--cg_sample_every", type=int, default=0,
                       help="CG progress snapshot interval in steps (0 = disabled). "
                            "Independent of --sample_every. Shows all active CG phases, "
                            "governance, and experiential controller state.")

    # Experiential Controller: 12-parameter resistance-driven plasticity
    parser.add_argument("--enable_experiential_controller", action="store_true",
                       help="Enable experiential controller (training-time plasticity modulation)")
    parser.add_argument("--experiential_d_model", type=int, default=128,
                       help="Internal d_model for experiential controller")
    parser.add_argument("--experiential_num_regions", type=int, default=12,
                       help="Number of plasticity regions")
    parser.add_argument("--experiential_lambda_temporal", type=float, default=0.5,
                       help="Temporal consistency loss weight")
    parser.add_argument("--experiential_lambda_coherence", type=float, default=0.3,
                       help="Cross-signal coherence loss weight")
    parser.add_argument("--experiential_lambda_latent", type=float, default=0.1,
                       help="Latent alignment loss weight")
    parser.add_argument("--experiential_k_r", type=float, default=2.0,
                       help="Resistance openness scaling")
    parser.add_argument("--experiential_k_m", type=float, default=2.0,
                       help="Misalignment suppression scaling")
    parser.add_argument("--experiential_b_p", type=float, default=-1.0,
                       help="Bias floor for plasticity gate")
    parser.add_argument("--experiential_G_base", type=float, default=3.0,
                       help="Base adaptive gain")
    parser.add_argument("--experiential_G_min", type=float, default=0.1,
                       help="Minimum gain clamp")
    parser.add_argument("--experiential_G_max", type=float, default=5.0,
                       help="Maximum gain clamp")
    parser.add_argument("--experiential_k_dv", type=float, default=1.0,
                       help="Gradient variance damping sensitivity")
    parser.add_argument("--experiential_k_dc", type=float, default=0.5,
                       help="Coherence instability damping sensitivity")
    parser.add_argument("--experiential_alpha_base", type=float, default=0.01,
                       help="Identity EMA base learning rate")
    parser.add_argument("--experiential_replay_interval", type=int, default=100,
                       help="Medium loop: replay buffer sample every N steps")
    parser.add_argument("--experiential_consolidation_interval", type=int, default=1000,
                       help="Slow loop: identity consolidation every N steps")
    parser.add_argument("--experiential_log_interval", type=int, default=100,
                       help="Experiential controller diagnostics log interval")
    parser.add_argument("--experiential_loss_weight", type=float, default=0.1,
                       help="Weight for experiential loss contribution to main loss")
    parser.add_argument("--experiential_warmup_steps", type=int, default=200,
                       help="Ramp experiential loss weight from 0 to full over N steps")
    parser.add_argument("--experiential_loss_clamp", type=float, default=5.0,
                       help="Max experiential loss contribution (prevents divergence on resume)")

    # Stage 8: Perspective Synthesizer (representation conditioning)
    parser.add_argument("--enable_perspective_synthesizer", action="store_true",
                       help="Enable Stage 8 Perspective Synthesizer (representation conditioning before lm_head)")
    parser.add_argument("--perspective_d_synthesis", type=int, default=64,
                       help="Synthesis MLP hidden dimension for Stage 8")
    parser.add_argument("--perspective_gate_init", type=float, default=0.0,
                       help="Initial gate value (0.0 for safe cold start)")
    parser.add_argument("--perspective_log_interpretive", action="store_true", default=True,
                       help="Log full InterpretiveState per token to TensorBoard")

    # Stage 9: Attention Mechanism Ablation Audit (F.14)
    parser.add_argument("--ablation_disable_phase_sync", action="store_true",
                       help="Stage 9: Disable phase synchronization (fall back to dot-product attention)")
    parser.add_argument("--ablation_disable_vritti", action="store_true",
                       help="Stage 9: Disable Vritti modulation (no cognitive gating)")
    parser.add_argument("--ablation_disable_guna_bias", action="store_true",
                       help="Stage 9: Disable Guna top-down bias")
    parser.add_argument("--ablation_enable_dual_channel_intent", action="store_true",
                       help="Stage 9: Enable dual-channel intent alignment (experimental)")
    parser.add_argument("--ablation_log_mechanism_strength_every", type=int, default=0,
                       help="Stage 9: Log mechanism strength signals every N steps (0=disabled)")
    parser.add_argument("--run_ablation_audit", action="store_true",
                       help="Stage 9: Run full ablation matrix after training/on checkpoint "
                            "(requires --resume)")

    # Conscious Generation Phase Test
    parser.add_argument("--test_cg_phases", action="store_true",
                       help="Run conscious generation phase tests instead of training. "
                            "Smoke-tests Phases 1-5 with synthetic data.")
    parser.add_argument("--test_cg_phases_list", type=int, nargs="*", default=None,
                       help="Which CG phases to test (e.g., --test_cg_phases_list 1 2 3)")
    parser.add_argument("--test_cg_phase5_only", action="store_true",
                       help="Only test Phase 5 (curriculum) — no model needed")
    parser.add_argument("--test_cg_no_loop", action="store_true",
                       help="Skip integration training loop (unit tests only)")

    # Stress Test (V9.4.4)
    parser.add_argument("--stress_test", action="store_true",
                       help="Run stress test instead of training")
    parser.add_argument("--stress_start", type=int, default=1000,
                       help="Step to start corruption")
    parser.add_argument("--stress_duration", type=int, default=200,
                       help="Steps to inject corruption")
    parser.add_argument("--corruption_rate", type=float, default=0.10,
                       help="Probability of corrupting each batch")
    parser.add_argument("--corruption_mode", type=str, default="noise",
                       choices=["noise", "label_flip", "repeat"],
                       help="Type of corruption")

    args = parser.parse_args()

    # Handle --use_amp convenience flag
    if args.use_amp:
        args.mixed_precision = "bf16"

    # Handle CG phase test redirect
    if args.test_cg_phases or args.test_cg_phase5_only:
        print("=" * 70)
        print("  CONSCIOUS GENERATION PHASE TEST MODE")
        print("=" * 70)
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "test_cg_phases.py")
        script_path = os.path.normpath(script_path)
        cg_cmd = [sys.executable, script_path]
        if args.test_cg_phase5_only:
            cg_cmd.append("--phase5-only")
        elif args.test_cg_phases_list:
            cg_cmd.extend(["--phases"] + [str(p) for p in args.test_cg_phases_list])
        cg_cmd.extend(["--steps", str(args.max_steps)])
        cg_cmd.extend(["--eval-every", str(args.eval_every)])
        cg_cmd.extend(["--batch-size", str(args.batch_size)])
        if args.model_size == "tiny":
            cg_cmd.append("--tiny")
        if args.test_cg_no_loop:
            cg_cmd.append("--no-loop")
        print(f"\nRunning: {' '.join(cg_cmd)}\n")
        result = subprocess.run(cg_cmd)
        sys.exit(result.returncode)

    # Handle stress test redirect
    if args.stress_test:
        print("=" * 70)
        print("  STRESS TEST MODE - Redirecting to stress_test.py")
        print("=" * 70)
        import subprocess
        stress_cmd = [
            sys.executable, "stress_test.py",
            "--resume", args.resume or "",
            "--stress_start", str(args.stress_start),
            "--stress_duration", str(args.stress_duration),
            "--corruption_rate", str(args.corruption_rate),
            "--corruption_mode", args.corruption_mode,
            "--checkpoint_dir", args.checkpoint_dir + "_stress_test",
        ]
        print(f"\nRunning: {' '.join(stress_cmd)}\n")
        result = subprocess.run(stress_cmd)
        sys.exit(result.returncode)

    # Create config
    config = UnifiedTrainingConfig(
        model_type=args.model_type,
        model_size=args.model_size,
        max_seq_len=args.max_seq_len,
        # Architecture overrides
        n_layer=args.n_layer,
        n_head=args.n_head,
        n_embd=args.n_embd,
        n_kv_heads=args.n_kv_heads,
        dropout=args.dropout,
        attention_dropout=args.attention_dropout,
        # Training hyperparameters
        batch_size=args.batch_size,
        batch_size_max=args.batch_size_max,
        gradient_accumulation=args.gradient_accumulation,
        vram_threshold=args.vram_threshold,
        vram_recovery_buffer=args.vram_recovery_buffer,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        warmup_until_ppl=args.warmup_until_ppl,
        weight_decay=args.weight_decay,
        max_grad_norm=args.max_grad_norm,
        dataset=args.dataset,
        dataset_name=args.dataset_name,
        dataset_subset=args.dataset_subset,
        cache_val_batches=args.cache_val_batches,
        cache_dataset=args.cache_dataset,
        gradient_checkpointing=args.gradient_checkpointing,
        checkpoint_offload_cpu=args.checkpoint_offload_cpu,
        mixed_precision=args.mixed_precision,
        local_backend=args.local_backend,
        window_size=args.window_size,
        alpha_local=args.alpha_local,
        local_layers=args.local_layers,
        # V10.14: Global Tokens / Slot Memory
        global_tokens_enabled=getattr(args, 'global_tokens', False),
        num_global_tokens=getattr(args, 'num_global_tokens', 64),
        global_update_mode=getattr(args, 'global_update_mode', 'slots'),
        slots_write_lr=getattr(args, 'slots_write_lr', 0.1),
        retrieval_loss_weight=getattr(args, 'retrieval_loss_weight', 1.0),
        slot_prediction_loss_weight=getattr(args, 'slot_prediction_loss_weight', 0.1),
        slot_memory_lr_scale=getattr(args, 'slot_memory_lr_scale', 0.1),
        # V11: Slot memory experiment
        global_read_interval=getattr(args, 'global_read_interval', 1),
        global_write_start_layer=getattr(args, 'global_write_start_layer', 0),
        disable_slot_adaptive_constraints=getattr(args, 'disable_slot_adaptive_constraints', False),
        reset_slot_constraints=getattr(args, 'reset_slot_constraints', False),
        slot_gate_target=getattr(args, 'slot_gate_target', None),
        slot_gate_ceil_weight=getattr(args, 'slot_gate_ceil_weight', None),
        slot_gate_ceil_margin=getattr(args, 'slot_gate_ceil_margin', None),
        # V16: Semantic coherence gate
        slot_coherence_floor=getattr(args, 'slot_coherence_floor', None),
        slot_coherence_floor_tied=getattr(args, 'slot_coherence_floor_tied', True),
        # V20: Auto-scaling
        slot_auto_scale=getattr(args, 'slot_auto_scale', False),
        # V10.23: Three-phase proportional slot LR
        slot_lr_scale_min=getattr(args, 'slot_lr_scale_min', 0.1),
        slot_lr_scale_max=getattr(args, 'slot_lr_scale_max', 0.8),
        slot_lr_eta=getattr(args, 'slot_lr_eta', 0.03),
        slot_lr_stabilize_after=getattr(args, 'slot_lr_stabilize_after', None),
        # GCT (Gated Coherence Transformer)
        gct_window_size=args.gct_window_size,
        gct_coherence_gamma=args.gct_coherence_gamma,
        gct_coherence_delta=args.gct_coherence_delta,
        gct_ema_decay=args.gct_ema_decay,
        gct_num_bands=args.gct_num_bands,
        gct_alpha_sharpness=args.gct_alpha_sharpness,
        gct_hard_route_threshold=args.gct_hard_route_threshold,
        gct_kappa=args.gct_kappa,
        gct_tau_ladder=args.gct_tau_ladder,
        gct_warmup_steps=args.gct_warmup_steps,
        gct_anneal_steps=args.gct_anneal_steps,
        cosine_mode=args.cosine_mode,  # V9.6.12: Cosine interaction mode
        decay_gamma=args.decay_gamma,  # V9.6.13: State decay factor
        learned_decay=args.learned_decay,  # V9.9.7: Per-head learned decay
        bounded_phase=args.bounded_phase,  # V9.9.11: Phase collapse fix 1
        zero_mean_cosine=args.zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
        # V10.3.8: Dual-Channel Attention
        dual_channel_mode=args.dual_channel_mode,
        alignment_authority=args.alignment_authority,
        # V10.6.1: Alignment Clamp
        alignment_clamp_min=args.alignment_clamp_min,
        alignment_clamp_max=args.alignment_clamp_max,
        # V10.6.2: No-Write Contract Enforcement
        strict_control_contract=args.strict_control_contract,
        # V10.6.3: Architecture Health Summary
        run_architecture_health_check=args.run_architecture_health_check,
        architecture_health_strict=args.architecture_health_strict,
        # V10.6.5: Parameter-Matched Baseline Enforcement
        enforce_baseline_param_match=args.enforce_baseline_param_match,
        # V10.6.6: Quad Utilization Sanity Checks
        enable_quad_utilization_checks=args.enable_quad_utilization_checks,
        quad_utilization_warn_threshold=args.quad_utilization_warn_threshold,
        quad_utilization_check_interval=args.quad_utilization_check_interval,
        # V10.6.7: Lightweight Probe Hooks
        enable_probe_hooks=args.enable_probe_hooks,
        probe_hook_interval=args.probe_hook_interval,
        probe_hook_types=args.probe_hook_types,
        # Phase Rotation Test
        phase_rotation=args.phase_rotation,
        phase_rotation_angles=args.phase_rotation_angles,
        phase_rotation_as_diagnostic=args.phase_rotation_as_diagnostic,
        state_dim=args.state_dim,  # V9.6.14: Ontological Hybrid state dimension
        project_per_head_dim=args.project_per_head_dim,  # V9.6.14: Per-head-dim projection
        # V10.0: Binding Cache options
        binding_cache_top_k=args.binding_cache_top_k,
        no_binding_cache=args.no_binding_cache,
        # V10.0: Binding Annotation (CSR/Kosha/SRK as selectors, not modifiers)
        # V10.5: Interference-Aware Proposal Scoring
        enable_quad_interference=args.enable_quad_interference,
        interference_lambda_text=args.interference_lambda_text,
        interference_min_step=args.interference_min_step,
        interference_entropy_gate=args.interference_entropy_gate,
        interference_auto_classify=args.interference_auto_classify and not args.no_interference_auto_classify,
        interference_modes=args.interference_modes,
        # V10.0: Binding Annotation (CSR/Kosha/SRK as selectors, not modifiers)
        use_binding_annotator=args.use_binding_annotator and not args.no_binding_annotator,
        use_csr_annotation=args.use_csr_annotation and not args.no_csr_annotation,
        use_kosha_annotation=args.use_kosha_annotation and not args.no_kosha_annotation,
        use_srk_annotation=args.use_srk_annotation and not args.no_srk_annotation,
        bhava_lambda=args.bhava_lambda,
        coherence_lambda=args.coherence_lambda,
        log_every=args.log_every,
        quiet=args.quiet,
        enable_kosha_diagnostics=args.enable_kosha_diagnostics,
        kosha_log_every=args.kosha_log_every,
        lightweight_diagnostics=not args.full_diagnostics,  # Default True unless --full_diagnostics
        enable_kosha_steering=args.enable_kosha_steering,
        kosha_steering_force=args.kosha_steering_force,
        kosha_steering_warmup=args.kosha_steering_warmup,
        kosha_steering_layer=args.kosha_steering_layer,
        # v2.2.1: Kosha Gyroscope - Homeostatic Self-Regulation
        enable_kosha_gyroscope=args.enable_kosha_gyroscope,
        # V9.8.7: Three-phase dynamic engagement
        gyroscope_engage_ppl=args.gyroscope_engage_ppl,
        gyroscope_active_ppl=args.gyroscope_active_ppl,
        gyroscope_relaxed_ceiling_clamp=args.gyroscope_relaxed_ceiling_clamp,
        gyroscope_relaxed_floor_push=args.gyroscope_relaxed_floor_push,
        gyroscope_active_ceiling_clamp=args.gyroscope_active_ceiling_clamp,
        gyroscope_active_floor_push=args.gyroscope_active_floor_push,
        gyroscope_base_gain=args.gyroscope_base_gain,
        gyroscope_max_gain=args.gyroscope_max_gain,
        gyroscope_ppl_ceiling=args.gyroscope_ppl_ceiling,
        gyroscope_target_ppl=args.gyroscope_target_ppl,
        gyroscope_trap_threshold=args.gyroscope_trap_threshold,
        gyroscope_gate_threshold=args.gyroscope_gate_threshold,
        gyroscope_balance_target=args.gyroscope_balance_target,
        gyroscope_gate_temperature=args.gyroscope_gate_temperature,
        # v2.3.0: Complete Harmonic Pentad - Floors and Ceilings
        gyroscope_floor_mental=args.gyroscope_floor_mental,
        gyroscope_ceiling_mental=args.gyroscope_ceiling_mental,
        gyroscope_floor_physical=args.gyroscope_floor_physical,
        gyroscope_ceiling_physical=args.gyroscope_ceiling_physical,
        gyroscope_floor_intellect=args.gyroscope_floor_intellect,
        gyroscope_ceiling_intellect=args.gyroscope_ceiling_intellect,
        gyroscope_floor_vital=args.gyroscope_floor_vital,
        gyroscope_ceiling_vital=args.gyroscope_ceiling_vital,
        gyroscope_floor_bliss=args.gyroscope_floor_bliss,
        gyroscope_ceiling_bliss=args.gyroscope_ceiling_bliss,
        gyroscope_floor_push_factor=args.gyroscope_floor_push_factor,
        gyroscope_ceiling_clamp_factor=args.gyroscope_ceiling_clamp_factor,
        # v2.3.2: Reflexive Domain Morph
        gyroscope_domain_morph_enabled=args.gyroscope_domain_morph_enabled and not args.disable_gyroscope_domain_morph,
        gyroscope_domain_morph_ema_decay=args.gyroscope_domain_morph_ema_decay,
        gyroscope_domain_morph_internal_weight=args.gyroscope_domain_morph_internal_weight,
        gyroscope_domain_morph_external_weight=args.gyroscope_domain_morph_external_weight,
        # v2.2.4: Three-Stage Hybrid Logic
        gyroscope_damper_steepness=args.gyroscope_damper_steepness,
        gyroscope_gate_steepness=args.gyroscope_gate_steepness,
        gyroscope_rip_multiplier=args.gyroscope_rip_multiplier,
        gyroscope_steepness=args.gyroscope_steepness,  # Legacy, deprecated
        gyroscope_temporal_window=args.gyroscope_temporal_window,
        gyroscope_vital_momentum=args.gyroscope_vital_momentum and not args.disable_gyroscope_vital_momentum,
        gyroscope_warmup_steps=args.gyroscope_warmup_steps,
        kosha_rampdown_steps=args.kosha_rampdown_steps,
        # V9.8.6: Three-Phase Kosha Curriculum
        kosha_engage_ppl=args.kosha_engage_ppl,
        kosha_disengage_ppl=args.kosha_disengage_ppl,
        gyroscope_graduation_ppl=args.gyroscope_graduation_ppl,
        gyroscope_graduation_variance=args.gyroscope_graduation_variance,
        gyroscope_graduation_window=args.gyroscope_graduation_window,
        enable_rip_logger=args.enable_rip_logger,
        rip_logger_dir=args.rip_logger_dir,
        # v2.3.3: 32D Sovereign State Regularizer
        enable_state_regularizer=args.enable_state_regularizer,
        state_reg_anti_sat_weight=args.state_reg_anti_sat_weight,
        state_reg_variance_weight=args.state_reg_variance_weight,
        state_reg_sat_thresh_high=args.state_reg_sat_thresh_high,
        state_reg_sat_thresh_low=args.state_reg_sat_thresh_low,
        state_reg_target_std_kosha=args.state_reg_target_std_kosha,
        state_reg_vital_weight=args.state_reg_vital_weight,
        state_reg_bliss_weight=args.state_reg_bliss_weight,
        # V9.7.0: Ontological Bridge (Layer 4 - Foundational Structure)
        enable_onto_bridge=args.enable_onto_bridge,
        onto_bridge_lambda=args.onto_bridge_lambda,
        onto_bridge_diversity=args.onto_bridge_diversity,
        onto_bridge_pramana=args.onto_bridge_pramana,
        onto_bridge_layer=args.onto_bridge_layer,
        # V9.8.6: Three-Phase Onto Bridge Curriculum
        onto_engage_ppl=args.onto_engage_ppl,
        onto_disengage_ppl=args.onto_disengage_ppl,
        onto_rampdown_steps=args.onto_rampdown_steps,
        eval_every=args.eval_every,
        save_every=args.save_every,
        no_save=args.no_save,
        checkpoint_dir=args.checkpoint_dir,
        no_coherence_loss=args.no_coherence_loss,
        seed=args.seed,
        # Sovereign-Lagrangian Loss [Patent B1/S3]
        enable_sovereign_loss=args.enable_sovereign_loss,
        sovereign_weight_r=args.sovereign_weight_r,
        sovereign_weight_s=args.sovereign_weight_s,
        sovereign_weight_c=args.sovereign_weight_c,
        b1_lambda=args.b1_lambda,
        mu_s3=args.mu_s3,
        enable_stability_constraint=args.enable_stability_constraint,
        gc_floor=args.gc_floor,
        # V9.5.1 Entropy Floor
        enable_entropy_floor=args.enable_entropy_floor,
        entropy_floor=args.entropy_floor,
        entropy_floor_weight=args.entropy_floor_weight,
        # Entropy-Based Logit Scale Control
        enable_entropy_control_train=args.enable_entropy_control_train,
        enable_entropy_control_infer=args.enable_entropy_control_infer,
        entropy_topk=args.entropy_topk,
        entropy_h_min=args.entropy_h_min,
        entropy_h_max=args.entropy_h_max,
        entropy_control_lambda=args.entropy_control_lambda,
        logit_scale_min=args.logit_scale_min,
        logit_scale_max=args.logit_scale_max,
        infer_h_target=args.infer_h_target,
        infer_eta=args.infer_eta,
        infer_delta_clip=args.infer_delta_clip,
        # V9.5.1 Force Evolution
        force_evolution_stage=args.force_evolution_stage,
        # V9.9.1 Multi-Stage Evolution
        enable_multi_stage_evolution=args.enable_multi_stage_evolution and not args.disable_multi_stage_evolution,
        evolution_trigger_mode=args.evolution_trigger_mode,
        evolution_ppl_triggers=args.evolution_ppl_triggers,
        evolution_step_triggers=args.evolution_step_triggers,
        custom_evolution_stages=args.custom_evolution_stages,
        evolution_patience=args.evolution_patience,
        evolution_coherence_min=args.evolution_coherence_min,
        evolution_entropy_floor=args.evolution_entropy_floor,
        evolution_ppl_window=args.evolution_ppl_window,
        evolution_thaw_alpha=args.evolution_thaw_alpha,
        evolution_thaw_steps=args.evolution_thaw_steps,
        # Alpha phase and decay schedule (for phase/hybrid attention)
        alpha_phase=args.alpha_phase,
        alpha_phase_start=args.alpha_phase_start,
        alpha_phase_end=args.alpha_phase_end,
        alpha_decay_steps=args.alpha_decay_steps,
        # Phase-first curriculum (unified inverse curriculum)
        phase_first_curriculum=args.phase_first_curriculum,
        # PPL-gated alpha curriculum
        enable_ppl_alpha_curriculum=args.enable_ppl_alpha_curriculum,
        alpha_phase_ppl_high=args.alpha_phase_ppl_high,
        alpha_phase_ppl_low=args.alpha_phase_ppl_low,
        ppl_high_threshold=args.ppl_high_threshold,
        ppl_low_threshold=args.ppl_low_threshold,
        # Adaptive window size
        enable_adaptive_window=args.enable_adaptive_window,
        window_size_high_ppl=args.window_size_high_ppl,
        window_size_low_ppl=args.window_size_low_ppl,
        # Post-curriculum adaptive alpha
        enable_adaptive_alpha=args.enable_adaptive_alpha,
        adaptive_alpha_min=args.adaptive_alpha_min,
        adaptive_alpha_max=args.adaptive_alpha_max,
        # Decorrelation loss (to force phase and local to learn different features)
        decorr_loss_weight=args.decorr_loss_weight,
        # V9.9.10/V9.9.12: Phase diversity loss
        phase_diversity_weight=args.phase_diversity_weight,
        phase_diversity_ramp_steps=args.phase_diversity_ramp_steps,
        enable_adaptive_phase_diversity=args.enable_adaptive_phase_diversity,
        phase_diversity_target_R=args.phase_diversity_target_R,
        phase_diversity_lambda_init=args.phase_diversity_lambda_init,
        phase_diversity_lambda_max=args.phase_diversity_lambda_max,
        phase_diversity_eta=args.phase_diversity_eta,
        phase_diversity_ramp_multiplier=args.phase_diversity_ramp_multiplier,
        # V9.9.12b: Task-loss scaling
        phase_diversity_task_scaling=args.phase_diversity_task_scaling and not args.no_phase_diversity_task_scaling,
        phase_diversity_task_alpha=args.phase_diversity_task_alpha,
        # V9.9.1 Per-Layer Phase Control
        # V9.9.8: Auto-enable when per_layer_phase_weights is provided
        enable_per_layer_phase=args.enable_per_layer_phase or bool(args.per_layer_phase_weights),
        per_layer_phase_weights=args.per_layer_phase_weights,
        layer_transition_steps=args.layer_transition_steps,
        # V9.9.1 Inverted Curriculum
        enable_inverted_curriculum=args.enable_inverted_curriculum,
        inverted_curriculum_stages=args.inverted_curriculum_stages,
        inverted_curriculum_ppl_triggers=args.inverted_curriculum_ppl_triggers,
        # V9.9.4: PPL Stability Check
        inverted_curriculum_stability_threshold=args.inverted_curriculum_stability_threshold,
        inverted_curriculum_stability_stages=args.inverted_curriculum_stability_stages,
        # V9.5.2 Emergency Stress-Probe (ChatGPT Guardrails)
        enable_stress_probe=args.enable_stress_probe,
        stress_probe_entropy_trigger=args.stress_probe_entropy_trigger,
        stress_probe_rep3_trigger=args.stress_probe_rep3_trigger,
        stress_probe_utr_trigger=args.stress_probe_utr_trigger,
        stress_probe_drs_trigger=args.stress_probe_drs_trigger,
        stress_probe_coherence_min=args.stress_probe_coherence_min,
        stress_probe_patience=args.stress_probe_patience,
        stress_probe_authority_scale=args.stress_probe_authority_scale,
        stress_probe_lr_factor=args.stress_probe_lr_factor,
        stress_probe_exit_entropy=args.stress_probe_exit_entropy,
        stress_probe_exit_rep3=args.stress_probe_exit_rep3,
        stress_probe_min_steps=args.stress_probe_min_steps,
        stress_probe_max_steps=args.stress_probe_max_steps,
        stress_probe_lr_restore_steps=args.stress_probe_lr_restore_steps,
        force_stress_probe=args.force_stress_probe,
        # PIDv2 Controller settings
        controller=args.controller,
        pidv2_kp_min=args.pidv2_kp_min,
        pidv2_kp_max=args.pidv2_kp_max,
        pidv2_kp_sensitivity=args.pidv2_kp_sensitivity,
        pidv2_ki=args.pidv2_ki,
        pidv2_kd=args.pidv2_kd,
        pidv2_a_min=args.pidv2_a_min,
        pidv2_c_floor=args.pidv2_c_floor,
        pidv2_c_good=args.pidv2_c_good,
        pidv2_w_s=args.pidv2_w_s,
        # V9.7.0: PIDv2 Dynamic Batch Sizing
        pidv2_batch_resize=args.pidv2_batch_resize,
        pidv2_batch_min=args.pidv2_batch_min,
        pidv2_batch_max=args.pidv2_batch_max,
        pidv2_batch_velocity_threshold=args.pidv2_batch_velocity_threshold,
        pidv2_batch_stable_streak=args.pidv2_batch_stable_streak,
        # V9.8.7: Three-phase PID engagement
        pidv2_engage_ppl=args.pidv2_engage_ppl,
        pidv2_disengage_ppl=args.pidv2_disengage_ppl,
        pidv2_rampdown_steps=args.pidv2_rampdown_steps,
        pidv2_engagement_enabled=not args.no_pidv2_engagement,
        phase_ramp_steps=args.phase_ramp_steps,
        tensorboard=args.tensorboard and not args.no_tensorboard,
        sample_every=args.sample_every,
        # Knowledge Probes
        knowledge_probe_every=args.knowledge_probe_every,
        knowledge_probe_top_k=args.knowledge_probe_top_k,
        knowledge_probe_coherence_tokens=args.knowledge_probe_coherence_tokens,
        knowledge_probe_chunk_size=args.knowledge_probe_chunk_size,
        # LRA Validation
        lra_validate_every=args.lra_validate_every,
        lra_haystack_lengths=args.lra_haystack_lengths,
        lra_num_samples=args.lra_num_samples,
        resume=args.resume,
        resume_weights_only=args.resume_weights_only,
        # Formula [1331]: 9:3 Hierarchical Split
        use_9_3_split=args.use_9_3_split,
        enable_gradient_scaling=args.enable_gradient_scaling,
        authority_layers=args.authority_layers,
        sensory_layers=args.sensory_layers,
        alpha_sens_initial=args.alpha_sens_initial,
        alpha_sens_max=args.alpha_sens_max,
        gradient_warmup_steps=args.gradient_warmup_steps,
        # V9.6.8: Layer-wise alpha dampening
        enable_layerwise_alpha=args.enable_layerwise_alpha and not args.disable_layerwise_alpha,
        alpha_output_scale=args.alpha_output_scale,
        alpha_reasoning_scale=args.alpha_reasoning_scale,
        authority_floor=args.authority_floor,
        use_per_layer_clipping=args.use_per_layer_clipping,
        use_8bit_optimizer=args.use_8bit_optimizer,
        use_compile=args.use_compile and not args.no_compile,
        # Dynamic Relaxation: 9:3 → 6:6 transition
        enable_dynamic_relaxation=args.enable_dynamic_relaxation and not args.disable_dynamic_relaxation,
        relaxation_mode=args.relaxation_mode,
        relaxation_stability_threshold=args.relaxation_stability_threshold,
        relaxation_stability_window=args.relaxation_stability_window,
        relaxation_streak_target=args.relaxation_streak_target,
        force_relaxation_step=args.force_relaxation_step,
        # Sovereign Saturation Gate
        enable_saturation_gate=args.enable_saturation_gate and not args.disable_saturation_gate,
        saturation_coherence_threshold=args.saturation_coherence_threshold,
        saturation_patience=args.saturation_patience,
        saturation_thaw_start=args.saturation_thaw_start,
        saturation_thaw_end=args.saturation_thaw_end,
        saturation_thaw_steps=args.saturation_thaw_steps,
        relaxation_target_authority=args.relaxation_target_authority,
        relaxation_target_sensory=args.relaxation_target_sensory,
        relaxation_thaw_alpha=args.relaxation_thaw_alpha,
        relaxation_thaw_steps=args.relaxation_thaw_steps,
        relaxation_ppl_spike_threshold=args.relaxation_ppl_spike_threshold,
        relaxation_recovery_steps=args.relaxation_recovery_steps,
        # Weight Transfer
        enable_weight_transfer=args.enable_weight_transfer and not args.disable_weight_transfer,
        guna_lock_steps=args.guna_lock_steps,
        # Toroidal Evolutionary Bridge
        enable_toroidal_bridge=args.enable_toroidal_bridge,
        toroidal_lambda=args.toroidal_lambda,
        toroidal_dropout=args.toroidal_dropout,
        toroidal_use_gating=args.toroidal_use_gating,
        toroidal_truncated_bptt=args.toroidal_truncated_bptt,
        toroidal_coherence_threshold=args.toroidal_coherence_threshold,
        # Full Evolutionary Flow System (Phase 2-5)
        enable_evolutionary_flow=args.enable_evolutionary_flow and not args.disable_evolutionary_flow,
        evo_lambda=args.evo_lambda,
        evo_micro_weight=args.evo_micro_weight,
        evo_meso_weight=args.evo_meso_weight,
        evo_macro_weight=args.evo_macro_weight,
        evo_dropout=args.evo_dropout,
        evo_use_rmatrix=args.evo_use_rmatrix,
        evo_coherence_window=args.evo_coherence_window,
        evo_resonance_alpha=args.evo_resonance_alpha,
        evo_lr_modulation=args.evo_lr_modulation,
        evo_lr_slowdown=args.evo_lr_slowdown,
        evo_lr_accelerate=args.evo_lr_accelerate,
        # V9.7.0: EvoFlow Fluency Gate
        evo_fluency_gate=args.evo_fluency_gate,
        evo_fluency_min_steps=args.evo_fluency_min_steps,
        evo_fluency_ppl_threshold=args.evo_fluency_ppl_threshold,
        # V9.8.0: RSS (Rational Sovereign Sequence)
        enable_rss=args.enable_rss,
        rss_evoflow_ppl=args.rss_evoflow_ppl,
        rss_toroidal_ppl=args.rss_toroidal_ppl,
        rss_csr_ppl=args.rss_csr_ppl,
        rss_kosha_ppl=args.rss_kosha_ppl,
        rss_csr_warmup_steps=args.rss_csr_warmup_steps,
        rss_use_val_ppl=args.rss_use_val_ppl,
        # PPL-Gated Curriculum Learning
        enable_curriculum=args.enable_curriculum,
        curriculum_ppl_regularization=args.curriculum_ppl_regularization,
        curriculum_ppl_grounding=args.curriculum_ppl_grounding,
        curriculum_ppl_sovereign=args.curriculum_ppl_sovereign,
        curriculum_stability_window=args.curriculum_stability_window,
        curriculum_hysteresis=args.curriculum_hysteresis,
        # V2.3.4: Sequence Length Curriculum
        enable_seq_curriculum=args.enable_seq_curriculum,
        seq_len_start=args.seq_len_start,
        seq_len_end=args.seq_len_end if args.seq_len_end > 0 else args.max_seq_len,
        seq_len_ramp_steps=args.seq_len_ramp_steps,
        seq_len_ramp_mode=args.seq_len_ramp_mode,
        seq_len_ppl_gate=args.seq_len_ppl_gate,
        # CSR Phoneme-Ontological Grounding
        enable_csr=args.enable_csr and not args.disable_csr,
        csr_lambda=args.csr_lambda,
        csr_tau=args.csr_tau,
        csr_use_phase_gating=args.csr_use_phase_gating,
        csr_trainable=args.csr_trainable,
        csr_use_entropy_sink=args.csr_use_entropy_sink,
        csr_use_synthesis_gate=args.csr_use_synthesis_gate,
        csr_alignment_layer=args.csr_alignment_layer,
        untie_embeddings=args.untie_embeddings,
        # V9.6.8: CSR Projector LR Scale and Gradient Warmup
        csr_projector_lr_scale=args.csr_projector_lr_scale,
        csr_gradient_warmup_steps=args.csr_gradient_warmup_steps,
        # V9.7.0: CSR Sparse Delayed Supervision
        csr_sparse_supervision=args.csr_sparse_supervision,
        csr_content_word_only=args.csr_content_word_only,
        # V9.8.6: CSR Three-Phase Curriculum
        csr_engage_ppl=args.csr_engage_ppl,
        csr_disengage_ppl=args.csr_disengage_ppl,
        csr_rampdown_steps=args.csr_rampdown_steps,
        # Appendix G Phase 3: Bliss Gating
        enable_bliss_gating=args.enable_bliss_gating,
        bliss_gate_gamma=args.bliss_gate_gamma,
        bliss_gate_lambda_min=args.bliss_gate_lambda_min,
        bliss_gate_warmup_steps=args.bliss_gate_warmup_steps,
        # Appendix G Phase 4: JEPA Injection
        enable_jepa_injection=args.enable_jepa_injection,
        jepa_injection_lambda=args.jepa_injection_lambda,
        jepa_injection_layer=args.jepa_injection_layer,
        jepa_injection_projector_lr_scale=args.jepa_injection_projector_lr_scale,
        # SGP (Stochastic Gradient Persistence)
        enable_sgp=args.enable_sgp and not args.disable_sgp,
        sgp_base_rate=args.sgp_base_rate,
        sgp_stagnation_rate=args.sgp_stagnation_rate,
        sgp_gamma=args.sgp_gamma,
        # Sattvic Controller
        sattvic_initial_lambda=args.sattvic_initial_lambda,
        sattvic_floor_lambda=args.sattvic_floor_lambda,
        sattvic_warmup_steps=args.sattvic_warmup_steps,
        sattvic_variance_window=args.sattvic_variance_window,
        sattvic_variance_threshold=args.sattvic_variance_threshold,
        # Adaptive Training Controller
        enable_adaptive_training=args.enable_adaptive_training and not args.disable_adaptive_training,
        adaptive_lr_min=args.adaptive_lr_min,
        adaptive_lr_max=args.adaptive_lr_max,
        adaptive_lr_boost=args.adaptive_lr_boost,
        adaptive_lr_decay=args.adaptive_lr_decay,
        adaptive_velocity_slow=args.adaptive_velocity_slow,
        adaptive_velocity_spike=args.adaptive_velocity_spike,
        adaptive_plateau_window=args.adaptive_plateau_window,
        adaptive_plateau_threshold=args.adaptive_plateau_threshold,
        adaptive_min_interval=args.adaptive_min_interval,
        # V9.8.2: Safeguards
        adaptive_max_lr_relative=args.adaptive_max_lr_relative,
        adaptive_loss_spike_threshold=args.adaptive_loss_spike_threshold,
        adaptive_grad_norm_spike=args.adaptive_grad_norm_spike,
        adaptive_emergency_decay=args.adaptive_emergency_decay,
        adaptive_consecutive_spike_limit=args.adaptive_consecutive_spike_limit,
        adaptive_max_boost_from_base=args.adaptive_max_boost_from_base,
        adaptive_boost_cooldown_steps=args.adaptive_boost_cooldown_steps,
        # Auto Batch Sizing
        enable_auto_batch=args.enable_auto_batch,
        auto_batch_target_utilization=args.auto_batch_target_utilization,
        auto_batch_safety_margin=args.auto_batch_safety_margin,
        auto_batch_target_effective=args.auto_batch_target_effective,
        # Friction Controller
        disable_friction=args.disable_friction,
        friction_dom_high=args.friction_dom_high,
        friction_dom_low=args.friction_dom_low,
        friction_align_critical=args.friction_align_critical,
        # V9.8.0: Sovereign Reasoning Kernel (SRK)
        enable_srk=args.enable_srk,
        srk_hidden_dim=args.srk_hidden_dim,
        srk_dna_bridge_layer=args.srk_dna_bridge_layer,
        srk_csr_alignment_layer=args.srk_csr_alignment_layer,
        srk_witness_layer=args.srk_witness_layer,
        srk_synthesis_layer=args.srk_synthesis_layer,
        srk_enable_dna_bridge=not args.srk_disable_dna_bridge,
        srk_enable_witness=not args.srk_disable_witness,
        srk_enable_synthesis=not args.srk_disable_synthesis,
        srk_enable_imr=not args.srk_disable_imr,
        srk_isomorphism_threshold=args.srk_isomorphism_threshold,
        srk_karma_decay=args.srk_karma_decay,
        srk_enable_mauna=not args.srk_disable_mauna,
        srk_mauna_confidence_threshold=args.srk_mauna_confidence_threshold,
        srk_mauna_consistency_threshold=args.srk_mauna_consistency_threshold,
        # SRK Loss
        srk_lambda_f=args.srk_lambda_f,
        srk_lambda_b=args.srk_lambda_b,
        srk_lambda_c=args.srk_lambda_c,
        srk_lambda_coherence=args.srk_lambda_coherence,
        srk_lambda_entropy=args.srk_lambda_entropy,
        srk_lambda_task=args.srk_lambda_task,
        srk_enable_nidra_penalty=not args.srk_disable_nidra_penalty,
        srk_nidra_penalty_weight=args.srk_nidra_penalty_weight,
        # SRK Annealing
        srk_total_steps=args.srk_total_steps,
        srk_warmup_steps=args.srk_warmup_steps,
        srk_invert_annealing=args.srk_invert_annealing,
        # V9.8.8: Sovereign Phase Controller (SPC)
        enable_sovereign_phase_controller=args.enable_sovereign_phase_controller,
        spc_entropy_critical=args.spc_entropy_critical,
        spc_entropy_warning=args.spc_entropy_warning,
        spc_entropy_recovered=args.spc_entropy_recovered,
        spc_variance_critical=args.spc_variance_critical,
        spc_variance_warning=args.spc_variance_warning,
        spc_variance_recovered=args.spc_variance_recovered,
        spc_min_boost_duration=args.spc_min_boost_duration,
        spc_alpha=args.spc_alpha,
        spc_max_rotation=args.spc_max_rotation,
        spc_damping=args.spc_damping,
        spc_velocity_threshold=args.spc_velocity_threshold,
        # V9.8.9: Dynamic Window Scheduler (DWS)
        enable_dynamic_window=args.enable_dynamic_window,
        dws_schedule=args.dws_schedule,
        dws_growth_rate_max=args.dws_growth_rate_max,
        dws_shrink_rate_max=args.dws_shrink_rate_max,
        dws_align_to=args.dws_align_to,
        dws_smooth_steps=args.dws_smooth_steps,
        dws_min_steps_between=args.dws_min_steps_between,
        dws_hysteresis=args.dws_hysteresis,
        dws_vram_threshold=args.dws_vram_threshold,
        # Phase-JEPA Configuration
        enable_jepa=args.enable_jepa,
        jepa_hidden_dim=args.jepa_hidden_dim,
        jepa_prediction_steps=args.jepa_prediction_steps,
        jepa_num_heads=args.jepa_num_heads,
        jepa_cosine_mode=args.jepa_cosine_mode,
        # JEPA Loss Weights
        jepa_vicreg_weight=args.jepa_vicreg_weight,
        jepa_alignment_weight=args.jepa_alignment_weight,
        jepa_prediction_weight=args.jepa_prediction_weight,
        jepa_orthogonality_weight=args.jepa_orthogonality_weight,
        # JEPA Per-Component Weights
        jepa_bhava_weight=args.jepa_bhava_weight,
        jepa_semantic_weight=args.jepa_semantic_weight,
        jepa_guna_weight=args.jepa_guna_weight,
        # JEPA Target Encoder
        jepa_target_momentum=args.jepa_target_momentum,
        jepa_momentum_schedule=args.jepa_momentum_schedule,
        # JEPA Training Curriculum
        jepa_training_phase=args.jepa_training_phase,
        jepa_phase_body_steps=args.jepa_phase_body_steps,
        jepa_phase_soul_steps=args.jepa_phase_soul_steps,
        jepa_auto_phase_transition=args.jepa_auto_phase_transition,
        # JEPA Dynamic Graduation
        jepa_enable_dynamic_graduation=args.jepa_enable_dynamic_graduation,
        jepa_graduation_loss_threshold=args.jepa_graduation_loss_threshold,
        jepa_graduation_alignment_threshold=args.jepa_graduation_alignment_threshold,
        # JEPA Vritti Validation
        jepa_enable_vritti_validation=args.jepa_enable_vritti_validation,
        jepa_viparyaya_threshold=args.jepa_viparyaya_threshold,
        jepa_vikalpa_threshold=args.jepa_vikalpa_threshold,
        jepa_damping_factor=args.jepa_damping_factor,
        # JEPA-SRK Integration
        jepa_enable_karma_injection=args.jepa_enable_karma_injection,
        jepa_karma_gate_bias=args.jepa_karma_gate_bias,
        # V10.3.7: Vritti Entropy Regularization
        vritti_entropy_reg=args.vritti_entropy_reg,
        vritti_entropy_lambda=args.vritti_entropy_lambda,
        # V10.2.1: Chunking for long sequences
        enable_chunking=args.enable_chunking,
        chunk_size=args.chunk_size,
        protected_phase=args.protected_phase,
        no_protected_phase=args.no_protected_phase,
        run_chunk_diagnostic=args.run_chunk_diagnostic,
        chunk_diagnostic_seq_len=args.chunk_diagnostic_seq_len,
        enable_tbptt=args.enable_tbptt,
        # BCVF Contrastive Structural Pressure on Representations
        use_bcvf_contrastive=args.use_bcvf_contrastive,
        bcvf_contrastive_lambda=args.bcvf_contrastive_lambda,
        bcvf_contrastive_K=args.bcvf_contrastive_K,
        bcvf_contrastive_K_pool=args.bcvf_contrastive_K_pool,
        bcvf_contrastive_margin=args.bcvf_contrastive_margin,
        bcvf_contrastive_alpha=args.bcvf_contrastive_alpha,
        bcvf_contrastive_eta=args.bcvf_contrastive_eta,
        bcvf_contrastive_d_r=args.bcvf_contrastive_d_r,
        bcvf_contrastive_T_sample=args.bcvf_contrastive_T_sample,
        bcvf_contrastive_projector=args.bcvf_contrastive_projector,
        # BCVF Logit-Margin + Entropy Band (perplexity-aligned)
        use_logit_margin=args.use_logit_margin,
        logit_margin_lambda=args.logit_margin_lambda,
        logit_margin_entropy_lambda=args.logit_margin_entropy_lambda,
        logit_margin_m=args.logit_margin_m,
        logit_margin_H_min=args.logit_margin_H_min,
        logit_margin_H_max=args.logit_margin_H_max,
        logit_margin_top_k_neg=args.logit_margin_top_k_neg,
        # State-Conditional Logit Scale ("Confidence Knob") + Entropy Band
        enable_confidence_scaler=args.enable_confidence_scaler,
        confidence_s_min=args.confidence_s_min,
        confidence_s_max=args.confidence_s_max,
        confidence_epsilon=args.confidence_epsilon,
        confidence_entropy_band_min=args.confidence_entropy_band_min,
        confidence_entropy_band_max=args.confidence_entropy_band_max,
        confidence_lambda_band=args.confidence_lambda_band,
        confidence_lambda_scale=args.confidence_lambda_scale,
        confidence_enable_risk_gating=args.confidence_enable_risk_gating,
        confidence_alpha_risk=args.confidence_alpha_risk,
        confidence_vritti_kl_weight=args.confidence_vritti_kl_weight,
        # Kosha-Vritti Structured Supervision
        enable_kv_supervision=args.enable_kv_supervision,
        kv_weight_kosha_kl=args.kv_weight_kosha_kl,
        kv_weight_vritti_kl=args.kv_weight_vritti_kl,
        kv_weight_entropy_floor=args.kv_weight_entropy_floor,
        kv_weight_compatibility=args.kv_weight_compatibility,
        kv_weight_prior=args.kv_weight_prior,
        kv_entropy_floor_ratio=args.kv_entropy_floor_ratio,
        kv_compatibility_prior_path=args.kv_compatibility_prior_path,
        kv_curriculum_exclude_epochs=args.kv_curriculum_exclude_epochs,
        kv_curriculum_ramp_epochs=args.kv_curriculum_ramp_epochs,
        kv_teacher_mode=args.kv_teacher_mode,
        kv_collapse_check_interval=args.kv_collapse_check_interval,
        kv_kl_clamp_max=args.kv_kl_clamp_max,
        # Conscious Generation (Phase 1+)
        enable_conscious_generation=args.enable_conscious_generation,
        token_ontology_dim=args.token_ontology_dim,
        ontology_cache_refresh_interval=args.ontology_cache_refresh_interval,
        lambda_ont=args.lambda_ont,
        ontology_loss_type=args.ontology_loss_type,
        ontology_loss_temperature=args.ontology_loss_temperature,
        ontology_scorer_use_low_rank=args.ontology_scorer_use_low_rank,
        ontology_scorer_rank=args.ontology_scorer_rank,
        # Conscious Generation (Phase 2)
        plausibility_token_dim=args.plausibility_token_dim if args.jepa_token_dim is None else args.jepa_token_dim,
        jepa_token_dim=args.jepa_token_dim,
        csr_token_dim=args.csr_token_dim,
        primitive_shortlist_k=args.primitive_shortlist_k,
        use_low_rank_primitives=args.use_low_rank_primitives,
        primitive_rank=args.primitive_rank,
        use_shared_token_basis=args.use_shared_token_basis,
        # Conscious Generation (Phase 3)
        lambda_kosha_routing=args.lambda_kosha_routing,
        lambda_bliss_token=args.lambda_bliss_token,
        lambda_plausibility_token=args.lambda_plausibility_token if args.lambda_jepa_token is None else args.lambda_jepa_token,
        lambda_jepa_token=args.lambda_jepa_token,
        lambda_csr_token=args.lambda_csr_token,
        lambda_vritti_token=args.lambda_vritti_token,
        lambda_guna_token=args.lambda_guna_token,
        bliss_lambda_B=args.bliss_lambda_B,
        kosha_routing_init=args.kosha_routing_init,
        # Conscious Generation (Phase 3+): Governance plane
        kosha_num_domains=args.kosha_num_domains,
        kosha_interaction_rank=args.kosha_interaction_rank,
        kosha_initial_policy_scale=args.kosha_initial_policy_scale,
        kosha_bliss_scale=args.kosha_bliss_scale,
        kosha_use_kosha=not args.kosha_no_kosha,
        kosha_use_domain=not args.kosha_no_domain,
        kosha_use_interaction=not args.kosha_no_interaction,
        kosha_use_dynamic_bliss=not args.kosha_no_dynamic_bliss,
        enable_governance_probes=args.enable_governance_probes,
        # Conscious Generation (Phase 4)
        use_field_integrated_softmax=args.use_field_integrated_softmax,
        field_softmax_temperature=args.field_softmax_temperature,
        use_agreement_energy=args.use_agreement_energy,
        agreement_energy_weight=args.agreement_energy_weight,
        # Conscious Generation (Phase 5)
        enable_cg_curriculum=args.enable_cg_curriculum,
        cg_curriculum_ramp_mode=args.cg_curriculum_ramp_mode,
        cg_curriculum_ppl_var_threshold=args.cg_curriculum_ppl_var_threshold,
        cg_curriculum_stability_window=args.cg_curriculum_stability_window,
        cg_curriculum_stage_proportions=args.cg_curriculum_stage_proportions,
        enable_cg_diagnostics=args.enable_cg_diagnostics,
        # Mistral CG Wrapper
        mistral_model_name=args.mistral_model_name,
        mistral_quantize=args.mistral_quantize,
        mistral_device_map=args.mistral_device_map,
        mistral_trust_remote_code=args.mistral_trust_remote_code,
        mistral_phase_adapter_hidden=args.mistral_phase_adapter_hidden,
        # Knowledge Distillation
        distill_from_mistral=args.distill_from_mistral,
        distill_temperature=args.distill_temperature,
        distill_alpha=args.distill_alpha,
        distill_warmup_steps=args.distill_warmup_steps,
        # Factual Eval
        enable_factual_eval=args.enable_factual_eval,
        factual_eval_interval=args.factual_eval_interval,
        factual_eval_probes=args.factual_eval_probes,
        factual_eval_start_step=args.factual_eval_start_step,
        # Embedding Diagnostics
        enable_embedding_diagnostics=args.enable_embedding_diagnostics,
        embedding_diag_interval=args.embedding_diag_interval,
        embedding_diag_vocab_sample=args.embedding_diag_vocab_sample,
        embedding_diag_neighbors=args.embedding_diag_neighbors,
        embedding_diag_no_samples=args.embedding_diag_no_samples,
        embedding_diag_start_step=args.embedding_diag_start_step,
        # CG Snapshot
        cg_sample_every=args.cg_sample_every,
        # Experiential Controller
        enable_experiential_controller=args.enable_experiential_controller,
        experiential_d_model=args.experiential_d_model,
        experiential_num_regions=args.experiential_num_regions,
        experiential_lambda_temporal=args.experiential_lambda_temporal,
        experiential_lambda_coherence=args.experiential_lambda_coherence,
        experiential_lambda_latent=args.experiential_lambda_latent,
        experiential_k_r=args.experiential_k_r,
        experiential_k_m=args.experiential_k_m,
        experiential_b_p=args.experiential_b_p,
        experiential_G_base=args.experiential_G_base,
        experiential_G_min=args.experiential_G_min,
        experiential_G_max=args.experiential_G_max,
        experiential_k_dv=args.experiential_k_dv,
        experiential_k_dc=args.experiential_k_dc,
        experiential_alpha_base=args.experiential_alpha_base,
        experiential_replay_interval=args.experiential_replay_interval,
        experiential_consolidation_interval=args.experiential_consolidation_interval,
        experiential_log_interval=args.experiential_log_interval,
        experiential_loss_weight=args.experiential_loss_weight,
        experiential_warmup_steps=args.experiential_warmup_steps,
        experiential_loss_clamp=args.experiential_loss_clamp,
        # Stage 8: Perspective Synthesizer
        enable_perspective_synthesizer=args.enable_perspective_synthesizer,
        perspective_d_synthesis=args.perspective_d_synthesis,
        perspective_gate_init=args.perspective_gate_init,
        perspective_log_interpretive=args.perspective_log_interpretive,
        # Stage 9: Attention Mechanism Ablation Audit
        ablation_disable_phase_sync=args.ablation_disable_phase_sync,
        ablation_disable_vritti=args.ablation_disable_vritti,
        ablation_disable_guna_bias=args.ablation_disable_guna_bias,
        ablation_enable_dual_channel_intent=args.ablation_enable_dual_channel_intent,
        ablation_log_mechanism_strength_every=args.ablation_log_mechanism_strength_every,
        run_ablation_audit=args.run_ablation_audit,
    )

    # ==========================================================================
    # PHASE-FIRST CURRICULUM: Enable sub-components when master flag is set
    # ==========================================================================
    if config.phase_first_curriculum:
        print("\n" + "=" * 70)
        print("  PHASE-FIRST CURRICULUM ENABLED")
        print("  Configuring optimal phase-first learning settings...")
        print("=" * 70)

        # Enable PPL-alpha curriculum (phase high when PPL high)
        if not config.enable_ppl_alpha_curriculum:
            config.enable_ppl_alpha_curriculum = True
            print("  ✓ PPL-Alpha Curriculum: ENABLED (phase dominates when PPL high)")

        # Enable adaptive window (small early, large later)
        if not config.enable_adaptive_window:
            config.enable_adaptive_window = True
            print(f"  ✓ Adaptive Window: ENABLED ({config.window_size_high_ppl}→{config.window_size_low_ppl})")

        # Enable SRK with inverted annealing (strong early, ramp down)
        if not config.enable_srk:
            config.enable_srk = True
            print("  ✓ SRK: ENABLED (auxiliary phase support)")
        if not config.srk_invert_annealing:
            config.srk_invert_annealing = True
            print("  ✓ SRK Annealing: INVERTED (strong→weak for phase-first)")

        # Summary
        print("-" * 70)
        print(f"  Phase-First Schedule:")
        print(f"    PPL >= {config.ppl_high_threshold}: alpha_phase={config.alpha_phase_ppl_high}, window={config.window_size_high_ppl}, SRK=STRONG")
        print(f"    PPL <= {config.ppl_low_threshold}: alpha_phase={config.alpha_phase_ppl_low}, window={config.window_size_low_ppl}, SRK=WEAK")
        print("=" * 70 + "\n")

    # V9.8.0: Build SRK config from legacy flags (backward compatibility)
    srk_config, srk_warnings = build_srk_config_from_legacy(args, config)
    for warning in srk_warnings:
        print(warning)

    # Train
    train(config)


if __name__ == "__main__":
    main()
