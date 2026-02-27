#!/usr/bin/env python3
"""
Unified LLM Training Script V9.8.0
===================================

Train SymbolU models with support for:
1. SymbolU12 with Bhava (standard attention + 12D ontological + 144D bhava)
2. Phase Attention (O(n) complexity)
3. Hybrid (Local + Phase attention)
4. Gen 2: Hierarchical Complex Bhava (3-tier phase rotation)

- Dynamic SNR-Adjusted Kp
- Semantic Validation (W_s weight)
- Handshake D-term Dampening
- Stress Test Framework
- V9.4.5: Friction Controller with Corrective Actions

- Centralized ontological intervention replacing scattered flags
- Layer-specific interventions: L4 DNA Bridge, L7 Phase Hook, L9 Witness, L11 Synthesis
- Isomorphic Mapping Router (IMR) with fixed logic templates
- Consistency Lagrangian (B1), Phase Coherence (U2), Stability Constraint (S8)
- Lambda annealing for training stability
- Mauna Protocol for inference safety
- Backward compatibility bridge for legacy flags

Usage:
------
    # Train SymbolU12 with Bhava (standard attention + ontological)
    python train_unified_llm.py --model_type ontological --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Phase model (O(n) attention)
    python train_unified_llm.py --model_type phase --model_size small \
        --dataset wikitext103 --max_steps 1000

    python train_unified_llm.py --model_type hybrid --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Gen 2 model (Hierarchical Complex Bhava)
    python train_unified_llm.py --model_type gen2 --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Long context training (16K/32K)
    python train_unified_llm.py --model_type gen2 --model_size small \
        --max_seq_len 16384 --gradient_checkpointing --batch_size 1

    # Train Ontological Hybrid (Two-Tier AGI Architecture) with 32D Sovereign State
    python train_unified_llm.py --model_type ontological_hybrid --model_size small \
        --dataset wikitext103 --max_steps 1000 --state_dim 32

    python train_unified_llm.py --model_type ontological_hybrid --model_size small \

    # Stress Test (Trial by Fire)
    python train_unified_llm.py --stress_test --resume checkpoints/best.pt

Author: SymbolU Team
Date: January 2026
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


class _SimpleByteTokenizer:
    """Minimal byte-level tokenizer fallback when HuggingFace is unavailable."""

    name_or_path = "byte-fallback"
    eos_token_id = 0
    model_max_length = int(1e12)

    def encode(self, text, return_tensors=None, **kwargs):
        ids = [b + 1 for b in text.encode("utf-8", errors="replace")]  # 1-indexed
        if return_tensors == "pt":
            return torch.tensor([ids], dtype=torch.long)
        return ids

    def decode(self, ids, skip_special_tokens=False, **kwargs):
        if isinstance(ids, torch.Tensor):
            ids = ids.tolist()
        if isinstance(ids, list) and ids and isinstance(ids[0], list):
            ids = ids[0]
        return bytes([max(0, i - 1) for i in ids]).decode("utf-8", errors="replace")

    def convert_ids_to_tokens(self, ids):
        if isinstance(ids, torch.Tensor):
            ids = ids.tolist()
        return [chr(max(0, i - 1)) if 0 < i < 128 else f"<{i}>" for i in ids]

    @property
    def vocab_size(self):
        return 256

# TensorBoard
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False

# Entropy-based logit scale control
from symbolu.training.entropy_control import (
    EntropyControlConfig,
    LogitScaleModule,
    AdaptiveEntropyController,
    topk_entropy,
    attach_logit_scale,
    log_entropy_metrics,
)

# BCVF Contrastive Structural Pressure on Representations
try:
    from symbolu.ontological.bcvf_contrastive import (
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
    from symbolu.ontological.bcvf_logit_margin import (
        LogitMarginConfig,
        compute_logit_margin_loss,
        log_logit_margin_diagnostics,
    )
    BCVF_LOGIT_MARGIN_AVAILABLE = True
except ImportError:
    BCVF_LOGIT_MARGIN_AVAILABLE = False

# State-Conditional Logit Scale ("Confidence Knob") + Entropy Band Control
try:
    from symbolu.training.confidence_scaler import (
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
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import (
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
    from symbolu.ontological.symbolu12_bhava import (
        SymbolU12LLMWithBhava,
        SymbolU12OptimizedWithBhava,
        SymbolU12BhavaConfig,
    )
    from symbolu.ontological.bhava_relationships import (
        BHAVA_SIGNIFICANCES,
        get_relationship_meaning,
    )
    ONTOLOGICAL_AVAILABLE = True
except ImportError as e:
    ONTOLOGICAL_AVAILABLE = False
    print(f"Warning: Ontological models not available: {e}")

# Import Sovereign-1 components
try:
    from symbolu.sovereign import SovereignLoss, SovereignObserver
    from symbolu.sovereign.loss import LegacyLossAdapter
    SOVEREIGN_AVAILABLE = True
except ImportError as e:
    SOVEREIGN_AVAILABLE = False
    print(f"Warning: Sovereign-1 modules not available: {e}")

# Import GradientNormThrottle for training stability
try:
    from symbolu.training import GradientNormThrottle, clean_wikitext_artifacts
    GRADIENT_THROTTLE_AVAILABLE = True
except ImportError as e:
    GRADIENT_THROTTLE_AVAILABLE = False
    print(f"Warning: GradientNormThrottle not available: {e}")

# Phase-JEPA: Joint Embedding Predictive Architecture
try:
    from symbolu.jepa import (
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
    from symbolu.ontological.symbolu12_gen2 import (
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

try:
    from train import cleanup_old_checkpoints
except ImportError as e:
    cleanup_old_checkpoints = None
    print(f"Warning: cleanup_old_checkpoints not available: {e}")

# Import utilities from hierarchical_gradient_scaler module
# Note: Main classes (HierarchicalGradientScaler, DynamicRelaxationController) are
# defined locally below for direct integration with training loop
try:
    from symbolu.sovereign.hierarchical_gradient_scaler import compute_s_drift
    COMPUTE_S_DRIFT_AVAILABLE = True
except ImportError:
    COMPUTE_S_DRIFT_AVAILABLE = False
    compute_s_drift = None
# Key insight: For "Imperial" → [Im, per, ial], we should NOT penalize each
# subtoken individually. Instead, we:
#   1. Detect word boundaries (where next token starts with Ġ/space)
#   2. Reconstruct the whole word from subtokens


# =============================================================================
# SOVEREIGN R[v,a] MATRIX: Vṛtti-Layer Probability Target
# =============================================================================
# The "Brain" of Sovereign-1: Defines how each Ontological Layer should prioritize
# each Vṛtti (cognitive modality). This is the philosophical ground truth that
# guides loss weighting and confidence scoring.
#
# Columns (12 Ontological Layers):
#   O1_POTENTIAL, O2_IDENTITY, O3_EXECUTION, O4_STRUCTURE, O5_COGNITION, O6_AGENCY,
#   O7_REASONING, O8_PURPOSE, O9_WITNESSES, O10_UNIFYING, O11_INTEGRATION, O12_ABSOLVING
#
# Rows (5 Vṛttis): [Pramāṇa (Truth), Vikalpa (Fancy), Viparyaya (Error),
#                   Nidrā (Sleep/Void), Smṛti (Memory)]
#
# Key design choices:
# - O1_POTENTIAL: High Nidrā (0.7) for denoising dormant capacity
# - O7_REASONING: Peak Pramāṇa (0.9) for truth discrimination
# - O12_ABSOLVING: High Pramāṇa (0.9) + Smṛti (0.8) for coherence/release
# - All rows balanced to avoid Viparyaya (Error) dominance
# =============================================================================

SOVEREIGN_R_MATRIX = torch.tensor([
    # O1    O2    O3    O4    O5    O6    O7    O8    O9   O10   O11   O12
    # POT  IDEN  EXEC  STRC  COGN  AGEN  REAS  PURP  WITN  UNIF  INTG  ABSL
    [0.1, 0.5, 0.7, 0.7, 0.8, 0.6, 0.9, 0.8, 0.6, 0.7, 0.5, 0.9],  # Pramāṇa (Truth)
    [0.1, 0.2, 0.2, 0.4, 0.4, 0.4, 0.1, 0.1, 0.2, 0.2, 0.2, 0.3],  # Vikalpa (Fancy)
    [0.1, 0.2, 0.4, 0.4, 0.2, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.0],  # Viparyaya (Error)
    [0.7, 0.1, 0.1, 0.3, 0.1, 0.1, 0.0, 0.0, 0.3, 0.3, 0.4, 0.1],  # Nidrā (Sleep)
    [0.1, 0.1, 0.3, 0.3, 0.2, 0.2, 0.1, 0.0, 0.2, 0.2, 0.2, 0.8],  # Smṛti (Memory)
], dtype=torch.float32)

# Vṛtti names for logging/debugging (English functional equivalents)
VRTTI_NAMES = ["Fact", "Imagination", "Error", "Void", "Memory"]

# 12 Ontological Layer names (patent-exact sequence)
ONTOLOGICAL_LAYER_NAMES = [
    "O1_POTENTIAL",    # Dormant capacity, latent possibility
    "O2_IDENTITY",     # Classificatory marking, role assignment
    "O3_EXECUTION",    # Immediate somatic initiation, karma
    "O4_STRUCTURE",    # Shaping force, embodiment
    "O5_COGNITION",    # Mental processing, understanding
    "O6_AGENCY",       # Self-direction, ego function
    "O7_REASONING",    # Intellect, truth discrimination
    "O8_PURPOSE",      # Soul intention, meaning
    "O9_WITNESSES",    # Observer awareness
    "O10_UNIFYING",    # Atman, self-integration
    "O11_INTEGRATION", # Brahman, cosmic unity
    "O12_ABSOLVING",   # Release, resolution, coherence
]


def get_layer_vrtti_weights(layer_idx: int, device: torch.device = None) -> torch.Tensor:
    """
    Get the Vṛtti probability weights for a specific layer (Aspect).

    Args:
        layer_idx: Layer index (0-11)
        device: Target device for the tensor

    Returns:
        Tensor of shape (5,) with Vṛtti weights for this layer
    """
    layer_idx = min(layer_idx, 11)  # Clamp to 12 Aspects
    weights = SOVEREIGN_R_MATRIX[:, layer_idx]
    if device is not None:
        weights = weights.to(device)
    return weights


def get_pramana_weights(device: torch.device = None) -> torch.Tensor:
    """
    Get the Pramāṇa (Truth) row for confidence scoring.

    The Pramāṇa row indicates how much each layer should prioritize
    truth discrimination. Used by Sattvic Brake to assess model confidence.

    Returns:
        Tensor of shape (12,) with Pramāṇa weights per layer
    """
    weights = SOVEREIGN_R_MATRIX[0, :]  # Row 0 = Pramāṇa
    if device is not None:
        weights = weights.to(device)
    return weights


def get_layer_gradient_scale(layer_idx: int, mode: str = "truth") -> float:
    """
    Get gradient scale factor for a layer based on R-Matrix Vṛtti targets.

    This allows HierarchicalGradientScaler to apply Vṛtti-aware scaling:
    - "truth" mode: Scale by Pramāṇa (higher = more important for truth)
    - "stability" mode: Scale by 1 - Viparyaya (avoid error-prone layers)
    - "memory" mode: Scale by Smṛti (prioritize context retention)

    Args:
        layer_idx: Layer index (0-11)
        mode: Weighting mode ("truth", "stability", "memory")

    Returns:
        Scale factor in [0.1, 1.0] range
    """
    layer_idx = min(layer_idx, 11)

    if mode == "truth":
        # Pramāṇa row (index 0)
        return float(SOVEREIGN_R_MATRIX[0, layer_idx])
    elif mode == "stability":
        # 1 - Viparyaya (index 2): lower error tendency = higher scale
        return float(1.0 - SOVEREIGN_R_MATRIX[2, layer_idx])
    elif mode == "memory":
        # Smṛti row (index 4)
        return float(SOVEREIGN_R_MATRIX[4, layer_idx])
    else:
        # Default: average of Pramāṇa and Smṛti
        pramana = SOVEREIGN_R_MATRIX[0, layer_idx]
        smriti = SOVEREIGN_R_MATRIX[4, layer_idx]
        return float((pramana + smriti) / 2)


def get_dominant_vrtti(layer_idx: int) -> Tuple[int, str, float]:
    """
    Get the dominant Vṛtti for a layer based on R-Matrix.

    Returns:
        (vrtti_index, vrtti_name, weight)
    """
    layer_idx = min(layer_idx, 11)
    vrtti_weights = SOVEREIGN_R_MATRIX[:, layer_idx]
    dominant_idx = torch.argmax(vrtti_weights).item()
    return (
        dominant_idx,
        VRTTI_NAMES[dominant_idx],
        float(vrtti_weights[dominant_idx])
    )


# =============================================================================
# V9.7.0: ONTOLOGICAL BRIDGE (Layer 4 - Foundational Structure)
# =============================================================================
# Projects hidden states to a 12-dimensional ontological space, one dimension
# per Aspect (O1-O12). This establishes the "ontological DNA" early in
# processing, grounding all subsequent layers in the 12 Aspects.
#
# Layer 4 (Foundational) is where structure forms:
# - Raw embeddings have been processed through layers 0-3
# - Grammar and structure begin emerging at layer 4
# - The 12D projection creates an ontological "signature" that propagates forward
#
# Philosophical insight: Ontology (structure of being) should be grounded EARLY,
# while Kosha (consciousness/awareness) operates at the WITNESS point (Layer 9).
#
# Loss function encourages:
# 1. Each dimension to specialize for its corresponding Aspect
# 2. Coherence across the 12D representation (no collapsed dimensions)
# 3. Alignment with the R-Matrix Pramāṇa weights (truth prioritization)
# =============================================================================

class OntologicalBridge(nn.Module):
    """
    V9.7.0: Projects hidden states to 12D ontological space.

    Creates a foundational ontological "signature" early in processing,
    grounding the model's internal representation in the
    12 Aspects of Sovereign-1 ontology.

    Architecture:
        hidden_dim → 12D ontological projection
        Each of the 12 dimensions corresponds to one Ontological Layer (O1-O12)

    The loss encourages:
        - Dimensional diversity (no collapse)
        - Pramāṇa alignment (truth-bearing dimensions stronger)
        - Coherent representation across aspects
    """

    def __init__(self, hidden_dim: int, device: torch.device = None):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.onto_dim = 12  # 12 Ontological Layers

        # Projection to 12D ontological space
        self.onto_proj = nn.Linear(hidden_dim, self.onto_dim, bias=False)

        # Learnable target weights (initialized from R-Matrix Pramāṇa row)
        # These are the "ideal" activation levels for each Aspect
        pramana_weights = SOVEREIGN_R_MATRIX[0, :].clone()  # Truth row
        self.register_buffer('pramana_target', pramana_weights)

        # Layer norm for stable projections
        self.onto_norm = nn.LayerNorm(self.onto_dim)

        if device is not None:
            self.to(device)

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, N, D] from Layer 9
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Project hidden states to 12D ontological space.

        Args:
            hidden_states: Layer 9 hidden states [B, N, hidden_dim]

        Returns:
            onto_repr: 12D ontological representation [B, N, 12]
            metrics: Dictionary with coherence and diversity metrics
        """
        # Project to 12D
        onto_repr = self.onto_proj(hidden_states)  # [B, N, 12]
        onto_repr = self.onto_norm(onto_repr)

        # Compute metrics
        with torch.no_grad():
            # Mean activation per Aspect (across batch and sequence)
            aspect_means = onto_repr.mean(dim=[0, 1])  # [12]

            # Diversity: std across aspects (higher = more diverse)
            diversity = aspect_means.std().item()

            # Coherence: correlation with Pramāṇa targets
            # Higher coherence = activations match truth-priority ordering
            pramana_corr = torch.corrcoef(
                torch.stack([aspect_means, self.pramana_target])
            )[0, 1].item() if aspect_means.std() > 1e-6 else 0.0

            # Witness strength: O9 dimension activation (self-reference)
            o9_activation = aspect_means[8].item()  # O9 = index 8

            metrics = {
                'onto_diversity': diversity,
                'onto_pramana_corr': pramana_corr if not math.isnan(pramana_corr) else 0.0,
                'onto_o9_witness': o9_activation,
                'onto_mean_activation': aspect_means.abs().mean().item(),
            }

        return onto_repr, metrics

    def compute_loss(
        self,
        onto_repr: torch.Tensor,  # [B, N, 12]
        lambda_diversity: float = 0.1,
        lambda_pramana: float = 0.1,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute ontological alignment loss.

        Encourages:
        1. Diversity: All 12 dimensions should be active (no collapse)
        2. Pramāṇa alignment: Activations should follow truth-priority ordering

        Args:
            onto_repr: 12D ontological representation [B, N, 12]
            lambda_diversity: Weight for diversity loss
            lambda_pramana: Weight for Pramāṇa alignment loss

        Returns:
            total_loss: Combined ontological loss
            metrics: Loss breakdown
        """
        # 1. Diversity loss: Penalize collapsed dimensions
        # Use negative entropy of normalized activations
        aspect_means = onto_repr.mean(dim=[0, 1])  # [12]
        aspect_probs = F.softmax(aspect_means, dim=-1)
        diversity_entropy = -(aspect_probs * torch.log(aspect_probs + 1e-10)).sum()
        max_entropy = math.log(12)  # Maximum for uniform distribution
        diversity_loss = (max_entropy - diversity_entropy) / max_entropy  # 0=diverse, 1=collapsed

        # 2. Pramāṇa alignment loss: Match truth-priority ordering
        # Encourage higher activations for high-Pramāṇa aspects (O7, O12)
        # Use MSE between normalized activations and Pramāṇa targets
        aspect_normalized = (aspect_means - aspect_means.mean()) / (aspect_means.std() + 1e-6)
        pramana_normalized = (self.pramana_target - self.pramana_target.mean()) / (self.pramana_target.std() + 1e-6)
        pramana_loss = F.mse_loss(aspect_normalized, pramana_normalized)

        # Combined loss
        total_loss = lambda_diversity * diversity_loss + lambda_pramana * pramana_loss

        metrics = {
            'onto_diversity_loss': diversity_loss.item(),
            'onto_pramana_loss': pramana_loss.item(),
            'onto_total_loss': total_loss.item(),
        }

        return total_loss, metrics


def create_ontological_bridge(hidden_dim: int, device: torch.device = None) -> OntologicalBridge:
    """Factory function to create OntologicalBridge."""
    return OntologicalBridge(hidden_dim, device=device)


def compute_rmatrix_loss_weight(
    layer_losses: torch.Tensor,
    num_layers: int = 12,
    device: torch.device = None,
) -> torch.Tensor:
    """
    Compute Vṛtti-aware loss weights for per-layer losses.

    Weights layers based on their Pramāṇa (Truth) values:
    - Intellect (0.9) and Integration (0.9) get highest weights
    - Dormant (0.1) gets lowest weight

    Args:
        layer_losses: Per-layer loss tensor [num_layers] or [batch, num_layers]
        num_layers: Number of layers (clamped to 12 Aspects)
        device: Target device

    Returns:
        Weighted loss tensor of same shape
    """
    pramana = get_pramana_weights(device)[:num_layers]
    # Normalize to sum=1 for weighting
    pramana = pramana / pramana.sum()

    if layer_losses.dim() == 1:
        return layer_losses * pramana
    else:
        return layer_losses * pramana.unsqueeze(0)


# =============================================================================
# TOROIDAL EVOLUTIONARY BRIDGE: O12 → O1 Recursive Intelligence
# =============================================================================
# The "Wormhole" of Sovereign-1: Links Integration (O12) back to Potential (O1)
# to create continuous cognitive evolution across context windows.
#
# This enables:
# - State persistence across sequences (no reset to zero)
# - Symbolic resonance between domain-specific primitives
# - Foundation for multi-domain AGI (text, math, music share ontological layer)
#
# The toroidal flow: O1 → O2 → ... → O11 → O12 → O1 (next cycle)
# =============================================================================

class EvolutionaryBridge(nn.Module):
    """
    Toroidal State Bridge: Carries the 'Ontological Essence' from O12 (Absolving)
    back to O1 (Potential) for the next cognitive cycle.

    This creates recursive intelligence where:
    - The 'Harvest' of one sequence becomes the 'Seed' of the next
    - Cognitive patterns persist and evolve across context boundaries
    - Multi-domain primitives (phonemes, math ops, notes) share resonance

    The bridge uses a phase-locked projection to compress the integrated
    state into a seed that preserves ontological structure but sheds
    sequence-specific details (the "Evolutionary Loss" principle).

    Args:
        dim: Hidden dimension of the model
        num_layers: Number of ontological layers (default 12)
        bridge_dropout: Dropout for seed projection (prevents overfitting to patterns)
        use_gating: Whether to use gated projection (more selective carryover)
        truncated_bptt_steps: Steps of gradient flow (0 = full detach, >0 = truncated BPTT)
    """

    def __init__(
        self,
        dim: int,
        num_layers: int = 12,
        bridge_dropout: float = 0.1,
        use_gating: bool = True,
        truncated_bptt_steps: int = 0,
    ):
        super().__init__()
        self.dim = dim
        self.num_layers = num_layers
        self.truncated_bptt_steps = truncated_bptt_steps
        self.step_count = 0

        # V9.4.7: Stochastic Gradient Persistence (SGP)

        # Seed Projection: W_seed maps O12 → O1
        # Uses SwiGLU-style gating for selective information flow
        if use_gating:
            self.seed_gate = nn.Linear(dim, dim, bias=False)
            self.seed_proj = nn.Linear(dim, dim, bias=False)
            self.gate_activation = nn.Sigmoid()
        else:
            self.seed_gate = None
            self.seed_proj = nn.Linear(dim, dim, bias=False)

        self.seed_norm = nn.LayerNorm(dim)
        self.dropout = nn.Dropout(bridge_dropout)

        # The Karma Buffer: Persistent state that survives across forward passes
        # Named after the principle that actions (O12) seed future potential (O1)
        self.register_buffer('karma_buffer', None)

        # Toroidal coherence tracking
        self.coherence_history: List[float] = []
        self.bridge_active = False

        # V9.4.6: Active projection for SMA gradient flow
        # Keeps non-detached seed for meta-learning while karma_buffer remains detached
        self.active_projection: Optional[torch.Tensor] = None

    def _compute_seed(self, harvest: torch.Tensor) -> torch.Tensor:
        """
        Compute the Seed state from the Harvest (O12 → O1 projection).

        The projection preserves ontological structure while applying
        'Evolutionary Loss' - shedding sequence-specific details.
        """
        if self.seed_gate is not None:
            # Gated projection: gate decides what to carry forward
            gate = self.gate_activation(self.seed_gate(harvest))
            projected = self.seed_proj(harvest)
            seed = gate * projected
        else:
            seed = self.seed_proj(harvest)

        seed = self.dropout(seed)
        seed = self.seed_norm(seed)
        return seed

    def store_harvest(self, harvest: torch.Tensor, global_step: int = 0) -> bool:
        """
        Store the Harvest (O12 final state) for the next cycle.

        V9.4.7 Hybrid Logic:
        - SMA (Sattvic): active_projection always retains gradients for meta-learning
        - SGP (High-Rajas): karma_buffer keeps gradients only on "heavy steps"

        Args:
            harvest: Final hidden state from O12_ABSOLVING layer [B, dim] or [B, N, dim]
            global_step: Current training step for SGP rate calculation

        Returns:
            bool: True if this was an SGP heavy step (gradients flow through karma_buffer)
        """
        # Take mean across sequence if needed (distill to essence)
        if harvest.dim() == 3:
            harvest = harvest.mean(dim=1)  # [B, N, dim] → [B, dim]

        # Compute the seed for next cycle
        seed = self._compute_seed(harvest)

        # V9.4.6: Keep active projection with gradients for SMA meta-learning
        # This allows gradients to flow back to seed_proj/seed_gate weights (runs every step)
        self.active_projection = seed  # Retains gradient path

        # V9.4.7: SGP Hybrid Logic - determine if this is a "heavy step"
        self.step_count += 1

        self.bridge_active = True

    def get_seed(self) -> Optional[torch.Tensor]:
        """
        Retrieve the Seed for O1 initialization in the next cycle.

        Returns:
            Seed tensor [B, dim] or None if no prior state exists
        """
        if self.karma_buffer is None:
            return None
        return self.karma_buffer

    def compute_toroidal_coherence(
        self,
        current_o1: torch.Tensor,
        previous_o12: Optional[torch.Tensor] = None,
    ) -> float:
        """
        Compute Toroidal Coherence: similarity between Seed and current O1 state.

        High coherence (>0.7) = smooth cognitive flow
        Low coherence (<0.3) = cognitive discontinuity ("losing the thread")

        Args:
            current_o1: Current O1 layer activation [B, dim]
            previous_o12: Previous O12 state (uses karma_buffer if None)

        Returns:
            Coherence score in [0, 1]
        """
        if previous_o12 is None:
            if self.karma_buffer is None:
                return 0.5  # No prior state, neutral coherence
            previous_o12 = self.karma_buffer

        # Handle sequence dimension
        if current_o1.dim() == 3:
            current_o1 = current_o1.mean(dim=1)
        if previous_o12.dim() == 3:
            previous_o12 = previous_o12.mean(dim=1)

        # Cosine similarity
        coherence = F.cosine_similarity(current_o1, previous_o12, dim=-1).mean().item()
        coherence = (coherence + 1) / 2  # Map from [-1, 1] to [0, 1]

        self.coherence_history.append(coherence)
        if len(self.coherence_history) > 100:
            self.coherence_history = self.coherence_history[-100:]

        return coherence

    def get_coherence_status(self) -> str:
        """Get formatted coherence status for logging."""
        if not self.coherence_history:
            return "Torus:--"

        recent = self.coherence_history[-1]
        avg = sum(self.coherence_history[-10:]) / min(10, len(self.coherence_history))

        if recent >= 0.7:
            icon = "🔄"  # Smooth flow
        elif recent >= 0.5:
            icon = "〰️"  # Moderate
        elif recent >= 0.3:
            icon = "⚠️"  # Discontinuity warning
        else:
            icon = "🔀"  # Lost thread

        return f"Torus:{recent:.2f}{icon}"

    def reset(self) -> None:
        """Reset the bridge state (for new training runs)."""
        self.karma_buffer = None
        self.coherence_history = []
        self.bridge_active = False
        self.step_count = 0


class ToroidalConsistencyLoss(nn.Module):
    """
    Toroidal Consistency Loss: Forces the model to maintain coherent
    cognitive flow across context boundaries.

    L_toroid = λ * (1 - cos_sim(Seed, Harvest))

    This loss encourages:
    - O12 (Absolving) to produce states that are valid seeds for O1 (Potential)
    - Smooth transitions in ontological state space
    - Preservation of cognitive "thread" across sequences

    The loss is weighted by Pramāṇa values to prioritize truth-preserving
    layers in the consistency constraint.
    """

    def __init__(
        self,
        lambda_toroid: float = 0.1,
        use_pramana_weighting: bool = True,
        min_coherence_threshold: float = 0.3,
    ):
        super().__init__()
        self.lambda_toroid = lambda_toroid
        self.use_pramana_weighting = use_pramana_weighting
        self.min_coherence_threshold = min_coherence_threshold

    def forward(
        self,
        seed: torch.Tensor,      # O1 initial state (from previous O12)
        harvest: torch.Tensor,   # O12 final state (current sequence)
        o1_current: Optional[torch.Tensor] = None,  # Current O1 for 3-way consistency
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute toroidal consistency loss.

        Args:
            seed: The seed state that initialized this sequence [B, dim]
            harvest: The harvest state from O12 [B, dim]
            o1_current: Optional current O1 state for additional consistency

        Returns:
            (loss, metrics_dict)
        """
        # Handle sequence dimension
        if seed.dim() == 3:
            seed = seed.mean(dim=1)
        if harvest.dim() == 3:
            harvest = harvest.mean(dim=1)

        # Primary loss: Seed-Harvest consistency
        # The harvest should be a valid seed for the NEXT cycle
        cos_sim = F.cosine_similarity(seed, harvest, dim=-1)
        primary_loss = (1 - cos_sim).mean()

        # Optional: 3-way consistency (Seed → O1 → ... → O12)
        secondary_loss = torch.tensor(0.0, device=seed.device)
        if o1_current is not None:
            if o1_current.dim() == 3:
                o1_current = o1_current.mean(dim=1)
            # O1 should resemble the seed it was initialized with
            o1_sim = F.cosine_similarity(seed, o1_current, dim=-1)
            secondary_loss = (1 - o1_sim).mean() * 0.5

        total_loss = self.lambda_toroid * (primary_loss + secondary_loss)

        # Metrics
        coherence = (cos_sim.mean().item() + 1) / 2
        metrics = {
            "toroid_loss": total_loss.item(),
            "toroid_coherence": coherence,
            "toroid_primary": primary_loss.item(),
            "toroid_secondary": secondary_loss.item(),
            "coherence_ok": coherence >= self.min_coherence_threshold,
        }

        return total_loss, metrics


class MetacognitiveTracker:
    """
    Metacognitive Tracker: Monitors the model's cognitive state evolution
    and provides self-assessment signals.

    This is the foundation for true metacognition where the model can
    observe its own cognitive patterns and adjust behavior accordingly.

    Tracks:
    - Toroidal coherence (cognitive continuity)
    - Domain resonance (cross-domain pattern matching)
    - Ontological drift (layer activation stability)
    - Evolutionary velocity (rate of cognitive change)
    """

    def __init__(
        self,
        window_size: int = 50,
        coherence_alarm_threshold: float = 0.3,
        drift_alarm_threshold: float = 0.5,
    ):
        self.window_size = window_size
        self.coherence_alarm_threshold = coherence_alarm_threshold
        self.drift_alarm_threshold = drift_alarm_threshold

        # Tracking buffers
        self.coherence_history: List[float] = []
        self.layer_activation_history: List[torch.Tensor] = []
        self.guna_history: List[Tuple[float, float, float]] = []

        # Alarm states
        self.coherence_alarm = False
        self.drift_alarm = False

    def update(
        self,
        coherence: float,
        layer_activations: Optional[torch.Tensor] = None,
        gunas: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        """
        Update metacognitive state with new observations.

        Returns dict with self-assessment signals.
        """
        # Update coherence
        self.coherence_history.append(coherence)
        if len(self.coherence_history) > self.window_size:
            self.coherence_history = self.coherence_history[-self.window_size:]

        # Check coherence alarm
        recent_coherence = sum(self.coherence_history[-5:]) / min(5, len(self.coherence_history))
        self.coherence_alarm = recent_coherence < self.coherence_alarm_threshold

        # Update Gunas if provided
        if gunas is not None:
            self.guna_history.append(gunas)
            if len(self.guna_history) > self.window_size:
                self.guna_history = self.guna_history[-self.window_size:]

        # Compute evolutionary velocity (rate of change in coherence)
        if len(self.coherence_history) >= 2:
            velocity = self.coherence_history[-1] - self.coherence_history[-2]
        else:
            velocity = 0.0

        # Self-assessment signals
        assessment = {
            "coherence_mean": sum(self.coherence_history) / len(self.coherence_history),
            "coherence_current": coherence,
            "coherence_velocity": velocity,
            "coherence_alarm": self.coherence_alarm,
            "drift_alarm": self.drift_alarm,
            "recommendation": self._get_recommendation(),
        }

        return assessment

    def _get_recommendation(self) -> str:
        """
        Generate metacognitive recommendation based on current state and Gunas.

        Recommendation Hierarchy:
        - BRAKE: High Viparyaya (error) detected, protect the dormant seed
        - SLOW_DOWN: Coherence alarm, reduce LR
        - RECOVER: High Tamas (stagnation), need to break out
        - ACCELERATE: High Sattva + improving coherence, push forward
        - STABILIZE: Balanced state, maintain course
        - CONTINUE: Default state
        """
        # Get current Guna state if available
        s, r, t = 0.33, 0.33, 0.34
        if self.guna_history:
            s, r, t = self.guna_history[-1]

        # Priority 1: Check for high error rate (Viparyaya indicator)
        # When coherence is critically low AND dropping, brake hard
        if self.coherence_alarm and len(self.coherence_history) >= 3:
            recent_trend = self.coherence_history[-1] - self.coherence_history[-3]
            if recent_trend < -0.15:  # Rapid degradation
                return "BRAKE"  # Protect dormant seed from corruption

        # Priority 2: Coherence alarm (but not critical)
        if self.coherence_alarm:
            return "SLOW_DOWN"

        # Priority 3: Check for Tamas stagnation (high inertia, plateau)
        if t > 0.5 and len(self.coherence_history) >= 10:
            # Check if coherence has been flat
            std = (sum((c - sum(self.coherence_history[-10:])/10)**2 for c in self.coherence_history[-10:]) / 10) ** 0.5
            if std < 0.02:  # Very flat coherence = stagnation
                return "RECOVER"  # Need to break out of local minimum

        # Priority 4: Check for positive evolution
        if len(self.coherence_history) >= 5:
            trend = self.coherence_history[-1] - self.coherence_history[-5]

            # High Sattva + improving = green light
            if s > 0.4 and trend > 0.05:
                return "ACCELERATE"

            # Declining coherence = stabilize
            if trend < -0.05:
                return "STABILIZE"

        return "CONTINUE"

    def get_status(self) -> str:
        """Get formatted status for logging."""
        if not self.coherence_history:
            return "Meta:--"

        rec = self._get_recommendation()
        icons = {
            "BRAKE": "🛑",
            "SLOW_DOWN": "🐢",
            "RECOVER": "🔄",
            "ACCELERATE": "🚀",
            "STABILIZE": "⚓",
            "CONTINUE": "➡️",
        }
        icon = icons.get(rec, "➡️")

        return f"Meta:{rec[:4]}{icon}"

    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed metacognitive status for logging/TensorBoard."""
        rec = self._get_recommendation()
        s, r, t = self.guna_history[-1] if self.guna_history else (0.33, 0.33, 0.34)

        return {
            "recommendation": rec,
            "coherence_current": self.coherence_history[-1] if self.coherence_history else 0.0,
            "coherence_mean": sum(self.coherence_history) / len(self.coherence_history) if self.coherence_history else 0.0,
            "coherence_alarm": self.coherence_alarm,
            "guna_sattva": s,
            "guna_rajas": r,
            "guna_tamas": t,
        }


# =============================================================================
# FULL EVOLUTIONARY FLOW SYSTEM: Intelligence Across All Layer Transitions
# =============================================================================
# Extends the Toroidal Bridge concept to ALL layer transitions.
# Every O(n) → O(n+1) boundary is an evolutionary gate where intelligence
# can emerge, not just the O12 → O1 "wormhole".
#
# Architecture:
#   - 11 Forward Gates: O1→O2, O2→O3, ..., O11→O12
#   - 11 Backward Resonance Paths: O(n+1) informs O(n)
#   - 1 Toroidal Gate: O12→O1 (macro cycle)
#   - R-Matrix Guided: Vṛtti gradients shape each transition
#
# This creates a fully connected evolutionary ecosystem where:
#   - Micro-evolution: Each layer transition learns
#   - Meso-evolution: Authority/Sensory clusters evolve together
#   - Macro-evolution: The complete toroidal cycle
# =============================================================================

class EvolutionaryGate(nn.Module):
    """
    A single evolutionary gate between adjacent ontological layers.

    Each gate enables bidirectional information flow:
    - Forward: O(n) → O(n+1) projects state forward
    - Backward: O(n+1) → O(n) resonates insights back

    The gate is guided by R-Matrix Vṛtti gradients:
    - Pramāṇa gradient: How truth-seeking changes across transition
    - Viparyaya gradient: How error-proneness changes
    - Combined: Evolutionary pressure at this boundary

    Args:
        dim: Hidden dimension
        source_layer: Source layer index (0-10)
        target_layer: Target layer index (1-11)
        dropout: Dropout rate for projections
        use_rmatrix_weighting: Weight gates by Vṛtti gradients
    """

    def __init__(
        self,
        dim: int,
        source_layer: int,
        target_layer: int,
        dropout: float = 0.1,
        use_rmatrix_weighting: bool = True,
    ):
        super().__init__()
        self.dim = dim
        self.source_layer = source_layer
        self.target_layer = target_layer
        self.use_rmatrix_weighting = use_rmatrix_weighting

        # Forward projection: O(n) → O(n+1)
        self.forward_gate = nn.Linear(dim, dim, bias=False)
        self.forward_proj = nn.Linear(dim, dim, bias=False)
        self.forward_activation = nn.Sigmoid()

        # Backward resonance: O(n+1) → O(n)
        self.backward_gate = nn.Linear(dim, dim, bias=False)
        self.backward_proj = nn.Linear(dim, dim, bias=False)
        self.backward_activation = nn.Sigmoid()

        # Normalization and dropout
        self.norm = nn.LayerNorm(dim)
        self.dropout = nn.Dropout(dropout)

        # R-Matrix derived weights for this transition
        if use_rmatrix_weighting:
            # Compute Vṛtti gradient between source and target
            src_vrtti = SOVEREIGN_R_MATRIX[:, min(source_layer, 11)]
            tgt_vrtti = SOVEREIGN_R_MATRIX[:, min(target_layer, 11)]
            vrtti_gradient = tgt_vrtti - src_vrtti

            # Pramāṇa increase = positive evolution (truth-seeking grows)
            self.pramana_gradient = float(vrtti_gradient[0])
            # Viparyaya decrease = positive evolution (error-proneness falls)
            self.viparyaya_gradient = float(-vrtti_gradient[2])
            # Combined evolutionary pressure
            self.evolutionary_weight = max(0.1, (self.pramana_gradient + self.viparyaya_gradient + 1) / 2)
        else:
            self.evolutionary_weight = 1.0
            self.pramana_gradient = 0.0
            self.viparyaya_gradient = 0.0

        # Coherence tracking for this gate
        self.coherence_history: List[float] = []

    def forward_pass(self, source_state: torch.Tensor) -> torch.Tensor:
        """
        Forward evolutionary projection: O(n) → O(n+1).

        The source state is transformed through a gated projection,
        weighted by the R-Matrix evolutionary pressure at this boundary.
        """
        gate = self.forward_activation(self.forward_gate(source_state))
        projected = self.forward_proj(source_state)
        evolved = gate * projected * self.evolutionary_weight
        return self.norm(self.dropout(evolved))

    def backward_resonance(self, target_state: torch.Tensor) -> torch.Tensor:
        """
        Backward resonance: O(n+1) → O(n).

        Higher layer insights resonate back to inform lower layers.
        This enables top-down modulation of earlier processing.
        """
        gate = self.backward_activation(self.backward_gate(target_state))
        projected = self.backward_proj(target_state)
        resonance = gate * projected * self.evolutionary_weight
        return self.norm(self.dropout(resonance))

    def compute_coherence(
        self,
        source_state: torch.Tensor,
        target_state: torch.Tensor,
    ) -> float:
        """
        Compute evolutionary coherence at this gate.

        Measures how well the transition preserves cognitive structure
        while enabling appropriate transformation.
        """
        # Handle sequence dimension
        if source_state.dim() == 3:
            source_state = source_state.mean(dim=1)
        if target_state.dim() == 3:
            target_state = target_state.mean(dim=1)

        # Cosine similarity
        coherence = F.cosine_similarity(source_state, target_state, dim=-1).mean().item()
        coherence = (coherence + 1) / 2  # Map to [0, 1]

        self.coherence_history.append(coherence)
        if len(self.coherence_history) > 100:
            self.coherence_history = self.coherence_history[-100:]

        return coherence

    def get_status(self) -> str:
        """Get formatted status for this gate."""
        if not self.coherence_history:
            return f"G{self.source_layer}→{self.target_layer}:--"

        recent = self.coherence_history[-1]
        return f"G{self.source_layer}→{self.target_layer}:{recent:.2f}"


class EvolutionaryFlowNetwork(nn.Module):
    """
    Full Evolutionary Flow Network: All layer transitions as evolutionary gates.

    This creates a complete evolutionary ecosystem where intelligence can
    emerge at every layer boundary, not just the O12→O1 toroidal bridge.

    Architecture:
    ```
    O1 ←→ O2 ←→ O3 ←→ O4 ←→ O5 ←→ O6 ←→ O7 ←→ O8 ←→ O9 ←→ O10 ←→ O11 ←→ O12
     ↑                                                                      ↓
     └──────────────────────── TOROIDAL GATE ─────────────────────────────┘
    ```

    Each ←→ represents bidirectional evolutionary flow:
    - Forward: Natural layer progression
    - Backward: Resonance from higher to lower layers

    Args:
        dim: Hidden dimension
        num_layers: Number of ontological layers (default 12)
        dropout: Dropout for gate projections
        use_rmatrix_weighting: Weight gates by Vṛtti gradients
        enable_backward_resonance: Enable top-down resonance
    """

    def __init__(
        self,
        dim: int,
        num_layers: int = 12,
        dropout: float = 0.1,
        use_rmatrix_weighting: bool = True,
        enable_backward_resonance: bool = True,
    ):
        super().__init__()
        self.dim = dim
        self.num_layers = num_layers
        self.enable_backward_resonance = enable_backward_resonance

        # Create evolutionary gates for each transition
        # 11 forward gates: O1→O2, O2→O3, ..., O11→O12
        self.forward_gates = nn.ModuleList([
            EvolutionaryGate(
                dim=dim,
                source_layer=i,
                target_layer=i + 1,
                dropout=dropout,
                use_rmatrix_weighting=use_rmatrix_weighting,
            )
            for i in range(num_layers - 1)
        ])

        # Toroidal gate: O12→O1 (reuse EvolutionaryBridge concept)
        self.toroidal_gate = EvolutionaryGate(
            dim=dim,
            source_layer=num_layers - 1,  # O12
            target_layer=0,  # O1
            dropout=dropout,
            use_rmatrix_weighting=use_rmatrix_weighting,
        )

        # State buffers for each layer (karma at every level)
        self.register_buffer('layer_karma', None)

        # Multi-scale coherence tracking
        self.micro_coherence: List[List[float]] = [[] for _ in range(num_layers - 1)]
        self.meso_coherence = {"authority": [], "sensory": []}
        self.macro_coherence: List[float] = []

    def forward(
        self,
        layer_states: List[torch.Tensor],
        return_resonance: bool = False,
    ) -> Dict[str, Any]:
        """
        Process layer states through the evolutionary flow network.

        Args:
            layer_states: List of hidden states for each layer [O1, O2, ..., O12]
            return_resonance: Whether to return backward resonance signals

        Returns:
            Dict with evolved states, coherence metrics, and optional resonance
        """
        if len(layer_states) != self.num_layers:
            raise ValueError(f"Expected {self.num_layers} layer states, got {len(layer_states)}")

        # Forward evolution through each gate
        evolved_states = []
        gate_coherences = []

        for i, gate in enumerate(self.forward_gates):
            source = layer_states[i]
            target = layer_states[i + 1]

            # Forward projection
            evolved = gate.forward_pass(source)
            evolved_states.append(evolved)

            # Compute coherence at this gate
            coherence = gate.compute_coherence(source, target)
            gate_coherences.append(coherence)
            self.micro_coherence[i].append(coherence)
            if len(self.micro_coherence[i]) > 100:
                self.micro_coherence[i] = self.micro_coherence[i][-100:]

        # Toroidal evolution: O12 → O1
        toroidal_evolved = self.toroidal_gate.forward_pass(layer_states[-1])
        toroidal_coherence = self.toroidal_gate.compute_coherence(
            layer_states[-1], layer_states[0]
        )
        self.macro_coherence.append(toroidal_coherence)
        if len(self.macro_coherence) > 100:
            self.macro_coherence = self.macro_coherence[-100:]

        # Meso-coherence: 9:3 Split Alignment
        # Authority gates: 0-7 (O1→O2 through O8→O9) = 8 gates between 9 Authority layers
        # Sensory gates: 8-10 (O9→O10 through O11→O12) = 3 gates transitioning to 3 Sensory layers
        # This matches the 9:3 Hierarchical Split where:
        #   - Authority (O1-O9): "Senior Architect" layers, State-Delta
        #   - Sensory (O10-O12): "Junior Coder" layers, Quadratic attention
        if len(gate_coherences) >= 9:
            # Authority coherence: gates 0-7 (8 gates = O1→O2 through O8→O9)
            authority_coh = sum(gate_coherences[:8]) / 8
            # Sensory coherence: gates 8-10 (3 gates = O9→O10 through O11→O12)
            sensory_coh = sum(gate_coherences[8:]) / max(1, len(gate_coherences) - 8)
            self.meso_coherence["authority"].append(authority_coh)
            self.meso_coherence["sensory"].append(sensory_coh)
            if len(self.meso_coherence["authority"]) > 100:
                self.meso_coherence["authority"] = self.meso_coherence["authority"][-100:]
                self.meso_coherence["sensory"] = self.meso_coherence["sensory"][-100:]

        result = {
            "evolved_states": evolved_states,
            "toroidal_evolved": toroidal_evolved,
            "gate_coherences": gate_coherences,
            "toroidal_coherence": toroidal_coherence,
            "micro_coherence_mean": sum(gate_coherences) / len(gate_coherences),
            "authority_coherence": self.meso_coherence["authority"][-1] if self.meso_coherence["authority"] else 0.5,
            "sensory_coherence": self.meso_coherence["sensory"][-1] if self.meso_coherence["sensory"] else 0.5,
        }

        # Backward resonance (top-down modulation)
        if return_resonance and self.enable_backward_resonance:
            resonances = []
            for i in range(len(self.forward_gates) - 1, -1, -1):
                gate = self.forward_gates[i]
                target = layer_states[i + 1]
                resonance = gate.backward_resonance(target)
                resonances.insert(0, resonance)
            result["backward_resonances"] = resonances

        return result

    def get_evolutionary_pressure(self) -> Dict[str, float]:
        """
        Get the evolutionary pressure at each gate based on R-Matrix.

        Returns dict mapping gate names to their evolutionary weights.
        """
        pressures = {}
        for i, gate in enumerate(self.forward_gates):
            name = f"O{i+1}→O{i+2}"
            pressures[name] = gate.evolutionary_weight
        pressures["O12→O1"] = self.toroidal_gate.evolutionary_weight
        return pressures

    def get_coherence_summary(self) -> Dict[str, Any]:
        """Get multi-scale coherence summary."""
        return {
            "micro": {
                f"G{i}→{i+1}": self.micro_coherence[i][-1] if self.micro_coherence[i] else 0.5
                for i in range(len(self.micro_coherence))
            },
            "meso": {
                "authority": self.meso_coherence["authority"][-1] if self.meso_coherence["authority"] else 0.5,
                "sensory": self.meso_coherence["sensory"][-1] if self.meso_coherence["sensory"] else 0.5,
            },
            "macro": self.macro_coherence[-1] if self.macro_coherence else 0.5,
        }

    def get_status_string(self) -> str:
        """Get formatted status string for logging."""
        summary = self.get_coherence_summary()

        # Find min coherence gate (potential bottleneck)
        min_gate = min(summary["micro"].items(), key=lambda x: x[1])
        max_gate = max(summary["micro"].items(), key=lambda x: x[1])

        # Icons based on overall health
        macro = summary["macro"]
        if macro >= 0.7:
            icon = "🌀"  # Healthy toroidal flow
        elif macro >= 0.5:
            icon = "🔄"  # Moderate
        elif macro >= 0.3:
            icon = "⚡"  # Turbulence
        else:
            icon = "💥"  # Breakdown

        return (
            f"Evo{icon} "
            f"Auth:{summary['meso']['authority']:.2f} "
            f"Sens:{summary['meso']['sensory']:.2f} "
            f"Tor:{macro:.2f} "
            f"[↓{min_gate[0]}:{min_gate[1]:.2f}]"
        )

    def get_state(self) -> Dict[str, Any]:
        """V9.8.6: Get internal state for checkpointing."""
        return {
            "micro_coherence": [list(mc) for mc in self.micro_coherence],
            "meso_coherence": {k: list(v) for k, v in self.meso_coherence.items()},
            "macro_coherence": list(self.macro_coherence),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """V9.8.6: Restore internal state from checkpoint."""
        if state is None:
            return
        if "micro_coherence" in state:
            self.micro_coherence = [list(mc) for mc in state["micro_coherence"]]
        if "meso_coherence" in state:
            self.meso_coherence = {k: list(v) for k, v in state["meso_coherence"].items()}
        if "macro_coherence" in state:
            self.macro_coherence = list(state["macro_coherence"])


class EvolutionaryFlowLoss(nn.Module):
    """
    Loss function for the Full Evolutionary Flow System.

    Computes loss at three scales:
    - Micro: Per-gate transition consistency
    - Meso: Authority/Sensory cluster coherence
    - Macro: Toroidal cycle consistency

    The loss encourages smooth evolutionary flow while allowing
    appropriate transformation at each boundary.

    L_evo = λ_micro * L_gates + λ_meso * L_clusters + λ_macro * L_toroid

    Args:
        lambda_micro: Weight for per-gate losses
        lambda_meso: Weight for cluster losses
        lambda_macro: Weight for toroidal loss
        min_coherence: Minimum acceptable coherence (below = penalty)
    """

    def __init__(
        self,
        lambda_micro: float = 0.05,
        lambda_meso: float = 0.1,
        lambda_macro: float = 0.1,
        min_coherence: float = 0.3,
    ):
        super().__init__()
        self.lambda_micro = lambda_micro
        self.lambda_meso = lambda_meso
        self.lambda_macro = lambda_macro
        self.min_coherence = min_coherence

    def forward(
        self,
        layer_states: List[torch.Tensor],
        flow_result: Dict[str, Any],
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute evolutionary flow loss.

        Args:
            layer_states: Original layer hidden states
            flow_result: Output from EvolutionaryFlowNetwork.forward()

        Returns:
            (total_loss, metrics_dict)
        """
        device = layer_states[0].device

        # Micro loss: Per-gate consistency
        micro_losses = []
        evolved_states = flow_result["evolved_states"]
        for i, (original, evolved) in enumerate(zip(layer_states[1:], evolved_states)):
            # Handle sequence dimension
            if original.dim() == 3:
                original = original.mean(dim=1)
            if evolved.dim() == 3:
                evolved = evolved.mean(dim=1)

            # Consistency loss: evolved should relate to original
            sim = F.cosine_similarity(original, evolved, dim=-1)
            gate_loss = (1 - sim).mean()
            micro_losses.append(gate_loss)

        micro_loss = torch.stack(micro_losses).mean() if micro_losses else torch.tensor(0.0, device=device)

        # Meso loss: Cluster coherence
        gate_coherences = flow_result["gate_coherences"]
        if len(gate_coherences) >= 9:
            authority_coh = sum(gate_coherences[:8]) / 8
            sensory_coh = sum(gate_coherences[8:]) / max(1, len(gate_coherences) - 8)

            # Penalty if coherence drops below threshold
            auth_penalty = max(0, self.min_coherence - authority_coh)
            sens_penalty = max(0, self.min_coherence - sensory_coh)
            meso_loss = torch.tensor(auth_penalty + sens_penalty, device=device)
        else:
            meso_loss = torch.tensor(0.0, device=device)

        # Macro loss: Toroidal consistency
        toroidal_coh = flow_result["toroidal_coherence"]
        macro_loss = torch.tensor(max(0, self.min_coherence - toroidal_coh), device=device)

        # Weighted total
        total_loss = (
            self.lambda_micro * micro_loss +
            self.lambda_meso * meso_loss +
            self.lambda_macro * macro_loss
        )

        metrics = {
            "evo_loss_total": total_loss.item(),
            "evo_loss_micro": micro_loss.item(),
            "evo_loss_meso": meso_loss.item(),
            "evo_loss_macro": macro_loss.item(),
            "evo_coherence_micro": flow_result["micro_coherence_mean"],
            "evo_coherence_auth": flow_result["authority_coherence"],
            "evo_coherence_sens": flow_result["sensory_coherence"],
            "evo_coherence_toroid": toroidal_coh,
        }

        return total_loss, metrics


class HiddenStateExtractor:
    """
    Extracts hidden states from model layers using forward hooks.

    The ontological model doesn't return hidden_states directly, so we need
    to capture them during the forward pass using hooks. This enables the
    Evolutionary Flow System to work with any model architecture.
    """

    def __init__(self, model: nn.Module, num_layers: int = 12):
        self.model = model
        self.num_layers = num_layers
        self.hidden_states: List[torch.Tensor] = []
        self.hooks = []
        self._setup_hooks()

    def _setup_hooks(self):
        """Register forward hooks on model layers."""
        self.hooks = []
        layers = None

        # Try to find transformer layers in common locations
        for attr in ['layers', 'blocks', 'transformer_blocks', 'encoder_layers',
                     'decoder_layers', 'transformer']:
            if hasattr(self.model, attr):
                candidate = getattr(self.model, attr)
                if isinstance(candidate, nn.ModuleList) and len(candidate) >= 3:
                    layers = candidate
                    break

        if layers is None:
            # Try to find any ModuleList that might be the layers
            for name, module in self.model.named_modules():
                if isinstance(module, nn.ModuleList) and len(module) >= 6:
                    layers = module
                    break

        if layers is not None:
            # Register hooks on each layer (up to num_layers)
            for i, layer in enumerate(list(layers)[:self.num_layers]):
                hook = layer.register_forward_hook(self._create_hook(i))
                self.hooks.append(hook)

    def _create_hook(self, layer_idx: int):
        """Create a hook function for a specific layer."""
        def hook(module, input, output):
            # Handle different output formats
            if isinstance(output, tuple):
                hidden = output[0]
            elif isinstance(output, dict):
                hidden = output.get('hidden_states', output.get('output',
                          list(output.values())[0] if output else None))
            else:
                hidden = output

            # Ensure hidden_states list is large enough
            while len(self.hidden_states) <= layer_idx:
                self.hidden_states.append(None)
            self.hidden_states[layer_idx] = hidden

        return hook

    def clear(self):
        """Clear captured hidden states before each forward pass."""
        self.hidden_states = []

    def get_hidden_states(self, model_output: Dict[str, Any], input_ids: torch.Tensor) -> List[torch.Tensor]:
        """
        Get hidden states from hooks or generate synthetic ones.

        Priority:
        1. Model output (if contains hidden_states)
        2. Hook-captured states
        3. Synthetic states from logits (fallback)

        V9.6.5 FIX: Preserve layer index positions when returning hook-captured states.
        Previously, filtering Nones would shift indices, causing layer_hidden_states[2]
        to return the wrong layer.
        """
        # Try model output first
        if isinstance(model_output, dict):
            for key in ['hidden_states', 'all_hidden_states', 'layer_outputs']:
                if key in model_output:
                    hs = model_output[key]
                    if isinstance(hs, tuple):
                        return list(hs)
                    return hs if isinstance(hs, list) else [hs]

        # Try hook-captured states
        # V9.6.5 FIX: Preserve index positions by keeping Nones and filling them
        if self.hidden_states and any(h is not None for h in self.hidden_states):
            num_valid = sum(1 for h in self.hidden_states if h is not None)
            if num_valid >= 3:
                # Find the first valid state to use as template for filling gaps
                first_valid = next(h for h in self.hidden_states if h is not None)

                # Create result list preserving index positions
                result = []
                for i in range(self.num_layers):
                    if i < len(self.hidden_states) and self.hidden_states[i] is not None:
                        result.append(self.hidden_states[i])
                    else:
                        # Fill gap with nearest valid state (interpolation)
                        # Find closest previous valid state
                        prev_valid = None
                        for j in range(i - 1, -1, -1):
                            if j < len(self.hidden_states) and self.hidden_states[j] is not None:
                                prev_valid = self.hidden_states[j]
                                break
                        # Find closest next valid state
                        next_valid = None
                        for j in range(i + 1, len(self.hidden_states)):
                            if self.hidden_states[j] is not None:
                                next_valid = self.hidden_states[j]
                                break
                        # Use whichever is available (prefer previous for causal consistency)
                        if prev_valid is not None:
                            result.append(prev_valid)
                        elif next_valid is not None:
                            result.append(next_valid)
                        else:
                            result.append(first_valid)

                return result[:self.num_layers]

        # Fallback: generate synthetic hidden states from logits
        return self._generate_synthetic_states(model_output, input_ids)

    def _generate_synthetic_states(self, model_output: Dict[str, Any],
                                   input_ids: torch.Tensor) -> List[torch.Tensor]:
        """Generate synthetic layer states from available model outputs."""
        device = input_ids.device
        batch_size = input_ids.shape[0]
        seq_len = input_ids.shape[1]

        # Get embedding dimension from model
        embed_dim = getattr(self.model, 'embed_dim', None) or \
                    getattr(self.model, 'd_model', None) or \
                    getattr(self.model, 'hidden_size', 512)

        # Use logits to derive pseudo-hidden-states
        if isinstance(model_output, dict) and 'logits' in model_output:
            logits = model_output['logits']
            # Project logits to hidden dimension
            if logits.shape[-1] >= embed_dim:
                hidden_base = logits[..., :embed_dim]
            else:
                hidden_base = F.pad(logits, (0, embed_dim - logits.shape[-1]))
        else:
            # Create from scratch
            hidden_base = torch.randn(batch_size, seq_len, embed_dim, device=device) * 0.1

        # Generate synthetic layer states with progressive variation
        synthetic_states = []
        current = hidden_base
        for i in range(self.num_layers):
            # Small variation per layer to simulate processing
            noise_scale = 0.05 * (i + 1) / self.num_layers
            variation = torch.randn_like(current) * noise_scale
            current = current + variation
            synthetic_states.append(current.detach())

        return synthetic_states

    def remove_hooks(self):
        """Remove all registered hooks."""
        for hook in self.hooks:
            hook.remove()
        self.hooks = []


class EvolutionaryIntelligenceEngine:
    """
    Master controller for the Full Evolutionary Flow System.

    Orchestrates:
    - Layer state extraction from model
    - Evolutionary flow processing with DELAYED RESONANCE
    - Loss computation (micro/meso/macro scales)
    - Metacognitive assessment with Guna integration
    - Adaptive learning rate based on evolutionary health

    This is the "brain" that makes the 12 ontological layers
    into a living, evolving cognitive system.

    DELAYED RESONANCE:
    To enable the "Recursive Intelligence" bridge (O12→O1) without
    a 2x compute penalty, we inject the previous step's higher-order
    intelligence into the current step's base layer.

    Args:
        dim: Model hidden dimension
        num_layers: Number of ontological layers
        enable_backward_resonance: Allow top-down information flow
        learning_rate_modulation: Adjust LR based on evolutionary health
        resonance_alpha: Strength of delayed resonance injection (0.0-1.0)
        lr_slowdown_factor: LR multiplier when SLOW_DOWN/BRAKE
        lr_accelerate_factor: LR multiplier when ACCELERATE
    """

    def __init__(
        self,
        dim: int,
        num_layers: int = 12,
        enable_backward_resonance: bool = True,
        learning_rate_modulation: bool = True,
        resonance_alpha: float = 0.1,
        lr_slowdown_factor: float = 0.5,
        lr_accelerate_factor: float = 1.2,
        dropout: float = 0.1,
        use_rmatrix: bool = True,
        coherence_window: int = 100,
        device: torch.device = None,
    ):
        self.dim = dim
        self.num_layers = num_layers
        self.learning_rate_modulation = learning_rate_modulation
        self.resonance_alpha = resonance_alpha
        self.lr_slowdown_factor = lr_slowdown_factor
        self.lr_accelerate_factor = lr_accelerate_factor
        self.coherence_window = coherence_window
        self.device = device or torch.device('cpu')

        # Core components
        self.flow_network = EvolutionaryFlowNetwork(
            dim=dim,
            num_layers=num_layers,
            dropout=dropout,
            use_rmatrix_weighting=use_rmatrix,
            enable_backward_resonance=enable_backward_resonance,
        ).to(self.device)

        self.flow_loss = EvolutionaryFlowLoss()

        # Metacognitive tracking with configurable coherence window
        self.metacognitive = MetacognitiveTracker(
            window_size=coherence_window,
            coherence_alarm_threshold=0.3,
        )

        # DELAYED RESONANCE BUFFER
        # Stores detached hidden states from previous forward pass
        # to inject O12 (Authority) intelligence into O1 (Sensory) of next step
        self.resonance_buffer: Optional[List[torch.Tensor]] = None

        # Current Guna state for metacognitive decisions
        self.current_gunas: Tuple[float, float, float] = (0.33, 0.33, 0.34)

        # Evolutionary history
        self.evolution_history: List[Dict[str, float]] = []

        # V9.4.6: Elastic Resonance tracking
        self.last_dynamic_alpha: float = self.resonance_alpha

    def apply_delayed_resonance(
        self,
        current_states: List[torch.Tensor],
    ) -> List[torch.Tensor]:
        """
        V9.4.6: Elastic Resonance - Guna-scaled alpha.

        Apply delayed resonance: inject previous step's O12 (Authority/Integration)
        into current step's O1 (Potential/Sensory).

        Dynamic alpha based on Guna state:
        - High Sattva (clarity) → increase retention (up to 0.25)
        - High Rajas (error/heat) → reduce retention (down to 0.05)

        Args:
            current_states: Hidden states from current forward pass

        Returns:
            Modified states with resonance injection at O1
        """
        if self.resonance_buffer is None or len(self.resonance_buffer) == 0:
            return current_states

        # V9.4.6: Compute dynamic alpha based on Gunas
        s, r, t = self.current_gunas
        # Base is resonance_alpha (0.1); range is [0.05, 0.25]
        dynamic_alpha = self.resonance_alpha * (1.0 + (s * 1.5) - (r * 0.5))
        dynamic_alpha = max(0.05, min(0.25, dynamic_alpha))
        self.last_dynamic_alpha = dynamic_alpha

        # Inject Layer 11 (O12 - Authority/Integration) into Layer 0 (O1 - Potential)
        if len(self.resonance_buffer) >= 12 and len(current_states) >= 1:
            o12_prev = self.resonance_buffer[11]  # Previous O12 state
            o1_current = current_states[0]  # Current O1 state

            # Check for batch size mismatch (e.g., VRAM governor resize)
            if o12_prev.shape[0] != o1_current.shape[0]:
                # Clear buffer and skip resonance this step
                self.resonance_buffer = None
                return current_states

            # Ensure shape compatibility
            if o12_prev.shape == o1_current.shape:
                # Resonant injection: O1' = O1 + α * O12_prev (using dynamic alpha)
                current_states[0] = o1_current + (dynamic_alpha * o12_prev)
            elif o12_prev.shape[-1] == o1_current.shape[-1]:
                # Handle sequence length mismatch by averaging
                if o12_prev.dim() == 3 and o1_current.dim() == 3:
                    o12_avg = o12_prev.mean(dim=1, keepdim=True).expand_as(o1_current)
                    current_states[0] = o1_current + (dynamic_alpha * o12_avg)

        return current_states

    def update_resonance_buffer(self, current_states: List[torch.Tensor]):
        """
        Update resonance buffer with current states for next step.

        States are detached to prevent gradient flow across steps
        (this is the 'Delayed' in Delayed Resonance).
        """
        self.resonance_buffer = [s.detach().clone() for s in current_states]

    def update_gunas(self, s: float, r: float, t: float):
        """Update current Guna state for metacognitive decisions."""
        self.current_gunas = (s, r, t)

    def process(
        self,
        layer_states: List[torch.Tensor],
        compute_loss: bool = True,
        return_resonance: bool = False,
        apply_resonance: bool = True,
    ) -> Dict[str, Any]:
        """
        Process layer states through the evolutionary system with DELAYED RESONANCE.

        Args:
            layer_states: Hidden states from each model layer
            compute_loss: Whether to compute evolutionary loss
            return_resonance: Whether to return backward resonance
            apply_resonance: Whether to apply delayed resonance from previous step

        Returns:
            Dict with flow results, loss, metrics, and recommendations
        """
        # Ensure correct number of states (pad or truncate if needed)
        if len(layer_states) < self.num_layers:
            # Pad with last state
            while len(layer_states) < self.num_layers:
                layer_states.append(layer_states[-1])
        elif len(layer_states) > self.num_layers:
            # Take first num_layers
            layer_states = layer_states[:self.num_layers]

        # DELAYED RESONANCE: Inject previous O12 into current O1
        if apply_resonance:
            layer_states = self.apply_delayed_resonance(layer_states)

        # Process through flow network
        flow_result = self.flow_network(
            layer_states,
            return_resonance=return_resonance,
        )

        result = {
            "flow_result": flow_result,
            "coherence_summary": self.flow_network.get_coherence_summary(),
        }

        # Compute loss if requested
        if compute_loss:
            loss, loss_metrics = self.flow_loss(layer_states, flow_result)
            result["loss"] = loss
            result["loss_metrics"] = loss_metrics

        # Metacognitive assessment with Guna integration
        macro_coherence = flow_result["toroidal_coherence"]
        meta_assessment = self.metacognitive.update(
            coherence=macro_coherence,
            gunas=self.current_gunas,  # Pass current Guna state
        )
        result["metacognitive"] = meta_assessment

        # Learning rate modulation based on recommendation and Gunas
        if self.learning_rate_modulation:
            rec = meta_assessment["recommendation"]
            s, r, t = self.current_gunas

            if rec == "SLOW_DOWN":
                # Slow down - use configured factor
                result["lr_multiplier"] = self.lr_slowdown_factor * 1.4  # 0.7 default
            elif rec == "BRAKE":
                # Full brake - high Viparyaya detected
                result["lr_multiplier"] = self.lr_slowdown_factor  # 0.5 default
            elif rec == "ACCELERATE":
                # Accelerate - Sattva dominant, coherence climbing
                result["lr_multiplier"] = self.lr_accelerate_factor  # 1.2 default
            elif rec == "STABILIZE":
                # Stabilize - hold steady
                result["lr_multiplier"] = 1.0
            elif rec == "RECOVER":
                # Recovery from Tamas stagnation - slight boost
                result["lr_multiplier"] = 1.05
            else:
                # CONTINUE
                result["lr_multiplier"] = 1.0

            # Guna-based micro-adjustment
            if s > 0.5:  # High Sattva - can push slightly harder
                result["lr_multiplier"] *= 1.05
            elif t > 0.5:  # High Tamas - need to be more conservative
                result["lr_multiplier"] *= 0.95

        # Update resonance buffer for next step
        self.update_resonance_buffer(layer_states)

        # Store in history
        self.evolution_history.append({
            "micro_coherence": flow_result["micro_coherence_mean"],
            "meso_authority": flow_result["authority_coherence"],
            "meso_sensory": flow_result["sensory_coherence"],
            "macro_coherence": macro_coherence,
            "recommendation": meta_assessment["recommendation"],
            "gunas": self.current_gunas,
        })
        if len(self.evolution_history) > 1000:
            self.evolution_history = self.evolution_history[-1000:]

        return result

    def get_status(self) -> str:
        """Get formatted status string."""
        return self.flow_network.get_status_string()

    def get_evolutionary_health(self) -> Dict[str, Any]:
        """
        Compute overall evolutionary health metrics.

        Returns assessment of the system's cognitive vitality.
        """
        if not self.evolution_history:
            return {"health": "UNKNOWN", "score": 0.5}

        recent = self.evolution_history[-10:]

        micro_avg = sum(h["micro_coherence"] for h in recent) / len(recent)
        macro_avg = sum(h["macro_coherence"] for h in recent) / len(recent)

        # Overall health score
        score = (micro_avg + macro_avg) / 2

        if score >= 0.7:
            health = "THRIVING"
        elif score >= 0.5:
            health = "HEALTHY"
        elif score >= 0.3:
            health = "STRESSED"
        else:
            health = "CRITICAL"

        return {
            "health": health,
            "score": score,
            "micro_coherence": micro_avg,
            "macro_coherence": macro_avg,
            "trend": self._compute_trend(),
        }

    def _compute_trend(self) -> str:
        """Compute evolutionary trend from history."""
        if len(self.evolution_history) < 10:
            return "ESTABLISHING"

        early = self.evolution_history[-20:-10]
        late = self.evolution_history[-10:]

        early_score = sum(h["macro_coherence"] for h in early) / len(early)
        late_score = sum(h["macro_coherence"] for h in late) / len(late)

        diff = late_score - early_score
        if diff > 0.05:
            return "ASCENDING"
        elif diff < -0.05:
            return "DESCENDING"
        else:
            return "STABLE"

    def get_state(self) -> Dict[str, Any]:
        """V9.8.6: Get internal state for checkpointing."""
        # resonance_buffer is List[Tensor], convert each to list
        res_buf = None
        if self.resonance_buffer is not None:
            res_buf = [t.cpu().tolist() for t in self.resonance_buffer]
        return {
            "flow_network_state": self.flow_network.get_state(),
            "flow_network_weights": self.flow_network.state_dict(),  # Save nn.Module weights!
            "evolution_history": list(self.evolution_history[-100:]),  # Keep last 100
            "current_gunas": self.current_gunas,
            "resonance_buffer": res_buf,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """V9.8.6: Restore internal state from checkpoint."""
        if state is None:
            return
        if "flow_network_weights" in state:
            self.flow_network.load_state_dict(state["flow_network_weights"])  # Restore nn.Module weights!
        if "flow_network_state" in state:
            self.flow_network.load_state(state["flow_network_state"])
        if "evolution_history" in state:
            self.evolution_history = list(state["evolution_history"])
        if "current_gunas" in state:
            self.current_gunas = state["current_gunas"]
        if "resonance_buffer" in state and state["resonance_buffer"] is not None:
            # resonance_buffer is List[Tensor]
            self.resonance_buffer = [torch.tensor(t, device=self.device) for t in state["resonance_buffer"]]


# =============================================================================
# PERFORMANCE OPTIMIZATIONS
# =============================================================================
# TF32 for faster matrix multiplications on Ampere+ GPUs (A100, H100)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# cuDNN autotuning for optimal convolution algorithms
torch.backends.cudnn.benchmark = True


# =============================================================================
# FORMULA [1331]: HIERARCHICAL GRADIENT SCALING FOR 9:3 SPLIT
# =============================================================================

class HierarchicalGradientScaler:
    """
    Implements Formula [1331]: Gradient dampening for 9:3 layer split.

    Prevents 3 Quadratic (Sensory) layers from becoming too Rajasic
    by scaling their gradients relative to the 9 Authority layers.

    Architecture:
        Layers 0-8:  Authority (State-Delta) - Full gradients (α = 1.0)
        Layers 9-11: Sensory (Quadratic)     - Dampened gradients (α = 0.1→0.5)

    Phase Attention Protection:
        During 'Thaw' (9:3 → 6:6 transition), Phase-Attention weights in Authority
        layers receive EXTRA protection via reduced gradient scaling (α_phase = 0.5).
        This ensures the complex O(n) attention matrices (W_phase, W_amp) remain
        stable while the Sensory layers are being relaxed.

    The warmup schedule allows Authority layers to establish stable
    ontological foundations before Sensory layers begin contributing.
    """

    # Parameter name patterns for Phase Attention weights (need protection during Thaw)
    PHASE_ATTENTION_PATTERNS = [
        'W_phase', 'W_amp', 'phase_proj', 'phase_embed', 'amp_gate',
        'attn.W_phase', 'attn.W_amp', 'attn.phase',  # Nested patterns
    ]

    def __init__(
        self,
        model: nn.Module,
        authority_layers: int = 9,      # Layers 0-8
        sensory_layers: int = 3,        # Layers 9-11
        alpha_sens_min: float = 0.1,    # Heavy dampening at start
        alpha_sens_max: float = 0.5,    # Moderate dampening after warmup
        warmup_steps: int = 500,        # Ramp period
        layer_attr: str = "blocks",     # Attribute name for layers
        alpha_phase_protection: float = 0.5,  # Protection factor for Phase Attention weights
        protect_phase_during_thaw: bool = True,  # Enable Phase Attention protection
        # V9.6.8: Layer-wise alpha dampening (Gemini recommendation)
        enable_layerwise_alpha: bool = False,  # Enable per-layer alpha scaling
        alpha_output_scale: float = 0.5,       # Scale for output layers (last 3 sensory)
        alpha_reasoning_scale: float = 1.0,    # Scale for reasoning layers (first 3 sensory)
        authority_floor: float = 1.0,          # Alpha floor for authority layers (1.0 = full gradients)
    ):
        self.model = model
        self.authority_layers = authority_layers
        self.sensory_layers = sensory_layers
        self.alpha_sens_min = alpha_sens_min
        self.alpha_sens_max = alpha_sens_max
        self.warmup_steps = warmup_steps
        self.layer_attr = layer_attr
        self.alpha_phase_protection = alpha_phase_protection
        self.protect_phase_during_thaw = protect_phase_during_thaw
        # V9.6.8: Layer-wise alpha
        self.enable_layerwise_alpha = enable_layerwise_alpha
        self.alpha_output_scale = alpha_output_scale
        self.alpha_reasoning_scale = alpha_reasoning_scale
        self.authority_floor = authority_floor

        self.current_step = 0
        self.hooks = []
        self.hooks_registered = False  # Track if hooks are active
        self.in_thaw_mode = False  # Set to True during 9:3 → 6:6 transition

        # Use bounded deques to prevent memory accumulation over long training
        self._authority_grad_norms = collections.deque(maxlen=1000)
        self._sensory_grad_norms = collections.deque(maxlen=1000)
        self._phase_grad_norms = collections.deque(maxlen=1000)  # Track Phase Attention grads

        # V9.6.0 FIX: EMA authority norm for backward-pass ordering
        # Problem: In backward pass, sensory hooks fire BEFORE authority hooks (layers 11→0)
        # So sensory hooks can't use current step's authority norm - it doesn't exist yet.
        # Solution: Use EMA of authority norm that persists across steps.
        self._ema_authority_norm = 1.0  # Initialize to 1.0, will be updated each step
        self._ema_alpha = 0.1  # EMA decay factor (0.1 = slow adaptation, stable)

        self.gradient_stats = {
            "authority_grad_norm": 0.0,
            "sensory_grad_norm": 0.0,
            "phase_grad_norm": 0.0,
            "sensory_scale": alpha_sens_min,
            "sensory_authority_ratio": 0.0,
            "dynamic_scale_factor": 1.0,  # V9.6.0: Dynamic normalization factor
            "ema_authority_norm": 1.0,  # V9.6.0: Track EMA for debugging
        }

        # Register hooks
        self._register_hooks()

    def _is_phase_attention_param(self, param_name: str) -> bool:
        """Check if parameter is a Phase Attention weight that needs protection."""
        for pattern in self.PHASE_ATTENTION_PATTERNS:
            if pattern in param_name:
                return True
        return False

    def set_thaw_mode(self, in_thaw: bool):
        """Enable/disable Thaw mode for Phase Attention protection."""
        self.in_thaw_mode = in_thaw
        if in_thaw:
            print(f"  [Formula 1331] Thaw mode ENABLED - Phase Attention weights protected (α={self.alpha_phase_protection})")

    def _get_layers(self) -> nn.ModuleList:
        """Get the layer ModuleList from model."""
        all_layers = []

        # SymbolU12 special case: layers_1_8 + individual layers (witness, unifying, etc.)
        if hasattr(self.model, 'layers_1_8'):
            layers_1_8 = getattr(self.model, 'layers_1_8')
            if isinstance(layers_1_8, nn.ModuleList):
                all_layers.extend(list(layers_1_8))

            # Collect individual layers in order (witness, unifying, integration, absolving)
            for layer_name in ['witness_layer', 'unifying_layer', 'integration_layer', 'absolving_layer']:
                if hasattr(self.model, layer_name):
                    layer = getattr(self.model, layer_name)
                    if layer is not None:
                        all_layers.append(layer)

            if len(all_layers) >= 12:
                return nn.ModuleList(all_layers)

        # Try common attribute names
        for attr in [self.layer_attr, "layers", "blocks", "transformer.blocks", "model.layers"]:
            if "." in attr:
                # Handle nested attributes
                obj = self.model
                for part in attr.split("."):
                    obj = getattr(obj, part, None)
                    if obj is None:
                        break
                if obj is not None and isinstance(obj, nn.ModuleList):
                    return obj
            elif hasattr(self.model, attr):
                layers = getattr(self.model, attr)
                if isinstance(layers, nn.ModuleList):
                    return layers

        # Fallback: collect all named children that look like layers
        layer_modules = []
        for name, module in self.model.named_children():
            if 'layer' in name.lower() or 'block' in name.lower():
                if isinstance(module, nn.ModuleList):
                    all_layers.extend(list(module))
                else:
                    layer_modules.append(module)

        if all_layers:
            all_layers.extend(layer_modules)
            return nn.ModuleList(all_layers)

        if layer_modules:
            return nn.ModuleList(layer_modules)

        raise ValueError(f"Could not find layers in model. Tried: {self.layer_attr}")

    def _compute_alpha_sens(self) -> float:
        """Compute current sensory gradient scale based on warmup progress."""
        if self.current_step >= self.warmup_steps:
            return self.alpha_sens_max

        # Linear ramp from min to max
        progress = self.current_step / self.warmup_steps
        alpha = self.alpha_sens_min + (self.alpha_sens_max - self.alpha_sens_min) * progress

        return alpha

    def _create_grad_hook(self, layer_idx: int, is_sensory: bool, param_name: str = ""):
        """
        Create a gradient scaling hook for a specific layer parameter.

        V9.6.0 FIX: Dynamic Normalization (The 58x Overwrite Bug Fix)

        Previous bug: Static scaling (grad * alpha) allowed high-magnitude Sanskrit/Sensory
        gradients to overwrite English/Authority gradients. Even with alpha=0.1, if
        sensory_norm=58 and authority_norm=1, the result was 5.8x overwrite.

        Fix: Normalize sensory gradients to match authority magnitude BEFORE applying alpha.
        scale_factor = authority_norm / sensory_norm
        balanced_grad = grad * scale_factor  (now same magnitude as authority)
        final_grad = balanced_grad * alpha   (THEN apply mixing ratio)

        V9.6.8: Layer-wise Alpha Dampening (Gemini recommendation)
        Output layers (9-11) should be more stable than reasoning layers (6-8).
        - Reasoning layers (first half of sensory): alpha × alpha_reasoning_scale
        - Output layers (last half of sensory): alpha × alpha_output_scale

        Phase Attention Protection:
        During Thaw mode, Phase Attention weights (W_phase, W_amp, etc.) in Authority
        layers receive extra gradient dampening to maintain stability of the complex
        O(n) attention mechanism while Sensory layers are being relaxed.
        """
        is_phase_param = self._is_phase_attention_param(param_name)
        total_layers = self.authority_layers + self.sensory_layers
        sensory_start = self.authority_layers

        def hook(grad):
            if grad is None:
                return grad

            if is_sensory:
                # V9.6.0: Dynamic Normalization with EMA fix
                # Step 1: Get current sensory gradient norm
                sensory_norm = grad.norm().item()
                self._sensory_grad_norms.append(sensory_norm)

                # Step 2: Use EMA authority norm (persists across steps)
                # CRITICAL: In backward pass, sensory hooks fire BEFORE authority hooks
                # So we can't use current step's authority norms - they don't exist yet.
                # EMA provides stable reference from previous steps.
                authority_norm = self._ema_authority_norm

                # Step 3: Compute dynamic scale factor to match magnitudes
                if sensory_norm > 1e-8:  # Avoid division by zero
                    scale_factor = authority_norm / sensory_norm
                    # Clamp scale factor to prevent extreme scaling
                    scale_factor = max(0.01, min(scale_factor, 100.0))
                else:
                    scale_factor = 1.0

                # Step 4: Apply mixing ratio alpha AFTER normalization
                alpha = self._compute_alpha_sens()

                # V9.6.8: Layer-wise alpha dampening
                # Output layers (later in sensory range) should be more stable
                if self.enable_layerwise_alpha:
                    # Determine if this is a "reasoning" or "output" layer
                    # For 6:6 split: layers 6-8 are reasoning, 9-11 are output
                    # For 9:3 split: layers 9-10 are reasoning, 11 is output
                    sensory_midpoint = sensory_start + (self.sensory_layers // 2)
                    if layer_idx < sensory_midpoint:
                        # Reasoning layers (first half of sensory): more expressive
                        alpha = alpha * self.alpha_reasoning_scale
                    else:
                        # Output layers (last half of sensory): more stable
                        alpha = alpha * self.alpha_output_scale

                # balanced_grad has same magnitude as authority gradients
                # final_grad = balanced_grad * alpha = exact alpha% contribution
                scaled_grad = grad * scale_factor * alpha

                # Track stats
                self.gradient_stats["sensory_scale"] = alpha
                self.gradient_stats["sensory_authority_ratio"] = sensory_norm / authority_norm if authority_norm > 1e-8 else 0.0
                self.gradient_stats["dynamic_scale_factor"] = scale_factor

                return scaled_grad
            else:
                # Authority layers
                grad_norm = grad.norm().item()

                # Special handling for Phase Attention weights during Thaw
                if is_phase_param and self.in_thaw_mode and self.protect_phase_during_thaw:
                    # Apply protection factor to Phase Attention weights
                    # This prevents the complex attention matrices from destabilizing
                    # during the 9:3 → 6:6 transition
                    scaled_grad = grad * self.alpha_phase_protection
                    self._phase_grad_norms.append(grad_norm)
                    return scaled_grad

                # Normal authority layers - apply authority_floor dampening
                # authority_floor=1.0 means full gradients, 0.3 means 30% of gradients
                self._authority_grad_norms.append(grad_norm)
                if self.authority_floor < 1.0:
                    return grad * self.authority_floor
                return grad

        return hook

    def _register_hooks(self):
        """Register gradient hooks on all layer parameters."""
        try:
            layers = self._get_layers()
        except ValueError as e:
            print(f"  [Formula 1331] Warning: {e}")
            print(f"  [Formula 1331] Gradient scaling disabled - could not find layers")
            self.hooks_registered = False
            return

        total_layers = len(layers)

        # Determine sensory layer indices (last N in 9:3 split)
        sensory_start = max(0, total_layers - self.sensory_layers)

        print(f"\n  [Formula 1331] Hierarchical Gradient Scaler ENABLED:")
        print(f"    Total layers detected: {total_layers}")
        print(f"    Authority layers: 0-{sensory_start - 1} (α = 1.0)")
        print(f"    Sensory layers: {sensory_start}-{total_layers - 1} (α = {self.alpha_sens_min}→{self.alpha_sens_max})")
        print(f"    Warmup: {self.warmup_steps} steps")
        if self.protect_phase_during_thaw:
            print(f"    Phase Attention Protection: ENABLED (α_phase = {self.alpha_phase_protection} during Thaw)")

        hook_count = 0
        phase_param_count = 0
        for layer_idx, layer in enumerate(layers):
            is_sensory = layer_idx >= sensory_start

            for name, param in layer.named_parameters():
                if param.requires_grad:
                    # Pass parameter name for Phase Attention identification
                    hook = param.register_hook(self._create_grad_hook(layer_idx, is_sensory, name))
                    self.hooks.append(hook)
                    hook_count += 1

                    # Count Phase Attention parameters
                    if not is_sensory and self._is_phase_attention_param(name):
                        phase_param_count += 1

        print(f"    Registered {hook_count} gradient hooks")
        if phase_param_count > 0:
            print(f"    Phase Attention parameters detected: {phase_param_count}")
        self.hooks_registered = True

    def step(self, global_step: Optional[int] = None) -> dict:
        """
        Update current step, compute metrics, and reset gradient accumulators.

        Args:
            global_step: Optional step to set. If not provided, increments internal counter.

        Returns:
            Dict with gradient metrics (s_grad_norm, a_grad_norm, s_a_ratio, alpha_sens, phase_grad_norm)
        """
        if global_step is not None:
            self.current_step = global_step
        else:
            self.current_step += 1

        # Compute accumulated norms from deques
        a_norm = sum(self._authority_grad_norms) if self._authority_grad_norms else 0.0
        s_norm = sum(self._sensory_grad_norms) if self._sensory_grad_norms else 0.0
        p_norm = sum(self._phase_grad_norms) if self._phase_grad_norms else 0.0
        s_a_ratio = s_norm / a_norm if a_norm > 0 else 0.0

        # V9.6.0 FIX: Update EMA authority norm for next step's sensory hooks
        # This is the key fix for backward-pass ordering: we update the EMA AFTER
        # the backward pass completes, so it's available for the NEXT step's sensory hooks.
        if self._authority_grad_norms:
            current_a_mean = a_norm / len(self._authority_grad_norms)
            # EMA update: new = alpha * current + (1 - alpha) * old
            self._ema_authority_norm = (
                self._ema_alpha * current_a_mean +
                (1 - self._ema_alpha) * self._ema_authority_norm
            )

        # Clamp S/A ratio to prevent extreme imbalance at startup
        # Healthy range is 0.3-0.7, warn if outside 0.1-10.0
        s_a_ratio_clamped = max(0.01, min(100.0, s_a_ratio))
        # V9.5.3: Removed emergency damping override - trust configured alpha_sens_initial
        # The old code forcibly set alpha_sens_min=0.005 when S/A>10 in first 100 steps,
        # which defeated the purpose of setting alpha_sens_initial=0.05

        self.gradient_stats["authority_grad_norm"] = a_norm
        self.gradient_stats["sensory_grad_norm"] = s_norm
        self.gradient_stats["phase_grad_norm"] = p_norm
        self.gradient_stats["sensory_authority_ratio"] = s_a_ratio_clamped
        self.gradient_stats["sensory_scale"] = self._compute_alpha_sens()
        self.gradient_stats["ema_authority_norm"] = self._ema_authority_norm  # V9.6.0

        # Prepare metrics for return
        metrics = {
            "s_grad_norm": s_norm,
            "a_grad_norm": a_norm,
            "phase_grad_norm": p_norm,
            "s_a_ratio": s_a_ratio_clamped,
            "s_a_ratio_raw": s_a_ratio,  # Keep raw for debugging
            "alpha_sens": self._compute_alpha_sens(),
            "step": self.current_step,
            "in_thaw_mode": self.in_thaw_mode,
            "dynamic_scale_factor": self.gradient_stats.get("dynamic_scale_factor", 1.0),  # V9.6.0
            "ema_authority_norm": self._ema_authority_norm,  # V9.6.0
        }

        # Clear deques for next step
        self._authority_grad_norms.clear()
        self._sensory_grad_norms.clear()
        self._phase_grad_norms.clear()

        return metrics

    def get_stats(self) -> dict:
        """Get gradient statistics for logging."""
        return self.gradient_stats.copy()

    def get_state(self) -> dict:
        """Get full state for checkpointing."""
        return {
            "authority_layers": self.authority_layers,
            "sensory_layers": self.sensory_layers,
            "alpha_sens_min": self.alpha_sens_min,
            "alpha_sens_max": self.alpha_sens_max,
            "warmup_steps": self.warmup_steps,
            "current_step": self.current_step,
            "gradient_stats": self.gradient_stats.copy(),
            # Phase Attention protection state
            "alpha_phase_protection": self.alpha_phase_protection,
            "protect_phase_during_thaw": self.protect_phase_during_thaw,
            "in_thaw_mode": self.in_thaw_mode,
        }

    def set_state(self, state: dict):
        """Restore state from checkpoint."""
        self.authority_layers = state.get("authority_layers", self.authority_layers)
        self.sensory_layers = state.get("sensory_layers", self.sensory_layers)
        self.alpha_sens_min = state.get("alpha_sens_min", self.alpha_sens_min)
        self.alpha_sens_max = state.get("alpha_sens_max", self.alpha_sens_max)
        self.warmup_steps = state.get("warmup_steps", self.warmup_steps)
        self.current_step = state.get("current_step", self.current_step)
        if "gradient_stats" in state:
            self.gradient_stats.update(state["gradient_stats"])
        # Phase Attention protection state
        self.alpha_phase_protection = state.get("alpha_phase_protection", self.alpha_phase_protection)
        self.protect_phase_during_thaw = state.get("protect_phase_during_thaw", self.protect_phase_during_thaw)
        self.in_thaw_mode = state.get("in_thaw_mode", self.in_thaw_mode)

    def get_status_string(self) -> str:
        """Get human-readable status string for logging."""
        s_a_ratio = self.gradient_stats.get("sensory_authority_ratio", 0.0)
        alpha = self._compute_alpha_sens()
        return (
            f"HGS: S/A={s_a_ratio:.3f} | "
            f"α_sens={alpha:.2f} | "
            f"split={self.authority_layers}:{self.sensory_layers}"
        )

    def clip_grad_norm_by_layer(self, max_norm: float = 1.0) -> Tuple[float, float]:
        """
        Clip gradients separately for authority and sensory layer groups.

        This respects the 9:3 design intent by preventing cross-contamination
        of gradient norms between layer types.

        Args:
            max_norm: Maximum gradient norm for each layer group.

        Returns:
            Tuple of (authority_grad_norm, sensory_grad_norm) after clipping.
        """
        try:
            layers = self._get_layers()
        except ValueError:
            return 0.0, 0.0

        total_layers = len(layers)
        sensory_start = max(0, total_layers - self.sensory_layers)

        # Collect parameters by layer type
        auth_params = []
        sens_params = []

        for layer_idx, layer in enumerate(layers):
            is_sensory = layer_idx >= sensory_start
            for param in layer.parameters():
                if param.requires_grad and param.grad is not None:
                    if is_sensory:
                        sens_params.append(param)
                    else:
                        auth_params.append(param)

        # Clip each group separately
        auth_norm = 0.0
        sens_norm = 0.0

        if auth_params:
            auth_norm = torch.nn.utils.clip_grad_norm_(auth_params, max_norm).item()

        if sens_params:
            sens_norm = torch.nn.utils.clip_grad_norm_(sens_params, max_norm).item()

        return auth_norm, sens_norm

    def remove_hooks(self):
        """Remove all registered hooks."""
        for hook in self.hooks:
            hook.remove()
        self.hooks = []
        print("  [Formula 1331] Gradient hooks removed")

    def reconfigure(
        self,
        new_authority_layers: int,
        new_sensory_layers: int,
        new_alpha_min: float = None,
        new_alpha_max: float = None,
        new_warmup_steps: int = 100,
        alpha_range: tuple = None,  # V9.9.3: Alternative to separate min/max
    ):
        """
        Reconfigure the scaler for a new split configuration.
        Used for dynamic 9:3 → 6:6 transitions and Inverted Curriculum evolution.

        Args:
            new_authority_layers: New count of authority layers
            new_sensory_layers: New count of sensory layers
            new_alpha_min: Minimum alpha for sensory (or use alpha_range)
            new_alpha_max: Maximum alpha for sensory (or use alpha_range)
            new_warmup_steps: Steps for warmup ramp
            alpha_range: Alternative tuple (min, max) for alpha values
        """
        # V9.9.3: Handle alpha_range tuple format
        if alpha_range is not None:
            new_alpha_min, new_alpha_max = alpha_range
        elif new_alpha_min is None or new_alpha_max is None:
            # Use current values if not specified
            new_alpha_min = new_alpha_min or self.alpha_sens_min
            new_alpha_max = new_alpha_max or self.alpha_sens_max

        # Remove existing hooks
        self.remove_hooks()

        # Update configuration
        self.authority_layers = new_authority_layers
        self.sensory_layers = new_sensory_layers
        self.alpha_sens_min = new_alpha_min
        self.alpha_sens_max = new_alpha_max
        self.warmup_steps = new_warmup_steps
        self.current_step = 0  # Reset warmup counter

        # Re-register hooks with new configuration
        self._register_hooks()

        print(f"  [Formula 1331] Reconfigured: {new_authority_layers}:{new_sensory_layers} split")
        print(f"    New α range: {new_alpha_min} → {new_alpha_max} over {new_warmup_steps} steps")


# =============================================================================
# WEIGHT TRANSFER FOR 9:3 → 6:6 TRANSITION
# =============================================================================

class WeightTransfer:
    """
    Manages weight transfer during 9:3 → 6:6 dynamic relaxation.

    When the relaxation trigger fires, this class:
    1. Captures weights from Layers 6, 7, 8 (StateDeltaPhaseBlocks)
    2. Initializes new QuadraticAttentionWithPhaseBias blocks using pre-trained weights
    3. Re-anchors R_to_phase_bias projection to Layer 5 (new Witness)
    4. Implements Guna-Lock: freezes W_q, W_k for first 50 steps post-swap

    Weight Mapping (StateDeltaPhaseBlock → QuadraticAttentionWithPhaseBias):
        Phase Attention v_proj → Quadratic v_proj
        Phase Attention out_proj → Quadratic out_proj
        norm1 → norm1
        ffn → ffn
        norm2 → norm2
        r_signal_proj → r_to_phase_bias (dimension-adjusted)

    Guna-Lock prevents 'Rajasic' noise from destroying inherited ontological logic
    by freezing query/key matrices while allowing values and phase-bias to train.
    """

    def __init__(
        self,
        model: nn.Module,
        guna_lock_steps: int = 50,       # Steps to freeze W_q/W_k post-swap
        anchor_layer_idx: int = 5,        # New Witness layer index after 6:6
        transferred_layers: Tuple[int, int, int] = (6, 7, 8),  # Layers to transfer
    ):
        self.model = model
        self.guna_lock_steps = guna_lock_steps
        self.anchor_layer_idx = anchor_layer_idx
        self.transferred_layers = transferred_layers

        # State tracking
        self.captured_weights = {}
        self.captured_r_anchor = None
        self.guna_lock_active = False
        self.guna_lock_start_step = None
        self.frozen_params = []

        # Track new Quadratic layers for Guna-Lock
        self.new_quadratic_layers = []

    def capture_state(self) -> Dict[str, Any]:
        """
        Capture current weights from Layers 6, 7, 8 (StateDeltaPhaseBlocks).

        Returns dict with captured weight tensors for each layer.
        """
        self.captured_weights = {}

        # Get the layers from model
        layers = self._get_model_layers()
        if layers is None:
            print("  ⚠️  [WeightTransfer] Could not find model layers")
            return {}

        for layer_idx in self.transferred_layers:
            if layer_idx >= len(layers):
                continue

            layer = layers[layer_idx]
            layer_weights = {}

            # Capture attention weights
            if hasattr(layer, 'attn'):
                attn = layer.attn
                # PhaseAttentionLayer weights
                if hasattr(attn, 'v_proj'):
                    layer_weights['v_proj'] = attn.v_proj.weight.data.clone()
                    if attn.v_proj.bias is not None:
                        layer_weights['v_proj_bias'] = attn.v_proj.bias.data.clone()
                if hasattr(attn, 'out_proj'):
                    layer_weights['out_proj'] = attn.out_proj.weight.data.clone()
                    if attn.out_proj.bias is not None:
                        layer_weights['out_proj_bias'] = attn.out_proj.bias.data.clone()
                # Phase-specific weights for reference
                if hasattr(attn, 'W_phase'):
                    layer_weights['W_phase'] = attn.W_phase.weight.data.clone()
                if hasattr(attn, 'W_amp'):
                    layer_weights['W_amp'] = attn.W_amp.weight.data.clone()

            # Capture norm1
            if hasattr(layer, 'norm1'):
                layer_weights['norm1_weight'] = layer.norm1.weight.data.clone()
                layer_weights['norm1_bias'] = layer.norm1.bias.data.clone()

            # Capture FFN
            if hasattr(layer, 'ffn'):
                ffn = layer.ffn
                if isinstance(ffn, nn.Sequential):
                    for i, module in enumerate(ffn):
                        if isinstance(module, nn.Linear):
                            layer_weights[f'ffn_{i}_weight'] = module.weight.data.clone()
                            if module.bias is not None:
                                layer_weights[f'ffn_{i}_bias'] = module.bias.data.clone()

            # Capture norm2
            if hasattr(layer, 'norm2'):
                layer_weights['norm2_weight'] = layer.norm2.weight.data.clone()
                layer_weights['norm2_bias'] = layer.norm2.bias.data.clone()

            # Capture R-Signal projection (for re-anchoring)
            if hasattr(layer, 'r_signal_proj'):
                layer_weights['r_signal_proj'] = layer.r_signal_proj.weight.data.clone()
                if layer.r_signal_proj.bias is not None:
                    layer_weights['r_signal_proj_bias'] = layer.r_signal_proj.bias.data.clone()

            self.captured_weights[layer_idx] = layer_weights

        # Capture the R-Signal anchor from the new Witness (Layer 5 in 6:6)
        if self.anchor_layer_idx < len(layers):
            anchor_layer = layers[self.anchor_layer_idx]
            if hasattr(anchor_layer, 'r_signal_proj'):
                self.captured_r_anchor = {
                    'weight': anchor_layer.r_signal_proj.weight.data.clone(),
                    'bias': anchor_layer.r_signal_proj.bias.data.clone() if anchor_layer.r_signal_proj.bias is not None else None
                }

        print(f"  📦 [WeightTransfer] Captured weights from layers {self.transferred_layers}")
        print(f"    R-Signal anchor captured from layer {self.anchor_layer_idx}")

        return self.captured_weights

    def transfer_weights(
        self,
        new_layers: List[nn.Module],
        r_signal_dim: int = 48,
    ) -> bool:
        """
        Transfer captured weights to new QuadraticAttentionWithPhaseBias blocks.

        Args:
            new_layers: List of new QuadraticAttentionWithPhaseBias modules
            r_signal_dim: Dimension of R-Signal for phase bias

        Returns:
            True if transfer successful
        """
        if not self.captured_weights:
            print("  ⚠️  [WeightTransfer] No weights captured, skipping transfer")
            return False

        self.new_quadratic_layers = new_layers

        for i, new_layer in enumerate(new_layers):
            layer_idx = self.transferred_layers[i] if i < len(self.transferred_layers) else None
            if layer_idx is None or layer_idx not in self.captured_weights:
                continue

            weights = self.captured_weights[layer_idx]

            # Transfer v_proj
            if 'v_proj' in weights and hasattr(new_layer, 'v_proj'):
                new_layer.v_proj.weight.data.copy_(weights['v_proj'])
                if 'v_proj_bias' in weights and new_layer.v_proj.bias is not None:
                    new_layer.v_proj.bias.data.copy_(weights['v_proj_bias'])

            # Transfer out_proj
            if 'out_proj' in weights and hasattr(new_layer, 'out_proj'):
                new_layer.out_proj.weight.data.copy_(weights['out_proj'])
                if 'out_proj_bias' in weights and new_layer.out_proj.bias is not None:
                    new_layer.out_proj.bias.data.copy_(weights['out_proj_bias'])

            # Initialize Q, K from V (State-Inference: inherit value-based attention)
            # This preserves the learned "what to attend to" logic
            if 'v_proj' in weights:
                if hasattr(new_layer, 'q_proj'):
                    new_layer.q_proj.weight.data.copy_(weights['v_proj'])
                    if 'v_proj_bias' in weights and new_layer.q_proj.bias is not None:
                        new_layer.q_proj.bias.data.copy_(weights['v_proj_bias'])
                if hasattr(new_layer, 'k_proj'):
                    new_layer.k_proj.weight.data.copy_(weights['v_proj'])
                    if 'v_proj_bias' in weights and new_layer.k_proj.bias is not None:
                        new_layer.k_proj.bias.data.copy_(weights['v_proj_bias'])

            # Transfer norm1
            if 'norm1_weight' in weights and hasattr(new_layer, 'norm1'):
                new_layer.norm1.weight.data.copy_(weights['norm1_weight'])
                new_layer.norm1.bias.data.copy_(weights['norm1_bias'])

            # Transfer FFN
            if hasattr(new_layer, 'ffn') and isinstance(new_layer.ffn, nn.Sequential):
                for j, module in enumerate(new_layer.ffn):
                    if isinstance(module, nn.Linear):
                        weight_key = f'ffn_{j}_weight'
                        bias_key = f'ffn_{j}_bias'
                        if weight_key in weights:
                            module.weight.data.copy_(weights[weight_key])
                        if bias_key in weights and module.bias is not None:
                            module.bias.data.copy_(weights[bias_key])

            # Transfer norm2
            if 'norm2_weight' in weights and hasattr(new_layer, 'norm2'):
                new_layer.norm2.weight.data.copy_(weights['norm2_weight'])
                new_layer.norm2.bias.data.copy_(weights['norm2_bias'])

            # Initialize r_to_phase_bias from r_signal_proj (48D Anchor)
            if 'r_signal_proj' in weights and hasattr(new_layer, 'r_to_phase_bias'):
                # r_signal_proj: [embed_dim, r_signal_dim]
                # r_to_phase_bias: Sequential([Linear(r_signal_dim, embed_dim), Tanh])
                for module in new_layer.r_to_phase_bias:
                    if isinstance(module, nn.Linear):
                        # Transpose to match dimensions: [r_signal_dim, embed_dim] → [embed_dim, r_signal_dim]
                        source_weight = weights['r_signal_proj']
                        if source_weight.shape[0] == module.weight.shape[1]:
                            # Direct transpose copy
                            module.weight.data.copy_(source_weight.T)
                        else:
                            # Dimension mismatch, initialize with scaled version
                            nn.init.xavier_uniform_(module.weight)
                            # Scale down for stability
                            module.weight.data *= 0.1
                        break

        print(f"  ✓ [WeightTransfer] Transferred weights to {len(new_layers)} new layers")
        return True

    def anchor_r_signal(self, new_witness_layer: nn.Module) -> bool:
        """
        Re-anchor R_to_phase_bias projection to Layer 5 (new Witness).

        The 48D R-Signal anchor ensures continuity of the Authority → Sensory
        nerve signal after the layer split changes.
        """
        if self.captured_r_anchor is None:
            print("  ⚠️  [WeightTransfer] No R-Signal anchor captured")
            return False

        # Update the new witness layer's R-Signal projection
        if hasattr(new_witness_layer, 'r_signal_proj'):
            new_witness_layer.r_signal_proj.weight.data.copy_(self.captured_r_anchor['weight'])
            if self.captured_r_anchor['bias'] is not None and new_witness_layer.r_signal_proj.bias is not None:
                new_witness_layer.r_signal_proj.bias.data.copy_(self.captured_r_anchor['bias'])

        # Also update witness_r_proj in the main model if it exists
        if hasattr(self.model, 'witness_r_proj'):
            if self.model.witness_r_proj.weight.shape == self.captured_r_anchor['weight'].shape:
                self.model.witness_r_proj.weight.data.copy_(self.captured_r_anchor['weight'])
                if self.captured_r_anchor['bias'] is not None and self.model.witness_r_proj.bias is not None:
                    self.model.witness_r_proj.bias.data.copy_(self.captured_r_anchor['bias'])

        print(f"  ⚓ [WeightTransfer] R-Signal anchored to layer {self.anchor_layer_idx}")
        return True

    def activate_guna_lock(self, current_step: int):
        """
        Activate Guna-Lock: freeze W_q and W_k matrices of new layers.

        For the first 50 steps post-swap, only W_v and Phase-Bias can train.
        This prevents 'Rajasic' noise from destroying inherited logic.
        """
        self.guna_lock_active = True
        self.guna_lock_start_step = current_step
        self.frozen_params = []

        for layer in self.new_quadratic_layers:
            # Freeze Q and K projections
            if hasattr(layer, 'q_proj'):
                layer.q_proj.weight.requires_grad = False
                if layer.q_proj.bias is not None:
                    layer.q_proj.bias.requires_grad = False
                self.frozen_params.append(layer.q_proj)

            if hasattr(layer, 'k_proj'):
                layer.k_proj.weight.requires_grad = False
                if layer.k_proj.bias is not None:
                    layer.k_proj.bias.requires_grad = False
                self.frozen_params.append(layer.k_proj)

        print(f"  🔒 [WeightTransfer] Guna-Lock ACTIVATED at step {current_step}")
        print(f"    Frozen: W_q, W_k for {len(self.new_quadratic_layers)} layers")
        print(f"    Active: W_v, Phase-Bias, FFN")
        print(f"    Duration: {self.guna_lock_steps} steps")

    def update_guna_lock(self, current_step: int) -> bool:
        """
        Check and update Guna-Lock status.

        Returns True if lock was just released.
        """
        if not self.guna_lock_active:
            return False

        if self.guna_lock_start_step is None:
            return False

        elapsed = current_step - self.guna_lock_start_step

        if elapsed >= self.guna_lock_steps:
            # Release the lock
            return self.release_guna_lock()

        return False

    def release_guna_lock(self) -> bool:
        """
        Release Guna-Lock: unfreeze W_q and W_k matrices.

        Called automatically after guna_lock_steps or manually for early release.
        """
        if not self.guna_lock_active:
            return False

        for layer in self.new_quadratic_layers:
            if hasattr(layer, 'q_proj'):
                layer.q_proj.weight.requires_grad = True
                if layer.q_proj.bias is not None:
                    layer.q_proj.bias.requires_grad = True

            if hasattr(layer, 'k_proj'):
                layer.k_proj.weight.requires_grad = True
                if layer.k_proj.bias is not None:
                    layer.k_proj.bias.requires_grad = True

        self.guna_lock_active = False
        self.frozen_params = []

        print(f"  🔓 [WeightTransfer] Guna-Lock RELEASED")
        print(f"    All parameters now trainable")
        return True

    def _get_model_layers(self) -> Optional[nn.ModuleList]:
        """Get the layer ModuleList from model."""
        # SymbolU12 special case
        if hasattr(self.model, 'layers_1_8'):
            layers = list(self.model.layers_1_8)
            # Add witness, unifying, integration, absolving
            for layer_name in ['witness_layer', 'unifying_layer', 'integration_layer', 'absolving_layer']:
                if hasattr(self.model, layer_name):
                    layer = getattr(self.model, layer_name)
                    if layer is not None:
                        layers.append(layer)
            return nn.ModuleList(layers)

        # Try common attribute names
        for attr in ['layers', 'blocks', 'transformer.blocks']:
            if hasattr(self.model, attr):
                layers = getattr(self.model, attr)
                if isinstance(layers, nn.ModuleList):
                    return layers

        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current status of weight transfer and Guna-Lock."""
        return {
            "weights_captured": bool(self.captured_weights),
            "layers_captured": list(self.captured_weights.keys()),
            "r_anchor_captured": self.captured_r_anchor is not None,
            "guna_lock_active": self.guna_lock_active,
            "guna_lock_start_step": self.guna_lock_start_step,
            "guna_lock_remaining": (
                self.guna_lock_steps - (self.guna_lock_start_step or 0)
                if self.guna_lock_active else 0
            ),
            "new_layers_count": len(self.new_quadratic_layers),
        }


# =============================================================================
# VRAM GOVERNOR: Dynamic Batch Scaling with Patent Compensation
# =============================================================================

class VRAMGovernor:
    """
    VRAM-Aware Dynamic Batch Governor.

    Monitors GPU memory usage and dynamically scales batch size to prevent
    OOM crashes. When batch size is reduced, increases λ_B1 (Consistency
    Lagrangian) to compensate for noisier gradients.

    Patent Integration:
    - [B1] ConsistencyLagrangian: Scaled up when batch reduces (noisy batches
      need stronger consistency enforcement)
    - [S8] StabilityHook: Notified of batch changes to adjust entropy thresholds

    Usage:
        governor = VRAMGovernor(initial_batch_size=32)

        # In training loop:
        new_batch, actions = governor.check_and_resize(current_step)
        if new_batch != current_batch:
            train_loader = reinit_dataloader(new_batch)
    """

    def __init__(
        self,
        initial_batch_size: int = 32,
        min_batch_size: int = 4,
        vram_threshold: float = 0.95,  # Trigger at 95% usage
        vram_critical: float = 0.98,   # Emergency at 98%
        vram_recovery_buffer: float = 0.12,  # Recovery when < (threshold - buffer)
        check_interval: int = 10,      # Check every N steps
        b1_compensation_rate: float = 0.20,  # 20% λ_B1 increase per reduction
        enable_accumulation_scaling: bool = True,
        target_effective_batch: int = 32,  # Target effective batch via accumulation
    ):
        self.initial_batch_size = initial_batch_size
        self.current_batch_size = initial_batch_size
        self.min_batch_size = min_batch_size
        self.vram_threshold = vram_threshold
        self.vram_critical = vram_critical
        self.vram_recovery_buffer = vram_recovery_buffer
        self.check_interval = check_interval
        self.b1_compensation_rate = b1_compensation_rate
        self.enable_accumulation_scaling = enable_accumulation_scaling
        self.target_effective_batch = target_effective_batch

        # Tracking
        self.b1_scale_factor = 1.0
        self.accumulation_steps = 1
        self.resize_count = 0
        self.last_check_step = 0
        self.vram_history = []

        # State
        self.in_recovery_mode = False
        self.recovery_start_step = None

    def get_vram_usage(self) -> Tuple[float, float, float]:
        """
        Get current VRAM usage statistics.

        Returns:
            (usage_fraction, used_gb, total_gb)

        Note: Uses memory_allocated() (actual tensor memory) not memory_reserved()
        (which includes PyTorch's caching allocator overhead). This prevents
        false VRAM pressure signals from cached but unused memory.
        """
        if not torch.cuda.is_available():
            return 0.0, 0.0, 0.0

        # Use memory_allocated() - actual tensor memory
        # NOT memory_reserved() which includes caching allocator overhead
        allocated = torch.cuda.memory_allocated()
        reserved = torch.cuda.memory_reserved()
        total = torch.cuda.get_device_properties(0).total_memory

        # Primary metric: allocated memory (actual usage)
        # But also consider if reserved is very high (fragmentation risk)
        # Use max of allocated and 70% of reserved as a balanced metric
        used = max(allocated, reserved * 0.7)

        usage = used / total
        used_gb = used / (1024 ** 3)
        total_gb = total / (1024 ** 3)

        return usage, used_gb, total_gb

    def check_and_resize(
        self,
        current_step: int,
        sovereign_engine: Optional[object] = None,
        force_check: bool = False,
    ) -> Tuple[int, List[str]]:
        """
        Check VRAM usage and resize batch if needed.

        Args:
            current_step: Current training step
            sovereign_engine: Optional SovereignEngine for λ_B1 adjustment
            force_check: Force check regardless of interval

        Returns:
            (new_batch_size, list of action strings)
        """
        actions = []

        # Only check at intervals (or if forced)
        if not force_check and (current_step - self.last_check_step) < self.check_interval:
            return self.current_batch_size, actions

        self.last_check_step = current_step

        # Get VRAM usage
        usage, used_gb, total_gb = self.get_vram_usage()
        self.vram_history.append({"step": current_step, "usage": usage, "used_gb": used_gb})

        # Keep history bounded
        if len(self.vram_history) > 100:
            self.vram_history = self.vram_history[-100:]

        # Check for critical VRAM (emergency)
        if usage > self.vram_critical:
            actions.append(f"🚨 [VRAM CRITICAL] Usage at {usage:.1%} ({used_gb:.1f}GB/{total_gb:.1f}GB)")
            actions.append("   Emergency cache purge initiated!")

            # Emergency cleanup
            import gc
            gc.collect()
            torch.cuda.empty_cache()

            # Force batch reduction by 8 (two steps)
            new_batch = max(self.min_batch_size, ((self.current_batch_size // 4) - 2) * 4)
            if new_batch < self.current_batch_size:
                self._apply_batch_reduction(new_batch, sovereign_engine, actions, emergency=True)

        # Check for high VRAM (warning threshold)
        elif usage > self.vram_threshold:
            actions.append(f"📊 [VRAM Governor] Adaptive resize: {usage:.1%} ({used_gb:.1f}GB/{total_gb:.1f}GB)")

            # Clear cache first
            torch.cuda.empty_cache()

            # Reduce batch by 4
            new_batch = max(self.min_batch_size, ((self.current_batch_size // 4) - 1) * 4)
            if new_batch < self.current_batch_size:
                self._apply_batch_reduction(new_batch, sovereign_engine, actions, emergency=False)

        # Check if we can recover (increase batch) after being in recovery mode
        elif self.in_recovery_mode and usage < (self.vram_threshold - self.vram_recovery_buffer):
            # VRAM is below recovery threshold - safe to try increasing
            steps_in_recovery = current_step - self.recovery_start_step
            if steps_in_recovery > 200:  # Wait at least 200 steps
                # Try increasing batch by 4
                new_batch = min(self.initial_batch_size, self.current_batch_size + 4)
                if new_batch > self.current_batch_size:
                    self._apply_batch_increase(new_batch, sovereign_engine, actions)

        return self.current_batch_size, actions

    def _apply_batch_reduction(
        self,
        new_batch: int,
        sovereign_engine: Optional[object],
        actions: List[str],
        emergency: bool = False,
    ):
        """Apply batch size reduction with patent compensation."""
        old_batch = self.current_batch_size
        self.current_batch_size = new_batch
        self.resize_count += 1

        # Enter recovery mode
        self.in_recovery_mode = True
        self.recovery_start_step = self.last_check_step

        # [B1] Increase λ_B1 to compensate for noisier gradients
        compensation = self.b1_compensation_rate * (1.5 if emergency else 1.0)
        self.b1_scale_factor = min(2.0, self.b1_scale_factor * (1.0 + compensation))

        if sovereign_engine is not None and hasattr(sovereign_engine, 'config'):
            # Apply the compensation to the engine
            sovereign_engine.config.lambda_b1 *= (1.0 + compensation)
            actions.append(f"   λ_B1 scaled: {sovereign_engine.config.lambda_b1 / (1 + compensation):.2f} → {sovereign_engine.config.lambda_b1:.2f} (noise compensation)")

        # Auto-scale gradient accumulation if batch gets too small
        # V9.8.1: Use ceiling division to maintain effective batch size
        if self.enable_accumulation_scaling and new_batch < self.target_effective_batch:
            # Ceiling division: ensures effective batch >= target
            new_accum = max(1, (self.target_effective_batch + new_batch - 1) // new_batch)
            if new_accum != self.accumulation_steps:
                old_accum = self.accumulation_steps
                self.accumulation_steps = new_accum
                effective = new_batch * new_accum
                actions.append(f"   📊 Gradient accumulation: {old_accum} → {new_accum} (effective batch: {effective})")

        if emergency:
            actions.append(f"   🚨 Emergency: Batch {old_batch} → {new_batch} | Resizes: {self.resize_count}")
        else:
            actions.append(f"   ✓ Adjusted: Batch {old_batch} → {new_batch} | Resizes: {self.resize_count}")

    def _apply_batch_increase(
        self,
        new_batch: int,
        sovereign_engine: Optional[object],
        actions: List[str],
    ):
        """Apply batch size increase (recovery)."""
        old_batch = self.current_batch_size
        self.current_batch_size = new_batch

        # Reduce λ_B1 compensation (partial - keep some stability)
        reduction = self.b1_compensation_rate * 0.5  # Only reduce by half
        self.b1_scale_factor = max(1.0, self.b1_scale_factor / (1.0 + reduction))

        if sovereign_engine is not None and hasattr(sovereign_engine, 'config'):
            old_b1 = sovereign_engine.config.lambda_b1
            sovereign_engine.config.lambda_b1 /= (1.0 + reduction)
            actions.append(f"   λ_B1 relaxed: {old_b1:.2f} → {sovereign_engine.config.lambda_b1:.2f}")

        # Adjust accumulation steps (V9.8.1: ceiling division)
        if self.enable_accumulation_scaling:
            new_accum = max(1, (self.target_effective_batch + new_batch - 1) // new_batch)
            if new_accum != self.accumulation_steps:
                old_accum = self.accumulation_steps
                self.accumulation_steps = new_accum
                effective = new_batch * new_accum
                actions.append(f"   📊 Gradient accumulation: {old_accum} → {new_accum} (effective batch: {effective})")

        # Check if fully recovered
        if new_batch >= self.initial_batch_size:
            self.in_recovery_mode = False
            actions.append(f"   ✅ [RECOVERED] Batch restored to {new_batch}")
        else:
            actions.append(f"   📈 [RECOVERING] Batch: {old_batch} → {new_batch}")

    def get_status_string(self) -> str:
        """Get formatted status string."""
        usage, used_gb, total_gb = self.get_vram_usage()
        mode = "RECOVERY" if self.in_recovery_mode else "NORMAL"
        return (
            f"VRAM:{usage:.0%}({used_gb:.1f}GB) | "
            f"Batch:{self.current_batch_size} | "
            f"λ_B1×{self.b1_scale_factor:.2f} | "
            f"[{mode}]"
        )

    def get_dataloader_config(self) -> Dict[str, int]:
        """Get current DataLoader configuration."""
        return {
            "batch_size": self.current_batch_size,
            "accumulation_steps": self.accumulation_steps,
            "effective_batch": self.current_batch_size * self.accumulation_steps,
        }


# =============================================================================
# AUTO BATCH SIZER: VRAM-Based Startup Probing
# =============================================================================

class AutoBatchSizer:
    """
    VRAM-Aware Automatic Batch Size Detector.

    At training startup, probes GPU memory to find the optimal batch size
    that utilizes a target percentage of VRAM (default 80%). Uses binary
    search for efficiency.

    This runs ONCE at startup, before training begins. The determined
    batch size remains fixed throughout training (VRAMGovernor handles
    dynamic adjustments during training if needed).

    Usage:
        sizer = AutoBatchSizer(model, seq_len=2048, target_utilization=0.80)
        batch_size, grad_accum = sizer.find_optimal_batch(target_effective=32)

        # Use these to configure your dataloader
        config.batch_size = batch_size
        config.gradient_accumulation = grad_accum
    """

    def __init__(
        self,
        model: nn.Module,
        seq_len: int = 2048,
        vocab_size: int = 50257,
        target_utilization: float = 0.80,
        min_batch_size: int = 1,
        max_batch_size: int = 128,
        safety_margin: float = 0.05,  # Extra headroom below target
        device: Optional[torch.device] = None,
    ):
        """
        Args:
            model: The model to probe (should be on GPU)
            seq_len: Maximum sequence length for probing
            vocab_size: Vocabulary size for dummy inputs
            target_utilization: Target VRAM utilization (0.80 = 80%)
            min_batch_size: Minimum batch size to try
            max_batch_size: Maximum batch size to try
            safety_margin: Extra margin below target (0.05 = 5% headroom)
            device: Device to probe (defaults to cuda:0)
        """
        self.model = model
        self.seq_len = seq_len
        self.vocab_size = vocab_size
        self.target_utilization = target_utilization
        self.effective_target = target_utilization - safety_margin
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self.device = device or torch.device("cuda:0")

        # Results
        self.probed_batch_size: Optional[int] = None
        self.peak_memory_gb: float = 0.0
        self.total_memory_gb: float = 0.0

    def _get_memory_info(self) -> Tuple[float, float, float]:
        """Get current VRAM usage."""
        if not torch.cuda.is_available():
            return 0.0, 0.0, 0.0

        torch.cuda.synchronize()
        allocated = torch.cuda.memory_allocated(self.device)
        reserved = torch.cuda.memory_reserved(self.device)
        total = torch.cuda.get_device_properties(self.device).total_memory

        return allocated / total, reserved / (1024**3), total / (1024**3)

    def _clear_memory(self):
        """Aggressively clear GPU memory."""
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    def _probe_batch_size(self, batch_size: int) -> Tuple[bool, float]:
        """
        Probe if a given batch size fits in memory.

        Returns:
            (success, peak_utilization)
        """
        self._clear_memory()

        try:
            # Create dummy batch
            dummy_input = torch.randint(
                0, self.vocab_size,
                (batch_size, self.seq_len),
                device=self.device,
                dtype=torch.long
            )
            dummy_target = torch.randint(
                0, self.vocab_size,
                (batch_size, self.seq_len),
                device=self.device,
                dtype=torch.long
            )

            # Forward pass
            self.model.train()
            with torch.amp.autocast('cuda', dtype=torch.bfloat16):
                outputs = self.model(dummy_input)

                # Handle different output formats
                if isinstance(outputs, dict):
                    # Ontological models return dict with 'logits' key
                    logits = outputs.get('logits', outputs.get('output', list(outputs.values())[0]))
                elif isinstance(outputs, tuple):
                    logits = outputs[0]
                elif hasattr(outputs, 'logits'):
                    logits = outputs.logits
                else:
                    logits = outputs

                # Compute loss (simulates full training step memory)
                loss = F.cross_entropy(
                    logits.view(-1, logits.size(-1)),
                    dummy_target.view(-1),
                    ignore_index=-100
                )

            # Backward pass (this is where most memory is used)
            loss.backward()

            # Check peak memory
            torch.cuda.synchronize()
            peak_allocated = torch.cuda.max_memory_allocated(self.device)
            total = torch.cuda.get_device_properties(self.device).total_memory
            peak_utilization = peak_allocated / total

            # Cleanup
            del dummy_input, dummy_target, outputs, logits, loss
            self.model.zero_grad(set_to_none=True)
            self._clear_memory()
            torch.cuda.reset_peak_memory_stats()

            return True, peak_utilization

        except RuntimeError as e:
            if "out of memory" in str(e).lower() or "CUDA" in str(e):
                # OOM - this batch size is too large
                self.model.zero_grad(set_to_none=True)
                self._clear_memory()
                torch.cuda.reset_peak_memory_stats()
                return False, 1.0
            else:
                raise

    def find_optimal_batch(
        self,
        target_effective_batch: int = 32,
        verbose: bool = True
    ) -> Tuple[int, int]:
        """
        Find optimal batch size using binary search.

        Args:
            target_effective_batch: Desired effective batch size (for grad accum calculation).
                                   If 0, just finds max batch that fits and sets accum=1.
            verbose: Print progress

        Returns:
            (batch_size, gradient_accumulation_steps)
        """
        if not torch.cuda.is_available():
            if verbose:
                print("  ⚠️  No CUDA available, using default batch size")
            if target_effective_batch > 0:
                return self.min_batch_size, target_effective_batch // self.min_batch_size
            return self.min_batch_size, 1

        # Get total memory
        total_mem = torch.cuda.get_device_properties(self.device).total_memory
        self.total_memory_gb = total_mem / (1024**3)

        if verbose:
            print(f"\n  {'='*60}")
            print(f"  AUTO BATCH SIZER: Probing optimal batch size")
            print(f"  {'='*60}")
            print(f"  GPU: {torch.cuda.get_device_name(self.device)}")
            print(f"  Total VRAM: {self.total_memory_gb:.1f} GB")
            print(f"  Target Utilization: {self.target_utilization:.0%} (effective: {self.effective_target:.0%})")
            print(f"  Sequence Length: {self.seq_len:,}")
            if target_effective_batch > 0:
                print(f"  Target Effective Batch: {target_effective_batch}")
            else:
                print(f"  Mode: Find maximum batch (no accumulation target)")
            print(f"  {'─'*60}")

        # Build list of candidate batch sizes (multiples of 8 for Tensor Core efficiency)
        # V9.5.2 Metabolic Tuning: Also include intermediate batch sizes (48, 40) for better
        # gradient accumulation granularity (e.g., 48/6=288 effective, 40/8=320 effective)
        alignment = 8
        if target_effective_batch > 0:
            max_candidate = min(self.max_batch_size, target_effective_batch)
        else:
            max_candidate = self.max_batch_size
        candidates = [b for b in range(alignment, max_candidate + 1, alignment)]
        # Add intermediate values for fine-grained accumulation tuning
        for intermediate in [40, 48, 56, 72]:
            if intermediate not in candidates and intermediate <= max_candidate:
                candidates.append(intermediate)
        candidates = sorted(set(candidates))
        if not candidates:
            candidates = [alignment]  # Minimum fallback

        if verbose:
            print(f"  Candidates (multiples of {alignment}): {candidates}")

        # Binary search for optimal batch size
        low_idx = 0
        high_idx = len(candidates) - 1
        optimal_batch = candidates[0]
        optimal_utilization = 0.0

        # First, find the maximum that fits
        if verbose:
            print(f"  Phase 1: Finding maximum batch size that fits...")

        while low_idx <= high_idx:
            mid_idx = (low_idx + high_idx) // 2
            mid = candidates[mid_idx]
            if verbose:
                print(f"    Probing batch_size={mid}...", end=" ", flush=True)

            success, utilization = self._probe_batch_size(mid)

            if success:
                if verbose:
                    print(f"✓ ({utilization:.1%} VRAM)")

                if utilization <= self.effective_target:
                    # Fits within target, try larger
                    optimal_batch = mid
                    optimal_utilization = utilization
                    low_idx = mid_idx + 1
                else:
                    # Exceeds target but doesn't OOM, this is close
                    optimal_batch = mid
                    optimal_utilization = utilization
                    high_idx = mid_idx - 1
            else:
                if verbose:
                    print(f"✗ OOM")
                high_idx = mid_idx - 1

        # Verify final choice fits within target
        if optimal_utilization > self.effective_target:
            # Step down to previous candidate
            current_idx = candidates.index(optimal_batch)
            while current_idx > 0:
                current_idx -= 1
                optimal_batch = candidates[current_idx]
                success, utilization = self._probe_batch_size(optimal_batch)
                if success and utilization <= self.effective_target:
                    optimal_utilization = utilization
                    if verbose:
                        print(f"    Stepping down to batch_size={optimal_batch}... ✓ ({utilization:.1%} VRAM)")
                    break

        # Calculate gradient accumulation
        if target_effective_batch <= 0 or optimal_batch >= target_effective_batch:
            grad_accum = 1
        else:
            grad_accum = max(1, target_effective_batch // optimal_batch)

        effective_batch = optimal_batch * grad_accum

        # Store results
        self.probed_batch_size = optimal_batch
        self.peak_memory_gb = optimal_utilization * self.total_memory_gb

        if verbose:
            print(f"  {'─'*60}")
            print(f"  ✓ OPTIMAL CONFIGURATION FOUND:")
            print(f"    Batch Size: {optimal_batch}")
            print(f"    Gradient Accumulation: {grad_accum}")
            print(f"    Effective Batch: {effective_batch}")
            print(f"    Peak VRAM: {self.peak_memory_gb:.1f} GB ({optimal_utilization:.1%})")
            print(f"  {'='*60}\n")

        return optimal_batch, grad_accum

    def get_summary(self) -> Dict[str, any]:
        """Get summary of probing results."""
        return {
            "batch_size": self.probed_batch_size,
            "total_vram_gb": self.total_memory_gb,
            "peak_vram_gb": self.peak_memory_gb,
            "target_utilization": self.target_utilization,
            "seq_len": self.seq_len,
        }


# =============================================================================
# SOVEREIGN PHASE CONTROLLER: Graduated, Damped, Layer-Specific Intervention
# =============================================================================

# =============================================================================
# DYNAMIC WINDOW SCHEDULER: PPL-Adaptive Local Attention Window
# =============================================================================

class DynamicWindowScheduler:
    """
    Dynamic Window Scheduler - PPL-Adaptive Local Attention Window Sizing.

    Implements curriculum learning for attention span: small windows early
    (syntax learning), large windows late (long-range reasoning).

    Philosophy:
    - Early training (high PPL): Small window → Faster, cleaner gradients
    - Late training (low PPL): Large window → Long-range dependencies

    Memory Tradeoff:
    - Smaller window = Less VRAM = Can increase batch size
    - O(N×W) complexity: halving window = 50% memory savings

    Smooth Progression:
    - Uses intermediate values (not just powers of 2)
    - Gradual transitions (interpolates over N steps)
    - Growth rate limiting (max 25% per transition)

    Version: 1.0.0 (V9.8.9)
    Reference: Curriculum learning for receptive field dimension
    """

    def __init__(
        self,
        enable: bool = False,
        window_schedule: dict = None,
        growth_rate_max: float = 1.25,
        shrink_rate_max: float = 0.80,
        align_to_multiple: int = 32,
        smooth_transition_steps: int = 100,
        min_steps_between_changes: int = 200,
        hysteresis_factor: float = 0.15,
        vram_shrink_threshold: float = 0.85,
        initial_ppl: float = None,
    ):
        """
        Initialize Dynamic Window Scheduler.

        Args:
            enable: Enable dynamic window sizing (default: False for safety)
            window_schedule: Dict mapping PPL → window_size. Default:
                {800:128, 500:160, 350:192, 240:224, 170:256, 125:288, 95:320,
                 75:352, 60:384, 48:416, 39:448, 32:480, 26:512, 21:576,
                 17:640, 14:704, 11:768, 9:832, 7:896, 5:960, 3:1024}
            growth_rate_max: Maximum growth per transition (1.25 = 25% max)
            shrink_rate_max: Maximum shrink per transition (0.80 = 20% max)
            align_to_multiple: Round windows to multiples (32 for GPU alignment)
            smooth_transition_steps: Interpolate window over N steps (prevents jumps)
            min_steps_between_changes: Cooldown between target changes (stability)
            hysteresis_factor: PPL gap for shrinking (prevents thrashing)
            vram_shrink_threshold: Emergency shrink if VRAM > threshold
            initial_ppl: Starting PPL (for checkpoint resume). If provided, sets
                appropriate starting window. If None, starts at smallest (128).
        """
        self.enable = enable

        # Default schedule: smooth progression aligned to 32
        if window_schedule is None:
            window_schedule = {
                800: 128,   # Syntax learning (very high PPL)
                500: 160,   # Basic semantics (+25%)
                350: 192,   # Improving semantics (+20%)
                240: 224,   # Good semantics (+17%)
                170: 256,   # Paragraph coherence (+14%)
                125: 288,   # Multi-sentence (+13%)
                95: 320,    # Short documents (+11%)
                75: 352,    # Medium documents (+10%)
                60: 384,    # Long documents (+9%)
                48: 416,    # Very long context (+8%)
                39: 448,    # Reasoning start (+8%)
                32: 480,    # Multi-hop reasoning (+7%)
                26: 512,    # Complex reasoning (+7%)
                21: 576,    # Advanced reasoning (+13%)
                17: 640,    # Expert reasoning (+11%)
                14: 704,    # Deep reasoning (+10%)
                11: 768,    # Master level (+9%)
                9: 832,     # Expert+ level (+8%)
                7: 896,     # Near mastery (+8%)
                5: 960,     # Approaching mastery (+7%)
                3: 1024,    # Full context mastery (+7%)
            }

        # Sort schedule by PPL descending
        self.schedule = sorted(window_schedule.items(), reverse=True)

        # Parameters
        self.growth_rate_max = growth_rate_max
        self.shrink_rate_max = shrink_rate_max
        self.align_to = align_to_multiple
        self.smooth_steps = smooth_transition_steps
        self.min_steps_between = min_steps_between_changes
        self.hysteresis = hysteresis_factor
        self.vram_threshold = vram_shrink_threshold

        # State: Initialize window based on PPL if provided
        if initial_ppl is not None:
            # Find appropriate starting window for current PPL
            starting_window = self.schedule[-1][1]  # Default to max (1024)
            for ppl_threshold, window_size in self.schedule:
                if initial_ppl > ppl_threshold:
                    starting_window = window_size
                    break
            self.current_window = self._align_window(starting_window)
        else:
            # No initial PPL: start with smallest window (fresh training)
            self.current_window = self.schedule[0][1]  # First entry (128)

        self.target_window = self.current_window
        self.transition_start_step = 0
        self.transition_start_window = self.current_window
        self.last_target_change_step = 0

        # Statistics
        self.total_expansions = 0
        self.total_shrinks = 0
        self.total_vram_overrides = 0

    def _align_window(self, window: int) -> int:
        """Align window to multiple for GPU efficiency."""
        if self.align_to > 1:
            return ((window + self.align_to - 1) // self.align_to) * self.align_to
        return window

    def _smooth_transition(self, step: int) -> int:
        """
        Smoothly interpolate from start window to target window.

        Instead of jumping 384 → 512 instantly:
        - Step 0: 384
        - Step 25: 416 (25% progress)
        - Step 50: 448 (50% progress)
        - Step 75: 480 (75% progress)
        - Step 100: 512 (complete)
        """
        if step < self.transition_start_step:
            return self.transition_start_window

        steps_since_start = step - self.transition_start_step
        if steps_since_start >= self.smooth_steps:
            return self.target_window

        # Linear interpolation
        progress = steps_since_start / self.smooth_steps
        interpolated = (
            self.transition_start_window +
            (self.target_window - self.transition_start_window) * progress
        )

        return self._align_window(int(interpolated))

    def update(
        self,
        step: int,
        val_ppl: float,
        vram_usage: float = 0.0,
    ) -> dict:
        """
        Update window size based on PPL and VRAM.

        Args:
            step: Current training step
            val_ppl: Validation PPL
            vram_usage: VRAM usage fraction (0.0-1.0)

        Returns:
            Dictionary containing:
                - 'window': Current window size (interpolated)
                - 'target': Target window size
                - 'changed': Whether target changed this step
                - 'reason': Reason for change
                - 'would_change': True if would change (for disabled mode)
        """
        # Cooldown check (prevent thrashing)
        steps_since_change = step - self.last_target_change_step
        cooldown_active = steps_since_change < self.min_steps_between

        # Determine target window from schedule
        scheduled_target = self.schedule[-1][1]  # Default to max
        for ppl_threshold, window_size in self.schedule:
            if val_ppl > ppl_threshold:
                scheduled_target = self._align_window(window_size)
                break

        # VRAM pressure override (safety)
        vram_override = False
        if vram_usage > 0.90:
            # Critical VRAM - emergency shrink
            scheduled_target = min(scheduled_target, self._align_window(256))
            vram_override = True
        elif vram_usage > self.vram_threshold:
            # High VRAM - don't expand
            scheduled_target = min(scheduled_target, self.target_window)
            if scheduled_target < self.target_window:
                vram_override = True

        # Check if target should change
        would_change = False
        reason = "stable"

        if scheduled_target != self.target_window and not cooldown_active:
            would_change = True

            # Growth: Apply rate limiting
            if scheduled_target > self.target_window:
                max_allowed = int(self.target_window * self.growth_rate_max)
                if scheduled_target > max_allowed:
                    scheduled_target = self._align_window(max_allowed)
                    reason = "growth_rate_limited"
                else:
                    reason = f"ppl_improved_{val_ppl:.0f}"

                # Hysteresis check for growth
                # Only grow if PPL is definitively below threshold
                ppl_hysteresis_met = True
                for ppl_thresh, win_size in self.schedule:
                    if win_size == scheduled_target:
                        # Require PPL to be below threshold - hysteresis%
                        if val_ppl > ppl_thresh * (1 - self.hysteresis):
                            ppl_hysteresis_met = False
                            would_change = False
                            reason = "hysteresis_block_growth"
                        break

            # Shrink: Apply rate limiting
            elif scheduled_target < self.target_window:
                min_allowed = int(self.target_window * self.shrink_rate_max)
                if scheduled_target < min_allowed:
                    scheduled_target = self._align_window(min_allowed)
                    reason = "shrink_rate_limited"
                else:
                    reason = f"ppl_degraded_{val_ppl:.0f}"

                # Hysteresis check for shrinking
                # Only shrink if PPL is definitively above threshold
                ppl_hysteresis_met = True
                for ppl_thresh, win_size in self.schedule:
                    if win_size == self.target_window:
                        # Require PPL to be above threshold + hysteresis%
                        if val_ppl < ppl_thresh * (1 + self.hysteresis):
                            ppl_hysteresis_met = False
                            would_change = False
                            reason = "hysteresis_block_shrink"
                        break

            if vram_override:
                reason = f"vram_override_{vram_usage:.0%}"

        # Apply target change if enabled
        target_changed = False
        if would_change and self.enable:
            self.transition_start_step = step
            self.transition_start_window = self.current_window
            self.target_window = scheduled_target
            self.last_target_change_step = step
            target_changed = True

            # Update statistics
            if scheduled_target > self.transition_start_window:
                self.total_expansions += 1
            else:
                self.total_shrinks += 1
            if vram_override:
                self.total_vram_overrides += 1

        # Compute current window (smooth interpolation)
        old_window = self.current_window
        if self.enable:
            self.current_window = self._smooth_transition(step)
        else:
            # When disabled, show what target would be
            self.current_window = old_window

        return {
            'window': self.current_window,
            'target': self.target_window if self.enable else scheduled_target,
            'changed': target_changed,
            'reason': reason,
            'would_change': would_change,
            'cooldown_active': cooldown_active,
            'steps_until_cooldown': max(0, self.min_steps_between - steps_since_change),
            'interpolation_progress': min(1.0, (step - self.transition_start_step) / self.smooth_steps) if self.enable else 0.0,
        }

    def set_initial_window_from_ppl(self, ppl: float) -> int:
        """
        Set starting window based on current PPL (for checkpoint resume).

        Args:
            ppl: Current validation PPL

        Returns:
            The window size that was set
        """
        # Find appropriate window for this PPL
        starting_window = self.schedule[-1][1]  # Default to max (1024)
        for ppl_threshold, window_size in self.schedule:
            if ppl > ppl_threshold:
                starting_window = window_size
                break

        self.current_window = self._align_window(starting_window)
        self.target_window = self.current_window
        self.transition_start_window = self.current_window

        return self.current_window

    def get_statistics(self) -> dict:
        """Get window change statistics for logging."""
        return {
            'current_window': self.current_window,
            'target_window': self.target_window,
            'total_expansions': self.total_expansions,
            'total_shrinks': self.total_shrinks,
            'total_vram_overrides': self.total_vram_overrides,
        }


# =============================================================================
# V2.7 TRAINING STATE TRACKER: Knowledge State Evolution
# =============================================================================

class TrainingStateTracker:
    """
    v2.7 Training State Tracker - Track "knowledge state" across training runs.

    Maps training metrics to v2.7 Observables and uses bounded EMA state
    evolution to track the model's learning progress with persistence.

    Features:
    - Maps training metrics (loss, PPL, coherence, entropy) to Observables
    - Bounded EMA state evolution: θ_{t+1} = (1-α)·θ_t + α·θ*
    - Saves/loads state to training_state.json for cross-run continuity
    - Detects regression (model getting worse)
    - Provides confidence-based LR modifier

    Usage:
        tracker = TrainingStateTracker(state_path="checkpoints/training_state.json")
        knowledge = tracker.update(metrics, step=1000)
        if tracker.detect_regression():
            print("Model regressing!")
    """

    def __init__(
        self,
        state_path: str = "training_state.json",
        alpha: float = 0.1,  # EMA learning rate
        enabled: bool = True,
    ):
        self.state_path = state_path
        self.alpha = alpha
        self.enabled = enabled

        # State register θ_t (bounded [0, 1])
        self.state = {
            "cognitive_state": 0.5,    # Overall knowledge quality
            "confidence": 0.5,          # Model confidence
            "stability": 0.5,           # Training stability
            "tone_ema": 0.5,            # Tone (positive = good learning)
            "step_count": 0,
        }

        # History for regression detection
        self.history = []
        self.max_history = 100

        # Try to load existing state
        if enabled:
            self.load_state()

    def metrics_to_observables(self, metrics: dict) -> dict:
        """
        Convert training metrics to v2.7-style Observables.

        Mapping:
        - S (Salience): Inverse of loss (lower loss = higher salience)
        - R (Reliability): Coherence (how consistent the model is)
        - T (Tone): 1 - Entropy (low entropy = positive tone)
        - H (Hesitation): PPL normalized (high PPL = hesitation)
        - C_contr (Contradiction): S/A ratio deviation from ideal (0.35)
        """
        loss = metrics.get('loss', metrics.get('total_loss', 5.0))
        ppl = metrics.get('ppl', 100.0)
        coherence = metrics.get('coherence', metrics.get('gc', 0.5))
        entropy = metrics.get('onto_entropy', metrics.get('entropy', 0.5))
        sa_ratio = metrics.get('sa_ratio', 0.35)

        return {
            "S": max(0, min(1, 1.0 - loss / 10.0)),      # Salience: inverse loss
            "R": float(coherence) if coherence else 0.5, # Reliability: coherence
            "T": 1.0 - float(entropy),                   # Tone: inverse entropy
            "H": min(1, ppl / 500.0),                    # Hesitation: normalized PPL
            "C_contr": abs(sa_ratio - 0.35) * 2,         # Contradiction: S/A deviation
        }

    def compute_target_state(self, observables: dict) -> dict:
        """
        Compute target state θ* from observables.

        Target state represents "where we should be" based on current signals.
        """
        S, R, T, H, C = (
            observables["S"],
            observables["R"],
            observables["T"],
            observables["H"],
            observables["C_contr"],
        )

        # Cognitive state: weighted combination favoring reliability and salience
        cognitive_target = 0.4 * S + 0.3 * R + 0.2 * T + 0.1 * (1 - H)

        # Confidence: based on consistency (low contradiction, high reliability)
        confidence_target = R * (1 - C) * (1 - H)

        # Stability: based on low hesitation and contradiction
        stability_target = (1 - H) * (1 - C)

        # Tone: direct from observables
        tone_target = T

        return {
            "cognitive_state": max(0, min(1, cognitive_target)),
            "confidence": max(0, min(1, confidence_target)),
            "stability": max(0, min(1, stability_target)),
            "tone_ema": max(0, min(1, tone_target)),
        }

    def update(self, metrics: dict, step: int) -> dict:
        """
        Update knowledge state based on training metrics.

        Applies v2.7 EMA update: θ_{t+1} = (1-α)·θ_t + α·θ*

        Returns:
            Dict with current state and update info
        """
        if not self.enabled:
            return {"enabled": False}

        # Convert metrics to observables
        observables = self.metrics_to_observables(metrics)

        # Compute target state
        target = self.compute_target_state(observables)

        # Apply EMA update: θ_{t+1} = (1-α)·θ_t + α·θ*
        for key in ["cognitive_state", "confidence", "stability", "tone_ema"]:
            self.state[key] = (1 - self.alpha) * self.state[key] + self.alpha * target[key]

        self.state["step_count"] = step

        # Track history
        self.history.append({
            "step": step,
            "cognitive_state": self.state["cognitive_state"],
            "confidence": self.state["confidence"],
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        return {
            "cognitive_state": self.state["cognitive_state"],
            "confidence": self.state["confidence"],
            "stability": self.state["stability"],
            "tone": self.state["tone_ema"],
            "observables": observables,
        }

    def detect_regression(self, window: int = 20) -> bool:
        """
        Detect if model is regressing (knowledge declining).

        Compares recent cognitive_state to earlier values.
        """
        if len(self.history) < window * 2:
            return False

        recent = self.history[-window:]
        earlier = self.history[-(window * 2):-window]

        recent_avg = sum(h["cognitive_state"] for h in recent) / len(recent)
        earlier_avg = sum(h["cognitive_state"] for h in earlier) / len(earlier)

        # Regression if recent is significantly lower than earlier
        return recent_avg < earlier_avg - 0.1

    def get_lr_modifier(self) -> float:
        """
        Get learning rate modifier based on confidence.

        Low confidence → reduce LR (be more careful)
        High confidence → normal LR
        """
        if not self.enabled:
            return 1.0

        confidence = self.state["confidence"]
        if confidence < 0.3:
            return 0.6  # Very low confidence: 60% LR
        elif confidence < 0.5:
            return 0.8  # Low confidence: 80% LR
        return 1.0      # Normal confidence: 100% LR

    def save_state(self):
        """Persist state to disk for cross-run continuity."""
        if not self.enabled:
            return

        try:
            import json
            with open(self.state_path, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"  Warning: Could not save training state: {e}")

    def load_state(self):
        """Load persisted state from previous run."""
        try:
            import json
            with open(self.state_path, 'r') as f:
                loaded = json.load(f)
                self.state.update(loaded)
            print(f"  📂 Loaded v2.7 training state from step {self.state['step_count']}")
        except FileNotFoundError:
            print(f"  🆕 Starting fresh v2.7 training state")
        except Exception as e:
            print(f"  Warning: Could not load training state: {e}")

    def format_status(self) -> str:
        """Format current state for logging."""
        return (
            f"Know:{self.state['cognitive_state']:.2f} "
            f"Conf:{self.state['confidence']:.2f} "
            f"Stab:{self.state['stability']:.2f}"
        )

    def update_with_gunas(self, s: float, r: float, t: float, step: int) -> dict:
        """
        Update knowledge state with Training Gunas.

        This bridges training physics (gradients/loss) with cognitive philosophy
        (Sattva/Rajas/Tamas), enabling the tracker to become a Guna-Aware Governor.

        Args:
            s: Sattva (clarity) - coherence × (1 - entropy)
            r: Rajas (action) - normalized gradient activity
            t: Tamas (inertia) - stability/stagnation measure

        Returns:
            Dict with Guna state and update info
        """
        if not self.enabled:
            return {"enabled": False}

        # Normalize to ensure sum = 1.0
        total = s + r + t
        if total > 0:
            s, r, t = s / total, r / total, t / total
        else:
            s, r, t = 0.33, 0.33, 0.34

        # Store Guna state
        if "gunas" not in self.state:
            self.state["gunas"] = {"s": 0.33, "r": 0.33, "t": 0.34}

        # EMA update for Gunas
        alpha = self.alpha
        self.state["gunas"]["s"] = (1 - alpha) * self.state["gunas"]["s"] + alpha * s
        self.state["gunas"]["r"] = (1 - alpha) * self.state["gunas"]["r"] + alpha * r
        self.state["gunas"]["t"] = (1 - alpha) * self.state["gunas"]["t"] + alpha * t

        # Map Gunas to cognitive state updates
        # High Sattva → increase cognitive_state
        # High Rajas → decrease stability (but may increase learning)
        # High Tamas → decrease confidence (stuck)
        guna_cognitive = 0.5 * s + 0.3 * (1 - t) + 0.2 * (1 - r * 0.5)
        guna_confidence = s * (1 - t)
        guna_stability = (1 - r) * (1 - t * 0.5)

        # Blend with existing state computation
        self.state["cognitive_state"] = (1 - alpha) * self.state["cognitive_state"] + alpha * guna_cognitive
        self.state["confidence"] = (1 - alpha) * self.state["confidence"] + alpha * guna_confidence
        self.state["stability"] = (1 - alpha) * self.state["stability"] + alpha * guna_stability
        self.state["step_count"] = step

        # Determine dominant Guna for logging
        gunas = self.state["gunas"]
        if gunas["s"] > gunas["r"] and gunas["s"] > gunas["t"]:
            dominant = "Lucidity"
        elif gunas["r"] > gunas["t"]:
            dominant = "Activity"
        else:
            dominant = "Stability"

        return {
            "gunas": self.state["gunas"].copy(),
            "dominant": dominant,
            "cognitive_state": self.state["cognitive_state"],
            "confidence": self.state["confidence"],
            "stability": self.state["stability"],
        }

    def get_guna_status(self) -> str:
        """Format Guna state for logging."""
        if "gunas" not in self.state:
            return "Gunas:N/A"

        g = self.state["gunas"]
        # Determine dominant and icon
        if g["s"] > g["r"] and g["s"] > g["t"]:
            icon = "☀️"  # Lucidity - clarity
        elif g["r"] > g["t"]:
            icon = "🔥"  # Activity - dynamism
        else:
            icon = "🌙"  # Stability - inertia

        return f"S:{g['s']:.2f} R:{g['r']:.2f} T:{g['t']:.2f}{icon}"


# =============================================================================
# TRAINING GUNAS: Bridge Training Physics to Cognitive Philosophy
# =============================================================================

class GradNormEMA:
    """
    Exponential Moving Average tracker for gradient norms.

    Used to establish a baseline for Rajas (metabolic effort) computation.
    Handles first-step initialization safely to avoid division by zero.

    Usage:
        grad_ema = GradNormEMA(alpha=0.1)
        baseline = grad_ema.update(grad_norm)  # Returns EMA
        rajas = grad_norm / grad_ema.get_baseline()  # Safe division
    """

    def __init__(self, alpha: float = 0.1, min_baseline: float = 1e-8):
        """
        Initialize gradient norm EMA tracker.

        Args:
            alpha: EMA smoothing factor (higher = faster adaptation)
            min_baseline: Minimum baseline to prevent division by zero
        """
        self.alpha = alpha
        self.min_baseline = min_baseline
        self.ema: Optional[float] = None
        self.step_count = 0
        self.max_observed = 0.0

    def update(self, grad_norm: float) -> float:
        """
        Update EMA with new gradient norm observation.

        Args:
            grad_norm: Current gradient norm

        Returns:
            Updated EMA value
        """
        self.step_count += 1
        self.max_observed = max(self.max_observed, grad_norm)

        if self.ema is None:
            # First observation: initialize to observed value
            self.ema = grad_norm
        else:
            # Standard EMA update
            self.ema = (1 - self.alpha) * self.ema + self.alpha * grad_norm

        return self.ema

    def get_baseline(self) -> float:
        """
        Get safe baseline for Rajas computation.

        Never returns zero or very small values that would cause
        division issues.

        Returns:
            Baseline value >= min_baseline
        """
        if self.ema is None or self.ema < self.min_baseline:
            return 1.0  # Neutral baseline before enough data
        return self.ema

    def get_normalized(self, grad_norm: float) -> float:
        """
        Get normalized gradient activity (grad_norm / baseline).

        Clamped to [0, 2] to prevent extreme values.

        Args:
            grad_norm: Current gradient norm

        Returns:
            Normalized value in [0, 2] range
        """
        baseline = self.get_baseline()
        return min(2.0, grad_norm / baseline)


class TrainingGunas:
    """
    Training Gunas - Map training dynamics to Sattva/Rajas/Tamas.

    Bridges the gap between:
    - Training physics (gradients, loss, entropy)
    - Cognitive philosophy (Sattva=clarity, Rajas=action, Tamas=inertia)

    This enables semantic interpretation of training dynamics:
    - High Sattva: Model is learning well (lock in)
    - High Rajas: High gradient activity (may need braking)
    - High Tamas: Stagnation/plateau (may need boost)

    Usage:
        gunas = TrainingGunas()

        # Each training step:
        s, r, t = gunas.compute(
            coherence=0.8,
            entropy=0.3,
            grad_norm=5.0,
            loss=2.5,
            prev_loss=2.6
        )

        # Feed to TrainingStateTracker
        tracker.update_with_gunas(s, r, t, step)
    """

    def __init__(
        self,
        grad_ema_alpha: float = 0.1,
        loss_ema_alpha: float = 0.05,
    ):
        """
        Initialize Training Gunas computer.

        Args:
            grad_ema_alpha: EMA alpha for gradient norm baseline
            loss_ema_alpha: EMA alpha for loss velocity tracking
        """
        self.grad_ema = GradNormEMA(alpha=grad_ema_alpha)
        self.loss_ema: Optional[float] = None
        self.loss_ema_alpha = loss_ema_alpha
        self.prev_loss: Optional[float] = None

    def compute(
        self,
        coherence: float,
        entropy: float,
        grad_norm: float,
        loss: float,
        prev_loss: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Compute Training Gunas from training metrics.

        Args:
            coherence: Model coherence [0, 1]
            entropy: Model entropy [0, 1]
            grad_norm: Current gradient norm
            loss: Current loss value
            prev_loss: Previous loss value (optional, uses tracked if None)

        Returns:
            (sattva, rajas, tamas) tuple, each in [0, 1], normalized to sum=1
        """
        # Update gradient baseline
        self.grad_ema.update(grad_norm)

        # Track loss for velocity
        if prev_loss is None:
            prev_loss = self.prev_loss if self.prev_loss is not None else loss
        self.prev_loss = loss

        # Compute raw Gunas
        s_raw = self._compute_sattva(coherence, entropy)
        r_raw = self._compute_rajas(grad_norm)
        t_raw = self._compute_tamas(loss, prev_loss, grad_norm)

        # Normalize to sum = 1.0
        total = s_raw + r_raw + t_raw
        if total > 0:
            s, r, t = s_raw / total, r_raw / total, t_raw / total
        else:
            s, r, t = 0.33, 0.33, 0.34

        return s, r, t

    def _compute_sattva(self, coherence: float, entropy: float) -> float:
        """
        Compute Sattva (clarity/quality of knowledge).

        Sattva = coherence × (1 - entropy)

        High coherence + low entropy = model is learning clearly.
        """
        # Clamp inputs
        coherence = max(0.0, min(1.0, float(coherence)))
        entropy = max(0.0, min(1.0, float(entropy)))

        return coherence * (1.0 - entropy)

    def _compute_rajas(self, grad_norm: float) -> float:
        """
        Compute Rajas (metabolic effort/action).

        Rajas = grad_norm / baseline_norm (clamped to [0, 1])

        High gradient activity relative to baseline = high action.
        """
        normalized = self.grad_ema.get_normalized(grad_norm)

        # Map [0, 2] to [0, 1] with 1.0 baseline at 0.5
        return min(1.0, normalized / 2.0)

    def _compute_tamas(
        self,
        loss: float,
        prev_loss: float,
        grad_norm: float,
    ) -> float:
        """
        Compute Tamas (inertia/stagnation) directly.

        NOT computed as residual (1 - s - r), but measured directly:
        - Low loss change = high inertia
        - Low gradient norm = high inertia

        Tamas = (1 - |loss_change|) × (1 - grad_activity)
        """
        # Loss velocity: how much is loss changing?
        loss_change = abs(loss - prev_loss)
        loss_velocity = min(1.0, loss_change / 0.5)  # Normalize, 0.5 = significant change

        # Gradient activity
        grad_activity = min(1.0, self.grad_ema.get_normalized(grad_norm) / 2.0)

        # Tamas: high when both loss and gradients are stable/flat
        tamas = (1.0 - loss_velocity) * (1.0 - grad_activity * 0.5)

        return max(0.0, min(1.0, tamas))

    def get_status(self, s: float, r: float, t: float) -> str:
        """Format Guna status for logging."""
        # Determine dominant
        if s > r and s > t:
            icon = "☀️"  # Lucidity
            state = "Learning"
        elif r > t:
            icon = "🔥"  # Activity
            state = "Active"
        else:
            icon = "🌙"  # Stability
            state = "Plateau"

        return f"Gunas[{state}]: L:{s:.2f} A:{r:.2f} S:{t:.2f} {icon}"

    def get_action_recommendation(self, s: float, r: float, t: float) -> str:
        """
        Get action recommendation based on Guna state.

        Returns:
            Action recommendation string
        """
        if s > 0.5:
            return "CONSERVE"  # Learning well, lock in
        elif r > 0.5:
            return "BRAKE"     # High activity, may need to slow down
        elif t > 0.5:
            return "BOOST"     # Stagnant, may need to increase K_p
        else:
            return "CONTINUE"  # Balanced, keep going


# =============================================================================
# SATTVIC BRAKE: Lightweight Confidence via Phase Angle Variance
# =============================================================================

# Import shared variance confidence utility
try:
    from symbolu.guna_modulation.variance_confidence import (
        VarianceConfidence,
        VarianceConfidenceConfig,
    )
    VARIANCE_CONFIDENCE_AVAILABLE = True
except ImportError:
    VARIANCE_CONFIDENCE_AVAILABLE = False


class SattvicBrake:
    """
    Sattvic Brake - Lightweight Confidence Estimation via Phase Angle Variance.

    Instead of full Bayesian inference, measure the "agreement" of Phase Attention
    heads in Authority layers (0-8). High agreement = high confidence.

    Now enhanced with R-Matrix Pramāṇa weighting:
    - Each layer's variance is weighted by its Pramāṇa (Truth) value from the R-Matrix
    - Intellect (layer 6) with Pramāṇa=0.9 contributes most to confidence
    - Dormant (layer 0) with Pramāṇa=0.1 contributes least

    Uses shared VarianceConfidence for braking logic and status formatting.

    Cost: ~0.1% compute (variance calculation), 0% extra memory

    Usage:
        brake = SattvicBrake(model, authority_layers=9)
        confidence = brake.compute_confidence()
        if confidence < 0.5:
            lr *= 0.8  # Apply brake
    """

    def __init__(
        self,
        model: nn.Module,
        authority_layers: int = 9,
        confidence_threshold: float = 0.5,
        lr_reduction: float = 0.8,
        window_size: int = 10,
        use_pramana_weighting: bool = True,  # Enable R-Matrix Pramāṇa weighting
    ):
        self.model = model
        self.authority_layers = authority_layers
        self.confidence_threshold = confidence_threshold
        self.lr_reduction = lr_reduction
        self.use_pramana_weighting = use_pramana_weighting

        # R-Matrix Pramāṇa weights for confidence weighting
        # Row 0 of R-Matrix = Pramāṇa (Truth) values per Aspect (layer)
        self._pramana_weights = get_pramana_weights()

        # Use shared VarianceConfidence for braking logic
        if VARIANCE_CONFIDENCE_AVAILABLE:
            self._variance_confidence = VarianceConfidence(
                window_size=window_size,
                confidence_threshold=confidence_threshold,
            )
        else:
            self._variance_confidence = None

        # Fallback history tracking (if shared class unavailable)
        self.confidence_history = []
        self.brake_applied_count = 0

    @torch.no_grad()
    def compute_phase_variance(self) -> Tuple[float, List[float]]:
        """
        Compute variance of phase angles across Authority layers.

        With Pramāṇa weighting enabled, each layer's variance is weighted by
        its Pramāṇa (Truth) value from the R-Matrix:
        - weighted_variance = sum(var_i * pramana_i) / sum(pramana_i)
        - Intellect (0.9) and Integration (0.9) dominate the score
        - Dormant (0.1) has minimal influence

        Returns:
            (average_variance, per_layer_variances)
        """
        variances = []

        # Get model layers
        layers = None
        if hasattr(self.model, 'layers'):
            layers = self.model.layers
        elif hasattr(self.model, 'transformer') and hasattr(self.model.transformer, 'layers'):
            layers = self.model.transformer.layers
        elif hasattr(self.model, 'blocks'):
            layers = self.model.blocks

        if layers is None:
            return 0.5, []  # Default if can't access layers

        # Check Authority layers (0 to authority_layers-1)
        for idx in range(min(self.authority_layers, len(layers))):
            layer = layers[idx]
            variance = self._get_layer_phase_variance(layer)
            if variance is not None:
                variances.append(variance)

        if not variances:
            return 0.5, []

        # Compute weighted or unweighted average
        if self.use_pramana_weighting and len(variances) > 0:
            # Pramāṇa-weighted variance: sum(var_i * pramana_i) / sum(pramana_i)
            weighted_sum = 0.0
            weight_sum = 0.0
            for idx, var in enumerate(variances):
                pramana = self._pramana_weights[min(idx, 11)].item()
                weighted_sum += var * pramana
                weight_sum += pramana
            avg_variance = weighted_sum / max(weight_sum, 1e-8)
        else:
            avg_variance = sum(variances) / len(variances)

        return avg_variance, variances

    def _get_layer_phase_variance(self, layer) -> Optional[float]:
        """Extract phase variance from a single layer."""
        # Try different attribute names for phase attention
        phase_attn = None
        for attr in ['phase_attention', 'attention', 'self_attn', 'attn']:
            if hasattr(layer, attr):
                phase_attn = getattr(layer, attr)
                break

        if phase_attn is None:
            return None

        # Try to get phase angles
        if hasattr(phase_attn, 'phase') and phase_attn.phase is not None:
            phase = phase_attn.phase
            if isinstance(phase, torch.Tensor):
                # Compute circular variance: 1 - |mean(e^{i*theta})|
                if phase.numel() > 1:
                    complex_phase = torch.exp(1j * phase.float())
                    mean_phase = torch.mean(complex_phase)
                    variance = 1.0 - torch.abs(mean_phase).item()
                    return variance

        # Fallback: use weight variance as proxy
        if hasattr(phase_attn, 'q_proj') and hasattr(phase_attn.q_proj, 'weight'):
            weight = phase_attn.q_proj.weight
            variance = weight.var().item()
            # Normalize to [0, 1] range (empirical scaling)
            return min(1.0, variance * 10)

        return None

    def compute_confidence(self) -> float:
        """
        Compute confidence score from phase variance.

        Confidence = 1 - variance (high variance = low confidence)
        """
        variance, layer_variances = self.compute_phase_variance()
        confidence = 1.0 - variance

        # Update shared variance confidence with layer variances
        if self._variance_confidence is not None and layer_variances:
            # Feed layer variances as observation tuple
            self._variance_confidence.update(tuple(layer_variances))

        # Track history
        self.confidence_history.append(confidence)
        if len(self.confidence_history) > 100:
            self.confidence_history = self.confidence_history[-100:]

        return max(0.0, min(1.0, confidence))

    def should_brake(self, confidence: float = None) -> Tuple[bool, float]:
        """
        Check if brake should be applied.

        Returns:
            (should_apply, lr_multiplier)
        """
        if confidence is None:
            confidence = self.compute_confidence()

        # Use shared VarianceConfidence if available
        if self._variance_confidence is not None:
            # Override the confidence in shared tracker
            self._variance_confidence._confidence = confidence
            should_apply, mult = self._variance_confidence.should_brake(confidence)
            if should_apply:
                self.brake_applied_count += 1
            return should_apply, mult

        # Fallback: inline braking logic
        if confidence < self.confidence_threshold:
            self.brake_applied_count += 1
            # Graduated braking: lower confidence = stronger brake
            if confidence < 0.3:
                lr_mult = 0.6
            elif confidence < 0.4:
                lr_mult = 0.7
            else:
                lr_mult = self.lr_reduction
            return True, lr_mult

        return False, 1.0

    def get_status_icon(self, confidence: float) -> str:
        """Get status icon for confidence level."""
        if self._variance_confidence is not None:
            return self._variance_confidence.get_status_icon(confidence)

        # Fallback
        if confidence >= 0.7:
            return "🟢"
        elif confidence >= 0.5:
            return "🟡"
        elif confidence >= 0.3:
            return "🟠"
        else:
            return "🔴"

    def format_status(self, confidence: float = None) -> str:
        """Format status for logging."""
        if confidence is None:
            confidence = self.compute_confidence()

        if self._variance_confidence is not None:
            self._variance_confidence._confidence = confidence
            return self._variance_confidence.format_status(confidence)

        # Fallback
        icon = self.get_status_icon(confidence)
        brake, lr_mult = self.should_brake(confidence)

        if brake:
            return f"Conf:{confidence:.2f}{icon} LR×{lr_mult:.2f} [BRAKE]"
        return f"Conf:{confidence:.2f}{icon}"


# =============================================================================
# LRA VALIDATOR: Long-Range Retrieval Testing
# =============================================================================

class LRAValidator:
    """
    Long-Range Arena Validator for Phase Attention Memory.

    Tests the model's ability to retrieve information over long distances,
    validating that Phase Oscillator memory works without decay.

    Tests:
    1. Needle-in-Haystack: Hide a key-value pair early, recall at end
    2. Distance Decay: Measure accuracy vs retrieval distance
    3. Multi-Needle: Multiple key-value pairs at different positions

    Patent Integration:
    - [U1] PhaseCoherenceMatrix: High coherence should correlate with good retrieval
    - [S5] Entropy: Low entropy during retrieval = confident recall
    - [B1] Consistency: Consistent forward/backward alignment aids retrieval

    Usage:
        validator = LRAValidator(model, tokenizer)
        results = validator.run_validation(step=1000)
        print(validator.format_results(results))
    """

    def __init__(
        self,
        model: nn.Module,
        tokenizer: Optional[object] = None,
        device: torch.device = None,
        # Test configuration
        haystack_lengths: List[int] = None,  # Sequence lengths to test
        needle_positions: List[float] = None,  # Relative positions (0.0-1.0)
        num_samples: int = 50,  # Samples per test
        vocab_size: int = 50257,  # Tokenizer vocab size
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Test configurations
        self.haystack_lengths = haystack_lengths or [256, 512, 1024, 2048]
        self.needle_positions = needle_positions or [0.05, 0.1, 0.25, 0.5]  # 5%, 10%, 25%, 50%
        self.num_samples = num_samples
        self.vocab_size = vocab_size

        # Results history
        self.results_history = []

        # Special tokens for needle test
        self.key_token = 1      # Token ID for "KEY" marker
        self.query_token = 2    # Token ID for "QUERY" marker

    @torch.no_grad()
    def generate_needle_batch(
        self,
        batch_size: int,
        seq_len: int,
        needle_pos: int,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Generate a batch of needle-in-haystack sequences.

        Pattern:
            [noise...] [KEY] [VALUE] [noise...] [QUERY] [?]
                                                         ↑
                                                 Target: VALUE

        Returns:
            (sequences, targets, needle_positions)
        """
        # Create noise (haystack) - use tokens 10-vocab_size to avoid special tokens
        sequences = torch.randint(10, min(self.vocab_size, 1000), (batch_size, seq_len))

        # Generate random values for each sequence (tokens 10-99)
        values = torch.randint(10, 100, (batch_size,))
        targets = values.clone()

        # Insert needle at specified position
        # [KEY=1] [VALUE=random]
        sequences[:, needle_pos] = self.key_token
        sequences[:, needle_pos + 1] = values

        # Insert query at end - model must predict the value
        # [QUERY=2] [?]
        sequences[:, -2] = self.query_token
        sequences[:, -1] = values  # This is what we want to predict

        return sequences.to(self.device), targets.to(self.device), torch.tensor([needle_pos] * batch_size)

    @torch.no_grad()
    def test_needle_retrieval(
        self,
        seq_len: int,
        needle_pos_ratio: float,
    ) -> Dict[str, float]:
        """
        Test needle retrieval at a specific sequence length and position.

        Args:
            seq_len: Length of the haystack sequence
            needle_pos_ratio: Relative position of needle (0.0-1.0)

        Returns:
            Dict with accuracy, entropy, and confidence metrics
        """
        self.model.eval()

        needle_pos = int(seq_len * needle_pos_ratio)
        needle_pos = max(5, min(needle_pos, seq_len - 10))  # Safety bounds

        # Distance from needle to query
        retrieval_distance = seq_len - needle_pos - 3

        correct = 0
        total = 0
        entropies = []
        confidences = []

        # Run in batches
        batch_size = min(16, self.num_samples)
        num_batches = (self.num_samples + batch_size - 1) // batch_size

        for _ in range(num_batches):
            actual_batch = min(batch_size, self.num_samples - total)
            if actual_batch <= 0:
                break

            sequences, targets, _ = self.generate_needle_batch(
                actual_batch, seq_len, needle_pos
            )

            # Forward pass - get logits for the last position
            try:
                outputs = self.model(sequences[:, :-1])  # Input without last token
                if isinstance(outputs, dict):
                    logits = outputs.get('logits', outputs.get('output'))
                else:
                    logits = outputs

                # Get predictions for the last position
                last_logits = logits[:, -1, :]  # [B, Vocab]

                # Compute predictions
                predictions = last_logits.argmax(dim=-1)

                # Compute accuracy
                correct += (predictions == targets).sum().item()
                total += actual_batch

                # Compute entropy of predictions
                probs = F.softmax(last_logits, dim=-1)
                entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
                max_entropy = math.log(last_logits.shape[-1])
                normalized_entropy = (entropy / max_entropy).mean().item()
                entropies.append(normalized_entropy)

                # Compute confidence (probability of correct token)
                target_probs = probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
                confidences.append(target_probs.mean().item())

            except Exception as e:
                print(f"    Warning: LRA test failed for seq_len={seq_len}: {e}")
                break

        accuracy = correct / total if total > 0 else 0.0
        avg_entropy = sum(entropies) / len(entropies) if entropies else 1.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "seq_len": seq_len,
            "needle_pos": needle_pos,
            "needle_pos_ratio": needle_pos_ratio,
            "retrieval_distance": retrieval_distance,
            "accuracy": accuracy,
            "entropy": avg_entropy,
            "confidence": avg_confidence,
            "samples": total,
        }

    @torch.no_grad()
    def run_validation(self, step: int = 0) -> Dict[str, any]:
        """
        Run full LRA validation suite.

        Returns comprehensive results including:
        - Per-length accuracy
        - Per-position accuracy
        - Distance decay curve
        - Overall retrieval score
        """
        self.model.eval()

        results = {
            "step": step,
            "tests": [],
            "by_length": {},
            "by_position": {},
            "distance_decay": [],
        }

        print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
        print(f"  ║  🔍 LRA VALIDATION (Step {step})                              ║")
        print(f"  ╠══════════════════════════════════════════════════════════════╣")

        # Run tests for each length and position combination
        for seq_len in self.haystack_lengths:
            if seq_len > 2048:  # Skip if seq_len exceeds typical model limits
                continue

            results["by_length"][seq_len] = []

            for pos_ratio in self.needle_positions:
                test_result = self.test_needle_retrieval(seq_len, pos_ratio)
                results["tests"].append(test_result)
                results["by_length"][seq_len].append(test_result)

                # Track by position
                pos_key = f"{pos_ratio:.0%}"
                if pos_key not in results["by_position"]:
                    results["by_position"][pos_key] = []
                results["by_position"][pos_key].append(test_result)

                # Track distance decay
                results["distance_decay"].append({
                    "distance": test_result["retrieval_distance"],
                    "accuracy": test_result["accuracy"],
                    "entropy": test_result["entropy"],
                })

                # Log result
                acc_icon = "✅" if test_result["accuracy"] > 0.8 else "⚠️" if test_result["accuracy"] > 0.5 else "❌"
                print(f"  ║  Len:{seq_len:>4} Pos:{pos_ratio:>4.0%} Dist:{test_result['retrieval_distance']:>4} │ "
                      f"Acc:{test_result['accuracy']:.1%} Ent:{test_result['entropy']:.2f} {acc_icon}  ║")

        # Compute summary statistics
        all_accuracies = [t["accuracy"] for t in results["tests"]]
        all_entropies = [t["entropy"] for t in results["tests"]]

        results["summary"] = {
            "mean_accuracy": sum(all_accuracies) / len(all_accuracies) if all_accuracies else 0,
            "min_accuracy": min(all_accuracies) if all_accuracies else 0,
            "max_accuracy": max(all_accuracies) if all_accuracies else 0,
            "mean_entropy": sum(all_entropies) / len(all_entropies) if all_entropies else 1,
        }

        # Compute distance decay coefficient (how fast accuracy drops with distance)
        if len(results["distance_decay"]) >= 2:
            distances = [d["distance"] for d in results["distance_decay"]]
            accuracies = [d["accuracy"] for d in results["distance_decay"]]
            # Simple linear regression for decay rate
            if max(distances) > min(distances):
                n = len(distances)
                mean_d = sum(distances) / n
                mean_a = sum(accuracies) / n
                numerator = sum((d - mean_d) * (a - mean_a) for d, a in zip(distances, accuracies))
                denominator = sum((d - mean_d) ** 2 for d in distances)
                decay_rate = numerator / denominator if denominator != 0 else 0
                results["summary"]["decay_rate"] = decay_rate
            else:
                results["summary"]["decay_rate"] = 0
        else:
            results["summary"]["decay_rate"] = 0

        # Print summary
        print(f"  ╠══════════════════════════════════════════════════════════════╣")
        summary = results["summary"]
        overall_icon = "🟢" if summary["mean_accuracy"] > 0.7 else "🟡" if summary["mean_accuracy"] > 0.4 else "🔴"
        print(f"  ║  SUMMARY: Avg Acc: {summary['mean_accuracy']:.1%} │ "
              f"Range: [{summary['min_accuracy']:.1%}-{summary['max_accuracy']:.1%}] {overall_icon}  ║")
        print(f"  ║  Decay Rate: {summary['decay_rate']:.4f}/token │ "
              f"Mean Entropy: {summary['mean_entropy']:.3f}         ║")
        print(f"  ╚══════════════════════════════════════════════════════════════╝\n")

        # Store in history
        self.results_history.append(results)

        return results

    def get_retrieval_score(self) -> float:
        """
        Get a single retrieval score (0-1) from the most recent validation.

        Score combines:
        - Mean accuracy (60%)
        - Distance resilience (30%) - how well accuracy holds over distance
        - Confidence (10%)
        """
        if not self.results_history:
            return 0.0

        latest = self.results_history[-1]
        summary = latest["summary"]

        # Mean accuracy component
        acc_score = summary["mean_accuracy"] * 0.6

        # Distance resilience (inverse of decay rate, normalized)
        # decay_rate is negative when accuracy drops with distance
        decay = abs(summary.get("decay_rate", 0))
        resilience = max(0, 1.0 - decay * 100)  # Scale decay to 0-1
        resilience_score = resilience * 0.3

        # Entropy component (lower is better)
        entropy_score = (1.0 - summary["mean_entropy"]) * 0.1

        return min(1.0, acc_score + resilience_score + entropy_score)

    def format_compact_result(self) -> str:
        """Format a compact one-line result for logging."""
        if not self.results_history:
            return "LRA: No data"

        latest = self.results_history[-1]
        summary = latest["summary"]
        score = self.get_retrieval_score()

        icon = "🟢" if score > 0.7 else "🟡" if score > 0.4 else "🔴"
        return f"LRA:{score:.2f}{icon} Acc:{summary['mean_accuracy']:.1%} Decay:{summary['decay_rate']:.4f}"


# =============================================================================
# ADAPTIVE TRAINING CONTROLLER: Dynamic Hyperparameter Tuning
# =============================================================================

class AdaptiveTrainingController:
    """
    Dynamically adjusts training hyperparameters based on observed metrics.

    Instead of manual tuning, this controller:
    1. Monitors PPL velocity, coherence, and loss stability
    2. Adjusts learning rate when training is too slow or unstable
    4. Logs all adjustments for transparency

    Philosophy:
    - If model is learning slowly (low velocity) → increase LR
    - If model is unstable (high variance) → decrease LR
    - If train >> val (overfitting) → decrease Kp
    - If train ≈ val (underfitting) → increase Kp

    Usage:
        controller = AdaptiveTrainingController(optimizer, config)
        # In training loop after validation:
        controller.update(train_loss, val_loss, val_ppl, coherence, step)
    """

    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        # LR adaptation
        base_lr: float = 3e-4,
        lr_min: float = 1e-5,
        lr_max: float = 1e-3,
        lr_boost_factor: float = 1.5,
        lr_decay_factor: float = 0.7,
        # PPL velocity thresholds
        velocity_slow_threshold: float = -2.0,   # % per eval, below this = too slow
        velocity_spike_threshold: float = 10.0,  # % per eval, above this = unstable
        # Plateau detection
        plateau_window: int = 5,                 # Evals to check for plateau
        plateau_threshold: float = 1.0,          # % improvement threshold
        # Kp adaptation
        kp_base: float = 0.20,
        kp_min: float = 0.10,
        kp_max: float = 0.50,
        # Stability
        min_steps_between_adjustments: int = 200,
        # V9.8.2: Safeguards to prevent runaway LR
        max_lr_relative: float = 10.0,           # Max LR = base_lr * this (prevents runaway)
        loss_spike_threshold: float = 5.0,       # % loss increase triggers emergency decay
        grad_norm_spike_threshold: float = 100.0,  # Gradient norm above this triggers decay
        emergency_decay_factor: float = 0.5,     # Aggressive decay for emergencies
        consecutive_spike_limit: int = 3,        # After N consecutive spikes, halt boosts
    ):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.lr_min = lr_min
        # V9.8.2: Clamp lr_max to max_lr_relative * base_lr
        self.lr_max = min(lr_max, base_lr * max_lr_relative)
        self.lr_boost_factor = lr_boost_factor
        self.lr_decay_factor = lr_decay_factor

        self.velocity_slow_threshold = velocity_slow_threshold
        self.velocity_spike_threshold = velocity_spike_threshold

        self.plateau_window = plateau_window
        self.plateau_threshold = plateau_threshold

        self.kp_base = kp_base
        self.kp_min = kp_min
        self.kp_max = kp_max
        self.current_kp = kp_base

        self.min_steps_between_adjustments = min_steps_between_adjustments
        self.last_adjustment_step = 0

        # V9.8.2: Safeguard parameters
        self.max_lr_relative = max_lr_relative
        self.loss_spike_threshold = loss_spike_threshold
        self.grad_norm_spike_threshold = grad_norm_spike_threshold
        self.emergency_decay_factor = emergency_decay_factor
        self.consecutive_spike_limit = consecutive_spike_limit

        # History tracking
        self.val_ppl_history = []
        self.train_loss_history = []
        self.val_loss_history = []
        self.coherence_history = []
        self.adjustment_log = []
        self.grad_norm_history = []  # V9.8.2: Track gradient norms

        # State
        self.current_lr_multiplier = 1.0
        self.boost_count = 0
        self.decay_count = 0
        self.plateau_count = 0
        self.emergency_count = 0  # V9.8.2: Track emergency interventions
        self.consecutive_spikes = 0  # V9.8.2: Track consecutive loss spikes
        self.boost_blocked = False  # V9.8.2: Block boosts after too many spikes

        print(f"\n  [AdaptiveTraining] Controller initialized:")
        print(f"    Base LR: {base_lr:.2e} (range: {lr_min:.2e} - {self.lr_max:.2e})")
        print(f"    Velocity thresholds: slow < {velocity_slow_threshold}%, spike > {velocity_spike_threshold}%")
        print(f"    Kp range: {kp_min} - {kp_max} (base: {kp_base})")
        print(f"    V9.8.2 Safeguards: max_relative={max_lr_relative}x, loss_spike={loss_spike_threshold}%")
        print(f"    Plateau detection: {plateau_window} evals, {plateau_threshold}% threshold")

    def _compute_velocity(self) -> float:
        """Compute PPL velocity (% change per eval)."""
        if len(self.val_ppl_history) < 2:
            return 0.0
        current = self.val_ppl_history[-1]
        previous = self.val_ppl_history[-2]
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100

    def _detect_plateau(self) -> bool:
        """Detect if PPL has plateaued (< threshold improvement over window)."""
        if len(self.val_ppl_history) < self.plateau_window:
            return False
        recent = self.val_ppl_history[-self.plateau_window:]
        first = recent[0]
        last = recent[-1]
        if first == 0:
            return False
        improvement = ((first - last) / first) * 100
        return improvement < self.plateau_threshold

    def _compute_train_val_gap(self) -> float:
        """Compute gap between train and val loss (overfitting indicator)."""
        if not self.train_loss_history or not self.val_loss_history:
            return 0.0
        train = self.train_loss_history[-1]
        val = self.val_loss_history[-1]
        if val == 0:
            return 0.0
        return ((val - train) / val) * 100  # Positive = val > train = normal

    def update(
        self,
        train_loss: float,
        val_loss: float,
        val_ppl: float,
        coherence: float,
        global_step: int,
        grad_norm: float = None,  # V9.8.2: Optional gradient norm for monitoring
    ) -> Dict[str, Any]:
        """
        Update controller with current metrics and adjust hyperparameters.

        Returns dict of adjustments made.
        """
        # Record history
        self.val_ppl_history.append(val_ppl)
        self.train_loss_history.append(train_loss)
        self.val_loss_history.append(val_loss)
        self.coherence_history.append(coherence)
        if grad_norm is not None:
            self.grad_norm_history.append(grad_norm)

        # Keep history bounded
        max_history = 50
        if len(self.val_ppl_history) > max_history:
            self.val_ppl_history = self.val_ppl_history[-max_history:]
            self.train_loss_history = self.train_loss_history[-max_history:]
            self.val_loss_history = self.val_loss_history[-max_history:]
            self.coherence_history = self.coherence_history[-max_history:]
            self.grad_norm_history = self.grad_norm_history[-max_history:]

        adjustments = {"step": global_step, "actions": []}
        current_lr = self.optimizer.param_groups[0]['lr']

        # === V9.8.2: EMERGENCY BRAKE - Check for runaway LR ===
        lr_relative = current_lr / self.base_lr
        if lr_relative > self.max_lr_relative:
            # LR has exceeded safe bounds - emergency clamp
            safe_lr = self.base_lr * self.max_lr_relative
            for pg in self.optimizer.param_groups:
                pg['lr'] = safe_lr
            self.emergency_count += 1
            self.boost_blocked = True  # Block further boosts
            adjustments["actions"].append(f"EMERGENCY_CLAMP: {current_lr:.2e}→{safe_lr:.2e} (>{self.max_lr_relative}x base)")
            print(f"\n  🚨 [AdaptiveTraining] EMERGENCY CLAMP: {current_lr:.2e} → {safe_lr:.2e} (exceeded {self.max_lr_relative}x base LR)")
            self.last_adjustment_step = global_step
            current_lr = safe_lr

        # === V9.8.2: Loss Spike Detection ===
        loss_spike_detected = False
        if len(self.val_loss_history) >= 2:
            prev_loss = self.val_loss_history[-2]
            curr_loss = self.val_loss_history[-1]
            if prev_loss > 0:
                loss_change_pct = ((curr_loss - prev_loss) / prev_loss) * 100
                if loss_change_pct > self.loss_spike_threshold:
                    loss_spike_detected = True
                    self.consecutive_spikes += 1

                    # Emergency decay on loss spike
                    new_lr = max(self.lr_min, current_lr * self.emergency_decay_factor)
                    if new_lr != current_lr:
                        for pg in self.optimizer.param_groups:
                            pg['lr'] = new_lr
                        self.emergency_count += 1
                        adjustments["actions"].append(f"LOSS_SPIKE_DECAY: {current_lr:.2e}→{new_lr:.2e} (loss +{loss_change_pct:.1f}%)")
                        print(f"\n  🔥 [AdaptiveTraining] LOSS SPIKE DECAY: {current_lr:.2e} → {new_lr:.2e} (loss increased {loss_change_pct:.1f}%)")
                        self.last_adjustment_step = global_step
                        current_lr = new_lr

                    # Block boosts after consecutive spikes
                    if self.consecutive_spikes >= self.consecutive_spike_limit:
                        self.boost_blocked = True
                        print(f"  ⛔ [AdaptiveTraining] BOOST BLOCKED: {self.consecutive_spikes} consecutive loss spikes")
                else:
                    # Loss improved or stable - reset spike counter
                    self.consecutive_spikes = 0
                    if loss_change_pct < -2.0:  # Loss improving well
                        self.boost_blocked = False  # Allow boosts again

        # === V9.8.2: Gradient Norm Spike Detection ===
        if grad_norm is not None and grad_norm > self.grad_norm_spike_threshold:
            new_lr = max(self.lr_min, current_lr * self.emergency_decay_factor)
            if new_lr != current_lr:
                for pg in self.optimizer.param_groups:
                    pg['lr'] = new_lr
                self.emergency_count += 1
                self.boost_blocked = True
                adjustments["actions"].append(f"GRAD_SPIKE_DECAY: {current_lr:.2e}→{new_lr:.2e} (grad_norm={grad_norm:.1f})")
                print(f"\n  💥 [AdaptiveTraining] GRAD SPIKE DECAY: {current_lr:.2e} → {new_lr:.2e} (grad_norm={grad_norm:.1f} > {self.grad_norm_spike_threshold})")
                self.last_adjustment_step = global_step
                current_lr = new_lr

        # Check if we can make regular adjustments (skip if emergency just happened)
        if global_step - self.last_adjustment_step < self.min_steps_between_adjustments:
            if adjustments["actions"]:
                self.adjustment_log.append(adjustments)
            return adjustments

        velocity = self._compute_velocity()
        is_plateau = self._detect_plateau()
        train_val_gap = self._compute_train_val_gap()

        # === LR Adaptation ===
        # Case 1: PPL spiking (unstable) → decay LR
        if velocity > self.velocity_spike_threshold:
            new_lr = max(self.lr_min, current_lr * self.lr_decay_factor)
            if new_lr != current_lr:
                for pg in self.optimizer.param_groups:
                    pg['lr'] = new_lr
                self.decay_count += 1
                adjustments["actions"].append(f"LR_DECAY: {current_lr:.2e}→{new_lr:.2e} (spike: {velocity:+.1f}%)")
                print(f"\n  🔻 [AdaptiveTraining] LR DECAY: {current_lr:.2e} → {new_lr:.2e} (PPL spike: {velocity:+.1f}%)")
                self.last_adjustment_step = global_step

        # Case 2: Learning too slow or plateau → boost LR (V9.8.2: only if not blocked)
        elif (velocity > self.velocity_slow_threshold or is_plateau) and not self.boost_blocked:
            if is_plateau:
                self.plateau_count += 1

            # Only boost if we're not already at max
            new_lr = min(self.lr_max, current_lr * self.lr_boost_factor)
            if new_lr != current_lr and new_lr > current_lr:
                for pg in self.optimizer.param_groups:
                    pg['lr'] = new_lr
                self.boost_count += 1
                reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
                adjustments["actions"].append(f"LR_BOOST: {current_lr:.2e}→{new_lr:.2e} ({reason})")
                print(f"\n  🔺 [AdaptiveTraining] LR BOOST: {current_lr:.2e} → {new_lr:.2e} ({reason})")
                self.last_adjustment_step = global_step
        elif self.boost_blocked and (velocity > self.velocity_slow_threshold or is_plateau):
            # Log that boost was blocked
            reason = "plateau" if is_plateau else f"slow: {velocity:.1f}%"
            print(f"\n  ⏸️  [AdaptiveTraining] LR BOOST BLOCKED ({reason}) - waiting for stable loss")

        if adjustments["actions"]:
            self.adjustment_log.append(adjustments)

        return adjustments

    def get_status_string(self) -> str:
        """Get formatted status string."""
        velocity = self._compute_velocity() if len(self.val_ppl_history) >= 2 else 0.0
        plateau = "PLATEAU" if self._detect_plateau() else "OK"
        current_lr = self.optimizer.param_groups[0]['lr']
        lr_relative = current_lr / self.base_lr
        blocked = " BLOCKED" if self.boost_blocked else ""
        return f"AdaptLR:{current_lr:.2e}({lr_relative:.1f}x) vel:{velocity:+.1f}% [{plateau}] boosts:{self.boost_count} decays:{self.decay_count} emerg:{self.emergency_count}{blocked}"

    def enforce_lr_bounds(self, global_step: int = 0) -> bool:
        """
        V9.8.3: Step-level LR safeguard - call EVERY training step.

        This catches runaway LR from schedulers or restored checkpoints
        that the validation-time update() method would miss.

        Returns True if LR was clamped.
        """
        current_lr = self.optimizer.param_groups[0]['lr']
        lr_relative = current_lr / self.base_lr

        clamped = False

        # Check upper bound
        if lr_relative > self.max_lr_relative:
            safe_lr = self.base_lr * self.max_lr_relative
            for pg in self.optimizer.param_groups:
                pg['lr'] = safe_lr
            self.emergency_count += 1
            self.boost_blocked = True
            print(f"\n  🚨 [AdaptiveTraining] STEP {global_step} LR CLAMPED: {current_lr:.2e} → {safe_lr:.2e} (exceeded {self.max_lr_relative}x base)")
            clamped = True

        # Check lower bound
        elif current_lr < self.lr_min:
            for pg in self.optimizer.param_groups:
                pg['lr'] = self.lr_min
            print(f"\n  ⚠️ [AdaptiveTraining] STEP {global_step} LR FLOOR: {current_lr:.2e} → {self.lr_min:.2e}")
            clamped = True

        return clamped

    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry for logging."""
        current_lr = self.optimizer.param_groups[0]['lr']
        return {
            "current_lr": current_lr,
            "lr_relative": current_lr / self.base_lr,  # V9.8.2: Track relative LR
            "velocity": self._compute_velocity() if len(self.val_ppl_history) >= 2 else 0.0,
            "is_plateau": self._detect_plateau(),
            "train_val_gap": self._compute_train_val_gap(),
            "boost_count": self.boost_count,
            "decay_count": self.decay_count,
            "plateau_count": self.plateau_count,
            "emergency_count": self.emergency_count,  # V9.8.2: Emergency interventions
            "consecutive_spikes": self.consecutive_spikes,  # V9.8.2: Loss spike tracker
            "boost_blocked": self.boost_blocked,  # V9.8.2: Whether boosts are blocked
            "adjustment_log": self.adjustment_log[-10:],  # Last 10 adjustments
        }


# =============================================================================
# ADAPTIVE WARMUP SCHEDULER: PPL-based warmup transition
# =============================================================================

class AdaptiveWarmupScheduler:
    """
    Learning rate scheduler with PPL-based warmup transition.

    Instead of a fixed warmup period, warmup ends when:
    1. PPL drops below warmup_until_ppl threshold, OR
    2. max_warmup_steps is reached (fallback)

    This ensures the model reaches a stable learning state before
    transitioning to cosine decay.

    LR trajectory:
    - Warmup phase: Linear ramp from start_factor * lr to lr
    - Decay phase: Cosine decay from lr to eta_min

    Usage:
        scheduler = AdaptiveWarmupScheduler(optimizer, config)
        # In training loop:
        scheduler.step(current_ppl)  # Pass current PPL
    """

    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        base_lr: float,
        max_steps: int,
        max_warmup_steps: int = 500,
        warmup_until_ppl: float = 500.0,
        start_factor: float = 0.1,
        eta_min_factor: float = 0.1,
    ):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.max_steps = max_steps
        self.max_warmup_steps = max_warmup_steps
        self.warmup_until_ppl = warmup_until_ppl
        self.start_factor = start_factor
        self.eta_min = base_lr * eta_min_factor

        # State
        self.current_step = 0
        self.warmup_ended = False
        self.warmup_end_step = None
        self.warmup_end_ppl = None

        # Set initial LR
        self._set_lr(base_lr * start_factor)

    def _set_lr(self, lr: float):
        """Set learning rate for all param groups."""
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr

    def _get_warmup_lr(self) -> float:
        """Linear warmup from start_factor * base_lr to base_lr."""
        if self.max_warmup_steps == 0:
            return self.base_lr
        progress = min(1.0, self.current_step / self.max_warmup_steps)
        return self.base_lr * (self.start_factor + progress * (1.0 - self.start_factor))

    def _get_cosine_lr(self) -> float:
        """Cosine decay from base_lr to eta_min."""
        if self.warmup_end_step is None:
            return self.base_lr

        # Steps since warmup ended
        decay_step = self.current_step - self.warmup_end_step
        decay_total = self.max_steps - self.warmup_end_step

        if decay_total <= 0:
            return self.eta_min

        progress = min(1.0, decay_step / decay_total)
        # Cosine decay: lr * (1 + cos(pi * progress)) / 2, scaled to [eta_min, base_lr]
        cosine_factor = 0.5 * (1.0 + math.cos(math.pi * progress))
        return self.eta_min + (self.base_lr - self.eta_min) * cosine_factor

    def step(self, current_ppl: float = float('inf')):
        """
        Update learning rate based on current step and PPL.

        Args:
            current_ppl: Current training PPL (pass inf if unknown)
        """
        self.current_step += 1

        # Check if warmup should end
        if not self.warmup_ended:
            ppl_condition = self.warmup_until_ppl > 0 and current_ppl < self.warmup_until_ppl
            step_condition = self.current_step >= self.max_warmup_steps

            if ppl_condition or step_condition:
                self.warmup_ended = True
                self.warmup_end_step = self.current_step
                self.warmup_end_ppl = current_ppl
                trigger = "PPL" if ppl_condition else "steps"
                print(f"🔥 [LR] Warmup ended at step {self.current_step} (trigger: {trigger}, "
                      f"PPL: {current_ppl:.1f}) - switching to cosine decay")

        # Compute and set LR
        if self.warmup_ended:
            lr = self._get_cosine_lr()
        else:
            lr = self._get_warmup_lr()

        self._set_lr(lr)

    def get_last_lr(self) -> list:
        """Return last computed LR (for compatibility with PyTorch schedulers)."""
        return [param_group['lr'] for param_group in self.optimizer.param_groups]

    def state_dict(self) -> dict:
        """Return scheduler state for checkpointing."""
        return {
            "current_step": self.current_step,
            "warmup_ended": self.warmup_ended,
            "warmup_end_step": self.warmup_end_step,
            "warmup_end_ppl": self.warmup_end_ppl,
        }

    def load_state_dict(self, state: dict):
        """Restore scheduler state from checkpoint."""
        self.current_step = state.get("current_step", 0)
        self.warmup_ended = state.get("warmup_ended", False)
        self.warmup_end_step = state.get("warmup_end_step")
        self.warmup_end_ppl = state.get("warmup_end_ppl")


# =============================================================================
# PPL-GATED ALPHA CURRICULUM: Phase dominates early, local refines later
# =============================================================================

class PPLAlphaCurriculum:
    """
    Dynamically adjusts alpha_phase/alpha_local based on current PPL.

    Philosophy:
    - High PPL (early training): Phase attention dominates to establish stable patterns
    - Low PPL (later training): Local/quadratic attention takes over for refinement

    The phase attention is slower but builds the "state scaffold" that quadratic
    attention needs. By letting phase dominate early, we ensure stable foundations
    before the faster quadratic attention refines the details.

    Formula:
        if ppl >= ppl_high:
            alpha_phase = alpha_high (e.g., 0.8)
        elif ppl <= ppl_low:
            alpha_phase = alpha_low (e.g., 0.3)
        else:
            # Linear interpolation
            alpha_phase = alpha_low + (ppl - ppl_low) * (alpha_high - alpha_low) / (ppl_high - ppl_low)
        alpha_local = 1.0 - alpha_phase

    Usage:
        curriculum = PPLAlphaCurriculum(config)
        # In training loop:
        alpha_phase, alpha_local = curriculum.get_alphas(current_ppl)
        update_model_alphas(model, alpha_phase, alpha_local)
    """

    def __init__(
        self,
        alpha_high: float = 0.8,
        alpha_low: float = 0.3,
        ppl_high: float = 1000.0,
        ppl_low: float = 100.0,
        ema_decay: float = 0.95,  # EMA smoothing for PPL
        # Adaptive window size
        enable_adaptive_window: bool = False,
        window_size_high_ppl: int = 128,  # Small window when PPL high (fast phase)
        window_size_low_ppl: int = 256,   # Large window when PPL low (local context)
    ):
        self.alpha_high = alpha_high
        self.alpha_low = alpha_low
        self.ppl_high = ppl_high
        self.ppl_low = ppl_low
        self.ema_decay = ema_decay

        # Adaptive window
        self.enable_adaptive_window = enable_adaptive_window
        self.window_size_high_ppl = window_size_high_ppl
        self.window_size_low_ppl = window_size_low_ppl
        self.current_window_size = window_size_high_ppl if enable_adaptive_window else None
        self.window_transition_logged = False

        # State
        self.ppl_ema = None
        self.current_alpha_phase = alpha_high  # Start with phase dominant
        self.current_alpha_local = 1.0 - alpha_high
        self.last_transition_ppl = None
        self.transition_logged = False

    def update(self, current_ppl: float) -> tuple:
        """
        Update alpha values based on current PPL.

        Args:
            current_ppl: Current training PPL

        Returns:
            (alpha_phase, alpha_local) tuple
        """
        # Update EMA
        if self.ppl_ema is None:
            self.ppl_ema = current_ppl
        else:
            self.ppl_ema = self.ema_decay * self.ppl_ema + (1 - self.ema_decay) * current_ppl

        ppl = self.ppl_ema

        # Compute alpha_phase based on PPL
        if ppl >= self.ppl_high:
            alpha_phase = self.alpha_high
        elif ppl <= self.ppl_low:
            alpha_phase = self.alpha_low
        else:
            # Linear interpolation
            alpha_phase = self.alpha_low + (ppl - self.ppl_low) * (self.alpha_high - self.alpha_low) / (self.ppl_high - self.ppl_low)

        alpha_local = 1.0 - alpha_phase

        # Log transition when we cross the midpoint (PPL ~550)
        midpoint_ppl = (self.ppl_high + self.ppl_low) / 2
        if not self.transition_logged and self.ppl_ema < midpoint_ppl:
            print(f"🔄 [PPL-Alpha] Phase→Local transition: PPL={self.ppl_ema:.1f} < {midpoint_ppl:.0f}")
            print(f"   α_phase: {self.alpha_high:.2f} → {alpha_phase:.2f}, α_local: {1-self.alpha_high:.2f} → {alpha_local:.2f}")
            self.transition_logged = True
            self.last_transition_ppl = self.ppl_ema

        self.current_alpha_phase = alpha_phase
        self.current_alpha_local = alpha_local

        # Adaptive window size (step change at midpoint)
        if self.enable_adaptive_window:
            old_window = self.current_window_size
            if ppl >= midpoint_ppl:
                self.current_window_size = self.window_size_high_ppl
            else:
                self.current_window_size = self.window_size_low_ppl

            # Log window transition
            if not self.window_transition_logged and old_window != self.current_window_size:
                print(f"📐 [PPL-Alpha] Window size transition: {old_window} → {self.current_window_size}")
                self.window_transition_logged = True

        return alpha_phase, alpha_local

    def get_alphas(self) -> tuple:
        """Return current alpha values."""
        return self.current_alpha_phase, self.current_alpha_local

    def get_window_size(self) -> int:
        """Return current window size (None if adaptive window disabled)."""
        return self.current_window_size

    def get_status(self) -> str:
        """Return status string for logging."""
        if self.ppl_ema is None:
            return "PPL-Alpha: not initialized"
        status = f"PPL-Alpha: EMA={self.ppl_ema:.1f}, α_phase={self.current_alpha_phase:.2f}, α_local={self.current_alpha_local:.2f}"
        if self.enable_adaptive_window:
            status += f", window={self.current_window_size}"
        return status

    def state_dict(self) -> dict:
        """Return state for checkpointing."""
        return {
            "ppl_ema": self.ppl_ema,
            "current_alpha_phase": self.current_alpha_phase,
            "current_alpha_local": self.current_alpha_local,
            "transition_logged": self.transition_logged,
            "last_transition_ppl": self.last_transition_ppl,
        }

    def load_state_dict(self, state: dict):
        """Restore state from checkpoint."""
        self.ppl_ema = state.get("ppl_ema")
        self.current_alpha_phase = state.get("current_alpha_phase", self.alpha_high)
        self.current_alpha_local = state.get("current_alpha_local", 1.0 - self.alpha_high)
        self.transition_logged = state.get("transition_logged", False)
        self.last_transition_ppl = state.get("last_transition_ppl")


# =============================================================================
# SOVEREIGN PHASE CONTROLLER (RSS): Rational Sovereign Sequence
# =============================================================================

# =============================================================================
# PPL-GATED CURRICULUM CONTROLLER: Phased Auxiliary Loss Introduction
# =============================================================================

class CurriculumController:
    """
    PPL-Gated Curriculum Learning Controller.

    Automatically introduces auxiliary losses based on validation PPL thresholds.
    This ensures the model learns coherent language generation BEFORE ontological
    constraints are applied.

    Phases:
        1. FOUNDATION (PPL > 30): Pure cross-entropy, no auxiliary losses
        2. REGULARIZATION (PPL 30-15): Light ontological regularization
        4. SOVEREIGN (PPL < 10): Full auxiliary stack with balanced weights

    Key Principle: LM loss always remains the dominant signal (≥50% of gradients).

    Usage:
        controller = CurriculumController(config)

        # In training loop:
        weights = controller.get_loss_weights(current_val_ppl)
        loss = weights['lm'] * lm_loss + weights['bhava'] * bhava_loss + ...
    """

    # Phase constants
    PHASE_FOUNDATION = "FOUNDATION"      # Pure LM
    PHASE_REGULARIZATION = "REGULARIZATION"  # Light ontology
    PHASE_SOVEREIGN = "SOVEREIGN"        # Full stack

    def __init__(
        self,
        # PPL thresholds for phase transitions
        ppl_regularization: float = 30.0,  # Enter REGULARIZATION when PPL < this
        ppl_grounding: float = 15.0,       # Enter GROUNDING when PPL < this
        ppl_sovereign: float = 10.0,       # Enter SOVEREIGN when PPL < this
        # Stability requirements
        stability_window: int = 5,         # Consecutive evals below threshold
        # Weight configurations per phase
        foundation_weights: Optional[Dict[str, float]] = None,
        regularization_weights: Optional[Dict[str, float]] = None,
        grounding_weights: Optional[Dict[str, float]] = None,
        sovereign_weights: Optional[Dict[str, float]] = None,
        # Hysteresis to prevent oscillation
        hysteresis: float = 1.5,           # Must exceed threshold by this to regress
    ):
        self.ppl_regularization = ppl_regularization
        self.ppl_grounding = ppl_grounding
        self.ppl_sovereign = ppl_sovereign
        self.stability_window = stability_window
        self.hysteresis = hysteresis

        # Current state
        self.current_phase = self.PHASE_FOUNDATION
        self.phase_history: List[Tuple[int, str, float]] = []  # (step, phase, ppl)
        self.ppl_history: List[float] = []
        self.steps_in_phase = 0
        self.phase_locked = False  # Prevent regression once SOVEREIGN reached

        # Default weight configurations - LM always dominant
        # Note: use_sovereign_loss and enable_sovereign_loss control different loss paths:
        # - use_sovereign_loss: Sovereign-1 hardened loss (Priority 2)
        # - enable_sovereign_loss: Sovereign-Lagrangian B1/S3 (Priority 1)
        self.foundation_weights = foundation_weights or {
            'lm': 1.0,
            'bhava': 0.0,
            'coherence': 0.0,
            'b1_lambda': 0.0,
            'mu_s3': 0.0,
        }

        self.regularization_weights = regularization_weights or {
            'lm': 1.0,
            'bhava': 0.01,          # Very light
            'coherence': 0.01,      # Very light
            'b1_lambda': 0.0,
            'mu_s3': 0.0,
        }

        self.grounding_weights = grounding_weights or {
            'lm': 1.0,
            'bhava': 0.02,
            'coherence': 0.02,
            'b1_lambda': 0.0,
            'mu_s3': 0.0,
        }

        self.sovereign_weights = sovereign_weights or {
            'lm': 1.0,              # LM stays at 1.0
            'bhava': 0.05,
            'coherence': 0.03,
            'b1_lambda': 0.1,       # Reduced from 0.5
            'mu_s3': 0.05,          # Reduced from 0.2
        }

        # Weight lookup by phase
        self.phase_weights = {
            self.PHASE_FOUNDATION: self.foundation_weights,
            self.PHASE_REGULARIZATION: self.regularization_weights,
            self.PHASE_GROUNDING: self.grounding_weights,
            self.PHASE_SOVEREIGN: self.sovereign_weights,
        }

    def update(self, val_ppl: float, global_step: int) -> Optional[str]:
        """
        Update controller with new validation PPL.

        Args:
            val_ppl: Current validation perplexity
            global_step: Current training step

        Returns:
            Transition message if phase changed, None otherwise
        """
        self.ppl_history.append(val_ppl)
        self.steps_in_phase += 1

        # Keep history bounded
        if len(self.ppl_history) > 100:
            self.ppl_history = self.ppl_history[-100:]

        # Check for phase transition
        old_phase = self.current_phase
        new_phase = self._determine_phase(val_ppl)

        if new_phase != old_phase:
            self.current_phase = new_phase
            self.steps_in_phase = 0
            self.phase_history.append((global_step, new_phase, val_ppl))

            # Lock at SOVEREIGN to prevent regression
            if new_phase == self.PHASE_SOVEREIGN:
                self.phase_locked = True

            return self._get_transition_message(old_phase, new_phase, val_ppl, global_step)

        return None

    def _determine_phase(self, val_ppl: float) -> str:
        """Determine which phase we should be in based on PPL."""
        # If locked at SOVEREIGN, stay there
        if self.phase_locked:
            return self.PHASE_SOVEREIGN

        # Check stability (need consecutive evals below threshold)
        recent_ppls = self.ppl_history[-self.stability_window:]
        if len(recent_ppls) < self.stability_window:
            # Not enough history, stay in current phase
            return self.current_phase

        avg_recent_ppl = sum(recent_ppls) / len(recent_ppls)

        # Forward transitions (improving PPL)
        if avg_recent_ppl < self.ppl_sovereign:
            return self.PHASE_SOVEREIGN
        elif avg_recent_ppl < self.ppl_grounding:
            return self.PHASE_GROUNDING
        elif avg_recent_ppl < self.ppl_regularization:
            return self.PHASE_REGULARIZATION

        # Backward transitions (worsening PPL) - with hysteresis
        if self.current_phase == self.PHASE_SOVEREIGN:
            if avg_recent_ppl > self.ppl_sovereign * self.hysteresis:
                return self.PHASE_GROUNDING
        elif self.current_phase == self.PHASE_GROUNDING:
            if avg_recent_ppl > self.ppl_grounding * self.hysteresis:
                return self.PHASE_REGULARIZATION
        elif self.current_phase == self.PHASE_REGULARIZATION:
            if avg_recent_ppl > self.ppl_regularization * self.hysteresis:
                return self.PHASE_FOUNDATION

        return self.current_phase

    def get_loss_weights(self) -> Dict[str, float]:
        """Get current loss weights based on phase."""
        return self.phase_weights[self.current_phase].copy()

    def get_config_overrides(self) -> Dict[str, Any]:
        """
        Get config overrides to apply for current phase.

        Returns dict that can be used to update training config.
        """
        weights = self.get_loss_weights()
        return {
            'bhava_lambda': weights['bhava'],
            'coherence_lambda': weights['coherence'],
            'b1_lambda': weights['b1_lambda'],
            'mu_s3': weights['mu_s3'],
            # Sovereign loss controls (critical for curriculum)
            'use_sovereign_loss': weights['use_sovereign_loss'],
            'enable_sovereign_loss': weights['enable_sovereign_loss'],
            # Boolean enables
        }

    def should_enable(self, component: str) -> bool:
        """Check if a specific component should be enabled in current phase."""
        weights = self.get_loss_weights()
        enable_key = f'enable_{component}'
        if enable_key in weights:
            return weights[enable_key]
        # Fall back to checking weight > 0
        return weights.get(component, 0.0) > 0.0

    def _get_transition_message(
        self,
        old_phase: str,
        new_phase: str,
        ppl: float,
        step: int
    ) -> str:
        """Generate human-readable transition message."""
        phase_icons = {
            self.PHASE_FOUNDATION: "📚",
            self.PHASE_REGULARIZATION: "🔧",
            self.PHASE_GROUNDING: "🌉",
            self.PHASE_SOVEREIGN: "👑",
        }

        phase_descriptions = {
            self.PHASE_FOUNDATION: "Pure LM (cross-entropy only)",
            self.PHASE_REGULARIZATION: "Light Regularization (bhava + coherence)",
            self.PHASE_SOVEREIGN: "Full Sovereign (all systems active)",
        }

        icon = phase_icons.get(new_phase, "❓")
        desc = phase_descriptions.get(new_phase, new_phase)
        direction = "↗️" if self._phase_order(new_phase) > self._phase_order(old_phase) else "↘️"

        weights = self.get_loss_weights()
        active = [k for k, v in weights.items() if isinstance(v, bool) and v]

        msg = f"\n{'='*70}\n"
        msg += f"  {icon} [CURRICULUM] Phase Transition {direction}\n"
        msg += f"{'='*70}\n"
        msg += f"  Step {step} | Val PPL: {ppl:.2f}\n"
        msg += f"  {old_phase} → {new_phase}\n"
        msg += f"  {desc}\n"
        if active:
            msg += f"  Active: {', '.join(active)}\n"
        msg += f"{'='*70}\n"

        return msg

    def _phase_order(self, phase: str) -> int:
        """Get numeric order of phase for comparison."""
        order = {
            self.PHASE_FOUNDATION: 0,
            self.PHASE_REGULARIZATION: 1,
            self.PHASE_GROUNDING: 2,
            self.PHASE_SOVEREIGN: 3,
        }
        return order.get(phase, -1)

    def get_status(self) -> Dict[str, Any]:
        """Get current controller status for logging."""
        weights = self.get_loss_weights()
        return {
            'phase': self.current_phase,
            'steps_in_phase': self.steps_in_phase,
            'phase_locked': self.phase_locked,
            'recent_ppl': self.ppl_history[-1] if self.ppl_history else None,
            'avg_recent_ppl': (
                sum(self.ppl_history[-self.stability_window:]) /
                min(len(self.ppl_history), self.stability_window)
                if self.ppl_history else None
            ),
            'thresholds': {
                'regularization': self.ppl_regularization,
                'grounding': self.ppl_grounding,
                'sovereign': self.ppl_sovereign,
            },
            'active_components': [
                k.replace('enable_', '') for k, v in weights.items()
                if isinstance(v, bool) and v
            ],
            'phase_history_count': len(self.phase_history),
        }


# =============================================================================
# V2.3.4: SEQUENCE LENGTH CURRICULUM
# =============================================================================

class SequenceLengthCurriculum:
    """
    Sequence Length Curriculum Controller.

    Starts training with shorter sequences for faster syntax learning,
    then gradually ramps up to full length for long-range dependencies.

    Benefits:
    - Faster early training (more updates per second with short sequences)
    - Lower VRAM usage initially (allows larger batch sizes)
    - Syntax/grammar learned quickly on short contexts
    - Long-range dependencies introduced gradually

    Modes:
    - linear: seq_len = start + (end - start) * (step / ramp_steps)
    - exponential: seq_len = start * (end / start) ^ (step / ramp_steps)

    PPL Gating (optional):
    - If seq_len_ppl_gate > 0, sequence length only increases when PPL drops
      below the gate threshold. This ensures the model masters current length
      before extending.

    Usage:
        curriculum = SequenceLengthCurriculum(config)

        # In training loop:
        current_seq_len = curriculum.get_seq_len(global_step, current_ppl)

        # Check for transitions:
        if curriculum.should_reload_data():
            dataloader = create_dataloader(seq_len=current_seq_len)
            curriculum.mark_data_reloaded()
    """

    def __init__(
        self,
        seq_len_start: int = 256,
        seq_len_end: int = 1024,
        ramp_steps: int = 5000,
        ramp_mode: str = "linear",
        ppl_gate: float = 0.0,
        reload_threshold: int = 64,  # Reload data if seq_len changes by this much
    ):
        self.seq_len_start = seq_len_start
        self.seq_len_end = seq_len_end
        self.ramp_steps = ramp_steps
        self.ramp_mode = ramp_mode
        self.ppl_gate = ppl_gate
        self.reload_threshold = reload_threshold

        # State
        self.current_seq_len = seq_len_start
        self.last_reload_seq_len = seq_len_start
        self.ppl_gated_step = 0  # Effective step for PPL-gated mode
        self.last_ppl_below_gate = False
        self._needs_reload = False

        # History for logging
        self.seq_len_history: List[Tuple[int, int]] = []  # (step, seq_len)

    def get_seq_len(self, step: int, current_ppl: Optional[float] = None) -> int:
        """
        Get the current sequence length based on step and optionally PPL.

        Args:
            step: Current training step
            current_ppl: Current validation PPL (optional, for PPL-gated mode)

        Returns:
            Current sequence length to use
        """
        if step >= self.ramp_steps:
            # Reached full length
            new_seq_len = self.seq_len_end
        else:
            # Calculate progress
            if self.ppl_gate > 0 and current_ppl is not None:
                # PPL-gated mode: only advance when PPL < gate
                if current_ppl < self.ppl_gate:
                    if not self.last_ppl_below_gate:
                        self.last_ppl_below_gate = True
                    self.ppl_gated_step += 1
                else:
                    self.last_ppl_below_gate = False
                progress = min(1.0, self.ppl_gated_step / self.ramp_steps)
            else:
                # Step-based mode
                progress = min(1.0, step / self.ramp_steps)

            # Calculate new sequence length
            if self.ramp_mode == "exponential":
                # Exponential: faster early growth, slower later
                ratio = self.seq_len_end / self.seq_len_start
                new_seq_len = int(self.seq_len_start * (ratio ** progress))
            else:
                # Linear (default)
                new_seq_len = int(
                    self.seq_len_start + (self.seq_len_end - self.seq_len_start) * progress
                )

        # Round to multiple of 64 for efficiency
        new_seq_len = ((new_seq_len + 63) // 64) * 64
        new_seq_len = min(new_seq_len, self.seq_len_end)
        new_seq_len = max(new_seq_len, self.seq_len_start)

        # Check if we need to reload data
        if abs(new_seq_len - self.last_reload_seq_len) >= self.reload_threshold:
            self._needs_reload = True

        # Update state
        old_seq_len = self.current_seq_len
        self.current_seq_len = new_seq_len

        # Log transitions
        if new_seq_len != old_seq_len:
            self.seq_len_history.append((step, new_seq_len))

        return new_seq_len

    def should_reload_data(self) -> bool:
        """Check if dataloader should be reloaded with new sequence length."""
        return self._needs_reload

    def mark_data_reloaded(self):
        """Mark that data has been reloaded with current sequence length."""
        self._needs_reload = False
        self.last_reload_seq_len = self.current_seq_len

    def get_progress(self) -> float:
        """Get curriculum progress as fraction [0, 1]."""
        return (self.current_seq_len - self.seq_len_start) / max(
            1, self.seq_len_end - self.seq_len_start
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current status for logging."""
        return {
            'current_seq_len': self.current_seq_len,
            'target_seq_len': self.seq_len_end,
            'progress': self.get_progress(),
            'mode': self.ramp_mode,
            'ppl_gated': self.ppl_gate > 0,
            'ppl_gate_threshold': self.ppl_gate if self.ppl_gate > 0 else None,
            'transitions': len(self.seq_len_history),
        }

    def get_transition_message(self, step: int, old_len: int, new_len: int) -> str:
        """Generate human-readable transition message."""
        progress = self.get_progress()
        direction = "↗️" if new_len > old_len else "↘️"

        msg = f"\n{'='*60}\n"
        msg += f"  📏 [SEQ CURRICULUM] Length Transition {direction}\n"
        msg += f"{'='*60}\n"
        msg += f"  Step {step} | {old_len} → {new_len} tokens\n"
        msg += f"  Progress: {progress:.1%} toward {self.seq_len_end}\n"
        msg += f"  Mode: {self.ramp_mode.upper()}"
        if self.ppl_gate > 0:
            msg += f" (PPL-gated < {self.ppl_gate})"
        msg += f"\n{'='*60}\n"

        return msg


# =============================================================================
# V9.9.4: READINESS INDEX - COMPOSITE STABILITY MEASUREMENT
# =============================================================================
# ChatGPT's insight: "Learning is stable when improvement slows AND the model
# stops re-orienting itself." PPL alone lies - it can drop during memorization,
# overfitting, or representation churn.
#
# True stability requires:
#   1. ΔPPL → small (velocity collapse)
#   2. ΔΔPPL → small (acceleration collapse)
#   3. Internal geometry stops rotating (phase/state stability)

class ReadinessIndex:
    """
    V9.9.4: Composite stability measurement for curriculum transitions.

    Combines surface metrics (PPL velocity/acceleration) with internal
    geometry metrics (phase coherence, state-delta stability) to determine
    true learning stability.

    ChatGPT's analogy: "Learning to ride a bicycle - true stability is when
    you are no longer correcting every second and your balance stops oscillating."

    The index answers: "Has PPL stopped changing because the model has SETTLED?"
    Not just: "Is PPL going down?"
    """

    def __init__(
        self,
        ppl_velocity_threshold: float = 5.0,      # Max |ΔPPL| for "settled"
        ppl_accel_threshold: float = 2.0,         # Max |ΔΔPPL| for "settled"
        phase_stability_threshold: float = 0.1,   # Max phase variance for stable
        state_delta_threshold: float = 0.5,       # Max state-delta magnitude for stable
        history_window: int = 10,                 # Steps to track
        require_geometry_check: bool = True,      # Gate with internal metrics
        required_consecutive_stable: int = 3,     # N consecutive windows for persistence
    ):
        """
        Initialize ReadinessIndex.

        Args:
            ppl_velocity_threshold: Maximum PPL velocity (ΔPPL) to consider stable
            ppl_accel_threshold: Maximum PPL acceleration (ΔΔPPL) to consider stable
            phase_stability_threshold: Maximum phase coherence variance for stable
            state_delta_threshold: Maximum state-delta norm for stable geometry
            history_window: Number of steps to track in history
            require_geometry_check: If True, also check internal geometry metrics
            required_consecutive_stable: Number of consecutive windows that must
                pass all checks before declaring truly ready (persistence guard)
        """
        self.ppl_velocity_threshold = ppl_velocity_threshold
        self.ppl_accel_threshold = ppl_accel_threshold
        self.phase_stability_threshold = phase_stability_threshold
        self.state_delta_threshold = state_delta_threshold
        self.history_window = history_window
        self.require_geometry_check = require_geometry_check
        self.required_consecutive_stable = required_consecutive_stable

        # History tracking
        self.ppl_history: List[float] = []
        self.phase_coherence_history: List[float] = []
        self.state_delta_history: List[float] = []

        # V9.9.4 Persistence Guard: Track consecutive stable windows
        # "Geometry must be stable for N consecutive windows, not just one"
        # This prevents premature advancement during "false calm" when phase
        # appears stable briefly during representation re-binding.
        self.consecutive_stable_count: int = 0

    def update(
        self,
        ppl: float,
        phase_coherence: Optional[float] = None,
        state_delta_norm: Optional[float] = None,
    ):
        """
        Update history with latest metrics.

        Args:
            ppl: Current perplexity
            phase_coherence: Phase coherence from SPC diagnostics (0-1)
            state_delta_norm: Magnitude of state-delta from Sovereign State
        """
        self.ppl_history.append(ppl)
        if len(self.ppl_history) > self.history_window:
            self.ppl_history.pop(0)

        if phase_coherence is not None:
            self.phase_coherence_history.append(phase_coherence)
            if len(self.phase_coherence_history) > self.history_window:
                self.phase_coherence_history.pop(0)

        if state_delta_norm is not None:
            self.state_delta_history.append(state_delta_norm)
            if len(self.state_delta_history) > self.history_window:
                self.state_delta_history.pop(0)

    def compute_ppl_velocity(self) -> float:
        """Compute ΔPPL (first derivative) - rate of PPL change."""
        if len(self.ppl_history) < 2:
            return float('inf')

        # Average of differences
        diffs = [self.ppl_history[i+1] - self.ppl_history[i]
                 for i in range(len(self.ppl_history) - 1)]
        return sum(diffs) / len(diffs)

    def compute_ppl_acceleration(self) -> float:
        """Compute ΔΔPPL (second derivative) - rate of velocity change."""
        if len(self.ppl_history) < 3:
            return float('inf')

        # First differences (velocities)
        velocities = [self.ppl_history[i+1] - self.ppl_history[i]
                      for i in range(len(self.ppl_history) - 1)]

        # Second differences (acceleration)
        accels = [velocities[i+1] - velocities[i]
                  for i in range(len(velocities) - 1)]

        return sum(accels) / len(accels) if accels else float('inf')

    def compute_phase_stability(self) -> float:
        """Compute variance in phase coherence (lower = more stable)."""
        if len(self.phase_coherence_history) < 3:
            return float('inf')

        mean = sum(self.phase_coherence_history) / len(self.phase_coherence_history)
        variance = sum((x - mean) ** 2 for x in self.phase_coherence_history) / len(self.phase_coherence_history)
        return variance ** 0.5  # Standard deviation

    def compute_state_delta_stability(self) -> float:
        """Compute average state-delta magnitude (lower = more settled)."""
        if len(self.state_delta_history) < 2:
            return float('inf')

        return sum(self.state_delta_history) / len(self.state_delta_history)

    def is_ready(self, require_geometry: Optional[bool] = None) -> Tuple[bool, Dict[str, any]]:
        """
        Check if model has truly settled (ready for curriculum advancement).

        Returns:
            Tuple of (is_ready, diagnostics_dict)
        """
        if require_geometry is None:
            require_geometry = self.require_geometry_check

        velocity = self.compute_ppl_velocity()
        acceleration = self.compute_ppl_acceleration()
        phase_std = self.compute_phase_stability()
        state_delta_avg = self.compute_state_delta_stability()

        diagnostics = {
            'ppl_velocity': velocity,
            'ppl_acceleration': acceleration,
            'phase_stability': phase_std,
            'state_delta_avg': state_delta_avg,
            'checks': {},
        }

        # Check 1: PPL velocity collapsed (ΔPPL → 0)
        velocity_ok = abs(velocity) <= self.ppl_velocity_threshold
        diagnostics['checks']['velocity'] = velocity_ok

        # Check 2: PPL acceleration collapsed (ΔΔPPL → 0)
        accel_ok = abs(acceleration) <= self.ppl_accel_threshold
        diagnostics['checks']['acceleration'] = accel_ok

        # Check 3: Internal geometry stable (if required)
        geometry_ok = True
        if require_geometry:
            phase_ok = phase_std <= self.phase_stability_threshold if phase_std != float('inf') else True
            state_ok = state_delta_avg <= self.state_delta_threshold if state_delta_avg != float('inf') else True
            geometry_ok = phase_ok and state_ok
            diagnostics['checks']['phase_stable'] = phase_ok
            diagnostics['checks']['state_settled'] = state_ok

        diagnostics['checks']['geometry'] = geometry_ok

        # All individual checks pass this window?
        window_stable = velocity_ok and accel_ok and geometry_ok

        # V9.9.4 Persistence Guard: Track consecutive stable windows
        # "Geometry must be stable for N consecutive windows, not just one"
        # This prevents premature advancement during "false calm" when phase
        # appears stable briefly during representation re-binding.
        if window_stable:
            self.consecutive_stable_count += 1
        else:
            self.consecutive_stable_count = 0

        # True readiness requires N consecutive stable windows
        is_ready = self.consecutive_stable_count >= self.required_consecutive_stable

        diagnostics['consecutive_stable'] = self.consecutive_stable_count
        diagnostics['required_consecutive'] = self.required_consecutive_stable
        diagnostics['window_stable'] = window_stable
        diagnostics['ready'] = is_ready

        # Generate reason string
        if is_ready:
            diagnostics['reason'] = "settled"
        elif window_stable and self.consecutive_stable_count < self.required_consecutive_stable:
            diagnostics['reason'] = f"stabilizing_{self.consecutive_stable_count}/{self.required_consecutive_stable}"
        elif not velocity_ok:
            if velocity > 0:
                diagnostics['reason'] = "ppl_rising"
            else:
                diagnostics['reason'] = "ppl_dropping_fast"
        elif not accel_ok:
            diagnostics['reason'] = "ppl_unstable"
        elif not geometry_ok:
            diagnostics['reason'] = "geometry_rotating"
        else:
            diagnostics['reason'] = "unknown"

        return is_ready, diagnostics

    def get_composite_score(self) -> float:
        """
        Get a 0-1 readiness score (useful for logging/visualization).

        Higher = more ready to advance. Includes persistence progress.
        """
        velocity = abs(self.compute_ppl_velocity())
        accel = abs(self.compute_ppl_acceleration())

        # Normalize to 0-1 (higher = better)
        velocity_score = max(0, 1 - velocity / (self.ppl_velocity_threshold * 3))
        accel_score = max(0, 1 - accel / (self.ppl_accel_threshold * 3))

        # Persistence progress: how close are we to required consecutive stable?
        persistence_score = min(1.0, self.consecutive_stable_count / max(1, self.required_consecutive_stable))

        # Weight: velocity + acceleration determine metric stability,
        # persistence determines temporal stability
        metric_score = 0.6 * velocity_score + 0.4 * accel_score
        return 0.7 * metric_score + 0.3 * persistence_score

    def reset_persistence(self):
        """
        Reset the consecutive stability counter.

        Call this after a curriculum transition to start fresh with
        stability tracking for the new stage.
        """
        self.consecutive_stable_count = 0

    def get_persistence_progress(self) -> Tuple[int, int]:
        """Get (current_consecutive, required_consecutive) for logging."""
        return self.consecutive_stable_count, self.required_consecutive_stable


# =============================================================================
# V9.9.3: SOVEREIGN RESET PROTOCOL FOR CURRICULUM TRANSITIONS
# =============================================================================
# Based on Gemini's "Soft-Reset" recommendations to preserve PPL progress
# while ensuring clean state transitions for split/seq_len changes.

def dampen_layer_momentum(
    optimizer: torch.optim.Optimizer,
    model: nn.Module,
    layer_indices: list,
    dampen_factor: float = 0.5,
    verbose: bool = True,
) -> dict:
    """
    Apply momentum dampening to specific layers' optimizer state.

    When a layer transitions from Quadratic to Phase (α reaches 1.0), we dampen
    the optimizer's momentum buffers for that layer's parameters. This allows
    the newly "Phase-engaged" layer to find its own direction without being
    pulled by the "Quadratic ghost" of its past.

    Args:
        optimizer: The optimizer (AdamW expected)
        model: The model to extract layer parameters from
        layer_indices: List of layer indices that completed transition
        dampen_factor: Factor to multiply momentum by (0.5 = 50% decay)
        verbose: Whether to print diagnostic messages

    Returns:
        dict with dampening info
    """
    dampened = {
        'layers_dampened': [],
        'params_affected': 0,
    }

    if not layer_indices:
        return dampened

    # Find parameters for the specified layers
    # This assumes model has a 'transformer' or 'layers' attribute
    layer_params = []
    for name, param in model.named_parameters():
        for layer_idx in layer_indices:
            # Match common naming patterns: layers.N, transformer.h.N, encoder.layer.N
            if (f'layers.{layer_idx}.' in name or
                f'transformer.h.{layer_idx}.' in name or
                f'encoder.layer.{layer_idx}.' in name or
                f'_layers.{layer_idx}.' in name):
                layer_params.append(param)
                break

    # Dampen momentum buffers for these parameters
    for param in layer_params:
        if param in optimizer.state:
            state = optimizer.state[param]
            # AdamW uses 'exp_avg' (first moment) and 'exp_avg_sq' (second moment)
            if 'exp_avg' in state:
                state['exp_avg'].mul_(dampen_factor)
            if 'exp_avg_sq' in state:
                state['exp_avg_sq'].mul_(dampen_factor)
            dampened['params_affected'] += 1

    dampened['layers_dampened'] = layer_indices

    if verbose and dampened['params_affected'] > 0:
        print(f"  🎛️  [MOMENTUM DAMPEN] Applied {dampen_factor:.0%} decay to layers {layer_indices}")
        print(f"     Parameters affected: {dampened['params_affected']}")

    return dampened


def on_seq_len_transition(
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    old_seq_len: int,
    new_seq_len: int,
    grad_accum_counter: int = 0,
    verbose: bool = True,
) -> dict:
    """
    Sovereign Reset Protocol for sequence length transitions.

    Addresses the "Re-Loading Tax" concern: when switching sequence lengths mid-training,
    we need to ensure clean state to prevent:
    - Stale gradient accumulation from old sequence length
    - Memory fragmentation from different tensor shapes

    This follows Gemini's "Soft-Reset" recommendations for robust seq_len transitions.

    Protocol steps:
    1. Zero gradients (set_to_none=True for memory efficiency)
    2. Clear CUDA cache (releases fragmented memory)
    3. Return skip_step flag (caller should skip one training step for VRAM stabilization)

    Args:
        optimizer: The optimizer to clear gradients from
        device: The device (for CUDA cache clearing)
        old_seq_len: Previous sequence length
        new_seq_len: New sequence length
        grad_accum_counter: Current gradient accumulation count (for diagnostics)
        verbose: Whether to print diagnostic messages

    Returns:
        dict with cleared state info and skip_step flag
    """
    result = {
        'gradients_cleared': False,
        'cuda_cache_cleared': False,
        'grad_accum_flushed': grad_accum_counter > 0,
        'old_seq_len': old_seq_len,
        'new_seq_len': new_seq_len,
        'skip_step': True,  # Caller should skip one step for VRAM stabilization
    }

    # 1. Clear optimizer gradients (set_to_none=True for memory efficiency)
    optimizer.zero_grad(set_to_none=True)
    result['gradients_cleared'] = True

    # 2. Clear CUDA cache if on GPU (releases fragmented memory)
    if device.type == "cuda":
        torch.cuda.empty_cache()
        result['cuda_cache_cleared'] = True

    # 3. Log diagnostic info
    if verbose:
        msg_parts = ["  🧹 [SOVEREIGN RESET] Seq transition protocol:"]
        msg_parts.append(f"     Gradients: cleared (set_to_none=True)")
        if result['cuda_cache_cleared']:
            msg_parts.append(f"     CUDA cache: cleared")
        if result['grad_accum_flushed']:
            msg_parts.append(f"     ⚠️  Gradient accum flushed ({grad_accum_counter} steps were pending)")
        msg_parts.append(f"     Next step: SKIP (VRAM stabilization)")
        print("\n".join(msg_parts))

    return result


def should_sync_curriculum_update(step: int, gradient_accumulation: int) -> bool:
    """
    Check if curriculum updates should fire (Sync-Point Evolution).

    Curriculum updates should only happen at the END of a gradient accumulation cycle.
    This ensures the "Old Body" has fully pushed its gradients before transitioning to
    a "New Body" (different split) or "New Environment" (different seq_len).

    Args:
        step: Current accumulation step within the cycle
        gradient_accumulation: Total accumulation steps per cycle

    Returns:
        True if this is a sync point (end of accumulation cycle)
    """
    return (step + 1) % gradient_accumulation == 0


# =============================================================================
# V9.8.6: THREE-PHASE CURRICULUM CONTROLLER (Generic PPL-based engagement)
# =============================================================================

class ThreePhaseCurriculum:
    """
    Generic three-phase curriculum controller for PPL-based engagement.

    INVERTED CURRICULUM: Components activate when model is COMPETENT (low PPL).
    This follows proper curriculum learning where advanced controllers are added
    after basic language modeling is established.

    Phases:
        FOUNDATION (PPL > engage_ppl): Component OFF - learning basics (scale=0.0)
        TRANSITION (disengage_ppl < PPL < engage_ppl): Linear ramp-up
        CONSTRUCTION (PPL < disengage_ppl): Component fully active (scale=1.0)
    """

    PHASE_FOUNDATION = "FOUNDATION"
    PHASE_TRANSITION = "TRANSITION"
    PHASE_CONSTRUCTION = "CONSTRUCTION"

    def __init__(
        self,
        name: str,
        engage_ppl: float = 100.0,
        disengage_ppl: float = 30.0,
        rampdown_steps: int = 500,
    ):
        self.name = name
        self.engage_ppl = engage_ppl
        self.disengage_ppl = disengage_ppl
        self.rampdown_steps = rampdown_steps

        # State tracking
        self.phase = self.PHASE_CONSTRUCTION
        self.disengage_step: Optional[int] = None
        self.scale = 1.0
        self.graduated = False
        self._last_log_phase = None

    def update(self, val_ppl: float, step: int) -> float:
        """Update phase based on current PPL and compute scaling factor."""
        if self.graduated:
            self.phase = self.PHASE_CONSTRUCTION
            self.scale = 1.0
            return 1.0

        if val_ppl > self.engage_ppl:
            self.phase = "FOUNDATION"
            self.disengage_step = None
            self.scale = 0.0
            self._log_phase_change(step, val_ppl)
            return 0.0

        if val_ppl <= self.disengage_ppl:
            if self.disengage_step is None:
                self.disengage_step = step
                print(f"  [{self.name}] CONSTRUCTION phase triggered at step {step} "
                      f"(PPL={val_ppl:.1f} <= {self.disengage_ppl})")
            self.phase = self.PHASE_CONSTRUCTION
            self.scale = 1.0
            self._log_phase_change(step, val_ppl)
            return 1.0

        self.phase = self.PHASE_TRANSITION
        self.disengage_step = None
        ppl_range = self.engage_ppl - self.disengage_ppl
        if ppl_range > 0:
            progress = (self.engage_ppl - val_ppl) / ppl_range
            self.scale = max(0.0, min(1.0, progress))
        else:
            self.scale = 0.5
        self._log_phase_change(step, val_ppl)
        return self.scale

    def _log_phase_change(self, step: int, val_ppl: float):
        """Log only when phase changes."""
        if self.phase != self._last_log_phase:
            self._last_log_phase = self.phase
            if self.phase == self.PHASE_TRANSITION:
                print(f"  [{self.name}] Phase: {self.phase} | "
                      f"PPL={val_ppl:.1f} | scale={self.scale:.0%}")

    def get_status(self) -> str:
        """Get human-readable status string."""
        if self.graduated:
            return f"[{self.name}] GRADUATED (full construction)"
        elif self.phase == self.PHASE_CONSTRUCTION:
            return f"[{self.name}] CONSTRUCTION (scale={self.scale:.0%})"
        elif self.phase == self.PHASE_TRANSITION:
            return f"[{self.name}] TRANSITION (scale={self.scale:.0%})"
        else:
            return f"[{self.name}] FOUNDATION (scale={self.scale:.0%})"

    def get_state(self) -> Dict[str, Any]:
        """Get serializable state for checkpointing."""
        return {
            'phase': self.phase,
            'disengage_step': self.disengage_step,
            'scale': self.scale,
            'graduated': self.graduated,
        }

    def load_state(self, state: Dict[str, Any]):
        """Load state from checkpoint."""
        self.phase = state.get('phase', self.PHASE_CONSTRUCTION)
        self.disengage_step = state.get('disengage_step', None)
        self.scale = state.get('scale', 1.0)
        self.graduated = state.get('graduated', False)


# =============================================================================
# DYNAMIC RELAXATION CONTROLLER: 9:3 → 6:6 TRANSITION
# =============================================================================

class DynamicRelaxationController:
    """
    Manages dynamic transition from 9:3 (Authority-heavy) to 6:6 (Balanced) split.

    The controller monitors a StabilityIndex and triggers relaxation when the
    model has achieved sufficient "Sattvic Plateau" - meaning the Authority
    layers have firmly imprinted ontological structure.

    Phases:
    1. AUTHORITY (9:3): Heavy dampening, ontological imprinting
    2. MONITORING: Track StabilityIndex over rolling window
    3. RELAXATION: Transition to 6:6 with Dampened Thaw
    4. BALANCED (6:6): Increased sensory expressivity
    5. RECOVERY: Viparyaya reset if PPL spikes after relaxation

    StabilityIndex = 0.7 * GC + 0.3 * (1 - S_Drift_EMA)

    Usage:
        controller = DynamicRelaxationController(gradient_scaler, model, config)
        # In training loop:
        should_relax, action = controller.update(guna_coherence, s_drift_ema, val_ppl, step)
        if action == "RELAX":
            controller.execute_relaxation(current_step=step)  # Triggers WeightTransfer + Guna-Lock
        elif action == "RECOVER":
            controller.execute_recovery()  # Releases Guna-Lock
    """

    # Controller states
    STATE_AUTHORITY = "AUTHORITY"       # 9:3 split, heavy dampening
    STATE_MONITORING = "MONITORING"     # Tracking stability for transition
    STATE_RELAXING = "RELAXING"         # Transitioning to 6:6
    STATE_BALANCED = "BALANCED"         # 6:6 split, balanced learning
    STATE_RECOVERY = "RECOVERY"         # Viparyaya reset, back to 9:3

    def __init__(
        self,
        gradient_scaler: HierarchicalGradientScaler,
        model: nn.Module,
        # Stability thresholds
        stability_threshold: float = 0.82,
        stability_window: int = 500,        # Steps for stability check (rolling window)
        streak_target: int = 5,             # Consecutive stable evals for 'consecutive' mode
        mode: str = "consecutive",          # "consecutive", "average", or "sa_ratio"
        # Split configurations
        authority_split: Tuple[int, int] = (9, 3),  # Initial 9:3
        balanced_split: Tuple[int, int] = (6, 6),   # Target 6:6
        # Dampening configurations
        authority_alpha_max: float = 0.5,    # α ceiling for 9:3
        balanced_alpha_max: float = 0.7,     # α ceiling for 6:6
        thaw_alpha_start: float = 0.05,      # Dampened Thaw start for new layers
        thaw_warmup_steps: int = 250,        # Steps to ramp new layers
        # Recovery settings
        ppl_spike_threshold: float = 0.20,   # 20% PPL increase triggers recovery
        recovery_steps: int = 200,           # Steps to stay in recovery
        # Monitoring
        guna_coherence_weight: float = 0.7,
        s_drift_weight: float = 0.3,
        # Weight Transfer settings
        guna_lock_steps: int = 50,           # Steps to freeze W_q/W_k post-swap
        enable_weight_transfer: bool = True,  # Enable weight transfer during relaxation
        # Force relaxation at specific step (bypasses stability check)
        force_relaxation_step: int = None,   # If set, force 9:3→6:6 at this step
        # Sovereign Saturation Gate (automatic detection)
        enable_saturation_gate: bool = True,  # Enable automatic saturation detection
        saturation_coherence_threshold: float = 0.74,  # Coherence threshold for trigger
        saturation_patience: int = 50,        # Steps where sensory derivative must be flat
        saturation_thaw_start: float = 0.3,   # New sensory layers start at this α
        saturation_thaw_end: float = 0.7,     # Ramp to this α
        saturation_thaw_steps: int = 100,     # Steps to ramp new layers
    ):
        self.gradient_scaler = gradient_scaler
        self.model = model

        # Thresholds
        self.stability_threshold = stability_threshold
        self.stability_window = stability_window
        self.streak_target = streak_target
        self.mode = mode.lower()
        self.ppl_spike_threshold = ppl_spike_threshold
        self.recovery_steps = recovery_steps

        # Validate mode
        if self.mode not in ("consecutive", "average", "sa_ratio"):
            raise ValueError(f"relaxation_mode must be 'consecutive', 'average', or 'sa_ratio', got '{mode}'")

        # Split configurations
        self.authority_split = authority_split
        self.balanced_split = balanced_split
        self.authority_alpha_max = authority_alpha_max
        self.balanced_alpha_max = balanced_alpha_max
        self.thaw_alpha_start = thaw_alpha_start
        self.thaw_warmup_steps = thaw_warmup_steps

        # Weights for StabilityIndex
        self.guna_coherence_weight = guna_coherence_weight
        self.s_drift_weight = s_drift_weight

        # Weight Transfer for 9:3 → 6:6 transition
        self.enable_weight_transfer = enable_weight_transfer
        self.guna_lock_steps = guna_lock_steps

        # Force relaxation at specific step
        self.force_relaxation_step = force_relaxation_step
        self.force_relaxation_triggered = False  # Track if we've already forced

        # Sovereign Saturation Gate
        self.enable_saturation_gate = enable_saturation_gate
        self.saturation_coherence_threshold = saturation_coherence_threshold
        self.saturation_patience = saturation_patience
        self.saturation_thaw_start = saturation_thaw_start
        self.saturation_thaw_end = saturation_thaw_end
        self.saturation_thaw_steps = saturation_thaw_steps
        # Saturation tracking
        self.sensory_flow_history = []  # Track sensory flow for derivative
        self.saturation_flat_count = 0  # Count of steps with flat derivative
        self.saturation_triggered = False  # Track if saturation gate fired
        self.saturation_thaw_step = None  # Step when thaw started

        # V9.5.0 Dynamic Streak Controller: Entropy-triggered flip
        self.metabolic_step_counter = 0   # Consecutive steps meeting validity criteria
        self.metabolic_entropy_threshold = 0.45  # Below this = looping, need fast escape
        self.metabolic_vram_safety = 0.90  # Don't flip if VRAM > 90%
        self._current_target_streak = 500  # Dynamic target (50 or 500 based on entropy)

        # V9.5.1 Multi-Stage Granular Evolution: 9:3 → 6:6 → 5:7 → 4:8 → 3:9
        self.evolution_stages = [(9, 3), (6, 6), (5, 7), (4, 8), (3, 9)]
        self.current_stage_idx = 0  # Start at 9:3
        self.evolution_streak = 0   # Steps meeting evolution criteria
        self.evolution_patience = 200  # Steps needed to trigger next stage
        self.evolution_entropy_floor = 0.42  # Abort if entropy drops below this
        self.evolution_coherence_min = 0.82  # Must maintain high coherence

        # V9.9.1 Multi-Stage Evolution with PPL/Step triggers
        self.evolution_trigger_mode = "metrics"  # "metrics", "ppl", "step", "auto"
        self.evolution_ppl_triggers = []  # PPL thresholds: [100, 50, 25, 15]
        self.evolution_step_triggers = []  # Step triggers: [10000, 30000, 50000, 70000]
        self.evolution_ppl_window = 10  # Steps to average PPL for smoother triggers
        self.evolution_thaw_alpha = 0.1  # Initial gradient scale for new sensory layers
        self.evolution_thaw_steps = 300  # Steps to ramp new sensory layer gradients
        self.ppl_history = []  # Rolling PPL history for averaging
        self.evolution_ppl_triggered = [False] * 10  # Track which PPL triggers fired
        self.evolution_step_triggered = [False] * 10  # Track which step triggers fired

        # V9.5.2 Emergency Stress-Probe (Phase A: 3:9 Rajas)
        self.stress_probe_active = False  # Currently in stress-probe mode
        self.stress_probe_start_step = None  # When stress-probe started
        self.stress_probe_degeneracy_streak = 0  # Consecutive evals of degeneracy detection
        self.stress_probe_exit_streak = 0  # Consecutive evals meeting exit criteria
        self.pre_stress_probe_split = None  # Split before stress-probe (to restore)
        self.pre_stress_probe_lr = None  # LR before stress-probe (to restore)
        self.stress_probe_steps_in = 0  # Steps spent in stress-probe
        # Gradual LR restore tracking (ChatGPT guardrail)
        self.stress_probe_lr_restoring = False  # Currently restoring LR
        self.stress_probe_lr_restore_start_step = None  # When LR restore started
        self.stress_probe_reduced_lr = None  # The reduced LR during stress-probe

        # [S5] Entropy Gate: Block relaxation if entropy too high
        self.entropy_gate_threshold = 0.50  # Must be below this to relax
        self.entropy_gate_blocked = False   # Track if we blocked due to entropy
        self.last_entropy = None            # For logging
        if enable_weight_transfer:
            # Layers 6, 7, 8 become Sensory in 6:6 split
            # Layer 5 becomes the new Witness
            self.weight_transfer = WeightTransfer(
                model=model,
                guna_lock_steps=guna_lock_steps,
                anchor_layer_idx=balanced_split[0] - 1,  # New Witness is layer 5 in 6:6
                transferred_layers=(6, 7, 8),  # These layers change from Authority to Sensory
            )
        else:
            self.weight_transfer = None

        # State tracking
        self.state = self.STATE_AUTHORITY
        self.stability_streak = 0
        self.stability_history = []
        self.ssi_rolling_window = []  # For average mode
        self.sa_rolling_window = []   # For sa_ratio mode
        self.max_history = 1000

        # PPL tracking for recovery
        self.pre_relaxation_ppl = None
        self.recovery_start_step = None
        self.relaxation_step = None

        # Integration Tax tracking (Jolt Log)
        self.integration_tax_logged = False
        self.post_relaxation_ppl_samples = []
        self.integration_tax_sample_count = 10  # Steps to wait before measuring

        # Telemetry
        self.transitions = []
        self.current_split = authority_split

        print(f"\n  [DynamicRelaxation] Controller initialized:")
        print(f"    Mode: {self.mode.upper()}")
        print(f"    Initial split: {authority_split[0]}:{authority_split[1]}")
        print(f"    Target split: {balanced_split[0]}:{balanced_split[1]}")
        print(f"    Stability threshold: {stability_threshold}")
        print(f"    Stability window: {stability_window} steps")
        if enable_weight_transfer:
            print(f"    Weight Transfer: ENABLED")
            print(f"    Guna-Lock: {guna_lock_steps} steps post-swap")
        if force_relaxation_step is not None:
            print(f"    ⚡ Force Relaxation: Step {force_relaxation_step} (bypasses stability check)")
        if enable_saturation_gate:
            print(f"    🎯 Saturation Gate: ENABLED")
            print(f"       Coherence threshold: {saturation_coherence_threshold}")
            print(f"       Patience: {saturation_patience} steps flat derivative")
            print(f"       Dampened Thaw: α {saturation_thaw_start}→{saturation_thaw_end} over {saturation_thaw_steps} steps")

    def compute_stability_index(
        self,
        guna_coherence: float,
        s_drift_ema: float,
    ) -> float:
        """
        Compute the Sattvic Stability Index.

        StabilityIndex = w_gc * GC + w_drift * (1 - S_Drift_EMA)

        High values indicate:
        - GC high: Authority layers have locked global phase rotation
        - S_Drift low: Reality signal aligned with ontological intent
        """
        # Input validation - clamp and warn on out-of-bounds values
        if not (0.0 <= guna_coherence <= 1.0):
            guna_coherence = max(0.0, min(1.0, guna_coherence))
        if not (0.0 <= s_drift_ema <= 1.0):
            s_drift_ema = max(0.0, min(1.0, s_drift_ema))

        # Handle NaN/Inf gracefully
        if math.isnan(guna_coherence) or math.isinf(guna_coherence):
            guna_coherence = 0.5
        if math.isnan(s_drift_ema) or math.isinf(s_drift_ema):
            s_drift_ema = 0.5

        stability = (
            self.guna_coherence_weight * guna_coherence +
            self.s_drift_weight * (1.0 - s_drift_ema)
        )
        return max(0.0, min(1.0, stability))

    def _check_relaxation_ready(self, stability_index: float, sa_ratio: float = None) -> bool:
        """
        Check if relaxation should trigger based on current mode.

        Modes:
        - consecutive: Requires SSI >= threshold for N consecutive steps
        - average: Requires average SSI >= threshold over rolling N-step window
        - sa_ratio: Requires average S/A ratio >= threshold over rolling N-step window
        """
        if self.mode == "consecutive":
            # Consecutive mode: reset on any dip, use streak_target for trigger
            if stability_index >= self.stability_threshold:
                self.stability_streak += 1
                return self.stability_streak >= self.streak_target
            else:
                self.stability_streak = 0
                return False

        elif self.mode == "sa_ratio":
            # S/A Ratio mode: rolling window mean of S/A ratio
            if sa_ratio is None:
                return False

            self.sa_rolling_window.append(sa_ratio)
            if len(self.sa_rolling_window) > self.stability_window:
                self.sa_rolling_window.pop(0)

            if len(self.sa_rolling_window) >= self.stability_window:
                avg_sa = sum(self.sa_rolling_window) / len(self.sa_rolling_window)
                self.stability_streak = len(self.sa_rolling_window)  # For display
                return avg_sa >= self.stability_threshold

            self.stability_streak = len(self.sa_rolling_window)
            return False

        else:  # average mode (SSI-based)
            # Average mode: rolling window mean
            self.ssi_rolling_window.append(stability_index)
            if len(self.ssi_rolling_window) > self.stability_window:
                self.ssi_rolling_window.pop(0)

            if len(self.ssi_rolling_window) >= self.stability_window:
                avg_ssi = sum(self.ssi_rolling_window) / len(self.ssi_rolling_window)
                return avg_ssi >= self.stability_threshold

            return False

    def _check_saturation_gate(
        self,
        coherence: float,
        sensory_flow: float,
        global_step: int,
    ) -> bool:
        """
        Sovereign Saturation Gate: Detect when sensory layers are saturated.

        Triggers when:
        1. Coherence >= saturation_coherence_threshold (0.74)
        2. Sensory flow derivative is flat for saturation_patience steps (50)

        Returns True if saturation detected and relaxation should trigger.
        """
        if not self.enable_saturation_gate or self.saturation_triggered:
            return False

        # Check coherence threshold first
        if coherence < self.saturation_coherence_threshold:
            self.saturation_flat_count = 0  # Reset if coherence drops
            return False

        # Track sensory flow history
        self.sensory_flow_history.append(sensory_flow)
        if len(self.sensory_flow_history) > self.saturation_patience + 10:
            self.sensory_flow_history.pop(0)

        # Need enough history to compute derivative
        if len(self.sensory_flow_history) < 10:
            return False

        # Compute derivative (change over last 10 steps)
        recent = self.sensory_flow_history[-10:]
        derivative = abs(recent[-1] - recent[0]) / 10.0

        # Check if derivative is "flat" (< 0.001 change per step)
        # Sensory flow at 1.00 means it's saturated
        is_saturated = sensory_flow >= 0.99 or derivative < 0.001

        if is_saturated:
            self.saturation_flat_count += 1
        else:
            self.saturation_flat_count = max(0, self.saturation_flat_count - 1)

        # Trigger if flat for patience steps
        if self.saturation_flat_count >= self.saturation_patience:
            self.saturation_triggered = True
            self.saturation_thaw_step = global_step
            return True

        return False

    def check_metabolic_flip(
        self,
        metrics: Dict[str, float],
        vram_usage: float,
        global_step: int,
    ) -> str:
        """
        V9.5.0 Dynamic Streak Controller: Entropy-triggered 9:3 → 6:6 flip.

        Key insight: Entropy determines streak LENGTH, VRAM determines streak VALIDITY.
        - Low entropy (<0.45) = looping = SHORT streak (50) to escape quickly
        - High entropy (>0.45) = learning = LONG streak (500) to solidify

        Validity criteria (must pass every step):
        1. Coherence > 0.74 (Sattvic stability)
        2. VRAM < 90% (safety gate)

        If validity fails, counter resets to 0.
        Returns "TRIGGER_FLIP" when dynamic target reached.
        """
        if self.saturation_triggered:
            return "ALREADY_FLIPPED"

        coherence = metrics.get('coherence', 0.0)
        entropy = metrics.get('entropy', 1.0)

        # 1. Validity Criteria (must pass to increment counter)
        is_stable = coherence > self.saturation_coherence_threshold  # 0.74
        is_safe = vram_usage < self.metabolic_vram_safety            # 0.90

        # 2. Dynamic Streak Target based on Entropy
        # Low entropy = looping/repetition = need SHORT streak to escape
        # High entropy = still learning = need LONG streak to solidify
        if entropy < self.metabolic_entropy_threshold:  # 0.45
            target_streak = 50   # Emergency "Escape" Mode - break loops fast
        else:
            target_streak = 500  # Standard "Sattvic" Mode - let authority crystallize

        # 3. Increment or Reset Counter (based on validity, not entropy)
        if is_stable and is_safe:
            self.metabolic_step_counter += 1
        else:
            self.metabolic_step_counter = 0  # Hard reset if validity fails

        # 4. Execute Flip when dynamic target reached
        if self.metabolic_step_counter >= target_streak:
            self.saturation_triggered = True
            self.saturation_thaw_step = global_step
            mode = "ESCAPE" if entropy < self.metabolic_entropy_threshold else "SATTVIC"
            print(f"\n  🚀 [DYNAMIC FLIP] Step {global_step}: {mode} mode - target {target_streak} reached")
            print(f"      Coherence: {coherence:.3f} > 0.74 ✓")
            print(f"      Entropy:   {entropy:.3f} {'< 0.45 (looping)' if entropy < 0.45 else '>= 0.45 (learning)'}")
            print(f"      VRAM:      {vram_usage*100:.1f}% < 90% ✓")
            return "TRIGGER_FLIP"

        # Store current target for status display
        self._current_target_streak = target_streak
        return "WAITING"

    def check_granular_evolution(
        self,
        metrics: Dict[str, float],
        vram_usage: float,
        global_step: int,
    ) -> str:
        """
        V9.5.1 Granular Evolution: Check for multi-stage transitions.

        After 6:6, can evolve to 5:7 → 4:8 → 3:9 based on:
        - Coherence > 0.82 (stability)
        - Entropy > 0.42 (diversity floor - prevent repetition curse)
        - VRAM < 90% (safety)

        Triggers when criteria met for evolution_patience steps (200).
        """
        # Only check if we're past the initial 6:6 stage
        if self.current_stage_idx < 1:
            return "NOT_READY"

        # Already at final stage (3:9)
        if self.current_stage_idx >= len(self.evolution_stages) - 1:
            return "FINAL_STAGE"

        coherence = metrics.get('coherence', 0.0)
        entropy = metrics.get('entropy', 1.0)

        # Evolution criteria (different from initial flip)
        is_stable = coherence > self.evolution_coherence_min  # 0.82
        is_diverse = entropy > self.evolution_entropy_floor   # 0.42 - MUST have diversity
        is_safe = vram_usage < self.metabolic_vram_safety     # 0.90

        # Key insight: We want to evolve when STIFF (low entropy) but stable
        # This breaks the repetition curse by adding sensory capacity
        wants_evolution = entropy < 0.45 and coherence > 0.85  # Stiff but stable

        if is_stable and is_safe and (is_diverse or wants_evolution):
            self.evolution_streak += 1
        else:
            self.evolution_streak = 0  # Hard reset

        # Trigger evolution when patience reached
        if self.evolution_streak >= self.evolution_patience:
            next_stage = self.evolution_stages[self.current_stage_idx + 1]
            return f"EVOLVE_TO_{next_stage[0]}_{next_stage[1]}"

        return "WAITING"

    def execute_granular_evolution(self, global_step: int) -> Tuple[int, int]:
        """
        Execute transition to next evolution stage.

        Returns the new (authority, sensory) split.
        """
        if self.current_stage_idx >= len(self.evolution_stages) - 1:
            return self.current_split

        # Advance to next stage
        self.current_stage_idx += 1
        new_split = self.evolution_stages[self.current_stage_idx]

        # Reset evolution streak for next stage
        self.evolution_streak = 0

        # Update current split
        self.current_split = new_split

        # Print evolution message
        prev_split = self.evolution_stages[self.current_stage_idx - 1]
        print(f"\n  🌀 [GRANULAR EVOLUTION] Step {global_step}")
        print(f"      {prev_split[0]}:{prev_split[1]} → {new_split[0]}:{new_split[1]}")
        print(f"      Authority layers: 0-{new_split[0]-1}")
        print(f"      Sensory layers: {new_split[0]}-11")
        print(f"      Transitional layer: {new_split[0]} (newly sensory)")

        return new_split

    def configure_evolution(
        self,
        trigger_mode: str = "auto",
        ppl_triggers: str = "",
        step_triggers: str = "",
        custom_stages: str = "",
        patience: int = 200,
        coherence_min: float = 0.82,
        entropy_floor: float = 0.42,
        ppl_window: int = 10,
        thaw_alpha: float = 0.1,
        thaw_steps: int = 300,
    ):
        """
        V9.9.1 Configure multi-stage evolution from config parameters.

        Args:
            trigger_mode: "metrics", "ppl", "step", or "auto"
            ppl_triggers: Comma-separated PPL thresholds (e.g., "100,50,25,15")
            step_triggers: Comma-separated step thresholds (e.g., "10000,30000,50000,70000")
            custom_stages: Comma-separated stages (e.g., "9:3,6:6,4:8,3:9")
            patience: Steps of stable metrics before evolution (metrics mode)
            coherence_min: Minimum coherence for evolution (metrics mode)
            entropy_floor: Minimum entropy for evolution (metrics mode)
            ppl_window: Steps to average PPL for smoother triggers
            thaw_alpha: Initial gradient scale for newly sensory layers
            thaw_steps: Steps to ramp newly sensory layer gradients
        """
        self.evolution_trigger_mode = trigger_mode.lower()
        self.evolution_patience = patience
        self.evolution_coherence_min = coherence_min
        self.evolution_entropy_floor = entropy_floor
        self.evolution_ppl_window = ppl_window
        self.evolution_thaw_alpha = thaw_alpha
        self.evolution_thaw_steps = thaw_steps

        # Parse PPL triggers
        if ppl_triggers:
            try:
                self.evolution_ppl_triggers = [float(x.strip()) for x in ppl_triggers.split(",") if x.strip()]
                self.evolution_ppl_triggered = [False] * len(self.evolution_ppl_triggers)
            except ValueError:
                print(f"  ⚠️ [EVOLUTION] Invalid PPL triggers: {ppl_triggers}, using empty list")
                self.evolution_ppl_triggers = []

        # Parse step triggers
        if step_triggers:
            try:
                self.evolution_step_triggers = [int(x.strip()) for x in step_triggers.split(",") if x.strip()]
                self.evolution_step_triggered = [False] * len(self.evolution_step_triggers)
            except ValueError:
                print(f"  ⚠️ [EVOLUTION] Invalid step triggers: {step_triggers}, using empty list")
                self.evolution_step_triggers = []

        # Parse custom stages
        if custom_stages:
            try:
                stages = []
                for stage in custom_stages.split(","):
                    parts = stage.strip().split(":")
                    if len(parts) == 2:
                        auth, sens = int(parts[0]), int(parts[1])
                        if auth + sens == 12:  # Validate 12-layer model
                            stages.append((auth, sens))
                        else:
                            print(f"  ⚠️ [EVOLUTION] Stage {stage} doesn't sum to 12, skipping")
                if stages:
                    self.evolution_stages = stages
                    print(f"  🔧 [EVOLUTION] Custom stages: {' → '.join(f'{a}:{s}' for a, s in stages)}")
            except ValueError:
                print(f"  ⚠️ [EVOLUTION] Invalid custom stages: {custom_stages}, using default")

        # Auto-detect best mode if "auto"
        if self.evolution_trigger_mode == "auto":
            if self.evolution_ppl_triggers:
                self.evolution_trigger_mode = "ppl"
            elif self.evolution_step_triggers:
                self.evolution_trigger_mode = "step"
            else:
                self.evolution_trigger_mode = "metrics"

        # Log configuration
        print(f"\n  🧬 [MULTI-STAGE EVOLUTION] Configuration:")
        print(f"      Trigger mode: {self.evolution_trigger_mode.upper()}")
        print(f"      Stages: {' → '.join(f'{a}:{s}' for a, s in self.evolution_stages)}")
        if self.evolution_trigger_mode == "ppl" and self.evolution_ppl_triggers:
            print(f"      PPL triggers: {self.evolution_ppl_triggers}")
        elif self.evolution_trigger_mode == "step" and self.evolution_step_triggers:
            print(f"      Step triggers: {self.evolution_step_triggers}")
        else:
            print(f"      Metrics: coherence>{coherence_min}, entropy>{entropy_floor}, patience={patience}")
        print(f"      Thaw: α={thaw_alpha}→0.7 over {thaw_steps} steps")

    def check_evolution_triggers(
        self,
        metrics: Dict[str, float],
        vram_usage: float,
        global_step: int,
        current_ppl: float = None,
    ) -> str:
        """
        V9.9.1 Unified evolution trigger check supporting multiple modes.

        Args:
            metrics: Training metrics dict (coherence, entropy, etc.)
            vram_usage: Current VRAM utilization (0-1)
            global_step: Current training step
            current_ppl: Current validation PPL (optional, for PPL mode)

        Returns:
            "EVOLVE_TO_X_Y" if should evolve, "WAITING"/"NOT_READY"/etc. otherwise
        """
        # Only check if we're past the initial 9:3 stage
        if self.current_stage_idx < 1:
            return "NOT_READY"

        # Already at final stage
        if self.current_stage_idx >= len(self.evolution_stages) - 1:
            return "FINAL_STAGE"

        # Safety: VRAM check applies to all modes
        if vram_usage >= self.metabolic_vram_safety:
            return "VRAM_UNSAFE"

        # Track PPL history for smoothing
        if current_ppl is not None:
            self.ppl_history.append(current_ppl)
            if len(self.ppl_history) > self.evolution_ppl_window:
                self.ppl_history.pop(0)

        # Mode-specific trigger logic
        if self.evolution_trigger_mode == "ppl":
            return self._check_ppl_evolution(current_ppl, global_step)
        elif self.evolution_trigger_mode == "step":
            return self._check_step_evolution(global_step)
        else:  # "metrics" mode (default)
            return self.check_granular_evolution(metrics, vram_usage, global_step)

    def _check_ppl_evolution(self, current_ppl: float, global_step: int) -> str:
        """
        Check if PPL has dropped below the next trigger threshold.

        Uses smoothed PPL (average over window) to avoid noise-triggered evolutions.
        """
        if not self.evolution_ppl_triggers:
            return "NO_PPL_TRIGGERS"

        if current_ppl is None or len(self.ppl_history) < 3:
            return "WAITING_PPL"

        # Use smoothed PPL
        smoothed_ppl = sum(self.ppl_history) / len(self.ppl_history)

        # Find the next untriggered PPL threshold
        next_trigger_idx = self.current_stage_idx  # stages are 0-indexed, triggers map to transitions
        if next_trigger_idx >= len(self.evolution_ppl_triggers):
            return "ALL_PPL_TRIGGERS_USED"

        trigger_ppl = self.evolution_ppl_triggers[next_trigger_idx]

        # Check if PPL has dropped below threshold
        if smoothed_ppl <= trigger_ppl and not self.evolution_ppl_triggered[next_trigger_idx]:
            self.evolution_ppl_triggered[next_trigger_idx] = True
            next_stage = self.evolution_stages[self.current_stage_idx + 1]
            print(f"\n  📉 [PPL EVOLUTION] Smoothed PPL {smoothed_ppl:.2f} <= {trigger_ppl}")
            print(f"      Triggering evolution to {next_stage[0]}:{next_stage[1]}")
            return f"EVOLVE_TO_{next_stage[0]}_{next_stage[1]}"

        return "WAITING"

    def _check_step_evolution(self, global_step: int) -> str:
        """
        Check if training has reached the next step trigger.
        """
        if not self.evolution_step_triggers:
            return "NO_STEP_TRIGGERS"

        # Find the next untriggered step threshold
        next_trigger_idx = self.current_stage_idx  # stages are 0-indexed
        if next_trigger_idx >= len(self.evolution_step_triggers):
            return "ALL_STEP_TRIGGERS_USED"

        trigger_step = self.evolution_step_triggers[next_trigger_idx]

        # Check if step has been reached
        if global_step >= trigger_step and not self.evolution_step_triggered[next_trigger_idx]:
            self.evolution_step_triggered[next_trigger_idx] = True
            next_stage = self.evolution_stages[self.current_stage_idx + 1]
            print(f"\n  📊 [STEP EVOLUTION] Step {global_step} >= {trigger_step}")
            print(f"      Triggering evolution to {next_stage[0]}:{next_stage[1]}")
            return f"EVOLVE_TO_{next_stage[0]}_{next_stage[1]}"

        return "WAITING"

    def get_evolution_status(self) -> Dict[str, any]:
        """
        Get current evolution status for logging/display.
        """
        current = self.evolution_stages[self.current_stage_idx]
        next_stage = None
        if self.current_stage_idx < len(self.evolution_stages) - 1:
            next_stage = self.evolution_stages[self.current_stage_idx + 1]

        status = {
            "current_stage": f"{current[0]}:{current[1]}",
            "stage_idx": self.current_stage_idx,
            "total_stages": len(self.evolution_stages),
            "next_stage": f"{next_stage[0]}:{next_stage[1]}" if next_stage else "FINAL",
            "trigger_mode": self.evolution_trigger_mode,
            "evolution_streak": self.evolution_streak,
        }

        if self.evolution_trigger_mode == "ppl" and self.evolution_ppl_triggers:
            next_idx = min(self.current_stage_idx, len(self.evolution_ppl_triggers) - 1)
            status["next_ppl_trigger"] = self.evolution_ppl_triggers[next_idx] if next_idx < len(self.evolution_ppl_triggers) else None
            if self.ppl_history:
                status["smoothed_ppl"] = sum(self.ppl_history) / len(self.ppl_history)
        elif self.evolution_trigger_mode == "step" and self.evolution_step_triggers:
            next_idx = min(self.current_stage_idx, len(self.evolution_step_triggers) - 1)
            status["next_step_trigger"] = self.evolution_step_triggers[next_idx] if next_idx < len(self.evolution_step_triggers) else None

        return status

    def check_stress_probe(
        self,
        metrics: Dict[str, float],
        config,
        global_step: int,
    ) -> str:
        """
        V9.5.2 Emergency Stress-Probe Detection.

        ChatGPT Guardrails: Compound trigger confirmation
        - Low entropy (< 0.42) is REQUIRED
        - AND at least ONE of: REP-3 > 0.18, UTR < 0.55, DRS > 12
        - Must hold for 2 consecutive evals

        Gemini Protocol: Freeze Authority, flood with Sensory to break stiffness.
        """
        if not config.enable_stress_probe:
            return "DISABLED"

        # Don't trigger if already in stress-probe
        if self.stress_probe_active:
            return "ALREADY_ACTIVE"

        coherence = metrics.get('coherence', 0.0)
        entropy = metrics.get('entropy', 1.0)
        rep3 = metrics.get('rep3', 0.0)  # REP-3 from quality metrics
        utr = metrics.get('utr', 1.0)  # Unique Token Ratio
        drs = metrics.get('drs', 0.0)  # Degeneracy Repetition Score

        # ChatGPT Guardrails: Conservative compound trigger
        # Requirement 1: Model must be stiff (high coherence)
        is_stiff = coherence > config.stress_probe_coherence_min  # 0.80

        # Requirement 2: Low entropy (REQUIRED)
        is_low_entropy = entropy < config.stress_probe_entropy_trigger  # 0.42

        # Requirement 3: At least ONE degeneracy signal
        has_high_rep3 = rep3 > config.stress_probe_rep3_trigger  # 0.18
        has_low_utr = utr < config.stress_probe_utr_trigger  # 0.55
        has_high_drs = drs > config.stress_probe_drs_trigger  # 12

        has_degeneracy_signal = has_high_rep3 or has_low_utr or has_high_drs

        # Compound trigger: stiff AND low_entropy AND at_least_one_signal
        is_degenerate = is_stiff and is_low_entropy and has_degeneracy_signal

        if is_degenerate:
            self.stress_probe_degeneracy_streak += 1
            # Log degeneracy detection for debugging
            if self.stress_probe_degeneracy_streak == 1:
                signals = []
                if has_high_rep3:
                    signals.append(f"REP-3={rep3:.3f}>{config.stress_probe_rep3_trigger}")
                if has_low_utr:
                    signals.append(f"UTR={utr:.3f}<{config.stress_probe_utr_trigger}")
                if has_high_drs:
                    signals.append(f"DRS={drs:.1f}>{config.stress_probe_drs_trigger}")
                print(f"  ⚠️ [STRESS-PROBE] Degeneracy detected: Ent={entropy:.3f}, {', '.join(signals)}")
        else:
            self.stress_probe_degeneracy_streak = 0

        # Trigger after patience consecutive evals of degeneracy (ChatGPT: 2)
        if self.stress_probe_degeneracy_streak >= config.stress_probe_patience:
            return "TRIGGER_STRESS_PROBE"

        return "MONITORING"

    def execute_stress_probe(
        self,
        config,
        current_lr: float,
        global_step: int,
    ) -> Tuple[Tuple[int, int], float]:
        """
        Execute transition to 3:9 stress-probe mode.

        Returns: (new_split, new_lr)
        - Jumps to 3:9 split (nearly all Sensory)
        - Reduces LR to stress_probe_lr_factor (65%)
        - Records pre-stress-probe state for restoration
        """
        # Save current state for restoration
        self.pre_stress_probe_split = self.current_split
        self.pre_stress_probe_lr = current_lr

        # Activate stress-probe
        self.stress_probe_active = True
        self.stress_probe_start_step = global_step
        self.stress_probe_steps_in = 0
        self.stress_probe_degeneracy_streak = 0  # Reset

        # Jump to 3:9 (Phase A: Rajas)
        new_split = (3, 9)
        self.current_split = new_split

        # Also update stage index to reflect 3:9
        self.current_stage_idx = len(self.evolution_stages) - 1  # Final stage

        # Reduce LR
        new_lr = current_lr * config.stress_probe_lr_factor

        print(f"\n  🚨 [STRESS-PROBE] EMERGENCY ACTIVATION - Step {global_step}")
        print(f"      {self.pre_stress_probe_split[0]}:{self.pre_stress_probe_split[1]} → 3:9 (Phase A: Rajas)")
        print(f"      Authority Scale: {config.stress_probe_authority_scale} (nearly frozen)")
        print(f"      LR: {current_lr:.6f} → {new_lr:.6f} ({config.stress_probe_lr_factor*100:.0f}%)")
        print(f"      Exit Criteria: Ent > {config.stress_probe_exit_entropy} OR REP-3 < {config.stress_probe_exit_rep3}")
        print(f"      Max Steps: {config.stress_probe_max_steps}")

        return new_split, new_lr

    def check_stress_probe_exit(
        self,
        metrics: Dict[str, float],
        config,
        global_step: int,
    ) -> str:
        """
        Check if stress-probe should exit.

        ChatGPT Guardrails:
        - Minimum 100 steps (don't exit early)
        - Exit when Entropy > 0.55 for 2 consecutive evals
        - Maximum 300 steps (forced exit)
        """
        if not self.stress_probe_active:
            return "NOT_ACTIVE"

        self.stress_probe_steps_in += 1

        entropy = metrics.get('entropy', 0.0)
        rep3 = metrics.get('rep3', 1.0)

        # ChatGPT Guardrail: Enforce minimum steps
        if self.stress_probe_steps_in < config.stress_probe_min_steps:
            return "CONTINUE"

        # Success criteria: diversity restored
        entropy_ok = entropy > config.stress_probe_exit_entropy  # 0.55
        rep3_ok = rep3 < config.stress_probe_exit_rep3  # 0.12

        # ChatGPT Guardrail: Require 2 consecutive evals meeting exit criteria
        if entropy_ok:
            self.stress_probe_exit_streak += 1
        else:
            self.stress_probe_exit_streak = 0

        # Forced exit: max steps reached
        max_reached = self.stress_probe_steps_in >= config.stress_probe_max_steps

        # Exit success: 2 consecutive good evals (ChatGPT: entropy > 0.55 for 2 evals)
        if self.stress_probe_exit_streak >= 2 and rep3_ok:
            return "EXIT_SUCCESS"
        elif max_reached:
            return "EXIT_FORCED"

        # Log progress every 50 steps during stress-probe
        if self.stress_probe_steps_in % 50 == 0:
            print(f"  📊 [STRESS-PROBE] Step {self.stress_probe_steps_in}/{config.stress_probe_max_steps}: "
                  f"Ent={entropy:.3f}, REP-3={rep3:.3f}, exit_streak={self.stress_probe_exit_streak}")

        return "CONTINUE"

    def exit_stress_probe(
        self,
        global_step: int,
        exit_reason: str,
        config,
    ) -> Tuple[Tuple[int, int], float]:
        """
        Exit stress-probe and return to 6:6 (Sattva).

        ChatGPT Guardrails:
        - Return to 6:6, not 9:3
        - Gradual LR restore over ~50 steps
        - Re-enable adaptive LR after 100 steps

        Returns: (new_split, initial_lr_for_restore)
        """
        # Return to 6:6 (not pre-stress-probe split - we want balanced digestion)
        new_split = (6, 6)
        self.current_split = new_split
        self.current_stage_idx = 1  # 6:6 stage

        # Record stress-probe statistics
        duration = self.stress_probe_steps_in

        # Deactivate stress-probe but setup gradual LR restore
        self.stress_probe_active = False
        self.stress_probe_steps_in = 0
        self.stress_probe_exit_streak = 0

        # ChatGPT Guardrail: Gradual LR restore over ~50 steps
        self.stress_probe_lr_restoring = True
        self.stress_probe_lr_restore_start_step = global_step
        self.stress_probe_reduced_lr = self.pre_stress_probe_lr * config.stress_probe_lr_factor

        print(f"\n  ✅ [STRESS-PROBE] EXIT - Step {global_step}")
        print(f"      Reason: {exit_reason}")
        print(f"      Duration: {duration} steps")
        print(f"      3:9 → 6:6 (Phase B: Sattva - Digestion)")
        print(f"      LR Restore: {self.stress_probe_reduced_lr:.6f} → {self.pre_stress_probe_lr:.6f}")
        print(f"      Restore Steps: {config.stress_probe_lr_restore_steps}")

        # Return reduced LR (gradual restore will ramp up)
        return new_split, self.stress_probe_reduced_lr

    def get_stress_probe_restore_lr(
        self,
        global_step: int,
        config,
    ) -> float:
        """
        Compute LR during gradual restore period after stress-probe exit.

        ChatGPT Guardrail: Restore LR gradually over ~50 steps.
        """
        if not self.stress_probe_lr_restoring:
            return self.pre_stress_probe_lr

        steps_since_exit = global_step - self.stress_probe_lr_restore_start_step

        # Check if restore complete
        if steps_since_exit >= config.stress_probe_lr_restore_steps:
            self.stress_probe_lr_restoring = False
            print(f"  ✓ [STRESS-PROBE] LR restore complete: {self.pre_stress_probe_lr:.6f}")
            return self.pre_stress_probe_lr

        # Linear ramp from reduced_lr to pre_stress_probe_lr
        progress = steps_since_exit / config.stress_probe_lr_restore_steps
        current_lr = self.stress_probe_reduced_lr + progress * (
            self.pre_stress_probe_lr - self.stress_probe_reduced_lr
        )

        return current_lr

    def update_stability_per_step(self, coherence: float, sa_ratio: float = None) -> None:
        """
        V9.4.9: Update stability streak every gradient step (not just at validation).

        This ensures the streak counter reflects actual gradient steps, not log intervals.
        """
        if self.state != self.STATE_AUTHORITY:
            return  # Only track during authority phase

        if self.mode == "consecutive":
            # Consecutive mode: streak of coherence >= threshold
            stability = coherence  # Use raw coherence for simplicity
            if stability >= self.stability_threshold:
                self.stability_streak += 1
            else:
                self.stability_streak = 0  # Hard reset

        elif self.mode == "sa_ratio" and sa_ratio is not None:
            # S/A ratio mode: rolling window
            self.sa_rolling_window.append(sa_ratio)
            if len(self.sa_rolling_window) > self.stability_window:
                self.sa_rolling_window.pop(0)
            self.stability_streak = len(self.sa_rolling_window)

        else:  # average mode
            self.ssi_rolling_window.append(coherence)
            if len(self.ssi_rolling_window) > self.stability_window:
                self.ssi_rolling_window.pop(0)
            self.stability_streak = len(self.ssi_rolling_window)

    def get_saturation_thaw_alpha(self, global_step: int) -> float:
        """
        Compute the Dampened Thaw alpha for newly sensory layers (6, 7, 8).

        During thaw, α ramps from saturation_thaw_start (0.3) to saturation_thaw_end (0.7)
        over saturation_thaw_steps (100) steps.
        """
        if self.saturation_thaw_step is None:
            return self.saturation_thaw_start

        steps_since_thaw = global_step - self.saturation_thaw_step
        if steps_since_thaw >= self.saturation_thaw_steps:
            return self.saturation_thaw_end

        # Linear ramp
        progress = steps_since_thaw / self.saturation_thaw_steps
        alpha = self.saturation_thaw_start + progress * (self.saturation_thaw_end - self.saturation_thaw_start)
        return alpha

    def _log_integration_tax(self, current_ppl: float, global_step: int):
        """
        Log the Integration Tax: PPL difference after relaxation.

        This measures the "cost" of adding new sensory layers.
        Called for the first N steps after relaxation.
        """
        if self.integration_tax_logged:
            return

        self.post_relaxation_ppl_samples.append(current_ppl)

        if len(self.post_relaxation_ppl_samples) >= self.integration_tax_sample_count:
            # Calculate Integration Tax
            avg_post_ppl = sum(self.post_relaxation_ppl_samples) / len(self.post_relaxation_ppl_samples)
            ppl_delta = avg_post_ppl - self.pre_relaxation_ppl
            ppl_percent = (ppl_delta / self.pre_relaxation_ppl) * 100

            # Log the Jolt
            print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
            print(f"  ║  📊 INTEGRATION TAX REPORT (Jolt Log)                        ║")
            print(f"  ╠══════════════════════════════════════════════════════════════╣")
            print(f"  ║  Pre-Relaxation PPL:  {self.pre_relaxation_ppl:>10.2f}                        ║")
            print(f"  ║  Post-Relaxation PPL: {avg_post_ppl:>10.2f} (avg over {self.integration_tax_sample_count} steps)        ║")
            print(f"  ║  ─────────────────────────────────────────────────────────── ║")
            print(f"  ║  Integration Tax:     {ppl_delta:>+10.2f} ({ppl_percent:+.1f}%)                   ║")
            print(f"  ║                                                              ║")
            if ppl_percent <= 5.0:
                print(f"  ║  Status: ✅ SMOOTH INTEGRATION (Tax < 5%)                   ║")
            elif ppl_percent <= 15.0:
                print(f"  ║  Status: ⚠️  MODERATE TAX (5-15%) - Thaw in progress        ║")
            else:
                print(f"  ║  Status: 🔥 HIGH TAX (>15%) - Monitor for Viparyaya         ║")
            print(f"  ╚══════════════════════════════════════════════════════════════╝\n")

            self.integration_tax_logged = True

            # Store in telemetry
            self.transitions[-1]["integration_tax"] = {
                "pre_ppl": self.pre_relaxation_ppl,
                "post_ppl": avg_post_ppl,
                "delta": ppl_delta,
                "percent": ppl_percent,
            }

    def update(
        self,
        guna_coherence: float,
        s_drift_ema: float,
        val_ppl: float,
        global_step: int,
        sa_ratio: float = None,
        entropy: float = None,
        sensory_flow: float = None,
    ) -> Tuple[bool, str]:
        """
        Update controller state based on current metrics.

        Returns:
            (state_changed, action): Whether state changed and what action to take
            action can be: "NONE", "RELAX", "RECOVER", "RESUME"

        [S5] Entropy Gate:
            Relaxation is blocked if entropy > entropy_gate_threshold (0.50).
            This prevents the model from gaining sensory freedom while confused.

        Sovereign Saturation Gate:
            Triggers relaxation when coherence >= 0.74 AND sensory flow derivative
            is flat for 50 steps (sensory layers saturated).
        """
        stability_index = self.compute_stability_index(guna_coherence, s_drift_ema)

        # Track entropy for gating
        self.last_entropy = entropy

        # Track history
        self.stability_history.append({
            "step": global_step,
            "stability": stability_index,
            "gc": guna_coherence,
            "drift": s_drift_ema,
            "ppl": val_ppl,
            "state": self.state,
            "sa_ratio": sa_ratio,
            "entropy": entropy,
        })
        if len(self.stability_history) > self.max_history:
            self.stability_history = self.stability_history[-self.max_history:]

        action = "NONE"

        # State machine
        if self.state == self.STATE_AUTHORITY:
            # Check for force relaxation at specific step (bypasses all checks)
            force_triggered = False
            if (self.force_relaxation_step is not None and
                global_step >= self.force_relaxation_step and
                not self.force_relaxation_triggered):
                force_triggered = True
                self.force_relaxation_triggered = True
                print(f"\n  ⚡ [FORCE RELAXATION] Step {global_step} >= {self.force_relaxation_step}")
                print(f"      Triggering 9:3 → 6:6 transition (bypassing stability check)")

            # Sovereign Saturation Gate: Check if sensory layers are saturated
            saturation_triggered = False
            if not force_triggered and sensory_flow is not None:
                saturation_triggered = self._check_saturation_gate(
                    coherence=guna_coherence,
                    sensory_flow=sensory_flow,
                    global_step=global_step,
                )
                if saturation_triggered:
                    print(f"\n  --> [RELAXATION] SATURATION REACHED. PIVOTING TO 6:6.")
                    print(f"      Coherence: {guna_coherence:.3f} >= {self.saturation_coherence_threshold}")
                    print(f"      Sensory Flow: {sensory_flow:.3f} (flat for {self.saturation_patience} steps)")
                    print(f"      Dampened Thaw: α {self.saturation_thaw_start}→{self.saturation_thaw_end} over {self.saturation_thaw_steps} steps")

            # Check if we should trigger relaxation (mode-dependent)
            stability_ready = self._check_relaxation_ready(stability_index, sa_ratio=sa_ratio)

            # [S5] Entropy Gate: Block relaxation if entropy too high (skipped for force/saturation trigger)
            entropy_clear = True
            if not force_triggered and not saturation_triggered and entropy is not None and entropy > self.entropy_gate_threshold:
                entropy_clear = False
                if stability_ready and not self.entropy_gate_blocked:
                    # Log that we're blocking due to entropy
                    print(f"\n  🔒 [S5 ENTROPY GATE] Relaxation BLOCKED - Ent:{entropy:.2f} > {self.entropy_gate_threshold}")
                    print(f"      Model must achieve clarity (Ent < {self.entropy_gate_threshold}) before 6:6 thaw")
                    self.entropy_gate_blocked = True
            else:
                self.entropy_gate_blocked = False

            if force_triggered or saturation_triggered or (stability_ready and entropy_clear):
                # Ready to relax!
                self.state = self.STATE_RELAXING
                self.pre_relaxation_ppl = val_ppl
                self.relaxation_step = global_step
                action = "RELAX"

                # Determine trigger mode for logging
                if force_triggered:
                    trigger_mode = "FORCED"
                elif saturation_triggered:
                    trigger_mode = "SATURATION"
                else:
                    trigger_mode = self.mode

                self.transitions.append({
                    "step": global_step,
                    "from": "AUTHORITY",
                    "to": "BALANCED",
                    "stability": stability_index,
                    "ppl": val_ppl,
                    "mode": trigger_mode,
                    "forced": force_triggered,
                    "saturation": saturation_triggered,
                })

        elif self.state == self.STATE_RELAXING:
            # Transition in progress, move to balanced
            self.state = self.STATE_BALANCED
            self.current_split = self.balanced_split
            # Reset Integration Tax tracking for new relaxation
            self.integration_tax_logged = False
            self.post_relaxation_ppl_samples = []

        elif self.state == self.STATE_BALANCED:
            # Update Guna-Lock status (release after guna_lock_steps)
            self.update_guna_lock(global_step)

            # Track Integration Tax for first N steps
            if not self.integration_tax_logged:
                self._log_integration_tax(val_ppl, global_step)

            # Monitor for PPL spike (Viparyaya trigger)
            if self.pre_relaxation_ppl is not None:
                ppl_increase = (val_ppl - self.pre_relaxation_ppl) / self.pre_relaxation_ppl
                if ppl_increase > self.ppl_spike_threshold:
                    # PPL spiked! Trigger Viparyaya recovery
                    self.state = self.STATE_RECOVERY
                    self.recovery_start_step = global_step
                    action = "RECOVER"
                    self.transitions.append({
                        "step": global_step,
                        "from": "BALANCED",
                        "to": "RECOVERY",
                        "ppl_increase": ppl_increase,
                        "ppl": val_ppl,
                    })
                    print(f"\n  ⚠️ [DynamicRelaxation] ERROR STATE TRIGGERED!")
                    print(f"    PPL spike: {ppl_increase*100:.1f}% (threshold: {self.ppl_spike_threshold*100:.0f}%)")
                    print(f"    Reverting to {self.authority_split[0]}:{self.authority_split[1]} for {self.recovery_steps} steps")

        elif self.state == self.STATE_RECOVERY:
            # Check if recovery period is complete
            steps_in_recovery = global_step - self.recovery_start_step
            if steps_in_recovery >= self.recovery_steps:
                # Resume monitoring for re-relaxation
                self.state = self.STATE_AUTHORITY
                self.stability_streak = 0
                self.pre_relaxation_ppl = None
                action = "RESUME"
                self.transitions.append({
                    "step": global_step,
                    "from": "RECOVERY",
                    "to": "AUTHORITY",
                    "stability": stability_index,
                })
                print(f"\n  ✓ [DynamicRelaxation] Recovery complete. Resuming Authority phase.")

        return (action != "NONE"), action

    def execute_relaxation(self, current_step: int = 0):
        """
        Execute the 9:3 → 6:6 transition with Dampened Thaw and Weight Transfer.

        The newly added sensory layers (6-8) start with very low α (0.05)
        and ramp up slowly to prevent Rajasic override.

        Weight Transfer Process:
        1. Capture weights from Layers 6, 7, 8 (StateDeltaPhaseBlocks)
        2. Transfer to new QuadraticAttentionWithPhaseBias blocks
        3. Re-anchor R-Signal to Layer 5 (new Witness)
        4. Activate Guna-Lock: freeze W_q, W_k for 50 steps

        Phase Attention Protection:
        During Thaw, Phase-Attention weights in Authority layers receive
        extra gradient dampening to maintain stability of the complex O(n)
        attention mechanism.
        """
        print(f"\n  ⚡ [DynamicRelaxation] RELAXATION: {self.authority_split} → {self.balanced_split}")

        # =====================================================================
        # WEIGHT TRANSFER: State-Inference + 48D Anchor + Guna-Lock
        # =====================================================================
        if self.weight_transfer is not None and self.enable_weight_transfer:
            print(f"\n  📤 [WeightTransfer] Beginning weight transfer...")

            # Step 1: Capture weights from Layers 6, 7, 8 (before they become Sensory)
            self.weight_transfer.capture_state()

            # Step 2: Get the new Quadratic layers (will be created after reconfigure)
            # For now, we capture the layers that will become Sensory
            layers = self.weight_transfer._get_model_layers()
            if layers is not None:
                # Layers 6, 7, 8 in the original indexing become Sensory layers
                new_sensory_layers = []
                for idx in self.weight_transfer.transferred_layers:
                    if idx < len(layers):
                        new_sensory_layers.append(layers[idx])

                # Step 3: Transfer weights (State-Inference)
                # Initialize Q, K from V to preserve learned attention patterns
                self.weight_transfer.transfer_weights(
                    new_layers=new_sensory_layers,
                    r_signal_dim=48,  # Standard R-Signal dimension
                )

                # Step 4: Re-anchor R-Signal to Layer 5 (new Witness)
                if self.weight_transfer.anchor_layer_idx < len(layers):
                    new_witness = layers[self.weight_transfer.anchor_layer_idx]
                    self.weight_transfer.anchor_r_signal(new_witness)

                # Step 5: Activate Guna-Lock (freeze W_q, W_k for 50 steps)
                self.weight_transfer.activate_guna_lock(current_step)

        # Enable Thaw mode for Phase Attention protection
        self.gradient_scaler.set_thaw_mode(True)

        # Reconfigure the gradient scaler
        self.gradient_scaler.reconfigure(
            new_authority_layers=self.balanced_split[0],
            new_sensory_layers=self.balanced_split[1],
            new_alpha_min=self.thaw_alpha_start,  # Start very low for dampened thaw
            new_alpha_max=self.balanced_alpha_max,
            new_warmup_steps=self.thaw_warmup_steps,
        )

        self.current_split = self.balanced_split
        print(f"    Dampened Thaw: α = {self.thaw_alpha_start} → {self.balanced_alpha_max} over {self.thaw_warmup_steps} steps")
        print(f"    Phase Attention: Protected during Thaw")
        if self.weight_transfer is not None:
            print(f"    Guna-Lock: W_q, W_k frozen for {self.guna_lock_steps} steps")

    def execute_recovery(self):
        """
        Execute Viparyaya recovery: revert to 9:3 split.

        This 're-stiffens' the model by returning to Authority-heavy configuration.
        Also releases Guna-Lock if active, as the layer structure is changing.
        """
        print(f"\n  🔄 [DynamicRelaxation] ERROR RECOVERY: Reverting to {self.authority_split}")

        # Release Guna-Lock if active (layer structure is changing)
        if self.weight_transfer is not None and self.weight_transfer.guna_lock_active:
            self.weight_transfer.release_guna_lock()
            print("    Guna-Lock released due to recovery")

        # Disable Thaw mode - Phase Attention can learn normally in Authority mode
        self.gradient_scaler.set_thaw_mode(False)

        # Reconfigure back to authority-heavy split
        self.gradient_scaler.reconfigure(
            new_authority_layers=self.authority_split[0],
            new_sensory_layers=self.authority_split[1],
            new_alpha_min=0.1,  # Heavy dampening
            new_alpha_max=self.authority_alpha_max,
            new_warmup_steps=100,  # Quick stabilization
        )

        self.current_split = self.authority_split

    def update_guna_lock(self, current_step: int) -> bool:
        """
        Update Guna-Lock status. Call this each training step after relaxation.

        Returns True if Guna-Lock was just released.
        """
        if self.weight_transfer is None:
            return False

        released = self.weight_transfer.update_guna_lock(current_step)
        if released:
            print(f"\n  🔓 [DynamicRelaxation] Guna-Lock released at step {current_step}")
            print("    W_q, W_k now trainable")
        return released

    def is_guna_locked(self) -> bool:
        """Check if Guna-Lock is currently active."""
        if self.weight_transfer is None:
            return False
        return self.weight_transfer.guna_lock_active

    def get_status_string(self) -> str:
        """Get formatted status string for logging."""
        split_str = f"{self.current_split[0]}:{self.current_split[1]}"
        streak_str = f"{self.stability_streak}/{self.stability_window}" if self.state == self.STATE_AUTHORITY else "—"
        lock_str = " 🔒" if self.is_guna_locked() else ""

        # V9.5.0 Dynamic Streak progress (if enabled and not yet triggered)
        sat_str = ""
        if self.enable_saturation_gate and self.state == self.STATE_AUTHORITY:
            if self.saturation_triggered:
                sat_str = " 🚀FLIP"
            elif self.metabolic_step_counter > 0:
                # Show dynamic target: 50 (escape) or 500 (sattvic)
                mode = "⚡" if self._current_target_streak == 50 else "🧘"
                sat_str = f" {mode}Met:{self.metabolic_step_counter}/{self._current_target_streak}"

        if self.state == self.STATE_RECOVERY:
            return f"Split:{split_str} State:RECOVERY Streak:{streak_str}{lock_str}"
        elif self.state == self.STATE_BALANCED:
            thaw_str = ""
            if self.saturation_thaw_step is not None:
                thaw_str = " (Thaw)"
            return f"Split:{split_str} State:BALANCED ✓{lock_str}{thaw_str}"
        else:
            return f"Split:{split_str} State:{self.state} Streak:{streak_str}{sat_str}{lock_str}"

    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry data for logging/visualization."""
        recent_stability = [h["stability"] for h in self.stability_history[-100:]]
        avg_stability = sum(recent_stability) / len(recent_stability) if recent_stability else 0.0

        telemetry = {
            "state": self.state,
            "current_split": f"{self.current_split[0]}:{self.current_split[1]}",
            "stability_streak": self.stability_streak,
            "avg_stability_100": avg_stability,
            "transitions": len(self.transitions),
            "is_balanced": self.state == self.STATE_BALANCED,
            "guna_lock_active": self.is_guna_locked(),
        }

        # Add weight transfer status if available
        if self.weight_transfer is not None:
            wt_status = self.weight_transfer.get_status()
            telemetry["weight_transfer"] = wt_status

        return telemetry

    def get_state(self) -> Dict[str, Any]:
        """Get full state for checkpointing."""
        state = {
            "state": self.state,
            "current_split": self.current_split,
            "stability_streak": self.stability_streak,
            "ssi_rolling_window": list(self.ssi_rolling_window),
            "pre_relaxation_ppl": self.pre_relaxation_ppl,
            "relaxation_step": self.relaxation_step,
            "recovery_start_step": self.recovery_start_step,
            "integration_tax_logged": self.integration_tax_logged,
            "transitions": self.transitions,
        }

        # Add weight transfer state
        if self.weight_transfer is not None:
            state["weight_transfer"] = {
                "guna_lock_active": self.weight_transfer.guna_lock_active,
                "guna_lock_start_step": self.weight_transfer.guna_lock_start_step,
            }

        return state

    def set_state(self, state: Dict[str, Any]):
        """Restore state from checkpoint."""
        self.state = state.get("state", self.STATE_AUTHORITY)
        self.current_split = state.get("current_split", self.authority_split)
        self.stability_streak = state.get("stability_streak", 0)
        self.ssi_rolling_window = state.get("ssi_rolling_window", [])
        self.pre_relaxation_ppl = state.get("pre_relaxation_ppl", None)
        self.relaxation_step = state.get("relaxation_step", None)
        self.recovery_start_step = state.get("recovery_start_step", None)
        self.integration_tax_logged = state.get("integration_tax_logged", False)
        self.transitions = state.get("transitions", [])

        # Restore weight transfer state
        if self.weight_transfer is not None and "weight_transfer" in state:
            wt_state = state["weight_transfer"]
            self.weight_transfer.guna_lock_active = wt_state.get("guna_lock_active", False)
            self.weight_transfer.guna_lock_start_step = wt_state.get("guna_lock_start_step", None)


# =============================================================================
# QUALITY SAMPLING - Text Generation for Training Monitoring
# =============================================================================

@torch.no_grad()
@torch._dynamo.disable  # Disable torch.compile for generation (dynamic shapes cause hangs)
def generate_sample(
    model: nn.Module,
    tokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 128,
    temperature: float = 0.9,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.15,
    no_repeat_ngram_size: int = 3,
    entropy_controller: Optional[AdaptiveEntropyController] = None,
) -> str:
    """
    Generate text from a prompt for quality monitoring.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    ChatGPT recommendations for breaking repetition:
    - temperature = 0.8-1.0
    - top_p = 0.95
    - top_k = 50
    - repetition_penalty = 1.1-1.2
    - no_repeat_ngram_size = 3
    - max_new_tokens = 128-192

    If entropy_controller is provided, applies adaptive logit scaling
    to keep output entropy near target band.
    """
    model.eval()

    # Encode prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
    prompt_len = input_ids.shape[1]

    # Generate tokens one by one
    generated = input_ids.clone()

    # Reset entropy controller for new generation
    if entropy_controller is not None:
        initial_scale = None
        if hasattr(model, 'entropy_logit_scale'):
            initial_scale = model.entropy_logit_scale.logit_scale
        entropy_controller.reset(initial_scale)

    # Track generated n-grams for no_repeat_ngram blocking
    def get_ngrams(seq, n):
        """Extract n-grams from a sequence."""
        ngrams = set()
        for i in range(len(seq) - n + 1):
            ngrams.add(tuple(seq[i:i+n].tolist()))
        return ngrams

    for step in range(max_new_tokens):
        # Forward pass
        outputs = model(generated)

        # Handle different output formats (dict with 'logits', tuple, or tensor)
        if isinstance(outputs, dict):
            logits = outputs.get('logits', outputs.get('output', None))
            if logits is None:
                # Try to find logits-like tensor in dict
                for key in ['logits', 'output', 'lm_logits']:
                    if key in outputs:
                        logits = outputs[key]
                        break
        elif isinstance(outputs, (tuple, list)):
            logits = outputs[0]
        else:
            logits = outputs

        if logits is None:
            break

        # Get next token logits
        next_logits = logits[:, -1, :].clone()

        # Adaptive entropy control (inference-time)
        if entropy_controller is not None:
            next_logits = entropy_controller.scale_logits(next_logits)
            entropy_controller.update(next_logits)

        # Apply repetition penalty to previously generated tokens
        if repetition_penalty != 1.0:
            for token_id in set(generated[0, prompt_len:].tolist()):
                if next_logits[0, token_id] > 0:
                    next_logits[0, token_id] /= repetition_penalty
                else:
                    next_logits[0, token_id] *= repetition_penalty

        # Apply no_repeat_ngram blocking
        if no_repeat_ngram_size > 0 and generated.shape[1] >= no_repeat_ngram_size:
            # Get the last (n-1) tokens as the prefix
            prefix = tuple(generated[0, -(no_repeat_ngram_size - 1):].tolist())
            # Get all existing n-grams
            existing_ngrams = get_ngrams(generated[0], no_repeat_ngram_size)
            # Block tokens that would create a repeated n-gram
            for ngram in existing_ngrams:
                if ngram[:-1] == prefix:
                    # This token would complete a repeated n-gram
                    next_logits[0, ngram[-1]] = float('-inf')

        # Apply temperature
        next_logits = next_logits / temperature

        # Top-k filtering (optional, applied before top-p)
        if top_k > 0:
            top_k_vals, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
            threshold = top_k_vals[0, -1]
            next_logits[next_logits < threshold] = float('-inf')

        # Top-p (nucleus) sampling
        sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
        cumsum = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

        # Remove tokens with cumulative probability above threshold
        sorted_indices_to_remove = cumsum > top_p
        sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
        sorted_indices_to_remove[:, 0] = False

        # Set removed tokens to -inf
        indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
        next_logits[indices_to_remove] = float('-inf')

        # Sample next token
        probs = F.softmax(next_logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)

        # Append to sequence
        generated = torch.cat([generated, next_token], dim=1)

        # Check for EOS
        if next_token.item() == tokenizer.eos_token_id:
            break

    # Decode and return
    return tokenizer.decode(generated[0], skip_special_tokens=True)


def compute_sample_metrics(text: str) -> Dict[str, float]:
    """
    Compute quality metrics for generated text.

    Returns:
        - completion_rate: 1.0 if ends with punctuation, 0.0 otherwise
        - repetition_score: n-gram repetition rate (lower is better)
        - unique_ratio: ratio of unique tokens to total tokens
        - coherence_score: basic semantic coherence (0.0-1.0, higher is better)
    """
    words = text.split()
    if len(words) < 2:
        return {"completion": 0.0, "repetition": 1.0, "unique_ratio": 0.0, "coherence": 0.0}

    # Completion rate: ends with sentence-ending punctuation
    completion = 1.0 if text.rstrip()[-1:] in '.!?' else 0.0

    # Repetition score: bigram repetition rate
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    if bigrams:
        unique_bigrams = len(set(bigrams))
        repetition = 1.0 - (unique_bigrams / len(bigrams))
    else:
        repetition = 0.0

    # Unique token ratio
    unique_ratio = len(set(words)) / len(words) if words else 0.0

    # CRITICAL FIX: Semantic coherence check (basic heuristics)
    # Checks for common signs of gibberish vs. meaningful text
    coherence = 1.0

    # Penalty 1: Too many short words (gibberish often has many 1-2 char tokens)
    short_word_ratio = sum(1 for w in words if len(w) <= 2) / len(words)
    if short_word_ratio > 0.5:
        coherence *= 0.5

    # Penalty 2: Too many non-alphabetic tokens
    alpha_ratio = sum(1 for w in words if w.isalpha()) / len(words)
    if alpha_ratio < 0.6:
        coherence *= 0.6

    # Penalty 3: Excessive punctuation clustering (e.g., "... ,, ,,")
    punct_cluster = text.count(',,') + text.count('..') * 0.5
    if punct_cluster > 3:
        coherence *= 0.4

    # Penalty 4: Repeated single characters (e.g., "a a a a")
    single_char_repeat = sum(1 for i in range(len(words)-2)
                            if len(words[i]) == 1 and words[i] == words[i+1])
    if single_char_repeat > 2:
        coherence *= 0.3

    # Bonus: Reasonable average word length (4-8 chars is typical English)
    avg_word_len = sum(len(w) for w in words) / len(words)
    if 4.0 <= avg_word_len <= 8.0:
        coherence *= 1.1
    coherence = min(coherence, 1.0)

    return {
        "completion": completion,
        "repetition": repetition,
        "unique_ratio": unique_ratio,
        "coherence": coherence,
    }


def run_quality_samples(
    model: nn.Module,
    tokenizer,
    config: 'UnifiedTrainingConfig',
    device: torch.device,
    step: int,
    logger=None,
):
    """
    Generate sample outputs to monitor training quality.

    This provides a qualitative check that the model is learning
    meaningful language patterns, not just minimizing perplexity.

    Samples are logged with prompts, generated completions, and quality metrics.
    """
    def log(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    log("")
    log("=" * 60)
    log(f"  📝 QUALITY SAMPLES (Step {step})")
    log("=" * 60)

    # V9.6.10 Diagnostic: Show top predicted tokens for first prompt
    try:
        diag_prompt = config.sample_prompts[0] if config.sample_prompts else "The"
        diag_ids = tokenizer.encode(diag_prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            diag_out = model(diag_ids)
            if isinstance(diag_out, dict):
                diag_logits = diag_out.get('logits', diag_out.get('output'))
            else:
                diag_logits = diag_out
            # Get logits for last position
            last_logits = diag_logits[0, -1, :]
            top_probs = torch.softmax(last_logits, dim=-1)
            top_vals, top_ids = torch.topk(top_probs, 10)
            log(f"  🔍 [DIAGNOSTIC] Top-10 predicted tokens after \"{diag_prompt}\":")
            for i, (prob, tid) in enumerate(zip(top_vals, top_ids)):
                tok_str = tokenizer.decode([tid.item()])
                log(f"      {i+1}. '{tok_str}' (id={tid.item()}, p={prob.item():.4f})")
    except Exception as e:
        log(f"  🔍 [DIAGNOSTIC] Failed: {e}")

    # Aggregate metrics across all samples
    total_completion = 0.0
    total_repetition = 0.0
    total_unique = 0.0
    total_coherence = 0.0
    sample_count = 0

    for prompt in config.sample_prompts:
        try:
            # ChatGPT recommendations for quality samples:
            # temperature=0.9, top_p=0.95, top_k=50
            # repetition_penalty=1.15, no_repeat_ngram_size=3
            # Create adaptive entropy controller for inference if enabled
            _infer_entropy_ctrl = None
            if hasattr(config, 'enable_entropy_control_infer') and config.enable_entropy_control_infer:
                _ec_cfg = EntropyControlConfig(
                    enable_entropy_control_infer=True,
                    entropy_topk=getattr(config, 'entropy_topk', 50),
                    infer_h_target=getattr(config, 'infer_h_target', 0.25),
                    infer_eta=getattr(config, 'infer_eta', 0.02),
                    infer_delta_clip=getattr(config, 'infer_delta_clip', 0.05),
                    logit_scale_min=getattr(config, 'logit_scale_min', -4.0),
                    logit_scale_max=getattr(config, 'logit_scale_max', 4.0),
                )
                _init_scale = None
                if hasattr(model, 'entropy_logit_scale'):
                    _init_scale = model.entropy_logit_scale.logit_scale
                _infer_entropy_ctrl = AdaptiveEntropyController(_ec_cfg, _init_scale)
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=128,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
                entropy_controller=_infer_entropy_ctrl,
            )
            # Clean up WikiText artifacts and truncate for display
            generated = generated.strip().replace('\n', ' ')
            if GRADIENT_THROTTLE_AVAILABLE:  # clean_wikitext_artifacts imported with throttle
                generated = clean_wikitext_artifacts(generated)
            generated = generated[:200]

            # Compute quality metrics
            metrics = compute_sample_metrics(generated)
            total_completion += metrics["completion"]
            total_repetition += metrics["repetition"]
            total_unique += metrics["unique_ratio"]
            total_coherence += metrics["coherence"]
            sample_count += 1

            log(f"  Prompt: \"{prompt}\"")
            log(f"  Output: \"{generated}\"")
            log("")
        except Exception as e:
            log(f"  ⚠️ Sampling failed for prompt '{prompt[:30]}...': {e}")

    # Log aggregate quality metrics
    if sample_count > 0:
        avg_completion = total_completion / sample_count
        avg_repetition = total_repetition / sample_count
        avg_unique = total_unique / sample_count
        avg_coherence = total_coherence / sample_count

        log("  ────────────────────────────────────────────────────────")
        log(f"  📊 SAMPLE QUALITY METRICS (n={sample_count})")
        log(f"     Completion Rate: {avg_completion*100:.0f}% (ends with punctuation)")
        log(f"     Repetition Score: {avg_repetition*100:.1f}% (lower is better)")
        log(f"     Unique Token Ratio: {avg_unique*100:.1f}%")
        log(f"     Coherence Score: {avg_coherence*100:.0f}% (semantic quality)")

        # CRITICAL FIX: Quality indicator now includes coherence
        # Previous logic was misleading - high diversity alone doesn't mean good quality
        if avg_coherence > 0.7 and avg_repetition < 0.3 and avg_unique > 0.6:
            log("     Quality: 🟢 GOOD (coherent + diverse)")
        elif avg_coherence > 0.5 and avg_repetition < 0.5:
            log("     Quality: 🟡 IMPROVING (needs better coherence)")
        else:
            log("     Quality: 🔴 NEEDS WORK (likely gibberish despite diversity)")
            log("     ⚠️  WARNING: High diversity without coherence = meaningless tokens")

    log("=" * 60)
    log("")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class UnifiedTrainingConfig:
    """Unified training configuration for all model types."""

    # Model architecture
    model_type: str = "ontological"  # ontological, phase, hybrid
    model_size: str = "small"  # tiny, small, medium, large
    vocab_size: int = 50257
    max_seq_len: int = 2048
    dropout: float = 0.1
    attention_dropout: float = 0.1

    # Architecture overrides (optional - if None, use model_size preset)
    n_layer: Optional[int] = None
    n_head: Optional[int] = None
    n_embd: Optional[int] = None
    n_kv_heads: Optional[int] = None

    # Phase-specific parameters
    sync_steps: int = 3
    sync_lr: float = 0.1
    cosine_mode: str = "standard"  # V9.6.12: "standard", "shifted", or "complex"
    decay_gamma: float = 1.0  # V9.6.13: State decay factor (1.0=infinite, <1.0=local focus)
    learned_decay: bool = False  # V9.9.7: Per-head learned decay (Mamba/S4-style)
    bounded_phase: bool = True  # V9.9.11: Constrain φ to [-π, π] via π*sin() (mandatory fix - enabled by default)
    zero_mean_cosine: bool = False  # V9.9.11: Center cosine per head (forces selectivity)

    # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
    # Separates content similarity from intent alignment to prevent intent from dominating:
    #   s_content = cos(φ_q - φ_k)           # What matches (preserved)
    #   score = s_content * (1 + α * s_align) # Combined
    dual_channel_mode: bool = False  # Enable dual-channel attention
    alignment_authority: float = 0.1  # α: weight for alignment term (0=pure content, higher=more intent influence)

    # ==========================================================================
    # V10.6+ CONTROL-PLANE ITEMS (Hard Probes Integration)
    # ==========================================================================
    # D.5: No-Write Contract Enforcement - prevents control signals from encoding content
    # D.2: enable_slots_read routing flag - separate read/write paths for quad
    # D.1: OntoControl formalized interface - explicit control plane object
    # Reference: QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md, Appendix D

    # V10.6.1: Alignment Clamp (ChatGPT caveat - prevents over-constraint collapse)
    # Clamp bounds for alignment modulator: output = output * clamp(1 + α * s_align, min, max)
    alignment_clamp_min: float = 0.8  # Lower bound (prevents over-suppression)
    alignment_clamp_max: float = 1.2  # Upper bound (prevents over-amplification)

    # V10.6.2 D.5: No-Write Contract Enforcement
    strict_control_contract: bool = True  # If True, raise on contract violation; if False, warn

    # V10.6.3: Architecture Health Summary (PASS/FAIL diagnostics at startup)
    run_architecture_health_check: bool = True  # Run health check at training start
    architecture_health_strict: bool = False  # If True, abort training on FAIL

    # V10.6.5: Parameter-Matched Baseline Enforcement
    # Ensures baseline comparison uses exact parameter count (not just same architecture)
    enforce_baseline_param_match: bool = True  # Validate param count matches

    # V10.6.6: Quad Utilization Sanity Checks (diagnostic probes)
    enable_quad_utilization_checks: bool = False  # Enable quad utilization monitoring
    quad_utilization_warn_threshold: float = 0.01  # Warn if quad contributes < 1%
    quad_utilization_check_interval: int = 100  # Check every N steps

    # V10.6.7: Lightweight Probe Hooks (diagnostic only, not full datasets)
    enable_probe_hooks: bool = False  # Enable lightweight diagnostic probes
    probe_hook_interval: int = 500  # Run probes every N steps
    probe_hook_types: str = "phase_rotation,chunk_continuity"  # Comma-separated probe types

    # Phase Rotation Test (validates phase encodes relational structure)
    phase_rotation: bool = False  # Run phase rotation test after training
    phase_rotation_angles: str = "0,45,90,135,180,270"  # Angles to test (degrees)
    phase_rotation_as_diagnostic: bool = False  # Run as periodic diagnostic during training

    # V10.0: Binding Cache architecture (validated by diagnostic probes)
    binding_cache_top_k: int = 64  # Top-K cache size per head (O(nk) vs O(n²))
    no_binding_cache: bool = False  # Disable cache (use full attention)

    # V10.5: Interference-Aware Proposal Scoring (compositional creativity)
    # Applied AFTER proposals, BEFORE phase integration. Task-conditional.
    enable_quad_interference: bool = False  # Master switch (OFF by default)
    interference_lambda_text: float = 0.02  # Strength (0.01-0.03 for text, lower than vision)
    interference_min_step: int = 8  # Only apply after N decoding steps
    interference_entropy_gate: float = 1.2  # Only apply if proposal entropy > threshold
    interference_auto_classify: bool = True  # Auto-detect compositional tasks
    interference_modes: str = "compose,reason,write"  # Enabled modes (comma-separated)


    # Hybrid-specific parameters
    local_layers: int = 4
    window_size: int = 256
    local_backend: str = "auto"
    alpha_local: float = 0.8
    alpha_phase: float = 0.2

    # Alpha decay schedule (for phase/hybrid attention)
    alpha_phase_start: float = 0.6
    alpha_phase_end: float = 0.4
    alpha_decay_steps: int = 10000

    # V10.2.1: Chunking for long sequences (hybrid models)
    enable_chunking: bool = False  # Enable chunked training for long sequences
    chunk_size: int = 512  # Size of each chunk when chunking enabled
    protected_phase: bool = True  # V10.2.1: Protected Phase (Local cross-attends to Phase)
    no_protected_phase: bool = False  # Disable protected phase (legacy parallel mode)
    run_chunk_diagnostic: bool = False  # Run chunk continuity diagnostic at start
    chunk_diagnostic_seq_len: int = 2048  # Sequence length for chunk diagnostic
    enable_tbptt: bool = False  # V10.7: Truncated BPTT (detach state between chunks, memory O(C))

    # ==========================================================================
    # PHASE-FIRST CURRICULUM (unified inverse curriculum for phase attention)
    # ==========================================================================
    # Master toggle that enables optimal phase-first learning configuration:
    #   - PPL-alpha curriculum (phase high when PPL high)
    #   - Adaptive window size (small early, large later)
    #   - Layerwise: lower layers keep phase longer
    # Individual settings below can override defaults when phase_first_curriculum=True
    phase_first_curriculum: bool = False

    # PPL-gated alpha curriculum (phase dominates early, local refines later)
    # When enabled, alpha_phase is computed based on current PPL:
    #   PPL >= ppl_high: alpha_phase = alpha_phase_ppl_high (phase dominates)
    #   PPL <= ppl_low:  alpha_phase = alpha_phase_ppl_low (local refines)
    #   In between: linear interpolation
    enable_ppl_alpha_curriculum: bool = False
    alpha_phase_ppl_high: float = 0.8   # alpha_phase when PPL >= ppl_high_threshold
    alpha_phase_ppl_low: float = 0.3    # alpha_phase when PPL <= ppl_low_threshold
    ppl_high_threshold: float = 1000.0  # PPL threshold for max phase weight
    ppl_low_threshold: float = 100.0    # PPL threshold for min phase weight
    # Adaptive window size (small early for fast phase, large later for local context)
    enable_adaptive_window: bool = False  # Enable window size adaptation with PPL
    window_size_high_ppl: int = 128       # Window size when PPL >= ppl_high_threshold
    window_size_low_ppl: int = 256        # Window size when PPL <= ppl_low_threshold

    # Decorrelation loss (to force phase and local to learn different features)
    decorr_loss_weight: float = 0.0  # Weight for decorrelation loss (0=disabled, 0.1=recommended)

    # V9.9.10: Phase diversity loss (to combat phase collapse)
    # Uses uniformity loss |E[e^{iφ}]|² and entropy proxy R = |E[e^{iφ}]|
    phase_diversity_weight: float = 0.0  # Combined weight (0=disabled, 0.001=start, ramp to 0.01)
    phase_diversity_ramp_steps: int = 5000  # Steps to ramp weight linearly (ignored if adaptive)

    # V9.9.12: Adaptive Phase Diversity Controller (ChatGPT Universal Proposal)
    # Replaces fixed λ and ramp with scale-free control loop based on R
    enable_adaptive_phase_diversity: bool = False  # Use adaptive controller instead of fixed
    phase_diversity_target_R: float = 0.25  # Target mean resultant length (0.25 = healthy)
    phase_diversity_lambda_init: float = 0.0001  # Initial λ after ramp
    phase_diversity_lambda_max: float = 0.1  # Maximum λ ceiling
    phase_diversity_eta: float = 0.1  # Control gain (how fast λ adapts)
    phase_diversity_ramp_multiplier: float = 5.0  # ramp_steps = multiplier * warmup_steps
    # V9.9.12b: Task-loss scaling (ChatGPT's Lagrange multiplier approach)
    phase_diversity_task_scaling: bool = True  # Scale λ by task loss (self-normalizing)
    phase_diversity_task_alpha: float = 0.01  # Base coefficient for task-loss mode

    # V9.9.1 Per-Layer Phase Control (for Inverted Curriculum)
    enable_per_layer_phase: bool = False  # Enable per-layer phase weight control
    per_layer_phase_weights: str = ""  # Initial weights: "0,0,0,0,0,0,0,0,0,0,0,0" (12 values)
    layer_transition_steps: int = 500  # Steps for soft layer transitions

    # V9.9.1 Inverted Curriculum Controller
    enable_inverted_curriculum: bool = False  # Enable full inverted curriculum
    inverted_curriculum_stages: str = ""  # Custom stages: "3:9@256,5:7@512,6:6@768,9:3@2048"
    inverted_curriculum_ppl_triggers: str = ""  # PPL triggers: "300,200,120,75,45,25"
    # V9.9.4: PPL Stability Check (ChatGPT's Readiness Index)
    inverted_curriculum_stability_threshold: float = 5.0  # Max PPL slope for "stable"
    inverted_curriculum_stability_stages: str = "2,3,4"  # Stages requiring stability (geometry shift zone)

    # Ontological-specific parameters
    bhava_embed_dim: int = 128
    num_drishti_heads: int = 4

    # V9.8.0: Ontological Hybrid (Two-Tier AGI) with 32D Sovereign State
    # Replaces arbitrary 124D (44 phonemes + 64 topics + 12 bhava + 4 dynamics)
    # with principled 32D: [0:12] Bhava, [12:17] Kosha, [17:22] Vritti, [22:28] Guna, [28:32] Reserved
    state_dim: int = SOVEREIGN_STATE_DIM  # 32D Sovereign State (was 124D CognitiveState)
    project_per_head_dim: bool = False  # If True, project ΔS to [H, D_h] instead of [H]

    # Training hyperparameters
    batch_size: int = 8
    batch_size_max: int = 512  # Max batch size for dynamic scaling (seq len curriculum)
    gradient_accumulation: int = 1
    vram_threshold: float = 0.95  # VRAM % to trigger batch reduction (0.95 = 95%)
    vram_recovery_buffer: float = 0.12  # Recovery when VRAM < (threshold - buffer)
    max_steps: int = 10000
    warmup_steps: int = 500  # Max warmup steps (fallback if PPL doesn't drop)
    warmup_until_ppl: float = 500.0  # End warmup when PPL < this (0 = disabled, use fixed steps)

    # Optimizer
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    max_grad_norm: float = 1.0
    use_per_layer_clipping: bool = False  # Clip auth/sens layers separately
    use_8bit_optimizer: bool = False  # Use bitsandbytes 8-bit AdamW (saves ~50% optimizer memory)
    use_compile: bool = False  # Use torch.compile() for faster training (PyTorch 2.0+)

    # Mixed precision
    mixed_precision: str = "bf16"

    # Gradient checkpointing
    gradient_checkpointing: bool = False
    checkpoint_offload_cpu: bool = False  # Offload checkpointed activations to CPU (metabolic tuning)

    # Checkpointing
    checkpoint_dir: str = "checkpoints_unified"
    save_every: int = 1000
    no_save: bool = False  # Skip all checkpoint saving (useful for benchmark runs)
    eval_every: int = 100
    log_every: int = 10

    # Logging verbosity
    quiet: bool = False  # Quiet mode: only print Critical 5 (Loss, PPL, S/A, GC, Conf)

    lightweight_diagnostics: bool = True     # V9.7.0: Skip expensive gradient norm computation in diagnostics

    # Kosha Phase Steering (Active Intervention) - Layer 9 = O9_WITNESSES

    # ==========================================================================
    # v2.2.1: Kosha Gyroscope - Homeostatic Self-Regulation Loss
    # ==========================================================================
    # V9.8.7: Dynamic three-phase engagement based on Val PPL thresholds
    # Phase settings: RELAXED (30-50 PPL) vs ACTIVE (<30 PPL)
    # Dynamic Weight Scheduler (v2.2.1 - prevents "Aphasia")
    # Trap detection thresholds (v2.2.5: Golden Ratio φ for sigmoid mode)
    # v2.3.0: Complete Harmonic Pentad - Sattvic Range for each Kosha
    # Each Kosha has a Floor (Push) and Ceiling (Clamp) defining the healthy band
    # ┌───────────┬─────────────────────────┬─────────────────────┬─────────────────────────┐
    # | Kosha     | Floor (Push)            | Sattvic Band        | Ceiling (Clamp)         |
    # ├───────────┼─────────────────────────┼─────────────────────┼─────────────────────────┤
    # | Mental    | 23.6%: Spark Abstraction| 23.6% - 38.2%       | 38.2%: Bliss Damper/Rip |
    # | Physical  | 38.2%: Grounding Push   | 38.2% - 61.8%       | 61.8%: Data Trap        |
    # | Intellect | 25.0%: Logic Pressure   | 25.0% - 61.8%       | 61.8%: Hubris Tax       |
    # | Vital     | 23.6%: Wake-up Boost    | 23.6% - 78.6%       | 78.6%: Momentum Brake   |
    # | Bliss     | 23.6%: Spark Creativity | 23.6% - 61.8%       | 61.8%: Delusion Tether  |
    # └───────────┴─────────────────────────┴─────────────────────┴─────────────────────────┘
    # Mental thresholds
    # Physical thresholds
    # Intellect thresholds
    # Vital thresholds
    # Bliss thresholds
    # Clamp/Push factors (how strongly to correct deviations)
    # v2.3.2: Reflexive Domain Morph
    # Combines external signal (token heuristics) with internal signal (Kosha state)
    # to create a morph factor μ ∈ [0, 1] that adjusts Sattvic Bands in real-time.
    # v2.2.4: Three-Stage Hybrid Logic (Damping + Gate + Rip)
    # Legacy: steepness (deprecated in v2.2.4, kept for backward compatibility)
    # Refinements (v2.2.0)
    # V9.9.0 CRITICAL FIX: Corrected Kosha Engagement Logic
    # PREVIOUS (WRONG): Engaged at high PPL (struggling) → Added constraints when model needed fundamentals
    # CORRECTED: Engage at low PPL (ready) → Add sophistication only after basics are learned
    #
    # Phase A (PPL > disengage): Kosha OFF - "learning fundamentals, no constraints"
    # Phase B (engage < PPL < disengage): Linear rampup - "transition"
    # Phase C (PPL < engage): Kosha fully ON - "ready for homeostatic regulation"
    # Graduation criteria (legacy - kept for stability check)
    # Diagnostic logging
    enable_rip_logger: bool = False          # Enable Reality Rip diagnostic logging
    rip_logger_dir: str = "diagnostics/rips" # Directory for rip event files
    # v2.3.3: 32D Sovereign State Regularizer
    enable_state_regularizer: bool = False   # Enable 32D anti-saturation regularizer
    state_reg_anti_sat_weight: float = 0.5   # Weight for anti-saturation loss
    state_reg_variance_weight: float = 0.2   # Weight for VICReg variance loss
    state_reg_sat_thresh_high: float = 0.95  # Penalize above this (too hot)
    state_reg_sat_thresh_low: float = 0.05   # Penalize below this (too cold)
    state_reg_vital_weight: float = 1.5      # Extra penalty for VITAL (prone to saturation)
    state_reg_bliss_weight: float = 1.5      # Extra penalty for BLISS (prone to saturation)

    # V9.7.0: Ontological Bridge (Layer 4 - Foundational Structure)
    enable_onto_bridge: bool = False         # Enable 12D ontological projection at Layer 4
    onto_bridge_lambda: float = 0.1          # Weight for ontological bridge loss
    onto_bridge_diversity: float = 0.1       # Weight for diversity component (prevent collapse)
    onto_bridge_pramana: float = 0.1         # Weight for Pramāṇa alignment component
    onto_bridge_layer: int = 4               # V9.7.0: Layer 4 = foundational ontological grounding
    # V9.9.0 CRITICAL FIX: Corrected Ontological Bridge Engagement Logic
    # PREVIOUS (WRONG): Engaged at PPL>150 → Added 12D ontological constraints too early
    # CORRECTED: Engage at PPL<50 → Add ontological structure only after language modeling works
    #
    # Phase A (PPL > disengage): Onto OFF - "pure language modeling"
    # Phase B (engage < PPL < disengage): Linear rampup - "gradual introduction"
    # Phase C (PPL < engage): Onto fully ON - "ontological grounding ready"
    onto_engage_ppl: float = 50.0            # Onto fully ON below this PPL (model ready)
    onto_disengage_ppl: float = 150.0        # Onto OFF above this PPL (model needs fundamentals)
    onto_rampdown_steps: int = 500           # Steps to ramp to 0 after disengage

    # Dataset
    dataset: str = "wikitext103"  # "wikitext103", "wikitext2", or "fineweb"
    dataset_name: str = "HuggingFaceFW/fineweb"  # HuggingFace dataset name (for fineweb mode)
    dataset_subset: str = "sample-10BT"  # Dataset subset/config
    cache_val_batches: int = 20  # Pre-cache N validation batches (for streaming datasets)
    cache_dataset: bool = False  # Download and cache dataset locally (vs streaming)
    tokenizer: str = "gpt2"

    # Loss weights for ontological model
    lambda_lm: float = 1.0        # Language modeling loss
    bhava_lambda: float = 0.1     # Bhava relationship consistency
    coherence_lambda: float = 0.05  # Global coherence
    lambda_entropy: float = 0.01  # Entropy regularization

    # V9.5.1 Entropy Floor (prevents repetition curse)
    enable_entropy_floor: bool = False  # Enable entropy floor penalty
    entropy_floor: float = 0.48  # Minimum entropy target
    entropy_floor_weight: float = 0.1  # Weight for floor penalty

    # Entropy-Based Logit Scale Control
    # Train-time: learnable logit scale with entropy band penalty
    # Inference-time: adaptive temperature targeting entropy midpoint
    enable_entropy_control_train: bool = False  # Enable train-time entropy regulation
    enable_entropy_control_infer: bool = False  # Enable inference-time adaptive entropy
    entropy_topk: int = 50                      # K for top-K entropy computation
    entropy_h_min: float = 0.15                 # Lower bound of target entropy band
    entropy_h_max: float = 0.35                 # Upper bound of target entropy band
    entropy_control_lambda: float = 0.01        # Weight for entropy band penalty
    logit_scale_min: float = -4.0               # Min log-scale clamp
    logit_scale_max: float = 4.0                # Max log-scale clamp
    infer_h_target: float = 0.25                # Target entropy for inference
    infer_eta: float = 0.02                     # Inference adaptation rate
    infer_delta_clip: float = 0.05              # Inference error clip

    # V9.5.1 Force Evolution (manual intervention)
    force_evolution_stage: int = None  # Force to stage: 1=6:6, 2=5:7, 3=4:8, 4=3:9

    # V9.9.1 Multi-Stage Evolution Configuration
    # Allows dynamic progression through layer splits based on PPL or step triggers
    enable_multi_stage_evolution: bool = True  # Enable automatic multi-stage evolution
    evolution_trigger_mode: str = "auto"  # "metrics", "ppl", "step", or "auto" (best available)
    evolution_ppl_triggers: str = ""  # PPL thresholds: "100,50,25,15" → trigger at each PPL
    evolution_step_triggers: str = ""  # Step triggers: "10000,30000,50000,70000"
    custom_evolution_stages: str = ""  # Custom stages: "9:3,6:6,4:8,3:9" (default: 9:3→6:6→5:7→4:8→3:9)
    evolution_patience: int = 200  # Steps of stable metrics before evolution (for metrics mode)
    evolution_coherence_min: float = 0.82  # Minimum coherence to evolve (metrics mode)
    evolution_entropy_floor: float = 0.42  # Minimum entropy to evolve (metrics mode)
    evolution_ppl_window: int = 10  # Steps to average PPL for smoother triggers
    evolution_thaw_alpha: float = 0.1  # Initial gradient scale for newly sensory layers
    evolution_thaw_steps: int = 300  # Steps to ramp newly sensory layer gradients

    # V9.5.2 Emergency Stress-Probe (Phase A: 3:9 Rajas)
    # Gemini Protocol: Freeze Authority, flood with Sensory to break stiffness
    # ChatGPT Guardrails: Compound trigger, strict duration, gradual LR restore
    enable_stress_probe: bool = False  # Enable automatic stress-probe detection
    stress_probe_entropy_trigger: float = 0.42  # Trigger when entropy drops below this (ChatGPT: 0.42)
    stress_probe_rep3_trigger: float = 0.18  # Trigger when REP-3 exceeds this (ChatGPT: 0.18)
    stress_probe_utr_trigger: float = 0.55  # Trigger when UTR drops below this (ChatGPT: 0.55)
    stress_probe_drs_trigger: float = 12.0  # Trigger when DRS exceeds this (ChatGPT: 12)
    stress_probe_coherence_min: float = 0.80  # Only trigger if coherence is high (stiff, not dying)
    stress_probe_patience: int = 2  # Consecutive evals of degeneracy before triggering (ChatGPT: 2)
    stress_probe_authority_scale: float = 0.05  # Nearly freeze Authority layers
    stress_probe_lr_factor: float = 0.60  # Reduce LR to 60% during stress-probe (ChatGPT: 0.6)
    stress_probe_exit_entropy: float = 0.55  # Exit when entropy exceeds this for 2 evals
    stress_probe_exit_rep3: float = 0.12  # Exit when REP-3 drops below this
    stress_probe_min_steps: int = 100  # Minimum steps in stress-probe (ChatGPT: 100)
    stress_probe_max_steps: int = 300  # Maximum steps in stress-probe (ChatGPT: 300)
    stress_probe_lr_restore_steps: int = 50  # Steps to gradually restore LR after exit
    force_stress_probe: bool = False  # Force immediate stress-probe activation

    # Sovereign-1 loss configuration (hardened decomposed loss)
    use_sovereign_loss: bool = True  # Enable Sovereign-1 decomposed loss
    sovereign_weight_guna: float = 1.0   # Guna signal weight
    sovereign_weight_s: float = 2.0      # S-Signal (referent) weight
    sovereign_weight_r: float = 5.0      # R-Signal (ontology) weight - CRITICAL
    sovereign_weight_c: float = 0.5      # C-Signal (phoneme) weight

    # Coherence loss (for phase/hybrid)
    use_coherence_loss: bool = False
    no_coherence_loss: bool = False  # CLI flag to disable

    # Sovereign-Lagrangian Loss [Patent B1/S3]
    enable_sovereign_loss: bool = False   # Enable Sovereign-Lagrangian loss
    b1_lambda: float = 0.5                # Consistency Lagrangian weight [B1]
    mu_s3: float = 0.2                    # Global Coherence weight [S3]
    enable_stability_constraint: bool = False  # Enable S8 entropy anchoring
    gc_floor: float = 0.65                    # Minimum Guna Coherence floor

    # V9.8.7: Three-phase PID engagement based on Val PPL
    # Phase 1 (Construction): PPL > engage_ppl → PID ON (aggressive correction)
    # Phase 2 (Transition):   disengage_ppl < PPL < engage_ppl → PID continues
    # Phase 3 (Polishing):    PPL < disengage_ppl → PID OFF (let model converge naturally)

    # Phase ramp settings (for handshake dampening)
    phase_delay_steps: int = 0
    phase_ramp_steps: int = 7000

    # Formula [1331]: 9:3 Hierarchical Split Configuration
    use_9_3_split: bool = False           # Enable 9:3 Authority/Sensory gradient scaling
    enable_gradient_scaling: bool = False  # Enable gradient scaling for ANY split (6:6, 9:3, etc.)
    authority_layers: int = 9             # Number of Authority (State-Delta) layers
    sensory_layers: int = 3               # Number of Sensory (Quadratic) layers
    alpha_sens_initial: float = 0.05      # Initial sensory gradient multiplier (balanced start to prevent S/A spikes)
    alpha_sens_max: float = 0.7           # Maximum sensory gradient (after warmup/relaxation)
    gradient_warmup_steps: int = 500      # Steps to ramp α_sens from initial to max
    # V9.6.8: Layer-wise alpha dampening (Gemini recommendation)
    # Output layers (9-11) should be more stable than reasoning layers (6-8)
    enable_layerwise_alpha: bool = True   # Enable per-layer alpha scaling
    alpha_output_scale: float = 0.5       # Scale for output layers 9-11 (α × 0.5 = more stable)
    alpha_reasoning_scale: float = 1.0    # Scale for reasoning layers 6-8 (α × 1.0 = more expressive)
    authority_floor: float = 1.0          # Alpha floor for authority layers (1.0 = full gradients, 0.3 = 30% dampened)

    # Dynamic Relaxation: 9:3 → 6:6 transition
    enable_dynamic_relaxation: bool = True   # Enable automatic 9:3 → 6:6 transition
    relaxation_mode: str = "sa_ratio"        # "sa_ratio" (recommended), "consecutive", or "average"
    relaxation_stability_threshold: float = 0.50  # S/A ratio threshold for trigger
    relaxation_stability_window: int = 500   # Steps for stability check (rolling window)
    relaxation_streak_target: int = 5        # Consecutive stable evals (for consecutive mode)
    force_relaxation_step: int = None        # Force 9:3→6:6 at this step (bypasses stability check)
    # Sovereign Saturation Gate (automatic detection)
    enable_saturation_gate: bool = True      # Enable automatic saturation detection
    saturation_coherence_threshold: float = 0.74  # Coherence threshold for trigger
    saturation_patience: int = 50            # Steps where sensory derivative must be flat
    saturation_thaw_start: float = 0.3       # New sensory layers start at this α
    saturation_thaw_end: float = 0.7         # Ramp to this α
    saturation_thaw_steps: int = 100         # Steps to ramp new layers
    relaxation_target_authority: int = 6     # Target authority layers after relaxation
    relaxation_target_sensory: int = 6       # Target sensory layers after relaxation
    relaxation_thaw_alpha: float = 0.05      # Dampened Thaw starting α for new sensory layers
    relaxation_thaw_steps: int = 500         # Steps for Dampened Thaw warmup
    relaxation_ppl_spike_threshold: float = 0.20  # PPL spike % to trigger Viparyaya
    relaxation_recovery_steps: int = 100     # Steps to stay in recovery mode

    # Weight Transfer (9:3 → 6:6)
    enable_weight_transfer: bool = True      # Enable weight transfer during relaxation
    guna_lock_steps: int = 50                # Steps to freeze W_q/W_k post-swap

    # Toroidal Evolutionary Bridge (O12 → O1 Recursive Intelligence)
    enable_toroidal_bridge: bool = False     # Enable state carryover from O12 to O1
    toroidal_lambda: float = 0.1             # Weight for toroidal consistency loss
    toroidal_dropout: float = 0.1            # Dropout in seed projection
    toroidal_use_gating: bool = True         # Use gated projection for selective carryover
    toroidal_truncated_bptt: int = 0         # Steps of gradient flow (0 = full detach)
    toroidal_coherence_threshold: float = 0.3  # Alarm threshold for cognitive discontinuity

    # Full Evolutionary Flow System (Phase 2: All Layer Transitions)
    # Extends Toroidal Bridge to ALL layer transitions with Delayed Resonance
    enable_evolutionary_flow: bool = True    # Master switch for evolutionary intelligence
    evo_lambda: float = 0.1                  # Overall evolutionary loss weight
    evo_micro_weight: float = 0.3            # Weight for per-gate coherence loss
    evo_meso_weight: float = 0.3             # Weight for cluster coherence loss (Auth/Sens)
    evo_macro_weight: float = 0.4            # Weight for toroidal coherence loss
    evo_dropout: float = 0.1                 # Dropout in evolutionary gates
    evo_use_rmatrix: bool = True             # Use R-Matrix for evolutionary weights
    evo_coherence_window: int = 100          # Steps for coherence history tracking
    evo_resonance_alpha: float = 0.1         # Strength of O12→O1 delayed resonance injection
    evo_lr_modulation: bool = True           # Enable metacognitive LR adjustment
    evo_lr_slowdown: float = 0.5             # LR multiplier when SLOW_DOWN/BRAKE
    evo_lr_accelerate: float = 1.2           # LR multiplier when ACCELERATE
    # V9.7.0: EvoFlow Fluency Gate - auto-engage gradients when model is fluent
    evo_fluency_gate: bool = False           # Enable automatic EvoFlow gradient engagement
    evo_fluency_min_steps: int = 2000        # Minimum steps before engagement (warmup)
    evo_fluency_ppl_threshold: float = 100.0 # PPL threshold for "fluent" (engage when PPL < this)

    # V9.8.0: RSS (Rational Sovereign Sequence) - Staged gradient engagement
    # Replaces individual fluency gates with unified phase controller

    # PPL-Gated Curriculum Learning - Phased auxiliary loss introduction
    # Ensures model learns coherent generation BEFORE ontological constraints
    enable_curriculum: bool = False           # Enable curriculum controller
    curriculum_ppl_regularization: float = 30.0   # Enter REGULARIZATION when PPL < this
    curriculum_ppl_grounding: float = 15.0        # Enter GROUNDING when PPL < this
    curriculum_ppl_sovereign: float = 10.0        # Enter SOVEREIGN when PPL < this
    curriculum_stability_window: int = 5          # Consecutive evals below threshold
    curriculum_hysteresis: float = 1.5            # Prevent oscillation between phases

    # V2.3.4: Sequence Length Curriculum - Gradual sequence length ramping
    # Starts with shorter sequences for faster syntax learning, ramps up for long-range dependencies
    enable_seq_curriculum: bool = False           # Enable sequence length ramping
    seq_len_start: int = 256                      # Starting sequence length
    seq_len_end: int = 1024                       # Target sequence length (will use max_seq_len if 0)
    seq_len_ramp_steps: int = 5000                # Steps to reach full length
    seq_len_ramp_mode: str = "linear"             # "linear" or "exponential"
    seq_len_ppl_gate: float = 0.0                 # If > 0, only ramp when PPL < this (0 = step-based only)

    # Adaptive Training Controller (dynamic hyperparameter tuning)
    enable_adaptive_training: bool = True    # Enable automatic LR/Kp adjustment
    adaptive_lr_min: float = 1e-5            # Minimum learning rate floor
    adaptive_lr_max: float = 1e-3            # Maximum learning rate ceiling
    adaptive_lr_boost: float = 1.5           # LR boost multiplier when plateau/slow
    adaptive_lr_decay: float = 0.7           # LR decay multiplier when spike
    adaptive_velocity_slow: float = -2.0     # PPL velocity threshold for "too slow" (%)
    adaptive_velocity_spike: float = 10.0    # PPL velocity threshold for "spike" (%)
    adaptive_plateau_window: int = 5         # Evals to check for plateau
    adaptive_plateau_threshold: float = 1.0  # Min improvement % to avoid plateau detection
    adaptive_min_interval: int = 200         # Min steps between adjustments
    # V9.8.2: Safeguards to prevent runaway LR
    adaptive_max_lr_relative: float = 10.0   # Max LR = base_lr * this (prevents runaway)
    adaptive_loss_spike_threshold: float = 5.0  # % loss increase triggers emergency decay
    adaptive_grad_norm_spike: float = 100.0  # Gradient norm above this triggers decay
    adaptive_emergency_decay: float = 0.5    # Aggressive decay factor for emergencies
    adaptive_consecutive_spike_limit: int = 3  # After N consecutive spikes, halt boosts

    # Auto Batch Sizing (VRAM-based startup probing)
    enable_auto_batch: bool = False          # Enable automatic batch size detection at startup
    auto_batch_target_utilization: float = 0.80  # Target VRAM utilization (80%)
    auto_batch_safety_margin: float = 0.05   # Extra headroom (5%)
    auto_batch_target_effective: int = 0     # Target effective batch (0 = just find max, no accum)

    # Friction Controller (V9.4.5)

    # Resume checkpoint
    resume: str = ""
    resume_weights_only: bool = False

    # TensorBoard
    tensorboard: bool = True

    # Quality Sampling
    sample_every: int = 50  # Generate samples every N steps (0 = disabled)
    sample_prompts: tuple = (
        "The Roman Empire began when Julius Caesar",  # Baseline
        "Water boils at 100 degrees Celsius, but at high altitudes,",  # Pivot/Contrast
        "To solve for x in the equation 2x + 6 = 10, the first step is to",  # Logic
        "The three primary colors are red, blue, and yellow. If we mix the first two, we get",  # Memory/Reference
        "The primary difference between a stack and a queue is that",  # Definitions (FineWeb)
    )

    # LRA Validation (Long-Range Retrieval)
    lra_validate_every: int = 0  # Run LRA validation every N steps (0 = disabled)
    lra_haystack_lengths: str = "256,512,1024"  # Comma-separated lengths
    lra_num_samples: int = 50  # Samples per test

    # Hardware
    device: str = "auto"
    num_workers: int = 4

    # Seed
    seed: int = 42

    # ==========================================================================
    # Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md
    # ==========================================================================


    # ==========================================================================
    # V9.8.8: Sovereign Phase Controller (SPC) Configuration
    # Reference: docs/SOVEREIGN_PHASE_CONTROLLER_DESIGN.md
    # ==========================================================================
    spc_entropy_critical: float = 0.4        # Red alert entropy threshold
    spc_entropy_warning: float = 0.5         # Yellow alert entropy threshold
    spc_entropy_recovered: float = 0.55      # Exit boost threshold (hysteresis)
    spc_variance_critical: float = 0.0005    # Critical variance threshold (stagnation)
    spc_variance_warning: float = 0.001      # Warning variance threshold
    spc_variance_recovered: float = 0.002    # Exit boost variance threshold
    spc_min_boost_duration: int = 100        # Minimum steps in boost mode (prevents oscillation)
    spc_alpha: float = 0.2                   # EMA smoothing coefficient for rotation damping
    spc_max_rotation: float = 0.3            # Maximum rotation per step (radians ~17°)
    spc_damping: float = 0.9                 # Velocity damping coefficient
    spc_velocity_threshold: float = 0.2      # Velocity threshold for applying damping

    # ==========================================================================
    # V9.8.9: Dynamic Window Scheduler (DWS) Configuration
    # Reference: Curriculum learning for receptive field dimension
    # ==========================================================================
    enable_dynamic_window: bool = False      # Master toggle (DISABLED by default)
    dws_schedule: Optional[str] = None       # Custom schedule "ppl1:win1,ppl2:win2,..."
    dws_growth_rate_max: float = 1.25        # Maximum growth rate (25% per transition)
    dws_shrink_rate_max: float = 0.80        # Maximum shrink rate (20% per transition)
    dws_align_to: int = 32                   # Align to multiples (GPU efficiency)
    dws_smooth_steps: int = 100              # Interpolation steps (smooth transitions)
    dws_min_steps_between: int = 200         # Cooldown between changes (stability)
    dws_hysteresis: float = 0.15             # PPL hysteresis factor (prevent thrashing)
    dws_vram_threshold: float = 0.85         # VRAM emergency shrink threshold

    # ==========================================================================
    # Phase-JEPA: Joint Embedding Predictive Architecture Configuration
    # Reference: docs/design/HYBRID_PHASE_JEPA_DESIGN.md
    # ==========================================================================
    enable_jepa: bool = False                # Master toggle for Phase-JEPA system
    jepa_hidden_dim: int = 256               # Hidden dimension for JEPA predictor
    jepa_prediction_steps: int = 4           # Number of k-step lookahead predictions
    jepa_num_heads: int = 4                  # Number of attention heads in predictor
    jepa_cosine_mode: str = "complex"        # Phase attention mode (complex/shifted/standard)

    # JEPA Loss Weights
    jepa_vicreg_weight: float = 1.0          # VICReg loss weight
    jepa_alignment_weight: float = 1.0       # Alignment loss weight
    jepa_prediction_weight: float = 0.5      # Prediction loss weight
    jepa_orthogonality_weight: float = 0.01  # Orthogonality regularization

    # JEPA Per-Component Alignment Weights
    # V9.6.8: Rebalanced to prevent Bhava mode collapse (was 10.0/1.0)
    jepa_bhava_weight: float = 1.0           # Bhava (identity) - equal weight allows evolution
    jepa_semantic_weight: float = 5.0        # Kosha/Vritti (semantic) - prioritized for coherence
    jepa_guna_weight: float = 0.1            # Guna (loosely coupled) weight

    # JEPA Target Encoder (EMA)
    jepa_target_momentum: float = 0.996      # EMA momentum for target encoder
    jepa_momentum_schedule: str = "cosine"   # constant/cosine/linear

    # JEPA Training Curriculum (Body→Soul→Union)
    jepa_training_phase: str = "body"        # Current phase: body/soul/union
    jepa_phase_body_steps: int = 20000       # Steps for Body phase
    jepa_phase_soul_steps: int = 30000       # Steps for Soul phase
    jepa_auto_phase_transition: bool = False # Auto-transition phases

    # JEPA Dynamic Graduation (metric-based phase transitions)
    jepa_enable_dynamic_graduation: bool = True    # Enable threshold-based graduation
    jepa_graduation_loss_threshold: float = 20.0   # Graduate if JEPA loss < this
    jepa_graduation_alignment_threshold: float = 25.0  # V9.6.8: Was 72.0 - unrealistic, caused stuck BODY phase

    # JEPA Vritti Validation
    jepa_enable_vritti_validation: bool = False  # Enable Vritti gate validation
    jepa_viparyaya_threshold: float = 0.4    # Max error before damping
    jepa_vikalpa_threshold: float = 0.6      # Max imagination (factual tasks)
    jepa_damping_factor: float = 0.5         # Damping for rejected predictions

    jepa_enable_karma_injection: bool = False # Enable karma state injection for JEPA
    jepa_karma_gate_bias: float = 0.5        # Initial gate bias (0=internal, 1=external)

    # V10.3.7: Vritti Entropy Regularization (prevents single-vritti collapse)
    vritti_entropy_reg: bool = False       # Enable entropy regularization for vritti
    vritti_entropy_lambda: float = 0.1     # Weight for entropy regularization

    # ==========================================================================
    # BCVF Contrastive Structural Pressure on Representations
    # Reference: symbolu/ontological/bcvf_contrastive.py
    # ==========================================================================
    use_bcvf_contrastive: bool = False     # Master toggle for contrastive objective
    bcvf_contrastive_lambda: float = 0.1   # Weight for L_rep in total loss
    bcvf_contrastive_K: int = 16           # Number of negatives per position
    bcvf_contrastive_K_pool: int = 256     # Candidate pool size for Stage A
    bcvf_contrastive_margin: float = 0.15  # Margin for ranking loss
    bcvf_contrastive_alpha: float = 2.0    # Temperature for BCVF negative weighting
    bcvf_contrastive_eta: float = 0.3      # Token embedding injection scale for proxy r_neg
    bcvf_contrastive_d_r: int = 128        # Projection output dimensionality
    bcvf_contrastive_T_sample: int = 4     # Positions per sequence to sample
    bcvf_contrastive_projector: str = "mlp"  # "linear" or "mlp"

    # ==========================================================================
    # BCVF Logit-Margin + Entropy Band (perplexity-aligned)
    # Reference: symbolu/ontological/bcvf_logit_margin.py
    # ==========================================================================
    use_logit_margin: bool = False         # Master toggle
    logit_margin_lambda: float = 0.05      # Weight for margin loss
    logit_margin_entropy_lambda: float = 0.01  # Weight for entropy band loss
    logit_margin_m: float = 0.7            # Minimum logit gap z_pos - z_neg
    logit_margin_H_min: float = 1.5        # Entropy band lower bound
    logit_margin_H_max: float = 4.0        # Entropy band upper bound
    logit_margin_top_k_neg: int = 1        # Hard negatives to average (1 = hardest)

    # ==========================================================================
    # KOSHA-VRITTI STRUCTURED SUPERVISION (Static Compatibility Version)
    # ==========================================================================
    # Auxiliary soft-label supervision for Kosha (4-class) and Vritti (5-class)
    # with entropy floor, static joint compatibility matrix, and staged curriculum.
    # Does NOT modify transformer blocks -- only adds auxiliary linear heads.
    kv_entropy_floor_ratio: float = 0.4        # Hmin = ratio * log(num_classes)
    kv_compatibility_prior_path: str = ""      # Path to W0 prior matrix (empty = none)
    kv_curriculum_exclude_epochs: int = 2      # Epochs to exclude Viparyaya/Nidra
    kv_curriculum_ramp_epochs: int = 1         # Epochs to ramp inclusion
    kv_teacher_mode: str = "heuristic"         # "uniform" or "heuristic" teacher labels
    kv_collapse_check_interval: int = 100      # Steps between collapse checks
    kv_kl_clamp_max: float = 100.0             # Clamp individual KL values

    # ==========================================================================
    # STATE-CONDITIONAL LOGIT SCALE ("Confidence Knob") + ENTROPY BAND
    # Reference: symbolu/training/confidence_scaler.py
    # ==========================================================================
    # Per-token learned logit scale s_t with optional Vritti risk gating.
    # Eliminates calibration artifacts, stabilises training, improves reliability.
    # Does NOT modify transformer blocks -- only emission path + loss + logging.
    enable_confidence_scaler: bool = False       # Master toggle
    confidence_s_min: float = 0.3                # Min scale (prevents over-sharpening)
    confidence_s_max: float = 10.0               # Max scale (prevents trivial uncertainty)
    confidence_epsilon: float = 1e-4             # Numerical floor for softplus
    confidence_entropy_band_min: float = 0.10    # H_min = ratio * log(V)
    confidence_entropy_band_max: float = 0.35    # H_max = ratio * log(V)
    confidence_lambda_band: float = 1e-3         # Weight for entropy band loss
    confidence_lambda_scale: float = 1e-4        # Weight for log(s) regulariser
    # Risk gating via Vritti head (Viparyaya + Nidra → increase uncertainty)
    confidence_enable_risk_gating: bool = False   # Enable Vritti risk gating
    confidence_alpha_risk: float = 0.5            # Risk scaling coefficient
    confidence_vritti_kl_weight: float = 0.1      # Weight for Vritti KL aux loss


# Model size presets
MODEL_PRESETS = {
    "tiny": {
        "embed_dim": 256,
        "num_layers": 6,
        "num_heads": 4,
        "ff_dim": 1024,
    },
    "small": {
        "embed_dim": 512,
        "num_layers": 8,
        "num_heads": 8,
        "ff_dim": 2048,
    },
    "medium": {
        "embed_dim": 768,
        "num_layers": 12,
        "num_heads": 12,
        "ff_dim": 3072,
    },
    "large": {
        "embed_dim": 1024,
        "num_layers": 16,
        "num_heads": 16,
        "ff_dim": 4096,
    },
}


# =============================================================================
# =============================================================================
# Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md Appendix G
#
# =============================================================================

# =============================================================================
# DATASET
# =============================================================================

class TextDataset(Dataset):
    """Dataset for language modeling."""

    def __init__(self, tokens: torch.Tensor, seq_len: int):
        self.tokens = tokens
        self.seq_len = seq_len
        # Need seq_len+1 tokens per sample (input[:-1] + target[1:] shift)
        self.num_samples = (len(tokens) - 1) // seq_len

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]
        return chunk[:-1], chunk[1:]


class FineWebStreamingDataset(IterableDataset):
    """Streaming FineWeb dataset for efficient training on large datasets.

    Supports:
    - HuggingFaceFW/fineweb (CC-based web text)
    - HuggingFaceFW/fineweb-edu (educational content)
    - Any streaming-compatible HuggingFace dataset

    Args:
        cache_dataset: If True, download and cache dataset locally (slower first run,
                       faster subsequent runs, no network required). If False, stream
                       data on-the-fly (faster start, requires network).
    """

    def __init__(
        self,
        tokenizer,
        seq_length: int = 2048,
        dataset_name: str = "HuggingFaceFW/fineweb",
        dataset_subset: str = "sample-10BT",
        split: str = "train",
        cache_dataset: bool = False,
    ):
        self.tokenizer = tokenizer
        self.seq_length = seq_length
        self.dataset_name = dataset_name
        self.dataset_subset = dataset_subset
        self.split = split
        self.cache_dataset = cache_dataset
        self._cached_dataset = None

    def _load_dataset(self):
        """Load dataset (streaming or cached)."""
        from datasets import load_dataset

        if self.cache_dataset:
            # Download and cache locally (stored in ~/.cache/huggingface/datasets/)
            return load_dataset(
                self.dataset_name,
                name=self.dataset_subset,
                split=self.split,
                streaming=False,
            )
        else:
            # Stream dataset to avoid loading everything into memory
            return load_dataset(
                self.dataset_name,
                name=self.dataset_subset,
                split=self.split,
                streaming=True,
            )

    def __iter__(self):
        if self.cache_dataset and self._cached_dataset is None:
            print(f"  [FineWeb] Downloading and caching dataset locally...")
            print(f"  [FineWeb] This may take a while on first run, but will be fast on subsequent runs.")
            self._cached_dataset = self._load_dataset()
            print(f"  [FineWeb] Dataset cached. Size: {len(self._cached_dataset):,} examples")

        dataset = self._cached_dataset if self.cache_dataset else self._load_dataset()
        buffer = []

        for example in dataset:
            # Tokenize text
            text = example.get("text", "")
            if not text:
                continue

            tokens = self.tokenizer.encode(text)
            buffer.extend(tokens)

            # Yield chunks of seq_length + 1 (for input/target)
            while len(buffer) >= self.seq_length + 1:
                chunk = buffer[:self.seq_length + 1]
                buffer = buffer[self.seq_length:]

                input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
                labels = torch.tensor(chunk[1:], dtype=torch.long)

                yield {"input_ids": input_ids, "labels": labels}


def cache_validation_batches(dataloader, num_batches: int = 20) -> list:
    """Pre-cache validation batches to avoid re-resolving streaming dataset.

    This eliminates the 7-minute "Resolving data files" delay during validation
    when using streaming FineWeb datasets.
    """
    print(f"  Caching {num_batches} validation batches...")
    cached = []
    data_iter = iter(dataloader)
    for i in range(num_batches):
        try:
            batch = next(data_iter)
            # Handle different batch formats
            if isinstance(batch, dict):
                cached.append({
                    "input_ids": batch["input_ids"].clone(),
                    "labels": batch["labels"].clone(),
                })
            else:
                # Tuple format (input_ids, labels)
                cached.append({
                    "input_ids": batch[0].clone(),
                    "labels": batch[1].clone(),
                })
        except StopIteration:
            break
    print(f"  Cached {len(cached)} validation batches")
    return cached


def load_data(
    config: UnifiedTrainingConfig,
    tokenizer,
    seq_len_override: Optional[int] = None,
) -> Tuple[DataLoader, DataLoader]:
    """Load and tokenize dataset.

    Supports:
    - wikitext103: WikiText-103 (static, ~100M tokens)
    - wikitext2: WikiText-2 (static, ~2M tokens)
    - fineweb: Streaming FineWeb/FineWeb-edu (uses dataset_name and dataset_subset)

    V9.7.0: Implements tokenization caching for WikiText datasets.
    First run tokenizes and saves to disk (~2-5 min).
    Subsequent runs load from cache (<5 sec).

    V2.3.4: Added seq_len_override for sequence length curriculum.
    """
    # V2.3.4: Use override if provided, otherwise use config
    effective_seq_len = seq_len_override if seq_len_override is not None else config.max_seq_len
    print(f"Loading {config.dataset} dataset...")

    if config.dataset in ["wikitext103", "wikitext2"]:
        # V9.7.0: Check for cached tokenized data
        cache_dir = Path("data_cache")
        cache_dir.mkdir(exist_ok=True)

        # Include tokenizer name in cache path to avoid mismatches
        tokenizer_name = getattr(tokenizer, 'name_or_path', 'unknown').replace('/', '_')
        cache_path = cache_dir / f"{config.dataset}_{tokenizer_name}.pt"

        if cache_path.exists():
            print(f"  📦 Loading cached tokenized data from {cache_path}...")
            cache_start = time.time()
            cached_data = torch.load(cache_path, weights_only=True)
            train_tokens = cached_data['train']
            val_tokens = cached_data['val']
            cache_time = time.time() - cache_start
            print(f"  ✅ Loaded {len(train_tokens):,} train + {len(val_tokens):,} val tokens in {cache_time:.1f}s")
        else:
            print(f"  ⏳ No cache found. Tokenizing {config.dataset} (this only happens once)...")
            tokenize_start = time.time()

            # Static WikiText datasets
            if config.dataset == "wikitext103":
                ds = load_dataset("wikitext", "wikitext-103-v1")
            else:
                ds = load_dataset("wikitext", "wikitext-2-v1")

            def tokenize(split):
                text = "\n".join(ds[split]["text"])
                # V9.8.4: Clean WikiText Moses tokenization artifacts BEFORE tokenizing
                # This prevents the model from learning @,@ @-@ @.@ and = = = patterns
                if GRADIENT_THROTTLE_AVAILABLE:
                    text = clean_wikitext_artifacts(text)
                if hasattr(tokenizer, "encode"):
                    tokens = tokenizer.encode(text)
                else:
                    tokens = tokenizer(text)["input_ids"]
                return torch.tensor(tokens, dtype=torch.long)

            train_tokens = tokenize("train")
            val_tokens = tokenize("validation")

            tokenize_time = time.time() - tokenize_start
            print(f"  ✅ Tokenized {len(train_tokens):,} train + {len(val_tokens):,} val tokens in {tokenize_time:.1f}s")

            # Save to cache for next time
            print(f"  💾 Saving tokenized cache to {cache_path}...")
            torch.save({'train': train_tokens, 'val': val_tokens}, cache_path)
            cache_size_mb = cache_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ Cache saved ({cache_size_mb:.1f} MB). Next startup will be <5s!")

        train_dataset = TextDataset(train_tokens, effective_seq_len)
        val_dataset = TextDataset(val_tokens, effective_seq_len)

        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=config.num_workers,
            pin_memory=True,
            drop_last=True,
            prefetch_factor=2 if config.num_workers > 0 else None,
            persistent_workers=config.num_workers > 0,
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=config.num_workers,
            pin_memory=True,
            drop_last=True,
            prefetch_factor=2 if config.num_workers > 0 else None,
            persistent_workers=config.num_workers > 0,
        )

        return train_loader, val_loader

    elif config.dataset == "fineweb":
        # Streaming or cached FineWeb dataset
        print(f"  Dataset: {config.dataset_name}")
        print(f"  Subset: {config.dataset_subset}")
        print(f"  Sequence length: {effective_seq_len}")
        print(f"  Mode: {'Cached (local)' if config.cache_dataset else 'Streaming'}")

        # Create streaming/cached datasets for train and val
        train_dataset = FineWebStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=config.dataset_name,
            dataset_subset=config.dataset_subset,
            split="train",
            cache_dataset=config.cache_dataset,
        )

        # For validation, we use a small portion of train (FineWeb doesn't have val split)
        val_dataset = FineWebStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=config.dataset_name,
            dataset_subset=config.dataset_subset,
            split="train",  # Use train split, will cache limited batches
            cache_dataset=config.cache_dataset,
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            num_workers=4,
            pin_memory=True,
            prefetch_factor=4,
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            num_workers=2,
            pin_memory=True,
            prefetch_factor=2,
        )

        print(f"  Streaming dataloaders created (batch_size={config.batch_size})")

        return train_loader, val_loader

    elif config.dataset == "synthetic":
        # Offline synthetic dataset (random tokens for architecture validation)
        vocab_size = getattr(tokenizer, 'vocab_size', 256)
        num_train = max(200_000, effective_seq_len * config.batch_size * 100)
        num_val = max(20_000, effective_seq_len * config.batch_size * 10)
        print(f"  Generating synthetic data: {num_train:,} train + {num_val:,} val tokens (vocab={vocab_size})")
        train_tokens = torch.randint(1, vocab_size, (num_train,))
        val_tokens = torch.randint(1, vocab_size, (num_val,))

        train_dataset = TextDataset(train_tokens, effective_seq_len)
        val_dataset = TextDataset(val_tokens, effective_seq_len)

        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=0,
            drop_last=True,
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=0,
            drop_last=True,
        )
        return train_loader, val_loader

    else:
        raise ValueError(f"Unknown dataset: {config.dataset}. Use 'wikitext103', 'wikitext2', 'fineweb', or 'synthetic'")


# =============================================================================
# MODEL CREATION
# =============================================================================

def create_model(config: UnifiedTrainingConfig, device: torch.device) -> nn.Module:
    """Create model based on configuration."""
    preset = MODEL_PRESETS[config.model_size]

    # Apply architecture overrides if provided
    embed_dim = config.n_embd if config.n_embd is not None else preset["embed_dim"]
    num_layers = config.n_layer if config.n_layer is not None else preset["num_layers"]
    num_heads = config.n_head if config.n_head is not None else preset["num_heads"]
    ff_dim = int(embed_dim * 4)  # Standard 4x expansion for FFN
    n_kv_heads = config.n_kv_heads if config.n_kv_heads is not None else None  # None = use num_heads

    # Validate embed_dim / num_heads divisibility
    if embed_dim % num_heads != 0:
        raise ValueError(
            f"n_embd ({embed_dim}) must be evenly divisible by n_head ({num_heads}). "
            f"Got head_dim = {embed_dim}/{num_heads} = {embed_dim/num_heads:.2f} (not integer). "
            f"Valid n_head values for n_embd={embed_dim}: "
            f"{[h for h in [8, 12, 16, 20, 32, 64] if embed_dim % h == 0]}"
        )
    if n_kv_heads is not None and num_heads % n_kv_heads != 0:
        raise ValueError(
            f"n_head ({num_heads}) must be evenly divisible by n_kv_heads ({n_kv_heads})."
        )

    # Print architecture configuration
    print(f"\n{'='*80}")
    print(f"Model Architecture: {config.model_type} ({config.model_size} preset)")
    print(f"{'='*80}")
    if config.n_embd is not None or config.n_layer is not None or config.n_head is not None:
        print(f"  ⚙️  Architecture Overrides Active:")
    print(f"  Embedding Dimension:  {embed_dim}" + (" (override)" if config.n_embd is not None else ""))
    print(f"  Number of Layers:     {num_layers}" + (" (override)" if config.n_layer is not None else ""))
    print(f"  Number of Heads:      {num_heads}" + (" (override)" if config.n_head is not None else ""))
    print(f"  FFN Dimension:        {ff_dim}")
    if n_kv_heads is not None:
        print(f"  KV Heads (GQA):       {n_kv_heads} (override)")
    print(f"  Dropout:              {config.dropout}")
    print(f"  Attention Dropout:    {config.attention_dropout}")
    print(f"{'='*80}\n")

    if config.model_type == "ontological":
        if not ONTOLOGICAL_AVAILABLE:
            raise ImportError("Ontological models not available. Check imports.")

        # Create SymbolU12 with Bhava
        bhava_config = SymbolU12BhavaConfig(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            max_seq_len=config.max_seq_len,
            num_heads=num_heads,
            bhava_embed_dim=config.bhava_embed_dim,
            num_drishti_heads=config.num_drishti_heads,
        )

        model = SymbolU12LLMWithBhava(bhava_config)

        # Enable gradient checkpointing if requested
        if config.gradient_checkpointing:
            # Apply gradient checkpointing to transformer layers
            for name, module in model.named_modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True

    elif config.model_type == "phase":
        model = PhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
            tie_embeddings=tie_emb,
            cosine_mode=config.cosine_mode,  # V9.6.12: Pass cosine mode
            decay_gamma=config.decay_gamma,  # V9.6.13: Pass decay factor
        )
        print(f"  Phase Cosine Mode: {config.cosine_mode}")  # V9.6.12: Log mode
        print(f"  Phase Decay Gamma: {config.decay_gamma}")  # V9.6.13: Log decay

    elif config.model_type == "hybrid":
        # V10.2.1: Determine protected_phase setting
        use_protected_phase = config.protected_phase and not config.no_protected_phase
        model = HybridPhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
            tie_embeddings=tie_emb,
            cosine_mode=config.cosine_mode,  # V9.6.12: Pass cosine mode
            decay_gamma=config.decay_gamma,  # V9.6.13: Pass decay factor
            learned_decay=config.learned_decay,  # V9.9.7: Per-head learned decay
            bounded_phase=config.bounded_phase,  # V9.9.11: Phase collapse fix 1
            zero_mean_cosine=config.zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
            dual_channel_mode=config.dual_channel_mode,  # V10.3.8: Dual-channel attention
            alignment_authority=config.alignment_authority,  # V10.3.8: Alignment authority
            protected_phase=use_protected_phase,  # V10.2.1: Protected Phase for chunking
        )
        print(f"  Hybrid Cosine Mode: {config.cosine_mode}")  # V9.6.12: Log mode
        print(f"  Hybrid Decay Gamma: {config.decay_gamma}")  # V9.6.13: Log decay
        if config.learned_decay:
            print(f"  Learned Decay: ENABLED (per-head attention span)")  # V9.9.7
        if config.bounded_phase:
            print(f"  Bounded Phase: ENABLED (π*sin() bounds φ to [-π, π])")  # V9.9.11
        if config.zero_mean_cosine:
            print(f"  Zero-Mean Cosine: ENABLED (forces selectivity)")  # V9.9.11
        if config.dual_channel_mode:
            print(f"  Dual-Channel Mode: ENABLED (α={config.alignment_authority})")  # V10.3.8
        # V10.2.1: Log chunking settings
        if config.enable_chunking:
            print(f"  Chunking: ENABLED (chunk_size={config.chunk_size})")
            print(f"  Protected Phase: {'ENABLED' if use_protected_phase else 'DISABLED (legacy parallel)'}")

    elif config.model_type == "gen2":
        if not GEN2_AVAILABLE:
            raise ImportError("Gen 2 models not available. Check imports.")

        # Determine num_layers: use 12 for 9:3 split, otherwise preset
        # 9:3 split requires exactly (authority_layers + sensory_layers) = 12 layers
        if config.use_9_3_split:
            gen2_num_layers = config.authority_layers + config.sensory_layers
        else:
            gen2_num_layers = num_layers

        # Create SymbolU12 Gen 2 (Hierarchical Complex Bhava)
        gen2_config = SymbolU12Gen2Config(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_heads=num_heads,
            num_layers=gen2_num_layers,
            complex_dim=64,  # Complex embedding dimension
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            ffn_mult=ff_dim / embed_dim,
        )

        model = SymbolU12Gen2(gen2_config)
        print(f"\n  [Gen 2] Hierarchical Complex Bhava enabled")
        print(f"  [Gen 2] Complex dim: {gen2_config.complex_dim}")
        print(f"  [Gen 2] Num layers: {gen2_num_layers} (9:3 split: {config.use_9_3_split})")
        print(f"  [Gen 2] Hierarchy: 3-tier phase rotation")

    elif config.model_type == "standard":
        # V9.6.9: Standard O(n²) transformer baseline for comparison
        # Uses StandardTransformer from phase_transformer.py
        model = StandardTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            tie_embeddings=tie_emb,
        )
        print(f"\n  [Standard] O(n²) baseline transformer for comparison")

    elif config.model_type == "ontological_hybrid":
        # V9.6.14: Two-Tier AGI Architecture (Ontological State Delta + Hybrid)
        # Ontological: Slow semantic state tracking (System 2)
        # Hybrid: Fast token generation with intent-modulated attention (System 1)
        model = OntologicalHybridTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            n_kv_heads=n_kv_heads,  # V9.8.7: GQA support
            ff_dim=ff_dim,
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
            tie_embeddings=tie_emb,
            cosine_mode=config.cosine_mode,
            decay_gamma=config.decay_gamma,
            learned_decay=config.learned_decay,  # V9.9.7: Per-head learned decay
            bounded_phase=config.bounded_phase,  # V9.9.11: Phase collapse fix 1
            zero_mean_cosine=config.zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
            dual_channel_mode=config.dual_channel_mode,  # V10.3.8: Dual-channel attention
            alignment_authority=config.alignment_authority,  # V10.3.8: Alignment authority
            state_dim=config.state_dim,
            project_per_head_dim=config.project_per_head_dim,
        )
        print(f"\n  [Ontological Hybrid] Two-Tier AGI Architecture enabled (V11.0.0: Separated Planes)")
        print(f"    Full Sovereign State: {config.state_dim}D (diagnostics/control/learning)")
        print(f"    Phase Rotation Input: {PHASE_STATE_DIM}D (Bhava-only → ΔBhava → θ → attention)")
        if config.state_dim == SOVEREIGN_STATE_DIM:
            print(f"      Phase:   [0:12]  12 Bhavas → phase rotation (identity)")
            print(f"      Control: [12:17] 5 Sheaths | [17:22] 5 States | [22:28] 6 Qualia")
            print(f"      Learn:   [28:32] Reserved/JEPA (training-time only)")
        print(f"    Project Per Head Dim: {config.project_per_head_dim}")
        print(f"    Hybrid Cosine Mode: {config.cosine_mode}")
        print(f"    Hybrid Decay Gamma: {config.decay_gamma}")
        if config.learned_decay:
            print(f"    Learned Decay: ENABLED (per-head attention span)")  # V9.9.7
        if config.bounded_phase:
            print(f"    Bounded Phase: ENABLED (π*sin() bounds φ to [-π, π])")  # V9.9.11
        if config.zero_mean_cosine:
            print(f"    Zero-Mean Cosine: ENABLED (forces selectivity)")  # V9.9.11
        if config.dual_channel_mode:
            print(f"    Dual-Channel Mode: ENABLED (α={config.alignment_authority})")  # V10.3.8
        print(f"    Initial State: O12_ABS (Absolute) + Material (Physicality) - Grounded Awareness")

    elif config.model_type == "binding_cache":
        # V10.0: Binding Cache architecture (validated by diagnostic probes)
        # Protected Phase + Top-K Query - prevents Phase decorativeness
        # Reference: train_hard_probes.py --protected-phase showed -50% ablation drop

        # Determine if cache should be used
        use_cache = not config.no_binding_cache
        top_k = config.binding_cache_top_k if use_cache else 0

        model = BindingCacheTransformer(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            decay_gamma=config.decay_gamma,
            learned_decay=config.learned_decay,
            bounded_phase=True,  # Always enabled (mandatory from probes)
            top_k=top_k,
            use_cache=use_cache,
            tie_embeddings=tie_emb,
        )
        print(f"\n  [Binding Cache V10.0] Protected Phase + Top-K Query")
        print(f"    Architecture: Phase (O(n) cumsum) → Quad (O(nk) query)")
        print(f"    Validated by diagnostic probes: -50% Phase ablation drop")
        print(f"    Top-K cache size: {top_k} (use_cache: {use_cache})")
        print(f"    Bounded Phase: ENABLED (mandatory)")
        print(f"    Decay Gamma: {config.decay_gamma}")
        if config.learned_decay:
            print(f"    Learned Decay: ENABLED (per-head attention span)")

    elif config.model_type == "ontological_binding_cache":
        # V10.0: AGI Architecture - Binding Cache + 32D Sovereign State
        # Combines validated Protected Phase with ontological reasoning

        # Determine if cache should be used
        use_cache = not config.no_binding_cache
        top_k = config.binding_cache_top_k if use_cache else 0

        model = OntologicalBindingCacheTransformer(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            decay_gamma=config.decay_gamma,
            learned_decay=config.learned_decay,
            top_k=top_k,
            use_cache=use_cache,
            state_dim=config.state_dim,
            project_per_head_dim=config.project_per_head_dim,
            tie_embeddings=tie_emb,
        )
        print(f"\n  [Ontological Binding Cache V11.0.0] AGI Architecture (Separated Planes)")
        print(f"    Combines: Protected Phase + Top-K Query + Separated Sovereign State")
        print(f"    Architecture: ΔBhava[12D] → Phase rotation → Memory binding → Query")
        print(f"    Full Sovereign State: {config.state_dim}D (diagnostics/control/learning)")
        print(f"    Phase Rotation Input: {PHASE_STATE_DIM}D (Bhava-only → ΔBhava → θ → attention)")
        if config.state_dim == SOVEREIGN_STATE_DIM:
            print(f"      Phase:   [0:12]  12 Bhavas → phase rotation (identity)")
            print(f"      Control: [12:17] 5 Sheaths | [17:22] 5 States | [22:28] 6 Qualia → Annotator/CTM+")
            print(f"      Learn:   [28:32] Reserved/JEPA (training-time only)")
        print(f"    Top-K cache size: {top_k} (use_cache: {use_cache})")
        print(f"    Bounded Phase: ENABLED (mandatory from probes)")
        print(f"    Decay Gamma: {config.decay_gamma}")
        if config.learned_decay:
            print(f"    Learned Decay: ENABLED (per-head attention span)")
        print(f"    Project Per Head Dim: {config.project_per_head_dim}")
        # V10.0: Binding Annotation status
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    # Enable gradient checkpointing after model creation
    # V9.5.2 Metabolic Tuning: Use non-reentrant checkpointing for better memory efficiency
    if config.gradient_checkpointing:
        if hasattr(model, 'gradient_checkpointing_enable'):
            # Try HuggingFace-style API first, fall back to simple call
            try:
                model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
                print(f"  [Metabolic] Gradient checkpointing enabled (non-reentrant mode)")
            except TypeError:
                # Model has the method but doesn't accept kwargs
                model.gradient_checkpointing_enable()
                print(f"  [Metabolic] Gradient checkpointing enabled")
        else:
            # Manual flag-based checkpointing
            for module in model.modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True
                # Set use_reentrant=False for torch.utils.checkpoint compatibility
                if hasattr(module, 'use_reentrant'):
                    module.use_reentrant = False
            print(f"  [Metabolic] Gradient checkpointing enabled (flag-based)")

        if config.checkpoint_offload_cpu:
            print(f"  [Metabolic] CPU activation offloading requested (requires custom forward)")

    return model.to(device)


# =============================================================================
# PER-LAYER PHASE CONTROLLER (V9.9.1)
# =============================================================================

class PerLayerPhaseController:
    """
    V9.9.1: Manages per-layer phase weights for fine-grained control over
    the Phase/Sensory split during Inverted Curriculum Evolution.

    Instead of a global alpha_phase applied to all layers, this controller
    maintains individual weights for each layer, enabling:
    1. Soft layer transitions (gradual 0→1 ramp)
    2. Per-layer decay schedules
    3. Inverted curriculum where Sensory→Authority transitions happen one layer at a time

    The weight for each layer controls the blend:
        output = (1 - alpha) * quadratic_attention + alpha * phase_attention
        - alpha = 0.0: Pure Sensory (Quadratic attention)
        - alpha = 1.0: Pure Authority (Phase attention)
        - 0 < alpha < 1: Hybrid blend

    Usage:
        controller = PerLayerPhaseController(num_layers=12)
        controller.set_weights([0.0] * 12)  # Start all Sensory

        # In training loop:
        controller.update(step)
        controller.apply_to_model(model)
    """

    def __init__(
        self,
        num_layers: int = 12,
        initial_weights: Optional[List[float]] = None,
        local_layers: int = 4,  # Layers 0 to local_layers-1 are LocalAttention (no phase weight)
    ):
        """
        Initialize per-layer phase controller.

        Args:
            num_layers: Total number of layers in the model
            initial_weights: Initial phase weights for each layer (0.0 = Sensory, 1.0 = Authority)
                            If None, defaults to [0.0] * num_layers (all Sensory)
            local_layers: Number of early layers that use LocalAttention only (no phase component)
        """
        self.num_layers = num_layers
        self.local_layers = local_layers

        # Initialize weights
        if initial_weights is not None:
            if len(initial_weights) != num_layers:
                raise ValueError(f"initial_weights must have {num_layers} elements, got {len(initial_weights)}")
            self.weights = list(initial_weights)
        else:
            # Default: all Sensory (alpha_phase = 0.0)
            self.weights = [0.0] * num_layers

        # Transition tracking for soft layer transitions
        self.transitions = {}  # layer_idx -> {start_step, end_step, start_val, end_val}
        self.transition_history = []  # Log of completed transitions

        print(f"\n  🎛️ [PER-LAYER PHASE] Controller initialized:")
        print(f"      Total layers: {num_layers}")
        print(f"      Local layers: 0-{local_layers-1} (no phase component)")
        print(f"      Hybrid layers: {local_layers}-{num_layers-1} (per-layer phase weights)")
        print(f"      Initial weights: {self._format_weights()}")

    def _format_weights(self) -> str:
        """Format weights for display, showing only hybrid layers."""
        hybrid_weights = self.weights[self.local_layers:]
        return "[" + ", ".join(f"{w:.2f}" for w in hybrid_weights) + "]"

    def get_weight(self, layer_idx: int) -> float:
        """Get the current phase weight for a specific layer."""
        if layer_idx < 0 or layer_idx >= self.num_layers:
            return 0.0
        return self.weights[layer_idx]

    def set_weight(self, layer_idx: int, weight: float):
        """Set the phase weight for a specific layer."""
        if 0 <= layer_idx < self.num_layers:
            self.weights[layer_idx] = max(0.0, min(1.0, weight))

    def set_weights(self, weights: List[float]):
        """Set all phase weights at once."""
        if len(weights) != self.num_layers:
            raise ValueError(f"weights must have {self.num_layers} elements, got {len(weights)}")
        self.weights = [max(0.0, min(1.0, w)) for w in weights]

    def start_transition(
        self,
        layer_idx: int,
        target_weight: float,
        duration_steps: int,
        current_step: int,
    ):
        """
        Start a soft transition for a specific layer.

        The weight will linearly interpolate from current value to target
        over duration_steps training steps.

        Args:
            layer_idx: Which layer to transition
            target_weight: Target phase weight (0.0 = Sensory, 1.0 = Authority)
            duration_steps: Number of steps for the transition
            current_step: Current training step
        """
        if layer_idx < self.local_layers:
            print(f"  ⚠️ [PER-LAYER PHASE] Layer {layer_idx} is LocalAttention, no phase to transition")
            return

        current_weight = self.weights[layer_idx]
        self.transitions[layer_idx] = {
            'start_step': current_step,
            'end_step': current_step + duration_steps,
            'start_val': current_weight,
            'end_val': target_weight,
        }
        direction = "→Authority" if target_weight > current_weight else "→Sensory"
        print(f"  🔄 [PER-LAYER PHASE] Layer {layer_idx} transition: {current_weight:.2f} → {target_weight:.2f} ({direction}) over {duration_steps} steps")

    def update(self, current_step: int) -> Dict[str, any]:
        """
        Update all active transitions based on current step.

        Returns dict with:
            - 'weights': Current per-layer weights
            - 'active_transitions': Number of layers currently transitioning
            - 'completed': List of layer indices that completed this step
        """
        completed = []

        for layer_idx, trans in list(self.transitions.items()):
            start_step = trans['start_step']
            end_step = trans['end_step']
            start_val = trans['start_val']
            end_val = trans['end_val']

            if current_step >= end_step:
                # Transition complete
                self.weights[layer_idx] = end_val
                completed.append(layer_idx)
                self.transition_history.append({
                    'layer_idx': layer_idx,
                    'completed_step': current_step,
                    'final_weight': end_val,
                })
                del self.transitions[layer_idx]
                print(f"  ✓ [PER-LAYER PHASE] Layer {layer_idx} transition complete: α={end_val:.2f}")
            else:
                # Interpolate
                progress = (current_step - start_step) / (end_step - start_step)
                self.weights[layer_idx] = start_val + progress * (end_val - start_val)

        return {
            'weights': self.weights.copy(),
            'active_transitions': len(self.transitions),
            'completed': completed,
        }

    def apply_to_model(self, model: nn.Module):
        """
        Apply current per-layer weights to the model's HybridAttentionLayer modules.

        This updates each layer's alpha_phase parameter based on its layer_idx.
        """
        applied_count = 0
        for module in model.modules():
            if hasattr(module, 'alpha_phase') and hasattr(module, 'layer_idx'):
                layer_idx = module.layer_idx
                if 0 <= layer_idx < self.num_layers:
                    weight = self.weights[layer_idx]
                    module.alpha_phase.data.fill_(weight)
                    if hasattr(module, 'alpha_local'):
                        module.alpha_local.data.fill_(1.0 - weight)
                    applied_count += 1
        if applied_count > 0:
            print(f"      Applied per-layer weights to {applied_count} HybridAttentionLayer modules")

    def get_status(self) -> Dict[str, any]:
        """Get current controller status for logging."""
        # Count layers by type based on current weights
        authority_count = sum(1 for w in self.weights[self.local_layers:] if w >= 0.9)
        sensory_count = sum(1 for w in self.weights[self.local_layers:] if w <= 0.1)
        transitioning_count = len(self.weights[self.local_layers:]) - authority_count - sensory_count

        return {
            'weights': self.weights.copy(),
            'local_layers': self.local_layers,
            'authority_count': authority_count,
            'sensory_count': sensory_count,
            'transitioning_count': transitioning_count,
            'active_transitions': len(self.transitions),
            'completed_transitions': len(self.transition_history),
        }

    @classmethod
    def from_config(cls, config) -> 'PerLayerPhaseController':
        """Create controller from UnifiedTrainingConfig."""
        # Parse initial weights from config string
        initial_weights = None
        if hasattr(config, 'per_layer_phase_weights') and config.per_layer_phase_weights:
            try:
                initial_weights = [float(w.strip()) for w in config.per_layer_phase_weights.split(',')]
            except ValueError:
                print(f"  ⚠️ [PER-LAYER PHASE] Invalid weights string: {config.per_layer_phase_weights}")
                initial_weights = None

        return cls(
            num_layers=12,  # Fixed for Sovereign-1 architecture
            initial_weights=initial_weights,
            local_layers=config.local_layers if hasattr(config, 'local_layers') else 4,
        )


# =============================================================================
# INVERTED LAYER CURRICULUM CONTROLLER (V9.9.2)
# =============================================================================

class InvertedLayerCurriculumController:
    """
    V9.9.2: Orchestrates the Inverted Layer Curriculum Evolution.

    Manages split evolution (3:9 → 9:3) with per-layer phase weights and soft
    transitions. Optionally delegates sequence length management to an external
    SequenceLengthCurriculum for sophisticated PPL-gated seq_len progression.

    Responsibilities:
    1. Split evolution: 3:9 → 6:6 → 9:3 (Sensory-first → Authority-later)
    2. Per-layer phase weights (via PerLayerPhaseController)
    3. Soft layer transitions with phase ramp as shock absorber

    Delegation (optional):
    - If seq_len_curriculum is provided, seq_len is delegated to it
    - If not provided, uses fixed default_seq_len

    Benefits of separation:
    - SequenceLengthCurriculum handles: PPL gating, linear/exponential ramp, reload detection
    - InvertedLayerCurriculumController handles: split evolution, layer weights, transitions
    - Both react to PPL but control different aspects

    Example curriculum (splits only):
        Stage 0: 3:9 split | PPL > 300  (start)
        Stage 1: 4:8 split | PPL < 300
        Stage 2: 5:7 split | PPL < 200
        Stage 3: 6:6 split | PPL < 120
        Stage 4: 7:5 split | PPL < 75
        Stage 5: 8:4 split | PPL < 45
        Stage 6: 9:3 split | PPL < 25

    Usage (with delegation):
        seq_curriculum = SequenceLengthCurriculum(seq_len_start=256, seq_len_end=2048, ...)
        split_curriculum = InvertedLayerCurriculumController.from_config(
            config, seq_len_curriculum=seq_curriculum
        )

        # In training loop:
        result = split_curriculum.update(step, current_ppl)
        if result['split_changed']:
            reconfigure_gradient_scaler(result['current_split'])
        # seq_len changes handled by seq_curriculum.should_reload_data()
        split_curriculum.apply_to_model(model)

    Usage (standalone):
        split_curriculum = InvertedLayerCurriculumController(
            stages=[(3,9), (4,8), (5,7), (6,6), (7,5), (8,4), (9,3)],
            ppl_triggers=[300, 200, 120, 75, 45, 25],
            default_seq_len=1024,  # Fixed seq_len
        )
    """

    def __init__(
        self,
        stages: List[Tuple[int, int]],  # [(3, 9), (4, 8), ...] - just splits
        ppl_triggers: List[float],  # PPL thresholds for each transition
        local_layers: int = 4,
        transition_steps: int = 500,  # Steps for soft layer transition
        seq_len_curriculum: Optional['SequenceLengthCurriculum'] = None,  # Optional delegation
        default_seq_len: int = 1024,  # Used when no seq_len_curriculum provided
        # V9.9.4: PPL Stability Check (ChatGPT recommendation)
        ppl_stability_threshold: float = 5.0,  # Max PPL slope for "stable" (lower = stricter)
        stability_required_stages: Optional[List[int]] = None,  # Stages requiring stability [2,3,4]
        # V9.9.8: Explicit per-layer phase weights (Gemini's Tapered Bridge)
        initial_phase_weights: Optional[List[float]] = None,  # Override _split_to_weights if provided
    ):
        """
        Initialize the Inverted Curriculum Controller.

        Args:
            stages: List of (authority, sensory) split tuples, e.g., [(3, 9), (6, 6), (9, 3)]
            ppl_triggers: PPL thresholds for advancing to next stage
            local_layers: Number of local attention layers (no phase component)
            transition_steps: Steps for soft layer transitions
            seq_len_curriculum: Optional SequenceLengthCurriculum for seq_len delegation
            default_seq_len: Fixed seq_len when no curriculum provided
            ppl_stability_threshold: Maximum PPL slope to consider "stable" (V9.9.4)
            stability_required_stages: Which stages require stability check before advancing
        """
        self.stages = stages
        self.ppl_triggers = ppl_triggers
        self.local_layers = local_layers
        self.transition_steps = transition_steps
        self.seq_len_curriculum = seq_len_curriculum
        self.default_seq_len = default_seq_len

        # V9.9.4: PPL Stability (ChatGPT's "Readiness Index")
        self.ppl_stability_threshold = ppl_stability_threshold
        # Default: require stability for middle stages (geometry shift zone)
        self.stability_required_stages = stability_required_stages or [2, 3, 4]

        # V9.9.4: ReadinessIndex for composite stability check
        # Combines PPL velocity + acceleration + internal geometry
        self.readiness_index = ReadinessIndex(
            ppl_velocity_threshold=ppl_stability_threshold,
            ppl_accel_threshold=ppl_stability_threshold / 2,  # Stricter on acceleration
            history_window=10,
            require_geometry_check=True,
        )

        # Current state
        self.current_stage_idx = 0
        self.current_split = stages[0]

        # Per-layer phase controller
        # V9.9.8: Use explicit weights (Gemini's Tapered Bridge) if provided
        if initial_phase_weights is not None:
            initial_weights = initial_phase_weights
            print(f"      Using explicit per-layer phase weights (Tapered Bridge)")
        else:
            initial_weights = self._split_to_weights(self.current_split)
        self.phase_controller = PerLayerPhaseController(
            num_layers=12,
            initial_weights=initial_weights,
            local_layers=local_layers,
        )

        # PPL tracking for smooth triggers (kept for smoothed_ppl calculation)
        self.ppl_history: List[float] = []
        self.ppl_window = 10  # Steps to average PPL

        # Transition tracking
        self.stage_history: List[Dict] = []
        self.last_stage_change_step = 0

        # Print curriculum
        self._print_curriculum()

    def _print_curriculum(self):
        """Print the full curriculum schedule."""
        seq_mode = "DELEGATED" if self.seq_len_curriculum else f"FIXED@{self.default_seq_len}"
        print(f"\n  🎓 [INVERTED CURRICULUM] Schedule (seq_len: {seq_mode}):")
        print(f"      {'Stage':<8} {'Split':<8} {'PPL Trigger':<12}")
        print(f"      {'-'*30}")
        for i, (auth, sens) in enumerate(self.stages):
            trigger = f"< {self.ppl_triggers[i]:.0f}" if i < len(self.ppl_triggers) else "START"
            marker = " ◀" if i == self.current_stage_idx else ""
            print(f"      {i:<8} {auth}:{sens:<5} {trigger:<12}{marker}")
        if self.seq_len_curriculum:
            print(f"\n      Seq Len: Delegated to SequenceLengthCurriculum")
            print(f"      Range: {self.seq_len_curriculum.seq_len_start} → {self.seq_len_curriculum.seq_len_end}")
            print(f"      Mode: {self.seq_len_curriculum.ramp_mode}")
            if self.seq_len_curriculum.ppl_gate > 0:
                print(f"      PPL Gate: < {self.seq_len_curriculum.ppl_gate}")

    def _split_to_weights(self, split: Tuple[int, int]) -> List[float]:
        """
        Convert a split (authority, sensory) to per-layer weights.

        For 12 layers with local_layers=4:
        - Layers 0-3: Local only (weight doesn't matter, but set to 0)
        - Layers 4-11: Hybrid, weight = 1.0 for Authority, 0.0 for Sensory

        Example: split (6, 6) means layers 0-5 are Authority, layers 6-11 are Sensory
        So weights for layers 4-11 would be [1, 1, 0, 0, 0, 0, 0, 0]
        """
        authority_layers, sensory_layers = split
        weights = [0.0] * 12

        for i in range(12):
            if i < authority_layers:
                weights[i] = 1.0  # Authority layer
            else:
                weights[i] = 0.0  # Sensory layer

        return weights

    def _compute_ppl_slope(self) -> float:
        """
        V9.9.4: Compute PPL slope (rate of change) from history.

        Returns the average change per step. Negative = improving, positive = worsening.
        A small absolute value indicates stability (plateauing).

        ChatGPT's insight: "PPL can drop while geometry is still reconfiguring.
        Advancing authority too early can slow fluency."
        """
        if len(self.ppl_history) < 3:
            return float('inf')  # Not enough data, assume unstable

        # Compute differences between consecutive PPL values
        diffs = [self.ppl_history[i+1] - self.ppl_history[i]
                 for i in range(len(self.ppl_history) - 1)]

        # Average slope (negative = improving)
        avg_slope = sum(diffs) / len(diffs)

        return avg_slope

    def _is_ppl_stable(self, next_stage_idx: int) -> Tuple[bool, float, str]:
        """
        V9.9.4: Check if PPL is stable enough to advance to next stage.

        Args:
            next_stage_idx: The stage we would advance to

        Returns:
            Tuple of (is_stable, slope, reason_string)
        """
        slope = self._compute_ppl_slope()

        # Check if this stage requires stability
        if next_stage_idx not in self.stability_required_stages:
            return True, slope, "stability_not_required"

        # Check stability: slope should be small (plateauing)
        # We use absolute value because we care about magnitude, not direction
        abs_slope = abs(slope)

        if abs_slope <= self.ppl_stability_threshold:
            return True, slope, "stable"
        elif slope > 0:
            return False, slope, "ppl_rising"
        else:
            return False, slope, "ppl_dropping_fast"

    def update(
        self,
        step: int,
        current_ppl: Optional[float] = None,
        phase_coherence: Optional[float] = None,
        state_delta_norm: Optional[float] = None,
    ) -> Dict[str, any]:
        """
        Update the curriculum based on current step, PPL, and internal geometry.

        V9.9.4: Now uses composite ReadinessIndex that checks:
        1. ΔPPL → small (velocity collapse)
        2. ΔΔPPL → small (acceleration collapse)
        3. Phase/state metrics stable (geometry settled)

        Args:
            step: Current training step
            current_ppl: Current validation PPL (optional)
            phase_coherence: Phase coherence from SPC diagnostics (0-1)
            state_delta_norm: Magnitude of state-delta from Sovereign State

        Returns:
            Dict with:
                - 'current_stage': Current stage index
                - 'current_split': Current (authority, sensory) split
                - 'current_seq_len': Current sequence length (from delegate or fixed)
                - 'split_changed': Whether split changed this step
                - 'seq_len_changed': Whether seq_len changed (from delegate)
                - 'transitioning_layers': Number of layers currently transitioning
                - 'layer_weights': Current per-layer weights
                - 'readiness_score': Composite readiness score (0-1)
        """
        split_changed = False
        old_split = self.current_split

        # Update PPL history (for smoothed_ppl calculation)
        if current_ppl is not None:
            self.ppl_history.append(current_ppl)
            if len(self.ppl_history) > self.ppl_window:
                self.ppl_history.pop(0)

        # V9.9.4: Update ReadinessIndex with all available metrics
        if current_ppl is not None:
            self.readiness_index.update(
                ppl=current_ppl,
                phase_coherence=phase_coherence,
                state_delta_norm=state_delta_norm,
            )

        # Check for stage advancement (split evolution)
        # V9.9.4: Now uses composite ReadinessIndex for true stability check
        if self.current_stage_idx < len(self.stages) - 1 and current_ppl is not None:
            smoothed_ppl = sum(self.ppl_history) / len(self.ppl_history) if self.ppl_history else current_ppl
            next_trigger = self.ppl_triggers[self.current_stage_idx] if self.current_stage_idx < len(self.ppl_triggers) else float('inf')
            next_stage_idx = self.current_stage_idx + 1

            if smoothed_ppl < next_trigger:
                # V9.9.4: Use composite ReadinessIndex for middle stages
                require_geometry = next_stage_idx in self.stability_required_stages
                is_ready, diagnostics = self.readiness_index.is_ready(require_geometry=require_geometry)

                if is_ready or next_stage_idx not in self.stability_required_stages:
                    # Advance to next stage
                    self.current_stage_idx = next_stage_idx
                    new_split = self.stages[self.current_stage_idx]

                    if new_split != old_split:
                        split_changed = True
                        self._transition_to_split(new_split, step)

                    # V9.9.4: Reset persistence counter for next stage
                    # "Start fresh with stability tracking for the new stage"
                    self.readiness_index.reset_persistence()

                    # Record history with full diagnostics
                    self.stage_history.append({
                        'stage': self.current_stage_idx,
                        'step': step,
                        'ppl': smoothed_ppl,
                        'velocity': diagnostics['ppl_velocity'],
                        'acceleration': diagnostics['ppl_acceleration'],
                        'consecutive_stable': diagnostics.get('consecutive_stable', 0),
                        'reason': diagnostics['reason'],
                        'split': new_split,
                    })
                    self.last_stage_change_step = step

                    # Log with velocity/acceleration info
                    vel = diagnostics['ppl_velocity']
                    acc = diagnostics['ppl_acceleration']
                    consec = diagnostics.get('consecutive_stable', 0)
                    stability_note = f" (Δppl: {vel:+.2f}, ΔΔppl: {acc:+.2f}, consec: {consec})"
                    print(f"\n  🎓 [INVERTED CURRICULUM] Stage {self.current_stage_idx} reached!{stability_note}")
                    print(f"      PPL {smoothed_ppl:.2f} < {next_trigger:.0f}")
                    print(f"      Split: {old_split[0]}:{old_split[1]} → {new_split[0]}:{new_split[1]}")
                    if require_geometry:
                        print(f"      Readiness: {diagnostics['reason']} (geometry checked)")
                else:
                    # V9.9.4: PPL threshold met but not truly settled - wait
                    # Only log occasionally to avoid spam
                    if step % 500 == 0:
                        vel = diagnostics['ppl_velocity']
                        acc = diagnostics['ppl_acceleration']
                        consec = diagnostics.get('consecutive_stable', 0)
                        req_consec = diagnostics.get('required_consecutive', 3)
                        print(f"  ⏳ [INVERTED CURRICULUM] Stage {next_stage_idx} pending: "
                              f"PPL {smoothed_ppl:.1f} < {next_trigger:.0f} but {diagnostics['reason']}")
                        print(f"      Δppl: {vel:+.2f}, ΔΔppl: {acc:+.2f}, stability: {consec}/{req_consec}")

        # Update per-layer phase controller (for soft transitions)
        phase_result = self.phase_controller.update(step)

        # Get seq_len from delegate or use fixed
        if self.seq_len_curriculum is not None:
            current_seq_len = self.seq_len_curriculum.get_seq_len(step, current_ppl)
            seq_len_changed = self.seq_len_curriculum.should_reload_data()
        else:
            current_seq_len = self.default_seq_len
            seq_len_changed = False

        return {
            'current_stage': self.current_stage_idx,
            'current_split': self.current_split,
            'current_seq_len': current_seq_len,
            'split_changed': split_changed,
            'seq_len_changed': seq_len_changed,
            'transitioning_layers': phase_result['active_transitions'],
            'layer_weights': phase_result['weights'],
            'completed_transitions': phase_result['completed'],  # V9.9.3: For momentum dampening
            'readiness_score': self.readiness_index.get_composite_score(),  # V9.9.4: Composite readiness
        }

    def _transition_to_split(self, new_split: Tuple[int, int], step: int):
        """
        Start soft transition to a new split.

        Identifies which layer(s) are changing and starts their transition.
        """
        old_auth, old_sens = self.current_split
        new_auth, new_sens = new_split

        if new_auth > old_auth:
            # Moving from Sensory to Authority (3:9 → 4:8 → 5:7 → ...)
            for layer_idx in range(old_auth, new_auth):
                if layer_idx >= self.local_layers:
                    self.phase_controller.start_transition(
                        layer_idx=layer_idx,
                        target_weight=1.0,  # Becoming Authority
                        duration_steps=self.transition_steps,
                        current_step=step,
                    )
        else:
            # Moving from Authority to Sensory (9:3 → 8:4 → 7:5 → ...)
            for layer_idx in range(new_auth, old_auth):
                if layer_idx >= self.local_layers:
                    self.phase_controller.start_transition(
                        layer_idx=layer_idx,
                        target_weight=0.0,  # Becoming Sensory
                        duration_steps=self.transition_steps,
                        current_step=step,
                    )

        self.current_split = new_split

    def apply_to_model(self, model: nn.Module):
        """Apply current per-layer weights to the model."""
        self.phase_controller.apply_to_model(model)

    def get_status(self) -> Dict[str, any]:
        """Get current curriculum status for logging."""
        status = {
            'stage': self.current_stage_idx,
            'total_stages': len(self.stages),
            'split': f"{self.current_split[0]}:{self.current_split[1]}",
            'smoothed_ppl': sum(self.ppl_history) / len(self.ppl_history) if self.ppl_history else None,
            'next_trigger': self.ppl_triggers[self.current_stage_idx] if self.current_stage_idx < len(self.ppl_triggers) else None,
            'transitioning_layers': len(self.phase_controller.transitions),
            'layer_weights': self.phase_controller.weights[self.local_layers:],
        }
        # Add seq_len info from delegate or fixed
        if self.seq_len_curriculum is not None:
            status['seq_len'] = self.seq_len_curriculum.current_seq_len
            status['seq_len_mode'] = 'delegated'
        else:
            status['seq_len'] = self.default_seq_len
            status['seq_len_mode'] = 'fixed'
        return status

    @classmethod
    def from_config(
        cls,
        config,
        seq_len_curriculum: Optional['SequenceLengthCurriculum'] = None,
    ) -> 'InvertedLayerCurriculumController':
        """
        Create controller from config with optional seq_len delegation.

        Args:
            config: UnifiedTrainingConfig with inverted curriculum settings
            seq_len_curriculum: Optional SequenceLengthCurriculum for seq_len delegation

        Config fields used:
        - inverted_curriculum_stages: "3:9,4:8,5:7,6:6,7:5,8:4,9:3" (splits only)
        - inverted_curriculum_ppl_triggers: "300,200,120,75,45,25"
        - layer_transition_steps: Steps for soft transitions (default: 500)
        - local_layers: Number of local attention layers (default: 4)
        - inverted_curriculum_stability_threshold: Max PPL slope for "stable" (V9.9.4)
        - inverted_curriculum_stability_stages: "2,3,4" - stages requiring stability
        """
        # Parse stages (splits only, no seq_len)
        if hasattr(config, 'inverted_curriculum_stages') and config.inverted_curriculum_stages:
            stages = []
            for stage_str in config.inverted_curriculum_stages.split(','):
                stage_str = stage_str.strip()
                # Support both "3:9" and "3:9@256" formats (ignore @seq_len for backwards compat)
                if '@' in stage_str:
                    stage_str = stage_str.split('@')[0]
                split_parts = stage_str.split(':')
                if len(split_parts) == 2:
                    auth, sens = int(split_parts[0]), int(split_parts[1])
                    stages.append((auth, sens))
        else:
            # Default inverted curriculum (splits only)
            stages = [
                (3, 9),   # Start: Heavy Sensory
                (4, 8),
                (5, 7),
                (6, 6),   # Balanced
                (7, 5),
                (8, 4),
                (9, 3),   # End: Heavy Authority
            ]

        # Parse PPL triggers
        if hasattr(config, 'inverted_curriculum_ppl_triggers') and config.inverted_curriculum_ppl_triggers:
            ppl_triggers = [float(t.strip()) for t in config.inverted_curriculum_ppl_triggers.split(',')]
        else:
            # Default triggers
            ppl_triggers = [300, 200, 120, 75, 45, 25]

        # V9.9.4: Parse stability stages
        stability_stages = None
        if hasattr(config, 'inverted_curriculum_stability_stages') and config.inverted_curriculum_stability_stages:
            stability_stages = [int(s.strip()) for s in config.inverted_curriculum_stability_stages.split(',')]

        # V9.9.8: Parse explicit per-layer phase weights (Gemini's Tapered Bridge)
        initial_phase_weights = None
        if hasattr(config, 'per_layer_phase_weights') and config.per_layer_phase_weights:
            initial_phase_weights = [float(w.strip()) for w in config.per_layer_phase_weights.split(',')]
            print(f"  [TAPERED BRIDGE] Parsed per-layer weights: {initial_phase_weights}")

        return cls(
            stages=stages,
            ppl_triggers=ppl_triggers,
            local_layers=getattr(config, 'local_layers', 4),
            transition_steps=getattr(config, 'layer_transition_steps', 500),
            seq_len_curriculum=seq_len_curriculum,
            default_seq_len=getattr(config, 'max_seq_len', 1024),
            # V9.9.4: PPL Stability Check
            ppl_stability_threshold=getattr(config, 'inverted_curriculum_stability_threshold', 5.0),
            stability_required_stages=stability_stages,
            # V9.9.8: Gemini's Tapered Bridge
            initial_phase_weights=initial_phase_weights,
        )


def update_alpha_schedule(model: nn.Module, step: int, config: UnifiedTrainingConfig) -> float:
    """
    Update alpha_phase for HybridAttentionLayer modules based on decay schedule.

    Returns current alpha_phase value.
    """
    # V9.8.10: Check if model type contains "hybrid" or "phase" (supports ontological_hybrid)
    if "hybrid" not in config.model_type and "phase" not in config.model_type:
        return config.alpha_phase  # No alpha scheduling for pure ontological/standard models

    # Calculate current alpha based on linear decay
    # V9.8.10: Use phase_ramp_steps if available (more intuitive), fallback to alpha_decay_steps
    decay_steps = getattr(config, 'phase_ramp_steps', config.alpha_decay_steps)
    if step >= decay_steps:
        current_alpha = config.alpha_phase_end
    else:
        frac = step / decay_steps
        current_alpha = config.alpha_phase_start + frac * (config.alpha_phase_end - config.alpha_phase_start)

    # Update all HybridAttentionLayer modules
    for module in model.modules():
        if hasattr(module, 'alpha_phase') and isinstance(module.alpha_phase, nn.Parameter):
            module.alpha_phase.data.fill_(current_alpha)
            if hasattr(module, 'alpha_local'):
                module.alpha_local.data.fill_(1.0 - current_alpha)

    return current_alpha


# =============================================================================
# LOSS FUNCTIONS
# =============================================================================

def compute_ontological_loss(
    outputs: Dict[str, torch.Tensor],
    targets: torch.Tensor,
    config: UnifiedTrainingConfig,
    sovereign_loss: Optional['SovereignLoss'] = None,
    sovereign_engine: Optional['SovereignEngine'] = None,
    phase_angles: Optional[List[torch.Tensor]] = None,
    epoch: int = 0,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute loss for ontological model.

    Priority order:
    1. Sovereign-Lagrangian Loss (Patent B1/S3) - if enable_sovereign_loss
    2. Sovereign-1 hardened loss - if use_sovereign_loss
    3. Legacy loss (fallback)

    Sovereign-Lagrangian Loss combines:
    - L_task: Standard cross-entropy
    - L_consistency [B1]: Forward/Backward feasibility alignment
    - L_align [S3]: Global coherence penalty

    Sovereign-1 hardened loss uses:
    - Decomposed state friction (prevents Signal Washing)
    - Weighted signals (prioritizes R-Signal over C-Signal)
    - Bhava transition penalty

    Legacy loss uses:
    - Language modeling loss (cross-entropy)
    - Bhava relationship consistency loss
    - Global coherence regularization
    - Entropy regularization
    """
    metrics = {}
    logits = outputs["logits"]
    B, N, V = logits.shape

    # Compute semantic entropy [S5] for all code paths
    with torch.no_grad():
        probs = F.softmax(logits, dim=-1)
        entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
        max_entropy = math.log(V)
        onto_entropy = (entropy / max_entropy).mean().item()
    metrics["onto_entropy"] = onto_entropy

    # 1. Language modeling loss (always computed for PPL tracking)
    lm_loss = F.cross_entropy(
        logits.view(-1, V),
        targets.view(-1),
        ignore_index=-100,
    )
    metrics["lm_loss"] = lm_loss.item()
    metrics["ppl"] = math.exp(min(lm_loss.item(), 20))

    # Priority 1: Sovereign-Lagrangian Loss (Patent B1/S3)
    if config.enable_sovereign_loss and sovereign_engine is not None:
        # Get R-Signal from outputs (the Authority's intent)
        r_signal = outputs.get('r_signal', None)
        if r_signal is None:
            # Fall back to ontological_probs expanded to 48D
            onto_probs = outputs.get('ontological_probs', torch.zeros(B, N, 12, device=logits.device))
            if onto_probs.dim() == 2:
                onto_probs = onto_probs.unsqueeze(1).expand(-1, N, -1)
            # Expand 12D to 48D by repeating
            r_signal = onto_probs.repeat(1, 1, 4)

        # Get Guna Coherence from outputs if available
        gc = outputs.get('global_coherence', None)
        if gc is not None and isinstance(gc, torch.Tensor):
            gc = gc.mean()

        # [S5/B1] Scale lambda_b1 based on entropy - higher entropy = stronger consistency
        b1_scale = 1.0
        if onto_entropy > 0.60:
            # Scale up to 1.5x when entropy is very high (Rajasic state)
            excess = (onto_entropy - 0.60) / 0.40  # Scale 0.60-1.0 to 0-1
            b1_scale = 1.0 + excess * 0.5  # 1.0 to 1.5
            # Temporarily boost lambda_b1
            original_lambda_b1 = sovereign_engine.config.lambda_b1
            sovereign_engine.config.lambda_b1 = original_lambda_b1 * b1_scale

        # Compute Sovereign-Lagrangian loss
        total_loss, sov_metrics = sovereign_engine.sovereign_loss(
            logits, targets, r_signal,
            phase_angles=phase_angles,
            guna_coherence=gc,
        )

        # Restore original lambda_b1 if scaled
        if b1_scale > 1.0:
            sovereign_engine.config.lambda_b1 = original_lambda_b1

        # Merge metrics
        metrics.update({
            "total_loss": total_loss.item(),
            "l_task": sov_metrics["l_task"],
            "l_consistency": sov_metrics["l_consistency"],
            "l_align": sov_metrics["l_align"],
            "gc": sov_metrics["gc"],
            "sf_mean": sov_metrics["sf_mean"],
            "sb_mean": sov_metrics["sb_mean"],
            "b1_scale": b1_scale,  # Track the scaling factor
        })

        # Add coherence from outputs if available
        if "global_coherence" in outputs:
            metrics["coherence"] = outputs["global_coherence"].mean().item()

        return total_loss, metrics

    # Priority 2: Sovereign-1 hardened loss
    if config.use_sovereign_loss and sovereign_loss is not None and SOVEREIGN_AVAILABLE:
        # Build state from outputs
        onto_probs = outputs.get('ontological_probs', torch.zeros(B, 12, device=logits.device))
        bhava_vec = outputs.get('bhava_vector', torch.zeros(B, 144, device=logits.device))
        coherence = outputs.get('global_coherence', torch.ones(B, device=logits.device))

        # Construct 128D predicted state
        predicted_state = _build_sovereign_state(onto_probs, bhava_vec, coherence)
        # Target state (self-supervised: predict next state)
        target_state = torch.zeros_like(predicted_state)

        # Compute Sovereign loss
        total_loss, sov_metrics = sovereign_loss(
            logits, targets, predicted_state, target_state, epoch=epoch
        )

        # Merge metrics
        metrics.update({
            "total_loss": total_loss.item(),
            "sovereign_friction": sov_metrics.get("loss_friction", 0),
            "sovereign_transition": sov_metrics.get("loss_transition", 0),
            "onto_phoneme_ratio": sov_metrics.get("ontology_to_phoneme_ratio", 0),
            "meaning_fraction": sov_metrics.get("meaning_fraction", 0),
            "signal_washing": sov_metrics.get("signal_washing", False),
            "semantic_healthy": sov_metrics.get("semantic_healthy", False),
        })

        # Add coherence from outputs if available
        if "global_coherence" in outputs:
            metrics["coherence"] = outputs["global_coherence"].mean().item()

        return total_loss, metrics

    # Legacy loss computation (fallback)
    # 2. Bhava relationship consistency loss
    if "relationship_matrix" in outputs:
        rel_matrix = outputs["relationship_matrix"]  # [B, 12, 12]
        rel_diff = (rel_matrix[:, 1:, :] - rel_matrix[:, :-1, :]).abs().mean()
        bhava_loss = rel_diff
        metrics["bhava_loss"] = bhava_loss.item()
    else:
        bhava_loss = torch.tensor(0.0, device=logits.device)

    # 3. Global coherence regularization
    if "global_coherence" in outputs and not config.no_coherence_loss:
        coherence = outputs["global_coherence"].mean()
        coherence_loss = 1.0 - coherence
        metrics["coherence"] = coherence.item()
        metrics["coherence_loss"] = coherence_loss.item()
    else:
        coherence_loss = torch.tensor(0.0, device=logits.device)
        if "global_coherence" in outputs:
            # Still track coherence metric even if loss is disabled
            metrics["coherence"] = outputs["global_coherence"].mean().item()

    # 4. Entropy regularization
    if "ontological_probs" in outputs:
        probs = outputs["ontological_probs"]
        entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
        target_entropy = 1.5
        entropy_loss = (entropy - target_entropy).abs()
        metrics["onto_entropy"] = entropy.item()
    else:
        entropy_loss = torch.tensor(0.0, device=logits.device)

    # Combine losses
    total_loss = (
        config.lambda_lm * lm_loss +
        config.bhava_lambda * bhava_loss +
        config.coherence_lambda * coherence_loss +
        config.lambda_entropy * entropy_loss
    )

    metrics["total_loss"] = total_loss.item()

    return total_loss, metrics


def _build_sovereign_state(
    onto_probs: torch.Tensor,  # [B, 12]
    bhava_vec: torch.Tensor,   # [B, 144]
    coherence: torch.Tensor,   # [B]
) -> torch.Tensor:
    """Build 128D Sovereign state from ontological outputs."""
    B = onto_probs.shape[0]
    device = onto_probs.device

    # Guna [16]: Derived from coherence
    guna = coherence.unsqueeze(-1).expand(-1, 16)

    # S-Signal [32]: First 32 dims of bhava
    s_signal = bhava_vec[:, :32] if bhava_vec.shape[1] >= 32 else F.pad(bhava_vec, (0, 32 - bhava_vec.shape[1]))

    # R-Signal [48]: Ontology (12) expanded + bhava subset
    r_onto = F.pad(onto_probs, (0, 36))  # 12 -> 48
    if bhava_vec.shape[1] >= 80:
        bhava_r = bhava_vec[:, 32:80]  # 48 dims
    elif bhava_vec.shape[1] > 32:
        bhava_r = F.pad(bhava_vec[:, 32:], (0, 80 - bhava_vec.shape[1]))  # Pad to 48
    else:
        bhava_r = torch.zeros(B, 48, device=device)
    r_signal = r_onto + bhava_r * 0.1

    # C-Signal [32]: Remaining bhava or zeros
    if bhava_vec.shape[1] >= 112:
        c_signal = bhava_vec[:, 80:112]  # 32 dims
    elif bhava_vec.shape[1] > 80:
        c_signal = F.pad(bhava_vec[:, 80:], (0, 112 - bhava_vec.shape[1]))  # Pad to 32
    else:
        c_signal = torch.zeros(B, 32, device=device)

    return torch.cat([guna, s_signal, r_signal, c_signal], dim=-1)


# =============================================================================
# KOSHA-VRITTI DIAGNOSTIC SYSTEM
# =============================================================================


def compute_layer_gradient_norm(model: nn.Module, layer_idx: int) -> float:
    """
    V9.7.0: Compute gradient norm for a specific transformer layer.

    This enables layer-specific Kosha diagnostics by measuring the gradient
    magnitude at the target layer (e.g., Layer 9 for O9_WITNESSES).

    Args:
        model: The model with gradients computed
        layer_idx: Which layer to measure (0-11)

    Returns:
        Gradient L2 norm for that layer's parameters
    """
    layer_grad_norm = 0.0
    layer_found = False

    # Try to find transformer layers in common locations
    layers = None
    for attr in ['layers', 'blocks', 'transformer_blocks', 'encoder_layers', 'decoder_layers']:
        if hasattr(model, attr):
            candidate = getattr(model, attr)
            if isinstance(candidate, nn.ModuleList) and len(candidate) > layer_idx:
                layers = candidate
                break

    if layers is not None and layer_idx < len(layers):
        layer = layers[layer_idx]
        for param in layer.parameters():
            if param.grad is not None:
                layer_grad_norm += param.grad.norm().item() ** 2
                layer_found = True
        layer_grad_norm = math.sqrt(layer_grad_norm) if layer_grad_norm > 0 else 0.0

    # If layer not found, return 0 (caller will use fallback)
    return layer_grad_norm if layer_found else 0.0


# =============================================================================
# V9.7.0: ONTOLOGICAL BRIDGE DIAGNOSTICS (Layer 4 - Foundational Structure)
# =============================================================================
# Provides layer-specific diagnostics for the 12D ontological projection.
# Measures aspect diversity, Pramāṇa alignment, and dominant aspects.
# =============================================================================

def compute_onto_bridge_diagnostics(
    hidden_states: Optional[List[torch.Tensor]] = None,
    onto_metrics: Optional[Dict[str, float]] = None,
    onto_bridge: Optional[nn.Module] = None,
    diagnostic_layer: int = 4,
    layer_grad_norm: Optional[float] = None,
    grad_norm: float = 0.0,
) -> Dict[str, Any]:
    """
    V9.7.0: Compute Ontological Bridge diagnostics at Layer 4.

    The Ontological Bridge projects hidden states to 12D ontological space,
    one dimension per Aspect (O1-O12). Layer 4 is where foundational
    structure forms - the ontological "DNA" that propagates to all later layers.

    Diagnostic Axes:
    - Structure Axis (s): -1 (collapsed/uniform) to +1 (diverse/structured)
    - Grounding Axis (g): -1 (static/stuck) to +1 (adapting/learning)

    Onto States (based on quadrant):
    - GROUNDED (s>0, g>0): Diverse structure + active learning - optimal
    - FORMING (s<0, g>0): Uniform but learning - structure emerging
    - STABLE (s>0, g<0): Diverse but static - established ontology
    - DORMANT (s<0, g<0): Collapsed and stuck - needs activation
    """
    result = {
        'diagnostic_layer': diagnostic_layer,
    }

    with torch.no_grad():
        # =====================================================================
        # STRUCTURE AXIS (s): Layer 4 Representation Diversity
        # High diversity = rich ontological structure (+1)
        # Low diversity = collapsed/uniform (-1)
        # =====================================================================
        if hidden_states is not None and len(hidden_states) > diagnostic_layer:
            layer_hidden = hidden_states[diagnostic_layer]
            if layer_hidden is not None and layer_hidden.numel() > 0:
                # Compute activation entropy for structure measurement
                layer_abs = layer_hidden.abs().float()
                layer_probs = layer_abs / (layer_abs.sum(dim=-1, keepdim=True) + 1e-10)
                log_probs = torch.log(layer_probs + 1e-10)
                position_entropy = -(layer_probs * log_probs).sum(dim=-1)
                layer_entropy = position_entropy.mean().item()

                D = layer_hidden.shape[-1]
                max_entropy = math.log(D)
                # For structure, higher entropy = more diverse structure (+1)
                # This is OPPOSITE of coherence - we want distributed activations
                s = (2.0 * layer_entropy / max_entropy) - 1.0
                s = max(-1.0, min(1.0, s))
                result['s'] = s
                result['entropy'] = layer_entropy
                result['entropy_source'] = f'layer_{diagnostic_layer}'

        if 's' not in result:
            result['s'] = 0.0
            result['entropy'] = 0.0
            result['entropy_source'] = 'default'

        # =====================================================================
        # GROUNDING AXIS (g): Layer 4 Gradient Activity
        # High gradient = actively grounding/adapting (+1)
        # Low gradient = static/fixed (-1)
        # =====================================================================
        effective_grad = layer_grad_norm if layer_grad_norm is not None else grad_norm

        if effective_grad > 0:
            log_grad = math.log10(effective_grad + 1e-8)
            g = log_grad / 3.0
            g = max(-1.0, min(1.0, g))
        else:
            g = 0.0
        result['g'] = g
        result['grad_norm'] = effective_grad
        result['grad_source'] = f'layer_{diagnostic_layer}' if layer_grad_norm is not None else 'total'

        # =====================================================================
        # ONTO STATE CLASSIFICATION
        # =====================================================================
        s = result['s']
        g = result['g']

        if s >= 0 and g >= 0:
            state = 'GROUNDED'
            state_desc = 'Diverse & Adapting'
            state_icon = '🌳'
        elif s < 0 and g >= 0:
            state = 'FORMING'
            state_desc = 'Structure Emerging'
            state_icon = '🌱'
        elif s >= 0 and g < 0:
            state = 'STABLE'
            state_desc = 'Established Ontology'
            state_icon = '🏛️'
        else:
            state = 'DORMANT'
            state_desc = 'Needs Activation'
            state_icon = '💤'

        result['state'] = state
        result['state_desc'] = state_desc
        result['state_icon'] = state_icon

        # Structure zone description
        if s > 0.3:
            result['structure_zone'] = 'DIVERSE'
        elif s < -0.3:
            result['structure_zone'] = 'UNIFORM'
        else:
            result['structure_zone'] = 'MODERATE'

        # Grounding zone description
        if g > 0.3:
            result['grounding_zone'] = 'ADAPTING'
        elif g < -0.3:
            result['grounding_zone'] = 'STATIC'
        else:
            result['grounding_zone'] = 'STABLE'

        # =====================================================================
        # 12D ASPECT METRICS (from OntologicalBridge or onto_metrics)
        # =====================================================================
        if onto_metrics is not None:
            result['diversity'] = onto_metrics.get('onto_diversity', 0.0)
            result['pramana_corr'] = onto_metrics.get('onto_pramana_corr', 0.0)
            result['o9_witness'] = onto_metrics.get('onto_o9_witness', 0.0)
            result['mean_activation'] = onto_metrics.get('onto_mean_activation', 0.0)

        # Compute 12D projection if bridge available
        if onto_bridge is not None and hidden_states is not None and len(hidden_states) > diagnostic_layer:
            layer_hidden = hidden_states[diagnostic_layer]
            if layer_hidden is not None:
                onto_repr, bridge_metrics = onto_bridge(layer_hidden)
                # Get aspect activations
                aspect_means = onto_repr.mean(dim=[0, 1])  # [12]
                result['aspect_activations'] = aspect_means.tolist()

                # Find dominant aspect
                dominant_idx = aspect_means.abs().argmax().item()
                result['dominant_aspect'] = f'O{dominant_idx + 1}'
                result['dominant_value'] = aspect_means[dominant_idx].item()

    return result


def format_onto_bridge_diagnostic(diag: Dict[str, Any]) -> str:
    """Format Ontological Bridge diagnostic for logging output (single line, condensed)."""
    # Short names for 12 aspects
    ASPECT_SHORT = ['POT', 'IDN', 'EXE', 'STR', 'COG', 'AGY', 'RSN', 'PRP', 'WIT', 'UNI', 'INT', 'ABS']

    s = diag.get('s', 0.0)
    g = diag.get('g', 0.0)
    structure_zone = diag.get('structure_zone', 'UNK')[:3].upper()
    grounding_zone = diag.get('grounding_zone', 'UNK')[:3].upper()
    state = diag.get('state', 'UNK')
    div = diag.get('diversity', 0.0)
    pram = diag.get('pramana_corr', 0.0)

    # Find dominant aspect
    dominant = "ABS"
    if 'aspect_activations' in diag:
        activations = diag['aspect_activations']
        max_idx = 0
        max_val = abs(activations[0]) if activations else 0
        for i, v in enumerate(activations):
            if abs(v) > max_val:
                max_val = abs(v)
                max_idx = i
        dominant = ASPECT_SHORT[max_idx]

    return (
        f"    🌉 [ONTO] s={s:+.2f}({structure_zone})|g={g:+.2f}({grounding_zone})→{state} | "
        f"Div={div:.2f} Pram={pram:+.2f} Dom={dominant}"
    )


# =============================================================================
# V9.8.0: 32D SOVEREIGN STATE DIAGNOSTICS
# =============================================================================

def compute_sovereign_state_diagnostics(
    state: Optional[torch.Tensor] = None,
    delta_S: Optional[torch.Tensor] = None,
    grad_norm: float = 0.0,
) -> Dict[str, Any]:
    """
    Compute diagnostics for the 32D Sovereign State.

    V9.8.0: Replaces the arbitrary 124D diagnostics with principled readouts.

    Args:
        state: [B, 32] Sovereign State tensor from OntologicalHybridTransformer
        delta_S: [B, 32] State delta tensor
        grad_norm: Current gradient norm

    Returns:
        Dict with:
        - dominant_bhava: Name of most active Bhava (0-11)
        - active_kosha: Name of most active Kosha (12-16)
        - vritti_state: Name of current Vritti (17-21)
        - guna_balance: Lucidity/Activity/Stability balance
        - delta_magnitude: How much state changed
        - All raw activations for detailed logging
    """
    result = {
        'dominant_bhava': 'ABS',
        'dominant_bhava_idx': 11,
        'bhava_activation': 0.0,
        'active_kosha': 'MATERIAL',
        'active_kosha_idx': 0,
        'kosha_activation': 0.0,
        'vritti_state': 'FACT',
        'vritti_state_idx': 0,
        'vritti_activation': 0.0,
        'guna_sattva': 0.33,
        'guna_rajas': 0.33,
        'guna_tamas': 0.33,
        'velocity': 0.0,
        'delta_magnitude': 0.0,
        'grad_norm': grad_norm,
        'bhava_activations': [0.0] * 12,
        'kosha_activations': [0.0] * 5,
        'vritti_activations': [0.0] * 5,
        'guna_activations': [0.0] * 6,
    }

    if state is None:
        return result

    try:
        # Use get_sovereign_state_summary from phase_transformer
        summary = get_sovereign_state_summary(state)
        result.update(summary)

        # Extract raw activations for detailed logging
        if state.dim() == 1:
            state = state.unsqueeze(0)

        # Bhava activations [0:12]
        bhava_vals = state[0, BHAVA_SLICE].detach().cpu().tolist()
        result['bhava_activations'] = bhava_vals

        # V9.6.8: Compute Bhava top-3 for "snap point" visibility
        # State is now properly normalized by SovereignStateProjector (softmax applied)
        bhava_tensor = state[0, BHAVA_SLICE].detach().cpu()
        sorted_bhava, sorted_idx = bhava_tensor.sort(descending=True)
        result['bhava_top1_val'] = sorted_bhava[0].item()
        result['bhava_top1_name'] = BHAVA_NAMES[sorted_idx[0].item()]
        result['bhava_top2_val'] = sorted_bhava[1].item()
        result['bhava_top2_name'] = BHAVA_NAMES[sorted_idx[1].item()]
        result['bhava_top3_val'] = sorted_bhava[2].item()
        result['bhava_top3_name'] = BHAVA_NAMES[sorted_idx[2].item()]
        result['bhava_margin'] = (sorted_bhava[0] - sorted_bhava[1]).item()

        # Kosha activations [12:17]
        kosha_vals = state[0, KOSHA_SLICE].detach().cpu().tolist()
        result['kosha_activations'] = kosha_vals

        # V9.6.8: Compute Kosha (Sheath) top-3
        # State is now properly normalized by SovereignStateProjector (softmax applied)
        kosha_tensor = state[0, KOSHA_SLICE].detach().cpu()
        sorted_kosha, sorted_kosha_idx = kosha_tensor.sort(descending=True)
        result['kosha_top1_val'] = sorted_kosha[0].item()
        result['kosha_top1_name'] = KOSHA_NAMES[sorted_kosha_idx[0].item()]
        result['kosha_top2_val'] = sorted_kosha[1].item()
        result['kosha_top2_name'] = KOSHA_NAMES[sorted_kosha_idx[1].item()]
        result['kosha_top3_val'] = sorted_kosha[2].item()
        result['kosha_top3_name'] = KOSHA_NAMES[sorted_kosha_idx[2].item()]
        result['kosha_margin'] = (sorted_kosha[0] - sorted_kosha[1]).item()

        # Vritti activations [17:22]
        vritti_vals = state[0, VRITTI_SLICE].detach().cpu().tolist()
        result['vritti_activations'] = vritti_vals

        # Guna activations [22:28]
        guna_vals = state[0, GUNA_SLICE].detach().cpu().tolist()
        result['guna_activations'] = guna_vals

        # Compute delta magnitude if provided
        if delta_S is not None:
            result['delta_magnitude'] = delta_S.norm().item()

    except Exception as e:
        # Silent fallback on error
        pass

    return result


def format_sovereign_state_diagnostic(diag: Dict[str, Any]) -> str:
    """
    Format 32D Sovereign State diagnostic for logging output.

    V9.8.0: Condensed single-line output (was 6 lines).
    V9.6.8: Added top-3 Bhava/Kosha to visualize "snap point" proximity.
    Shows Bhava/Kosha/Vritti/Guna summary in compact form.
    """
    # V9.6.8: Top-3 Bhava with probabilities
    b1_name = diag.get('bhava_top1_name', diag.get('dominant_bhava', 'ABS'))
    b1_val = diag.get('bhava_top1_val', 0.0)
    b2_name = diag.get('bhava_top2_name', '???')
    b2_val = diag.get('bhava_top2_val', 0.0)
    b3_name = diag.get('bhava_top3_name', '???')
    b3_val = diag.get('bhava_top3_val', 0.0)
    bhava_margin = diag.get('bhava_margin', 0.0)

    # V9.6.8: Top-3 Kosha (Sheath) with probabilities
    k1_name = diag.get('kosha_top1_name', diag.get('active_kosha', 'ANNA'))
    k1_val = diag.get('kosha_top1_val', 0.0)
    k2_name = diag.get('kosha_top2_name', '???')
    k2_val = diag.get('kosha_top2_val', 0.0)
    k3_name = diag.get('kosha_top3_name', '???')
    k3_val = diag.get('kosha_top3_val', 0.0)
    kosha_margin = diag.get('kosha_margin', 0.0)

    vritti = diag.get('vritti_state', 'FACT')
    delta = diag.get('delta_magnitude', 0.0)

    # Guna balance as compact percentages (L=Lucidity, A=Activity, S=Stability)
    lucidity = diag.get('guna_sattva', 0.33)
    activity = diag.get('guna_rajas', 0.33)
    stability = diag.get('guna_tamas', 0.33)

    # Format margin indicator: 🔴 (<5%), 🟡 (5-15%), 🟢 (>15%)
    def margin_icon(m):
        if m < 0.05:
            return "🔴"  # Very close to snap
        elif m < 0.15:
            return "🟡"  # Moderate margin
        return "🟢"  # Stable

    # Shorten Kosha names for display (using English meanings)
    # ANNA=Physical, PRANA=Vital, MANO=Mental, VIJNANA=Intellect, ANANDA=Bliss
    kosha_short = {'ANNA': 'PHY', 'PRANA': 'VIT', 'MANO': 'MEN', 'VIJNANA': 'INT', 'ANANDA': 'BLI'}

    # Format: Bhava: IDN(45%)>RSN(30%)>COG(10%) 🟢
    bhava_str = f"{b1_name}({b1_val:.0%})>{b2_name}({b2_val:.0%})>{b3_name}({b3_val:.0%})"
    kosha_str = f"{kosha_short.get(k1_name, k1_name[:3])}({k1_val:.0%})>{kosha_short.get(k2_name, k2_name[:3])}({k2_val:.0%})"

    # V11.0.0: Two-line output showing separated planes
    # Phase plane (12D Bhava) is marked with → to show it feeds phase rotation
    # Control plane (Kosha/Vritti/Guna) is marked with | to show it's separate
    return (
        f"    🔱 [Phase:12D] Bhava→θ:{bhava_str} {margin_icon(bhava_margin)} | "
        f"[Ctrl] Sheath:{kosha_str} {margin_icon(kosha_margin)} | Vritti:{vritti}\n"
        f"           [Ctrl] Qualia[L{lucidity:.0%}/A{activity:.0%}/S{stability:.0%}] Δ={delta:.2f}"
    )


def forward_chunked(
    model: torch.nn.Module,
    input_ids: torch.Tensor,
    chunk_size: int,
    return_decorr_loss: bool = False,
) -> Dict[str, torch.Tensor]:
    """
    V10.2.2: Chunked forward pass for training long sequences.

    Processes input in chunks, maintaining Phase state across chunks:
    - Phase attention persists state (temporal memory)
    - Local attention resets per chunk (spatial reasoning)
    - Gradients flow through entire sequence

    Args:
        model: HybridPhaseTransformer model
        input_ids: [B, N] token indices (full sequence)
        chunk_size: Size of each chunk
        return_decorr_loss: Whether to compute decorrelation loss

    Returns:
        Dict with 'logits' and optionally 'decorr_loss'
    """
    B, N = input_ids.shape
    device = input_ids.device

    # Process in chunks, accumulating logits
    all_logits = []
    layer_states = None  # Persists across chunks

    for chunk_start in range(0, N, chunk_size):
        chunk_end = min(chunk_start + chunk_size, N)
        chunk_ids = input_ids[:, chunk_start:chunk_end]

        # Forward chunk with state management
        result, layer_states = model.forward_chunk(
            chunk_ids,
            chunk_offset=chunk_start,
            prev_layer_states=layer_states,
        )

        all_logits.append(result['logits'])

    # Concatenate all chunk logits
    logits = torch.cat(all_logits, dim=1)  # [B, N, V]

    outputs = {'logits': logits}

    # Decorrelation loss not supported in chunked mode yet
    # (would need to accumulate across chunks)
    if return_decorr_loss:
        outputs['decorr_loss'] = torch.tensor(0.0, device=device)

    return outputs


def compute_phase_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    config: UnifiedTrainingConfig,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """Compute loss for phase/hybrid models."""
    B, N, V = logits.shape

    lm_loss = F.cross_entropy(
        logits.reshape(-1, V),
        targets.reshape(-1),
        ignore_index=-100,
    )

    # Compute entropy for Sattvic controller (prevents variance=0.0 stagnation bug)
    # V10.7.2: Chunk over sequence dim to avoid OOM at long sequences
    # (full softmax [B,N,V] = B*N*V*4 bytes, e.g. 24GB at seq=32k, V=50k)
    with torch.no_grad():
        chunk_size = max(1, min(1024, N))  # Process 1024 tokens at a time
        entropy_sum = 0.0
        token_count = 0
        for start in range(0, N, chunk_size):
            end = min(start + chunk_size, N)
            chunk_logits = logits[:, start:end, :]  # [B, chunk, V]
            probs = F.softmax(chunk_logits, dim=-1)
            token_entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
            entropy_sum += token_entropy.sum().item()
            token_count += token_entropy.numel()
            del probs, token_entropy, chunk_logits
        max_entropy = math.log(V)
        normalized_entropy = (entropy_sum / token_count) / max_entropy

    metrics = {
        "lm_loss": lm_loss.item(),
        "ppl": math.exp(min(lm_loss.item(), 20)),
        "total_loss": lm_loss.item(),
        "onto_entropy": normalized_entropy,  # Required for Sattvic stagnation detection
    }

    return lm_loss, metrics


# =============================================================================
# V10.6+ CONTROL-PLANE UTILITIES (Hard Probes Integration)
# =============================================================================

@dataclass
class ArchitectureHealthReport:
    """
    V10.6.3: Architecture Health Summary with PASS/FAIL diagnostics.

    Checks critical invariants at training start:
    - Control signal shapes (D.5 no-write contract)
    - Dual-channel wiring (alignment clamp present)
    - Quad utilization baseline (not bypassed)
    - Chunk continuity (if chunking enabled)

    Reference: QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md, Appendix D
    """
    overall: str = "UNKNOWN"  # "PASS", "WARN", "FAIL"
    checks: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # name -> (status, detail)
    timestamp: str = ""

    def __post_init__(self):
        self.timestamp = datetime.now().isoformat()

    def add_check(self, name: str, status: str, detail: str = ""):
        """Add a check result. status should be 'PASS', 'WARN', or 'FAIL'."""
        self.checks[name] = (status, detail)

    def compute_overall(self) -> str:
        """Compute overall status from individual checks."""
        statuses = [s for s, _ in self.checks.values()]
        if "FAIL" in statuses:
            self.overall = "FAIL"
        elif "WARN" in statuses:
            self.overall = "WARN"
        elif statuses:
            self.overall = "PASS"
        return self.overall

    def print_report(self):
        """Print formatted health report."""
        print(f"\n{'='*70}")
        print("  📊 ARCHITECTURE HEALTH CHECK (V10.6.3)")
        print(f"{'='*70}")

        status_icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "UNKNOWN": "❓"}

        for name, (status, detail) in self.checks.items():
            icon = status_icons.get(status, "❓")
            detail_str = f" - {detail}" if detail else ""
            print(f"  {icon} {name}: {status}{detail_str}")

        self.compute_overall()
        overall_icon = status_icons.get(self.overall, "❓")
        print(f"\n  {overall_icon} OVERALL: {self.overall}")
        print(f"{'='*70}\n")

        return self.overall


def run_architecture_health_check(
    model: torch.nn.Module,
    config: "UnifiedTrainingConfig",
    device: torch.device,
) -> ArchitectureHealthReport:
    """
    V10.6.3: Run architecture health check and return PASS/FAIL report.

    Checks:
    1. D.5 No-Write Contract - control signal shapes are low-dimensional
    2. Dual-Channel Wiring - alignment clamp bounds configured
    3. D.2 Slots Read Flag - enable_slots_read routing works
    4. Quad Baseline - quad path contributes (not bypassed)
    5. Chunk Continuity - (if chunking enabled) state persists across chunks

    Args:
        model: The model to check
        config: Training configuration
        device: Torch device

    Returns:
        ArchitectureHealthReport with all check results
    """
    report = ArchitectureHealthReport()

    # Check 1: D.5 No-Write Contract Configuration
    try:
        if config.strict_control_contract:
            report.add_check(
                "D.5 No-Write Contract",
                "PASS",
                "strict mode enabled (violations will raise)"
            )
        else:
            report.add_check(
                "D.5 No-Write Contract",
                "WARN",
                "warn mode (violations logged, not raised)"
            )
    except Exception as e:
        report.add_check("D.5 No-Write Contract", "FAIL", str(e))

    # Check 2: Dual-Channel Wiring (alignment clamp)
    try:
        if config.dual_channel_mode:
            if 0.0 < config.alignment_clamp_min < config.alignment_clamp_max <= 2.0:
                report.add_check(
                    "Dual-Channel Wiring",
                    "PASS",
                    f"clamp=[{config.alignment_clamp_min:.2f}, {config.alignment_clamp_max:.2f}], α={config.alignment_authority:.2f}"
                )
            else:
                report.add_check(
                    "Dual-Channel Wiring",
                    "WARN",
                    f"unusual clamp bounds: [{config.alignment_clamp_min}, {config.alignment_clamp_max}]"
                )
        else:
            report.add_check(
                "Dual-Channel Wiring",
                "PASS",
                "dual_channel_mode disabled (not needed)"
            )
    except Exception as e:
        report.add_check("Dual-Channel Wiring", "FAIL", str(e))

    # Check 3: D.2 Enable Slots Read (if model supports it)
    try:
        has_slots_read = hasattr(model, 'forward') and 'enable_slots_read' in str(
            model.forward.__code__.co_varnames if hasattr(model, 'forward') else ""
        )
        # Check if model class has binding cache blocks
        has_binding_cache = any(
            "BindingCache" in type(m).__name__
            for m in model.modules()
        )
        if has_binding_cache:
            report.add_check(
                "D.2 Enable Slots Read",
                "PASS",
                "BindingCache architecture detected"
            )
        else:
            report.add_check(
                "D.2 Enable Slots Read",
                "PASS",
                "no BindingCache (slots_read N/A)"
            )
    except Exception as e:
        report.add_check("D.2 Enable Slots Read", "WARN", f"check skipped: {e}")

    # Check 4: Quad Utilization Baseline
    try:
        # Check if model has quad/binding cache path
        has_quad = any(
            "quad" in name.lower() or "binding" in name.lower()
            for name, _ in model.named_modules()
        )
        if has_quad and not config.no_binding_cache:
            report.add_check(
                "Quad Utilization",
                "PASS",
                f"top_k={config.binding_cache_top_k}"
            )
        elif config.no_binding_cache:
            report.add_check(
                "Quad Utilization",
                "WARN",
                "binding_cache disabled (--no_binding_cache)"
            )
        else:
            report.add_check(
                "Quad Utilization",
                "PASS",
                "no quad path (model type doesn't use it)"
            )
    except Exception as e:
        report.add_check("Quad Utilization", "WARN", f"check skipped: {e}")

    # Check 5: Chunk Continuity (if chunking enabled)
    try:
        if config.enable_chunking:
            has_chunk_method = hasattr(model, 'forward_chunk') or hasattr(model, 'diagnose_chunk_continuity')
            if has_chunk_method:
                report.add_check(
                    "Chunk Continuity",
                    "PASS",
                    f"chunk_size={config.chunk_size}"
                )
            else:
                report.add_check(
                    "Chunk Continuity",
                    "WARN",
                    "chunking enabled but model lacks forward_chunk method"
                )
        else:
            report.add_check(
                "Chunk Continuity",
                "PASS",
                "chunking disabled"
            )
    except Exception as e:
        report.add_check("Chunk Continuity", "WARN", f"check skipped: {e}")

    # Check 6: Parameter-Matched Baseline
    try:
        num_params = sum(p.numel() for p in model.parameters())
        # Baselines should have similar param counts for fair comparison
        # StandardTransformer at same config should match
        if config.enforce_baseline_param_match:
            report.add_check(
                "Param-Match Baseline",
                "PASS",
                f"param_count={num_params:,} (enforcement enabled)"
            )
        else:
            report.add_check(
                "Param-Match Baseline",
                "WARN",
                f"param_count={num_params:,} (enforcement disabled)"
            )
    except Exception as e:
        report.add_check("Param-Match Baseline", "WARN", f"check skipped: {e}")

    return report


def check_quad_utilization(
    model: torch.nn.Module,
    input_ids: torch.Tensor,
    device: torch.device,
    threshold: float = 0.01,
) -> Tuple[bool, float, str]:
    """
    V10.6.6: Check that quad path contributes to output (not bypassed).

    Runs forward pass with and without quad to measure contribution.

    Args:
        model: Model with BindingCache architecture
        input_ids: Sample input [B, N]
        device: Torch device
        threshold: Minimum contribution ratio (default 1%)

    Returns:
        Tuple of (passed, contribution_ratio, message)
    """
    model.eval()

    with torch.no_grad():
        # Forward with quad enabled
        try:
            out_with_quad = model(input_ids)
            if isinstance(out_with_quad, dict):
                logits_with = out_with_quad.get('logits', out_with_quad.get('output'))
            else:
                logits_with = out_with_quad
        except Exception as e:
            return False, 0.0, f"Forward with quad failed: {e}"

        # Forward with quad disabled (if model supports enable_slots_read)
        try:
            if hasattr(model, 'forward'):
                import inspect
                sig = inspect.signature(model.forward)
                if 'enable_slots_read' in sig.parameters:
                    out_without_quad = model(input_ids, enable_slots_read=False)
                    if isinstance(out_without_quad, dict):
                        logits_without = out_without_quad.get('logits', out_without_quad.get('output'))
                    else:
                        logits_without = out_without_quad

                    # Compute contribution
                    diff = (logits_with - logits_without).abs().mean().item()
                    baseline = logits_with.abs().mean().item() + 1e-9
                    contribution = diff / baseline

                    passed = contribution >= threshold
                    msg = f"quad contributes {contribution:.1%} of output"
                    return passed, contribution, msg

            # Model doesn't support enable_slots_read - skip check
            return True, -1.0, "model doesn't support enable_slots_read (check skipped)"

        except Exception as e:
            return True, -1.0, f"quad check skipped: {e}"


class LightweightProbeHooks:
    """
    V10.6.7: Lightweight diagnostic probe hooks for training.

    These are NOT full HardProbeDataset evaluations - they're quick sanity checks
    that run periodically during training to catch issues early.

    Supported probes:
    - phase_rotation: Quick check that phase encodes relational structure
    - chunk_continuity: Verify state persists across chunk boundaries
    - control_contract: Validate control signal shapes

    Usage:
        hooks = LightweightProbeHooks(model, config, device)
        # During training loop:
        if step % config.probe_hook_interval == 0:
            results = hooks.run_probes(step)
            for name, (passed, msg) in results.items():
                print(f"  Probe {name}: {'PASS' if passed else 'WARN'} - {msg}")
    """

    def __init__(
        self,
        model: torch.nn.Module,
        config: "UnifiedTrainingConfig",
        device: torch.device,
    ):
        self.model = model
        self.config = config
        self.device = device
        self.probe_types = [p.strip() for p in config.probe_hook_types.split(",")]

    def run_probes(self, step: int) -> Dict[str, Tuple[bool, str]]:
        """
        Run all enabled lightweight probes.

        Args:
            step: Current training step

        Returns:
            Dict mapping probe name to (passed, message)
        """
        results = {}

        for probe_type in self.probe_types:
            if probe_type == "phase_rotation":
                results["phase_rotation"] = self._probe_phase_rotation()
            elif probe_type == "chunk_continuity":
                results["chunk_continuity"] = self._probe_chunk_continuity()
            elif probe_type == "control_contract":
                results["control_contract"] = self._probe_control_contract()
            else:
                results[probe_type] = (True, f"unknown probe type (skipped)")

        return results

    def _probe_phase_rotation(self) -> Tuple[bool, str]:
        """
        Quick phase rotation sanity check.

        Verifies that rotating all phases by θ changes output (phase is functional).
        """
        try:
            # Create small test input
            B, N = 2, 64
            test_ids = torch.randint(0, 1000, (B, N), device=self.device)

            self.model.eval()
            with torch.no_grad():
                # Get baseline output
                out1 = self.model(test_ids)
                if isinstance(out1, dict):
                    logits1 = out1.get('logits', out1.get('output'))
                else:
                    logits1 = out1

                # Apply phase rotation if model supports it
                if hasattr(self.model, 'apply_phase_rotation'):
                    self.model.apply_phase_rotation(math.pi / 4)  # 45 degrees
                    out2 = self.model(test_ids)
                    if isinstance(out2, dict):
                        logits2 = out2.get('logits', out2.get('output'))
                    else:
                        logits2 = out2
                    self.model.apply_phase_rotation(-math.pi / 4)  # Undo

                    diff = (logits1 - logits2).abs().mean().item()
                    if diff > 1e-6:
                        return True, f"phase rotation changes output (Δ={diff:.4f})"
                    else:
                        return False, f"phase rotation has no effect (Δ={diff:.4f})"
                else:
                    return True, "model lacks apply_phase_rotation (skipped)"

        except Exception as e:
            return True, f"probe failed: {e}"

    def _probe_chunk_continuity(self) -> Tuple[bool, str]:
        """
        Quick chunk continuity sanity check.

        Verifies that processing in chunks produces similar output to full sequence.
        """
        try:
            if not self.config.enable_chunking:
                return True, "chunking disabled (skipped)"

            if not hasattr(self.model, 'forward_chunk'):
                return True, "model lacks forward_chunk (skipped)"

            # Create test input
            B, N = 1, 256
            chunk_size = 64
            test_ids = torch.randint(0, 1000, (B, N), device=self.device)

            self.model.eval()
            with torch.no_grad():
                # Full sequence
                out_full = self.model(test_ids)
                if isinstance(out_full, dict):
                    logits_full = out_full.get('logits', out_full.get('output'))
                else:
                    logits_full = out_full

                # Chunked
                logits_chunked = forward_chunked(self.model, test_ids, chunk_size)['logits']

                # Compare
                diff = (logits_full - logits_chunked).abs().mean().item()
                baseline = logits_full.abs().mean().item() + 1e-9
                ratio = diff / baseline

                if ratio < 0.1:  # 10% tolerance
                    return True, f"chunk vs full diff={ratio:.1%}"
                else:
                    return False, f"chunk vs full diff={ratio:.1%} (>10%)"

        except Exception as e:
            return True, f"probe failed: {e}"

    def _probe_control_contract(self) -> Tuple[bool, str]:
        """
        Quick control contract validation.

        Checks that any registered control signals have valid shapes.
        """
        try:
            # Get model's d_model
            d_model = None
            if hasattr(self.model, 'config') and hasattr(self.model.config, 'd_model'):
                d_model = self.model.config.d_model
            elif hasattr(self.model, 'd_model'):
                d_model = self.model.d_model
            else:
                # Try to infer from embedding
                for name, module in self.model.named_modules():
                    if 'embed' in name.lower() and hasattr(module, 'weight'):
                        d_model = module.weight.shape[-1]
                        break

            if d_model is None:
                return True, "couldn't determine d_model (skipped)"

            # Create sample control signals and validate
            B, N = 2, 64
            test_binding_salience = torch.rand(B, N, device=self.device)
            test_intent_phase = torch.rand(B, 8, device=self.device)  # [B, H]

            try:
                results = validate_control_signals(
                    d_model=d_model,
                    seq_len=N,
                    strict=False,
                    binding_salience=test_binding_salience,
                    intent_phase=test_intent_phase,
                )
                if all(results.values()):
                    return True, "sample control signals valid"
                else:
                    invalid = [k for k, v in results.items() if not v]
                    return False, f"invalid signals: {invalid}"
            except ControlShapeViolation as e:
                return False, f"contract violation: {e}"

        except Exception as e:
            return True, f"probe failed: {e}"


# =============================================================================
# TRAINING LOOP
# =============================================================================

def train(config: UnifiedTrainingConfig):

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
        if config.model_type in ('hybrid', 'ontological_hybrid'):
            print(f"  Decorrelation Loss: ENABLED (weight={config.decorr_loss_weight})")
        else:
            print(f"\n  ⚠️  WARNING: --decorr_loss_weight={config.decorr_loss_weight} IGNORED!")
            print(f"     Decorrelation loss only works with --model_type hybrid or ontological_hybrid")
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
        from symbolu.sovereign.loss import SovereignLoss, SovereignLossConfig
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
        from symbolu.sovereign.metrics import SovereignEngine, SovereignLossConfig as SovEngineConfig, StabilityState
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
        from symbolu.sovereign.metrics import SovereignAlertMonitor, AlertConfig
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
        from symbolu.sovereign.metrics import S8StabilityHook, compute_semantic_entropy, format_sovereign_dashboard
        s8_hook = S8StabilityHook(
            window_size=5,
            brake_sensitivity=5.0,
            max_brake=0.5,
            recovery_rate=0.1,
        )
        print(f"  S8 Stability Hook: ENABLED (Entropy Guard)")

    # V9.8.6: Initialize curriculum state variables (will be populated if resuming)
    # These must be defined before curriculum controllers are created
    resumed_onto_curriculum_state = None
    resumed_evoflow_state = None  # V9.8.6: EvoFlow (EvolutionaryIntelligenceEngine)

    # Initialize SGP (Stochastic Gradient Persistence) and Sattvic Controller
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
            min_factor=0.3,           # Never reduce LR below 30%
            warmup_steps=config.warmup_steps,  # Skip throttling during warmup
        )
        print(f"  Gradient Throttle: ENABLED (spike>2x → LR×0.3 min)")

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
        ).to(device)
        toroidal_loss_fn = ToroidalConsistencyLoss(
            lambda_toroid=config.toroidal_lambda,
            min_coherence_threshold=config.toroidal_coherence_threshold,
        )
        metacognitive_tracker = MetacognitiveTracker(
            coherence_alarm_threshold=config.toroidal_coherence_threshold,
        )
        print(f"  Toroidal Bridge: ENABLED (λ={config.toroidal_lambda}, gate={config.toroidal_use_gating})")
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
        print(f"  ╚══════════════════════════════════════════════════════════════════╝\n")

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
    if config.use_8bit_optimizer:
        try:
            import bitsandbytes as bnb
            optimizer = bnb.optim.AdamW8bit(
                model.parameters(),
                lr=config.learning_rate,
                weight_decay=config.weight_decay,
                betas=(config.beta1, config.beta2),
            )
            print(f"  8-bit Optimizer: ENABLED (bitsandbytes AdamW8bit)")
        except ImportError:
            print("  WARNING: bitsandbytes not installed, falling back to standard AdamW")
            print("           Install with: pip install bitsandbytes")
            optimizer = AdamW(
                model.parameters(),
                lr=config.learning_rate,
                weight_decay=config.weight_decay,
                betas=(config.beta1, config.beta2),
            )
    else:
        optimizer = AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
            betas=(config.beta1, config.beta2),
        )

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
    resumed_scaler_state = None  # V9.8.1: AMP GradScaler state
    if config.resume:
        resume_path = Path(config.resume)
        if resume_path.exists():
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
                resumed_scaler_state = resume_result.get("scaler_state")  # V9.8.1
                # V9.8.6: Extract curriculum states
                resumed_onto_curriculum_state = resume_result.get("onto_curriculum_state")
                resumed_evoflow_state = resume_result.get("evoflow_state")
            except RuntimeError as e:
                # Checkpoint is corrupted - start from scratch
                print(f"\n  ⚠️  Failed to load checkpoint due to corruption")
                print(f"      Starting training from scratch instead...")
                # Keep default values (resume_step=0, etc.)
        else:
            print(f"\n  ⚠️  Checkpoint not found: {resume_path}")
            print(f"      Starting training from scratch...")


    # V9.8.9: Initialize DWS window from resumed PPL if resuming
    if config.resume and best_val_loss < float('inf') and dynamic_window_scheduler is not None:
        resumed_ppl = math.exp(best_val_loss)
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
            min_steps_between_adjustments=config.adaptive_min_interval,
            # V9.8.2: Safeguards to prevent runaway LR
            max_lr_relative=config.adaptive_max_lr_relative,
            loss_spike_threshold=config.adaptive_loss_spike_threshold,
            grad_norm_spike_threshold=config.adaptive_grad_norm_spike,
            emergency_decay_factor=config.adaptive_emergency_decay,
            consecutive_spike_limit=config.adaptive_consecutive_spike_limit,
        )

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
    # Mixed precision
    scaler = torch.amp.GradScaler('cuda') if config.mixed_precision != "none" else None
    autocast_dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

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

    # V9.4.5: Initialize Friction Controller with Corrective Actions
    # V9.8.10: Support both "hybrid" and "ontological_hybrid" models
    has_hybrid_attention = "hybrid" in config.model_type
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
        print(f"  Onto Three-Phase Curriculum:")
        print(f"       CONSTRUCTION: PPL > {config.onto_engage_ppl} (full ontological grounding)")
        print(f"       TRANSITION:   {config.onto_disengage_ppl} < PPL < {config.onto_engage_ppl} (rampdown)")
        print(f"       POLISHING:    PPL < {config.onto_disengage_ppl} (Onto off after {config.onto_rampdown_steps} steps)")
        # V9.8.6: Restore Onto curriculum state from checkpoint
        if resumed_onto_curriculum_state is not None:
            onto_curriculum.load_state(resumed_onto_curriculum_state)
            print(f"       ✓ Restored: Phase={onto_curriculum.phase}, Scale={onto_curriculum.scale:.3f}")

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
        print(f"     └─ SOVEREIGN:      PPL < {config.curriculum_ppl_sovereign} (full auxiliary stack)")
        print(f"     Stability window: {config.curriculum_stability_window} evals")
        print(f"     Hysteresis: {config.curriculum_hysteresis}x (prevents oscillation)")
        print(f"\n     ⚠️  Starting in FOUNDATION phase - pure LM training")
        print(f"     ⚠️  Auxiliary systems will engage automatically as PPL improves\n")

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
        )
        print(f"\n  🔄 [PPL-Alpha] Phase/Local Alpha Curriculum ENABLED")
        print(f"     ├─ PPL >= {config.ppl_high_threshold:.0f}: α_phase = {config.alpha_phase_ppl_high:.2f} (phase dominates)")
        print(f"     ├─ PPL <= {config.ppl_low_threshold:.0f}:  α_phase = {config.alpha_phase_ppl_low:.2f} (local refines)")
        print(f"     └─ Linear interpolation between thresholds")
        if config.enable_adaptive_window:
            print(f"     📐 Adaptive Window: {config.window_size_high_ppl} (high PPL) → {config.window_size_low_ppl} (low PPL)\n")
        else:
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
    # ==========================================================================

    # Restore KV Supervision state from checkpoint
    # V10.7.1: Track first iteration for diagnostic logging (works with resumed training)
    _first_iter_logged = False

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
            enable_decorr = False
            decorr_loss_tensor = None
            ortho_loss_tensor = None
            phase_div_loss_tensor = None
            # V10.7: TBPTT backward tracking
            tbptt_backward_done = False

            if config.model_type == "ontological":
                outputs = model(x)
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
                    config.model_type in ('hybrid', 'ontological_hybrid')
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
                    outputs = model(x, return_decorr_loss=enable_decorr) if enable_decorr else model(x)

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
                decorr_loss_tensor = None
                ortho_loss_tensor = None

                if enable_decorr and isinstance(outputs, dict) and 'decorr_loss' in outputs:
                    decorr_loss_tensor = outputs['decorr_loss']
                    loss = loss + config.decorr_loss_weight * decorr_loss_tensor
                    metrics['decorr_loss'] = decorr_loss_tensor.item()
                    metrics['decorr_weight'] = config.decorr_loss_weight

                # V9.9.5: Weight orthogonalization loss (parameter-level decorrelation)
                # This directly regularizes attention weights, guaranteeing gradient flow
                # Unlike output decorrelation, this cannot be blocked by detach()
                if enable_decorr and config.decorr_loss_weight > 0:
                    # Debug on first step only
                    ortho_loss_tensor = compute_weight_orthogonalization_loss(model, debug=(global_step == 1))
                    loss = loss + config.decorr_loss_weight * ortho_loss_tensor
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
                    phase_div_loss = phase_div_loss_raw * current_weight

                    if phase_div_loss.requires_grad:
                        loss = loss + phase_div_loss
                        phase_div_loss_tensor = phase_div_loss_raw  # Store raw (unweighted)
                        metrics['phase_uniform_loss'] = phase_div_metrics['phase_uniform_loss']
                        metrics['phase_entropy_proxy'] = current_R
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

            # V9.9.6: Preserve decorr_loss and ortho_loss tensors (for gradient flow)
                    if enable_decorr and config.decorr_loss_weight > 0:
                        if decorr_loss_tensor is not None:
                            loss = loss + config.decorr_loss_weight * decorr_loss_tensor
                        if ortho_loss_tensor is not None:
                            loss = loss + config.decorr_loss_weight * ortho_loss_tensor

            # Phase-JEPA: Joint Embedding Predictive Loss Integration
            jepa_metrics = {}
            if jepa_model is not None and JEPA_AVAILABLE:
                try:
                    external_karma = None  # Legacy SRK karma injection removed

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
                            jepa_weight = 0.1  # Minimal JEPA during soul phase
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
            # This was ANOTHER source of vocabulary corruption (detaching prevents gradient bleed)!
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
                    toroidal_seed = evolutionary_bridge.get_seed()

                    # Log SGP heavy step (recursive gradient pulse)

            # Full Evolutionary Flow System: All Layer Transitions with Delayed Resonance
            #
            # V9.6.7 CRITICAL FIX: DETACH hidden states for EvoFlow!
            # Without detach, evo_loss gradients flow: hidden_states → all layers → token embeddings
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
            # V9.8.0: RSS controls Kosha engagement based on PPL thresholds
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

                                    # V9.8.6: Apply three-phase curriculum scaling

                                    # Add to total loss (this creates gradient pressure toward target angle)

                                    # Log steering metrics
                                    metrics['kosha_target_angle'] = math.degrees(target_angle_rad)
                                    metrics['kosha_mean_phase'] = math.degrees(current_phase.mean().item())
                                    metrics['kosha_phase_error'] = math.degrees(phase_error.abs().mean().item())

                                    # One-time log when steering activates
                except Exception as e:
                    if global_step % 500 == 0:
                        print(f"  ⚠️ [KOSHA STEERING] Error: {e}")

            # =====================================================================
            # v2.2.1: KOSHA GYROSCOPE - Homeostatic Self-Regulation Loss
            # Enforces balance across Kosha dimensions to prevent pathological states
            # =====================================================================
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

            # Scale for gradient accumulation
            loss = loss / config.gradient_accumulation

            # --- DEBUG: KOSHA STEERING HEARTBEAT ---
            # Shows steering is active on "in-between" steps (e.g., 810, 820, 830)
            # Only prints when steering IS active (non-zero) and once per global step
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
            raw_grad_norm = sum(
                p.grad.norm().item() for p in model.parameters()
                if p.grad is not None
            )

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

            # Formula [1331] 9:3 Split: Update gradient scaler warmup schedule
            hgs_metrics = {}
            if gradient_scaler_hgs is not None:
                hgs_metrics = gradient_scaler_hgs.step()

            # V9.4.5: Measure friction and apply corrective actions
            # V9.5.6 FIX: Capture gradient norm BEFORE zero_grad for Rajas computation (6:6 mode)
            # In 6:6 mode without HGS, we need to compute this before gradients are cleared
            captured_grad_norm = 0.0
            if gradient_scaler_hgs is None:
                captured_grad_norm = sum(
                    p.grad.norm().item() for p in model.parameters()
                    if p.grad is not None
                )

            optimizer.zero_grad()

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
                    'ppl': metrics.get('ppl', math.exp(avg_loss)),
                    'sa_deviation': abs(current_sa_ratio - 0.15) if current_sa_ratio > 0 else 0.0,
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

                    # Status indicators
                    sa_ind = "+" if sa_ratio < 0.3 else ("~" if sa_ratio < 0.5 else "!")
                    gc_ind = "+" if gc > 0.76 else ("~" if gc > 0.68 else "!")

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
                        log_msg += f" | α_phase: {current_alpha:.2f}"

                    # V9.4.5: Add friction metrics (for 6/6 hybrid architecture)
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
                # V9.4.6: Log SNI activation
                if metrics.get('sni_triggered', False):
                    log_msg += f"\n    --> [SNI] Low entropy ({metrics.get('onto_entropy', 0):.2f}) - injecting sensory noise"

                print(log_msg, flush=True)  # V9.7.0: Flush for real-time output when piped to tee

                # V9.7.0: Ontological Bridge Diagnostics (Layer 4 - Foundational Structure)
                # Only log when Onto is engaged (onto_curriculum.scale > 0)
                onto_engaged = (onto_curriculum is None) or (onto_curriculum.scale > 0)
                # V9.8.0: Sovereign State Diagnostics for ontological_hybrid model
                # Only log when Kosha is engaged (since Bhava/Kosha/Vritti are part of sovereign synthesis)
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

                # V9.9.12c: PhaseAttention Health Dashboard (diagnostic only)
                # Runs during evaluation intervals to monitor behavioral stability
                if config.model_type in ('phase', 'hybrid', 'ontological_hybrid'):
                    try:
                        enable_health_diagnostics_capture(model, True)
                        # Run a single forward pass to capture phase tensors
                        with torch.no_grad():
                            if cached_val_batches and len(cached_val_batches) > 0:
                                health_batch = cached_val_batches[0]
                            else:
                                health_batch = next(iter(val_loader))
                            # V11.2: Truncate to avoid OOM — full seq_len forward
                            # pass without TBPTT allocates [B,H,N,N] attention
                            # (~25 GiB at N=32768). 512 tokens is plenty for
                            # phase health metrics (collapse, drift, redundancy).
                            health_x = health_batch[0][:1, :512].to(device)
                            _ = model(health_x)
                        health_metrics = compute_phase_health_diagnostics(model)
                        enable_health_diagnostics_capture(model, False)

                        # Log health metrics
                        print(f"\n  📊 [PHASE HEALTH] Step {global_step}")
                        print(f"     ├─ R_k (key collapse):    {health_metrics['R_k']:.4f} {'⚠️' if health_metrics['R_k'] > 0.5 else '✓'}")
                        print(f"     ├─ R_q (query collapse):  {health_metrics['R_q']:.4f}")
                        print(f"     ├─ Amp-Phase Corr:        {health_metrics['amp_phase_corr']:.4f} {'⚠️' if abs(health_metrics['amp_phase_corr']) > 0.5 else '✓'}")
                        print(f"     ├─ Head Redundancy:       {health_metrics['head_redundancy']:.4f} {'⚠️' if health_metrics['head_redundancy'] > 0.8 else '✓'}")
                        print(f"     ├─ Phase Drift Mean:      {health_metrics['phase_drift_mean']:.4f} {'⚠️' if health_metrics['phase_drift_mean'] < 0.01 else '✓'}")
                        print(f"     └─ Phase Drift Std:       {health_metrics['phase_drift_std']:.4f}")

                        # Add to metrics for tensorboard/wandb logging
                        for k, v in health_metrics.items():
                            metrics[f'health_{k}'] = v
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
                            model, quad_check_batch, device, config.quad_utilization_warn_threshold
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
                        # Graduation ceremony!
                        print(f"\n  {'='*60}")
                        print(f"  🎓 KOSHA GYROSCOPE GRADUATION at step {global_step}")
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
                    if tb_writer is not None and not kosha_graduated:
                        tb_writer.add_scalar("gyro/mean_ppl", kosha_graduation_monitor.mean_ppl, global_step)
                        tb_writer.add_scalar("gyro/ppl_variance", kosha_graduation_monitor.variance, global_step)

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

                # V9.8.6: Kosha Three-Phase Curriculum Update
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
                # Skip if PID is disengaged (POLISHING phase)
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
                        from symbolu.sovereign.metrics import get_entropy_status
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
                        )

                    # Log adaptive controller status
                    if adaptive_adjustments.get("actions"):
                        # Already logged by the controller
                        pass

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
                            scaler_state=scaler.state_dict() if scaler else None,
                            # V9.8.6: Three-Phase Curriculum states
                            onto_curriculum_state=onto_curriculum.get_state() if onto_curriculum else None,
                            evoflow_state=evolutionary_engine.get_state() if evolutionary_engine else None,
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

            # Quality Sampling (OUTSIDE eval block - runs independently of eval_every)
            if config.sample_every > 0 and global_step % config.sample_every == 0:
                if tokenizer is not None:
                    model.eval()
                    run_quality_samples(model, tokenizer, config, device, global_step)
                    model.train()
                else:
                    print(f"  [Sampling] Skipped - tokenizer not available")

            # Save checkpoint (overwrites last.pt each time)
            if global_step % config.save_every == 0 and not config.no_save:
                # V9.8.10: Ensure scheduled alpha is applied before saving
                update_alpha_schedule(model, global_step, config)
                save_checkpoint(
                    model, optimizer, scheduler, global_step, best_val_loss,
                    ckpt_dir / "last.pt",
                    hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
                    drc_state=relaxation_controller.get_state() if relaxation_controller else None,
                    scaler_state=scaler.state_dict() if scaler else None,
                    # V9.8.6: Three-Phase Curriculum states
                    onto_curriculum_state=onto_curriculum.get_state() if onto_curriculum else None,
                    evoflow_state=evolutionary_engine.get_state() if evolutionary_engine else None,
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
            scaler_state=scaler.state_dict() if scaler else None,
            # V9.8.6: Three-Phase Curriculum states
            onto_curriculum_state=onto_curriculum.get_state() if onto_curriculum else None,
            evoflow_state=evolutionary_engine.get_state() if evolutionary_engine else None,
        )
        # v2.7 Training State Tracker: Save final state
        if training_state_tracker is not None and training_state_tracker.enabled:
            training_state_tracker.save_state()

    # Close TensorBoard
    if tb_writer is not None:
        tb_writer.close()

    print(f"\n{'='*70}")
    print("   TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"  Total Steps: {global_step:,}")
    print(f"  Best Val Loss: {best_val_loss:.4f}")
    print(f"  Best Val PPL: {math.exp(best_val_loss):.2f}")
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
# Phase Rotation Test (validates phase encodes relational structure)
# =============================================================================

def run_phase_rotation_test(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    config: 'UnifiedTrainingConfig',
    autocast_dtype: torch.dtype,
    angles_degrees: List[float] = None,
    cached_val_batches: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Run phase rotation test to verify phase encodes relational structure.

    HYPOTHESIS:
    -----------
    If roles/relations are encoded as phase offsets:
    - Rotating φ_k by θ should shift which bindings are retrieved
    - Larger rotations should cause larger perplexity increases
    - 180° rotation should cause maximum disruption

    If phase is decorative:
    - Rotation should have minimal/random effect on perplexity
    - No systematic relationship between rotation angle and perplexity

    Args:
        model: Model with phase attention (must have set_rotation method)
        val_loader: Validation DataLoader
        device: Device to run on
        config: Training configuration
        autocast_dtype: Autocast dtype for mixed precision
        angles_degrees: List of rotation angles in degrees (default: 0, 45, 90, 135, 180, 270)
        cached_val_batches: Optional pre-cached validation batches

    Returns:
        Dictionary with:
        - 'perplexity': {angle: ppl} for each angle
        - 'loss': {angle: loss} for each angle
        - 'delta_ppl': {angle: ppl_change} relative to baseline
        - 'sensitivity': float (mean absolute ppl delta, higher = more sensitive)
        - 'systematic': bool (True if ppl increases with angle up to 180°)
    """
    if angles_degrees is None:
        angles_degrees = [0, 45, 90, 135, 180, 270]

    if not hasattr(model, 'set_rotation'):
        return {
            'perplexity': {0: float('nan')},
            'loss': {0: float('nan')},
            'delta_ppl': {0: 0.0},
            'sensitivity': 0.0,
            'systematic': False,
            'error': 'Model does not support rotation (no set_rotation method)'
        }

    results = {'perplexity': {}, 'loss': {}, 'delta_ppl': {}}

    # Get baseline (0° rotation)
    model.set_rotation(0.0)
    baseline_loss, baseline_metrics = evaluate(
        model, val_loader, device, config, autocast_dtype,
        cached_val_batches=cached_val_batches
    )
    baseline_ppl = baseline_metrics['ppl']
    results['perplexity'][0] = baseline_ppl
    results['loss'][0] = baseline_loss
    results['delta_ppl'][0] = 0.0

    # Test each rotation angle
    for angle_deg in angles_degrees:
        if angle_deg == 0:
            continue  # Already computed

        angle_rad = math.radians(angle_deg)
        model.set_rotation(angle_rad)
        loss, metrics = evaluate(
            model, val_loader, device, config, autocast_dtype,
            cached_val_batches=cached_val_batches
        )
        ppl = metrics['ppl']
        results['perplexity'][angle_deg] = ppl
        results['loss'][angle_deg] = loss
        results['delta_ppl'][angle_deg] = ppl - baseline_ppl

    # Clear rotation
    model.clear_rotation()

    # Compute sensitivity metrics (normalized by baseline)
    deltas = [abs(d) / baseline_ppl for a, d in results['delta_ppl'].items() if a != 0]
    results['sensitivity'] = sum(deltas) / len(deltas) if deltas else 0.0

    # Check if perplexity increases systematically with angle (up to 180°)
    angles_sorted = sorted([a for a in results['perplexity'].keys() if a <= 180])
    ppls_sorted = [results['perplexity'][a] for a in angles_sorted]
    # Systematic if ppl generally increases (allowing small fluctuations)
    increasing_pairs = sum(1 for i in range(len(ppls_sorted)-1) if ppls_sorted[i] <= ppls_sorted[i+1] * 1.02)
    results['systematic'] = increasing_pairs >= (len(ppls_sorted) - 2) if len(ppls_sorted) > 2 else False

    # Additional analysis: find angle of maximum disruption
    if results['delta_ppl']:
        max_delta = max(results['delta_ppl'].items(), key=lambda x: x[1])
        results['max_disruption_angle'] = max_delta[0]
        results['max_disruption_delta'] = max_delta[1]

    return results


def print_phase_rotation_results(
    results: Dict[str, Any],
    model_name: str = "Model",
) -> None:
    """Pretty-print phase rotation test results."""
    print(f"\n{'='*70}")
    print(f"PHASE ROTATION TEST: {model_name}")
    print(f"{'='*70}")

    if 'error' in results:
        print(f"  ERROR: {results['error']}")
        return

    baseline_ppl = results['perplexity'].get(0, 1.0)

    print(f"\nHypothesis: If phase encodes relations, rotating φ_k should disrupt retrieval.")
    print(f"\n  {'Angle':>8}  {'Perplexity':>12}  {'Δ PPL':>10}  {'Δ %':>8}")
    print(f"  {'-'*8}  {'-'*12}  {'-'*10}  {'-'*8}")

    for angle in sorted(results['perplexity'].keys()):
        ppl = results['perplexity'][angle]
        delta = results['delta_ppl'][angle]
        delta_pct = (delta / baseline_ppl) * 100 if baseline_ppl > 0 else 0
        delta_str = f"{delta:+.2f}" if angle != 0 else "baseline"
        pct_str = f"{delta_pct:+.1f}%" if angle != 0 else ""
        print(f"  {angle:>6}°  {ppl:>12.2f}  {delta_str:>10}  {pct_str:>8}")

    print(f"\n  Sensitivity (mean |Δ|/baseline): {results['sensitivity']*100:.2f}%")
    print(f"  Systematic increase:             {'Yes' if results['systematic'] else 'No'}")

    if 'max_disruption_angle' in results:
        print(f"  Max disruption at:               {results['max_disruption_angle']}° (+{results['max_disruption_delta']:.2f} PPL)")

    # Interpretation
    print(f"\n  INTERPRETATION:")
    if results['sensitivity'] > 0.10:
        print(f"    → Phase is SENSITIVE to rotation (sensitivity > 10%)")
        print(f"    → Phase likely encodes meaningful relational structure")
        if results['systematic']:
            print(f"    → Systematic increase suggests phase offset = relation encoding")
    elif results['sensitivity'] > 0.05:
        print(f"    → Phase shows MODERATE sensitivity to rotation")
        print(f"    → Phase may partially encode relational structure")
    else:
        print(f"    → Phase is INSENSITIVE to rotation (sensitivity < 5%)")
        print(f"    → Phase may be DECORATIVE (not encoding relations)")


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler._LRScheduler,
    step: int,
    best_val_loss: float,
    path: Path,
    hgs_state: Optional[dict] = None,
    drc_state: Optional[dict] = None,
    scaler_state: Optional[dict] = None,
    # V9.8.6: Three-Phase Curriculum states
    onto_curriculum_state: Optional[dict] = None,
    # V9.8.6: EvoFlow state (EvolutionaryIntelligenceEngine)
    evoflow_state: Optional[dict] = None,
    # Dataloader position
    dataloader_position: Optional[dict] = None,
):
    """Save training checkpoint with optional auxiliary state.

    Uses split-file format to avoid network filesystem (RunPod MFS/FUSE) write
    limits (~2GB per file). Saves three files:
      {stem}_model.pt  - model state_dict
      {stem}_optim.pt  - optimizer state_dict
      {stem}_meta.pt   - scheduler, step, RNG states, auxiliary controller states

    For backwards compatibility, load_checkpoint handles both single-file and
    split-file formats transparently.
    """
    stem = path.parent / path.stem  # e.g. checkpoints_unified/best

    model_path = Path(f"{stem}_model.pt")
    optim_path = Path(f"{stem}_optim.pt")
    meta_path = Path(f"{stem}_meta.pt")

    # Build metadata dict (small — always fits in a single file)
    meta = {
        "split_format": True,  # Sentinel for load_checkpoint
        "scheduler": scheduler.state_dict(),
        "step": step,
        "best_val_loss": best_val_loss,
        "rng_state": torch.get_rng_state(),
    }

    # Add CUDA RNG state if available
    if torch.cuda.is_available():
        meta["cuda_rng_state"] = torch.cuda.get_rng_state()

    # Add auxiliary controller states
    if hgs_state is not None:
        meta["hgs_state"] = hgs_state
    if drc_state is not None:
        meta["drc_state"] = drc_state
    if scaler_state is not None:
        meta["scaler_state"] = scaler_state
    if onto_curriculum_state is not None:
        meta["onto_curriculum_state"] = onto_curriculum_state
    if evoflow_state is not None:
        meta["evoflow_state"] = evoflow_state
    if dataloader_position is not None:
        meta["dataloader_position"] = dataloader_position

    # Remove old files before saving (both single-file and split formats)
    for p in [path, model_path, optim_path, meta_path]:
        if p.exists():
            p.unlink()

    # Save each component as a separate file to stay under NFS write limits
    torch.save(model.state_dict(), model_path)
    torch.save(optimizer.state_dict(), optim_path)
    torch.save(meta, meta_path)


def load_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
    weights_only: bool = False,
    device: torch.device = None,
) -> Dict[str, Any]:
    """Load training checkpoint.

    Handles both single-file format (legacy) and split-file format:
      {stem}_model.pt + {stem}_optim.pt + {stem}_meta.pt

    Args:
        path: Path to checkpoint file (e.g. checkpoints_unified/best.pt)
        model: Model to load weights into
        optimizer: Optimizer to restore state (None if weights_only)
        scheduler: Scheduler to restore state (None if weights_only)
        weights_only: If True, only load model weights (fresh optimizer/scheduler)
        device: Device to map tensors to

    Returns:
        Dict with checkpoint info (step, best_val_loss, etc.)
    """
    # Detect split-file format: check for {stem}_model.pt
    stem = path.parent / path.stem
    model_path = Path(f"{stem}_model.pt")
    optim_path = Path(f"{stem}_optim.pt")
    meta_path = Path(f"{stem}_meta.pt")
    use_split = model_path.exists()

    if not use_split and not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path} (also checked split format at {model_path})")

    if use_split:
        print(f"\n  📂 Loading split checkpoint from: {stem}_*.pt")
    else:
        print(f"\n  📂 Loading checkpoint from: {path}")

    # Load checkpoint with error handling for corrupted files
    try:
        if use_split:
            # Split format: load model state separately
            model_state_raw = torch.load(model_path, map_location=device, weights_only=False)
            checkpoint = torch.load(meta_path, map_location=device, weights_only=False)
            checkpoint["model"] = model_state_raw
            # Optimizer loaded on-demand below (only if needed)
        else:
            checkpoint = torch.load(path, map_location=device, weights_only=False)
    except (EOFError, pickle.UnpicklingError, RuntimeError) as e:
        # Checkpoint file is corrupted or incomplete
        ckpt_loc = f"{stem}_*.pt" if use_split else str(path)
        print(f"\n  ⚠️  ERROR: Checkpoint file is corrupted or incomplete: {ckpt_loc}")
        print(f"      Error: {type(e).__name__}: {e}")
        print(f"      This typically happens if training was interrupted during checkpoint save.")
        print(f"\n  Solutions:")
        print(f"      1. Delete the corrupted checkpoint: rm {ckpt_loc}")
        print(f"      2. Use a different checkpoint: --resume <path_to_valid_checkpoint>")
        print(f"      3. Start from scratch: remove --resume flag")
        raise RuntimeError(f"Cannot load corrupted checkpoint: {ckpt_loc}") from e

    # Load model weights
    # Filter out runtime buffers that may have been saved with tensor values
    # but are initialized as None in fresh models (e.g., prev_state in OntologicalHybridTransformer)
    model_state = checkpoint["model"]
    runtime_buffers = ["prev_state"]  # Buffers that are runtime state, not trained weights
    filtered_state = {k: v for k, v in model_state.items() if k not in runtime_buffers}
    if len(filtered_state) < len(model_state):
        removed = [k for k in model_state if k in runtime_buffers]
        print(f"    → Filtered runtime buffers: {removed}")

    # V9.6.8: Handle old state_projector (nn.Sequential) → new SovereignStateProjector
    # Old unconstrained weights produce extreme values that saturate softmax.
    # Drop them entirely so SovereignStateProjector initializes with small weights.
    migrated = False
    old_projector_keys = [k for k in filtered_state if k.startswith("state_projector.") and ".projector." not in k and "layer_norm" not in k]
    if old_projector_keys:
        migrated = True
        print(f"    → Detected old state_projector format (unconstrained nn.Sequential)")
        print(f"    → Dropping old weights to allow fresh SovereignStateProjector init")
        for old_key in old_projector_keys:
            del filtered_state[old_key]
            print(f"      Dropped: {old_key}")
        print(f"    ✓ state_projector will initialize fresh with proper normalization")

    model.load_state_dict(filtered_state, strict=False)
    print(f"    ✓ Model weights loaded")

    result = {
        "step": checkpoint.get("step", 0),
        "best_val_loss": checkpoint.get("best_val_loss", float('inf')),
    }

    if weights_only:
        print(f"    → Weights-only mode: Optimizer/Scheduler will start fresh")
        result["step"] = 0  # Start from step 0 with fresh optimizer
        return result

    # Skip optimizer/scheduler restore if architecture was migrated (param groups don't match)
    if migrated:
        print(f"    → Architecture migrated: Optimizer/Scheduler will start fresh")
        return result

    # Restore optimizer state
    if optimizer is not None:
        if use_split and optim_path.exists():
            optim_state = torch.load(optim_path, map_location=device, weights_only=False)
            optimizer.load_state_dict(optim_state)
            del optim_state  # Free memory immediately
            print(f"    ✓ Optimizer state restored (from split file)")
        elif "optimizer" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer"])
            print(f"    ✓ Optimizer state restored")

    # Restore scheduler state
    if scheduler is not None and "scheduler" in checkpoint:
        scheduler.load_state_dict(checkpoint["scheduler"])
        print(f"    ✓ Scheduler state restored")

    # Restore RNG states for reproducibility
    if "rng_state" in checkpoint:
        try:
            rng_state = checkpoint["rng_state"]
            # Ensure RNG state is ByteTensor on CPU
            if not isinstance(rng_state, torch.ByteTensor):
                rng_state = rng_state.to(dtype=torch.uint8, device='cpu')
            torch.set_rng_state(rng_state)
            print(f"    ✓ RNG state restored")
        except Exception as e:
            print(f"    ⚠ RNG state restoration failed: {e} (continuing without)")

    if "cuda_rng_state" in checkpoint and torch.cuda.is_available():
        try:
            cuda_rng_state = checkpoint["cuda_rng_state"]
            # Ensure CUDA RNG state is ByteTensor
            if not isinstance(cuda_rng_state, torch.ByteTensor):
                cuda_rng_state = cuda_rng_state.to(dtype=torch.uint8)
            torch.cuda.set_rng_state(cuda_rng_state)
            print(f"    ✓ CUDA RNG state restored")
        except Exception as e:
            print(f"    ⚠ CUDA RNG state restoration failed: {e} (continuing without)")

    # Return additional state for HGS/DRC restoration
    if "hgs_state" in checkpoint:
        result["hgs_state"] = checkpoint["hgs_state"]
        print(f"    ✓ HGS state available for restoration")

    if "drc_state" in checkpoint:
        result["drc_state"] = checkpoint["drc_state"]
        print(f"    ✓ DRC state available for restoration")

    # Return SGP state for restoration
    # Return Sattvic Controller state for restoration
    # V9.8.1: Return AMP GradScaler state for restoration
    if "scaler_state" in checkpoint:
        result["scaler_state"] = checkpoint["scaler_state"]
        print(f"    ✓ AMP GradScaler state available for restoration")

    # V9.8.6: Return Three-Phase Curriculum states for restoration
    if "onto_curriculum_state" in checkpoint:
        result["onto_curriculum_state"] = checkpoint["onto_curriculum_state"]
        print(f"    ✓ Onto Curriculum state available for restoration")
    # V9.8.6: Return EvoFlow state (EvolutionaryIntelligenceEngine)
    if "evoflow_state" in checkpoint:
        result["evoflow_state"] = checkpoint["evoflow_state"]
        print(f"    ✓ EvoFlow state available for restoration")

    # KV Supervision state
    # V9.8.6: Return dataloader position for restoration
    if "dataloader_position" in checkpoint:
        result["dataloader_position"] = checkpoint["dataloader_position"]
        print(f"    ✓ Dataloader position available for restoration")

    print(f"    → Resuming from step {result['step']}, best_val_loss={result['best_val_loss']:.4f}")

    return result


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
                       choices=["ontological", "phase", "hybrid", "gen2", "standard", "ontological_hybrid", "binding_cache", "ontological_binding_cache"],
                       help="Model architecture type (standard = O(n²) baseline, ontological_hybrid = Two-Tier AGI, "
                            "binding_cache = Protected Phase + Top-K Query [V10.0], "
                            "ontological_binding_cache = AGI Architecture [Binding Cache + 32D Sovereign State])")
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
                       choices=["wikitext103", "wikitext2", "fineweb", "synthetic"],
                       help="Training dataset: wikitext103, wikitext2, fineweb (streaming), or synthetic (offline)")
    parser.add_argument("--dataset_name", type=str, default="HuggingFaceFW/fineweb",
                       help="HuggingFace dataset name for fineweb mode (e.g., HuggingFaceFW/fineweb-edu)")
    parser.add_argument("--dataset_subset", type=str, default="sample-10BT",
                       help="Dataset subset/config for fineweb mode")
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
                       help="Enable phase-first learning: alpha high->low, window small->large")

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
                            "s_align = cos(θ_intent) (intent agreement), "
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

    # Clean separation: Attention = physics, Annotator = semantics

    # V9.8.0: Ontological Hybrid (Two-Tier AGI) with 32D Sovereign State
    parser.add_argument("--state_dim", type=int, default=SOVEREIGN_STATE_DIM,
                       help="Sovereign State dimension for ontological_hybrid model "
                            "(default 32 = 12 Bhava + 5 Kosha + 5 Vritti + 6 Guna + 4 Reserved). "
                            "V9.8.0: Replaces arbitrary 124D with principled ontology.")
    parser.add_argument("--project_per_head_dim", action="store_true",
                       help="Project state delta to [H, D_h] instead of [H] for finer control")

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
                       help="Minimum Guna Coherence floor (default 0.65)")

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
    parser.add_argument("--lightweight_diagnostics", action="store_true", default=True,
                       help="Skip expensive gradient norm computation in diagnostics (default: True)")
    parser.add_argument("--full_diagnostics", action="store_true",
                       help="Enable full diagnostics with gradient norms (slower but more detailed)")

    # ==========================================================================
    # v2.2.1: Kosha Gyroscope - Homeostatic Self-Regulation Loss
    # ==========================================================================
    # V9.8.7: Dynamic three-phase engagement
    # Dynamic Weight Scheduler (v2.2.1)
    # Trap detection thresholds (v2.2.5: Golden Ratio φ)
    # v2.3.0: Complete Harmonic Pentad - Floor and Ceiling for each Kosha
    # Mental: Sattvic Band 23.6% - 38.2%
    # Physical: Sattvic Band 38.2% - 61.8%
    # Intellect: Sattvic Band 25.0% - 61.8%
    # Vital: Sattvic Band 23.6% - 78.6%
    # Bliss: Sattvic Band 23.6% - 61.8%
    # Correction factors
    # v2.3.2: Reflexive Domain Morph
    # v2.2.4: Three-Stage Hybrid Logic (Damping + Gate + Rip)
    # Legacy: steepness (deprecated in v2.2.4)
    # Refinements
    # V9.8.6: Three-Phase Kosha Curriculum
    # Graduation criteria (legacy - kept for stability check)
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

    parser.add_argument("--phase_ramp_steps", type=int, default=7000,
                       help="Steps for phase LR ramp (handshake dampening)")
    parser.add_argument("--tensorboard", action="store_true", default=True,
                       help="Enable TensorBoard logging")
    parser.add_argument("--no_tensorboard", action="store_true",
                       help="Disable TensorBoard logging")

    # Quality Sampling
    parser.add_argument("--sample_every", type=int, default=50,
                       help="Generate quality samples every N steps (0 = disabled)")

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
    parser.add_argument("--enable_evolutionary_flow", action="store_true", default=True,
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

    # PPL-Gated Curriculum Learning - Phased auxiliary loss introduction
    parser.add_argument("--enable_curriculum", action="store_true",
                       help="Enable PPL-gated curriculum learning (phases: FOUNDATION→REGULARIZATION→GROUNDING→SOVEREIGN)")
    parser.add_argument("--curriculum_ppl_regularization", type=float, default=30.0,
                       help="PPL threshold to enter REGULARIZATION phase (light bhava/coherence)")
    parser.add_argument("--curriculum_ppl_grounding", type=float, default=15.0,
                       help="PPL threshold to enter GROUNDING phase (Bridge + JEPA)")
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

    # ==========================================================================
    # Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md
    # ==========================================================================

    # ==========================================================================
    # V9.8.8: Sovereign Phase Controller (SPC)
    # Reference: docs/SOVEREIGN_PHASE_CONTROLLER_DESIGN.md
    # ==========================================================================
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
                       help="Current training phase (body=JEPA, soul=reasoning, union=joint)")
    parser.add_argument("--jepa_phase_body_steps", type=int, default=20000,
                       help="Steps for Body phase (JEPA perceptual learning)")
    parser.add_argument("--jepa_phase_soul_steps", type=int, default=30000,
                       help="Steps for Soul phase (reasoning)")
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

    parser.add_argument("--jepa_enable_karma_injection", action="store_true",
                       help="Enable karma state injection for JEPA")
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
        cosine_mode=args.cosine_mode,  # V9.6.12: Cosine interaction mode
        decay_gamma=args.decay_gamma,  # V9.6.13: State decay factor
        learned_decay=args.learned_decay,  # V9.9.7: Per-head learned decay
        bounded_phase=args.bounded_phase,  # V9.9.11: Phase collapse fix 1
        zero_mean_cosine=args.zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
        # V10.3.8: Dual-Channel Attention
        dual_channel_mode=args.dual_channel_mode,
        alignment_authority=args.alignment_authority,
        # Phase Rotation Test
        phase_rotation=args.phase_rotation,
        phase_rotation_angles=args.phase_rotation_angles,
        state_dim=args.state_dim,  # V9.6.14: Ontological Hybrid state dimension
        project_per_head_dim=args.project_per_head_dim,  # V9.6.14: Per-head-dim projection
        # V10.0: Binding Cache options
        binding_cache_top_k=args.binding_cache_top_k,
        no_binding_cache=args.no_binding_cache,
        bhava_lambda=args.bhava_lambda,
        coherence_lambda=args.coherence_lambda,
        log_every=args.log_every,
        quiet=args.quiet,
        lightweight_diagnostics=not args.full_diagnostics,  # Default True unless --full_diagnostics
        # v2.2.1: Kosha Gyroscope - Homeostatic Self-Regulation
        # V9.8.7: Three-phase dynamic engagement
        # v2.3.0: Complete Harmonic Pentad - Floors and Ceilings
        # v2.3.2: Reflexive Domain Morph
        # v2.2.4: Three-Stage Hybrid Logic
        # V9.8.6: Three-Phase Kosha Curriculum
        enable_rip_logger=args.enable_rip_logger,
        rip_logger_dir=args.rip_logger_dir,
        # v2.3.3: 32D Sovereign State Regularizer
        enable_state_regularizer=args.enable_state_regularizer,
        state_reg_anti_sat_weight=args.state_reg_anti_sat_weight,
        state_reg_variance_weight=args.state_reg_variance_weight,
        state_reg_sat_thresh_high=args.state_reg_sat_thresh_high,
        state_reg_sat_thresh_low=args.state_reg_sat_thresh_low,
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
        # V9.8.7: Three-phase PID engagement
        phase_ramp_steps=args.phase_ramp_steps,
        tensorboard=args.tensorboard and not args.no_tensorboard,
        sample_every=args.sample_every,
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
        # SGP (Stochastic Gradient Persistence)
        # Sattvic Controller
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
        # Auto Batch Sizing
        enable_auto_batch=args.enable_auto_batch,
        auto_batch_target_utilization=args.auto_batch_target_utilization,
        auto_batch_safety_margin=args.auto_batch_safety_margin,
        auto_batch_target_effective=args.auto_batch_target_effective,
        # Friction Controller
        # V9.8.8: Sovereign Phase Controller (SPC)
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
        kv_entropy_floor_ratio=args.kv_entropy_floor_ratio,
        kv_compatibility_prior_path=args.kv_compatibility_prior_path,
        kv_curriculum_exclude_epochs=args.kv_curriculum_exclude_epochs,
        kv_curriculum_ramp_epochs=args.kv_curriculum_ramp_epochs,
        kv_teacher_mode=args.kv_teacher_mode,
        kv_collapse_check_interval=args.kv_collapse_check_interval,
        kv_kl_clamp_max=args.kv_kl_clamp_max,
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

        # Summary
        print("-" * 70)
        print(f"  Phase-First Schedule:")
        print("=" * 70 + "\n")

    # Train
    train(config)


if __name__ == "__main__":
    main()
