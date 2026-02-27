"""
Centralized imports and availability flags.

All optional dependencies use try/except with fallback flags.
Other modules import availability flags from here.
"""

import math
import os
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set
from enum import Enum
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# Entropy-based logit scale control
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from symbolu.training.entropy_control import (
    EntropyControlConfig,
    LogitScaleModule,
    AdaptiveEntropyController,
    topk_entropy,
    attach_logit_scale,
    log_entropy_metrics,
)


# =============================================================================
# SRK (SOVEREIGN REASONING KERNEL) IMPORTS
# =============================================================================
# V10.3.0: Enable SRK to monitor how phase learning progresses at different layers
# SRK provides auxiliary components at:
#   - L4: DNA Bridge (Foundational Ontology)
#   - L7: CSR Alignment Phase Extraction Hook
#   - L9: Witness Arbitrator (Consciousness/Attention)
#   - L11: Synthesis Gate (Output Integration)

try:
    from symbolu.sovereign import (
        SRKConfig,
        SovereignReasoningKernel,
        OntologicalBridge,
        WitnessArbitrator,
        SynthesisGate,
        PhaseExtractionHook,
        SOVEREIGN_STATE_DIM,
        BHAVA_NAMES,
        KOSHA_NAMES,
        VRITTI_NAMES,
        GUNA_NAMES,
    )
    from symbolu.sovereign.sovereign_loss import (
        SovereignLossConfig as SRKLossConfig,
        SovereignLoss as SRKLoss,
        SovereignAnnealer,
    )
    SRK_AVAILABLE = True
except ImportError as e:
    SRK_AVAILABLE = False
    SOVEREIGN_STATE_DIM = 32  # Fallback: 12 Bhava + 5 Kosha + 5 Vritti + 6 Guna + 4 Reserved
    PHASE_STATE_DIM = 12     # V11.0.0: Bhava-only for phase rotation
    print(f"Note: SRK modules not available for import: {e}")
    print("      SRK phase learning will use local implementations.")


# =============================================================================
# KOSHA SYSTEM IMPORTS (V10.3.4)
# =============================================================================
# The 5-layer Kosha model (from Vedantic philosophy):
#   - Annamaya (Physical/Material): Token/syntax grounding
#   - Pranamaya (Vital/Energy): Gradient/attention flow
#   - Manomaya (Mental): Semantic binding
#   - Vijnanamaya (Intellectual/Wisdom): Abstract reasoning
#   - Anandamaya (Blissful): Coherence/integration

try:
    from symbolu.losses.kosha_gyroscope import (
        KoshaGyroscopicLoss,
        KoshaPhaseCorrector,
        KoshaPhaseCorrectorConfig,
    )
    from symbolu.sovereign.reasoning_kernel import KoshaShiftController
    KOSHA_AVAILABLE = True
except ImportError as e:
    KOSHA_AVAILABLE = False
    print(f"Note: Kosha modules not available for import: {e}")
    print("      Kosha system will use local implementations.")

# Kosha names and indices in 32D Sovereign State
KOSHA_NAMES = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
KOSHA_VEDIC_NAMES = ['Annamaya', 'Pranamaya', 'Manomaya', 'Vijnanamaya', 'Anandamaya']
KOSHA_INDICES = {
    'MATERIAL': 12, 'VITAL': 13, 'MENTAL': 14, 'INTELLECTUAL': 15, 'BLISSFUL': 16
}
KOSHA_SLICE = slice(12, 17)  # Indices [12:17] in 32D state


# =============================================================================
# TEXT INTERFERENCE IMPORTS (V10.5)
# =============================================================================
# Interference-aware proposal scoring for text LLMs.
# Key features:
#   - Task classification (compositional vs factual/code)
#   - Lower lambda (0.01-0.03) than vision (0.05-0.08)
#   - Entropy gating (only when proposals are uncertain)
#   - Late decoding only (min step requirement)

try:
    from symbolu.text_interference import (
        TextInterferenceConfig,
        TextInterferencePolicy,
        TextInterferenceScorer,
        TaskClassifier,
        InterferenceMode,
        BCVFTextScorer,
        text_interference_rescore,
    )
    TEXT_INTERFERENCE_AVAILABLE = True
except ImportError as e:
    TEXT_INTERFERENCE_AVAILABLE = False
    print(f"Note: Text interference modules not available for import: {e}")
    print("      Interference benchmarks will use local implementations.")


# =============================================================================
# MOE FFN IMPORTS (V10.6)
# =============================================================================
# Mixture of Experts FFN for compute efficiency (Mixtral-style).
# Key features:
#   - Lightweight router (single linear layer)
#   - Top-K expert selection (default: top-2 of 8)
#   - Load balance loss for uniform utilization
#   - ~2x compute savings with similar quality

try:
    from symbolu.moe_ffn import (
        MoEFFN,
        MoEConfig,
        MoEFFNBenchmark,
        create_moe_ffn,
    )
    MOE_FFN_AVAILABLE = True
except ImportError as e:
    MOE_FFN_AVAILABLE = False
    print(f"Note: MoE FFN modules not available for import: {e}")
    print("      MoE benchmarks will use local implementations.")

# =============================================================================
# V10.7: HIERARCHICAL PHASE-QUAD (HP-QUAD)
# =============================================================================
# Multi-timescale processing inspired by HM-RNN (Chung et al., 2016).
# Key features:
#   - Boundary detection for adaptive update frequency
#   - Multi-level Phase Integrator (fast/medium/slow)
#   - Hierarchical Quad Proposal with multi-granularity retrieval
#   - Top-down modulation from slow to fast layers

try:
    from symbolu.hp_quad import (
        HPQuadBlock,
        HPQuadConfig,
        HPQuadBenchmark,
        HierarchicalPhaseIntegrator,
        HierarchicalQuadProposal,
        BoundaryDetector,
        create_hp_quad,
    )
    HP_QUAD_AVAILABLE = True
except ImportError as e:
    HP_QUAD_AVAILABLE = False
    print(f"Note: HP-Quad modules not available for import: {e}")
    print("      HP-Quad benchmarks will be skipped.")

# =============================================================================
# V10.8: RLM-PHASE-QUAD INTEGRATION
# =============================================================================
# Combines Recursive Language Models (RLM) orchestration with Phase-Quad
# efficient processing for unlimited context handling.
# Key features:
#   - Unlimited context via RLM decomposition (10M+ tokens)
#   - O(n) sub-query processing with Phase-Quad
#   - Persistent Phase State across recursive calls
#   - Semantic chunking via HP-Quad boundary detection
#   - Quality-aware recursion with Reflective validation

try:
    from symbolu.rlm_phase_quad import (
        RLMPhaseQuadSystem,
        RLMPhaseQuadConfig,
        RLMPhaseQuadBenchmark,
        REPLEnvironment,
        PhaseStateManager,
        BoundaryAwareChunker,
        MemoryBankSynchronizer,
        QualityAwareRecursionController,
        create_rlm_phase_quad,
    )
    RLM_PHASE_QUAD_AVAILABLE = True
except ImportError as e:
    RLM_PHASE_QUAD_AVAILABLE = False
    print(f"Note: RLM-Phase-Quad modules not available for import: {e}")
    print("      RLM-Phase-Quad benchmarks will be skipped.")


# =============================================================================
# V10.9: REFLECTIVE PHASE-QUAD
# =============================================================================
# Self-reflective extension enabling autonomous solution refinement.
# Key features:
#   - Neural Critic (Process Reward Model) for quality estimation
#   - Decision Gate for output vs revise logic
#   - Revision Encoder for latent-space revision context
#   - Internal revision loop with quality thresholds
#   - Adaptive compute allocation (think harder when needed)
#
# Advantages over o1-style token-based reasoning:
#   - O(N) per revision vs O(N^2) for token-based
#   - Constant memory (Phase state) vs linear growth (context)
#   - Latent-space revision (efficient) vs token-space (expensive)

try:
    from symbolu.reflective_phase_quad import (
        ReflectivePhaseQuadBlock,
        ReflectivePhaseQuadModel,
        ReflectivePhaseQuadConfig,
        ReflectivePhaseQuadBenchmark,
        ReflectivePhaseState,
        ReflectiveCritic,
        DecisionGate,
        RevisionEncoder,
        QualityCritique,
        create_reflective_phase_quad,
        create_reflective_model,
    )
    REFLECTIVE_PHASE_QUAD_AVAILABLE = True
except ImportError as e:
    REFLECTIVE_PHASE_QUAD_AVAILABLE = False
    print(f"Note: Reflective Phase-Quad modules not available for import: {e}")
    print("      Reflective Phase-Quad benchmarks will be skipped.")


# =============================================================================
# V10.10: CAUSAL WORLD MODEL
# =============================================================================
# True causal AI with explicit causal graphs, intervention modeling,
# and world simulation capabilities.
# Key features:
#   - Explicit Causal Graphs - DAG structure learning (NOTEARS-style)
#   - Intervention Modeling - do-calculus (P(Y|do(X)))
#   - World State Simulation - Multi-step rollouts
#   - Counterfactual Reasoning - "What if X had been different?"
#
# Advantages over standard LLMs:
#   - Distinguishes correlation from causation
#   - Handles interventions correctly (not just conditioning)
#   - Counterfactual reasoning with proper abduction

try:
    from symbolu.causal_world_model import (
        CausalWorldModel,
        CausalWorldModelConfig,
        CausalWorldModelBenchmark,
        CausalGraphLayer,
        CausalGraph,
        WorldState,
        WorldStateModule,
        InterventionModule,
        CounterfactualReasoner,
        WorldSimulator,
        CausalPhaseQuadBlock,
        CausalState,
        DAGConstraint,
        create_causal_world_model,
    )
    CAUSAL_WORLD_MODEL_AVAILABLE = True
except ImportError as e:
    CAUSAL_WORLD_MODEL_AVAILABLE = False
    print(f"Note: Causal World Model modules not available for import: {e}")
    print("      Causal World Model benchmarks will be skipped.")


# =============================================================================
# CAUSAL DATASETS (COPA, e-CARE, Synthetic SCM)
# =============================================================================
# Datasets with known causal structure for training and evaluating
# the Causal World Model:
#   - COPA: Choice of Plausible Alternatives (commonsense causal reasoning)
#   - e-CARE: Explainable Causal Reasoning with explanations
#   - Synthetic SCM: Structural Causal Models with ground-truth graphs

try:
    from symbolu.causal_datasets import (
        CausalDataLoader,
        CausalDatasetConfig,
        CausalTorchDataset,
        CausalExample,
        COPADataset,
        ECareDataset,
        SyntheticSCMDataset,
        create_causal_dataloader,
        load_copa,
        load_ecare,
        load_synthetic_scm,
    )
    CAUSAL_DATASETS_AVAILABLE = True
except ImportError as e:
    CAUSAL_DATASETS_AVAILABLE = False
    print(f"Note: Causal Datasets modules not available for import: {e}")
    print("      Causal dataset benchmarks will use synthetic data.")


# =============================================================================
# SPATIAL-CAUSAL MODULE (V10.11)
# =============================================================================
# Extends Causal World Model with spatial reasoning capabilities:
#   - Spatial state tracking (position, orientation, velocity, scale)
#   - Physics-grounded causal edges (gravity, contact, collision, propagation)
#   - Spatial intervention operators (move, rotate, place, remove)
#   - Spatial counterfactual reasoning

try:
    from symbolu.spatial_causal_module import (
        # Config
        SpatialCausalConfig,
        # Enums
        SpatialRelation,
        PhysicsCausalType,
        InterventionType,
        # Data structures
        SpatialObject,
        SpatialRelationEdge,
        PhysicsCausalEdge,
        SpatialWorld,
        SpatialIntervention,
        SpatialCausalState,
        # Core modules
        SpatialStateEncoder,
        SpatialRelationPredictor,
        PhysicsCausalLayer,
        SpatialInterventionModule,
        PhysicsSimulator,
        SpatialCounterfactualReasoner,
        SpatialCausalPhaseQuadBlock,
        SpatialCausalModule,
        # Benchmark
        SpatialCausalBenchmark,
        # Factory
        create_spatial_causal_module,
        create_test_world_with_scenario,
    )
    SPATIAL_CAUSAL_AVAILABLE = True
except ImportError as e:
    SPATIAL_CAUSAL_AVAILABLE = False
    print(f"Note: Spatial-Causal Module not available for import: {e}")
    print("      Spatial-Causal benchmarks will be skipped.")


# =============================================================================
# PHASE-AWARE ADAPTATION: IA³ + SURGICAL LORA (V10.12)
# =============================================================================
# Controlled plasticity for Phase Quad:
#   - IA³ (primary): Multiplicative scaling on attention/quad/FFN outputs
#     Architecturally congruent with existing AdaLN-Zero gates
#   - LoRA (secondary, surgical): Low-rank deltas ONLY on projections
#     Never on MLP, residual paths, or phase gates
#
# Design hierarchy:
#   1. IA³ inside Phase Quad (default) — controlled amplification
#   2. LoRA on projections only (optional, constrained)
#   3. No classic adapters anywhere — conflicts with zero-init + phase math

try:
    from symbolu.vision.adaptation import (
        IA3Gate,
        IA3BlockGates,
        IA3Config,
        LoRALinear,
        LoRAConfig,
        AdaptationConfig,
        PhaseQuadAdaptationManager,
    )
    ADAPTATION_AVAILABLE = True
except ImportError as e:
    ADAPTATION_AVAILABLE = False
    print(f"Note: Adaptation modules not available for import: {e}")
    print("      Adaptation benchmarks will use local implementations.")


# =============================================================================
# NO-WRITE CONTRACTS (V10.6.2)
# =============================================================================
# From ChatGPT Gap Analysis (Appendix D.5):
#
# The Contract in One Sentence:
#   "intent_phase (and any control) must be low-dimensional, broadcastable,
#    and not token-position dependent."
#
# What We Want to PREVENT:
#   - Token-wise content being injected into Phase control
#   - Control signals that have sequence length dimension
#   - Control signals that have d_model as last dimension
#
# What We Want to ALLOW:
#   - Scalars or per-head/per-layer control: [layers, heads], [batch, heads], [heads]
#   - Broadcastable scalars
#   - Shapes like [B, H, 1, 1] that broadcast correctly
#
# This is the "highest value gap fix" per ChatGPT analysis.

# Global flag to enable/disable contract enforcement (for performance)
_ENFORCE_NO_WRITE_CONTRACTS = True

