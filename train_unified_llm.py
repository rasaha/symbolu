#!/usr/bin/env python3
"""
Unified LLM Training Script V9.4.5
===================================

Train SymbolU models with support for:
1. SymbolU12 with Bhava (standard attention + 12D ontological + 144D bhava)
2. Phase Attention (O(n) complexity)
3. Hybrid (Local + Phase attention)
4. Gen 2: Hierarchical Complex Bhava (3-tier phase rotation)

Now includes PIDv2 Governor from train_pid.py:
- Dynamic SNR-Adjusted Kp
- Semantic Validation (W_s weight)
- Handshake D-term Dampening
- Stress Test Framework
- V9.4.5: Friction Controller with Corrective Actions

Usage:
------
    # Train SymbolU12 with Bhava (standard attention + ontological)
    python train_unified_llm.py --model_type ontological --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Phase model (O(n) attention)
    python train_unified_llm.py --model_type phase --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Train Hybrid model (Local + Phase) with PIDv2 Governor
    python train_unified_llm.py --model_type hybrid --model_size small \
        --dataset wikitext103 --max_steps 1000 --controller pidv2

    # Train Gen 2 model (Hierarchical Complex Bhava)
    python train_unified_llm.py --model_type gen2 --model_size small \
        --dataset wikitext103 --max_steps 1000

    # Long context training (16K/32K)
    python train_unified_llm.py --model_type gen2 --model_size small \
        --max_seq_len 16384 --gradient_checkpointing --batch_size 1

    # Stress Test (Trial by Fire)
    python train_unified_llm.py --stress_test --resume checkpoints/best.pt

Author: SymbolU Team
Date: December 2025
"""

import argparse
import collections
import json
import logging
import math
import os
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
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR

# Hugging Face imports
try:
    from transformers import AutoTokenizer
    from datasets import load_dataset
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

# TensorBoard
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False

# Local imports
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import (
    PhaseTransformer,
    HybridPhaseTransformer,
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
    from symbolu.sovereign.hierarchical_gradient_scaler import compute_s_drift
    COMPUTE_S_DRIFT_AVAILABLE = True
except ImportError:
    COMPUTE_S_DRIFT_AVAILABLE = False
    compute_s_drift = None

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

# Import SGP (Stochastic Gradient Persistence) and Sattvic Controller
try:
    from symbolu.resonance.sgp import (
        SGPController,
        SGPConfig,
        create_sgp_controller,
        create_synchronized_controllers,
    )
    from symbolu.resonance.controller import (
        SattvicController,
        SattvicConfig,
        create_sattvic_controller,
    )
    SGP_AVAILABLE = True
except ImportError as e:
    SGP_AVAILABLE = False
    print(f"Warning: SGP Controller not available: {e}")


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

# Vṛtti names for logging/debugging
VRTTI_NAMES = ["Pramāṇa", "Vikalpa", "Viparyaya", "Nidrā", "Smṛti"]

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
        enable_sgp: bool = False,
        sgp_rate: int = 100,
    ):
        super().__init__()
        self.dim = dim
        self.num_layers = num_layers
        self.truncated_bptt_steps = truncated_bptt_steps
        self.step_count = 0

        # V9.4.7: Stochastic Gradient Persistence (SGP)
        self.enable_sgp = enable_sgp
        self.sgp_rate = sgp_rate
        self.last_sgp_step: Optional[int] = None  # Track last SGP pulse

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
        is_sgp_heavy_step = False

        if self.enable_sgp and self.sgp_rate > 0 and global_step > 0:
            # SGP: Keep gradients only at capped rate (e.g., every 100 steps)
            if global_step % self.sgp_rate == 0:
                # High-Rajas: Main graph remains connected for recursive evolution
                # V9.5.2 Metabolic Tuning: Ensure BF16 precision to save memory
                self.karma_buffer = seed.to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed
                is_sgp_heavy_step = True
                self.last_sgp_step = global_step
            else:
                # Sattvic: Detach to maintain high throughput
                # V9.5.2 Metabolic Tuning: Ensure BF16 precision
                self.karma_buffer = seed.detach().to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed.detach()
        elif self.truncated_bptt_steps > 0 and self.step_count % self.truncated_bptt_steps != 0:
            # Legacy truncated BPTT mode (if SGP not enabled)
            self.karma_buffer = seed.to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed
        else:
            # Default: Detach to prevent infinite gradient chains
            # V9.5.2 Metabolic Tuning: Ensure BF16 precision
            self.karma_buffer = seed.detach().to(torch.bfloat16) if seed.dtype != torch.bfloat16 else seed.detach()

        self.bridge_active = True
        return is_sgp_heavy_step

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
        if self.hidden_states and any(h is not None for h in self.hidden_states):
            valid_states = [h for h in self.hidden_states if h is not None]
            if len(valid_states) >= 3:
                # Pad to num_layers if needed
                while len(valid_states) < self.num_layers:
                    valid_states.append(valid_states[-1])
                return valid_states[:self.num_layers]

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

        self.current_step = 0
        self.hooks = []
        self.hooks_registered = False  # Track if hooks are active
        self.in_thaw_mode = False  # Set to True during 9:3 → 6:6 transition

        # Use bounded deques to prevent memory accumulation over long training
        self._authority_grad_norms = collections.deque(maxlen=1000)
        self._sensory_grad_norms = collections.deque(maxlen=1000)
        self._phase_grad_norms = collections.deque(maxlen=1000)  # Track Phase Attention grads

        self.gradient_stats = {
            "authority_grad_norm": 0.0,
            "sensory_grad_norm": 0.0,
            "phase_grad_norm": 0.0,
            "sensory_scale": alpha_sens_min,
            "sensory_authority_ratio": 0.0,
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

        Phase Attention Protection:
        During Thaw mode, Phase Attention weights (W_phase, W_amp, etc.) in Authority
        layers receive extra gradient dampening to maintain stability of the complex
        O(n) attention mechanism while Sensory layers are being relaxed.
        """
        is_phase_param = self._is_phase_attention_param(param_name)

        def hook(grad):
            if grad is None:
                return grad

            if is_sensory:
                # Apply dampening to sensory layers
                alpha = self._compute_alpha_sens()
                scaled_grad = grad * alpha

                # Track stats using bounded deques
                self._sensory_grad_norms.append(grad.norm().item())
                self.gradient_stats["sensory_scale"] = alpha

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

                # Normal authority layers get full gradient
                self._authority_grad_norms.append(grad_norm)
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

        # Clamp S/A ratio to prevent extreme imbalance at startup
        # Healthy range is 0.3-0.7, warn if outside 0.1-10.0
        s_a_ratio_clamped = max(0.01, min(100.0, s_a_ratio))
        if s_a_ratio > 10.0 and self.current_step < 100:
            # Early training with extreme ratio - apply emergency damping
            # This prevents runaway sensory gradients from destabilizing authority
            self.alpha_sens_min = min(self.alpha_sens_min, 0.005)

        self.gradient_stats["authority_grad_norm"] = a_norm
        self.gradient_stats["sensory_grad_norm"] = s_norm
        self.gradient_stats["phase_grad_norm"] = p_norm
        self.gradient_stats["sensory_authority_ratio"] = s_a_ratio_clamped
        self.gradient_stats["sensory_scale"] = self._compute_alpha_sens()

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
        new_alpha_min: float,
        new_alpha_max: float,
        new_warmup_steps: int,
    ):
        """
        Reconfigure the scaler for a new split configuration.
        Used for dynamic 9:3 → 6:6 transitions.
        """
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
        vram_threshold: float = 0.92,  # Trigger at 92% usage
        vram_critical: float = 0.97,   # Emergency at 97%
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
        """
        if not torch.cuda.is_available():
            return 0.0, 0.0, 0.0

        used = torch.cuda.memory_reserved()
        total = torch.cuda.get_device_properties(0).total_memory
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
            actions.append(f"⚠️  [VRAM ALERT] Usage at {usage:.1%} ({used_gb:.1f}GB/{total_gb:.1f}GB)")

            # Clear cache first
            torch.cuda.empty_cache()

            # Reduce batch by 4
            new_batch = max(self.min_batch_size, ((self.current_batch_size // 4) - 1) * 4)
            if new_batch < self.current_batch_size:
                self._apply_batch_reduction(new_batch, sovereign_engine, actions, emergency=False)

        # Check if we can recover (increase batch) after being in recovery mode
        elif self.in_recovery_mode and usage < (self.vram_threshold - 0.15):
            # VRAM is now 15% below threshold - safe to try increasing
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
        if self.enable_accumulation_scaling and new_batch < self.target_effective_batch:
            new_accum = max(1, self.target_effective_batch // new_batch)
            if new_accum != self.accumulation_steps:
                old_accum = self.accumulation_steps
                self.accumulation_steps = new_accum
                effective = new_batch * new_accum
                actions.append(f"   Gradient accumulation: {old_accum} → {new_accum} (effective batch: {effective})")

        mode = "EMERGENCY" if emergency else "RESIZE"
        actions.append(f"   🛠️  [{mode}] Batch: {old_batch} → {new_batch} | Total resizes: {self.resize_count}")

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

        # Adjust accumulation steps
        if self.enable_accumulation_scaling:
            new_accum = max(1, self.target_effective_batch // new_batch)
            if new_accum != self.accumulation_steps:
                self.accumulation_steps = new_accum

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
            dominant = "Sattva"
        elif gunas["r"] > gunas["t"]:
            dominant = "Rajas"
        else:
            dominant = "Tamas"

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
            icon = "☀️"  # Sattva - clarity
        elif g["r"] > g["t"]:
            icon = "🔥"  # Rajas - action
        else:
            icon = "🌙"  # Tamas - inertia

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
            icon = "☀️"  # Sattva
            state = "Learning"
        elif r > t:
            icon = "🔥"  # Rajas
            state = "Active"
        else:
            icon = "🌙"  # Tamas
            state = "Plateau"

        return f"Gunas[{state}]: S:{s:.2f} R:{r:.2f} T:{t:.2f} {icon}"

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
    3. Modulates PIDv2 Kp based on train/val gap
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
    ):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.lr_min = lr_min
        self.lr_max = lr_max
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

        # History tracking
        self.val_ppl_history = []
        self.train_loss_history = []
        self.val_loss_history = []
        self.coherence_history = []
        self.adjustment_log = []

        # State
        self.current_lr_multiplier = 1.0
        self.boost_count = 0
        self.decay_count = 0
        self.plateau_count = 0

        print(f"\n  [AdaptiveTraining] Controller initialized:")
        print(f"    Base LR: {base_lr:.2e} (range: {lr_min:.2e} - {lr_max:.2e})")
        print(f"    Velocity thresholds: slow < {velocity_slow_threshold}%, spike > {velocity_spike_threshold}%")
        print(f"    Kp range: {kp_min} - {kp_max} (base: {kp_base})")
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
        authority_controller=None,  # PIDv2 controller reference
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

        # Keep history bounded
        max_history = 50
        if len(self.val_ppl_history) > max_history:
            self.val_ppl_history = self.val_ppl_history[-max_history:]
            self.train_loss_history = self.train_loss_history[-max_history:]
            self.val_loss_history = self.val_loss_history[-max_history:]
            self.coherence_history = self.coherence_history[-max_history:]

        adjustments = {"step": global_step, "actions": []}

        # Check if we can make adjustments
        if global_step - self.last_adjustment_step < self.min_steps_between_adjustments:
            return adjustments

        velocity = self._compute_velocity()
        is_plateau = self._detect_plateau()
        train_val_gap = self._compute_train_val_gap()

        # === LR Adaptation ===
        current_lr = self.optimizer.param_groups[0]['lr']

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

        # Case 2: Learning too slow or plateau → boost LR
        elif velocity > self.velocity_slow_threshold or is_plateau:
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

        # === Kp Adaptation (if PIDv2 controller provided) ===
        if authority_controller is not None and hasattr(authority_controller, 'Kp_min'):
            # Adjust Kp based on train/val gap
            # Large positive gap (val >> train) = overfitting → lower Kp
            # Small or negative gap = underfitting → higher Kp

            if train_val_gap > 20:  # Significant overfitting
                new_kp_min = max(self.kp_min, authority_controller.Kp_min * 0.8)
                new_kp_max = max(self.kp_min, authority_controller.Kp_max * 0.8)
                if new_kp_min != authority_controller.Kp_min:
                    authority_controller.Kp_min = new_kp_min
                    authority_controller.Kp_max = new_kp_max
                    adjustments["actions"].append(f"Kp_REDUCE: gap={train_val_gap:.1f}%")
                    print(f"\n  📉 [AdaptiveTraining] Kp REDUCED (train/val gap: {train_val_gap:.1f}%)")
                    self.last_adjustment_step = global_step

            elif train_val_gap < 5 and velocity > self.velocity_slow_threshold:
                # Underfitting and slow → increase Kp
                new_kp_min = min(self.kp_max, authority_controller.Kp_min * 1.2)
                new_kp_max = min(self.kp_max, authority_controller.Kp_max * 1.2)
                if new_kp_max != authority_controller.Kp_max:
                    authority_controller.Kp_min = new_kp_min
                    authority_controller.Kp_max = new_kp_max
                    adjustments["actions"].append(f"Kp_BOOST: gap={train_val_gap:.1f}%")
                    print(f"\n  📈 [AdaptiveTraining] Kp BOOSTED (underfitting, gap: {train_val_gap:.1f}%)")
                    self.last_adjustment_step = global_step

        if adjustments["actions"]:
            self.adjustment_log.append(adjustments)

        return adjustments

    def get_status_string(self) -> str:
        """Get formatted status string."""
        velocity = self._compute_velocity() if len(self.val_ppl_history) >= 2 else 0.0
        plateau = "PLATEAU" if self._detect_plateau() else "OK"
        current_lr = self.optimizer.param_groups[0]['lr']
        return f"AdaptLR:{current_lr:.2e} vel:{velocity:+.1f}% [{plateau}] boosts:{self.boost_count} decays:{self.decay_count}"

    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry for logging."""
        return {
            "current_lr": self.optimizer.param_groups[0]['lr'],
            "velocity": self._compute_velocity() if len(self.val_ppl_history) >= 2 else 0.0,
            "is_plateau": self._detect_plateau(),
            "train_val_gap": self._compute_train_val_gap(),
            "boost_count": self.boost_count,
            "decay_count": self.decay_count,
            "plateau_count": self.plateau_count,
            "adjustment_log": self.adjustment_log[-10:],  # Last 10 adjustments
        }


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
                    print(f"\n  ⚠️ [DynamicRelaxation] VIPARYAYA TRIGGERED!")
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
        print(f"\n  🔄 [DynamicRelaxation] VIPARYAYA RECOVERY: Reverting to {self.authority_split}")

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
    """
    model.eval()

    # Encode prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
    prompt_len = input_ids.shape[1]

    # Generate tokens one by one
    generated = input_ids.clone()

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
    Compute quality metrics for generated text (ChatGPT recommendation).

    Returns:
        - completion_rate: 1.0 if ends with punctuation, 0.0 otherwise
        - repetition_score: n-gram repetition rate (lower is better)
        - unique_ratio: ratio of unique tokens to total tokens
    """
    words = text.split()
    if len(words) < 2:
        return {"completion": 0.0, "repetition": 1.0, "unique_ratio": 0.0}

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

    return {
        "completion": completion,
        "repetition": repetition,
        "unique_ratio": unique_ratio,
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

    # Aggregate metrics across all samples
    total_completion = 0.0
    total_repetition = 0.0
    total_unique = 0.0
    sample_count = 0

    for prompt in config.sample_prompts:
        try:
            # ChatGPT recommendations for quality samples:
            # temperature=0.9, top_p=0.95, top_k=50
            # repetition_penalty=1.15, no_repeat_ngram_size=3
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=128,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
            )
            # Clean up and truncate for display
            generated = generated.strip().replace('\n', ' ')[:200]

            # Compute quality metrics
            metrics = compute_sample_metrics(generated)
            total_completion += metrics["completion"]
            total_repetition += metrics["repetition"]
            total_unique += metrics["unique_ratio"]
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

        log("  ────────────────────────────────────────────────────────")
        log(f"  📊 SAMPLE QUALITY METRICS (n={sample_count})")
        log(f"     Completion Rate: {avg_completion*100:.0f}% (ends with punctuation)")
        log(f"     Repetition Score: {avg_repetition*100:.1f}% (lower is better)")
        log(f"     Unique Token Ratio: {avg_unique*100:.1f}%")

        # Quality indicator
        if avg_repetition < 0.3 and avg_unique > 0.6:
            log("     Quality: 🟢 GOOD")
        elif avg_repetition < 0.5 and avg_unique > 0.4:
            log("     Quality: 🟡 IMPROVING")
        else:
            log("     Quality: 🔴 NEEDS WORK (expect improvement by step 2k-6k)")

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

    # Phase-specific parameters
    sync_steps: int = 3
    sync_lr: float = 0.1

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

    # Ontological-specific parameters
    bhava_embed_dim: int = 128
    num_drishti_heads: int = 4

    # Training hyperparameters
    batch_size: int = 8
    gradient_accumulation: int = 1
    max_steps: int = 10000
    warmup_steps: int = 500

    # Optimizer
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    max_grad_norm: float = 1.0
    use_per_layer_clipping: bool = False  # Clip auth/sens layers separately

    # Mixed precision
    mixed_precision: str = "bf16"

    # Gradient checkpointing
    gradient_checkpointing: bool = False
    checkpoint_offload_cpu: bool = False  # Offload checkpointed activations to CPU (metabolic tuning)

    # Checkpointing
    checkpoint_dir: str = "checkpoints_unified"
    save_every: int = 1000
    eval_every: int = 100
    log_every: int = 10

    # Logging verbosity
    quiet: bool = False  # Quiet mode: only print Critical 5 (Loss, PPL, S/A, GC, Conf)

    # Dataset
    dataset: str = "wikitext103"
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

    # V9.5.1 Force Evolution (manual intervention)
    force_evolution_stage: int = None  # Force to stage: 1=6:6, 2=5:7, 3=4:8, 4=3:9

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
    gc_floor: float = 0.65                # Minimum GC for PIDv2 intervention

    # PIDv2 Controller settings (V9.4.4)
    controller: str = "none"  # none, pidv2, emergency_pd
    pidv2_kp_min: float = 0.10
    pidv2_kp_max: float = 0.30
    pidv2_kp_sensitivity: float = 5.0
    pidv2_ki: float = 0.02
    pidv2_kd: float = 0.10
    pidv2_a_min: float = 0.40  # Raised from 0.30 to boost sensory floor
    pidv2_c_floor: float = 0.68
    pidv2_c_good: float = 0.76
    pidv2_w_s: float = 0.30  # Semantic weight
    pidv2_semantic_scale: float = 50.0
    pidv2_handshake_dampen: bool = True

    # Phase ramp settings (for handshake dampening)
    phase_delay_steps: int = 0
    phase_ramp_steps: int = 7000

    # Formula [1331]: 9:3 Hierarchical Split Configuration
    use_9_3_split: bool = False           # Enable 9:3 Authority/Sensory gradient scaling
    authority_layers: int = 9             # Number of Authority (State-Delta) layers
    sensory_layers: int = 3               # Number of Sensory (Quadratic) layers
    alpha_sens_initial: float = 0.01      # Initial sensory gradient multiplier (very heavy dampening to prevent S/A imbalance)
    alpha_sens_max: float = 0.7           # Maximum sensory gradient (after warmup/relaxation)
    gradient_warmup_steps: int = 500      # Steps to ramp α_sens from initial to max

    # Dynamic Relaxation: 9:3 → 6:6 transition
    enable_dynamic_relaxation: bool = False  # Enable automatic 9:3 → 6:6 transition
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

    # CSR Phoneme-Ontological Grounding
    enable_csr: bool = True                  # Enable CSR phoneme grounding
    csr_lambda: float = 0.1                  # CSR injection strength
    csr_use_phase_gating: bool = True        # Gate Phase Attention with CSR confidence
    csr_trainable: bool = True               # Allow CSR projection to train
    csr_use_entropy_sink: bool = True        # Apply Layer 0 entropy floor
    csr_use_synthesis_gate: bool = True      # Apply Layer 11 synthesis reconciliation

    # SGP (Stochastic Gradient Persistence) - "Cement" for CSR structure
    enable_sgp: bool = True                  # Enable SGP synchronized with Sattvic Controller
    sgp_base_rate: int = 25                  # Base SGP rate (Toroidal Refresh Rate)
    sgp_stagnation_rate: int = 12            # Rate when stagnation detected (HALVED for more frequent hammering)
    sgp_gamma: float = 0.3                   # Persistence coefficient: θ ← θ - η(∇θ + γ∇θ_persisted)

    # Sattvic Controller (Dynamic λ_csr regulation)
    sattvic_initial_lambda: float = 0.5      # Initial λ_csr during warmup
    sattvic_floor_lambda: float = 0.1        # Minimum λ_csr after decay
    sattvic_warmup_steps: int = 500          # Steps for warmup phase
    sattvic_variance_window: int = 50        # Window for entropy variance detection
    sattvic_variance_threshold: float = 0.001  # Variance threshold for stagnation

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

    # Auto Batch Sizing (VRAM-based startup probing)
    enable_auto_batch: bool = False          # Enable automatic batch size detection at startup
    auto_batch_target_utilization: float = 0.80  # Target VRAM utilization (80%)
    auto_batch_safety_margin: float = 0.05   # Extra headroom (5%)
    auto_batch_target_effective: int = 0     # Target effective batch (0 = just find max, no accum)

    # Resume checkpoint
    resume: str = ""
    resume_weights_only: bool = False

    # TensorBoard
    tensorboard: bool = True

    # Quality Sampling
    sample_every: int = 500  # Generate samples every N steps (0 = disabled)
    sample_prompts: tuple = (
        # Original open-ended prompts
        "The history of the Roman Empire began when",
        "In computer science, algorithms are",
        # Targeted probes for factual continuity (ChatGPT recommendation)
        "The Roman Empire began when Julius Caesar",
        "An algorithm is a step-by-step procedure that",
        # Syntax closure probes
        "A triangle has three sides, therefore",
        "If A implies B and A is true, then",
        # Causal reasoning probe
        "Water boils at 100 degrees Celsius because",
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
# DATASET
# =============================================================================

class TextDataset(Dataset):
    """Dataset for language modeling."""

    def __init__(self, tokens: torch.Tensor, seq_len: int):
        self.tokens = tokens
        self.seq_len = seq_len
        self.num_samples = len(tokens) // seq_len

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]
        return chunk[:-1], chunk[1:]


def load_data(config: UnifiedTrainingConfig, tokenizer) -> Tuple[DataLoader, DataLoader]:
    """Load and tokenize dataset."""
    print(f"Loading {config.dataset} dataset...")

    if config.dataset == "wikitext103":
        ds = load_dataset("wikitext", "wikitext-103-v1")
    elif config.dataset == "wikitext2":
        ds = load_dataset("wikitext", "wikitext-2-v1")
    else:
        raise ValueError(f"Unknown dataset: {config.dataset}")

    def tokenize(split):
        text = "\n".join(ds[split]["text"])
        if hasattr(tokenizer, "encode"):
            tokens = tokenizer.encode(text)
        else:
            tokens = tokenizer(text)["input_ids"]
        return torch.tensor(tokens, dtype=torch.long)

    train_tokens = tokenize("train")
    val_tokens = tokenize("validation")

    print(f"Loaded {len(train_tokens):,} train tokens, {len(val_tokens):,} val tokens")

    train_dataset = TextDataset(train_tokens, config.max_seq_len)
    val_dataset = TextDataset(val_tokens, config.max_seq_len)

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


# =============================================================================
# MODEL CREATION
# =============================================================================

def create_model(config: UnifiedTrainingConfig, device: torch.device) -> nn.Module:
    """Create model based on configuration."""
    preset = MODEL_PRESETS[config.model_size]

    if config.model_type == "ontological":
        if not ONTOLOGICAL_AVAILABLE:
            raise ImportError("Ontological models not available. Check imports.")

        # Create SymbolU12 with Bhava
        bhava_config = SymbolU12BhavaConfig(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            max_seq_len=config.max_seq_len,
            num_heads=preset["num_heads"],
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
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
        )

    elif config.model_type == "hybrid":
        model = HybridPhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
        )

    elif config.model_type == "gen2":
        if not GEN2_AVAILABLE:
            raise ImportError("Gen 2 models not available. Check imports.")

        # Determine num_layers: use 12 for 9:3 split, otherwise preset
        # 9:3 split requires exactly (authority_layers + sensory_layers) = 12 layers
        if config.use_9_3_split:
            gen2_num_layers = config.authority_layers + config.sensory_layers
        else:
            gen2_num_layers = preset["num_layers"]

        # Create SymbolU12 Gen 2 (Hierarchical Complex Bhava)
        gen2_config = SymbolU12Gen2Config(
            vocab_size=config.vocab_size,
            embed_dim=preset["embed_dim"],
            num_heads=preset["num_heads"],
            num_layers=gen2_num_layers,
            complex_dim=64,  # Complex embedding dimension
            max_seq_len=config.max_seq_len,
            dropout=config.dropout,
            ffn_mult=preset["ff_dim"] / preset["embed_dim"],
        )

        model = SymbolU12Gen2(gen2_config)
        print(f"\n  [Gen 2] Hierarchical Complex Bhava enabled")
        print(f"  [Gen 2] Complex dim: {gen2_config.complex_dim}")
        print(f"  [Gen 2] Num layers: {gen2_num_layers} (9:3 split: {config.use_9_3_split})")
        print(f"  [Gen 2] Hierarchy: 3-tier phase rotation")

    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    # Enable gradient checkpointing after model creation
    # V9.5.2 Metabolic Tuning: Use non-reentrant checkpointing for better memory efficiency
    if config.gradient_checkpointing:
        if hasattr(model, 'gradient_checkpointing_enable'):
            # Modern HuggingFace-style API
            model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
            print(f"  [Metabolic] Gradient checkpointing enabled (non-reentrant mode)")
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


def update_alpha_schedule(model: nn.Module, step: int, config: UnifiedTrainingConfig) -> float:
    """
    Update alpha_phase for HybridAttentionLayer modules based on decay schedule.

    Returns current alpha_phase value.
    """
    if config.model_type not in ("phase", "hybrid"):
        return config.alpha_phase  # No decay for ontological

    # Calculate current alpha based on linear decay
    if step >= config.alpha_decay_steps:
        current_alpha = config.alpha_phase_end
    else:
        frac = step / config.alpha_decay_steps
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


def compute_phase_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    config: UnifiedTrainingConfig,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """Compute loss for phase/hybrid models."""
    B, N, V = logits.shape

    lm_loss = F.cross_entropy(
        logits.view(-1, V),
        targets.view(-1),
        ignore_index=-100,
    )

    metrics = {
        "lm_loss": lm_loss.item(),
        "ppl": math.exp(min(lm_loss.item(), 20)),
        "total_loss": lm_loss.item(),
    }

    return lm_loss, metrics


# =============================================================================
# TRAINING LOOP
# =============================================================================

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

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    tokenizer.model_max_length = int(1e12)

    # Create model BEFORE data loading (needed for AutoBatchSizer)
    model = create_model(config, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"\n  Model Parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # Auto Batch Sizing: Probe VRAM at startup to find optimal batch size
    if config.enable_auto_batch:
        print(f"\n  Auto Batch Sizing: ENABLED")

        # V9.5.2: Calibrated max batch limits from real-world testing
        # These are HARD LIMITS for sovereign loss + 2048 seq len
        # Medium and Large models have SAME limits (sovereign loss dominates)
        # Only tiny/small can use larger batches
        model_size_scale = {
            "tiny": 2.0,    # Can use 2x the base limit
            "small": 1.5,   # Can use 1.5x the base limit
            "medium": 1.0,  # Base limit (tested)
            "large": 1.0,   # Same as medium (sovereign loss dominates)
        }
        size_factor = model_size_scale.get(config.model_size, 1.0)

        # V9.5.2: Sequence length scaling (baseline: 2048)
        # Only scale UP for shorter sequences, not down (limits are already tight)
        seq_baseline = 2048
        if config.max_seq_len < seq_baseline:
            # Shorter sequences can use slightly larger batches
            seq_factor = min(1.5, seq_baseline / config.max_seq_len)
        else:
            # Longer sequences: be conservative
            seq_factor = max(0.5, seq_baseline / config.max_seq_len)

        # Combined scaling factor
        combined_factor = size_factor * seq_factor

        # Sovereign loss requires (B, Seq, Vocab) tensors - massive overhead
        # V9.5.2: HARD LIMITS calibrated from real GPU testing (medium/large, 2048 seq)
        #   - A100 (80GB): 16 max batch
        #   - H100 (96GB): 24 max batch
        #   - H200 (141GB): 32 max batch
        if config.enable_sovereign_loss:
            total_vram_gb = torch.cuda.get_device_properties(device).total_memory / 1e9
            if total_vram_gb >= 140:  # H200 class (141GB+)
                base_max_batch = 32
            elif total_vram_gb >= 90:  # H100 class (96GB)
                base_max_batch = 24
            elif total_vram_gb >= 70:  # A100 80GB class
                base_max_batch = 16
            else:  # Smaller GPUs
                base_max_batch = 8
            # Apply scaling (only for tiny/small models or shorter sequences)
            auto_max_batch = max(8, int(base_max_batch * combined_factor))
            print(f"  ⚠️  Sovereign Loss: max_batch={auto_max_batch} (VRAM: {total_vram_gb:.0f}GB, model: {config.model_size}, seq: {config.max_seq_len}, scale: {combined_factor:.2f}x)")
        else:
            auto_max_batch = max(8, int(64 * combined_factor))

        auto_sizer = AutoBatchSizer(
            model=model,
            seq_len=config.max_seq_len,
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

    # Initialize CSR Phoneme-Ontological Grounding
    csr_provider = None
    csr_entropy_sink = None
    csr_synthesis_gate = None
    if config.enable_csr and CSR_AVAILABLE:
        # V9.5.2 Optimization: Wait for background G2P preload to complete
        # This ensures CMUdict and g2p_en are ready (should already be loaded by now)
        if csr_wait_preload is not None:
            csr_wait_preload(timeout=30.0)
        csr_provider, csr_entropy_sink, csr_synthesis_gate = create_csr_for_training(
            model_config=model.config if hasattr(model, 'config') else type('Config', (), {'d_model': 512})(),
            tokenizer=tokenizer,
            lambda_csr=config.csr_lambda,
            use_phase_gating=config.csr_use_phase_gating,
            trainable=config.csr_trainable,
        )
        csr_provider = csr_provider.to(device)
        csr_entropy_sink = csr_entropy_sink.to(device) if config.csr_use_entropy_sink else None
        csr_synthesis_gate = csr_synthesis_gate.to(device) if config.csr_use_synthesis_gate else None
        print(f"  CSR Phoneme Grounding: ENABLED (λ_csr={config.csr_lambda})")
    elif config.enable_csr and not CSR_AVAILABLE:
        print(f"  CSR Phoneme Grounding: Disabled (module not available)")
    else:
        print(f"  CSR Phoneme Grounding: Disabled")

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

        # Register Authority layer parameters (layers 0-8) for gradient persistence
        authority_params = []
        for name, param in model.named_parameters():
            # Match layers 0-8 (Authority layers)
            layer_match = False
            for i in range(9):  # 0-8
                if f"layers.{i}." in name or f"layer.{i}." in name:
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
        vram_threshold=0.92,
        vram_critical=0.97,
        check_interval=10,
        b1_compensation_rate=0.20,
        enable_accumulation_scaling=True,
        target_effective_batch=config.batch_size,
    )
    print(f"  VRAM Governor: ENABLED (threshold=92%, compensation=20%)")

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
    print(f"  Training Gunas: ENABLED (S/R/T tracking)")

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

        # Create HiddenStateExtractor for models that don't return hidden_states
        hidden_state_extractor = HiddenStateExtractor(model, num_layers=12)
        print(f"    → Hidden State Extractor: ENABLED ({len(hidden_state_extractor.hooks)} hooks registered)")

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

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
        betas=(config.beta1, config.beta2),
    )

    # Scheduler
    scheduler = CosineAnnealingLR(
        optimizer,
        T_max=config.max_steps - config.warmup_steps,
        eta_min=config.learning_rate * 0.1,
    )

    # Resume from checkpoint if specified
    resume_step = 0
    best_val_loss = float('inf')
    resumed_hgs_state = None
    resumed_drc_state = None
    if config.resume:
        resume_path = Path(config.resume)
        if resume_path.exists():
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
        else:
            print(f"\n  ⚠️  Checkpoint not found: {resume_path}")
            print(f"      Starting training from scratch...")

    # Formula [1331]: 9:3 Hierarchical Gradient Scaling
    gradient_scaler_hgs = None
    if config.use_9_3_split:
        gradient_scaler_hgs = HierarchicalGradientScaler(
            model=model,
            authority_layers=config.authority_layers,
            sensory_layers=config.sensory_layers,
            alpha_sens_min=config.alpha_sens_initial,
            alpha_sens_max=config.alpha_sens_max,
            warmup_steps=config.gradient_warmup_steps,
            layer_attr="blocks",  # Common attribute name for transformer layers
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
        )

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

    # Mixed precision
    scaler = torch.amp.GradScaler('cuda') if config.mixed_precision != "none" else None
    autocast_dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

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
        )
        authority_controller = AuthorityPIDv2(pidv2_config)
        print(f"\n  PIDv2 Governor ENABLED")
        print(f"    Dynamic Kp: [{config.pidv2_kp_min}, {config.pidv2_kp_max}]")
        print(f"    Semantic Weight (W_s): {config.pidv2_w_s:.0%}")
        print(f"    Authority floor: {config.pidv2_a_min}")
    elif config.controller == "emergency_pd" and PIDV2_AVAILABLE:
        pd_config = EmergencyPDConfig(A_min=0.25)
        authority_controller = EmergencyPD(pd_config)
        print(f"\n  Emergency PD Controller ENABLED")
    elif config.controller != "none":
        print(f"\n  Warning: Controller '{config.controller}' not available")

    # V9.4.5: Initialize Friction Controller with Corrective Actions
    friction_controller = None
    if PIDV2_AVAILABLE and config.model_type == "hybrid":
        friction_controller = FrictionController(FrictionControllerConfig())
        print(f"\n  V9.4.5: Friction Controller ENABLED")
        print(f"    Alignment thresholds: warn={friction_controller.config.align_warning}, crit={friction_controller.config.align_critical}")
        print(f"    Dominance range: [{friction_controller.config.dom_low}, {friction_controller.config.dom_high}]")

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

    print(f"\n{'='*70}")
    print("   STARTING TRAINING")
    print(f"{'='*70}\n")

    model.train()
    train_iter = iter(train_loader)
    step_start_time = time.time()
    running_loss = 0.0
    accumulation_step = 0

    # Toroidal Bridge tracking
    toroidal_coherence = 0.5  # Neutral initial coherence
    toroidal_loss_value = 0.0
    toroidal_seed = None  # Will be populated after first forward pass

    # Training Gunas: Initialize before loop (used by Evolutionary Flow and Metacognitive Tracker)
    guna_s, guna_r, guna_t = 0.33, 0.33, 0.34  # Default balanced state

    # Sensory flow tracking for Saturation Gate (used by DynamicRelaxationController)
    last_sensory_flow = 0.5  # Default value, updated each step from EvoFlow

    while global_step < config.max_steps:
        # Get batch
        try:
            x, y = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            x, y = next(train_iter)

        x, y = x.to(device), y.to(device)

        # Forward pass
        # Clear hidden state extractor before forward pass so hooks capture fresh states
        if 'hidden_state_extractor' in dir() and hidden_state_extractor is not None:
            hidden_state_extractor.clear()

        with torch.amp.autocast('cuda', dtype=autocast_dtype):
            if config.model_type == "ontological":
                outputs = model(x)
                # Extract phase angles if available (for U1/U2 coherence)
                phase_angles = outputs.get('phase_angles', None)
                loss, metrics = compute_ontological_loss(
                    outputs, y, config,
                    sovereign_loss=sovereign_loss,
                    sovereign_engine=sovereign_engine,
                    phase_angles=phase_angles,
                    epoch=global_step // len(train_loader),
                )
            elif config.model_type == "gen2":
                outputs = model(x, labels=y)
                loss = outputs['loss']
                metrics = {
                    'coherence': outputs['coherence'].mean().item(),
                    'level_1_coh': outputs['level_coherences'][:, 0].mean().item(),
                    'level_2_coh': outputs['level_coherences'][:, 1].mean().item(),
                    'level_3_coh': outputs['level_coherences'][:, 2].mean().item(),
                }
            else:
                # Phase or Hybrid - handle both tensor and dict returns
                outputs = model(x)  # Use 'outputs' consistently for hidden_state_extractor
                if isinstance(outputs, dict):
                    logits = outputs.get('logits', outputs.get('output', outputs.get('last_hidden_state')))
                else:
                    logits = outputs
                loss, metrics = compute_phase_loss(logits, y, config)

            # CSR Phoneme-Ontological Grounding Integration
            csr_metrics = {}
            if csr_provider is not None:
                # Decode tokens for phoneme extraction
                token_strings = None
                if tokenizer is not None:
                    try:
                        token_strings = [[tokenizer.decode([tid.item()]) for tid in batch] for batch in x]
                    except Exception:
                        token_strings = None

                # Compute CSR embeddings
                csr_output = csr_provider(x, token_strings=token_strings)
                csr_emb = csr_output['csr_emb']
                csr_affinity = csr_output['csr_affinity']
                csr_confidence = csr_output['csr_confidence']

                # Get hidden states for CSR alignment (if available)
                csr_hidden = None
                if isinstance(outputs, dict):
                    csr_hidden = outputs.get('last_hidden_state', outputs.get('logits'))
                elif isinstance(outputs, torch.Tensor):
                    csr_hidden = outputs

                if csr_hidden is not None and csr_hidden.shape[-1] == csr_emb.shape[-1]:
                    # CSR alignment loss: encourage hidden states to correlate with CSR embeddings
                    # Use cosine similarity weighted by confidence
                    csr_hidden_norm = torch.nn.functional.normalize(csr_hidden, dim=-1)
                    csr_emb_norm = torch.nn.functional.normalize(csr_emb, dim=-1)
                    csr_similarity = (csr_hidden_norm * csr_emb_norm).sum(dim=-1)
                    csr_alignment_loss = (1 - csr_similarity) * csr_confidence.squeeze(-1)
                    csr_loss = csr_alignment_loss.mean() * config.csr_lambda

                    # Add CSR loss to total loss
                    loss = loss + csr_loss
                    csr_metrics['csr_loss'] = csr_loss.item()
                    csr_metrics['csr_confidence'] = csr_confidence.mean().item()
                    csr_metrics['csr_similarity'] = csr_similarity.mean().item()
                else:
                    csr_metrics['csr_loss'] = 0.0
                    csr_metrics['csr_confidence'] = csr_confidence.mean().item() if csr_confidence is not None else 0.0

                # CSR Safety Layers: EntropySink (Layer 0) and SynthesisGate (Layer 11)
                # These enforce ontological safety at the boundaries of the 12D structure
                if hidden_state_extractor is not None:
                    layer_hidden_states = hidden_state_extractor.get_hidden_states(outputs, x)

                    if layer_hidden_states is not None and len(layer_hidden_states) >= 12:
                        # EntropySink: Layer 0 (O1_Potential) safety - prevents mode collapse
                        if csr_entropy_sink is not None:
                            layer_0_hidden = layer_hidden_states[0]
                            if layer_0_hidden.shape[-1] == csr_emb.shape[-1]:
                                _, sink_metrics = csr_entropy_sink(layer_0_hidden, csr_affinity)
                                csr_metrics['entropy_sink_entropy'] = sink_metrics.get('entropy', 0.0)
                                csr_metrics['entropy_sink_anchor'] = sink_metrics.get('anchor_strength', 0.0)
                                # Add entropy floor loss: penalize if entropy drops below min_entropy
                                if 'entropy' in sink_metrics:
                                    entropy_val = sink_metrics['entropy']
                                    if isinstance(entropy_val, torch.Tensor):
                                        entropy_floor_loss = torch.clamp(0.1 - entropy_val.mean(), min=0) * 0.1
                                        loss = loss + entropy_floor_loss
                                        csr_metrics['entropy_floor_loss'] = entropy_floor_loss.item()

                        # SynthesisGate: Layer 11 (O11_Integration) safety - reconciles structure with flow
                        if csr_synthesis_gate is not None:
                            layer_11_hidden = layer_hidden_states[11]
                            if layer_11_hidden.shape[-1] == csr_emb.shape[-1]:
                                synthesized, gate_metrics = csr_synthesis_gate(layer_11_hidden, csr_emb, csr_affinity)
                                csr_metrics['synthesis_gate_value'] = gate_metrics.get('gate_value', 0.0)
                                csr_metrics['synthesis_coherence'] = gate_metrics.get('coherence', 0.0)
                                # Add synthesis coherence loss: encourage high coherence at integration layer
                                if 'coherence' in gate_metrics:
                                    coherence_val = gate_metrics['coherence']
                                    if isinstance(coherence_val, torch.Tensor):
                                        synthesis_loss = (1 - coherence_val.mean()) * 0.05
                                        loss = loss + synthesis_loss
                                        csr_metrics['synthesis_loss'] = synthesis_loss.item()

            # Initialize default guna values for first iteration
            # (actual values computed later in the loop, but needed here for evolutionary bridge)
            try:
                _ = guna_s
            except NameError:
                guna_s, guna_r, guna_t = 0.33, 0.33, 0.34

            # Toroidal Evolutionary Bridge: O12 → O1 state carryover
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
                    # Get O12 (harvest) - either last element of list or the tensor itself
                    if isinstance(hidden_states, (list, tuple)) and len(hidden_states) > 0:
                        o12_state = hidden_states[-1]  # Last layer = O12
                        o1_state = hidden_states[0] if len(hidden_states) > 1 else o12_state
                    else:
                        o12_state = hidden_states
                        o1_state = hidden_states

                    # Compute toroidal coherence if we have a prior seed
                    if toroidal_seed is not None:
                        toroidal_coherence = evolutionary_bridge.compute_toroidal_coherence(
                            o1_state, toroidal_seed
                        )

                        # Compute toroidal loss
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
                        o1_target = o1_state.detach()  # Don't backprop through model
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
            evo_result = None
            evo_lr_multiplier = 1.0
            # Note: guna_s/r/t initialized earlier in the loop (before evolutionary_bridge section)
            if evolutionary_engine is not None and hidden_state_extractor is not None:
                # Extract hidden states using HiddenStateExtractor (handles models without hidden_states output)
                # Note: clear() was called before forward pass, hooks captured states during model(x)
                hidden_states = hidden_state_extractor.get_hidden_states(outputs, x)

                if hidden_states is not None and len(hidden_states) > 0:

                    # V9.4.6: Sensory Noise Injection (SNI)
                    # Break repetitive loops by injecting tiny noise into sensory layers
                    # when entropy drops below floor (signaling "city of the city" patterns)
                    sni_entropy_floor = 0.30
                    sni_noise_scale = 1e-4
                    current_entropy = metrics.get("onto_entropy", 1.0)

                    if current_entropy < sni_entropy_floor:
                        # Inject noise into sensory layers (O10-O12 = indices 9, 10, 11)
                        sensory_indices = [9, 10, 11]
                        for idx in sensory_indices:
                            if idx < len(hidden_states):
                                hidden_states[idx] = hidden_states[idx] + \
                                    torch.randn_like(hidden_states[idx]) * sni_noise_scale
                        metrics['sni_triggered'] = True
                    else:
                        metrics['sni_triggered'] = False

                    # Update Gunas in engine for metacognitive decisions
                    evolutionary_engine.update_gunas(guna_s, guna_r, guna_t)

                    # Process through evolutionary system with delayed resonance
                    evo_result = evolutionary_engine.process(
                        layer_states=hidden_states,
                        compute_loss=True,
                        apply_resonance=True,
                    )

                    # Add evolutionary loss to total
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

            # Scale for gradient accumulation
            loss = loss / config.gradient_accumulation

        # Backward pass
        if scaler is not None:
            scaler.scale(loss).backward()
        else:
            loss.backward()

        running_loss += loss.item() * config.gradient_accumulation
        accumulation_step += 1

        # Update weights
        if accumulation_step % config.gradient_accumulation == 0:
            if scaler is not None:
                scaler.unscale_(optimizer)

            # Note: Gradient scaling via hooks happens automatically during backward()
            # We'll call step() after optimizer.step() to update warmup schedule

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
            friction_alignment = 0.0
            friction_dominance = 1.0
            friction_penalty = 1.0
            if PIDV2_AVAILABLE and global_step % 10 == 0:  # Every 10 steps to save compute
                try:
                    friction_alignment, friction_dominance = measure_friction(model, local_layers=6)
                    # Update friction controller with corrective actions
                    if friction_controller is not None:
                        friction_penalty = friction_controller.update(friction_alignment, friction_dominance)
                except Exception as e:
                    if global_step % 100 == 0:  # Log warning every 100 steps to avoid spam
                        print(f"  Warning: Friction measurement failed at step {global_step}: {e}")

            optimizer.zero_grad()

            # Update scheduler after warmup
            if global_step >= config.warmup_steps:
                scheduler.step()

            # Update alpha schedule for phase/hybrid models
            current_alpha = update_alpha_schedule(model, global_step, config)

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
                # Get gradient norm from HGS metrics or compute from model
                if hgs_metrics:
                    grad_norm = hgs_metrics.get('a_grad_norm', 0.0) + hgs_metrics.get('s_grad_norm', 0.0)
                else:
                    # Fallback: compute total gradient norm
                    grad_norm = sum(p.grad.norm().item() for p in model.parameters() if p.grad is not None)

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

                # SGP Metabolic Step: Inject persisted gradients to Authority layers
                pulse_applied = sgp_controller.sgp_metabolic_step({
                    'entropy': entropy,
                    'variance': sattvic_controller.entropy_variance,
                })

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

                    # V9.5.1 Granular Evolution: Check for further evolution (6:6 → 5:7 → 4:8 → 3:9)
                    evolution_result = relaxation_controller.check_granular_evolution(
                        metrics=metrics,
                        vram_usage=vram_usage,
                        global_step=global_step,
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
                    train_loader = DataLoader(
                        dataset,
                        batch_size=new_batch,
                        shuffle=True,
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
                    # Memory usage
                    if device.type == "cuda":
                        mem_used = torch.cuda.max_memory_allocated() / (1024**3)
                        mem_str = f" | VRAM: {mem_used:.1f}GB"
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

                    # Add alpha for phase/hybrid models
                    if config.model_type in ("phase", "hybrid"):
                        log_msg += f" | α_phase: {current_alpha:.2f}"

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

                    # Training Gunas: S/R/T with dominant state icon
                    if training_gunas is not None:
                        # Determine dominant Guna and icon
                        if guna_s > guna_r and guna_s > guna_t:
                            guna_icon = "☀️"  # Sattva - clarity/learning
                        elif guna_r > guna_t:
                            guna_icon = "🔥"  # Rajas - action/activity
                        else:
                            guna_icon = "🌙"  # Tamas - inertia/plateau
                        log_msg += f" | S:{guna_s:.2f} R:{guna_r:.2f} T:{guna_t:.2f}{guna_icon}"

                    # Toroidal Bridge: Coherence and metacognitive status (only every 100 steps)
                    if evolutionary_bridge is not None and is_verbose_step:
                        log_msg += f" | {evolutionary_bridge.get_coherence_status()}"
                        if metacognitive_tracker is not None:
                            log_msg += f" {metacognitive_tracker.get_status()}"

                    # Full Evolutionary Flow: Multi-scale coherence and metacognitive status
                    if evolutionary_engine is not None and evo_result is not None:
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

                print(log_msg)
                step_start_time = time.time()

            # Evaluation
            if global_step % config.eval_every == 0:
                val_loss, val_metrics = evaluate(
                    model, val_loader, device, config, autocast_dtype,
                    sovereign_loss=sovereign_loss,
                    sovereign_engine=sovereign_engine,
                )
                val_ppl = val_metrics['ppl']
                current_coh = val_metrics.get('coherence', 0.75)

                # PIDv2 Controller Update (V9.4.4)
                if authority_controller is not None:
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

                    print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f} | {authority_controller.get_status_string()}", end="")
                    if relaxation_dampening_active:
                        print(f" [RELAX_DAMP]")
                    else:
                        print()

                    # V9.4.5: Log Friction Controller status (with corrective actions)
                    if friction_controller is not None:
                        print(f"  --> {friction_controller.get_status_string()}")
                        if friction_controller.correction_active:
                            print(f"  ⚠️ FRICTION CORRECTION: LR reduced by {(1-friction_controller.friction_penalty)*100:.0f}%")

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
                else:
                    print(f"  --> Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f}")

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
                if adaptive_controller is not None:
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

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    save_checkpoint(
                        model, optimizer, scheduler, global_step, best_val_loss,
                        ckpt_dir / "best.pt",
                        hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
                        drc_state=relaxation_controller.get_state() if relaxation_controller else None,
                    )
                    print(f"  --> New best! Saved to {ckpt_dir / 'best.pt'}")

                # Quality Sampling
                if config.sample_every > 0 and global_step % config.sample_every == 0:
                    if tokenizer is not None:
                        run_quality_samples(model, tokenizer, config, device, global_step)
                    else:
                        print(f"  [Sampling] Skipped - tokenizer not available")

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

            # Save checkpoint (overwrites last.pt each time)
            if global_step % config.save_every == 0:
                save_checkpoint(
                    model, optimizer, scheduler, global_step, best_val_loss,
                    ckpt_dir / "last.pt",
                    hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
                    drc_state=relaxation_controller.get_state() if relaxation_controller else None,
                )
                # v2.7 Training State Tracker: Save state on checkpoint
                if training_state_tracker is not None and training_state_tracker.enabled:
                    training_state_tracker.save_state()

    # Final save
    save_checkpoint(
        model, optimizer, scheduler, global_step, best_val_loss,
        ckpt_dir / "final.pt",
        hgs_state=gradient_scaler_hgs.get_state() if gradient_scaler_hgs else None,
        drc_state=relaxation_controller.get_state() if relaxation_controller else None,
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
    if authority_controller is not None:
        print(f"  Final Authority: {authority_controller.A:.3f}")
    print(f"  Final Checkpoint: {ckpt_dir / 'final.pt'}")


def evaluate(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    config: UnifiedTrainingConfig,
    autocast_dtype: torch.dtype,
    sovereign_loss: Optional['SovereignLoss'] = None,
    sovereign_engine: Optional['SovereignEngine'] = None,
) -> Tuple[float, Dict[str, float]]:
    """Evaluate model on validation set."""
    model.eval()
    total_loss = 0.0
    total_batches = 0

    with torch.no_grad():
        for x, y in val_loader:
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


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler._LRScheduler,
    step: int,
    best_val_loss: float,
    path: Path,
    hgs_state: Optional[dict] = None,
    drc_state: Optional[dict] = None,
):
    """Save training checkpoint with optional HGS/DRC state.

    For last.pt checkpoints, explicitly removes old file before saving new one
    to ensure clean replacement and avoid potential corruption.
    """
    checkpoint = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "step": step,
        "best_val_loss": best_val_loss,
        "rng_state": torch.get_rng_state(),
    }

    # Add CUDA RNG state if available
    if torch.cuda.is_available():
        checkpoint["cuda_rng_state"] = torch.cuda.get_rng_state()

    # Add HGS state if provided
    if hgs_state is not None:
        checkpoint["hgs_state"] = hgs_state

    # Add DRC state if provided
    if drc_state is not None:
        checkpoint["drc_state"] = drc_state

    # Explicitly remove old checkpoint before saving (especially for last.pt)
    # This ensures clean replacement and frees disk space before writing
    if path.exists():
        path.unlink()

    torch.save(checkpoint, path)


def load_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
    weights_only: bool = False,
    device: torch.device = None,
) -> Dict[str, Any]:
    """Load training checkpoint.

    Args:
        path: Path to checkpoint file
        model: Model to load weights into
        optimizer: Optimizer to restore state (None if weights_only)
        scheduler: Scheduler to restore state (None if weights_only)
        weights_only: If True, only load model weights (fresh optimizer/scheduler)
        device: Device to map tensors to

    Returns:
        Dict with checkpoint info (step, best_val_loss, etc.)
    """
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    print(f"\n  📂 Loading checkpoint from: {path}")

    # Load checkpoint
    checkpoint = torch.load(path, map_location=device, weights_only=False)

    # Load model weights
    model.load_state_dict(checkpoint["model"])
    print(f"    ✓ Model weights loaded")

    result = {
        "step": checkpoint.get("step", 0),
        "best_val_loss": checkpoint.get("best_val_loss", float('inf')),
    }

    if weights_only:
        print(f"    → Weights-only mode: Optimizer/Scheduler will start fresh")
        result["step"] = 0  # Start from step 0 with fresh optimizer
        return result

    # Restore optimizer state
    if optimizer is not None and "optimizer" in checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer"])
        print(f"    ✓ Optimizer state restored")

    # Restore scheduler state
    if scheduler is not None and "scheduler" in checkpoint:
        scheduler.load_state_dict(checkpoint["scheduler"])
        print(f"    ✓ Scheduler state restored")

    # Restore RNG states for reproducibility
    if "rng_state" in checkpoint:
        torch.set_rng_state(checkpoint["rng_state"])
        print(f"    ✓ RNG state restored")

    if "cuda_rng_state" in checkpoint and torch.cuda.is_available():
        torch.cuda.set_rng_state(checkpoint["cuda_rng_state"])
        print(f"    ✓ CUDA RNG state restored")

    # Return additional state for HGS/DRC restoration
    if "hgs_state" in checkpoint:
        result["hgs_state"] = checkpoint["hgs_state"]
        print(f"    ✓ HGS state available for restoration")

    if "drc_state" in checkpoint:
        result["drc_state"] = checkpoint["drc_state"]
        print(f"    ✓ DRC state available for restoration")

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
                       choices=["ontological", "phase", "hybrid", "gen2"],
                       help="Model architecture type (gen2 = hierarchical complex Bhava)")
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large"],
                       help="Model size preset")
    parser.add_argument("--max_seq_len", type=int, default=2048,
                       help="Maximum sequence length")

    # Training
    parser.add_argument("--batch_size", type=int, default=8,
                       help="Batch size per GPU")
    parser.add_argument("--gradient_accumulation", type=int, default=1,
                       help="Gradient accumulation steps")
    parser.add_argument("--max_steps", type=int, default=10000,
                       help="Maximum training steps")
    parser.add_argument("--learning_rate", type=float, default=3e-4,
                       help="Peak learning rate")
    parser.add_argument("--use_per_layer_clipping", action="store_true",
                       help="Clip authority/sensory gradients separately (respects 9:3 design)")

    # Dataset
    parser.add_argument("--dataset", type=str, default="wikitext103",
                       choices=["wikitext103", "wikitext2"],
                       help="Training dataset")

    # Memory optimization
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing")
    parser.add_argument("--checkpoint_offload_cpu", action="store_true",
                       help="Offload checkpointed activations to CPU (metabolic tuning for large models)")
    parser.add_argument("--mixed_precision", type=str, default="bf16",
                       choices=["none", "fp16", "bf16"],
                       help="Mixed precision training")

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

    # Alpha decay schedule (for phase/hybrid attention)
    parser.add_argument("--alpha_phase_start", type=float, default=0.6,
                       help="Initial alpha_phase value (decays over time)")
    parser.add_argument("--alpha_phase_end", type=float, default=0.4,
                       help="Final alpha_phase value after decay")
    parser.add_argument("--alpha_decay_steps", type=int, default=10000,
                       help="Steps over which alpha_phase decays from start to end")

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

    # V9.5.1 Force Evolution (manual intervention)
    parser.add_argument("--force_evolution_stage", type=int, default=None,
                       help="Force evolution to specific stage: 1=6:6, 2=5:7, 3=4:8, 4=3:9")

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
    parser.add_argument("--eval_every", type=int, default=100,
                       help="Evaluate every N steps")
    parser.add_argument("--save_every", type=int, default=1000,
                       help="Save checkpoint every N steps")
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
    parser.add_argument("--pidv2_w_s", type=float, default=0.30,
                       help="Semantic weight (0.30 = 30%% prompt-based)")
    parser.add_argument("--phase_ramp_steps", type=int, default=7000,
                       help="Steps for phase LR ramp (handshake dampening)")
    parser.add_argument("--tensorboard", action="store_true", default=True,
                       help="Enable TensorBoard logging")
    parser.add_argument("--no_tensorboard", action="store_true",
                       help="Disable TensorBoard logging")

    # Quality Sampling
    parser.add_argument("--sample_every", type=int, default=500,
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
    parser.add_argument("--authority_layers", type=int, default=9,
                       help="Number of Authority (State-Delta) layers")
    parser.add_argument("--sensory_layers", type=int, default=3,
                       help="Number of Sensory (Quadratic) layers")
    parser.add_argument("--alpha_sens_initial", type=float, default=0.01,
                       help="Initial sensory gradient scale (heavy dampening at start)")
    parser.add_argument("--alpha_sens_max", type=float, default=0.7,
                       help="Maximum sensory gradient scale (after warmup/relaxation)")
    parser.add_argument("--gradient_warmup_steps", type=int, default=500,
                       help="Steps to ramp sensory gradient scale from initial to max")

    # Dynamic Relaxation: 9:3 → 6:6 transition
    parser.add_argument("--enable_dynamic_relaxation", action="store_true",
                       help="Enable automatic 9:3 → 6:6 split transition based on stability")
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

    # CSR Phoneme-Ontological Grounding
    parser.add_argument("--enable_csr", action="store_true", default=True,
                       help="Enable CSR phoneme grounding")
    parser.add_argument("--disable_csr", action="store_true",
                       help="Disable CSR phoneme grounding")
    parser.add_argument("--csr_lambda", type=float, default=0.1,
                       help="CSR injection strength")
    parser.add_argument("--csr_use_phase_gating", action="store_true", default=True,
                       help="Gate Phase Attention with CSR confidence")
    parser.add_argument("--csr_trainable", action="store_true", default=True,
                       help="Allow CSR projection to train")
    parser.add_argument("--csr_use_entropy_sink", action="store_true", default=True,
                       help="Apply Layer 0 entropy floor")
    parser.add_argument("--csr_use_synthesis_gate", action="store_true", default=True,
                       help="Apply Layer 11 synthesis reconciliation")

    # SGP (Stochastic Gradient Persistence) - "Cement" for CSR structure
    parser.add_argument("--enable_sgp", action="store_true", default=True,
                       help="Enable SGP synchronized with Sattvic Controller")
    parser.add_argument("--disable_sgp", action="store_true",
                       help="Disable SGP")
    parser.add_argument("--sgp_base_rate", type=int, default=25,
                       help="SGP base rate (Toroidal Refresh Rate)")
    parser.add_argument("--sgp_stagnation_rate", type=int, default=12,
                       help="SGP rate when stagnation detected (HALVED for more frequent hammering)")
    parser.add_argument("--sgp_gamma", type=float, default=0.3,
                       help="SGP persistence coefficient (gamma) for gradient injection")

    # Sattvic Controller (Dynamic λ_csr regulation)
    parser.add_argument("--sattvic_initial_lambda", type=float, default=0.5,
                       help="Initial λ_csr during warmup")
    parser.add_argument("--sattvic_floor_lambda", type=float, default=0.1,
                       help="Minimum λ_csr after decay")
    parser.add_argument("--sattvic_warmup_steps", type=int, default=500,
                       help="Steps for warmup phase")
    parser.add_argument("--sattvic_variance_window", type=int, default=50,
                       help="Window for entropy variance detection")
    parser.add_argument("--sattvic_variance_threshold", type=float, default=0.001,
                       help="Variance threshold for stagnation")

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
                       help="PPL velocity threshold (%) for 'too slow' detection")
    parser.add_argument("--adaptive_velocity_spike", type=float, default=10.0,
                       help="PPL velocity threshold (%) for 'spike' detection")
    parser.add_argument("--adaptive_plateau_window", type=int, default=5,
                       help="Number of evaluations to check for plateau")
    parser.add_argument("--adaptive_plateau_threshold", type=float, default=1.0,
                       help="Minimum improvement (%) to avoid plateau detection")
    parser.add_argument("--adaptive_min_interval", type=int, default=200,
                       help="Minimum steps between adaptive adjustments")

    # Auto Batch Sizing (VRAM-based startup probing)
    parser.add_argument("--enable_auto_batch", action="store_true",
                       help="Enable automatic batch size detection at startup based on VRAM")
    parser.add_argument("--auto_batch_target_utilization", type=float, default=0.80,
                       help="Target VRAM utilization for auto batch sizing (0.80 = 80%%)")
    parser.add_argument("--auto_batch_safety_margin", type=float, default=0.05,
                       help="Extra VRAM headroom below target (0.05 = 5%%)")
    parser.add_argument("--auto_batch_target_effective", type=int, default=0,
                       help="Target effective batch size (0 = just find max batch, no accumulation)")

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
        batch_size=args.batch_size,
        gradient_accumulation=args.gradient_accumulation,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        dataset=args.dataset,
        gradient_checkpointing=args.gradient_checkpointing,
        checkpoint_offload_cpu=args.checkpoint_offload_cpu,
        mixed_precision=args.mixed_precision,
        local_backend=args.local_backend,
        window_size=args.window_size,
        bhava_lambda=args.bhava_lambda,
        coherence_lambda=args.coherence_lambda,
        log_every=args.log_every,
        quiet=args.quiet,
        eval_every=args.eval_every,
        save_every=args.save_every,
        checkpoint_dir=args.checkpoint_dir,
        no_coherence_loss=args.no_coherence_loss,
        seed=args.seed,
        # Sovereign-Lagrangian Loss [Patent B1/S3]
        enable_sovereign_loss=args.enable_sovereign_loss,
        b1_lambda=args.b1_lambda,
        mu_s3=args.mu_s3,
        enable_stability_constraint=args.enable_stability_constraint,
        gc_floor=args.gc_floor,
        # V9.5.1 Entropy Floor
        enable_entropy_floor=args.enable_entropy_floor,
        entropy_floor=args.entropy_floor,
        entropy_floor_weight=args.entropy_floor_weight,
        # V9.5.1 Force Evolution
        force_evolution_stage=args.force_evolution_stage,
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
        pidv2_w_s=args.pidv2_w_s,
        phase_ramp_steps=args.phase_ramp_steps,
        tensorboard=args.tensorboard and not args.no_tensorboard,
        sample_every=args.sample_every,
        resume=args.resume,
        resume_weights_only=args.resume_weights_only,
        # Formula [1331]: 9:3 Hierarchical Split
        use_9_3_split=args.use_9_3_split,
        authority_layers=args.authority_layers,
        sensory_layers=args.sensory_layers,
        alpha_sens_initial=args.alpha_sens_initial,
        alpha_sens_max=args.alpha_sens_max,
        gradient_warmup_steps=args.gradient_warmup_steps,
        use_per_layer_clipping=args.use_per_layer_clipping,
        # Dynamic Relaxation: 9:3 → 6:6 transition
        enable_dynamic_relaxation=args.enable_dynamic_relaxation,
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
        # CSR Phoneme-Ontological Grounding
        enable_csr=args.enable_csr and not args.disable_csr,
        csr_lambda=args.csr_lambda,
        csr_use_phase_gating=args.csr_use_phase_gating,
        csr_trainable=args.csr_trainable,
        csr_use_entropy_sink=args.csr_use_entropy_sink,
        csr_use_synthesis_gate=args.csr_use_synthesis_gate,
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
        # Auto Batch Sizing
        enable_auto_batch=args.enable_auto_batch,
        auto_batch_target_utilization=args.auto_batch_target_utilization,
        auto_batch_safety_margin=args.auto_batch_safety_margin,
        auto_batch_target_effective=args.auto_batch_target_effective,
    )

    # Train
    train(config)


if __name__ == "__main__":
    main()
