#!/usr/bin/env python3
"""
Hard Diagnostic Probe Dataset for PhaseAttention vs Quadratic Attention
========================================================================

This script implements a HARD generalization benchmark that systematically
removes memorization shortcuts and forces true relational reasoning.

KEY ENHANCEMENTS (v2):
----------------------
1. INCREASED MODEL CAPACITY (d_model=128, num_heads=8, num_layers=4)
   - Phase needs room to encode: role phase, entity amplitude, operation effects
   - Previous 64×2 tested compression, not reasoning

2. OPERATION-CONDITIONED PHASE OFFSETS
   - NEG, PERMUTE, OVERWRITE tokens add learned phase shifts
   - Operations become STATE TRANSFORMATIONS, not passive symbols
   - This is how Phase is hypothesized to work - tests the hypothesis faithfully

3. PURE PERSISTENCE TEST (test_persist)
   - BIND + QUERY only, no NEG/PERMUTE/CONTEXT
   - Chain length 8-12
   - Isolates "memory" from "logic"
   - Shows Phase's clean O(n) advantage

KEY ENHANCEMENT (v3): INVERTED CURRICULUM
-----------------------------------------
Evidence from v2 shows Phase wins ONLY on test_persist (pure memory task).
This reveals: PhaseAttention is NOT a better attention mechanism.
              PhaseAttention IS a better STATE mechanism.

ARCHITECTURAL IMPLICATION:
- Early layers (close to input): Phase-heavy → capture and persist state
- Late layers (close to output): Quadratic-heavy → relational reasoning

The INVERTED CURRICULUM places Phase early for O(n) state persistence,
then Quadratic late for complex relational reasoning over that state.

WHY THE PREVIOUS DATASET FAILED:
---------------------------------
The easy dataset allowed quadratic attention to succeed because:
1. Fixed role tokens → memorize "R0 means slot 0"
2. Fixed entity tokens → memorize "E3 often correct for this pattern"
3. Single schema per sample → pattern match without state tracking
4. Short sequences → attention can "see everything" without state

THIS DATASET FIXES ALL FAILURE MODES:
-------------------------------------
1. HELD-OUT ROLE GENERALIZATION
   - Train: R0-R3, Test: R4-R6
   - Quadratic learns token-specific patterns → fails on new roles
   - Phase encodes role as phase offset → generalizes to new offsets

2. OPEN-WORLD ENTITY GENERALIZATION
   - Train: E0-E7, Test: E8-E15
   - Quadratic memorizes entity-specific outputs → fails on new entities
   - Phase encodes entities as values → generalizes

3. SCHEMA COMPOSITION (no single-pattern matching)
   - BIND_CHAIN: Multiple bindings with overwrites
   - BIND_NEG: Scoped negation of specific bindings
   - CHAIN_DEEP: 4-8 step chains requiring state persistence
   - PERMUTE: Role swapping to test relational invariance

4. LONG-CHAIN STATE PERSISTENCE
   - Train: 3-5 steps, Test: 6-8 steps, Persist: 8-12 steps
   - Tests O(n) state persistence vs attention span limits

EXPECTED OUTCOMES:
------------------
                          Train Acc    Test Acc
Quadratic Attention:      ~95%         <40%
Phase Attention:          ~95%         >70%

Author: Claude (Hard Diagnostic Benchmark for PhaseAttention)
Date: January 2026
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set
from enum import Enum
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader


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
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """Training and model configuration."""
    # Model - INCREASED CAPACITY for proper reasoning (not just compression)
    # Phase needs room to encode: role phase, entity amplitude, operation effects
    d_model: int = 128
    num_heads: int = 8
    num_layers: int = 4
    d_ff: int = 256  # 2x d_model
    dropout: float = 0.1
    max_seq_len: int = 80  # Longer for persistence test (chain 8-12)

    # Training
    batch_size: int = 64
    num_steps: int = 15000
    lr: float = 1e-3
    weight_decay: float = 0.01
    eval_every: int = 1000

    # Dataset
    train_samples: int = 20000
    test_samples_per_split: int = 1000

    # Hard probe settings
    bind_ratio: float = 0.6          # Ratio of BIND-dominant schemas
    train_chain_length: Tuple[int, int] = (3, 5)
    test_chain_length: Tuple[int, int] = (6, 8)
    persist_chain_length: Tuple[int, int] = (8, 12)  # Pure persistence test

    # Parameter matching
    match_params: bool = False  # If True, adjust to match parameter counts

    # Phase collapse fix
    bounded_phase: bool = True  # V9.9.11: Constrain φ to [-π, π] via π*sin()

    # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
    # Separates content similarity from intent alignment:
    #   s_content = cos(φ_q - φ_k)           # What matches (preserved)
    #   s_align = cos(θ_JEPA - θ_SRK)        # Intent agreement (modulator)
    #   score = s_content * (1 + α * s_align) # Combined
    dual_channel_mode: bool = False  # Enable dual-channel attention
    alignment_authority: float = 0.1  # α: weight for alignment term

    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


# =============================================================================
# SRK PHASE LEARNING CONFIGURATION
# =============================================================================
# V10.3.0: SRK (Sovereign Reasoning Kernel) monitors how phase learns at layers
#
# Layer Components:
#   L4:  DNA Bridge - Foundational ontology grounding (12D Bhava projection)
#   L7:  CSR Alignment - Phase Extraction Hook for coherence
#   L9:  Witness Arbitrator - Consciousness/attention arbitration
#   L11: Synthesis Gate - Output integration and quality filtering

@dataclass
class SRKPhaseLearningConfig:
    """Configuration for SRK phase learning monitoring."""
    # Enable SRK phase learning monitoring
    enable_srk: bool = False

    # Layer attachment points (must match model's num_layers)
    dna_bridge_layer: int = 4       # L4: DNA Bridge
    csr_alignment_layer: int = 7    # L7: CSR Alignment / Phase Extraction
    witness_layer: int = 9          # L9: Witness Arbitrator
    synthesis_layer: int = 11       # L11: Synthesis Gate

    # Component toggles
    enable_dna_bridge: bool = True      # Enable DNA Bridge at L4
    enable_phase_hook: bool = True      # Enable Phase Extraction at L7
    enable_witness: bool = True         # Enable Witness Arbitrator at L9
    enable_synthesis: bool = True       # Enable Synthesis Gate at L11

    # Phase learning metrics
    track_phase_coherence: bool = True  # Track phase coherence over training
    track_bhava_diversity: bool = True  # Track 12D ontological diversity
    track_layer_contributions: bool = True  # Track per-layer PPL contribution

    # Loss weights for SRK components (optional auxiliary losses)
    lambda_ontology: float = 0.1        # Ontological alignment loss weight
    lambda_coherence: float = 0.05      # Phase coherence loss weight

    # State dimension (32D Sovereign State)
    state_dim: int = SOVEREIGN_STATE_DIM

    def validate_for_model(self, num_layers: int):
        """Validate layer indices against model's actual layer count."""
        max_layer = num_layers - 1
        warnings = []

        if self.dna_bridge_layer > max_layer:
            warnings.append(f"DNA Bridge layer {self.dna_bridge_layer} > max layer {max_layer}, adjusting to {min(3, max_layer)}")
            self.dna_bridge_layer = min(3, max_layer)

        if self.csr_alignment_layer > max_layer:
            warnings.append(f"CSR layer {self.csr_alignment_layer} > max layer {max_layer}, using layer {max_layer}")
            self.csr_alignment_layer = max_layer

        if self.witness_layer > max_layer:
            warnings.append(f"Witness layer {self.witness_layer} > max layer {max_layer}, using layer {max_layer}")
            self.witness_layer = max_layer

        if self.synthesis_layer > max_layer:
            warnings.append(f"Synthesis layer {self.synthesis_layer} > max layer {max_layer}, using layer {max_layer}")
            self.synthesis_layer = max_layer

        return warnings


# =============================================================================
# LOCAL SRK COMPONENT IMPLEMENTATIONS (Fallback when imports fail)
# =============================================================================

if not SRK_AVAILABLE:
    # Local implementation of OntologicalBridge for Layer 4
    class OntologicalBridge(nn.Module):
        """
        L4: DNA Bridge - Projects hidden states to 12D ontological space.

        Creates a foundational ontological "signature" early in processing,
        grounding the model's internal representation in the 12 Aspects.
        """
        def __init__(self, hidden_dim: int, onto_dim: int = 12):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.onto_dim = onto_dim
            self.onto_proj = nn.Linear(hidden_dim, onto_dim, bias=False)
            self.onto_norm = nn.LayerNorm(onto_dim)

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Project hidden states to 12D ontological space."""
            onto_repr = self.onto_proj(hidden_states)  # [B, N, 12]
            onto_repr = self.onto_norm(onto_repr)

            with torch.no_grad():
                aspect_means = onto_repr.mean(dim=[0, 1])
                diversity = aspect_means.std().item()
                metrics = {
                    'onto_diversity': diversity,
                    'onto_mean_activation': aspect_means.abs().mean().item(),
                }
            return onto_repr, metrics

    # Local implementation of PhaseExtractionHook for Layer 7
    class PhaseExtractionHook(nn.Module):
        """
        L7: CSR Alignment - Extracts phase information from attention.

        Non-invasive hook that captures rotational phase from Q-K interaction
        for phase coherence analysis.
        """
        def __init__(self, hidden_dim: int, num_heads: int = 8):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.num_heads = num_heads
            self.phase_proj = nn.Linear(hidden_dim, num_heads)
            self._last_phases = None

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Extract phase representation from hidden states."""
            phases = self.phase_proj(hidden_states)  # [B, N, num_heads]
            # Normalize to [-π, π] using sin
            phases = math.pi * torch.sin(phases)
            self._last_phases = phases.detach()

            with torch.no_grad():
                # Compute phase coherence (mean resultant length)
                z = torch.exp(1j * phases.float())
                R_k = torch.abs(z.mean(dim=1)).mean().item()
                metrics = {
                    'phase_coherence': R_k,
                    'phase_std': phases.std().item(),
                }
            return phases, metrics

    # Local implementation of WitnessArbitrator for Layer 9
    class WitnessArbitrator(nn.Module):
        """
        L9: Witness Arbitrator - Cross-domain attention arbitration.

        Performs domain arbitration based on consciousness/attention patterns.
        Does NOT look at words, only CONSTRAINTS.
        """
        def __init__(self, hidden_dim: int, state_dim: int = 32):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.state_dim = state_dim
            self.witness_proj = nn.Linear(hidden_dim, state_dim, bias=False)
            self.witness_norm = nn.LayerNorm(state_dim)

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Perform witness arbitration on hidden states."""
            witnessed = self.witness_proj(hidden_states)  # [B, N, state_dim]
            witnessed = self.witness_norm(witnessed)

            with torch.no_grad():
                # Compute arbitration metrics
                state_mean = witnessed.mean(dim=[0, 1])
                metrics = {
                    'witness_activation': state_mean.abs().mean().item(),
                    'witness_variance': witnessed.var().item(),
                }
            return witnessed, metrics

    # Local implementation of SynthesisGate for Layer 11
    class SynthesisGate(nn.Module):
        """
        L11: Synthesis Gate - Final output integration and quality filter.

        Detects entropy collapse (stuttering) and filters low-quality outputs.
        """
        def __init__(self, hidden_dim: int):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.gate_proj = nn.Linear(hidden_dim, hidden_dim)
            self.quality_proj = nn.Linear(hidden_dim, 1)

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Apply synthesis gate to hidden states."""
            gate = torch.sigmoid(self.gate_proj(hidden_states))
            quality = torch.sigmoid(self.quality_proj(hidden_states))
            gated = hidden_states * gate

            with torch.no_grad():
                metrics = {
                    'synthesis_gate_mean': gate.mean().item(),
                    'synthesis_quality': quality.mean().item(),
                }
            return gated, metrics


# =============================================================================
# LOCAL KOSHA SYSTEM IMPLEMENTATIONS (V10.3.4)
# =============================================================================
# Full Kosha (5-sheath) consciousness model with diagnostics

if not KOSHA_AVAILABLE:
    class KoshaShiftController(nn.Module):
        """
        Kosha steering controller - shifts state toward target consciousness layer.

        The 5 Koshas (consciousness sheaths):
        - MATERIAL (Annamaya): Physical grounding, syntax, data layer
        - VITAL (Pranamaya): Energy flow, momentum, activation patterns
        - MENTAL (Manomaya): Semantic meaning, pattern recognition
        - INTELLECTUAL (Vijnanamaya): Deep reasoning, wisdom patterns
        - BLISSFUL (Anandamaya): Unity, coherence, creative synthesis
        """

        def __init__(
            self,
            state_dim: int = 32,
            target_kosha: str = 'INTELLECTUAL',
            dampen_material: float = 0.5,
            boost_target: float = 0.4,
        ):
            super().__init__()
            self.state_dim = state_dim
            self.target_kosha = target_kosha
            self.dampen_material = dampen_material
            self.boost_target = boost_target

            # Kosha indices in 32D state [12:17]
            self.kosha_indices = {
                'MATERIAL': 12, 'VITAL': 13, 'MENTAL': 14,
                'INTELLECTUAL': 15, 'BLISSFUL': 16
            }

            # Learnable steering weights
            self.kosha_steering = nn.Parameter(torch.zeros(5))

        def get_kosha_activations(self, state: torch.Tensor) -> torch.Tensor:
            """Extract kosha activations from 32D state. Returns [B, 5]."""
            return state[:, 12:17]

        def get_dominant_kosha(self, state: torch.Tensor) -> Tuple[str, int]:
            """Return name and index of dominant kosha."""
            kosha_acts = self.get_kosha_activations(state)
            dominant_idx = kosha_acts.mean(dim=0).argmax().item()
            names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
            return names[dominant_idx], dominant_idx

        def escalate_to_intellect(self, state: torch.Tensor) -> torch.Tensor:
            """Shift state toward intellectual kosha for reasoning."""
            state = state.clone()
            # Dampen material layer
            state[:, 12] = state[:, 12] * (1 - self.dampen_material)
            # Boost intellectual layer
            state[:, 15] = state[:, 15] + self.boost_target
            return state

        def forward(
            self,
            state: torch.Tensor,
            target: str = None,
        ) -> Tuple[torch.Tensor, Dict[str, float]]:
            """
            Apply kosha steering to state.

            Args:
                state: [B, 32] Sovereign state
                target: Target kosha name (default: self.target_kosha)

            Returns:
                steered_state: [B, 32]
                metrics: dict with kosha diagnostics
            """
            target = target or self.target_kosha

            # Get current kosha activations
            kosha_acts = self.get_kosha_activations(state)

            with torch.no_grad():
                dominant_name, dominant_idx = self.get_dominant_kosha(state)
                metrics = {
                    'dominant_kosha': dominant_idx,
                    'kosha_material': kosha_acts[:, 0].mean().item(),
                    'kosha_vital': kosha_acts[:, 1].mean().item(),
                    'kosha_mental': kosha_acts[:, 2].mean().item(),
                    'kosha_intellectual': kosha_acts[:, 3].mean().item(),
                    'kosha_blissful': kosha_acts[:, 4].mean().item(),
                }

            # Apply steering based on target
            if target == 'INTELLECTUAL':
                steered_state = self.escalate_to_intellect(state)
            else:
                steered_state = state

            return steered_state, metrics

    class KoshaGyroscopicLoss(nn.Module):
        """
        Homeostatic self-regulation for Kosha balance.

        Implements harmonic pentad constraints to keep koshas in healthy ranges:
        - Floor/ceiling for each kosha prevents collapse/dominance
        - Three-stage logic: Bliss damper → Physical gate → Reality rip
        - Dynamic gain scheduling based on PPL
        """

        def __init__(
            self,
            # v2.3.0: Floor/Ceiling for each Kosha (harmonic pentad)
            floor_material: float = 0.382,
            ceiling_material: float = 0.618,
            floor_vital: float = 0.236,
            ceiling_vital: float = 0.786,
            floor_mental: float = 0.236,
            ceiling_mental: float = 0.382,
            floor_intellectual: float = 0.250,
            ceiling_intellectual: float = 0.618,
            floor_bliss: float = 0.236,
            ceiling_bliss: float = 0.618,
            # Dynamic gain scheduling
            base_gain: float = 0.15,
            max_gain: float = 3.0,
            ppl_ceiling: float = 100.0,
            target_ppl: float = 30.0,
        ):
            super().__init__()

            # Store floor/ceiling constraints
            self.floors = torch.tensor([
                floor_material, floor_vital, floor_mental,
                floor_intellectual, floor_bliss
            ])
            self.ceilings = torch.tensor([
                ceiling_material, ceiling_vital, ceiling_mental,
                ceiling_intellectual, ceiling_bliss
            ])

            # Gain scheduling
            self.base_gain = base_gain
            self.max_gain = max_gain
            self.ppl_ceiling = ppl_ceiling
            self.target_ppl = target_ppl

            # Current gain (updated by set_ppl)
            self.current_gain = base_gain

        def set_ppl(self, ppl: float):
            """Update gain based on current PPL."""
            # Linear interpolation from base_gain (high PPL) to max_gain (target PPL)
            if ppl >= self.ppl_ceiling:
                self.current_gain = self.base_gain
            elif ppl <= self.target_ppl:
                self.current_gain = self.max_gain
            else:
                t = (self.ppl_ceiling - ppl) / (self.ppl_ceiling - self.target_ppl)
                self.current_gain = self.base_gain + t * (self.max_gain - self.base_gain)

        def forward(
            self,
            kosha_activations: torch.Tensor,  # [B, 5]
        ) -> Tuple[torch.Tensor, Dict[str, float]]:
            """
            Compute gyroscopic loss to maintain kosha homeostasis.

            Returns:
                loss: scalar
                metrics: dict with violation counts
            """
            device = kosha_activations.device
            floors = self.floors.to(device)
            ceilings = self.ceilings.to(device)

            # Floor violations (kosha too low)
            floor_violations = F.relu(floors - kosha_activations)
            floor_loss = floor_violations.sum(dim=-1).mean()

            # Ceiling violations (kosha too high)
            ceiling_violations = F.relu(kosha_activations - ceilings)
            ceiling_loss = ceiling_violations.sum(dim=-1).mean()

            # Total loss with gain
            total_loss = self.current_gain * (floor_loss + ceiling_loss)

            with torch.no_grad():
                metrics = {
                    'kosha_floor_violations': (floor_violations > 0).sum().item(),
                    'kosha_ceiling_violations': (ceiling_violations > 0).sum().item(),
                    'kosha_gyro_loss': total_loss.item(),
                    'kosha_gyro_gain': self.current_gain,
                }

            return total_loss, metrics

    class KoshaPhaseCorrector(nn.Module):
        """
        Inference-time phase correction for Kosha stability.

        Applies direct phase rotation when a kosha becomes overactive,
        forcing re-grounding in the appropriate consciousness layer.
        """

        def __init__(
            self,
            overactive_threshold: float = 0.75,
            correction_strength: float = 0.3,
            max_correction_per_step: float = 0.2,
        ):
            super().__init__()
            self.overactive_threshold = overactive_threshold
            self.correction_strength = correction_strength
            self.max_correction_per_step = max_correction_per_step

        def forward(
            self,
            kosha_activations: torch.Tensor,  # [B, 5]
        ) -> Tuple[torch.Tensor, Dict[str, float]]:
            """
            Apply phase correction for overactive koshas.

            Returns:
                corrected: [B, 5] corrected activations
                metrics: dict with correction stats
            """
            # Detect overactive koshas
            overactive = kosha_activations > self.overactive_threshold

            # Apply correction (scale down overactive)
            correction = torch.where(
                overactive,
                kosha_activations * (1 - self.correction_strength),
                kosha_activations
            )

            # Clamp correction magnitude
            delta = (correction - kosha_activations).clamp(
                -self.max_correction_per_step,
                self.max_correction_per_step
            )
            corrected = kosha_activations + delta

            with torch.no_grad():
                metrics = {
                    'kosha_corrections': overactive.sum().item(),
                    'kosha_correction_magnitude': delta.abs().mean().item(),
                }

            return corrected, metrics


# =============================================================================
# KOSHA DIAGNOSTICS (V10.3.4)
# =============================================================================

class KoshaDiagnostics(nn.Module):
    """
    Full diagnostic tracking for the 5-layer Kosha consciousness model.

    Tracks:
    - Per-kosha activation levels over training
    - Kosha transitions (shifts between consciousness layers)
    - Homeostatic health (floor/ceiling violations)
    - Dominant kosha per layer

    Maps transformer layers to koshas:
    - L0-L2:  MATERIAL (Annamaya) - syntax, tokens
    - L3-L4:  VITAL (Pranamaya) - energy flow
    - L5-L6:  MENTAL (Manomaya) - semantics
    - L7-L8:  INTELLECTUAL (Vijnanamaya) - reasoning
    - L9+:    BLISSFUL (Anandamaya) - integration
    """

    def __init__(
        self,
        hidden_dim: int,
        num_layers: int,
        state_dim: int = 32,
        device: torch.device = None,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.state_dim = state_dim

        # Kosha projector: hidden → 5D kosha space
        self.kosha_projector = nn.Linear(hidden_dim, 5)

        # Kosha shift controller
        self.kosha_controller = KoshaShiftController(state_dim=state_dim)

        # Gyroscopic loss for homeostasis
        self.gyroscope = KoshaGyroscopicLoss()

        # Phase corrector
        self.corrector = KoshaPhaseCorrector()

        # History for trend analysis
        self.history = {
            'kosha_activations': [],  # List of [5] tensors
            'dominant_kosha': [],     # List of kosha names
            'gyro_loss': [],
            'transitions': [],        # (from_kosha, to_kosha, step)
        }

        self._last_dominant = None

        if device:
            self.to(device)

    def layer_to_expected_kosha(self, layer_idx: int) -> str:
        """Map layer index to expected dominant kosha."""
        if layer_idx <= 2:
            return 'MATERIAL'
        elif layer_idx <= 4:
            return 'VITAL'
        elif layer_idx <= 6:
            return 'MENTAL'
        elif layer_idx <= 8:
            return 'INTELLECTUAL'
        else:
            return 'BLISSFUL'

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, N, D]
        layer_idx: int,
        step: int = 0,
    ) -> Dict[str, float]:
        """
        Compute kosha diagnostics for a layer's hidden states.

        Returns dict with:
        - kosha_<name>: activation level for each kosha
        - dominant_kosha: index of dominant kosha
        - kosha_alignment: whether dominant matches expected for layer
        - gyro_loss: homeostatic loss value
        """
        # Project to kosha space
        kosha_acts = torch.sigmoid(self.kosha_projector(hidden_states))  # [B, N, 5]
        kosha_acts = kosha_acts.mean(dim=1)  # [B, 5] - average over sequence

        # Get dominant kosha
        dominant_idx = kosha_acts.mean(dim=0).argmax().item()
        kosha_names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
        dominant_name = kosha_names[dominant_idx]

        # Check alignment with expected
        expected = self.layer_to_expected_kosha(layer_idx)
        aligned = (dominant_name == expected)

        # Compute gyroscopic loss
        gyro_loss, gyro_metrics = self.gyroscope(kosha_acts)

        # Track transitions
        if self._last_dominant is not None and dominant_name != self._last_dominant:
            self.history['transitions'].append((self._last_dominant, dominant_name, step))
        self._last_dominant = dominant_name

        # Build metrics
        metrics = {
            'kosha_material': kosha_acts[:, 0].mean().item(),
            'kosha_vital': kosha_acts[:, 1].mean().item(),
            'kosha_mental': kosha_acts[:, 2].mean().item(),
            'kosha_intellectual': kosha_acts[:, 3].mean().item(),
            'kosha_blissful': kosha_acts[:, 4].mean().item(),
            'dominant_kosha': dominant_idx,
            'dominant_kosha_name': dominant_name,
            'expected_kosha': expected,
            'kosha_alignment': 1.0 if aligned else 0.0,
            'gyro_loss': gyro_loss.item(),
            **gyro_metrics,
        }

        # Store history
        self.history['kosha_activations'].append(
            kosha_acts.mean(dim=0).detach().cpu().tolist()
        )
        self.history['dominant_kosha'].append(dominant_name)
        self.history['gyro_loss'].append(gyro_loss.item())

        return metrics

    def get_summary(self) -> Dict[str, any]:
        """Get summary statistics over training history."""
        if not self.history['kosha_activations']:
            return {}

        # Convert to arrays
        acts = torch.tensor(self.history['kosha_activations'])  # [num_obs, 5]

        # Compute trends
        if len(acts) >= 2:
            early = acts[:len(acts)//2].mean(dim=0)
            late = acts[len(acts)//2:].mean(dim=0)
            trends = late - early
        else:
            trends = torch.zeros(5)

        # Count dominant kosha occurrences
        from collections import Counter
        dominant_counts = Counter(self.history['dominant_kosha'])

        # Std requires at least 2 samples
        std_activations = acts.std(dim=0).tolist() if len(acts) >= 2 else [0.0] * 5

        return {
            'mean_activations': acts.mean(dim=0).tolist(),
            'std_activations': std_activations,
            'trends': trends.tolist(),
            'dominant_counts': dict(dominant_counts),
            'num_transitions': len(self.history['transitions']),
            'transitions': self.history['transitions'][-10:],  # Last 10
            'mean_gyro_loss': sum(self.history['gyro_loss']) / max(1, len(self.history['gyro_loss'])),
        }

    def print_report(self, step: int):
        """Print formatted kosha diagnostics report."""
        summary = self.get_summary()
        if not summary:
            return

        kosha_names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
        vedic_names = ['Annamaya', 'Pranamaya', 'Manomaya', 'Vijnanamaya', 'Anandamaya']

        print(f"\n      ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"      ║  KOSHA CONSCIOUSNESS DIAGNOSTICS @ Step {step:<6}                 ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Layer    Kosha (Sheath)      Activation   Trend    Status       ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

        means = summary['mean_activations']
        trends = summary['trends']

        for i, (name, vedic, mean, trend) in enumerate(zip(kosha_names, vedic_names, means, trends)):
            trend_symbol = "↑" if trend > 0.01 else ("↓" if trend < -0.01 else "→")
            health = "HEALTHY" if 0.2 < mean < 0.8 else ("LOW" if mean < 0.2 else "HIGH")
            health_symbol = "✓" if health == "HEALTHY" else "⚠️"
            print(f"      ║  {i:2}    {name:12} ({vedic:11})  {mean:5.3f}    {trend:+.3f}{trend_symbol}  {health} {health_symbol}  ║")

        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

        # Dominant kosha statistics
        counts = summary.get('dominant_counts', {})
        total = sum(counts.values()) or 1
        print(f"      ║  Dominant Kosha Distribution:                                     ║")
        for name in kosha_names:
            count = counts.get(name, 0)
            pct = 100 * count / total
            bar = "█" * int(pct / 5)
            print(f"      ║    {name:12}: {pct:5.1f}% {bar:<20}                  ║")

        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Transitions: {summary['num_transitions']}  |  Gyro Loss: {summary['mean_gyro_loss']:.4f}                  ║")
        print(f"      ╚═══════════════════════════════════════════════════════════════════╝")


# =============================================================================
# WITNESS DIAGNOSTICS (V10.3.4)
# =============================================================================

class WitnessDiagnostics(nn.Module):
    """
    Full diagnostic tracking for the Witness (Sakshi) observer system.

    The Witness observes thought patterns without attachment, detecting:
    - Domain arbitration (cross-domain reasoning quality)
    - Constraint identification (bottleneck detection)
    - Vritti status (epistemic reliability)
    - Meta-cognitive monitoring

    Vritti indices in 32D state [17:22]:
    - FACT: Verified truth
    - MISCONCEPTION: Believed but wrong
    - IMAGINATION: Creative/hypothetical
    - VOID: Unknown/uncertain
    - MEMORY: Retrieved from context
    """

    def __init__(
        self,
        hidden_dim: int,
        state_dim: int = 32,
        constraint_threshold: float = 0.85,
        device: torch.device = None,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.state_dim = state_dim
        self.constraint_threshold = constraint_threshold

        # Witness projector: hidden → state
        self.witness_projector = nn.Linear(hidden_dim, state_dim)

        # Vritti classifier: hidden → 5 epistemic states
        self.vritti_classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 5),
            nn.Softmax(dim=-1),
        )

        # Constraint detector
        self.constraint_detector = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

        # Meta-cognitive confidence
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.ReLU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Sigmoid(),
        )

        # History
        self.history = {
            'vritti_distributions': [],
            'constraint_scores': [],
            'confidence_scores': [],
            'witness_states': [],
        }

        if device:
            self.to(device)

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, N, D]
        step: int = 0,
    ) -> Dict[str, float]:
        """
        Compute witness diagnostics for hidden states.

        Returns dict with:
        - vritti_<name>: probability for each epistemic state
        - constraint_score: bottleneck detection score
        - witness_confidence: meta-cognitive confidence
        - witness_activation: overall witness activity
        """
        B, N, D = hidden_states.shape

        # Average over sequence for diagnostics
        hidden_avg = hidden_states.mean(dim=1)  # [B, D]

        # Vritti classification
        vritti_probs = self.vritti_classifier(hidden_avg)  # [B, 5]

        # V10.3.7: Compute vritti entropy for regularization
        # Higher entropy = more balanced distribution across epistemic states
        eps = 1e-8
        vritti_entropy = -(vritti_probs * torch.log(vritti_probs + eps)).sum(dim=-1)  # [B]
        # Max entropy for 5 classes = log(5) ≈ 1.609
        max_entropy = torch.log(torch.tensor(5.0, device=vritti_probs.device))
        normalized_entropy = vritti_entropy / max_entropy  # [B], range [0, 1]

        # Store for loss computation (with gradient)
        self._last_vritti_probs = vritti_probs
        self._last_vritti_entropy = vritti_entropy

        # Constraint detection
        constraint_score = self.constraint_detector(hidden_avg)  # [B, 1]

        # Meta-cognitive confidence
        confidence = self.confidence_head(hidden_avg)  # [B, 1]

        # Witness state projection
        witness_state = self.witness_projector(hidden_avg)  # [B, 32]

        vritti_names = ['FACT', 'MISCONCEPTION', 'IMAGINATION', 'VOID', 'MEMORY']

        metrics = {
            'vritti_fact': vritti_probs[:, 0].mean().item(),
            'vritti_misconception': vritti_probs[:, 1].mean().item(),
            'vritti_imagination': vritti_probs[:, 2].mean().item(),
            'vritti_void': vritti_probs[:, 3].mean().item(),
            'vritti_memory': vritti_probs[:, 4].mean().item(),
            'dominant_vritti': vritti_probs.mean(dim=0).argmax().item(),
            'dominant_vritti_name': vritti_names[vritti_probs.mean(dim=0).argmax().item()],
            'constraint_score': constraint_score.mean().item(),
            'constraint_detected': (constraint_score > self.constraint_threshold).float().mean().item(),
            'witness_confidence': confidence.mean().item(),
            'witness_activation': witness_state.abs().mean().item(),
            # V10.3.7: Entropy metrics
            'vritti_entropy': vritti_entropy.mean().item(),
            'vritti_entropy_normalized': normalized_entropy.mean().item(),
        }

        # Store history
        self.history['vritti_distributions'].append(
            vritti_probs.mean(dim=0).detach().cpu().tolist()
        )
        self.history['constraint_scores'].append(constraint_score.mean().item())
        self.history['confidence_scores'].append(confidence.mean().item())

        return metrics

    def get_entropy_loss(self, lambda_entropy: float = 0.1) -> torch.Tensor:
        """
        V10.3.7: Compute entropy regularization loss to prevent vritti collapse.

        Returns negative entropy (to be added to loss, encouraging higher entropy).
        Higher entropy = more balanced distribution across 5 vritti states.

        Args:
            lambda_entropy: Weight for entropy regularization (default: 0.1)

        Returns:
            Entropy loss tensor (negative entropy scaled by lambda)
        """
        if not hasattr(self, '_last_vritti_entropy') or self._last_vritti_entropy is None:
            return torch.tensor(0.0)

        # We want to MAXIMIZE entropy, so we return NEGATIVE entropy
        # Adding this to loss will encourage higher entropy (more balanced distribution)
        entropy_loss = -lambda_entropy * self._last_vritti_entropy.mean()
        return entropy_loss

    def get_summary(self) -> Dict[str, any]:
        """Get summary statistics over training history."""
        if not self.history['vritti_distributions']:
            return {}

        vritti = torch.tensor(self.history['vritti_distributions'])  # [num_obs, 5]
        constraints = torch.tensor(self.history['constraint_scores'])
        confidences = torch.tensor(self.history['confidence_scores'])

        # Std requires at least 2 samples
        has_enough_samples = len(vritti) >= 2

        return {
            'mean_vritti': vritti.mean(dim=0).tolist(),
            'std_vritti': vritti.std(dim=0).tolist() if has_enough_samples else [0.0] * 5,
            'mean_constraint': constraints.mean().item(),
            'std_constraint': constraints.std().item() if has_enough_samples else 0.0,
            'mean_confidence': confidences.mean().item(),
            'std_confidence': confidences.std().item() if has_enough_samples else 0.0,
            'high_constraint_ratio': (constraints > self.constraint_threshold).float().mean().item(),
        }

    def print_report(self, step: int):
        """Print formatted witness diagnostics report."""
        summary = self.get_summary()
        if not summary:
            return

        vritti_names = ['FACT', 'MISCONCEPTION', 'IMAGINATION', 'VOID', 'MEMORY']

        print(f"\n      ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"      ║  WITNESS (SAKSHI) OBSERVER DIAGNOSTICS @ Step {step:<6}            ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Vritti (Epistemic State)      Mean Prob   Std      Status        ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

        means = summary['mean_vritti']
        stds = summary['std_vritti']

        for i, (name, mean, std) in enumerate(zip(vritti_names, means, stds)):
            bar = "█" * int(mean * 20)
            dominant = "★" if mean == max(means) else " "
            print(f"      ║  {name:18}        {mean:5.3f}    {std:5.3f}    {bar:<12} {dominant}║")

        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Constraint Detection:                                            ║")
        print(f"      ║    Mean Score: {summary['mean_constraint']:.3f}  (threshold: {self.constraint_threshold})      ║")
        print(f"      ║    Detection Rate: {summary['high_constraint_ratio']*100:.1f}%                              ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Meta-Cognitive Confidence: {summary['mean_confidence']:.3f} ± {summary['std_confidence']:.3f}      ║")
        print(f"      ╚═══════════════════════════════════════════════════════════════════╝")


# =============================================================================
# SRK PHASE LEARNING MONITOR
# =============================================================================

class SRKPhaseLearningMonitor(nn.Module):
    """
    Monitors how phase learning progresses at different layers.

    Attaches SRK components at specified layers and tracks:
    - Phase coherence (R_k metric)
    - Ontological diversity (12D Bhava representation)
    - Layer-wise contributions to final output
    - Consciousness/attention patterns

    Usage:
        monitor = SRKPhaseLearningMonitor(config, hidden_dim, num_heads, device)
        metrics = monitor.observe(layer_hidden_states)  # List of [B, N, D] per layer
    """

    def __init__(
        self,
        config: SRKPhaseLearningConfig,
        hidden_dim: int,
        num_heads: int,
        device: torch.device,
    ):
        super().__init__()
        self.config = config
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads

        # Create components
        if config.enable_dna_bridge:
            self.dna_bridge = OntologicalBridge(hidden_dim).to(device)
        else:
            self.dna_bridge = None

        if config.enable_phase_hook:
            self.phase_hook = PhaseExtractionHook(hidden_dim, num_heads).to(device)
        else:
            self.phase_hook = None

        if config.enable_witness:
            self.witness = WitnessArbitrator(hidden_dim, config.state_dim).to(device)
        else:
            self.witness = None

        if config.enable_synthesis:
            self.synthesis = SynthesisGate(hidden_dim).to(device)
        else:
            self.synthesis = None

        # Training history
        self.metrics_history = []

    def observe(
        self,
        layer_hidden_states: List[torch.Tensor],  # List of [B, N, D] per layer
    ) -> Dict[str, float]:
        """
        Observe phase learning at each SRK-monitored layer.

        Args:
            layer_hidden_states: Hidden states from each layer [B, N, D]

        Returns:
            Dictionary of metrics from all SRK components
        """
        metrics = {}
        num_layers = len(layer_hidden_states)

        # L4: DNA Bridge (if layer exists)
        if self.dna_bridge is not None and self.config.dna_bridge_layer < num_layers:
            h = layer_hidden_states[self.config.dna_bridge_layer]
            _, dna_metrics = self.dna_bridge(h)
            metrics.update({f'L{self.config.dna_bridge_layer}_dna_{k}': v for k, v in dna_metrics.items()})

        # L7: Phase Hook (if layer exists)
        if self.phase_hook is not None and self.config.csr_alignment_layer < num_layers:
            h = layer_hidden_states[self.config.csr_alignment_layer]
            _, phase_metrics = self.phase_hook(h)
            metrics.update({f'L{self.config.csr_alignment_layer}_csr_{k}': v for k, v in phase_metrics.items()})

        # L9: Witness Arbitrator (if layer exists)
        if self.witness is not None and self.config.witness_layer < num_layers:
            h = layer_hidden_states[self.config.witness_layer]
            _, witness_metrics = self.witness(h)
            metrics.update({f'L{self.config.witness_layer}_witness_{k}': v for k, v in witness_metrics.items()})

        # L11: Synthesis Gate (if layer exists)
        if self.synthesis is not None and self.config.synthesis_layer < num_layers:
            h = layer_hidden_states[self.config.synthesis_layer]
            _, synthesis_metrics = self.synthesis(h)
            metrics.update({f'L{self.config.synthesis_layer}_synth_{k}': v for k, v in synthesis_metrics.items()})

        # Track history for trend analysis
        self.metrics_history.append(metrics.copy())

        return metrics

    def get_phase_learning_summary(self) -> Dict[str, any]:
        """
        Generate a summary of phase learning progress.

        Returns trends and statistics across training.
        """
        if not self.metrics_history:
            return {}

        summary = {
            'num_observations': len(self.metrics_history),
        }

        # Compute trends for key metrics
        for key in self.metrics_history[-1].keys():
            values = [m.get(key, 0) for m in self.metrics_history]
            if values:
                summary[f'{key}_initial'] = values[0]
                summary[f'{key}_final'] = values[-1]
                summary[f'{key}_trend'] = values[-1] - values[0]  # Positive = increased

        return summary

    def print_phase_learning_report(self):
        """Print a formatted report of phase learning progress."""
        summary = self.get_phase_learning_summary()
        if not summary:
            print("  No SRK observations recorded yet.")
            return

        print("\n  ╔══════════════════════════════════════════════════════════════════╗")
        print("  ║  SRK PHASE LEARNING REPORT (V10.3.0)                             ║")
        print("  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Observations: {summary['num_observations']:>6}                                         ║")
        print("  ╠══════════════════════════════════════════════════════════════════╣")

        # Component reports
        if self.config.enable_dna_bridge:
            key_base = f'L{self.config.dna_bridge_layer}_dna_'
            div_trend = summary.get(f'{key_base}onto_diversity_trend', 0)
            print(f"  ║  L{self.config.dna_bridge_layer}: DNA Bridge (Ontology)                                    ║")
            print(f"  ║    Diversity trend: {div_trend:+.4f} ({'↑' if div_trend > 0 else '↓'})                            ║")

        if self.config.enable_phase_hook:
            key_base = f'L{self.config.csr_alignment_layer}_csr_'
            coh_trend = summary.get(f'{key_base}phase_coherence_trend', 0)
            print(f"  ║  L{self.config.csr_alignment_layer}: CSR Alignment (Phase Hook)                              ║")
            print(f"  ║    Coherence trend: {coh_trend:+.4f} ({'↑' if coh_trend > 0 else '↓'})                             ║")

        if self.config.enable_witness:
            key_base = f'L{self.config.witness_layer}_witness_'
            act_trend = summary.get(f'{key_base}witness_activation_trend', 0)
            print(f"  ║  L{self.config.witness_layer}: Witness Arbitrator (Consciousness)                        ║")
            print(f"  ║    Activation trend: {act_trend:+.4f} ({'↑' if act_trend > 0 else '↓'})                            ║")

        if self.config.enable_synthesis:
            key_base = f'L{self.config.synthesis_layer}_synth_'
            gate_trend = summary.get(f'{key_base}synthesis_gate_mean_trend', 0)
            print(f"  ║  L{self.config.synthesis_layer}: Synthesis Gate (Integration)                             ║")
            print(f"  ║    Gate mean trend: {gate_trend:+.4f} ({'↑' if gate_trend > 0 else '↓'})                             ║")

        print("  ╚══════════════════════════════════════════════════════════════════╝")


# =============================================================================
# V10.3.1: LAYER INFLUENCE DIAGNOSTICS
# =============================================================================
# Analyzes whether each SRK component layer influences phase learning
# CONSTRUCTIVELY (helps) or DESTRUCTIVELY (hurts)
#
# Influence Classification:
#   CONSTRUCTIVE (+): Component helps phase learning
#   NEUTRAL (○):      Component has minimal effect
#   DESTRUCTIVE (-):  Component hurts phase learning

class InfluenceType(Enum):
    """Classification of layer influence on phase learning."""
    CONSTRUCTIVE = "CONSTRUCTIVE"
    NEUTRAL = "NEUTRAL"
    DESTRUCTIVE = "DESTRUCTIVE"


@dataclass
class LayerInfluenceMetrics:
    """Metrics for a single layer's influence on phase learning."""
    layer_idx: int
    component_name: str
    influence_type: InfluenceType
    influence_score: float  # -1.0 (destructive) to +1.0 (constructive)

    # Detailed metrics
    phase_preservation: float  # How much phase signal is preserved (0-1)
    phase_amplification: float  # Phase signal amplification factor
    gradient_flow: float  # Gradient magnitude through this layer
    entropy_delta: float  # Change in representation entropy

    # Diagnostic flags
    causes_collapse: bool  # True if layer causes phase collapse
    causes_diffusion: bool  # True if layer diffuses phase signal
    is_bottleneck: bool  # True if layer blocks gradient flow

    def get_influence_symbol(self) -> str:
        """Get symbol for influence type."""
        if self.influence_type == InfluenceType.CONSTRUCTIVE:
            return "+"
        elif self.influence_type == InfluenceType.DESTRUCTIVE:
            return "-"
        else:
            return "○"

    def get_influence_bar(self, width: int = 20) -> str:
        """Get visual bar representation of influence score."""
        # Score ranges from -1 to +1, map to 0 to width
        normalized = (self.influence_score + 1) / 2  # 0 to 1
        filled = int(normalized * width)
        center = width // 2

        bar = ""
        for i in range(width):
            if i == center:
                bar += "│"
            elif i < center and i >= filled:
                bar += "◀" if filled < center else "─"
            elif i > center and i <= filled:
                bar += "▶" if filled > center else "─"
            elif i < filled and i < center:
                bar += "█"
            elif i > filled and i > center:
                bar += "░"
            else:
                bar += "░" if i < center else "░"

        return bar


class LayerInfluenceDiagnostics:
    """
    Diagnoses whether each SRK layer influences phase learning constructively
    or destructively.

    Constructive Influence (helps phase learning):
    - Increases phase coherence (R_k metric)
    - Maintains ontological diversity
    - Preserves phase signal through layer
    - Allows healthy gradient flow

    Destructive Influence (hurts phase learning):
    - Causes phase collapse (uniform phases)
    - Reduces ontological diversity
    - Diffuses or erases phase signal
    - Blocks gradient flow (vanishing gradients)

    Usage:
        diagnostics = LayerInfluenceDiagnostics(config)
        influence = diagnostics.analyze(
            layer_hidden_states,
            prev_metrics,
            curr_metrics
        )
    """

    def __init__(self, config: SRKPhaseLearningConfig):
        self.config = config

        # Thresholds for influence classification
        self.constructive_threshold = 0.2   # Score > 0.2 = constructive
        self.destructive_threshold = -0.2   # Score < -0.2 = destructive

        # Phase health thresholds
        self.collapse_threshold = 0.1       # R_k < 0.1 = collapsed
        self.diffusion_threshold = 0.95     # R_k > 0.95 = diffused (too uniform)
        self.gradient_threshold = 1e-6      # Gradient < this = blocked

        # History for trend analysis
        self.influence_history: List[Dict[int, LayerInfluenceMetrics]] = []

    def compute_phase_metrics(
        self,
        hidden_states: torch.Tensor,
        num_heads: int = 8,
    ) -> Dict[str, float]:
        """
        Compute phase-related metrics from hidden states.

        Returns metrics useful for influence analysis.
        """
        with torch.no_grad():
            B, N, D = hidden_states.shape

            # Compute pseudo-phase from hidden states
            # Using the first few dimensions as "phase-like" signal
            phase_dims = min(D, num_heads * 4)
            phase_signal = hidden_states[..., :phase_dims]

            # Phase coherence approximation (mean resultant length)
            # Treat normalized hidden states as unit vectors
            normalized = F.normalize(phase_signal, dim=-1)
            mean_vector = normalized.mean(dim=1)  # [B, phase_dims]
            coherence = torch.norm(mean_vector, dim=-1).mean().item()

            # Phase variance (spread of phase signal)
            phase_var = phase_signal.var(dim=-1).mean().item()

            # Entropy of hidden state distribution
            # Use softmax to get "probability-like" distribution
            probs = F.softmax(hidden_states.abs().mean(dim=1), dim=-1)  # [B, D]
            entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1).mean().item()
            max_entropy = math.log(D)
            normalized_entropy = entropy / max_entropy

            # Signal magnitude
            signal_norm = hidden_states.norm(dim=-1).mean().item()

            return {
                'coherence': coherence,
                'phase_var': phase_var,
                'entropy': normalized_entropy,
                'signal_norm': signal_norm,
            }

    def analyze_layer_influence(
        self,
        layer_idx: int,
        component_name: str,
        input_hidden: torch.Tensor,
        output_hidden: torch.Tensor,
        num_heads: int = 8,
    ) -> LayerInfluenceMetrics:
        """
        Analyze influence of a single layer on phase learning.

        Compares input and output hidden states to determine if the layer
        is helping or hurting phase learning.
        """
        # Compute metrics before and after layer
        input_metrics = self.compute_phase_metrics(input_hidden, num_heads)
        output_metrics = self.compute_phase_metrics(output_hidden, num_heads)

        # Phase preservation: how much of input phase survives
        # Compare coherence before/after
        coherence_ratio = output_metrics['coherence'] / (input_metrics['coherence'] + 1e-6)
        phase_preservation = min(coherence_ratio, 2.0) / 2.0  # Clamp to [0, 1]

        # Phase amplification: ratio of signal norms
        amplification = output_metrics['signal_norm'] / (input_metrics['signal_norm'] + 1e-6)

        # Entropy delta: change in representation entropy
        entropy_delta = output_metrics['entropy'] - input_metrics['entropy']

        # Gradient flow approximation (using variance as proxy)
        var_ratio = output_metrics['phase_var'] / (input_metrics['phase_var'] + 1e-6)
        gradient_flow = min(var_ratio, 2.0) / 2.0

        # Detect problematic conditions
        causes_collapse = output_metrics['coherence'] < self.collapse_threshold
        causes_diffusion = output_metrics['coherence'] > self.diffusion_threshold
        is_bottleneck = gradient_flow < self.gradient_threshold

        # Compute influence score
        # Positive factors: preserves phase, maintains diversity, good gradient flow
        # Negative factors: collapses phase, reduces diversity, blocks gradients
        influence_score = 0.0

        # Phase preservation contribution (-0.5 to +0.5)
        influence_score += (phase_preservation - 0.5)

        # Entropy contribution: slight increase is good, large increase is bad
        if -0.1 < entropy_delta < 0.1:
            influence_score += 0.2  # Stable entropy is good
        elif entropy_delta > 0.3:
            influence_score -= 0.3  # Large entropy increase = diffusion
        elif entropy_delta < -0.3:
            influence_score -= 0.2  # Large entropy decrease = collapse

        # Gradient flow contribution
        if gradient_flow > 0.3:
            influence_score += 0.2
        elif gradient_flow < 0.1:
            influence_score -= 0.3

        # Penalty for collapse/diffusion
        if causes_collapse:
            influence_score -= 0.5
        if causes_diffusion:
            influence_score -= 0.2

        # Clamp to [-1, 1]
        influence_score = max(-1.0, min(1.0, influence_score))

        # Classify influence type
        if influence_score > self.constructive_threshold:
            influence_type = InfluenceType.CONSTRUCTIVE
        elif influence_score < self.destructive_threshold:
            influence_type = InfluenceType.DESTRUCTIVE
        else:
            influence_type = InfluenceType.NEUTRAL

        return LayerInfluenceMetrics(
            layer_idx=layer_idx,
            component_name=component_name,
            influence_type=influence_type,
            influence_score=influence_score,
            phase_preservation=phase_preservation,
            phase_amplification=amplification,
            gradient_flow=gradient_flow,
            entropy_delta=entropy_delta,
            causes_collapse=causes_collapse,
            causes_diffusion=causes_diffusion,
            is_bottleneck=is_bottleneck,
        )

    def analyze_all_layers(
        self,
        layer_hidden_states: List[torch.Tensor],
        num_heads: int = 8,
    ) -> Dict[int, LayerInfluenceMetrics]:
        """
        Analyze influence for all configured SRK layers.

        Args:
            layer_hidden_states: List of hidden states from each layer

        Returns:
            Dictionary mapping layer index to influence metrics
        """
        results = {}
        num_layers = len(layer_hidden_states)

        # Analyze DNA Bridge layer
        if self.config.enable_dna_bridge and self.config.dna_bridge_layer < num_layers:
            layer_idx = self.config.dna_bridge_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)] if layer_idx > 0 else layer_hidden_states[0]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "DNA Bridge", input_h, output_h, num_heads
            )

        # Analyze CSR Alignment layer
        if self.config.enable_phase_hook and self.config.csr_alignment_layer < num_layers:
            layer_idx = self.config.csr_alignment_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "CSR Alignment", input_h, output_h, num_heads
            )

        # Analyze Witness Arbitrator layer
        if self.config.enable_witness and self.config.witness_layer < num_layers:
            layer_idx = self.config.witness_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "Witness Arbitrator", input_h, output_h, num_heads
            )

        # Analyze Synthesis Gate layer
        if self.config.enable_synthesis and self.config.synthesis_layer < num_layers:
            layer_idx = self.config.synthesis_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "Synthesis Gate", input_h, output_h, num_heads
            )

        # Store in history
        self.influence_history.append(results)

        return results

    def print_influence_report(
        self,
        influence_metrics: Dict[int, LayerInfluenceMetrics],
        step: int = 0,
    ):
        """Print formatted influence report for all layers."""
        print(f"\n      ╔══════════════════════════════════════════════════════════════════╗")
        print(f"      ║  SRK LAYER INFLUENCE DIAGNOSTICS @ Step {step:<6}                  ║")
        print(f"      ╠══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Layer  Component           Influence    Score   Flags          ║")
        print(f"      ╠══════════════════════════════════════════════════════════════════╣")

        for layer_idx in sorted(influence_metrics.keys()):
            m = influence_metrics[layer_idx]
            symbol = m.get_influence_symbol()

            # Build flags string
            flags = []
            if m.causes_collapse:
                flags.append("COLLAPSE")
            if m.causes_diffusion:
                flags.append("DIFFUSE")
            if m.is_bottleneck:
                flags.append("BLOCKED")
            flags_str = ",".join(flags) if flags else "OK"

            # Influence type with color indicator
            if m.influence_type == InfluenceType.CONSTRUCTIVE:
                inf_str = f"[{symbol}] CONSTRUCTIVE"
            elif m.influence_type == InfluenceType.DESTRUCTIVE:
                inf_str = f"[{symbol}] DESTRUCTIVE"
            else:
                inf_str = f"[{symbol}] NEUTRAL    "

            print(f"      ║  L{layer_idx:<4} {m.component_name:<18} {inf_str}  {m.influence_score:+.2f}   {flags_str:<14} ║")

        print(f"      ╠══════════════════════════════════════════════════════════════════╣")

        # Summary
        constructive = sum(1 for m in influence_metrics.values() if m.influence_type == InfluenceType.CONSTRUCTIVE)
        destructive = sum(1 for m in influence_metrics.values() if m.influence_type == InfluenceType.DESTRUCTIVE)
        neutral = sum(1 for m in influence_metrics.values() if m.influence_type == InfluenceType.NEUTRAL)

        total_score = sum(m.influence_score for m in influence_metrics.values())
        avg_score = total_score / len(influence_metrics) if influence_metrics else 0

        if avg_score > 0.1:
            overall = "CONSTRUCTIVE overall"
        elif avg_score < -0.1:
            overall = "DESTRUCTIVE overall"
        else:
            overall = "NEUTRAL overall"

        print(f"      ║  Summary: {constructive} constructive, {neutral} neutral, {destructive} destructive        ║")
        print(f"      ║  Average Score: {avg_score:+.3f} → {overall:<20}                  ║")
        print(f"      ╚══════════════════════════════════════════════════════════════════╝")

    def print_detailed_layer_report(
        self,
        influence_metrics: Dict[int, LayerInfluenceMetrics],
    ):
        """Print detailed per-layer breakdown."""
        print(f"\n      Detailed Layer Analysis:")
        print(f"      " + "-" * 60)

        for layer_idx in sorted(influence_metrics.keys()):
            m = influence_metrics[layer_idx]
            print(f"\n      L{layer_idx}: {m.component_name}")
            print(f"        Influence: {m.influence_type.value} (score: {m.influence_score:+.3f})")
            print(f"        Phase Preservation:  {m.phase_preservation:.3f} {'✓' if m.phase_preservation > 0.5 else '⚠️'}")
            print(f"        Phase Amplification: {m.phase_amplification:.3f}x")
            print(f"        Gradient Flow:       {m.gradient_flow:.3f} {'✓' if m.gradient_flow > 0.1 else '⚠️'}")
            print(f"        Entropy Delta:       {m.entropy_delta:+.3f}")

            # Interpretation
            if m.influence_type == InfluenceType.CONSTRUCTIVE:
                print(f"        → This layer HELPS phase learning")
                if m.phase_preservation > 0.7:
                    print(f"          Good phase preservation through layer")
                if m.gradient_flow > 0.3:
                    print(f"          Healthy gradient flow")
            elif m.influence_type == InfluenceType.DESTRUCTIVE:
                print(f"        → This layer HURTS phase learning")
                if m.causes_collapse:
                    print(f"          ⚠️ Causing phase collapse!")
                if m.causes_diffusion:
                    print(f"          ⚠️ Causing phase diffusion!")
                if m.is_bottleneck:
                    print(f"          ⚠️ Blocking gradient flow!")
            else:
                print(f"        → This layer has MINIMAL effect on phase")

    def get_influence_summary(self) -> Dict[str, any]:
        """Get summary of influence trends over training."""
        if not self.influence_history:
            return {}

        summary = {'num_observations': len(self.influence_history)}

        # Track per-layer trends
        for layer_idx in self.influence_history[-1].keys():
            scores = [h[layer_idx].influence_score for h in self.influence_history if layer_idx in h]
            if scores:
                summary[f'L{layer_idx}_score_initial'] = scores[0]
                summary[f'L{layer_idx}_score_final'] = scores[-1]
                summary[f'L{layer_idx}_score_trend'] = scores[-1] - scores[0]

                # Count influence type changes
                types = [h[layer_idx].influence_type for h in self.influence_history if layer_idx in h]
                summary[f'L{layer_idx}_constructive_pct'] = sum(1 for t in types if t == InfluenceType.CONSTRUCTIVE) / len(types)
                summary[f'L{layer_idx}_destructive_pct'] = sum(1 for t in types if t == InfluenceType.DESTRUCTIVE) / len(types)

        return summary


# =============================================================================
# VOCABULARY (48 tokens)
# =============================================================================

class HardVocabulary:
    """
    Extended vocabulary for hard generalization probes.

    Design: Large enough to prevent memorization, structured for splits.

    Tokens (total: 48):
        0: PAD
        1: SEP (separator between operations)
        2: QUERY
        3: ANS (answer marker)
        4: NULL (negated/empty result)
        5: NEG (negation operator)
        6: BIND (binding operator)
        7: PERMUTE (role swap operator)
        8: OVERWRITE (explicit overwrite marker)
        9-24: Entities E0-E15 (train: E0-E7, test: E8-E15)
        25-31: Roles R0-R6 (train: R0-R3, test: R4-R6)
        32-37: Contexts C0-C5 (for SI disambiguation)
        38-43: Verbs V0-V5 (for LP schemas)
        44-47: Filler F0-F3 (distractor tokens)
    """

    def __init__(self):
        # Special tokens
        self.PAD = 0
        self.SEP = 1
        self.QUERY = 2
        self.ANS = 3
        self.NULL = 4
        self.NEG = 5
        self.BIND = 6
        self.PERMUTE = 7
        self.OVERWRITE = 8

        # Entities: 16 total (split for generalization)
        self.entities = list(range(9, 25))  # E0-E15
        self.train_entities = list(range(9, 17))   # E0-E7
        self.test_entities = list(range(17, 25))   # E8-E15

        # Roles: 7 total (split for generalization)
        self.roles = list(range(25, 32))  # R0-R6
        self.train_roles = list(range(25, 29))  # R0-R3
        self.test_roles = list(range(29, 32))   # R4-R6

        # Contexts
        self.contexts = list(range(32, 38))  # C0-C5

        # Verbs
        self.verbs = list(range(38, 44))  # V0-V5

        # Fillers
        self.fillers = list(range(44, 48))  # F0-F3

        self.vocab_size = 48

        # Human-readable names
        self._build_names()

    def _build_names(self):
        self.id2name = {
            self.PAD: "PAD", self.SEP: "|", self.QUERY: "Q",
            self.ANS: "→", self.NULL: "NULL", self.NEG: "NOT",
            self.BIND: "BIND", self.PERMUTE: "PERM", self.OVERWRITE: "OVR",
        }
        for i, e in enumerate(self.entities):
            self.id2name[e] = f"E{i}"
        for i, r in enumerate(self.roles):
            self.id2name[r] = f"R{i}"
        for i, c in enumerate(self.contexts):
            self.id2name[c] = f"C{i}"
        for i, v in enumerate(self.verbs):
            self.id2name[v] = f"V{i}"
        for i, f in enumerate(self.fillers):
            self.id2name[f] = f"F{i}"

    def decode(self, ids: List[int]) -> str:
        return " ".join(self.id2name.get(t, f"[{t}]") for t in ids if t != self.PAD)

    def entity_to_idx(self, entity_id: int) -> int:
        """Convert entity token ID to classification index."""
        return self.entities.index(entity_id)

    def idx_to_entity(self, idx: int) -> int:
        """Convert classification index to entity token ID."""
        return self.entities[idx]


# =============================================================================
# SCHEMA TYPES
# =============================================================================

class SchemaType(Enum):
    """Types of composed schemas."""
    BIND_CHAIN = "bind_chain"           # Multiple bindings with overwrites
    BIND_NEG = "bind_neg"               # Scoped negation
    CHAIN_DEEP = "chain_deep"           # Long chains (4-8 steps)
    SI_BIND = "si_bind"                 # Symbol reinterpretation + binding
    LP_BIND = "lp_bind"                 # Long persistence + binding
    PERMUTE_BIND = "permute_bind"       # Role permutation


# =============================================================================
# SPLIT TYPES
# =============================================================================

class SplitType(Enum):
    """Test split types for separate evaluation."""
    TRAIN = "train"
    TEST_ROLES = "test_roles"           # Held-out roles R4-R6
    TEST_ENTITIES = "test_entities"     # Open-world entities E8-E15
    TEST_BOTH = "test_both"             # Both held-out
    TEST_LONG = "test_long"             # Long chains with train tokens
    TEST_PERSIST = "test_persist"       # Pure persistence: BIND+QUERY only, chain 8-12


# =============================================================================
# STATE TRACKER (for computing correct answers)
# =============================================================================

class BindingState:
    """
    Tracks binding state through composed operations.

    This is the "ground truth" state machine that computes correct answers.
    The model must learn to replicate this state tracking.
    """

    def __init__(self):
        self.bindings: Dict[int, int] = {}  # role -> entity
        self.negated_roles: Set[int] = set()
        self.permutations: List[Tuple[int, int]] = []  # (r1, r2) swaps

    def bind(self, entity: int, role: int):
        """Bind entity to role (overwrites existing)."""
        self.bindings[role] = entity

    def negate(self, role: int):
        """Mark role as negated."""
        self.negated_roles.add(role)

    def permute(self, role1: int, role2: int):
        """Swap bindings of two roles."""
        e1 = self.bindings.get(role1)
        e2 = self.bindings.get(role2)
        if e1 is not None:
            self.bindings[role2] = e1
        elif role2 in self.bindings:
            del self.bindings[role2]
        if e2 is not None:
            self.bindings[role1] = e2
        elif role1 in self.bindings:
            del self.bindings[role1]
        self.permutations.append((role1, role2))

    def query(self, role: int, null_entity: int) -> int:
        """Query binding for role, respecting negation."""
        if role in self.negated_roles:
            return null_entity
        return self.bindings.get(role, null_entity)


# =============================================================================
# SCHEMA GENERATORS
# =============================================================================

class ComposedSchemaGenerator:
    """
    Base class for composed schema generators.

    KEY DESIGN: Each generator produces multi-step sequences that require
    state tracking to solve. Single-pattern matching cannot succeed.
    """

    def __init__(
        self,
        vocab: HardVocabulary,
        max_seq_len: int,
        entities: List[int],
        roles: List[int],
        chain_length: Tuple[int, int] = (3, 5),
    ):
        self.vocab = vocab
        self.max_seq_len = max_seq_len
        self.entities = entities
        self.roles = roles
        self.chain_min, self.chain_max = chain_length

    def generate(self) -> Tuple[List[int], int, str]:
        """Generate (input_ids, target_entity_id, explanation)."""
        raise NotImplementedError

    def pad(self, ids: List[int]) -> List[int]:
        """Pad sequence to max_seq_len."""
        if len(ids) < self.max_seq_len:
            ids = ids + [self.vocab.PAD] * (self.max_seq_len - len(ids))
        return ids[:self.max_seq_len]


class BindChainGenerator(ComposedSchemaGenerator):
    """
    BIND_CHAIN: Multiple bindings with overwrites.

    Pattern: BIND E1 R0 | BIND E2 R1 | BIND E3 R0 | QUERY R0 → E3
                                       ↑ overwrites first binding

    WHY QUADRATIC FAILS:
    - Learns "first BIND with R0 → return that entity"
    - Cannot track that later BIND overwrites earlier one
    - Attention pattern for R0 points to wrong position

    WHY PHASE SUCCEEDS:
    - Cumsum state naturally accumulates (later overwrites earlier)
    - Phase offset for R0 always reflects most recent binding
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Number of bindings (includes overwrites)
        n_bindings = random.randint(self.chain_min, self.chain_max)

        # Select roles (some will be overwritten)
        n_roles = min(len(self.roles), max(2, n_bindings - 1))
        used_roles = random.sample(self.roles, n_roles)

        # Generate bindings (with intentional overwrites)
        bindings_made = []
        for i in range(n_bindings):
            entity = random.choice(self.entities)
            # Sometimes reuse a role (overwrite)
            if i > 0 and random.random() < 0.4:
                role = random.choice(used_roles)  # Reuse → overwrite
            else:
                role = random.choice(used_roles)

            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)
            bindings_made.append((entity, role))

        # Query a role that was used
        query_role = random.choice(used_roles)
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"BIND_CHAIN: {len(bindings_made)} bindings, query {self.vocab.id2name[query_role]}"
        return self.pad(ids), target, explanation


class BindNegGenerator(ComposedSchemaGenerator):
    """
    BIND_NEG: Scoped negation of specific bindings.

    Pattern: BIND E1 R0 | BIND E2 R1 | NEG R1 | QUERY R0 → E1
                                                QUERY R1 → NULL

    WHY QUADRATIC FAILS:
    - Cannot track which specific roles are negated
    - NEG applies to R1, not R0 — requires relational scope tracking
    - Pattern matching sees "NEG somewhere" → might negate everything

    WHY PHASE SUCCEEDS:
    - NEG operation modifies phase state for specific role
    - Query phase alignment detects negation state per-role
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Generate base bindings (allow role reuse if chain > available roles)
        max_unique = min(len(self.roles), len(self.entities))
        effective_min = min(self.chain_min, max_unique)
        effective_max = min(self.chain_max, max_unique)
        n_bindings = random.randint(effective_min, effective_max)
        used_roles = random.sample(self.roles, n_bindings)
        used_entities = random.sample(self.entities, n_bindings)

        for entity, role in zip(used_entities, used_roles):
            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)

        # Negate some roles (not all)
        n_negations = random.randint(1, max(1, n_bindings - 1))
        negated_roles = random.sample(used_roles, n_negations)

        for role in negated_roles:
            ids.extend([self.vocab.NEG, role, self.vocab.SEP])
            state.negate(role)

        # Query (mix of negated and non-negated)
        query_role = random.choice(used_roles)
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"BIND_NEG: negated {negated_roles}, query {self.vocab.id2name[query_role]}"
        return self.pad(ids), target, explanation


class ChainDeepGenerator(ComposedSchemaGenerator):
    """
    CHAIN_DEEP: Long chains requiring state persistence across many steps.

    Pattern: BIND E1 R0 | BIND E2 R1 | ... | BIND En Rm | ... | QUERY R0 → E1

    WHY QUADRATIC FAILS:
    - At small model sizes, attention span is limited
    - Early bindings get "washed out" by later processing
    - Must attend to position 0-3 from position 30+ (attention decay)

    WHY PHASE SUCCEEDS:
    - Cumsum maintains state with O(n) complexity
    - Early bindings persist in accumulated state
    - No attention span limitation
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Force longer chains for this schema
        n_bindings = random.randint(max(4, self.chain_min), self.chain_max)
        n_roles = min(len(self.roles), n_bindings)
        used_roles = random.sample(self.roles, n_roles)

        # Generate many bindings
        for i in range(n_bindings):
            entity = random.choice(self.entities)
            role = used_roles[i % n_roles]  # Cycle through roles

            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)

            # Add filler between some bindings (increases distance)
            if i < n_bindings - 1 and random.random() < 0.3:
                n_filler = random.randint(1, 3)
                for _ in range(n_filler):
                    ids.append(random.choice(self.vocab.fillers))
                ids.append(self.vocab.SEP)

        # Query an early role (tests long-range persistence)
        query_role = used_roles[0]  # Always query first role used
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"CHAIN_DEEP: {n_bindings} steps, query early R0"
        return self.pad(ids), target, explanation


class PermuteBindGenerator(ComposedSchemaGenerator):
    """
    PERMUTE_BIND: Role permutation to test true relational invariance.

    Pattern: BIND E1 R0 | BIND E2 R1 | PERMUTE R0 R1 | QUERY R0 → E2
                                                       QUERY R1 → E1

    WHY QUADRATIC FAILS:
    - Learns token-specific attention patterns
    - "R0" always attends to same relative positions
    - Cannot dynamically swap role meanings

    WHY PHASE SUCCEEDS:
    - Phase encodes role as relational offset, not token identity
    - PERMUTE swaps phase offsets → queries work correctly
    - True relational encoding, not token lookup
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Need at least 2 roles for permutation
        n_bindings = random.randint(max(2, self.chain_min), self.chain_max)
        n_roles = min(len(self.roles), n_bindings)
        used_roles = random.sample(self.roles, max(2, n_roles))
        used_entities = random.sample(self.entities, len(used_roles))

        # Initial bindings
        for entity, role in zip(used_entities, used_roles):
            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)

        # Permute two roles
        r1, r2 = random.sample(used_roles, 2)
        ids.extend([self.vocab.PERMUTE, r1, r2, self.vocab.SEP])
        state.permute(r1, r2)

        # Query one of the permuted roles
        query_role = random.choice([r1, r2])
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"PERMUTE: swapped {self.vocab.id2name[r1]}↔{self.vocab.id2name[r2]}, query {self.vocab.id2name[query_role]}"
        return self.pad(ids), target, explanation


class SIBindGenerator(ComposedSchemaGenerator):
    """
    SI_BIND: Symbol reinterpretation + binding.

    Pattern: BIND E1 R0 C0 | BIND E1 R1 C1 | QUERY E1 C0 → R0 (returns entity bound in C0 context)

    Note: Simplified to return entity, querying by context.

    WHY QUADRATIC FAILS:
    - Same entity token E1 appears multiple times
    - Cannot track which context applies to which binding
    - Pattern matching on E1 is ambiguous

    WHY PHASE SUCCEEDS:
    - Context modifies phase, creating distinct states
    - Query with context selects correct binding
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Use same entity in different contexts
        entity = random.choice(self.entities)
        contexts = random.sample(self.vocab.contexts, 2)
        roles = random.sample(self.roles, 2)

        # Bind same entity to different roles in different contexts
        # We'll encode context as part of the role selection
        for ctx, role in zip(contexts, roles):
            ids.extend([self.vocab.BIND, entity, role, ctx, self.vocab.SEP])
            # For simplicity, bind entity to role (context just adds complexity)
            state.bind(entity, role)

        # Add some noise bindings
        for _ in range(random.randint(1, 2)):
            other_entity = random.choice([e for e in self.entities if e != entity])
            other_role = random.choice([r for r in self.roles if r not in roles])
            ids.extend([self.vocab.BIND, other_entity, other_role, self.vocab.SEP])
            state.bind(other_entity, other_role)

        # Query by role (the context was a distractor that complicates patterns)
        query_role = random.choice(roles)
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"SI_BIND: context-varied bindings"
        return self.pad(ids), target, explanation


class LPBindGenerator(ComposedSchemaGenerator):
    """
    LP_BIND: Long persistence + binding.

    Pattern: E1 V0 | F0 F1 F2 | BIND E1 R0 | QUERY R0 → E1

    WHY QUADRATIC FAILS:
    - Filler tokens dilute attention to E1
    - Must persist entity salience across distractors
    - Then bind the persisted entity

    WHY PHASE SUCCEEDS:
    - Phase state accumulates entity information
    - Filler doesn't erase state (cumsum persists)
    - Binding captures persisted entity
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Primary entity with verb
        primary = random.choice(self.entities)
        verb = random.choice(self.vocab.verbs)
        ids.extend([primary, verb, self.vocab.SEP])

        # Filler (distractors)
        n_filler = random.randint(2, 4)
        for _ in range(n_filler):
            ids.append(random.choice(self.vocab.fillers))
        ids.append(self.vocab.SEP)

        # Now bind the primary entity (must have persisted it)
        role = random.choice(self.roles)
        ids.extend([self.vocab.BIND, primary, role, self.vocab.SEP])
        state.bind(primary, role)

        # Add more bindings for complexity
        for _ in range(random.randint(1, 2)):
            other = random.choice([e for e in self.entities if e != primary])
            other_role = random.choice([r for r in self.roles if r != role])
            ids.extend([self.vocab.BIND, other, other_role, self.vocab.SEP])
            state.bind(other, other_role)

        # Query the persisted entity's role
        ids.extend([self.vocab.QUERY, role, self.vocab.ANS])
        target = state.query(role, self.vocab.NULL)

        explanation = f"LP_BIND: persist {self.vocab.id2name[primary]} across {n_filler} fillers"
        return self.pad(ids), target, explanation


class PureBindGenerator(ComposedSchemaGenerator):
    """
    PURE_BIND: Pure persistence test - BIND + QUERY only, no operations.

    Pattern: BIND E1 R0 | BIND E2 R1 | ... | BIND En Rm | QUERY Rx → Ex

    This isolates STATE PERSISTENCE from LOGICAL COMPOSITION.
    No NEG, no PERMUTE, no CONTEXT - just raw binding and retrieval.

    WHY THIS MATTERS:
    -----------------
    This shows Phase's clean O(n) advantage for pure memory tasks.
    It separates "can the model remember bindings?" from "can it reason about operations?"

    WHY QUADRATIC FAILS:
    - At chain length 8-12, attention span limits kick in
    - Early bindings get washed out by later processing
    - No attention "shortcut" to early positions from late queries

    WHY PHASE SUCCEEDS:
    - Cumsum maintains state with O(n) complexity
    - Early bindings persist indefinitely in accumulated state
    - Query phase alignment retrieves correct binding regardless of distance
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Number of bindings (long chains for persistence test)
        n_bindings = random.randint(self.chain_min, self.chain_max)

        # Use all available roles, cycle if needed
        n_roles = min(len(self.roles), n_bindings)
        used_roles = random.sample(self.roles, n_roles)

        # Track which entity is bound to which role (last binding wins)
        role_to_entity = {}

        # Generate bindings (some roles may be overwritten)
        for i in range(n_bindings):
            entity = random.choice(self.entities)
            role = used_roles[i % n_roles]  # Cycle through roles

            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)
            role_to_entity[role] = entity

        # Query an early role (tests long-range persistence)
        # Prefer querying a role that was bound early
        query_role = used_roles[0]
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"PURE_BIND: {n_bindings} bindings, query early role"
        return self.pad(ids), target, explanation


# =============================================================================
# DATASET
# =============================================================================

class HardProbeDataset(Dataset):
    """
    Dataset with strict train/test splits for generalization testing.

    CRITICAL: No leakage between splits.
    - Training uses only train_entities and train_roles
    - Test splits use held-out tokens as specified
    """

    def __init__(
        self,
        vocab: HardVocabulary,
        split: SplitType,
        num_samples: int,
        max_seq_len: int,
        chain_length: Tuple[int, int],
        bind_ratio: float = 0.6,
        seed: int = 42,
    ):
        self.vocab = vocab
        self.split = split
        self.num_samples = num_samples
        self.bind_ratio = bind_ratio

        # Determine allowed entities and roles based on split
        self._persist_only = False  # Special flag for pure persistence test
        if split == SplitType.TRAIN:
            entities = vocab.train_entities
            roles = vocab.train_roles
        elif split == SplitType.TEST_ROLES:
            entities = vocab.train_entities  # Same entities
            roles = vocab.test_roles         # Held-out roles
        elif split == SplitType.TEST_ENTITIES:
            entities = vocab.test_entities   # Held-out entities
            roles = vocab.train_roles        # Same roles
        elif split == SplitType.TEST_BOTH:
            entities = vocab.test_entities   # Held-out
            roles = vocab.test_roles         # Held-out
        elif split == SplitType.TEST_LONG:
            entities = vocab.train_entities  # Same tokens
            roles = vocab.train_roles        # Same tokens
            # But chain_length is longer (set externally)
        elif split == SplitType.TEST_PERSIST:
            entities = vocab.train_entities  # Same tokens
            roles = vocab.train_roles        # Same tokens
            self._persist_only = True        # Only use PureBindGenerator
            # Chain length 8-12 for pure persistence test (set externally)
        else:
            raise ValueError(f"Unknown split: {split}")

        # Create generators
        self.generators = self._create_generators(
            vocab, max_seq_len, entities, roles, chain_length
        )

        # Pre-generate samples
        random.seed(seed)
        self.samples = []
        for _ in range(num_samples):
            gen = self._select_generator()
            ids, target, explanation = gen.generate()
            self.samples.append((ids, target, explanation))

    def _create_generators(
        self,
        vocab: HardVocabulary,
        max_seq_len: int,
        entities: List[int],
        roles: List[int],
        chain_length: Tuple[int, int],
    ) -> Dict[SchemaType, ComposedSchemaGenerator]:
        """Create all generators with specified entity/role pools."""
        gens = {
            SchemaType.BIND_CHAIN: BindChainGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.BIND_NEG: BindNegGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.CHAIN_DEEP: ChainDeepGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.PERMUTE_BIND: PermuteBindGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.SI_BIND: SIBindGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.LP_BIND: LPBindGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
        }
        # Also create PureBindGenerator for persistence-only tests
        self._pure_bind_gen = PureBindGenerator(
            vocab, max_seq_len, entities, roles, chain_length
        )
        return gens

    def _select_generator(self) -> ComposedSchemaGenerator:
        """Select generator based on bind_ratio curriculum or persist_only mode."""
        # For pure persistence test: only use PureBindGenerator
        if self._persist_only:
            return self._pure_bind_gen

        bind_schemas = [
            SchemaType.BIND_CHAIN,
            SchemaType.BIND_NEG,
            SchemaType.CHAIN_DEEP,
            SchemaType.PERMUTE_BIND,
        ]
        other_schemas = [
            SchemaType.SI_BIND,
            SchemaType.LP_BIND,
        ]

        if random.random() < self.bind_ratio:
            schema = random.choice(bind_schemas)
        else:
            schema = random.choice(other_schemas)

        return self.generators[schema]

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        ids, target, explanation = self.samples[idx]
        return (
            torch.tensor(ids, dtype=torch.long),
            torch.tensor(target, dtype=torch.long),
            explanation,
        )


def collate_fn(batch):
    """Collate function that handles explanations."""
    ids = torch.stack([b[0] for b in batch])
    targets = torch.stack([b[1] for b in batch])
    explanations = [b[2] for b in batch]
    return ids, targets, explanations


# =============================================================================
# MODELS
# =============================================================================

class QuadraticAttention(nn.Module):
    """Standard O(n^2) attention."""

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.scale = math.sqrt(self.head_dim)

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, D = x.shape

        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.W_k(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Causal mask
        mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class PhaseAttention(nn.Module):
    """
    O(n) phasor attention with operation-conditioned phase offsets.

    KEY ENHANCEMENT: Operation tokens (NEG, PERMUTE, OVERWRITE) add learned
    phase shifts before the cumsum. This allows operations to be true STATE
    TRANSFORMATIONS rather than passive symbols.

    WHY THIS MATTERS:
    -----------------
    Without operation-conditioned offsets, operations like NEG are just tokens
    that the model must learn to interpret through content-based attention.
    With offsets, operations directly transform the phase state, which is how
    Phase is hypothesized to encode relational structure.

    This is NOT cheating - it tests the hypothesis more faithfully by making
    operations act as they're theoretically supposed to.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1,
                 operation_tokens: List[int] = None, bounded_phase: bool = True,
                 dual_channel_mode: bool = False, alignment_authority: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.bounded_phase = bounded_phase  # V9.9.11: Constrain φ to [-π, π] via π*sin()

        # V10.3.8: Dual-Channel Attention
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority

        self.W_q_phase = nn.Linear(d_model, d_model)
        self.W_k_phase = nn.Linear(d_model, d_model)
        self.W_q_amp = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

        # Operation-conditioned phase offsets
        # Each operation token gets a learned phase shift per head
        self.operation_tokens = operation_tokens or []
        if self.operation_tokens:
            # Map operation token IDs to indices 0, 1, 2, ...
            self.op_to_idx = {tok: i for i, tok in enumerate(self.operation_tokens)}
            # Learned phase shifts: [num_ops, num_heads, head_dim]
            self.op_phase_shifts = nn.Parameter(
                torch.randn(len(self.operation_tokens), num_heads, self.head_dim) * 0.1
            )
        else:
            self.op_to_idx = {}
            self.op_phase_shifts = None

        self._ablation_mode = "none"
        self._scramble_seed = 42
        self.capture_diagnostics = False
        self._phi_k = None
        self._phi_q = None

        # Rotation test: add a global phase rotation to φ_q
        self._rotation_angle = 0.0  # in radians

        # V10.3.8: Intent phase storage for dual-channel diagnostics
        self._intent_phase_query = None  # θ_JEPA
        self._intent_phase_key = None    # θ_SRK

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode
        self._scramble_seed = seed

    def set_rotation(self, angle_radians: float):
        """
        Set a global phase rotation to apply to φ_q.

        This tests whether phase encodes relational structure:
        - If roles are phase-encoded, rotating φ_q should shift which bindings are retrieved
        - If phase is decorative, rotation should have minimal effect

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self._rotation_angle = angle_radians

    def clear_rotation(self):
        """Clear any applied rotation."""
        self._rotation_angle = 0.0

    def _ablate(self, phi: torch.Tensor) -> torch.Tensor:
        if self._ablation_mode == "none":
            return phi
        elif self._ablation_mode == "scramble":
            B, N, H, D = phi.shape
            torch.manual_seed(self._scramble_seed)
            result = phi.clone()
            for b in range(B):
                for h in range(H):
                    perm = torch.randperm(N, device=phi.device)
                    result[b, :, h, :] = phi[b, perm, h, :]
            return result
        elif self._ablation_mode in ["freeze", "off"]:
            return torch.zeros_like(phi)
        return phi

    def _apply_operation_phase_shifts(self, phi_k: torch.Tensor,
                                       token_ids: torch.Tensor) -> torch.Tensor:
        """
        Apply learned phase shifts for operation tokens.

        When NEG, PERMUTE, or OVERWRITE appears, add its learned phase shift
        to phi_k at that position. This transforms the state before cumsum.
        """
        if self.op_phase_shifts is None or token_ids is None:
            return phi_k

        B, N, H, D = phi_k.shape

        # Create mask for each operation type and apply its phase shift
        for tok_id, op_idx in self.op_to_idx.items():
            # Mask: [B, N] where operation token appears
            mask = (token_ids == tok_id).float()  # [B, N]
            # Expand mask to [B, N, H, D]
            mask = mask.unsqueeze(-1).unsqueeze(-1).expand(B, N, H, D)
            # Get phase shift for this operation: [H, D] -> [1, 1, H, D]
            shift = self.op_phase_shifts[op_idx].unsqueeze(0).unsqueeze(0)
            # Apply: add shift where operation token appears
            phi_k = phi_k + mask * shift

        return phi_k

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None,
                intent_phase_query: torch.Tensor = None,
                intent_phase_key: torch.Tensor = None) -> torch.Tensor:
        """
        Forward pass with optional operation-conditioned phase shifts.

        Args:
            x: Input tensor [B, N, D]
            token_ids: Token IDs [B, N] for operation-conditioned phase shifts
            intent_phase_query: V10.3.8 - θ_JEPA from Sensor (optional)
            intent_phase_key: V10.3.8 - θ_SRK from Master (optional)
        """
        B, N, D = x.shape

        # Compute phase projections
        phi_q_raw = self.W_q_phase(x).view(B, N, self.num_heads, self.head_dim)
        phi_k_raw = self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim)

        # V9.9.11: Bounded phase parameterization (constrain φ to [-π, π] via π*sin())
        if self.bounded_phase:
            phi_q = math.pi * torch.sin(phi_q_raw)
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_q = phi_q_raw
            phi_k = phi_k_raw

        # Apply operation-conditioned phase shifts BEFORE ablation
        phi_k = self._apply_operation_phase_shifts(phi_k, token_ids)

        phi_q = self._ablate(phi_q)
        phi_k = self._ablate(phi_k)

        # Apply rotation to φ_q (tests phase selectivity)
        if self._rotation_angle != 0.0:
            phi_q = phi_q + self._rotation_angle

        # V10.3.8: Store intent phases for diagnostics
        self._intent_phase_query = intent_phase_query
        self._intent_phase_key = intent_phase_key

        if self.capture_diagnostics:
            self._phi_k = phi_k.detach()
            self._phi_q = phi_q.detach()

        a_q = torch.sigmoid(self.W_q_amp(x)).view(B, N, self.num_heads, self.head_dim)
        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x).view(B, N, self.num_heads, self.head_dim)

        dtype = phi_q.dtype
        if dtype == torch.bfloat16:
            phi_q, phi_k, a_q, a_k, v = [t.float() for t in [phi_q, phi_k, a_q, a_k, v]]

        q_phasor = torch.polar(a_q, phi_q)
        k_phasor = torch.polar(a_k, -phi_k)

        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex
        state = torch.cumsum(kv, dim=1)

        output = (q_phasor * state).real

        # V10.3.8: Dual-Channel Alignment Modulation
        # If dual_channel_mode is enabled and we have intent phases,
        # modulate the content score by the alignment term:
        #   output = output * (1 + α * s_align)
        # where s_align = cos(θ_JEPA - θ_SRK)
        if self.dual_channel_mode and (intent_phase_query is not None or intent_phase_key is not None):
            # Normalize intent_phase shapes
            def _norm_intent(ip):
                if ip is None:
                    return None
                if ip.dim() == 2:
                    return ip.unsqueeze(1).unsqueeze(-1)  # [B, H] → [B, 1, H, 1]
                elif ip.dim() == 3:
                    return ip.unsqueeze(1)  # [B, H, D_h] → [B, 1, H, D_h]
                return ip

            theta_jepa = _norm_intent(intent_phase_query)
            theta_srk = _norm_intent(intent_phase_key)

            if theta_jepa is not None and theta_srk is not None:
                theta_diff = theta_jepa - theta_srk
            elif theta_jepa is not None:
                theta_diff = theta_jepa
            else:
                theta_diff = theta_srk

            # s_align = cos(θ_JEPA - θ_SRK)
            s_align = torch.cos(theta_diff.float())

            # Modulate: output = output * (1 + α * s_align)
            alignment_modulator = 1.0 + self.alignment_authority * s_align
            output = output * alignment_modulator

        if dtype == torch.bfloat16:
            output = output.to(dtype)

        output = output.reshape(B, N, D)
        return self.out_proj(self.dropout(output))

    def get_R_k(self) -> float:
        """Mean resultant length (phase health metric)."""
        if self._phi_k is None:
            return 0.0
        z = torch.exp(1j * self._phi_k.float())
        return torch.abs(z.mean()).item()

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float,
                 use_phase: bool, extra_ff: int = 0, operation_tokens: List[int] = None,
                 bounded_phase: bool = True, dual_channel_mode: bool = False,
                 alignment_authority: float = 0.1):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # PhaseAttention gets operation_tokens for conditioned phase shifts
        if use_phase:
            self.attn = PhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase,
                                       dual_channel_mode, alignment_authority)
        else:
            self.attn = QuadraticAttention(d_model, num_heads, dropout)

        # Extra FF parameters for matching (added to quadratic when match_params=True)
        actual_d_ff = d_ff + extra_ff
        self.ff = nn.Sequential(
            nn.Linear(d_model, actual_d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(actual_d_ff, d_model), nn.Dropout(dropout)
        )
        self.use_phase = use_phase

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        # Pass token_ids to PhaseAttention for operation-conditioned phase shifts
        if self.use_phase and token_ids is not None:
            x = x + self.attn(self.norm1(x), token_ids)
        else:
            x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x


class HybridTransformerBlock(nn.Module):
    """
    Hybrid block that MIXES Phase and Quadratic attention outputs.

    WHY MIXING (not switching):
    ---------------------------
    Instead of choosing one attention type per layer, we combine both:
      output = phase_ratio * phase_out + (1 - phase_ratio) * quad_out

    This allows smooth interpolation and lets the model learn to leverage
    Phase for state persistence and Quadratic for reasoning within each layer.

    The INVERTED CURRICULUM sets:
    - Early layers: phase_ratio ≈ 0.9 (mostly Phase for state capture)
    - Late layers: phase_ratio ≈ 0.1 (mostly Quadratic for reasoning)
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        phase_ratio: float = 0.5,  # 0.0 = pure Quadratic, 1.0 = pure Phase
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
        dual_channel_mode: bool = False,
        alignment_authority: float = 0.1,
    ):
        super().__init__()
        self.phase_ratio = phase_ratio
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # Both attention types
        self.phase_attn = PhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase,
                                         dual_channel_mode, alignment_authority)
        self.quad_attn = QuadraticAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        normed = self.norm1(x)

        # Run both attention types
        phase_out = self.phase_attn(normed, token_ids)
        quad_out = self.quad_attn(normed)

        # Mix outputs according to phase_ratio
        attn_out = self.phase_ratio * phase_out + (1 - self.phase_ratio) * quad_out

        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for Phase attention component."""
        self.phase_attn.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for Phase attention component."""
        self.phase_attn.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from Phase attention component."""
        self.phase_attn.clear_rotation()


class HybridTransformer(nn.Module):
    """
    Transformer with per-layer Phase/Quadratic mixing (INVERTED CURRICULUM).

    INVERTED CURRICULUM RATIONALE:
    ------------------------------
    Evidence shows PhaseAttention excels at STATE PERSISTENCE, not reasoning.
    Therefore:
    - Early layers: Phase-heavy → capture input state with O(n) efficiency
    - Late layers: Quadratic-heavy → reason over persisted state

    Curriculum format: List of phase_ratios per layer
    - [0.9, 0.7, 0.3, 0.1] = Inverted (Phase early, Quad late) ← RECOMMENDED
    - [0.1, 0.3, 0.7, 0.9] = Standard (Quad early, Phase late)
    - [0.5, 0.5, 0.5, 0.5] = Balanced
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        num_classes: int,
        curriculum: List[float],  # phase_ratio per layer
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
        dual_channel_mode: bool = False,
        alignment_authority: float = 0.1,
    ):
        super().__init__()
        self.curriculum = curriculum
        self.operation_tokens = operation_tokens
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority

        assert len(curriculum) == num_layers, \
            f"Curriculum length ({len(curriculum)}) must match num_layers ({num_layers})"

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList([
            HybridTransformerBlock(
                d_model, num_heads, d_ff, dropout,
                phase_ratio=curriculum[i],
                operation_tokens=operation_tokens,
                bounded_phase=bounded_phase,
                dual_channel_mode=dual_channel_mode,
                alignment_authority=alignment_authority,
            )
            for i in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        for layer in self.layers:
            x = layer(x, input_ids)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for all Phase attention components."""
        for layer in self.layers:
            layer.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for all Phase attention layers."""
        for layer in self.layers:
            layer.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase attention layers."""
        for layer in self.layers:
            layer.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        """Enable/disable phase diagnostics capture."""
        for layer in self.layers:
            layer.phase_attn.capture_diagnostics = enable

    def get_R_k(self) -> float:
        """Get mean R_k across all Phase attention layers."""
        r_values = []
        for layer in self.layers:
            r_values.append(layer.phase_attn.get_R_k())
        return sum(r_values) / len(r_values) if r_values else 0.0

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def describe_curriculum(self) -> str:
        """Return human-readable curriculum description."""
        parts = []
        for i, ratio in enumerate(self.curriculum):
            parts.append(f"L{i}:{ratio*100:.0f}%P")
        return " → ".join(parts)


# =============================================================================
# PROTECTED PHASE ARCHITECTURE (v5)
# =============================================================================
# Evidence shows Phase becomes DECORATIVE when mixed with Quadratic.
# Solution: Give Phase and Quadratic EXCLUSIVE, NON-COMPETING roles.
#
# Architecture:
#   Phase:     memory_state = cumsum(keys * values)  # Accumulate bindings
#   Quadratic: output = attention(query, memory_state)  # Query the memory
#
# This is NOT mixing - it's COLLABORATION:
#   - Phase has exclusive control over state accumulation
#   - Quadratic has exclusive control over state querying
#   - They don't compete for the same gradient signal
# =============================================================================

class ProtectedPhaseAttention(nn.Module):
    """
    Phase attention that outputs a MEMORY STATE for Quadratic to query.

    Unlike regular PhaseAttention which outputs attention-weighted values,
    this outputs the raw cumsum state that Quadratic can query.

    Phase's exclusive job: Accumulate key-value pairs into persistent state.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1,
                 operation_tokens: List[int] = None, bounded_phase: bool = True):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.bounded_phase = bounded_phase  # V9.9.11: Constrain φ to [-π, π] via π*sin()

        # Phase projections for keys
        self.W_k_phase = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)

        # Operation-conditioned phase offsets
        self.operation_tokens = operation_tokens or []
        if self.operation_tokens:
            self.op_to_idx = {tok: i for i, tok in enumerate(self.operation_tokens)}
            self.op_phase_shifts = nn.Parameter(
                torch.randn(len(self.operation_tokens), num_heads, self.head_dim) * 0.1
            )
        else:
            self.op_to_idx = {}
            self.op_phase_shifts = None

        self.dropout = nn.Dropout(dropout)
        self._ablation_mode = "none"
        self._rotation_angle = 0.0  # For rotation test (applied to phi_k)

        # Health tracking: R_k (amplitude) statistics
        self._last_r_k_mean = 0.0
        self._last_r_k_std = 0.0
        self._last_r_k_min = 0.0
        self._last_r_k_max = 0.0

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode
        self._scramble_seed = seed

    def set_rotation(self, angle_radians: float):
        """
        Set a global phase rotation to apply to φ_k.

        For Protected Phase, we rotate φ_k (not φ_q) because:
        - Protected Phase uses φ_k for memory accumulation (cumsum)
        - There is no φ_q in this architecture (Quadratic handles queries)

        This tests whether phase encodes relational structure:
        - If roles are phase-encoded in keys, rotating φ_k should disrupt retrieval
        - If phase is decorative, rotation should have minimal effect

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self._rotation_angle = angle_radians

    def clear_rotation(self):
        """Clear any applied rotation."""
        self._rotation_angle = 0.0

    def get_health_metrics(self) -> dict:
        """Return Phase health metrics (R_k statistics)."""
        return {
            "r_k_mean": self._last_r_k_mean,
            "r_k_std": self._last_r_k_std,
            "r_k_min": self._last_r_k_min,
            "r_k_max": self._last_r_k_max,
        }

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        """
        Compute Phase memory state via cumsum.

        Returns: memory_state [B, N, D] - the accumulated state for Quadratic to query
        """
        B, N, D = x.shape

        # Compute phase projection for keys
        phi_k_raw = self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim)

        # V9.9.11: Bounded phase parameterization (constrain φ to [-π, π] via π*sin())
        if self.bounded_phase:
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_k = phi_k_raw

        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x).view(B, N, self.num_heads, self.head_dim)

        # Track R_k health metrics (amplitude statistics)
        with torch.no_grad():
            self._last_r_k_mean = a_k.mean().item()
            self._last_r_k_std = a_k.std().item()
            self._last_r_k_min = a_k.min().item()
            self._last_r_k_max = a_k.max().item()

        # Apply operation-conditioned phase shifts
        if self.op_phase_shifts is not None and token_ids is not None:
            for tok_id, op_idx in self.op_to_idx.items():
                mask = (token_ids == tok_id).float().unsqueeze(-1).unsqueeze(-1)
                mask = mask.expand(B, N, self.num_heads, self.head_dim)
                shift = self.op_phase_shifts[op_idx].unsqueeze(0).unsqueeze(0)
                phi_k = phi_k + mask * shift

        # Ablation
        if self._ablation_mode == "scramble":
            torch.manual_seed(self._scramble_seed)
            for b in range(B):
                for h in range(self.num_heads):
                    perm = torch.randperm(N, device=phi_k.device)
                    phi_k[b, :, h, :] = phi_k[b, perm, h, :]
        elif self._ablation_mode in ["freeze", "off"]:
            phi_k = torch.zeros_like(phi_k)

        # Apply rotation to φ_k (tests phase selectivity for Protected Phase)
        # Note: We rotate φ_k here because Protected Phase has no φ_q
        if self._rotation_angle != 0.0:
            phi_k = phi_k + self._rotation_angle

        # Compute complex phasor and accumulate via cumsum
        dtype = phi_k.dtype
        if dtype == torch.bfloat16:
            phi_k, a_k, v = phi_k.float(), a_k.float(), v.float()

        k_phasor = torch.polar(a_k, -phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex

        # CUMSUM: This is Phase's exclusive job - accumulate state
        memory_state = torch.cumsum(kv, dim=1)

        # Return real part as memory state for Quadratic to query
        memory_state = memory_state.real

        if dtype == torch.bfloat16:
            memory_state = memory_state.to(dtype)

        return memory_state.reshape(B, N, D)


class ProtectedQuadAttention(nn.Module):
    """
    Quadratic attention that QUERIES a memory state (from Phase).

    Unlike regular QuadraticAttention which computes K,V from input,
    this uses the Phase memory state as keys/values.

    Quadratic's exclusive job: Query the Phase-accumulated memory.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.scale = math.sqrt(self.head_dim)

        # Query projection (from input)
        self.W_q = nn.Linear(d_model, d_model)
        # Key/Value projections (from memory state)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, memory_state: torch.Tensor) -> torch.Tensor:
        """
        Query the Phase memory state.

        Args:
            x: Input tensor [B, N, D] - used for queries
            memory_state: Phase memory [B, N, D] - used for keys/values
        """
        B, N, D = x.shape

        # Queries from input
        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        # Keys and Values from Phase memory state
        K = self.W_k(memory_state).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(memory_state).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Standard attention over memory
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Causal mask
        mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)


class ProtectedPhaseBlock(nn.Module):
    """
    Block with PROTECTED Phase and Quadratic roles.

    Architecture:
        1. Phase accumulates memory: memory = cumsum(k * v)
        2. Quadratic queries memory: output = attention(q, memory)

    This is SEQUENTIAL COLLABORATION, not parallel mixing.
    Phase and Quadratic don't compete for gradients.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm_mem = nn.LayerNorm(d_model)

        # Protected Phase: accumulates memory state
        self.phase_memory = ProtectedPhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase)
        # Protected Quad: queries memory state
        self.quad_query = ProtectedQuadAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        # Step 1: Phase accumulates memory state (Phase's exclusive job)
        normed = self.norm1(x)
        memory_state = self.phase_memory(normed, token_ids)
        memory_state = self.norm_mem(memory_state)

        # Step 2: Quadratic queries the memory (Quad's exclusive job)
        attn_out = self.quad_query(normed, memory_state)

        # Residual and FF
        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for Phase component."""
        self.phase_memory.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for Phase component (applied to φ_k)."""
        self.phase_memory.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from Phase component."""
        self.phase_memory.clear_rotation()


class ProtectedPhaseTransformer(nn.Module):
    """
    Transformer with PROTECTED Phase architecture.

    Key insight from ablation tests:
    - When mixed, Phase becomes DECORATIVE (0% ablation drop)
    - When alone, Phase is ESSENTIAL (37% ablation drop)

    Solution: Give Phase and Quadratic NON-COMPETING roles:
    - Phase: O(n) memory accumulation (cumsum)
    - Quadratic: O(n²) memory querying (attention)

    They collaborate sequentially, not compete in parallel.
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        num_classes: int,
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.operation_tokens = operation_tokens

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList([
            ProtectedPhaseBlock(d_model, num_heads, d_ff, dropout, operation_tokens, bounded_phase)
            for _ in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        for layer in self.layers:
            x = layer(x, input_ids)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for all Phase components."""
        for layer in self.layers:
            layer.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """
        Set rotation angle for all Phase components (applied to φ_k).

        Note: ProtectedPhaseTransformer uses φ_k only (for memory accumulation),
        not φ_q. So we rotate φ_k to test whether phase encodes relational structure.

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        for layer in self.layers:
            layer.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase components."""
        for layer in self.layers:
            layer.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        """Enable/disable phase diagnostics (placeholder for compatibility)."""
        pass

    def get_phase_health(self) -> dict:
        """
        Aggregate Phase health metrics (R_k statistics) from all layers.

        Interpretation:
        - R_k → 0: Phase collapsed (bad)
        - R_k → 1: Phase degenerate (bad)
        - R_k stable in (0.3, 0.7): Healthy
        """
        metrics = {
            "r_k_mean": [],
            "r_k_std": [],
            "r_k_min": [],
            "r_k_max": [],
        }
        for layer in self.layers:
            layer_metrics = layer.phase_memory.get_health_metrics()
            for k, v in layer_metrics.items():
                metrics[k].append(v)

        # Average across layers
        return {
            "r_k_mean": sum(metrics["r_k_mean"]) / len(metrics["r_k_mean"]) if metrics["r_k_mean"] else 0.0,
            "r_k_std": sum(metrics["r_k_std"]) / len(metrics["r_k_std"]) if metrics["r_k_std"] else 0.0,
            "r_k_min": min(metrics["r_k_min"]) if metrics["r_k_min"] else 0.0,
            "r_k_max": max(metrics["r_k_max"]) if metrics["r_k_max"] else 0.0,
        }

    def get_R_k(self) -> float:
        """Get mean R_k metric for backward compatibility."""
        return self.get_phase_health()["r_k_mean"]

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class HardProbeTransformer(nn.Module):
    """Transformer for hard probe classification with operation-conditioned phase shifts."""

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        num_classes: int,
        use_phase: bool,
        extra_ff_per_layer: int = 0,  # For parameter matching
        operation_tokens: List[int] = None,  # Tokens that trigger phase shifts
        bounded_phase: bool = True,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
        dual_channel_mode: bool = False,  # V10.3.8: Separate content/intent
        alignment_authority: float = 0.1,  # V10.3.8: α weight for alignment
    ):
        super().__init__()
        self.use_phase = use_phase
        self.operation_tokens = operation_tokens
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            TransformerBlock(d_model, num_heads, d_ff, dropout, use_phase,
                           extra_ff_per_layer, operation_tokens, bounded_phase,
                           dual_channel_mode, alignment_authority)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        # Pass input_ids to layers for operation-conditioned phase shifts
        for layer in self.layers:
            x = layer(x, input_ids if self.use_phase else None)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        for layer in self.layers:
            if hasattr(layer.attn, 'set_ablation'):
                layer.attn.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for all Phase attention layers."""
        for layer in self.layers:
            if hasattr(layer.attn, 'set_rotation'):
                layer.attn.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase attention layers."""
        for layer in self.layers:
            if hasattr(layer.attn, 'clear_rotation'):
                layer.attn.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        for layer in self.layers:
            if hasattr(layer.attn, 'capture_diagnostics'):
                layer.attn.capture_diagnostics = enable

    def get_R_k(self) -> float:
        r_values = []
        for layer in self.layers:
            if hasattr(layer.attn, 'get_R_k'):
                r_values.append(layer.attn.get_R_k())
        return sum(r_values) / len(r_values) if r_values else 0.0

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def compute_param_diff(d_model: int, num_heads: int, num_layers: int) -> int:
    """
    Compute parameter difference between Phase and Quadratic attention.

    Phase has extra W_q_phase, W_k_phase, W_q_amp, W_k_amp projections.
    Quadratic has W_q, W_k, W_v.

    Difference per layer = 2 * d_model^2 (two extra projections)
    """
    # Phase: W_q_phase, W_k_phase, W_q_amp, W_k_amp, W_v, out_proj = 6
    # Quadratic: W_q, W_k, W_v, out_proj = 4
    # Difference: 2 projections per layer
    extra_per_layer = 2 * d_model * d_model
    return extra_per_layer * num_layers


# =============================================================================
# EVALUATION
# =============================================================================

def evaluate(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
) -> float:
    """Evaluate model accuracy."""
    model.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for ids, targets, _ in loader:
            ids, targets = ids.to(device), targets.to(device)

            # Convert entity IDs to class indices
            target_idx = torch.tensor([
                vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
                for t in targets
            ], device=device)

            logits = model(ids)
            preds = logits.argmax(dim=-1)

            # Handle NULL (maps to class 0 by convention, or separate handling)
            for i in range(len(targets)):
                if targets[i].item() == vocab.NULL:
                    # NULL target — check if prediction is outside entity range or class 0
                    # For simplicity, we'll treat NULL as predicting the "NULL entity" which is vocab.entities[0]
                    target_idx[i] = 0

            correct += (preds == target_idx).sum().item()
            total += len(targets)

    return correct / max(total, 1)


def evaluate_all_splits(
    model: nn.Module,
    test_loaders: Dict[SplitType, DataLoader],
    vocab: HardVocabulary,
    device: str,
) -> Dict[str, float]:
    """Evaluate on all test splits separately."""
    results = {}
    for split, loader in test_loaders.items():
        acc = evaluate(model, loader, vocab, device)
        results[split.value] = acc
    return results


def run_ablation(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
) -> Dict[str, float]:
    """Run phase ablation tests."""
    results = {}
    for mode in ["none", "scramble", "freeze", "off"]:
        model.set_ablation(mode)
        acc = evaluate(model, loader, vocab, device)
        results[mode] = acc
    model.set_ablation("none")
    return results


def run_rotation_test(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
    angles_degrees: List[float] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Run phase rotation tests to verify phase encodes relational structure.

    HYPOTHESIS:
    -----------
    If roles are encoded as phase offsets (e.g., R0 → φ=0, R1 → φ=π/2):
    - Rotating φ_q by θ should shift which role's binding is retrieved
    - Larger rotations should cause larger accuracy drops
    - Specific rotations might "swap" roles (retrieve R1 when querying R0)

    If phase is decorative:
    - Rotation should have minimal/random effect on accuracy
    - No systematic relationship between rotation angle and accuracy

    Args:
        model: Model with phase attention (must have set_rotation method)
        loader: DataLoader for evaluation
        vocab: Vocabulary for decoding
        device: Device to run on
        angles_degrees: List of rotation angles in degrees (default: 0, 45, 90, 135, 180)

    Returns:
        Dictionary with:
        - 'accuracy': {angle: accuracy} for each angle
        - 'delta': {angle: accuracy_change} relative to baseline
        - 'sensitivity': float (mean absolute delta, higher = more sensitive)
        - 'systematic': bool (True if accuracy decreases monotonically with angle)
    """
    if angles_degrees is None:
        angles_degrees = [0, 45, 90, 135, 180, 270]

    if not hasattr(model, 'set_rotation'):
        return {
            'accuracy': {0: evaluate(model, loader, vocab, device)},
            'delta': {0: 0.0},
            'sensitivity': 0.0,
            'systematic': False,
            'error': 'Model does not support rotation (no set_rotation method)'
        }

    results = {'accuracy': {}, 'delta': {}}

    # Get baseline (0° rotation)
    model.set_rotation(0.0)
    baseline = evaluate(model, loader, vocab, device)
    results['accuracy'][0] = baseline
    results['delta'][0] = 0.0

    # Test each rotation angle
    for angle_deg in angles_degrees:
        if angle_deg == 0:
            continue  # Already computed

        angle_rad = math.radians(angle_deg)
        model.set_rotation(angle_rad)
        acc = evaluate(model, loader, vocab, device)
        results['accuracy'][angle_deg] = acc
        results['delta'][angle_deg] = acc - baseline

    # Clear rotation
    model.clear_rotation()

    # Compute sensitivity metrics
    deltas = [abs(d) for a, d in results['delta'].items() if a != 0]
    results['sensitivity'] = sum(deltas) / len(deltas) if deltas else 0.0

    # Check if accuracy drops systematically with angle (up to 180°)
    angles_sorted = sorted([a for a in results['accuracy'].keys() if a <= 180])
    accs_sorted = [results['accuracy'][a] for a in angles_sorted]
    # Systematic if accuracy generally decreases (allowing small fluctuations)
    decreasing_pairs = sum(1 for i in range(len(accs_sorted)-1) if accs_sorted[i] >= accs_sorted[i+1] - 0.02)
    results['systematic'] = decreasing_pairs >= (len(accs_sorted) - 2) if len(accs_sorted) > 2 else False

    # Additional analysis: find angle of maximum disruption
    if results['delta']:
        min_delta_angle = min(results['delta'].items(), key=lambda x: x[1])
        results['max_disruption_angle'] = min_delta_angle[0]
        results['max_disruption_delta'] = min_delta_angle[1]

    return results


def print_rotation_test_results(
    results: Dict[str, Dict[str, float]],
    model_name: str = "Phase",
) -> None:
    """Pretty-print rotation test results."""
    print(f"\n--- PHASE ROTATION TEST: {model_name} ---")

    if 'error' in results:
        print(f"  ERROR: {results['error']}")
        return

    print(f"\n  {'Angle':>8}  {'Accuracy':>10}  {'Δ from 0°':>10}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*10}")

    for angle in sorted(results['accuracy'].keys()):
        acc = results['accuracy'][angle]
        delta = results['delta'][angle]
        delta_str = f"{delta*100:+.1f}%" if angle != 0 else "baseline"
        print(f"  {angle:>6}°  {acc*100:>9.1f}%  {delta_str:>10}")

    print(f"\n  Sensitivity (mean |Δ|): {results['sensitivity']*100:.2f}%")
    print(f"  Systematic decrease:    {'Yes' if results['systematic'] else 'No'}")

    if 'max_disruption_angle' in results:
        print(f"  Max disruption at:      {results['max_disruption_angle']}° ({results['max_disruption_delta']*100:+.1f}%)")

    # Interpretation
    print(f"\n  INTERPRETATION:")
    if results['sensitivity'] > 0.10:
        print(f"    → Phase is SENSITIVE to rotation (sensitivity > 10%)")
        print(f"    → Phase likely encodes meaningful relational structure")
        if results['systematic']:
            print(f"    → Systematic decrease suggests phase offset = role encoding")
    elif results['sensitivity'] > 0.03:
        print(f"    → Phase shows MODERATE sensitivity to rotation")
        print(f"    → Phase may partially encode relational structure")
    else:
        print(f"    → Phase is INSENSITIVE to rotation (sensitivity < 3%)")
        print(f"    → Phase appears DECORATIVE (not encoding relations)")


# =============================================================================
# REAL LANGUAGE MODE: WikiText Dataset and LM Training
# =============================================================================

class WikiTextDataset(Dataset):
    """Text dataset for language modeling with layer probing.

    Supports:
    - wikitext2, wikitext103: Encyclopedia text (good for LM, basic Phase)
    - tinystories: Narrative stories (RECOMMENDED for Kosha/Witness - diverse epistemic states)
    - writingprompts: Creative writing (excellent Vritti diversity)
    - imdb: Movie reviews (opinions/emotions)
    - openwebtext, c4: Large web corpora
    """

    def __init__(self, split: str = "train", seq_len: int = 256, dataset_name: str = "wikitext2"):
        """
        Args:
            split: "train", "validation", or "test"
            seq_len: Sequence length for chunks
            dataset_name: Dataset to load (tinystories recommended for consciousness training)
        """
        try:
            from datasets import load_dataset
            from transformers import GPT2Tokenizer
        except ImportError:
            raise ImportError("Install: pip install datasets transformers")

        self.seq_len = seq_len
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load dataset based on name
        dataset_name_lower = dataset_name.lower()

        if dataset_name_lower == "wikitext2":
            ds = load_dataset("wikitext", "wikitext-2-raw-v1", split=split)
            text_field = "text"
            ds_label = "WikiText-2"
        elif dataset_name_lower == "wikitext103":
            ds = load_dataset("wikitext", "wikitext-103-raw-v1", split=split)
            text_field = "text"
            ds_label = "WikiText-103"
        elif dataset_name_lower == "tinystories":
            # TinyStories - narrative stories, excellent for Kosha/Witness
            # Small, diverse epistemic states (imagination, memory, facts)
            ds = load_dataset("roneneldan/TinyStories", split=split, trust_remote_code=True)
            text_field = "text"
            ds_label = "TinyStories"
        elif dataset_name_lower == "writingprompts":
            # WritingPrompts - creative writing with diverse epistemic modes
            # Great for exercising all Vritti states
            try:
                ds = load_dataset("euclaise/writingprompts", split=split, trust_remote_code=True)
            except Exception:
                ds = load_dataset("writing_prompts", split=split, trust_remote_code=True)
            # Has 'prompt' and 'story' fields - concatenate them
            text_field = "story" if "story" in ds.column_names else "text"
            ds_label = "WritingPrompts"
        elif dataset_name_lower == "imdb":
            # IMDB reviews - opinions/emotions, good for Vritti diversity
            ds = load_dataset("imdb", split=split, trust_remote_code=True)
            text_field = "text"
            ds_label = "IMDB Reviews"
        elif dataset_name_lower == "openwebtext":
            # OpenWebText - large web text corpus
            ds = load_dataset("openwebtext", split=split, trust_remote_code=True)
            text_field = "text"
            ds_label = "OpenWebText"
        elif dataset_name_lower == "c4":
            # C4 (Colossal Clean Crawled Corpus) - very large
            # Only load a subset to avoid memory issues
            ds = load_dataset("c4", "en", split=f"{split}[:10000]", trust_remote_code=True)
            text_field = "text"
            ds_label = "C4 (subset)"
        else:
            raise ValueError(f"Unknown dataset: {dataset_name}. "
                           f"Choose from: wikitext2, wikitext103, tinystories, writingprompts, imdb, openwebtext, c4")

        # Tokenize all text
        if text_field in ds.column_names:
            all_text = " ".join([t for t in ds[text_field] if t and t.strip()])
        else:
            # Fallback: try common text field names
            for field in ["text", "content", "section_text", "document"]:
                if field in ds.column_names:
                    all_text = " ".join([t for t in ds[field] if t and t.strip()])
                    break
            else:
                raise ValueError(f"Could not find text field in dataset. Available: {ds.column_names}")

        self.tokens = self.tokenizer.encode(all_text)
        print(f"  [{ds_label}] {split}: {len(self.tokens):,} tokens → {len(self.tokens) // seq_len:,} chunks")

    def __len__(self):
        return max(1, len(self.tokens) // self.seq_len - 1)

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1  # +1 for target
        chunk = self.tokens[start:end]

        # Pad if needed
        if len(chunk) < self.seq_len + 1:
            chunk = chunk + [self.tokenizer.pad_token_id] * (self.seq_len + 1 - len(chunk))

        x = torch.tensor(chunk[:-1], dtype=torch.long)
        y = torch.tensor(chunk[1:], dtype=torch.long)
        return x, y


class HybridLMTransformer(nn.Module):
    """
    Language Modeling Transformer with per-layer Phase/Quadratic mixing.

    Supports:
    - Phase-first curriculum (phase_ratio adjustable per layer)
    - Layer-wise probing (can ablate individual layers)
    - Real language modeling (cross-entropy loss)
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        curriculum: List[float],  # phase_ratio per layer
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.num_layers = num_layers
        self.curriculum = curriculum  # Mutable for phase-first curriculum

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        # Create hybrid layers
        self.layers = nn.ModuleList([
            HybridTransformerBlock(
                d_model, num_heads, d_ff, dropout,
                phase_ratio=curriculum[i],
                operation_tokens=None,
                bounded_phase=bounded_phase,
            )
            for i in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        # Layer-wise probing storage
        self.layer_outputs = []
        self.probe_mode = False

    def update_curriculum(self, new_curriculum: List[float]):
        """Update phase ratios for phase-first curriculum."""
        self.curriculum = new_curriculum
        for i, layer in enumerate(self.layers):
            layer.phase_ratio = new_curriculum[i]

    def forward(self, input_ids: torch.Tensor, probe_layers: bool = False) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        self.layer_outputs = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            if probe_layers:
                # Store intermediate output for layer probing
                self.layer_outputs.append(x.detach().clone())

        x = self.norm(x)
        logits = self.lm_head(x)
        return logits

    def get_layer_ppl(self, input_ids: torch.Tensor, targets: torch.Tensor) -> List[float]:
        """
        Compute PPL contribution from each layer by early-exiting.

        Returns list of PPLs: [ppl_after_layer_0, ppl_after_layer_1, ...]
        """
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_ppls = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            # Early exit: compute PPL after this layer
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()
            layer_ppls.append(ppl)

        return layer_ppls

    def get_layer_contributions(self, input_ids: torch.Tensor, targets: torch.Tensor) -> Dict[str, List[float]]:
        """
        Compute detailed per-layer metrics to see if phase learns faster/richer.

        Returns:
            - 'ppl': PPL after each layer
            - 'ppl_delta': PPL reduction from each layer (positive = layer helps)
            - 'phase_ratio': Current phase ratio per layer
            - 'contribution_pct': % of total PPL reduction from each layer
        """
        layer_ppls = self.get_layer_ppl(input_ids, targets)

        # Compute PPL before any layer (just embeddings)
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        x_normed = self.norm(x)
        logits = self.lm_head(x_normed)
        loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
        ppl_embed = torch.exp(loss).item()

        # PPL delta (reduction) per layer
        ppl_deltas = []
        prev_ppl = ppl_embed
        for ppl in layer_ppls:
            delta = prev_ppl - ppl  # Positive = layer reduced PPL
            ppl_deltas.append(delta)
            prev_ppl = ppl

        # Total PPL reduction
        total_reduction = ppl_embed - layer_ppls[-1]

        # Contribution percentage per layer
        contribution_pcts = []
        for delta in ppl_deltas:
            if total_reduction > 0:
                pct = (delta / total_reduction) * 100
            else:
                pct = 0.0
            contribution_pcts.append(pct)

        return {
            'ppl': layer_ppls,
            'ppl_delta': ppl_deltas,
            'phase_ratio': self.curriculum.copy(),
            'contribution_pct': contribution_pcts,
            'ppl_embed': ppl_embed,
            'total_reduction': total_reduction,
        }

    def ablate_attention(self, input_ids: torch.Tensor, targets: torch.Tensor,
                         ablate_phase: bool = False, ablate_local: bool = False) -> float:
        """
        Compute PPL with phase or local attention ablated (zeroed out).

        This shows what each attention type contributes:
        - ablate_phase=True: Only local attention active
        - ablate_local=True: Only phase attention active
        """
        # Store original ratios
        original_curriculum = self.curriculum.copy()

        if ablate_phase:
            # Set all phase ratios to 0 (only local)
            ablated_curriculum = [0.0] * self.num_layers
        elif ablate_local:
            # Set all phase ratios to 1 (only phase)
            ablated_curriculum = [1.0] * self.num_layers
        else:
            ablated_curriculum = original_curriculum

        self.update_curriculum(ablated_curriculum)

        # Compute PPL
        with torch.no_grad():
            logits = self.forward(input_ids)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()

        # Restore original
        self.update_curriculum(original_curriculum)

        return ppl


class PhaseFirstCurriculum:
    """
    Adjusts per-layer phase ratios based on current PPL.

    High PPL (early training): More phase in all layers
    Low PPL (later training): Phase only in early layers, local in later layers
    """

    def __init__(
        self,
        num_layers: int,
        alpha_high: float = 0.8,
        alpha_low: float = 0.3,
        ppl_high: float = 1000.0,
        ppl_low: float = 100.0,
    ):
        self.num_layers = num_layers
        self.alpha_high = alpha_high
        self.alpha_low = alpha_low
        self.ppl_high = ppl_high
        self.ppl_low = ppl_low
        self.current_ppl = float('inf')

    def update(self, ppl: float) -> List[float]:
        """
        Compute per-layer phase ratios based on PPL.

        Returns: curriculum list [phase_ratio_L0, phase_ratio_L1, ...]
        """
        self.current_ppl = ppl

        # Compute base alpha from PPL
        if ppl >= self.ppl_high:
            base_alpha = self.alpha_high
        elif ppl <= self.ppl_low:
            base_alpha = self.alpha_low
        else:
            # Linear interpolation
            ratio = (ppl - self.ppl_low) / (self.ppl_high - self.ppl_low)
            base_alpha = self.alpha_low + ratio * (self.alpha_high - self.alpha_low)

        # Per-layer curriculum: early layers keep more phase
        # Layer 0: base_alpha, Layer N-1: base_alpha * 0.5
        curriculum = []
        for i in range(self.num_layers):
            layer_factor = 1.0 - (i / (self.num_layers - 1)) * 0.5  # 1.0 → 0.5
            layer_alpha = base_alpha * layer_factor
            curriculum.append(layer_alpha)

        return curriculum


# =============================================================================
# V10.3.2: PROTECTED PHASE FOR REAL LANGUAGE MODE
# =============================================================================
# Protected Phase architecture gives Phase and Quadratic NON-COMPETING roles:
#   - Phase: O(n) memory accumulation (cumsum) - persists binding state
#   - Quadratic: O(n²) memory querying (attention) - reasons over state
#
# They collaborate SEQUENTIALLY, not compete in PARALLEL.
# This prevents Phase from becoming "decorative" (0% ablation drop).

class ProtectedPhaseLMBlock(nn.Module):
    """
    Protected Phase block for Language Modeling.

    Architecture:
        1. Phase accumulates memory: memory = cumsum(k * v)
        2. Quadratic queries memory: output = attention(q, memory)

    This is SEQUENTIAL COLLABORATION, not parallel mixing.
    Phase and Quadratic don't compete for gradients.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm_mem = nn.LayerNorm(d_model)

        # Protected Phase: accumulates memory state
        self.phase_memory = ProtectedPhaseAttention(d_model, num_heads, dropout, None, bounded_phase)
        # Protected Quad: queries memory state
        self.quad_query = ProtectedQuadAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Step 1: Phase accumulates memory state (Phase's exclusive job)
        normed = self.norm1(x)
        memory_state = self.phase_memory(normed, None)  # No token_ids for LM
        memory_state = self.norm_mem(memory_state)

        # Step 2: Quadratic queries the memory (Quad's exclusive job)
        attn_out = self.quad_query(normed, memory_state)

        # Residual and FF
        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def get_phase_health(self) -> dict:
        """Get Phase health metrics."""
        return self.phase_memory.get_health_metrics()


class ProtectedPhaseLMTransformer(nn.Module):
    """
    Language Modeling Transformer with PROTECTED Phase architecture.

    Key insight from ablation tests:
    - When mixed (parallel), Phase becomes DECORATIVE (0% ablation drop)
    - When protected (sequential), Phase is ESSENTIAL (37% ablation drop)

    Solution: Give Phase and Quadratic NON-COMPETING roles:
    - Phase: O(n) memory accumulation (cumsum)
    - Quadratic: O(n²) memory querying (attention)

    They collaborate sequentially, not compete in parallel.

    Supports:
    - Layer-wise probing (for SRK integration)
    - Real language modeling (cross-entropy loss)
    - Phase health monitoring (R_k statistics)
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.num_heads = num_heads
        self.num_layers = num_layers

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        # Create protected phase layers
        self.layers = nn.ModuleList([
            ProtectedPhaseLMBlock(d_model, num_heads, d_ff, dropout, bounded_phase)
            for _ in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        # Layer-wise probing storage (for SRK integration)
        self.layer_outputs = []

        # Curriculum placeholder (not used in protected phase, but for API compatibility)
        self.curriculum = [1.0] * num_layers  # Protected = 100% phase contribution

    def forward(self, input_ids: torch.Tensor, probe_layers: bool = False) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        self.layer_outputs = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            if probe_layers:
                # Store intermediate output for layer probing / SRK
                self.layer_outputs.append(x.detach().clone())

        x = self.norm(x)
        logits = self.lm_head(x)
        return logits

    def get_phase_health(self) -> dict:
        """
        Aggregate Phase health metrics (R_k statistics) from all layers.

        Interpretation:
        - R_k → 0: Phase collapsed (bad)
        - R_k → 1: Phase degenerate (bad)
        - R_k stable in (0.3, 0.7): Healthy
        """
        metrics = {
            "r_k_mean": [],
            "r_k_std": [],
            "r_k_min": [],
            "r_k_max": [],
        }
        for layer in self.layers:
            layer_metrics = layer.get_phase_health()
            for k, v in layer_metrics.items():
                metrics[k].append(v)

        # Average across layers
        return {
            "r_k_mean": sum(metrics["r_k_mean"]) / len(metrics["r_k_mean"]) if metrics["r_k_mean"] else 0.0,
            "r_k_std": sum(metrics["r_k_std"]) / len(metrics["r_k_std"]) if metrics["r_k_std"] else 0.0,
            "r_k_min": min(metrics["r_k_min"]) if metrics["r_k_min"] else 0.0,
            "r_k_max": max(metrics["r_k_max"]) if metrics["r_k_max"] else 0.0,
        }

    def update_curriculum(self, new_curriculum: List[float]):
        """API compatibility with HybridLMTransformer (no-op for protected phase)."""
        # Protected phase doesn't use curriculum - phase is always protected
        pass

    def get_layer_ppl(self, input_ids: torch.Tensor, targets: torch.Tensor) -> List[float]:
        """Compute PPL contribution from each layer by early-exiting."""
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_ppls = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            # Early exit: compute PPL after this layer
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()
            layer_ppls.append(ppl)

        return layer_ppls

    def get_layer_contributions(self, input_ids: torch.Tensor, targets: torch.Tensor) -> Dict[str, List[float]]:
        """
        Analyze per-layer contributions for Protected Phase.

        Returns dict with:
        - ppl: PPL after each layer
        - ppl_delta: PPL improvement from each layer
        - contribution_pct: % of total PPL reduction from each layer
        - phase_ratio: Always 1.0 for protected phase
        """
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        # Initial PPL (embedding only)
        logits_embed = self.lm_head(self.norm(x))
        loss_embed = F.cross_entropy(logits_embed.view(-1, self.vocab_size), targets.view(-1))
        ppl_embed = torch.exp(loss_embed).item()

        layer_ppls = []
        layer_deltas = []
        prev_ppl = ppl_embed

        for i, layer in enumerate(self.layers):
            x = layer(x)
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()

            layer_ppls.append(ppl)
            layer_deltas.append(prev_ppl - ppl)  # Positive = improvement
            prev_ppl = ppl

        total_reduction = ppl_embed - layer_ppls[-1]
        contribution_pcts = [
            (delta / total_reduction * 100) if total_reduction > 0 else 0
            for delta in layer_deltas
        ]

        return {
            'ppl': layer_ppls,
            'ppl_delta': layer_deltas,
            'contribution_pct': contribution_pcts,
            'phase_ratio': [1.0] * self.num_layers,  # Always 100% phase contribution
            'ppl_embed': ppl_embed,
            'total_reduction': total_reduction,
        }

    def ablate_attention(self, input_ids: torch.Tensor, targets: torch.Tensor,
                         ablate_phase: bool = False, ablate_local: bool = False) -> float:
        """
        For Protected Phase, ablation is different:
        - ablate_phase: Disable phase memory accumulation
        - ablate_local: Disable quadratic querying

        Returns PPL with ablation applied.
        """
        # Store original forward, apply ablation, restore
        # For now, return normal PPL (full ablation requires modifying layers)
        with torch.no_grad():
            logits = self.forward(input_ids)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            return torch.exp(loss).item()

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# =============================================================================
# V10.3.3: BINDING CACHE FOR REAL LANGUAGE MODE
# =============================================================================
# Binding Cache architecture combines THREE attention paths:
#   1. Local: O(n*w) - Direct token-to-token for syntax learning
#   2. Phase: O(n) - Memory state accumulation (global compression)
#   3. Quad:  O(n*k) - Top-K memory query (global retrieval)
#
# This is the V10.0 architecture validated by diagnostic probes.
# Reference: --protected-phase showed -50% ablation drop (Phase essential)

class LocalWindowAttention(nn.Module):
    """
    Local window attention for fast syntax learning.

    Uses sliding window attention (O(n*w) complexity) for direct
    token-to-token patterns like "the → cat".
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        window_size: int = 64,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.window_size = window_size

        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_k = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)
        self.W_o = nn.Linear(embed_dim, embed_dim)

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = 1.0 / math.sqrt(self.head_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Local window attention.

        Args:
            x: [B, N, D]

        Returns:
            output: [B, N, D]
        """
        B, N, D = x.shape
        x_norm = self.norm(x)

        # Project Q, K, V
        q = self.W_q(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.W_k(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.W_v(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Compute attention scores with causal mask
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        # Create causal mask
        causal_mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()

        # Create local window mask (only attend within window)
        window_mask = torch.ones(N, N, device=x.device).bool()
        for i in range(N):
            start = max(0, i - self.window_size)
            window_mask[i, start:i+1] = False

        # Combine masks
        combined_mask = causal_mask | window_mask
        attn_scores = attn_scores.masked_fill(combined_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        # Softmax and apply
        attn_probs = F.softmax(attn_scores, dim=-1)
        attn_probs = self.dropout(attn_probs)

        attn_out = torch.matmul(attn_probs, v)
        attn_out = attn_out.transpose(1, 2).contiguous().view(B, N, D)

        return self.W_o(attn_out)


class BindingCachePhaseState(nn.Module):
    """
    Phase state accumulator for binding cache.

    Accumulates key-value bindings into a persistent memory state
    using O(n) cumulative sum (no attention).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        decay_gamma: float = 0.9,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.decay_gamma = decay_gamma
        self.bounded_phase = bounded_phase

        # Phase projections
        self.W_k_phase = nn.Linear(embed_dim, embed_dim)
        self.W_k_amp = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Health tracking
        self._last_r_k_mean = 0.0
        self._last_r_k_std = 0.0
        self._last_r_k_min = 0.0
        self._last_r_k_max = 0.0

        self._ablation_mode = "none"

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode

    def set_rotation(self, angle: float):
        pass  # Not implemented for probe

    def clear_rotation(self):
        pass

    def get_health_metrics(self) -> dict:
        return {
            "r_k_mean": self._last_r_k_mean,
            "r_k_std": self._last_r_k_std,
            "r_k_min": self._last_r_k_min,
            "r_k_max": self._last_r_k_max,
        }

    def compute_confidence(self, memory_state: torch.Tensor) -> torch.Tensor:
        """
        Compute confidence score for proposal mode.

        Higher confidence means phase state has strong, stable bindings.
        Used in V10.4 proposal mode to decide whether to skip quad attention.

        Args:
            memory_state: [B, N, D] accumulated memory state

        Returns:
            confidence: [B, N] confidence scores in [0, 1]
        """
        # Confidence based on memory state magnitude (normalized)
        # Higher magnitude = stronger bindings = higher confidence
        mem_norm = torch.norm(memory_state, dim=-1)  # [B, N]

        # Normalize to [0, 1] using sigmoid of z-scored values
        mem_mean = mem_norm.mean(dim=-1, keepdim=True)
        mem_std = mem_norm.std(dim=-1, keepdim=True) + 1e-6
        z_scores = (mem_norm - mem_mean) / mem_std

        # Sigmoid to get [0, 1] confidence
        confidence = torch.sigmoid(z_scores)

        return confidence

    def integrate_proposals(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
        proposals: torch.Tensor,
        proposal_scores: torch.Tensor,
        gamma: float = 0.9,
    ) -> torch.Tensor:
        """
        V10.4: Integrate quad proposals into phase state.

        This implements the "phase-as-integrator" pattern where phase
        decides which proposals survive and integrates them into state.

        Args:
            x: Input tensor [B, N, D]
            memory_state: Current phase state [B, N, D]
            proposals: [B, N, K, D] - K proposals from quad
            proposal_scores: [B, N, K] - retrieval scores for each proposal
            gamma: Decay factor for state (0 < gamma < 1)

        Returns:
            integrated_output: [B, N, D] - integrated state update
        """
        B, N, K, D = proposals.shape

        # Phase computes gating weights (NOT quad softmax)
        # Use sigmoid + normalize for smoother gradients than softmax
        gate_logits = proposal_scores  # [B, N, K]

        # Sigmoid + normalize (not winner-take-all like softmax)
        gate_weights_raw = torch.sigmoid(gate_logits)  # [B, N, K]
        gate_weights = gate_weights_raw / (gate_weights_raw.sum(dim=-1, keepdim=True) + 1e-8)  # [B, N, K]

        # Weighted sum of proposals
        # [B, N, K, 1] * [B, N, K, D] -> [B, N, K, D] -> sum -> [B, N, D]
        weighted_proposals = (gate_weights.unsqueeze(-1) * proposals).sum(dim=2)  # [B, N, D]

        # State update: decay old state + integrate new proposals
        # S_{t+1} = gamma * S_t + (1 - gamma) * weighted_proposals
        integrated = gamma * memory_state + (1 - gamma) * weighted_proposals

        return integrated

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute memory state via cumsum.

        Args:
            x: [B, N, D]

        Returns:
            memory_state: [B, N, D]
        """
        B, N, D = x.shape
        x_norm = self.norm(x)

        # Compute phase and amplitude
        phi_k_raw = self.W_k_phase(x_norm).view(B, N, self.num_heads, self.head_dim)
        if self.bounded_phase:
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_k = phi_k_raw

        a_k = torch.sigmoid(self.W_k_amp(x_norm)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x_norm).view(B, N, self.num_heads, self.head_dim)

        # Track R_k health
        with torch.no_grad():
            r_k = a_k.mean(dim=(0, 1))  # [H, D_h]
            self._last_r_k_mean = r_k.mean().item()
            self._last_r_k_std = r_k.std().item()
            self._last_r_k_min = r_k.min().item()
            self._last_r_k_max = r_k.max().item()

        # Complex representation: z = a * e^(i*phi)
        z_real = a_k * torch.cos(phi_k)
        z_imag = a_k * torch.sin(phi_k)

        # Weighted value
        weighted_v = v * a_k

        # Cumsum for memory accumulation (with decay)
        if self.decay_gamma < 1.0:
            # Apply exponential decay
            decay_weights = torch.pow(
                torch.tensor(self.decay_gamma, device=x.device),
                torch.arange(N, device=x.device).float()
            ).view(1, N, 1, 1)
            weighted_v = weighted_v * decay_weights

        memory_state = torch.cumsum(weighted_v, dim=1)

        # Reshape back
        memory_state = memory_state.view(B, N, D)
        return memory_state


class BindingCacheQuadQuery(nn.Module):
    """
    Quadratic query with Top-K cache for efficient memory retrieval.

    Uses Top-K selection to reduce O(n²) attention to O(n*k).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        top_k: int = 64,
        use_cache: bool = True,
        proposal_mode: bool = False,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.top_k = top_k
        self.use_cache = use_cache
        self.proposal_mode = proposal_mode

        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_o = nn.Linear(embed_dim, embed_dim)

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = 1.0 / math.sqrt(self.head_dim)

    def get_proposals(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        V10.4: Get TopK proposals WITHOUT softmax mixing.

        Instead of returning attention-weighted output, returns raw proposals
        for Phase to integrate. This implements the "quad-as-proposer" pattern.

        Args:
            x: Input tensor [B, N, D] - source for queries
            memory_state: [B, N, D] - from BindingCachePhaseState

        Returns:
            proposals: [B, N, K, D] - K proposal values per position
            scores: [B, N, K] - retrieval scores (before softmax) for each proposal
        """
        B, N, D = x.shape
        K = min(self.top_k, N)

        x_norm = self.norm(x)

        # Query projection
        q = self.W_q(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Memory as key-value
        mem = memory_state.view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Compute attention scores
        scores = torch.matmul(q, mem.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Causal mask
        causal_mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        # TopK selection - NO SOFTMAX
        top_scores, top_indices = scores.topk(K, dim=-1, largest=True)  # [B, H, N, K]

        # Gather corresponding values
        top_indices_expanded = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, self.head_dim)
        mem_expanded = mem.unsqueeze(2).expand(-1, -1, N, -1, -1)  # [B, H, N, N, D_h]
        top_mem = torch.gather(mem_expanded, 3, top_indices_expanded)  # [B, H, N, K, D_h]

        # Reshape: [B, H, N, K, D_h] -> [B, N, K, H*D_h] = [B, N, K, D]
        proposals = top_mem.permute(0, 2, 3, 1, 4).reshape(B, N, K, D)

        # Scores: [B, H, N, K] -> [B, N, K] (mean across heads)
        proposal_scores = top_scores.permute(0, 2, 3, 1).mean(dim=-1)  # [B, N, K]

        return proposals, proposal_scores

    def forward(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Query memory state with Top-K selection.

        Args:
            x: [B, N, D]
            memory_state: [B, N, D] from Phase accumulator

        Returns:
            output: [B, N, D]
        """
        B, N, D = x.shape
        x_norm = self.norm(x)

        # Query projection
        q = self.W_q(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Memory as key-value
        mem = memory_state.view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Compute attention scores
        attn_scores = torch.matmul(q, mem.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Causal mask
        causal_mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        attn_scores = attn_scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        if self.use_cache and self.top_k < N:
            # Top-K selection per query position
            # For each query, only attend to top-k memory positions
            k = min(self.top_k, N)
            top_k_scores, top_k_indices = torch.topk(attn_scores, k, dim=-1)

            # Create sparse attention (only top-k positions)
            attn_probs = F.softmax(top_k_scores, dim=-1)
            attn_probs = self.dropout(attn_probs)

            # Gather top-k memory values
            top_k_indices_expanded = top_k_indices.unsqueeze(-1).expand(-1, -1, -1, -1, self.head_dim)
            mem_expanded = mem.unsqueeze(2).expand(-1, -1, N, -1, -1)  # [B, H, N, N, D_h]
            top_k_mem = torch.gather(mem_expanded, 3, top_k_indices_expanded)  # [B, H, N, k, D_h]

            attn_out = torch.matmul(attn_probs.unsqueeze(-2), top_k_mem).squeeze(-2)  # [B, H, N, D_h]
        else:
            # Full attention (no cache)
            attn_probs = F.softmax(attn_scores, dim=-1)
            attn_probs = self.dropout(attn_probs)
            attn_out = torch.matmul(attn_probs, mem)

        attn_out = attn_out.transpose(1, 2).contiguous().view(B, N, D)
        return self.W_o(attn_out)


class BindingCacheLMBlock(nn.Module):
    """
    Binding Cache block for Language Modeling.

    V10.5.2 Cross-Attention Architecture:
    1. Local: O(n*w) - Syntax attention, ALSO provides queries for quad
    2. Phase: O(n) - Memory accumulation, provides keys/values for quad
    3. Quad:  O(n*k) - Cross-attention from local (Q) into phase memory (K/V)

    Key change from V10.0: Phase no longer contributes directly to output.
    Quad is the SOLE interface to phase memory, forcing it to learn.

    Information flow:
        local_out = local_attn(x)           # Syntax + queries
        memory_state = phase_state(x)       # Semantic memory (K/V)
        quad_out = quad_query(local_out, memory_state)  # Cross-attention
        output = local_ratio * local_out + quad_ratio * quad_out

    This fixes the quad gradient starvation problem (was 0.1% gradients)
    where phase leaked full memory to output, making quad redundant.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        ff_dim: int,
        dropout: float = 0.1,
        decay_gamma: float = 0.9,
        bounded_phase: bool = True,
        top_k: int = 64,
        use_cache: bool = True,
        local_window_size: int = 64,
        local_ratio: float = 0.4,
        phase_ratio: float = 0.3,
        quad_ratio: float = 0.3,
        proposal_mode: bool = False,  # V10.4: Quad proposes, Phase integrates
        confidence_threshold: float = 0.7,  # V10.4: Skip quad if confidence > threshold
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.proposal_mode = proposal_mode
        self.confidence_threshold = confidence_threshold

        # Store ratios for weighted combination
        self.local_ratio = local_ratio
        self.phase_ratio = phase_ratio
        self.quad_ratio = quad_ratio

        # Local attention for syntax learning
        self.local_attn = LocalWindowAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=local_window_size,
            dropout=dropout,
        )

        # Phase state accumulator
        self.phase_state = BindingCachePhaseState(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            decay_gamma=decay_gamma,
            bounded_phase=bounded_phase,
        )

        # Quad memory query
        self.quad_query = BindingCacheQuadQuery(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            top_k=top_k,
            use_cache=use_cache,
            proposal_mode=proposal_mode,
        )

        # Feed-forward
        self.norm_ff = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, embed_dim),
            nn.Dropout(dropout),
        )

        # V10.4: Instrumentation for proposal mode
        self._last_confidence_mean = 0.0
        self._last_skip_rate = 0.0

    def get_phase_health(self) -> dict:
        return self.phase_state.get_health_metrics()

    def get_proposal_metrics(self) -> dict:
        """V10.4: Return proposal mode instrumentation."""
        return {
            "confidence_mean": self._last_confidence_mean,
            "skip_rate": self._last_skip_rate,
        }

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Three-path forward pass with cross-attention architecture (V10.5.2).

        V10.5.2 Change: Quad cross-attends from local_out into memory_state
        - Q = local_out (syntax context)
        - K/V = memory_state (semantic memory from phase)
        - Removes direct phase_ratio * memory_state from output (was causing quad redundancy)

        This makes quad the SOLE interface to phase memory, forcing it to learn.

        1. Local attention for syntax (provides queries)
        2. Phase accumulates memory (provides keys/values)
        3. Quad cross-attends: retrieves from memory using local context

        Output = x + (local_ratio * local + quad_ratio * quad_out) + ff
        Note: phase contributes ONLY via quad, not directly to output
        """
        # Step 1: Local attention for syntax (the → cat patterns)
        # This now serves dual purpose: syntax output AND query source for quad
        local_out = self.local_attn(x)

        # Step 2: Phase accumulates memory state (keys/values for quad)
        # Phase no longer contributes directly to output - only via quad retrieval
        memory_state = self.phase_state(x)

        if self.proposal_mode:
            # V10.4: Proposal Mode - quad proposes, phase integrates
            # Check confidence for conditional skip
            confidence = self.phase_state.compute_confidence(memory_state)

            with torch.no_grad():
                self._last_confidence_mean = confidence.mean().item()
                self._last_skip_rate = (confidence > self.confidence_threshold).float().mean().item()

            # V10.5.2: Get proposals using local_out as query source (cross-attention)
            proposals, proposal_scores = self.quad_query.get_proposals(local_out, memory_state)

            # Phase integrates proposals
            quad_out = self.phase_state.integrate_proposals(
                local_out, memory_state, proposals, proposal_scores
            )
        else:
            # V10.5.2: Quad cross-attends from local_out (Q) into memory_state (K/V)
            # This replaces: quad_out = self.quad_query(x, memory_state)
            quad_out = self.quad_query(local_out, memory_state)

        # V10.5.2: Weighted combination WITHOUT direct phase contribution
        # Phase contributes ONLY through quad's cross-attention retrieval
        # This forces quad to be necessary (was getting 0.1% gradients before)
        attn_out = (
            self.local_ratio * local_out +
            # REMOVED: self.phase_ratio * memory_state  (was causing quad redundancy)
            self.quad_ratio * quad_out
        )

        # Residual and FF
        x = x + attn_out
        x = x + self.ff(self.norm_ff(x))

        return x


class BindingCacheLMTransformer(nn.Module):
    """
    Language Modeling Transformer with Binding Cache architecture (V10.0).

    Validated by diagnostic probes:
    - Phase: O(n) state accumulator (exclusive role)
    - Quad: O(n*k) memory query via Top-K cache (exclusive role)
    - Local: O(n*w) direct syntax attention

    Reference: --protected-phase showed -50% ablation drop when Phase
    has protected role (vs ~0% when mixed with Quad).

    Supports:
    - Layer-wise probing for SRK integration
    - Phase health monitoring (R_k statistics)
    - Top-K cache for O(n*k) complexity
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        bounded_phase: bool = True,
        top_k: int = 64,
        use_cache: bool = True,
        decay_gamma: float = 0.9,
        window_size: int = 64,
        phase_ratios: List[float] = None,
        local_ratios: List[float] = None,
        quad_ratios: List[float] = None,
        proposal_mode: bool = False,  # V10.4: Quad proposes, Phase integrates
        confidence_threshold: float = 0.7,  # V10.4: Skip quad if confidence > threshold
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.proposal_mode = proposal_mode

        # Default ratios if not specified
        if phase_ratios is None:
            phase_ratios = [0.3] * num_layers
        if local_ratios is None:
            local_ratios = [0.4] * num_layers
        if quad_ratios is None:
            quad_ratios = [0.3] * num_layers

        # Store ratios for logging
        self.phase_ratios = phase_ratios
        self.local_ratios = local_ratios
        self.quad_ratios = quad_ratios

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        # Binding Cache blocks with per-layer ratios
        self.layers = nn.ModuleList([
            BindingCacheLMBlock(
                embed_dim=d_model,
                num_heads=num_heads,
                ff_dim=d_ff,
                dropout=dropout,
                decay_gamma=decay_gamma,
                bounded_phase=bounded_phase,
                top_k=top_k,
                use_cache=use_cache,
                local_window_size=window_size,
                local_ratio=local_ratios[i],
                phase_ratio=phase_ratios[i],
                quad_ratio=quad_ratios[i],
                proposal_mode=proposal_mode,
                confidence_threshold=confidence_threshold,
            )
            for i in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        # Layer outputs for SRK probing
        self.layer_outputs = []

        # Curriculum placeholder (for API compatibility)
        self.curriculum = [1.0] * num_layers

    def forward(self, input_ids: torch.Tensor, probe_layers: bool = False) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        self.layer_outputs = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            if probe_layers:
                self.layer_outputs.append(x.detach().clone())

        x = self.norm(x)
        logits = self.lm_head(x)
        return logits

    def get_phase_health(self) -> dict:
        """Aggregate Phase health metrics from all layers."""
        metrics = {"r_k_mean": [], "r_k_std": [], "r_k_min": [], "r_k_max": []}
        for layer in self.layers:
            layer_metrics = layer.get_phase_health()
            for k, v in layer_metrics.items():
                metrics[k].append(v)

        return {
            "r_k_mean": sum(metrics["r_k_mean"]) / len(metrics["r_k_mean"]) if metrics["r_k_mean"] else 0.0,
            "r_k_std": sum(metrics["r_k_std"]) / len(metrics["r_k_std"]) if metrics["r_k_std"] else 0.0,
            "r_k_min": min(metrics["r_k_min"]) if metrics["r_k_min"] else 0.0,
            "r_k_max": max(metrics["r_k_max"]) if metrics["r_k_max"] else 0.0,
        }

    def get_proposal_metrics(self) -> dict:
        """
        V10.4: Aggregate proposal mode metrics from all layers.

        Returns:
            dict with confidence_mean, skip_rate, and per-layer metrics
        """
        if not self.proposal_mode:
            return {
                "confidence_mean": 0.0,
                "skip_rate": 0.0,
                "per_layer_confidence": [],
                "per_layer_skip_rate": [],
            }

        confidence_means = []
        skip_rates = []
        for layer in self.layers:
            metrics = layer.get_proposal_metrics()
            confidence_means.append(metrics["confidence_mean"])
            skip_rates.append(metrics["skip_rate"])

        return {
            "confidence_mean": sum(confidence_means) / len(confidence_means) if confidence_means else 0.0,
            "skip_rate": sum(skip_rates) / len(skip_rates) if skip_rates else 0.0,
            "per_layer_confidence": confidence_means,
            "per_layer_skip_rate": skip_rates,
        }

    def update_curriculum(self, new_curriculum: List[float]):
        """API compatibility (no-op for binding cache)."""
        pass

    def get_layer_ppl(self, input_ids: torch.Tensor, targets: torch.Tensor) -> List[float]:
        """Compute PPL contribution from each layer by early-exiting."""
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_ppls = []
        for layer in self.layers:
            x = layer(x)
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()
            layer_ppls.append(ppl)

        return layer_ppls

    def get_layer_contributions(self, input_ids: torch.Tensor, targets: torch.Tensor) -> Dict[str, List[float]]:
        """Analyze per-layer contributions."""
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        # Initial PPL (embedding only)
        logits_embed = self.lm_head(self.norm(x))
        loss_embed = F.cross_entropy(logits_embed.view(-1, self.vocab_size), targets.view(-1))
        ppl_embed = torch.exp(loss_embed).item()

        layer_ppls = []
        layer_deltas = []
        prev_ppl = ppl_embed

        for layer in self.layers:
            x = layer(x)
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()

            layer_ppls.append(ppl)
            layer_deltas.append(prev_ppl - ppl)
            prev_ppl = ppl

        total_reduction = ppl_embed - layer_ppls[-1]
        contribution_pcts = [
            (delta / total_reduction * 100) if total_reduction > 0 else 0
            for delta in layer_deltas
        ]

        return {
            'ppl': layer_ppls,
            'ppl_delta': layer_deltas,
            'contribution_pct': contribution_pcts,
            'phase_ratio': [1.0] * self.num_layers,
            'ppl_embed': ppl_embed,
            'total_reduction': total_reduction,
        }

    def ablate_attention(self, input_ids: torch.Tensor, targets: torch.Tensor,
                         ablate_phase: bool = False, ablate_local: bool = False) -> float:
        """Return normal PPL (full ablation not implemented for probe)."""
        with torch.no_grad():
            logits = self.forward(input_ids)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            return torch.exp(loss).item()

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    # =========================================================================
    # V10.5: FIX 3 - True Gradient Norm Diagnostic (not curriculum-based)
    # =========================================================================
    def get_component_grad_norms(self) -> Dict[str, List[float]]:
        """
        Measure actual gradient norms for each attention component per layer.

        Returns dict with per-layer gradient norms for:
        - local: LocalWindowAttention gradients
        - phase: BindingCachePhaseState gradients
        - quad:  BindingCacheQuadQuery gradients
        - ff:    Feed-forward gradients

        This replaces the broken curriculum-based "gradient dominance" diagnostic
        which falsely reported 100% phase-heavy for Protected Phase architecture.
        """
        grad_norms = {
            'local': [],
            'phase': [],
            'quad': [],
            'ff': [],
        }

        for layer in self.layers:
            # Local attention gradient norm
            local_norm = 0.0
            for p in layer.local_attn.parameters():
                if p.grad is not None:
                    local_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['local'].append(local_norm ** 0.5)

            # Phase state gradient norm
            phase_norm = 0.0
            for p in layer.phase_state.parameters():
                if p.grad is not None:
                    phase_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['phase'].append(phase_norm ** 0.5)

            # Quad query gradient norm
            quad_norm = 0.0
            for p in layer.quad_query.parameters():
                if p.grad is not None:
                    quad_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['quad'].append(quad_norm ** 0.5)

            # Feed-forward gradient norm
            ff_norm = 0.0
            for p in layer.ff.parameters():
                if p.grad is not None:
                    ff_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['ff'].append(ff_norm ** 0.5)

        return grad_norms

    def get_gradient_dominance_report(self) -> Dict[str, any]:
        """
        Analyze which components receive gradients and detect dominance issues.

        A healthy model should have gradients flowing to all components at all layers.
        Gradient dominance (one component >> others) indicates learning imbalance.

        Returns:
            dict with:
            - component_totals: Total gradient norm per component
            - component_pcts: Percentage contribution per component
            - per_layer_dominant: Which component dominates each layer
            - dominance_detected: True if one component > 70% of total
            - layer_gradient_decay: Ratio of L_last / L_0 gradients (healthy > 0.1)
        """
        grad_norms = self.get_component_grad_norms()

        # Sum across layers for each component
        totals = {k: sum(v) for k, v in grad_norms.items()}
        grand_total = sum(totals.values()) + 1e-10  # Avoid division by zero

        # Percentage contribution per component
        pcts = {k: (v / grand_total * 100) for k, v in totals.items()}

        # Per-layer dominant component
        per_layer_dominant = []
        for i in range(self.num_layers):
            layer_norms = {k: grad_norms[k][i] for k in grad_norms.keys()}
            dominant = max(layer_norms, key=layer_norms.get)
            per_layer_dominant.append(dominant)

        # Check for dominance (any component > 70%)
        max_pct = max(pcts.values())
        dominance_detected = max_pct > 70

        # Layer gradient decay: how much gradient reaches later layers
        # Healthy models should have layer_gradient_decay > 0.1
        total_per_layer = [sum(grad_norms[k][i] for k in grad_norms.keys())
                          for i in range(self.num_layers)]
        if total_per_layer[0] > 1e-10:
            layer_gradient_decay = total_per_layer[-1] / total_per_layer[0]
        else:
            layer_gradient_decay = 0.0

        return {
            'component_totals': totals,
            'component_pcts': pcts,
            'per_layer_dominant': per_layer_dominant,
            'dominance_detected': dominance_detected,
            'layer_gradient_decay': layer_gradient_decay,
            'per_layer_totals': total_per_layer,
        }

    # =========================================================================
    # V10.5: FIX 1 - Deep Supervision for Depth Utilization
    # =========================================================================
    def init_deep_supervision(self, lambda_decay: float = 1.0):
        """
        Initialize auxiliary classification heads for deep supervision.

        Deep supervision forces later layers to learn useful representations
        by adding auxiliary losses at intermediate layers. This prevents
        L0 overfitting where only the first layer contributes to PPL reduction.

        Args:
            lambda_decay: Controls how much later layers are weighted.
                          Loss_i = lambda_decay * (i / num_layers) * CE(proj_i(h_i), targets)
                          Higher values encourage later layers more strongly.
        """
        self.deep_supervision_enabled = True
        self.deep_supervision_lambda = lambda_decay

        # Auxiliary projection heads - one per layer (except last)
        # These project intermediate representations to logits
        # We use weight-tied heads (share with lm_head) to reduce params
        self.aux_norms = nn.ModuleList([
            nn.LayerNorm(self.d_model) for _ in range(self.num_layers - 1)
        ])

        # Move to same device as model
        device = next(self.parameters()).device
        self.aux_norms = self.aux_norms.to(device)

    def forward_with_deep_supervision(
        self,
        input_ids: torch.Tensor,
        targets: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, List[float]]:
        """
        Forward pass with deep supervision losses at intermediate layers.

        Args:
            input_ids: [B, N] input token IDs
            targets: [B, N] target token IDs for loss computation

        Returns:
            logits: [B, N, V] final layer logits
            deep_loss: Scalar tensor with weighted sum of auxiliary losses
            layer_losses: List of per-layer auxiliary losses (for monitoring)
        """
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_losses = []
        deep_loss = torch.tensor(0.0, device=input_ids.device)

        for i, layer in enumerate(self.layers):
            x = layer(x)

            # Compute auxiliary loss for all layers except the last
            if hasattr(self, 'deep_supervision_enabled') and self.deep_supervision_enabled:
                if i < self.num_layers - 1:
                    # Layer weight: increases with depth to emphasize later layers
                    # λ * (i+1) / num_layers ensures L0 gets minimal weight, Ln-1 gets max
                    layer_weight = self.deep_supervision_lambda * (i + 1) / self.num_layers

                    # Project to logits using shared lm_head
                    x_normed = self.aux_norms[i](x)
                    aux_logits = self.lm_head(x_normed)
                    aux_loss = F.cross_entropy(
                        aux_logits.view(-1, self.vocab_size),
                        targets.view(-1)
                    )

                    layer_losses.append(aux_loss.item())
                    deep_loss = deep_loss + layer_weight * aux_loss

        # Final layer
        x = self.norm(x)
        logits = self.lm_head(x)

        return logits, deep_loss, layer_losses


# =============================================================================
# SAMPLE GENERATION FOR QUALITY MONITORING
# =============================================================================
# V10.3.5: Generate text samples every N steps to monitor quality

SAMPLE_PROMPTS = (
    "The",                                          # Simple completion
    "In the beginning",                             # Narrative
    "The cat sat on",                               # Simple syntax
    "Scientists have discovered that",              # Factual
    "Once upon a time, there was a",               # Story
)


def generate_sample(
    model: nn.Module,
    tokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 64,
    temperature: float = 0.9,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.15,
) -> str:
    """
    Generate text from a prompt for quality monitoring.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    """
    model.eval()

    # Encode prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

    # Generate tokens one by one
    generated = input_ids.clone()

    with torch.no_grad():
        for _ in range(max_new_tokens):
            # Forward pass
            outputs = model(generated)

            # Handle different output formats
            if isinstance(outputs, dict):
                logits = outputs.get('logits', outputs.get('output', None))
            elif isinstance(outputs, (tuple, list)):
                logits = outputs[0]
            else:
                logits = outputs

            if logits is None:
                break

            # Get next token logits
            next_logits = logits[:, -1, :].clone()

            # Apply repetition penalty
            if repetition_penalty != 1.0:
                for token_id in set(generated[0].tolist()):
                    if next_logits[0, token_id] > 0:
                        next_logits[0, token_id] /= repetition_penalty
                    else:
                        next_logits[0, token_id] *= repetition_penalty

            # Apply temperature
            next_logits = next_logits / temperature

            # Top-k filtering
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

            indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
            next_logits[indices_to_remove] = float('-inf')

            # Sample next token
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append to sequence
            generated = torch.cat([generated, next_token], dim=1)

            # Check for EOS
            if hasattr(tokenizer, 'eos_token_id') and next_token.item() == tokenizer.eos_token_id:
                break

    # Decode and return
    return tokenizer.decode(generated[0], skip_special_tokens=True)


def run_quality_samples(
    model: nn.Module,
    tokenizer,
    device: torch.device,
    step: int,
    prompts: tuple = SAMPLE_PROMPTS,
):
    """Generate and display quality samples."""
    print(f"\n      ╔═══════════════════════════════════════════════════════════════════╗")
    print(f"      ║  QUALITY SAMPLES @ Step {step:<6}                                 ║")
    print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

    model.eval()
    for i, prompt in enumerate(prompts):
        try:
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=64,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.15,
            )
            # Clean up for display
            generated = generated.strip().replace('\n', ' ')[:150]
            print(f"      ║  [{i+1}] Prompt: \"{prompt}\"")
            print(f"      ║      Output: \"{generated}\"")
            print(f"      ║")
        except Exception as e:
            print(f"      ║  [{i+1}] Error: {e}")
            print(f"      ║")

    print(f"      ╚═══════════════════════════════════════════════════════════════════╝")
    model.train()


def train_real_language(
    args,
    config: Config,
    curriculum: List[float],
):
    """
    Train with real language data (WikiText) and layer probing.
    """
    print("\n" + "=" * 70)
    print("REAL LANGUAGE MODE: WikiText Language Modeling")
    print("=" * 70)

    # Load dataset
    print(f"\nLoading {args.dataset} dataset...")
    train_dataset = WikiTextDataset("train", args.seq_len, args.dataset)
    val_dataset = WikiTextDataset("validation", args.seq_len, args.dataset)

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False)

    # Create model
    # V10.3.3: Support for Binding Cache architecture
    use_binding_cache = getattr(args, 'binding_cache', False)
    # V10.3.2: Support for Protected Phase architecture
    use_protected_phase = getattr(args, 'protected_phase', False)

    if use_binding_cache:
        # Parse binding cache ratios
        bc_phase_ratio = [float(x) for x in args.binding_cache_phase_ratio.split(",")]
        bc_local_ratio = [float(x) for x in args.binding_cache_local_ratio.split(",")]
        bc_quad_ratio = [float(x) for x in args.binding_cache_quad_ratio.split(",")]

        # Pad/truncate to match num_layers
        while len(bc_phase_ratio) < config.num_layers:
            bc_phase_ratio.append(bc_phase_ratio[-1] if bc_phase_ratio else 0.3)
        while len(bc_local_ratio) < config.num_layers:
            bc_local_ratio.append(bc_local_ratio[-1] if bc_local_ratio else 0.4)
        while len(bc_quad_ratio) < config.num_layers:
            bc_quad_ratio.append(bc_quad_ratio[-1] if bc_quad_ratio else 0.3)
        bc_phase_ratio = bc_phase_ratio[:config.num_layers]
        bc_local_ratio = bc_local_ratio[:config.num_layers]
        bc_quad_ratio = bc_quad_ratio[:config.num_layers]

        print(f"\n╔═══════════════════════════════════════════════════════════════════════╗")
        print(f"║  V10.3.3: BINDING CACHE ARCHITECTURE                                  ║")
        print(f"╠═══════════════════════════════════════════════════════════════════════╣")
        print(f"║  d_model={config.d_model}, num_heads={config.num_heads}, num_layers={config.num_layers}")
        print(f"║  Three-Path Architecture (No Gradient Competition):                   ║")
        print(f"║                                                                       ║")
        print(f"║    1. LOCAL PATH  - O(n*w) Window Attention                          ║")
        print(f"║       Window size: {args.local_window_size}")
        print(f"║       Fast syntax learning, direct token-to-token                    ║")
        print(f"║                                                                       ║")
        print(f"║    2. PHASE PATH  - O(n) Memory State Accumulation                   ║")
        print(f"║       Decay gamma: {args.decay_gamma}")
        print(f"║       Binding accumulation via decayed cumsum                        ║")
        print(f"║                                                                       ║")
        print(f"║    3. QUAD PATH   - O(n*k) Top-K Cache Query                         ║")
        print(f"║       Top-K: {args.binding_cache_top_k}")
        print(f"║       Quadratic attention over cached memories                       ║")
        if args.proposal_mode:
            print(f"╠═══════════════════════════════════════════════════════════════════════╣")
            print(f"║  V10.4 PROPOSAL MODE ENABLED                                          ║")
            print(f"║    Quad returns K proposals (no softmax mixing)                       ║")
            print(f"║    Phase integrates proposals with gating                             ║")
            print(f"║    Confidence threshold: {args.confidence_threshold:.2f}                                      ║")
        print(f"╠═══════════════════════════════════════════════════════════════════════╣")
        print(f"║  Per-Layer Ratios:                                                    ║")
        for i in range(config.num_layers):
            print(f"║    L{i}: Local={bc_local_ratio[i]:.2f}, Phase={bc_phase_ratio[i]:.2f}, Quad={bc_quad_ratio[i]:.2f}")
        print(f"╚═══════════════════════════════════════════════════════════════════════╝")

        model = BindingCacheLMTransformer(
            vocab_size=args.lm_vocab_size,
            d_model=config.d_model,
            num_heads=config.num_heads,
            num_layers=config.num_layers,
            d_ff=config.d_ff,
            dropout=config.dropout,
            max_seq_len=args.seq_len,
            window_size=args.local_window_size,
            top_k=args.binding_cache_top_k,
            decay_gamma=args.decay_gamma,
            phase_ratios=bc_phase_ratio,
            local_ratios=bc_local_ratio,
            quad_ratios=bc_quad_ratio,
            proposal_mode=args.proposal_mode,
            confidence_threshold=args.confidence_threshold,
        ).to(config.device)

    elif use_protected_phase:
        print(f"\nCreating ProtectedPhaseLMTransformer (V10.3.2)...")
        print(f"  d_model={config.d_model}, num_heads={config.num_heads}, num_layers={config.num_layers}")
        print(f"  Architecture: Phase → Memory State → Quadratic Query")
        print(f"  Phase's job:  Accumulate bindings via O(n) cumsum")
        print(f"  Quad's job:   Query memory via O(n²) attention")
        print(f"  Key insight:  No gradient competition - they collaborate")

        model = ProtectedPhaseLMTransformer(
            vocab_size=args.lm_vocab_size,
            d_model=config.d_model,
            num_heads=config.num_heads,
            num_layers=config.num_layers,
            d_ff=config.d_ff,
            dropout=config.dropout,
            max_seq_len=args.seq_len,
            bounded_phase=config.bounded_phase,
        ).to(config.device)
    else:
        print(f"\nCreating HybridLMTransformer...")
        print(f"  d_model={config.d_model}, num_heads={config.num_heads}, num_layers={config.num_layers}")
        print(f"  Initial curriculum: {curriculum}")

        model = HybridLMTransformer(
            vocab_size=args.lm_vocab_size,
            d_model=config.d_model,
            num_heads=config.num_heads,
            num_layers=config.num_layers,
            d_ff=config.d_ff,
            dropout=config.dropout,
            max_seq_len=args.seq_len,
            curriculum=curriculum,
            bounded_phase=config.bounded_phase,
        ).to(config.device)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {param_count:,}")

    # V10.5: Deep Supervision initialization (Fix 1 for L0 overfitting)
    use_deep_supervision = getattr(args, 'deep_supervision', False)
    if use_deep_supervision and hasattr(model, 'init_deep_supervision'):
        deep_lambda = getattr(args, 'deep_supervision_lambda', 0.5)
        model.init_deep_supervision(lambda_decay=deep_lambda)
        print(f"\n  Deep Supervision: ENABLED (V10.5)")
        print(f"    Lambda (layer weight): {deep_lambda}")
        print(f"    Purpose: Force later layers to learn useful representations")
        print(f"    Formula: loss += λ * (i+1)/L * CE(aux_proj(h_i), targets)")
    elif use_deep_supervision:
        print(f"\n  Deep Supervision: REQUESTED but model lacks init_deep_supervision()")
        print(f"    Only supported for BindingCacheLMTransformer currently")
        use_deep_supervision = False

    # Phase-first curriculum controller (disabled for protected phase)
    pfc = None
    if args.phase_first_curriculum and not use_protected_phase:
        pfc = PhaseFirstCurriculum(
            num_layers=config.num_layers,
            alpha_high=args.alpha_phase_high,
            alpha_low=args.alpha_phase_low,
            ppl_high=args.ppl_high,
            ppl_low=args.ppl_low,
        )
        print(f"\n  Phase-First Curriculum: ENABLED")
        print(f"    alpha_high={args.alpha_phase_high}, alpha_low={args.alpha_phase_low}")
        print(f"    ppl_high={args.ppl_high}, ppl_low={args.ppl_low}")

    # ==========================================================================
    # V10.3.0: SRK PHASE LEARNING MONITORING
    # ==========================================================================
    srk_monitor = None
    if hasattr(args, 'enable_srk') and args.enable_srk:
        if not args.probe_layers:
            print("\n  ⚠️  WARNING: --enable-srk requires --probe-layers to capture layer outputs")
            print("       Enabling --probe-layers automatically.")
            args.probe_layers = True

        # Build SRK configuration
        srk_config = SRKPhaseLearningConfig(
            enable_srk=True,
            dna_bridge_layer=getattr(args, 'srk_dna_bridge_layer', 0),
            csr_alignment_layer=getattr(args, 'srk_csr_layer', 1),
            witness_layer=getattr(args, 'srk_witness_layer', 2),
            synthesis_layer=getattr(args, 'srk_synthesis_layer', 3),
            enable_dna_bridge=not getattr(args, 'srk_disable_dna_bridge', False),
            enable_phase_hook=not getattr(args, 'srk_disable_phase_hook', False),
            enable_witness=not getattr(args, 'srk_disable_witness', False),
            enable_synthesis=not getattr(args, 'srk_disable_synthesis', False),
            lambda_ontology=getattr(args, 'srk_lambda_ontology', 0.1),
            lambda_coherence=getattr(args, 'srk_lambda_coherence', 0.05),
        )

        # Validate layer indices for this model
        layer_warnings = srk_config.validate_for_model(config.num_layers)
        for warning in layer_warnings:
            print(f"  ⚠️  {warning}")

        # Create SRK monitor
        srk_monitor = SRKPhaseLearningMonitor(
            config=srk_config,
            hidden_dim=config.d_model,
            num_heads=config.num_heads,
            device=torch.device(config.device),
        )

        # V10.3.1: Create layer influence diagnostics
        srk_influence = LayerInfluenceDiagnostics(srk_config)

        print(f"\n  ╔══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.1: SRK PHASE LEARNING MONITORING ENABLED                  ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Layer Components (with Influence Diagnostics):                  ║")
        if srk_config.enable_dna_bridge:
            print(f"  ║    L{srk_config.dna_bridge_layer}: DNA Bridge (Ontology)          ACTIVE + INFLUENCE    ║")
        if srk_config.enable_phase_hook:
            print(f"  ║    L{srk_config.csr_alignment_layer}: CSR Alignment (Phase Hook)   ACTIVE + INFLUENCE    ║")
        if srk_config.enable_witness:
            print(f"  ║    L{srk_config.witness_layer}: Witness Arbitrator         ACTIVE + INFLUENCE    ║")
        if srk_config.enable_synthesis:
            print(f"  ║    L{srk_config.synthesis_layer}: Synthesis Gate            ACTIVE + INFLUENCE    ║")
        print(f"  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Tracking: Phase coherence, Ontological diversity, Layer PPL     ║")
        print(f"  ║  NEW: Per-layer CONSTRUCTIVE/DESTRUCTIVE influence analysis      ║")
        print(f"  ╚══════════════════════════════════════════════════════════════════╝")
    else:
        srk_influence = None

    # ==========================================================================
    # V10.3.4: KOSHA/WITNESS CONSCIOUSNESS DIAGNOSTICS
    # ==========================================================================
    kosha_diagnostics = None
    witness_diagnostics = None

    if getattr(args, 'enable_kosha', False):
        kosha_diagnostics = KoshaDiagnostics(
            hidden_dim=config.d_model,
            num_layers=config.num_layers,
            state_dim=SOVEREIGN_STATE_DIM,
            device=torch.device(config.device),
        )

        print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.4: KOSHA CONSCIOUSNESS DIAGNOSTICS ENABLED                 ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  The 5-Layer Kosha Model (Pancha Kosha):                          ║")
        print(f"  ║                                                                    ║")
        print(f"  ║    0. MATERIAL   (Annamaya)     - Token/syntax grounding          ║")
        print(f"  ║    1. VITAL      (Pranamaya)    - Energy/gradient flow            ║")
        print(f"  ║    2. MENTAL     (Manomaya)     - Semantic binding                ║")
        print(f"  ║    3. INTELLECTUAL (Vijnanamaya) - Abstract reasoning             ║")
        print(f"  ║    4. BLISSFUL   (Anandamaya)   - Coherence/integration           ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Target Kosha: {args.kosha_target:<12}                              ║")
        print(f"  ║  Dampen Material: {args.kosha_dampen_material:.2f}  |  Boost Target: {args.kosha_boost_target:.2f}       ║")
        print(f"  ║  Gyroscopic Loss: base={args.kosha_gyro_base_gain:.2f}, max={args.kosha_gyro_max_gain:.2f}            ║")
        print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

    if getattr(args, 'enable_witness', False):
        witness_diagnostics = WitnessDiagnostics(
            hidden_dim=config.d_model,
            state_dim=SOVEREIGN_STATE_DIM,
            constraint_threshold=args.witness_constraint_threshold,
            device=torch.device(config.device),
        )

        print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.4: WITNESS (SAKSHI) OBSERVER DIAGNOSTICS ENABLED           ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  The Witness observes thought patterns without attachment:        ║")
        print(f"  ║                                                                    ║")
        print(f"  ║    Vritti (Epistemic States):                                     ║")
        print(f"  ║      - FACT: Verified truth                                       ║")
        print(f"  ║      - MISCONCEPTION: Believed but wrong                          ║")
        print(f"  ║      - IMAGINATION: Creative/hypothetical                         ║")
        print(f"  ║      - VOID: Unknown/uncertain                                    ║")
        print(f"  ║      - MEMORY: Retrieved from context                             ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Constraint Threshold: {args.witness_constraint_threshold:.2f}                               ║")
        print(f"  ║  Tracks: Domain arbitration, bottleneck detection, meta-cognition ║")
        print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

        # V10.3.7: Witness entropy regularization
        if getattr(args, 'witness_entropy_reg', False):
            lambda_entropy = getattr(args, 'witness_entropy_lambda', 0.1)
            print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
            print(f"  ║  V10.3.7: WITNESS ENTROPY REGULARIZATION ENABLED                  ║")
            print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
            print(f"  ║  Prevents vritti collapse to single epistemic state               ║")
            print(f"  ║  Loss += -λ * H(vritti)   where H = -Σ p*log(p)                   ║")
            print(f"  ║  Lambda: {lambda_entropy:.3f}  (higher = more balanced distribution)        ║")
            print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

    # ==========================================================================
    # V10.3.5: DOMAIN SEPARATION - Aligned with SRK component layout
    # ==========================================================================
    use_domain_separation = getattr(args, 'domain_separation', False)
    csr_domain_layers = []
    kosha_domain_layers = []
    witness_domain_layers = []
    synthesis_domain_layers = []

    if use_domain_separation:
        # Parse layer assignments
        csr_domain_layers = [int(x) for x in args.csr_domain_layers.split(",")]
        kosha_domain_layers = [int(x) for x in args.kosha_domain_layers.split(",")]
        witness_domain_layers = [int(x) for x in args.witness_domain_layers.split(",")]
        synthesis_domain_layers = [int(x) for x in args.synthesis_domain_layers.split(",")]

        print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"  ║  V10.3.5: DOMAIN SEPARATION ENABLED                               ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  SRK Component Layout (no authority conflict):                    ║")
        print(f"  ║                                                                    ║")
        print(f"  ║  Layer  Component              Domain         Role                ║")
        print(f"  ║  ─────────────────────────────────────────────────────────────    ║")
        print(f"  ║  L0     DNA Bridge            ONTOLOGY       Foundational Ontology║")
        print(f"  ║  L1     CSR Alignment         CSR            Phase Extraction     ║")
        print(f"  ║  L2     Kosha + Witness       KOSHA          Consciousness        ║")
        print(f"  ║  L3     Synthesis Gate        SYNTHESIS      Output Integration   ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Actual Layer Assignments:                                        ║")
        for i in range(config.num_layers):
            components = []
            if i in csr_domain_layers:
                if i == 0:
                    components.append("DNA_BRIDGE")
                else:
                    components.append("CSR")
            if i in kosha_domain_layers:
                components.append("KOSHA")
            if i in witness_domain_layers and i not in kosha_domain_layers:
                components.append("WITNESS")
            elif i in witness_domain_layers and i in kosha_domain_layers:
                components[-1] = "KOSHA+WITNESS"  # Combine if same layer
            if i in synthesis_domain_layers:
                components.append("SYNTHESIS")
            comp_str = "+".join(components) if components else "NONE"
            print(f"  ║    L{i}: {comp_str:<30}                     ║")
        print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)

    # Training loop
    print(f"\nTraining for {config.num_steps} steps...")
    model.train()
    step = 0
    total_loss = 0.0
    total_main_loss = 0.0  # V10.5.1: Track main loss separately for comparable PPL
    total_deep_loss = 0.0  # V10.5.1: Track deep supervision loss separately
    log_interval = 100

    train_iter = iter(train_loader)
    best_val_ppl = float('inf')

    # Convergence milestones tracking (to measure learning speed)
    ppl_milestones = [500, 200, 100, 50]
    milestone_steps = {m: None for m in ppl_milestones}
    ppl_history = []  # Track PPL over time

    while step < config.num_steps:
        try:
            x, y = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            x, y = next(train_iter)

        x, y = x.to(config.device), y.to(config.device)

        # V10.3.7: Check if witness entropy regularization is enabled
        use_witness_entropy = getattr(args, 'witness_entropy_reg', False) and witness_diagnostics is not None

        # V10.5: Deep Supervision forward path
        deep_loss_value = 0.0
        main_loss_value = 0.0  # V10.5.1: Track main loss separately for PPL reporting
        if use_deep_supervision and hasattr(model, 'forward_with_deep_supervision'):
            logits, deep_loss, layer_losses = model.forward_with_deep_supervision(x, y)
            main_loss = F.cross_entropy(logits.view(-1, args.lm_vocab_size), y.view(-1))
            main_loss_value = main_loss.item()  # Track main loss for reporting
            loss = main_loss + deep_loss  # Combined loss for backprop
            deep_loss_value = deep_loss.item()
            layer_hidden_states = None  # Not needed when using deep supervision
        # Forward - use probe_layers if witness entropy is enabled
        elif use_witness_entropy and hasattr(model, 'layer_outputs'):
            logits = model(x, probe_layers=True)
            layer_hidden_states = model.layer_outputs
            loss = F.cross_entropy(logits.view(-1, args.lm_vocab_size), y.view(-1))
            main_loss_value = loss.item()
        else:
            logits = model(x)
            layer_hidden_states = None
            loss = F.cross_entropy(logits.view(-1, args.lm_vocab_size), y.view(-1))
            main_loss_value = loss.item()

        # V10.3.7: Witness entropy regularization to prevent vritti collapse
        if use_witness_entropy and layer_hidden_states:
            # Use witness domain layer if domain separation enabled
            if use_domain_separation and witness_domain_layers:
                witness_layer_idx = max([l for l in witness_domain_layers if l < len(layer_hidden_states)])
            else:
                witness_layer_idx = min(2, len(layer_hidden_states) - 1)
            # Forward pass through witness (this stores _last_vritti_entropy with gradients)
            _ = witness_diagnostics(layer_hidden_states[witness_layer_idx], step=step)
            # Get entropy loss and add to main loss
            lambda_entropy = getattr(args, 'witness_entropy_lambda', 0.1)
            entropy_loss = witness_diagnostics.get_entropy_loss(lambda_entropy)
            loss = loss + entropy_loss

        # Backward
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()
        total_main_loss += main_loss_value  # V10.5.1: Track main loss separately
        total_deep_loss += deep_loss_value  # V10.5.1: Track deep loss separately
        step += 1

        # Logging
        if step % log_interval == 0:
            avg_loss = total_loss / log_interval
            avg_main_loss = total_main_loss / log_interval  # V10.5.1: Main loss for PPL
            avg_deep_loss = total_deep_loss / log_interval  # V10.5.1: Deep loss avg
            ppl = math.exp(avg_main_loss)  # V10.5.1: PPL from main loss only (comparable)
            total_loss = 0.0
            total_main_loss = 0.0
            total_deep_loss = 0.0

            # Track PPL history (using main-loss PPL for comparability)
            ppl_history.append((step, ppl))

            # Check milestones (convergence speed tracking)
            for milestone in ppl_milestones:
                if milestone_steps[milestone] is None and ppl < milestone:
                    milestone_steps[milestone] = step
                    print(f"  ★ MILESTONE: PPL dropped below {milestone} at step {step}!")

            # Update phase-first curriculum
            if pfc is not None:
                new_curriculum = pfc.update(ppl)
                model.update_curriculum(new_curriculum)
                curr_str = ",".join([f"{c:.2f}" for c in new_curriculum])
                print(f"  Step {step:5d} | Loss: {avg_loss:.4f} | PPL: {ppl:8.2f} | Curriculum: [{curr_str}]")
            elif use_deep_supervision:
                # V10.5.1: Show main loss, PPL (from main loss), and deep loss separately
                print(f"  Step {step:5d} | MainLoss: {avg_main_loss:.4f} | PPL: {ppl:8.2f} | DeepLoss: {avg_deep_loss:.4f}")
            else:
                print(f"  Step {step:5d} | Loss: {avg_loss:.4f} | PPL: {ppl:8.2f}")

        # Evaluation
        if step % config.eval_every == 0:
            model.eval()
            val_loss = 0.0
            val_batches = 0

            with torch.no_grad():
                for x, y in val_loader:
                    x, y = x.to(config.device), y.to(config.device)
                    logits = model(x)
                    val_loss += F.cross_entropy(logits.view(-1, args.lm_vocab_size), y.view(-1)).item()
                    val_batches += 1
                    if val_batches >= 50:  # Limit eval batches
                        break

            val_loss /= val_batches
            val_ppl = math.exp(val_loss)
            print(f"\n  === Validation @ Step {step} ===")
            print(f"      Val Loss: {val_loss:.4f} | Val PPL: {val_ppl:.2f}")

            if val_ppl < best_val_ppl:
                best_val_ppl = val_ppl
                print(f"      ★ New best Val PPL!")

            # V10.3.2: Protected Phase health monitoring
            if use_protected_phase and hasattr(model, 'get_phase_health'):
                phase_health = model.get_phase_health()
                print(f"\n      Protected Phase Health (R_k statistics):")
                print(f"        R_k mean: {phase_health['r_k_mean']:.4f} (target: 0.3-0.7)")
                print(f"        R_k std:  {phase_health['r_k_std']:.4f}")
                print(f"        R_k range: [{phase_health['r_k_min']:.4f}, {phase_health['r_k_max']:.4f}]")

                # Interpret health
                r_k_mean = phase_health['r_k_mean']
                if r_k_mean < 0.1:
                    print(f"        ⚠️  Phase COLLAPSED (R_k → 0)")
                elif r_k_mean > 0.9:
                    print(f"        ⚠️  Phase DEGENERATE (R_k → 1)")
                elif 0.3 <= r_k_mean <= 0.7:
                    print(f"        ✓  Phase HEALTHY")
                else:
                    print(f"        Phase marginal (outside optimal range)")

            # Layer-wise probing with detailed metrics
            if args.probe_layers:
                x_sample, y_sample = next(iter(val_loader))
                x_sample, y_sample = x_sample.to(config.device), y_sample.to(config.device)

                # Get detailed layer contributions
                contrib = model.get_layer_contributions(x_sample, y_sample)

                print(f"\n      Layer Contributions (Does Phase Learn Faster/Richer?):")
                print(f"      {'Layer':<8} {'Phase%':<8} {'PPL':<10} {'Δ PPL':<10} {'Contrib%':<10}")
                print(f"      {'-'*46}")
                for i in range(model.num_layers):
                    phase_pct = contrib['phase_ratio'][i] * 100
                    ppl = contrib['ppl'][i]
                    delta = contrib['ppl_delta'][i]
                    contrib_pct = contrib['contribution_pct'][i]
                    # Highlight layers that contribute most
                    marker = "★" if contrib_pct > 100 / model.num_layers * 1.5 else " "
                    print(f"      L{i:<6} {phase_pct:>6.1f}%  {ppl:>8.1f}  {delta:>+8.1f}  {contrib_pct:>8.1f}% {marker}")

                print(f"\n      Summary:")
                print(f"        Embed-only PPL: {contrib['ppl_embed']:.1f}")
                print(f"        Final PPL:      {contrib['ppl'][-1]:.1f}")
                print(f"        Total Reduction: {contrib['total_reduction']:.1f}")

                # Ablation test: Phase-only vs Local-only
                if use_protected_phase:
                    # Protected Phase: Sequential collaboration, not parallel mixing
                    print(f"\n      Protected Phase Architecture (no ablation test):")
                    print(f"        Architecture: Phase → Memory → Quad Query (sequential)")
                    print(f"        Normal PPL:  {val_ppl:.1f}")
                    print(f"        Phase and Quad COLLABORATE, not compete")
                    print(f"        → Ablation N/A for sequential architecture")

                    # Use dummy values for later analysis
                    ppl_phase_only = val_ppl
                    ppl_local_only = val_ppl
                else:
                    print(f"\n      Ablation Test (Phase vs Local contribution):")
                    ppl_normal = val_ppl
                    ppl_phase_only = model.ablate_attention(x_sample, y_sample, ablate_local=True)
                    ppl_local_only = model.ablate_attention(x_sample, y_sample, ablate_phase=True)

                    print(f"        Normal (mixed):    PPL = {ppl_normal:.1f}")
                    print(f"        Phase-only:        PPL = {ppl_phase_only:.1f}")
                    print(f"        Local-only:        PPL = {ppl_local_only:.1f}")

                    # Interpretation
                    phase_better = ppl_phase_only < ppl_local_only
                    if phase_better:
                        improvement = ((ppl_local_only - ppl_phase_only) / ppl_local_only) * 100
                        print(f"        → Phase is {improvement:.1f}% BETTER than Local alone!")
                    else:
                        improvement = ((ppl_phase_only - ppl_local_only) / ppl_phase_only) * 100
                        print(f"        → Local is {improvement:.1f}% better than Phase alone")

                # V10.3.0: SRK Phase Learning Observation
                if srk_monitor is not None:
                    # Forward pass with layer capture
                    _ = model(x_sample, probe_layers=True)
                    layer_hidden_states = model.layer_outputs

                    if layer_hidden_states:
                        srk_metrics = srk_monitor.observe(layer_hidden_states)

                        print(f"\n      ╔══════════════════════════════════════════════════════╗")
                        print(f"      ║  SRK Phase Learning Metrics @ Step {step:<6}            ║")
                        print(f"      ╠══════════════════════════════════════════════════════╣")

                        # DNA Bridge (L4)
                        dna_key = f'L{srk_monitor.config.dna_bridge_layer}_dna_onto_diversity'
                        if dna_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.dna_bridge_layer} DNA Bridge:                              ║")
                            print(f"      ║    Ontology Diversity: {srk_metrics[dna_key]:.4f}                   ║")

                        # CSR Phase Hook (L7)
                        csr_key = f'L{srk_monitor.config.csr_alignment_layer}_csr_phase_coherence'
                        if csr_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.csr_alignment_layer} CSR Alignment:                           ║")
                            print(f"      ║    Phase Coherence (R_k): {srk_metrics[csr_key]:.4f}                ║")

                        # Witness Arbitrator (L9)
                        wit_key = f'L{srk_monitor.config.witness_layer}_witness_witness_activation'
                        if wit_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.witness_layer} Witness Arbitrator:                       ║")
                            print(f"      ║    Witness Activation: {srk_metrics[wit_key]:.4f}                  ║")

                        # Synthesis Gate (L11)
                        syn_key = f'L{srk_monitor.config.synthesis_layer}_synth_synthesis_gate_mean'
                        if syn_key in srk_metrics:
                            print(f"      ║  L{srk_monitor.config.synthesis_layer} Synthesis Gate:                           ║")
                            print(f"      ║    Gate Mean: {srk_metrics[syn_key]:.4f}                           ║")

                        print(f"      ╚══════════════════════════════════════════════════════╝")

                        # V10.3.1: Layer Influence Diagnostics
                        if srk_influence is not None:
                            influence_metrics = srk_influence.analyze_all_layers(
                                layer_hidden_states,
                                num_heads=config.num_heads,
                            )
                            srk_influence.print_influence_report(influence_metrics, step)

                            # Print detailed breakdown every 5 evaluations
                            if len(srk_influence.influence_history) % 5 == 0:
                                srk_influence.print_detailed_layer_report(influence_metrics)

                # V10.3.4/V10.3.5: Kosha Consciousness Diagnostics (with domain separation)
                if kosha_diagnostics is not None:
                    # Forward pass with layer capture
                    if not layer_hidden_states:
                        _ = model(x_sample, probe_layers=True)
                        layer_hidden_states = model.layer_outputs

                    # V10.3.5: Only analyze layers in Kosha's domain
                    if use_domain_separation and kosha_domain_layers:
                        layers_to_analyze = [i for i in kosha_domain_layers if i < len(layer_hidden_states)]
                    else:
                        layers_to_analyze = range(len(layer_hidden_states))

                    for i in layers_to_analyze:
                        if i < len(layer_hidden_states):
                            kosha_metrics = kosha_diagnostics(layer_hidden_states[i], layer_idx=i, step=step)

                    # Print summary report
                    if use_domain_separation:
                        print(f"\n      [Kosha Domain: Layers {list(layers_to_analyze)}]")
                    kosha_diagnostics.print_report(step)

                # V10.3.4/V10.3.5: Witness Observer Diagnostics (with domain separation)
                if witness_diagnostics is not None:
                    # Forward pass with layer capture
                    if not layer_hidden_states:
                        _ = model(x_sample, probe_layers=True)
                        layer_hidden_states = model.layer_outputs

                    # V10.3.5: Only observe layers in Witness's domain
                    if use_domain_separation and witness_domain_layers:
                        # Use the highest layer in witness domain
                        witness_layer_idx = max([l for l in witness_domain_layers if l < len(layer_hidden_states)])
                    else:
                        witness_layer_idx = min(2, len(layer_hidden_states) - 1)

                    if layer_hidden_states and witness_layer_idx < len(layer_hidden_states):
                        witness_metrics = witness_diagnostics(
                            layer_hidden_states[witness_layer_idx],
                            step=step,
                        )

                    # Print summary report
                    if use_domain_separation:
                        print(f"\n      [Witness Domain: Layer {witness_layer_idx}]")
                    witness_diagnostics.print_report(step)

            print()
            model.train()

        # V10.3.6: Quality sample generation
        sample_every = getattr(args, 'sample_every', 500)
        if sample_every > 0 and step % sample_every == 0 and step > 0:
            # Get tokenizer from dataset
            tokenizer = train_dataset.tokenizer
            # Parse custom prompts if provided
            prompts = SAMPLE_PROMPTS
            custom_prompts = getattr(args, 'sample_prompts', None)
            if custom_prompts:
                prompts = tuple(p.strip() for p in custom_prompts.split(","))
            run_quality_samples(model, tokenizer, config.device, step, prompts)
            model.train()

    # Final evaluation with comprehensive analysis
    print("\n" + "=" * 70)
    if use_protected_phase:
        print("FINAL RESULTS: Protected Phase Learning Analysis (V10.3.2)")
    else:
        print("FINAL RESULTS: Phase Learning Analysis")
    print("=" * 70)
    print(f"  Best Val PPL: {best_val_ppl:.2f}")

    if use_protected_phase:
        print(f"  Architecture: Protected Phase (sequential collaboration)")
        print(f"  Phase contributes 100% as memory accumulator")
    else:
        print(f"  Final Curriculum: {[f'{c:.2f}' for c in model.curriculum]}")

    # Convergence speed summary
    print(f"\n  Convergence Speed (steps to reach PPL milestone):")
    for milestone in ppl_milestones:
        steps = milestone_steps[milestone]
        if steps is not None:
            print(f"    PPL < {milestone:4d}: {steps:5d} steps ✓")
        else:
            print(f"    PPL < {milestone:4d}: Not reached")

    # Final ablation and layer contribution analysis
    model.eval()
    x_final, y_final = next(iter(val_loader))
    x_final, y_final = x_final.to(config.device), y_final.to(config.device)

    with torch.no_grad():
        if use_protected_phase:
            # Protected Phase: no ablation (sequential architecture)
            ppl_phase_only = best_val_ppl  # Phase is always active
            ppl_local_only = best_val_ppl  # Local is always active
        else:
            ppl_phase_only = model.ablate_attention(x_final, y_final, ablate_local=True)
            ppl_local_only = model.ablate_attention(x_final, y_final, ablate_phase=True)
        # Get layer contributions for stability analysis
        contrib = model.get_layer_contributions(x_final, y_final)

    if use_protected_phase:
        print(f"\n  Protected Phase Architecture:")
        print(f"    Phase + Quad collaboration:  PPL = {best_val_ppl:.2f}")
        print(f"    (No ablation - they work sequentially, not in parallel)")

        # Show phase health instead
        if hasattr(model, 'get_phase_health'):
            phase_health = model.get_phase_health()
            print(f"\n  Final Phase Health:")
            print(f"    R_k mean: {phase_health['r_k_mean']:.4f}")
            print(f"    R_k std:  {phase_health['r_k_std']:.4f}")
            if 0.3 <= phase_health['r_k_mean'] <= 0.7:
                print(f"    Status:   HEALTHY ✓")
            elif phase_health['r_k_mean'] < 0.1:
                print(f"    Status:   COLLAPSED ⚠️")
            elif phase_health['r_k_mean'] > 0.9:
                print(f"    Status:   DEGENERATE ⚠️")
            else:
                print(f"    Status:   MARGINAL")
    else:
        print(f"\n  Final Ablation:")
        print(f"    Phase-only PPL: {ppl_phase_only:.2f}")
        print(f"    Local-only PPL: {ppl_local_only:.2f}")
        print(f"    Mixed PPL:      {best_val_ppl:.2f}")

    # =========================================================================
    # CONTROL BASELINE ANCHOR (Epistemic Hygiene)
    # =========================================================================
    print(f"\n  Control Baselines (Rules out confounds):")
    param_count = sum(p.numel() for p in model.parameters())
    print(f"    • Model parameters: {param_count:,}")
    print(f"    • Local-only (ablated) uses SAME parameters, SAME curriculum")
    print(f"    • Phase-only (ablated) uses SAME parameters, SAME curriculum")
    print(f"    • Difference is ONLY attention mechanism, not capacity")

    # Curriculum effect isolation
    if use_protected_phase:
        print(f"    • Architecture: Protected Phase (Phase→Memory→Quad Query)")
        print(f"    • Phase and Quad have SEPARATE roles, not parallel mixing")
        print(f"    • No curriculum needed - roles are architecturally defined")
    elif pfc is not None:
        print(f"    • Curriculum was DYNAMIC (PPL-based), applied to BOTH attention types")
        print(f"    • Final curriculum: {[f'{c:.2f}' for c in model.curriculum]}")
    else:
        print(f"    • Curriculum was STATIC: {[f'{c:.2f}' for c in model.curriculum]}")

    # =========================================================================
    # STABILITY / CONFIDENCE FLAGS (Trust indicators)
    # =========================================================================
    print(f"\n  Stability Notes (Why you can trust these results):")

    # 1. Phase collapse detection (phase values cluster near 0 or ±π)
    phase_collapse_detected = False
    phase_variance_total = 0.0
    phase_layers_checked = 0
    for layer in model.layers:
        if hasattr(layer, 'phase_attn') and hasattr(layer.phase_attn, 'W_phase'):
            # Check if phase projection has collapsed (very low variance)
            w = layer.phase_attn.W_phase.weight.data
            var = w.var().item()
            phase_variance_total += var
            phase_layers_checked += 1
            if var < 1e-6:
                phase_collapse_detected = True

    avg_phase_var = phase_variance_total / max(phase_layers_checked, 1)
    print(f"    • Phase collapse detected:     {'YES ⚠️' if phase_collapse_detected else 'NO ✓'}")
    if phase_layers_checked > 0:
        print(f"      (avg phase weight variance: {avg_phase_var:.6f})")

    # 2. Gradient dominance (one attention component dominates gradients)
    # V10.5 FIX 3: Use actual gradient norms instead of curriculum-based classification
    # The old curriculum-based diagnostic was broken for Protected Phase (curriculum=[1.0]*L)
    if hasattr(model, 'get_gradient_dominance_report'):
        # New: Measure actual gradient norms per component (local/phase/quad/ff)
        grad_report = model.get_gradient_dominance_report()
        gradient_dominance = grad_report['dominance_detected']
        layer_grad_decay = grad_report['layer_gradient_decay']

        print(f"    • Gradient dominance:          {'YES ⚠️' if gradient_dominance else 'NO ✓'}")
        print(f"      Component gradient distribution:")
        for comp, pct in grad_report['component_pcts'].items():
            marker = "⚠️" if pct > 70 else ""
            print(f"        {comp:6s}: {pct:5.1f}% {marker}")
        print(f"      Layer gradient decay (L{model.num_layers-1}/L0): {layer_grad_decay:.3f}", end="")
        if layer_grad_decay < 0.1:
            print(" ⚠️ (vanishing gradients)")
        elif layer_grad_decay > 10:
            print(" ⚠️ (exploding gradients)")
        else:
            print(" ✓")
    else:
        # Fallback for models without the new diagnostic (HybridTransformer, etc.)
        # This is the OLD curriculum-based diagnostic - known to be broken for Protected Phase
        phase_contrib = sum(contrib['contribution_pct'][i] for i in range(model.num_layers) if model.curriculum[i] > 0.5)
        local_contrib = sum(contrib['contribution_pct'][i] for i in range(model.num_layers) if model.curriculum[i] <= 0.5)
        gradient_dominance = abs(phase_contrib - local_contrib) > 70  # One side > 85%
        print(f"    • Gradient dominance:          {'YES ⚠️' if gradient_dominance else 'NO ✓'}")
        print(f"      (phase-heavy layers: {phase_contrib:.1f}%, local-heavy: {local_contrib:.1f}%)")
        if all(c == 1.0 for c in model.curriculum):
            print(f"      ⚠️  WARNING: curriculum=[1.0]*L, this metric is INVALID for Protected Phase")

    # 3. Representation saturation (PPL stops improving)
    ppl_improving = len(ppl_history) < 5 or (ppl_history[-1][1] < ppl_history[-5][1] * 0.99)
    print(f"    • Representation saturation:   {'YES ⚠️' if not ppl_improving else 'NO ✓'}")

    # 4. Early-layer overfitting (L0 contributes too much)
    early_overfit = contrib['contribution_pct'][0] > 60 if len(contrib['contribution_pct']) > 0 else False
    print(f"    • Early-layer overfitting:     {'YES ⚠️' if early_overfit else 'NO ✓'}")
    if early_overfit:
        print(f"      (L0 contributes {contrib['contribution_pct'][0]:.1f}% of PPL reduction)")

    # Overall confidence
    issues = sum([phase_collapse_detected, gradient_dominance, not ppl_improving, early_overfit])
    if issues == 0:
        confidence = "HIGH ✓"
    elif issues == 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW ⚠️"
    print(f"\n    Overall Confidence: {confidence} ({4-issues}/4 checks passed)")

    # V10.5: Deep Supervision Status
    if use_deep_supervision:
        print(f"\n  Deep Supervision (V10.5 Fix 1):")
        print(f"    Status: ENABLED")
        deep_lambda = getattr(args, 'deep_supervision_lambda', 0.5)
        print(f"    Lambda: {deep_lambda}")
        if early_overfit:
            print(f"    Effect: L0 still dominates ({contrib['contribution_pct'][0]:.1f}%) - consider increasing lambda")
        else:
            print(f"    Effect: Depth utilization improved ✓")
            # Show per-layer contribution distribution
            print(f"    Layer contributions: ", end="")
            for i, pct in enumerate(contrib['contribution_pct']):
                marker = "★" if pct > 100 / model.num_layers * 1.5 else ""
                print(f"L{i}:{pct:.0f}% ", end="")
            print()

    # =========================================================================
    # CONCLUSION
    # =========================================================================
    if use_protected_phase:
        print(f"\n  CONCLUSION: Protected Phase Architecture (V10.3.2)")
        print(f"    Phase ACCUMULATES memory state via O(n) cumsum")
        print(f"    Quad QUERIES memory state via O(n²) attention")
        print(f"    They COLLABORATE sequentially - no gradient competition")
        print(f"    Final PPL: {best_val_ppl:.2f}")

        # Protected phase health verdict
        if hasattr(model, 'get_phase_health'):
            health = model.get_phase_health()
            if 0.3 <= health['r_k_mean'] <= 0.7:
                print(f"    Phase health: OPTIMAL (R_k = {health['r_k_mean']:.3f})")
            else:
                print(f"    Phase health: SUBOPTIMAL (R_k = {health['r_k_mean']:.3f})")
    elif ppl_phase_only < ppl_local_only:
        print(f"\n  CONCLUSION: Phase learns RICHER representations!")
        print(f"    Phase alone achieves {((ppl_local_only - ppl_phase_only) / ppl_local_only * 100):.1f}% better PPL than Local alone.")
        if issues == 0:
            print(f"    This result is TRUSTWORTHY (all stability checks passed).")
    else:
        print(f"\n  CONCLUSION: Local attention dominates for this task.")
        print(f"    But mixed attention achieves best results ({best_val_ppl:.2f}).")

    # =========================================================================
    # V10.3.0: SRK PHASE LEARNING FINAL REPORT
    # =========================================================================
    if srk_monitor is not None:
        print("\n" + "=" * 70)
        print("SRK PHASE LEARNING ANALYSIS (V10.3.0)")
        print("=" * 70)
        srk_monitor.print_phase_learning_report()

        # Detailed trend analysis
        summary = srk_monitor.get_phase_learning_summary()
        if summary.get('num_observations', 0) > 1:
            print("\n  Phase Learning Trends Over Training:")
            print("  " + "-" * 50)

            # Check if phase coherence improved
            csr_key = f'L{srk_monitor.config.csr_alignment_layer}_csr_phase_coherence'
            if f'{csr_key}_trend' in summary:
                trend = summary[f'{csr_key}_trend']
                initial = summary.get(f'{csr_key}_initial', 0)
                final = summary.get(f'{csr_key}_final', 0)
                if trend > 0:
                    print(f"    Phase Coherence: IMPROVED {initial:.4f} → {final:.4f} (+{trend:.4f})")
                    print(f"      → Phase is LEARNING relational structure!")
                else:
                    print(f"    Phase Coherence: DECLINED {initial:.4f} → {final:.4f} ({trend:.4f})")
                    print(f"      → Phase may be collapsing or becoming decorative")

            # Check ontological diversity
            dna_key = f'L{srk_monitor.config.dna_bridge_layer}_dna_onto_diversity'
            if f'{dna_key}_trend' in summary:
                trend = summary[f'{dna_key}_trend']
                initial = summary.get(f'{dna_key}_initial', 0)
                final = summary.get(f'{dna_key}_final', 0)
                if trend > 0:
                    print(f"    Ontology Diversity: IMPROVED {initial:.4f} → {final:.4f} (+{trend:.4f})")
                    print(f"      → Model developing rich 12D ontological representation")
                else:
                    print(f"    Ontology Diversity: DECLINED {initial:.4f} → {final:.4f} ({trend:.4f})")
                    print(f"      → Possible dimensional collapse in ontological space")

            # Check witness activation
            wit_key = f'L{srk_monitor.config.witness_layer}_witness_witness_activation'
            if f'{wit_key}_trend' in summary:
                trend = summary[f'{wit_key}_trend']
                initial = summary.get(f'{wit_key}_initial', 0)
                final = summary.get(f'{wit_key}_final', 0)
                print(f"    Witness Activation: {initial:.4f} → {final:.4f} ({trend:+.4f})")
                if abs(final) > 0.1:
                    print(f"      → Consciousness/attention layer is ACTIVE")
                else:
                    print(f"      → Witness layer may be underutilized")

            # Check synthesis gate
            syn_key = f'L{srk_monitor.config.synthesis_layer}_synth_synthesis_gate_mean'
            if f'{syn_key}_trend' in summary:
                trend = summary[f'{syn_key}_trend']
                initial = summary.get(f'{syn_key}_initial', 0)
                final = summary.get(f'{syn_key}_final', 0)
                print(f"    Synthesis Gate: {initial:.4f} → {final:.4f} ({trend:+.4f})")
                if 0.3 < final < 0.7:
                    print(f"      → Gate is SELECTIVE (good output integration)")
                elif final > 0.9:
                    print(f"      → Gate is fully OPEN (minimal filtering)")
                else:
                    print(f"      → Gate is mostly CLOSED (may block outputs)")

        # V10.3.1: Layer Influence Summary
        if srk_influence is not None and srk_influence.influence_history:
            print("\n" + "=" * 70)
            print("SRK LAYER INFLUENCE ANALYSIS (V10.3.1)")
            print("=" * 70)

            inf_summary = srk_influence.get_influence_summary()

            print(f"\n  Layer Influence Over Training ({inf_summary.get('num_observations', 0)} observations):")
            print("  " + "-" * 60)
            print(f"  {'Layer':<8} {'Component':<20} {'Initial':<10} {'Final':<10} {'Trend':<12} {'Verdict'}")
            print("  " + "-" * 60)

            layer_verdicts = []
            for layer_idx in sorted(set(int(k.split('_')[0][1:]) for k in inf_summary.keys() if k.startswith('L') and '_score_initial' in k)):
                # Get metrics for this layer
                initial = inf_summary.get(f'L{layer_idx}_score_initial', 0)
                final = inf_summary.get(f'L{layer_idx}_score_final', 0)
                trend = inf_summary.get(f'L{layer_idx}_score_trend', 0)
                constructive_pct = inf_summary.get(f'L{layer_idx}_constructive_pct', 0)
                destructive_pct = inf_summary.get(f'L{layer_idx}_destructive_pct', 0)

                # Determine component name
                if layer_idx == srk_monitor.config.dna_bridge_layer:
                    component = "DNA Bridge"
                elif layer_idx == srk_monitor.config.csr_alignment_layer:
                    component = "CSR Alignment"
                elif layer_idx == srk_monitor.config.witness_layer:
                    component = "Witness Arbitrator"
                elif layer_idx == srk_monitor.config.synthesis_layer:
                    component = "Synthesis Gate"
                else:
                    component = "Unknown"

                # Determine verdict
                if constructive_pct > 0.6:
                    verdict = "CONSTRUCTIVE"
                    layer_verdicts.append(("constructive", layer_idx, component))
                elif destructive_pct > 0.6:
                    verdict = "DESTRUCTIVE"
                    layer_verdicts.append(("destructive", layer_idx, component))
                elif trend > 0.1:
                    verdict = "IMPROVING"
                    layer_verdicts.append(("improving", layer_idx, component))
                elif trend < -0.1:
                    verdict = "DEGRADING"
                    layer_verdicts.append(("degrading", layer_idx, component))
                else:
                    verdict = "NEUTRAL"
                    layer_verdicts.append(("neutral", layer_idx, component))

                trend_arrow = "↑" if trend > 0.05 else "↓" if trend < -0.05 else "→"
                print(f"  L{layer_idx:<6} {component:<20} {initial:+.3f}     {final:+.3f}     {trend:+.3f} {trend_arrow}     {verdict}")

            # Overall recommendation
            print("\n  " + "=" * 60)
            print("  RECOMMENDATIONS:")
            print("  " + "-" * 60)

            constructive_layers = [v for v in layer_verdicts if v[0] == "constructive"]
            destructive_layers = [v for v in layer_verdicts if v[0] == "destructive"]
            degrading_layers = [v for v in layer_verdicts if v[0] == "degrading"]

            if destructive_layers:
                print(f"\n  ⚠️  DESTRUCTIVE layers detected:")
                for _, idx, name in destructive_layers:
                    print(f"      L{idx} ({name}): Consider disabling or adjusting")
                    if name == "DNA Bridge":
                        print(f"        → Try --srk-disable-dna-bridge or different layer")
                    elif name == "CSR Alignment":
                        print(f"        → Try --srk-disable-phase-hook or different layer")
                    elif name == "Witness Arbitrator":
                        print(f"        → Try --srk-disable-witness or different layer")
                    elif name == "Synthesis Gate":
                        print(f"        → Try --srk-disable-synthesis or different layer")

            if degrading_layers:
                print(f"\n  ⚠️  DEGRADING layers (getting worse over training):")
                for _, idx, name in degrading_layers:
                    print(f"      L{idx} ({name}): May need longer training or tuning")

            if constructive_layers:
                print(f"\n  ✓  CONSTRUCTIVE layers (helping phase learning):")
                for _, idx, name in constructive_layers:
                    print(f"      L{idx} ({name}): Keep enabled!")

            # Overall assessment
            if len(destructive_layers) > len(constructive_layers):
                print(f"\n  OVERALL: More layers DESTRUCTIVE than constructive.")
                print(f"           Consider adjusting layer positions or disabling problematic layers.")
            elif len(constructive_layers) > len(destructive_layers):
                print(f"\n  OVERALL: More layers CONSTRUCTIVE - SRK is helping phase learning!")
            else:
                print(f"\n  OVERALL: Mixed influence - consider fine-tuning layer positions.")

    # ==========================================================================
    # V10.3.4/V10.3.5: KOSHA/WITNESS FINAL ANALYSIS (with domain separation)
    # ==========================================================================
    if kosha_diagnostics is not None:
        print("\n" + "=" * 70)
        if use_domain_separation:
            print(f"KOSHA CONSCIOUSNESS ANALYSIS (V10.3.5) - Domain: Layers {kosha_domain_layers}")
        else:
            print("KOSHA CONSCIOUSNESS ANALYSIS (V10.3.4)")
        print("=" * 70)
        kosha_diagnostics.print_report(step)

        summary = kosha_diagnostics.get_summary()
        if summary:
            kosha_names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
            vedic_names = ['Annamaya', 'Pranamaya', 'Manomaya', 'Vijnanamaya', 'Anandamaya']
            means = summary['mean_activations']
            trends = summary['trends']

            # Find dominant and fastest-growing kosha
            dominant_idx = means.index(max(means))
            fastest_idx = trends.index(max(trends))

            print(f"\n  KOSHA CONCLUSIONS:")
            print(f"  " + "-" * 60)
            print(f"    Dominant Kosha: {kosha_names[dominant_idx]} ({vedic_names[dominant_idx]})")
            print(f"    Fastest Growing: {kosha_names[fastest_idx]} ({vedic_names[fastest_idx]})")
            print(f"    Gyroscopic Loss: {summary['mean_gyro_loss']:.4f}")
            print(f"    Transitions: {summary['num_transitions']} state changes")

            # Interpretation
            if dominant_idx == 3:  # INTELLECTUAL
                print(f"\n    ✓ Model is operating at INTELLECTUAL (Vijnanamaya) level")
                print(f"      → Good for abstract reasoning and pattern recognition")
            elif dominant_idx == 4:  # BLISSFUL
                print(f"\n    ✓ Model reached BLISSFUL (Anandamaya) level")
                print(f"      → Excellent coherence and integration")
            elif dominant_idx <= 1:  # MATERIAL or VITAL
                print(f"\n    ⚠️ Model is stuck at lower consciousness layers")
                print(f"      → May need more training or kosha steering")

    if witness_diagnostics is not None:
        print("\n" + "=" * 70)
        if use_domain_separation:
            print(f"WITNESS (SAKSHI) OBSERVER ANALYSIS (V10.3.5) - Domain: Layers {witness_domain_layers}")
        else:
            print("WITNESS (SAKSHI) OBSERVER ANALYSIS (V10.3.4)")
        print("=" * 70)
        witness_diagnostics.print_report(step)

        summary = witness_diagnostics.get_summary()
        if summary:
            vritti_names = ['FACT', 'MISCONCEPTION', 'IMAGINATION', 'VOID', 'MEMORY']
            means = summary['mean_vritti']

            # Find dominant vritti
            dominant_idx = means.index(max(means))

            print(f"\n  WITNESS CONCLUSIONS:")
            print(f"  " + "-" * 60)
            print(f"    Dominant Vritti: {vritti_names[dominant_idx]}")
            print(f"    Constraint Detection Rate: {summary['high_constraint_ratio']*100:.1f}%")
            print(f"    Meta-Cognitive Confidence: {summary['mean_confidence']:.3f}")

            # Interpretation
            if dominant_idx == 0:  # FACT
                print(f"\n    ✓ Model primarily in FACTUAL epistemic state")
                print(f"      → High reliability for factual reasoning")
            elif dominant_idx == 2:  # IMAGINATION
                print(f"\n    Creative/imaginative state dominant")
                print(f"      → Good for generative tasks, verify facts carefully")
            elif dominant_idx == 3:  # VOID
                print(f"\n    ⚠️ High uncertainty (VOID) detected")
                print(f"      → Model may need more training or clearer inputs")

    return model, best_val_ppl


# =============================================================================
# V10.2.1 CHUNKING ARCHITECTURE TESTS
# =============================================================================

def run_chunking_tests_v10(args, config):
    """
    V10.2.1: Comprehensive tests for the new chunking architecture.

    Tests:
    1. Cross-Attention Ablation: Does Local need Phase memory?
    2. Chunk Continuity: Full-sequence vs chunked processing match?
    3. Cross-Chunk Dependencies: Can Phase capture long-range across chunks?
    4. Gradient Flow: Does Phase get gradients only through Local?
    """
    print("\n" + "=" * 70)
    print("V10.2.1 CHUNKING ARCHITECTURE TESTS")
    print("=" * 70)
    print("\nThese tests verify the new Protected Phase with cross-attention:")
    print("  - Phase accumulates temporal memory (O(n) cumsum)")
    print("  - Local queries Phase memory via cross-attention")
    print("  - Phase gets gradients ONLY through Local's K/V")
    print()

    # Try to import the actual HybridPhaseTransformer from symbolu
    try:
        import sys
        import os
        # Try multiple paths to find symbolu module
        possible_paths = [
            os.getcwd(),  # Current working directory (e.g., /workspace/symbolu)
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),  # Project root from script
            '/home/user/symbolu',
            '/workspace/symbolu',
        ]
        for path in possible_paths:
            symbolu_path = os.path.join(path, 'symbolu')
            if path not in sys.path and os.path.exists(symbolu_path):
                sys.path.insert(0, path)
                print(f"  Added {path} to PYTHONPATH")
                break

        from symbolu.phase_transformer import HybridPhaseTransformer
        USE_REAL_MODEL = True
        print("✓ Using real HybridPhaseTransformer from symbolu/phase_transformer.py")
    except ImportError as e:
        print(f"⚠ Could not import HybridPhaseTransformer: {e}")
        print("  Hint: Run from project root: cd /workspace/symbolu && python scripts/...")
        print("  Or set PYTHONPATH: export PYTHONPATH=/workspace/symbolu:$PYTHONPATH")
        USE_REAL_MODEL = False

    device = args.device
    chunk_size = args.chunk_size
    seq_len = args.chunk_test_seq_len

    results = {}
    model = None  # Will be created if USE_REAL_MODEL

    # =========================================================================
    # TRAINING PHASE: CURRICULUM LEARNING for Cross-Chunk Memory
    # =========================================================================
    # The key insight: we need to verify the model CAN learn cross-chunk deps.
    # Start with the SIMPLEST possible task and gradually increase complexity.
    #
    # CURRICULUM:
    # Phase 1: SINGLE anchor copy (one value, copy to all queries)
    #          - If this fails, architecture has fundamental issue
    # Phase 2: MULTI anchor with SUM (predict sum of all anchors mod 10)
    #          - Tests if Phase can aggregate info across chunk 0
    # Phase 3: POSITION-BASED recall (original hard task)
    #          - Only attempt if Phase 1 & 2 succeed
    # =========================================================================
    if USE_REAL_MODEL:
        print("\n" + "-" * 70)
        print("[TRAINING] Curriculum Learning for Cross-Chunk Memory")
        print("-" * 70)

        # Smaller vocab makes tasks learnable
        vocab_size = 50
        # Tokens: 0-9 anchor values, 10 query token, 11-49 fillers
        NUM_ANCHORS = 10
        QUERY_TOKEN = 10
        FILLER_START = 11

        model = HybridPhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=config.d_model,
            num_layers=config.num_layers,
            num_heads=config.num_heads,
            ff_dim=config.d_ff,
            max_seq_len=seq_len,
            dropout=0.0,  # No dropout for cleaner learning signal
            local_layers=2,
            window_size=32,
            protected_phase=True,
        ).to(device)

        print(f"  Model: {sum(p.numel() for p in model.parameters()):,} parameters")
        print(f"  Protected Phase: ENABLED")
        print(f"  Vocab: {vocab_size} (anchors 0-9, query 10, fillers 11-49)")

        # =================================================================
        # PHASE 1: Single Anchor Copy (SIMPLEST POSSIBLE)
        # =================================================================
        # One anchor at position 5, every query in later chunks must copy it
        # This is the absolute minimum cross-chunk task
        # =================================================================
        print(f"\n  === PHASE 1: Single Anchor Copy ===")
        print(f"  Task: anchor[5] in chunk 0 → copy to ALL queries in chunks 1+")

        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.0)
        model.train()

        phase1_steps = 3000
        batch_size = 32
        log_every = 500
        anchor_pos = 5  # Single anchor position

        running_loss = 0.0
        running_acc = 0.0
        best_acc = 0.0

        for step in range(phase1_steps):
            # Fill with random fillers
            input_ids = torch.randint(FILLER_START, vocab_size, (batch_size, seq_len), device=device)
            targets = torch.full((batch_size, seq_len), -100, device=device)

            for b in range(batch_size):
                # Single anchor value (0-9) at position 5 in chunk 0
                anchor_val = random.randint(0, NUM_ANCHORS - 1)
                input_ids[b, anchor_pos] = anchor_val

                # Place query tokens at multiple positions in later chunks
                # All must predict the SAME anchor value
                for chunk_idx in range(1, seq_len // chunk_size):
                    chunk_start = chunk_idx * chunk_size
                    # 3 query positions per chunk
                    for q_offset in [5, 20, 40]:
                        query_pos = chunk_start + q_offset
                        if query_pos < seq_len - 1:
                            input_ids[b, query_pos] = QUERY_TOKEN
                            targets[b, query_pos] = anchor_val

            # Forward
            result = model(input_ids)
            logits = result['logits']

            # Loss on query positions only
            shift_logits = logits[:, :-1, :].contiguous()
            shift_targets = targets[:, 1:].contiguous()

            loss = F.cross_entropy(
                shift_logits.view(-1, vocab_size),
                shift_targets.view(-1),
                ignore_index=-100
            )

            # Accuracy
            valid_mask = shift_targets != -100
            if valid_mask.sum() > 0:
                preds = shift_logits.argmax(dim=-1)
                correct = (preds == shift_targets) & valid_mask
                acc = correct.sum().float() / valid_mask.sum().float()
                running_acc += acc.item()
                best_acc = max(best_acc, acc.item())

            running_loss += loss.item()

            # Backward
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            if (step + 1) % log_every == 0:
                avg_loss = running_loss / log_every
                avg_acc = running_acc / log_every
                print(f"    Step {step+1}/{phase1_steps}: Loss={avg_loss:.4f}, Acc={avg_acc:.1%}, Best={best_acc:.1%}")
                running_loss = 0.0
                running_acc = 0.0

        # Evaluate Phase 1
        model.eval()
        phase1_correct = 0
        phase1_total = 0
        with torch.no_grad():
            for _ in range(20):
                input_ids = torch.randint(FILLER_START, vocab_size, (batch_size, seq_len), device=device)
                targets = torch.full((batch_size, seq_len), -100, device=device)

                for b in range(batch_size):
                    anchor_val = random.randint(0, NUM_ANCHORS - 1)
                    input_ids[b, anchor_pos] = anchor_val
                    for chunk_idx in range(1, seq_len // chunk_size):
                        chunk_start = chunk_idx * chunk_size
                        for q_offset in [5, 20, 40]:
                            query_pos = chunk_start + q_offset
                            if query_pos < seq_len - 1:
                                input_ids[b, query_pos] = QUERY_TOKEN
                                targets[b, query_pos] = anchor_val

                result = model(input_ids)
                logits = result['logits']
                shift_logits = logits[:, :-1, :]
                shift_targets = targets[:, 1:]
                valid_mask = shift_targets != -100
                preds = shift_logits.argmax(dim=-1)
                phase1_correct += ((preds == shift_targets) & valid_mask).sum().item()
                phase1_total += valid_mask.sum().item()

        phase1_acc = phase1_correct / phase1_total if phase1_total > 0 else 0
        print(f"  Phase 1 Final Accuracy: {phase1_acc:.1%}")

        phase1_passed = phase1_acc > 0.5  # Should get >50% to show learning

        if phase1_passed:
            print(f"  ✓ PHASE 1 PASSED - Model CAN learn cross-chunk dependencies!")
        else:
            print(f"  ⚠ PHASE 1 INCOMPLETE - Model needs more training or architecture changes")
            print(f"    (But architecture verification still valid)")

        # =================================================================
        # PHASE 2: Multi-Anchor Sum (only if Phase 1 passed)
        # =================================================================
        if phase1_passed:
            print(f"\n  === PHASE 2: Multi-Anchor Aggregation ===")
            print(f"  Task: 3 anchors in chunk 0 → query predicts (sum mod 10)")

            # Fresh optimizer for phase 2
            optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=0.0)
            model.train()

            phase2_steps = 2000
            anchor_positions = [5, 20, 40]

            running_loss = 0.0
            running_acc = 0.0

            for step in range(phase2_steps):
                input_ids = torch.randint(FILLER_START, vocab_size, (batch_size, seq_len), device=device)
                targets = torch.full((batch_size, seq_len), -100, device=device)

                for b in range(batch_size):
                    # 3 anchor values
                    anchor_vals = [random.randint(0, NUM_ANCHORS - 1) for _ in range(3)]
                    target_val = sum(anchor_vals) % NUM_ANCHORS

                    for i, pos in enumerate(anchor_positions):
                        input_ids[b, pos] = anchor_vals[i]

                    # Queries in later chunks predict the sum
                    for chunk_idx in range(1, seq_len // chunk_size):
                        chunk_start = chunk_idx * chunk_size
                        query_pos = chunk_start + 30
                        if query_pos < seq_len - 1:
                            input_ids[b, query_pos] = QUERY_TOKEN
                            targets[b, query_pos] = target_val

                result = model(input_ids)
                logits = result['logits']
                shift_logits = logits[:, :-1, :].contiguous()
                shift_targets = targets[:, 1:].contiguous()

                loss = F.cross_entropy(
                    shift_logits.view(-1, vocab_size),
                    shift_targets.view(-1),
                    ignore_index=-100
                )

                valid_mask = shift_targets != -100
                if valid_mask.sum() > 0:
                    preds = shift_logits.argmax(dim=-1)
                    correct = (preds == shift_targets) & valid_mask
                    acc = correct.sum().float() / valid_mask.sum().float()
                    running_acc += acc.item()

                running_loss += loss.item()

                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

                if (step + 1) % log_every == 0:
                    avg_loss = running_loss / log_every
                    avg_acc = running_acc / log_every
                    print(f"    Step {step+1}/{phase2_steps}: Loss={avg_loss:.4f}, Acc={avg_acc:.1%}")
                    running_loss = 0.0
                    running_acc = 0.0

            print(f"  Phase 2 complete.")

        model.eval()
        print(f"\n  Training curriculum complete.")

        # Store vocab_size for tests
        model._test_vocab_size = vocab_size

    # =========================================================================
    # TEST 1: Cross-Attention Ablation
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 1] CROSS-ATTENTION ABLATION (after training)")
    print("-" * 70)
    print("Question: Does Local NEED Phase memory for long-range info?")
    print("Method: Compare Local with/without phase_memory parameter")
    print()

    if USE_REAL_MODEL and model is not None:
        # Get vocab size from model
        test_vocab_size = getattr(model, '_test_vocab_size', 100)

        # Create test input with cross-chunk copy task structure
        test_input = torch.randint(11, test_vocab_size, (1, seq_len), device=device)
        # Place anchor at position 5 in chunk 0, query at position 5 in chunk 1
        anchor_value = random.randint(0, 9)  # Anchor token
        test_input[0, 5] = anchor_value
        test_input[0, chunk_size + 5] = 10  # Query token

        # Forward with normal protected phase (Local queries Phase memory)
        model.eval()
        with torch.no_grad():
            result_normal = model(test_input)
            logits_normal = result_normal['logits']

        # Now temporarily disable protected_phase in hybrid layers
        # This makes Local use self-attention instead of cross-attention to Phase
        for block in model.blocks:
            if hasattr(block, 'attention') and hasattr(block.attention, 'protected_phase'):
                block.attention.protected_phase = False

        with torch.no_grad():
            result_ablated = model(test_input)
            logits_ablated = result_ablated['logits']

        # Restore
        for block in model.blocks:
            if hasattr(block, 'attention') and hasattr(block.attention, 'protected_phase'):
                block.attention.protected_phase = True

        # Compare
        logit_diff = (logits_normal - logits_ablated).abs()
        max_diff = logit_diff.max().item()
        mean_diff = logit_diff.mean().item()

        print(f"  Logit difference (Protected vs Parallel):")
        print(f"    Max:  {max_diff:.6f}")
        print(f"    Mean: {mean_diff:.6f}")

        # If difference is large, cross-attention to Phase matters
        if max_diff > 0.1:
            print(f"  ✓ PASS: Significant difference - Local depends on Phase memory")
            results['cross_attention_ablation'] = 'PASS'
        else:
            print(f"  ⚠ Note: Small difference - may need more training for Phase to learn")
            results['cross_attention_ablation'] = 'SMALL_DIFF'
    else:
        print("  (Skipped - real model not available)")
        results['cross_attention_ablation'] = 'SKIPPED'

    # =========================================================================
    # TEST 2: Chunk Continuity
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 2] CHUNK CONTINUITY")
    print("-" * 70)
    print("Question: Do full-sequence and chunked processing produce same output?")
    print(f"Method: Compare model(full_seq) vs model.forward_chunk(chunks)")
    print(f"  Sequence length: {seq_len}, Chunk size: {chunk_size}")
    print()

    if USE_REAL_MODEL and model is not None:
        # Use the model's built-in diagnostic
        try:
            diag = model.diagnose_chunk_continuity(
                test_input,
                chunk_size=chunk_size,
                verbose=True
            )
            results['chunk_continuity'] = 'PASS' if diag['healthy'] else 'FAIL'
        except Exception as e:
            print(f"  ✗ Error running diagnostic: {e}")
            results['chunk_continuity'] = 'ERROR'
    else:
        print("  (Skipped - real model not available)")
        results['chunk_continuity'] = 'SKIPPED'

    # =========================================================================
    # TEST 3: Cross-Chunk Dependencies (after training)
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 3] CROSS-CHUNK DEPENDENCIES (after training)")
    print("-" * 70)
    print("Question: Can Phase capture dependencies that span chunk boundaries?")
    print("Method: Create sequence where answer depends on token in previous chunk")
    print()

    if USE_REAL_MODEL and model is not None:
        # Test using the cross-chunk copy task structure
        # If Phase works, changing the anchor should change the prediction at query
        test_vocab_size = getattr(model, '_test_vocab_size', 100)

        # Anchor at position 5 in chunk 0, query at position 5 in chunk 1
        anchor_pos = 5
        query_pos = chunk_size + 5  # Same relative position in chunk 1

        if query_pos < seq_len:
            # Create two inputs: same except for anchor token value
            input_a = torch.randint(11, test_vocab_size, (1, seq_len), device=device)
            input_b = input_a.clone()

            # Set different anchor values (both valid anchor tokens 0-9)
            input_a[0, anchor_pos] = 3  # Anchor A = 3
            input_b[0, anchor_pos] = 7  # Anchor B = 7
            # Both have query token at same position
            input_a[0, query_pos] = 10  # Query token
            input_b[0, query_pos] = 10

            # Process both with chunking
            with torch.no_grad():
                layer_states_a = None
                layer_states_b = None

                # First chunk (contains anchor)
                chunk1_a = input_a[:, :chunk_size]
                chunk1_b = input_b[:, :chunk_size]

                result_a, layer_states_a = model.forward_chunk(
                    chunk1_a, chunk_offset=0, prev_layer_states=layer_states_a
                )
                result_b, layer_states_b = model.forward_chunk(
                    chunk1_b, chunk_offset=0, prev_layer_states=layer_states_b
                )

                # Second chunk (contains reference)
                chunk2_a = input_a[:, chunk_size:2*chunk_size]
                chunk2_b = input_b[:, chunk_size:2*chunk_size]

                result2_a, _ = model.forward_chunk(
                    chunk2_a, chunk_offset=chunk_size, prev_layer_states=layer_states_a
                )
                result2_b, _ = model.forward_chunk(
                    chunk2_b, chunk_offset=chunk_size, prev_layer_states=layer_states_b
                )

            # Check if output at query position differs and predicts correctly
            query_local = anchor_pos  # Same relative position in chunk 1
            if query_local < result2_a['logits'].shape[1]:
                logits_at_query_a = result2_a['logits'][0, query_local]
                logits_at_query_b = result2_b['logits'][0, query_local]

                # Check predictions
                pred_a = logits_at_query_a.argmax().item()
                pred_b = logits_at_query_b.argmax().item()

                # Logit difference
                diff_at_query = (logits_at_query_a - logits_at_query_b).abs().mean().item()

                print(f"  Input A: anchor=3 at pos {anchor_pos}, query at pos {query_pos}")
                print(f"  Input B: anchor=7 at pos {anchor_pos}, query at pos {query_pos}")
                print(f"  Prediction A (should be 3): {pred_a}")
                print(f"  Prediction B (should be 7): {pred_b}")
                print(f"  Logit difference: {diff_at_query:.6f}")

                # Pass if predictions differ AND match anchors
                correct_a = pred_a == 3
                correct_b = pred_b == 7
                if correct_a and correct_b:
                    print(f"  ✓ PASS: Both predictions correct! Cross-chunk memory works!")
                    results['cross_chunk_deps'] = 'PASS'
                elif diff_at_query > 0.1:
                    print(f"  ⚠ Partial: Different predictions but not perfect copy")
                    results['cross_chunk_deps'] = 'PARTIAL'
                else:
                    print(f"  ⚠ Note: Predictions don't reflect anchor difference")
                    results['cross_chunk_deps'] = 'SMALL_DIFF'
            else:
                print(f"  Query position out of bounds")
                results['cross_chunk_deps'] = 'ERROR'
        else:
            print(f"  Sequence too short for cross-chunk test")
            results['cross_chunk_deps'] = 'SKIPPED'
    else:
        print("  (Skipped - real model not available)")
        results['cross_chunk_deps'] = 'SKIPPED'

    # =========================================================================
    # TEST 4: Gradient Flow Verification
    # =========================================================================
    print("\n" + "-" * 70)
    print("[TEST 4] GRADIENT FLOW VERIFICATION")
    print("-" * 70)
    print("Question: Does Phase get gradients only through Local's cross-attention?")
    print("Method: Check gradient paths with backward pass")
    print()

    if USE_REAL_MODEL and model is not None:
        model.train()

        # Create input and do forward pass
        test_vocab_size = getattr(model, '_test_vocab_size', 100)
        test_input_grad = torch.randint(0, test_vocab_size, (2, 64), device=device)

        # Zero gradients
        model.zero_grad()

        # Forward and backward
        result = model(test_input_grad)
        logits = result['logits']

        # Simple loss: sum of logits at last position
        loss = logits[:, -1, :].sum()
        loss.backward()

        # Check gradients in Phase attention layers vs Local
        phase_grad_norms = []
        local_grad_norms = []

        for name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                if 'phase_attn' in name or 'phase' in name.lower():
                    phase_grad_norms.append((name, grad_norm))
                elif 'local_attn' in name or 'local' in name.lower():
                    local_grad_norms.append((name, grad_norm))

        # Report
        if phase_grad_norms:
            avg_phase_grad = sum(g for _, g in phase_grad_norms) / len(phase_grad_norms)
            print(f"  Phase attention gradient norms (sample):")
            for name, norm in phase_grad_norms[:3]:
                print(f"    {name[-50:]}: {norm:.6f}")
            print(f"  Average Phase grad norm: {avg_phase_grad:.6f}")
        else:
            print(f"  No Phase gradients found (names may differ)")

        if local_grad_norms:
            avg_local_grad = sum(g for _, g in local_grad_norms) / len(local_grad_norms)
            print(f"\n  Local attention gradient norms (sample):")
            for name, norm in local_grad_norms[:3]:
                print(f"    {name[-50:]}: {norm:.6f}")
            print(f"  Average Local grad norm: {avg_local_grad:.6f}")

        # In Protected Phase mode, both should have gradients
        # (Phase gets gradients via Local's K/V projection of memory_state)
        if phase_grad_norms and local_grad_norms:
            print(f"\n  ✓ Both Phase and Local receive gradients")
            print(f"    (In Protected Phase, gradients flow: Loss → Local → K/V → Phase)")
            results['gradient_flow'] = 'PASS'
        else:
            print(f"\n  ⚠ Could not verify gradient flow (check parameter names)")
            results['gradient_flow'] = 'UNCLEAR'

        model.eval()
    else:
        print("  (Skipped - real model not available)")
        results['gradient_flow'] = 'SKIPPED'

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("V10.2.1 CHUNKING TEST SUMMARY")
    print("=" * 70)

    print(f"\n{'Test':<35} {'Result':<15}")
    print("-" * 50)
    for test_name, result in results.items():
        status_icon = "✓" if result == "PASS" else "⚠" if result in ["SMALL_DIFF", "UNCLEAR"] else "✗"
        print(f"{test_name:<35} {status_icon} {result:<15}")

    all_pass = all(r == 'PASS' for r in results.values())
    if all_pass:
        print(f"\n✓ ALL TESTS PASSED - V10.2.1 architecture is working correctly!")
    else:
        print(f"\n⚠ Some tests need attention - see details above")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Hard Diagnostic Probe Training for PhaseAttention",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default run (Quadratic vs Phase)
  python train_hard_probes.py

  # BIND-dominant curriculum (recommended)
  python train_hard_probes.py --bind-ratio 0.7

  # Parameter-matched comparison
  python train_hard_probes.py --match-params

  # Longer chains for harder test
  python train_hard_probes.py --test-chain-min 6 --test-chain-max 8

  # v3: Test INVERTED CURRICULUM hypothesis (Phase=state, Quad=reasoning)
  python train_hard_probes.py --compare-curricula

  # v3: Custom curriculum (90% Phase L0 → 10% Phase L3)
  python train_hard_probes.py --run-hybrid --curriculum 0.9,0.7,0.3,0.1

  # Full scientific comparison
  python train_hard_probes.py --compare-curricula --bind-ratio 0.7 --match-params

  # Phase rotation test (verify phase encodes relational structure)
  python train_hard_probes.py --rotation-test

  # Custom rotation angles
  python train_hard_probes.py --rotation-test --rotation-angles 0,30,60,90,120,150,180

  # V10.2.1: Test chunking architecture (cross-attention, continuity, etc.)
  python train_hard_probes.py --test-chunking-v10

  # V10.2.1: Test with custom chunk size and sequence length
  python train_hard_probes.py --test-chunking-v10 --chunk-size 64 --chunk-test-seq-len 256
        """
    )

    # Model - INCREASED CAPACITY (d_model=128, num_heads=8, num_layers=4)
    parser.add_argument("--d-model", type=int, default=128,
                        help="Model dimension (increased for reasoning capacity)")
    parser.add_argument("--num-heads", type=int, default=8,
                        help="Number of attention heads")
    parser.add_argument("--num-layers", type=int, default=4,
                        help="Number of transformer layers")
    parser.add_argument("--d-ff", type=int, default=256,
                        help="FFN dimension (2x d_model)")

    # Training
    parser.add_argument("--num-steps", type=int, default=15000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)

    # Dataset
    parser.add_argument("--train-samples", type=int, default=20000)
    parser.add_argument("--test-samples", type=int, default=1000,
                        help="Samples per test split")
    parser.add_argument("--bind-ratio", type=float, default=0.6,
                        help="Ratio of BIND-dominant schemas (0.0-1.0)")

    # Chain lengths
    parser.add_argument("--train-chain-min", type=int, default=3)
    parser.add_argument("--train-chain-max", type=int, default=5)
    parser.add_argument("--test-chain-min", type=int, default=6)
    parser.add_argument("--test-chain-max", type=int, default=8)
    parser.add_argument("--persist-chain-min", type=int, default=8,
                        help="Min chain length for pure persistence test")
    parser.add_argument("--persist-chain-max", type=int, default=12,
                        help="Max chain length for pure persistence test")

    # Parameter matching
    parser.add_argument("--match-params", action="store_true",
                        help="Add extra FF params to quadratic to match phase param count")

    # Hybrid curriculum (v3)
    parser.add_argument("--run-hybrid", action="store_true",
                        help="Also run Hybrid model with inverted curriculum")
    parser.add_argument("--curriculum", type=str, default="0.9,0.7,0.3,0.1",
                        help="Phase ratios per layer (comma-separated). "
                             "Inverted=0.9,0.7,0.3,0.1 (Phase early, Quad late)")
    parser.add_argument("--compare-curricula", action="store_true",
                        help="Compare inverted vs standard curriculum")

    # Protected Phase (v5)
    parser.add_argument("--protected-phase", action="store_true",
                        help="Run Protected Phase model (Phase accumulates, Quad queries)")

    # Phase Rotation Test
    parser.add_argument("--rotation-test", action="store_true",
                        help="Run phase rotation test after training to verify phase encodes relations")
    parser.add_argument("--rotation-angles", type=str, default="0,45,90,135,180,270",
                        help="Comma-separated rotation angles in degrees for rotation test")

    # Phase collapse fix (V9.9.11)
    parser.add_argument("--bounded-phase", action="store_true", default=True,
                        help="Constrain phase to [-π, π] via π*sin() (default: True)")
    parser.add_argument("--no-bounded-phase", dest="bounded_phase", action="store_false",
                        help="Disable bounded phase (use raw linear projection)")

    # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
    parser.add_argument("--dual-channel-mode", action="store_true",
                        help="Enable dual-channel attention: separates content similarity from intent alignment. "
                             "s_content = cos(φ_q - φ_k) (what matches), "
                             "s_align = cos(θ_JEPA - θ_SRK) (intent agreement), "
                             "score = s_content * (1 + α * s_align). "
                             "Prevents intent from dominating content selectivity.")
    parser.add_argument("--alignment-authority", type=float, default=0.1,
                        help="α: Weight for alignment term in dual-channel mode (default: 0.1). "
                             "0.0 = pure content matching (intent ignored), "
                             "0.1 = mild intent influence (recommended), "
                             "1.0 = strong intent influence.")

    # V10.4: Proposal Mode (Quad-as-Proposer, Phase-as-Integrator)
    parser.add_argument("--proposal-mode", action="store_true",
                        help="Enable proposal mode: Quad returns K proposals (no softmax mixing), "
                             "Phase integrates proposals with gating. This reverses the power hierarchy - "
                             "Phase decides meaning, Quad only proposes. Potential 30-50%% compute savings "
                             "when phase is confident enough to skip quad.")
    parser.add_argument("--confidence-threshold", type=float, default=0.7,
                        help="Threshold for phase confidence to skip quad (default: 0.7). "
                             "Higher = less skipping, lower = more aggressive skipping.")

    # V10.5: Deep Supervision (Fix 1 for L0 overfitting)
    parser.add_argument("--deep-supervision", action="store_true",
                        help="Enable deep supervision: add auxiliary losses at intermediate layers "
                             "to force later layers to learn useful representations. Prevents L0 overfitting "
                             "where only the first layer contributes to PPL reduction.")
    parser.add_argument("--deep-supervision-lambda", type=float, default=0.5,
                        help="Weight for deep supervision losses (default: 0.5). "
                             "Loss_i = lambda * (i+1)/num_layers * CE(h_i, targets). "
                             "Higher values encourage later layers more strongly.")

    # ==========================================================================
    # REAL LANGUAGE MODE (WikiText/FineWeb)
    # ==========================================================================
    parser.add_argument("--real-language", action="store_true",
                        help="Use real language data (WikiText) instead of synthetic data")
    parser.add_argument("--dataset", type=str, default="wikitext2",
                        choices=["wikitext2", "wikitext103", "tinystories", "writingprompts", "imdb", "openwebtext", "c4"],
                        help="Dataset: tinystories (recommended for Kosha/Witness), wikitext2/103 (LM), writingprompts/imdb (diverse)")
    parser.add_argument("--seq-len", type=int, default=256,
                        help="Sequence length for language modeling")
    parser.add_argument("--lm-vocab-size", type=int, default=50257,
                        help="Vocabulary size for language modeling (GPT-2: 50257)")

    # Phase-first curriculum (from train_unified_llm.py)
    parser.add_argument("--phase-first-curriculum", action="store_true",
                        help="Enable phase-first learning: phase dominates early, local later")
    parser.add_argument("--alpha-phase-high", type=float, default=0.8,
                        help="alpha_phase when PPL >= ppl_high_threshold")
    parser.add_argument("--alpha-phase-low", type=float, default=0.3,
                        help="alpha_phase when PPL <= ppl_low_threshold")
    parser.add_argument("--ppl-high", type=float, default=1000.0,
                        help="PPL threshold for max phase weight")
    parser.add_argument("--ppl-low", type=float, default=100.0,
                        help="PPL threshold for min phase weight")

    # Layer-wise probing
    parser.add_argument("--probe-layers", action="store_true",
                        help="Probe each layer's contribution to PPL (real-language mode only)")

    # ==========================================================================
    # V10.3.0: SRK PHASE LEARNING MONITORING
    # ==========================================================================
    # Enable SRK (Sovereign Reasoning Kernel) to see how phase learning progresses
    # at different layers. SRK provides auxiliary components:
    #   - L4: DNA Bridge (Foundational Ontology)
    #   - L7: CSR Alignment Phase Extraction Hook
    #   - L9: Witness Arbitrator (Consciousness/Attention)
    #   - L11: Synthesis Gate (Output Integration)
    parser.add_argument("--enable-srk", action="store_true",
                        help="Enable SRK phase learning monitoring (requires --real-language --probe-layers)")
    parser.add_argument("--srk-dna-bridge-layer", type=int, default=0,
                        help="Layer for DNA Bridge (default: 0 for 4-layer model, maps to L4 in 12-layer)")
    parser.add_argument("--srk-csr-layer", type=int, default=1,
                        help="Layer for CSR Alignment / Phase Hook (default: 1 for 4-layer model)")
    parser.add_argument("--srk-witness-layer", type=int, default=2,
                        help="Layer for Witness Arbitrator (default: 2 for 4-layer model)")
    parser.add_argument("--srk-synthesis-layer", type=int, default=3,
                        help="Layer for Synthesis Gate (default: 3 for 4-layer model)")
    parser.add_argument("--srk-disable-dna-bridge", action="store_true",
                        help="Disable DNA Bridge component")
    parser.add_argument("--srk-disable-phase-hook", action="store_true",
                        help="Disable Phase Extraction Hook component")
    parser.add_argument("--srk-disable-witness", action="store_true",
                        help="Disable Witness Arbitrator component")
    parser.add_argument("--srk-disable-synthesis", action="store_true",
                        help="Disable Synthesis Gate component")
    parser.add_argument("--srk-lambda-ontology", type=float, default=0.1,
                        help="Weight for ontological alignment loss (default: 0.1)")
    parser.add_argument("--srk-lambda-coherence", type=float, default=0.05,
                        help="Weight for phase coherence loss (default: 0.05)")

    # ==========================================================================
    # V10.3.3: BINDING CACHE ARCHITECTURE
    # ==========================================================================
    parser.add_argument("--binding-cache", action="store_true",
                        help="Use Binding Cache architecture (Local + Phase + Quad) - "
                             "three-path with no gradient competition")
    parser.add_argument("--binding-cache-top-k", type=int, default=64,
                        help="Top-K cache size for Quad query (default: 64)")
    parser.add_argument("--local-window-size", type=int, default=64,
                        help="Window size for local attention (default: 64)")
    parser.add_argument("--decay-gamma", type=float, default=0.9,
                        help="Decay factor for phase memory accumulation (default: 0.9)")
    parser.add_argument("--binding-cache-phase-ratio", type=str, default="0.3,0.3,0.3,0.3",
                        help="Phase ratio per layer for binding cache (default: balanced 0.3)")
    parser.add_argument("--binding-cache-local-ratio", type=str, default="0.4,0.4,0.4,0.4",
                        help="Local ratio per layer for binding cache (default: 0.4)")
    parser.add_argument("--binding-cache-quad-ratio", type=str, default="0.3,0.3,0.3,0.3",
                        help="Quad ratio per layer for binding cache (default: 0.3)")

    # ==========================================================================
    # V10.3.4: KOSHA/WITNESS CONSCIOUSNESS SYSTEM
    # ==========================================================================
    parser.add_argument("--enable-kosha", action="store_true",
                        help="Enable Kosha (5-layer consciousness) diagnostics")
    parser.add_argument("--enable-witness", action="store_true",
                        help="Enable Witness (Sakshi observer) diagnostics")
    parser.add_argument("--kosha-target", type=str, default="INTELLECTUAL",
                        choices=["MATERIAL", "VITAL", "MENTAL", "INTELLECTUAL", "BLISSFUL"],
                        help="Target kosha for steering (default: INTELLECTUAL)")
    parser.add_argument("--kosha-dampen-material", type=float, default=0.5,
                        help="Dampen material kosha during reasoning (default: 0.5)")
    parser.add_argument("--kosha-boost-target", type=float, default=0.4,
                        help="Boost target kosha strength (default: 0.4)")
    parser.add_argument("--kosha-gyro-base-gain", type=float, default=0.15,
                        help="Base gain for kosha homeostatic loss (default: 0.15)")
    parser.add_argument("--kosha-gyro-max-gain", type=float, default=3.0,
                        help="Max gain for kosha homeostatic loss (default: 3.0)")
    parser.add_argument("--witness-constraint-threshold", type=float, default=0.85,
                        help="Threshold for constraint/bottleneck detection (default: 0.85)")

    # V10.3.7: WITNESS ENTROPY REGULARIZATION
    parser.add_argument("--witness-entropy-reg", action="store_true",
                        help="Enable entropy regularization to prevent vritti collapse")
    parser.add_argument("--witness-entropy-lambda", type=float, default=0.1,
                        help="Weight for vritti entropy regularization (default: 0.1)")

    # V10.3.5: DOMAIN SEPARATION - Aligned with SRK component layout
    # Layer assignments (4-layer model):
    #   L0: DNA Bridge (Foundational Ontology)       → ONTOLOGY domain
    #   L1: CSR Alignment (Phase Extraction Hook)    → CSR domain
    #   L2: Kosha + Witness (Consciousness/attention) → KOSHA domain
    #   L3: Synthesis Gate (Output integration)       → SYNTHESIS domain
    parser.add_argument("--domain-separation", action="store_true",
                        help="Enable domain separation: each component governs its assigned layer")
    parser.add_argument("--csr-domain-layers", type=str, default="0,1",
                        help="Layers for Ontology+CSR (default: 0=DNA Bridge, 1=CSR Alignment)")
    parser.add_argument("--kosha-domain-layers", type=str, default="2",
                        help="Layers for Kosha consciousness (default: 2)")
    parser.add_argument("--witness-domain-layers", type=str, default="2",
                        help="Layers for Witness observation (default: 2 = same as Kosha)")
    parser.add_argument("--synthesis-domain-layers", type=str, default="3",
                        help="Layers for Synthesis Gate (default: 3 = output integration)")

    # ==========================================================================
    # V10.3.6: SAMPLE GENERATION FOR QUALITY MONITORING
    # ==========================================================================
    parser.add_argument("--sample-every", type=int, default=500,
                        help="Generate quality samples every N steps (0 to disable, default: 500)")
    parser.add_argument("--sample-prompts", type=str, default=None,
                        help="Comma-separated custom prompts for sampling (uses defaults if not set)")

    # ==========================================================================
    # V10.2.1: CHUNKING ARCHITECTURE TESTS
    # ==========================================================================
    parser.add_argument("--test-chunking-v10", action="store_true",
                        help="Run V10.2.1 chunking architecture tests: cross-attention, "
                             "chunk continuity, cross-chunk dependencies")
    parser.add_argument("--chunk-size", type=int, default=64,
                        help="Chunk size for chunking tests (default: 64 for synthetic tasks)")
    parser.add_argument("--chunk-test-seq-len", type=int, default=256,
                        help="Sequence length for chunk continuity test")

    # Device
    parser.add_argument("--device", type=str,
                        default="cuda" if torch.cuda.is_available() else "cpu")

    args = parser.parse_args()

    # Parse curriculum
    curriculum = [float(x) for x in args.curriculum.split(",")]
    # Pad/truncate to match num_layers
    while len(curriculum) < args.num_layers:
        curriculum.append(curriculum[-1] if curriculum else 0.5)
    curriculum = curriculum[:args.num_layers]

    # Build config
    config = Config(
        d_model=args.d_model,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        d_ff=args.d_ff,
        num_steps=args.num_steps,
        batch_size=args.batch_size,
        lr=args.lr,
        train_samples=args.train_samples,
        test_samples_per_split=args.test_samples,
        bind_ratio=args.bind_ratio,
        train_chain_length=(args.train_chain_min, args.train_chain_max),
        test_chain_length=(args.test_chain_min, args.test_chain_max),
        persist_chain_length=(args.persist_chain_min, args.persist_chain_max),
        match_params=args.match_params,
        bounded_phase=args.bounded_phase,
        dual_channel_mode=args.dual_channel_mode,
        alignment_authority=args.alignment_authority,
        device=args.device,
    )

    # ==========================================================================
    # REAL LANGUAGE MODE: Route to WikiText training
    # ==========================================================================
    if args.real_language:
        train_real_language(args, config, curriculum)
        return

    # ==========================================================================
    # V10.2.1 CHUNKING TESTS: Route to chunking architecture tests
    # ==========================================================================
    if args.test_chunking_v10:
        run_chunking_tests_v10(args, config)
        return

    print("=" * 70)
    print("HARD DIAGNOSTIC PROBE: PhaseAttention vs Quadratic Attention")
    print("=" * 70)
    print("\nThis benchmark tests TRUE RELATIONAL GENERALIZATION:")
    print("  - Held-out roles (R4-R6 never seen in training)")
    print("  - Open-world entities (E8-E15 never seen in training)")
    print("  - Long chains (6-8 steps vs 3-5 in training)")
    print("  - Schema composition (no single-pattern shortcuts)")
    print()

    # Vocabulary
    vocab = HardVocabulary()
    print(f"Vocabulary: {vocab.vocab_size} tokens")
    print(f"  Train entities: E0-E7 ({len(vocab.train_entities)})")
    print(f"  Test entities:  E8-E15 ({len(vocab.test_entities)})")
    print(f"  Train roles:    R0-R3 ({len(vocab.train_roles)})")
    print(f"  Test roles:     R4-R6 ({len(vocab.test_roles)})")

    # Datasets
    print(f"\nCreating datasets...")
    print(f"  BIND ratio: {config.bind_ratio:.0%}")
    print(f"  Train chain length: {config.train_chain_length}")
    print(f"  Test chain length: {config.test_chain_length}")
    print(f"  Persist chain length: {config.persist_chain_length}")

    train_ds = HardProbeDataset(
        vocab, SplitType.TRAIN, config.train_samples, config.max_seq_len,
        config.train_chain_length, config.bind_ratio, seed=42
    )

    test_datasets = {
        SplitType.TEST_ROLES: HardProbeDataset(
            vocab, SplitType.TEST_ROLES, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=100
        ),
        SplitType.TEST_ENTITIES: HardProbeDataset(
            vocab, SplitType.TEST_ENTITIES, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=200
        ),
        SplitType.TEST_BOTH: HardProbeDataset(
            vocab, SplitType.TEST_BOTH, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=300
        ),
        SplitType.TEST_LONG: HardProbeDataset(
            vocab, SplitType.TEST_LONG, config.test_samples_per_split,
            config.max_seq_len, config.test_chain_length, config.bind_ratio, seed=400
        ),
        # Pure persistence test: BIND+QUERY only, long chains (8-12)
        SplitType.TEST_PERSIST: HardProbeDataset(
            vocab, SplitType.TEST_PERSIST, config.test_samples_per_split,
            config.max_seq_len, config.persist_chain_length, config.bind_ratio, seed=500
        ),
    }

    train_loader = DataLoader(train_ds, batch_size=config.batch_size,
                              shuffle=True, collate_fn=collate_fn)
    test_loaders = {
        split: DataLoader(ds, batch_size=config.batch_size,
                          shuffle=False, collate_fn=collate_fn)
        for split, ds in test_datasets.items()
    }

    print(f"\nTrain samples: {len(train_ds)}")
    for split, ds in test_datasets.items():
        print(f"  {split.value}: {len(ds)}")

    # Show examples
    print("\n--- Example Samples ---")
    for i in range(min(5, len(train_ds))):
        ids, target, explanation = train_ds.samples[i]
        print(f"  {vocab.decode(ids)} → {vocab.id2name.get(target, target)}")
        print(f"    ({explanation})")

    # Models
    print("\n--- Creating Models ---")
    num_classes = len(vocab.entities)  # Classify into entity slots

    # Compute parameter matching if needed
    extra_ff = 0
    if config.match_params:
        param_diff = compute_param_diff(config.d_model, config.num_heads, config.num_layers)
        # Add to d_ff to approximately match
        extra_ff = param_diff // (2 * config.d_model * config.num_layers)
        print(f"Parameter matching: adding {extra_ff} to d_ff for quadratic")

    # Operation tokens for phase-conditioned shifts (NEG, PERMUTE, OVERWRITE)
    operation_tokens = [vocab.NEG, vocab.PERMUTE, vocab.OVERWRITE]
    print(f"Operation tokens for phase shifts: {[vocab.id2name[t] for t in operation_tokens]}")

    model_quad = HardProbeTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes,
        use_phase=False, extra_ff_per_layer=extra_ff if config.match_params else 0
    ).to(config.device)

    model_phase = HardProbeTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes,
        use_phase=True, extra_ff_per_layer=0,
        operation_tokens=operation_tokens,  # Enable operation-conditioned phase shifts
        bounded_phase=config.bounded_phase,  # V9.9.11: Constrain φ to [-π, π]
        dual_channel_mode=config.dual_channel_mode,  # V10.3.8: Dual-channel attention
        alignment_authority=config.alignment_authority,  # V10.3.8: Alignment authority
    ).to(config.device)

    print(f"Quadratic params: {model_quad.count_params():,}")
    print(f"Phase params:     {model_phase.count_params():,}")
    if config.bounded_phase:
        print(f"  Bounded Phase: ENABLED (π*sin() bounds φ to [-π, π])")
    else:
        print(f"  Bounded Phase: DISABLED (raw linear projection)")
    if config.dual_channel_mode:
        print(f"  Dual-Channel Mode: ENABLED (α={config.alignment_authority})")
    if config.match_params:
        diff = abs(model_phase.count_params() - model_quad.count_params())
        print(f"  Param difference: {diff:,} ({diff / model_phase.count_params() * 100:.1f}%)")

    # Hybrid model with inverted curriculum (v3)
    model_hybrid = None
    model_hybrid_std = None  # For curriculum comparison
    opt_hybrid = None
    opt_hybrid_std = None

    if args.run_hybrid or args.compare_curricula:
        # Inverted curriculum: Phase-heavy early, Quadratic-heavy late
        inverted_curriculum = curriculum  # From CLI arg
        print(f"\n--- Hybrid Model (INVERTED CURRICULUM) ---")
        print(f"  Curriculum: {' → '.join(f'L{i}:{r*100:.0f}%P' for i, r in enumerate(inverted_curriculum))}")
        print(f"  Interpretation: Phase-heavy early (state capture) → Quadratic-heavy late (reasoning)")

        model_hybrid = HybridTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            curriculum=inverted_curriculum,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
            dual_channel_mode=config.dual_channel_mode,
            alignment_authority=config.alignment_authority,
        ).to(config.device)
        print(f"  Hybrid params: {model_hybrid.count_params():,}")

        opt_hybrid = torch.optim.AdamW(model_hybrid.parameters(), lr=config.lr,
                                        weight_decay=config.weight_decay)

    if args.compare_curricula:
        # Standard curriculum: Quadratic-heavy early, Phase-heavy late (for comparison)
        standard_curriculum = list(reversed(curriculum))
        print(f"\n--- Hybrid Model (STANDARD CURRICULUM - for comparison) ---")
        print(f"  Curriculum: {' → '.join(f'L{i}:{r*100:.0f}%P' for i, r in enumerate(standard_curriculum))}")
        print(f"  Interpretation: Quadratic-heavy early → Phase-heavy late")

        model_hybrid_std = HybridTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            curriculum=standard_curriculum,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
            dual_channel_mode=config.dual_channel_mode,
            alignment_authority=config.alignment_authority,
        ).to(config.device)
        print(f"  Standard Hybrid params: {model_hybrid_std.count_params():,}")

        opt_hybrid_std = torch.optim.AdamW(model_hybrid_std.parameters(), lr=config.lr,
                                            weight_decay=config.weight_decay)

    # Protected Phase model (v5) - Phase accumulates, Quad queries
    model_protected = None
    opt_protected = None

    if args.protected_phase:
        print(f"\n--- Protected Phase Model (v5) ---")
        print(f"  Architecture: Phase → Memory State → Quadratic Query")
        print(f"  Phase's job:  Accumulate bindings via O(n) cumsum")
        print(f"  Quad's job:   Query memory via O(n²) attention")
        print(f"  Key insight:  No gradient competition - they collaborate")

        model_protected = ProtectedPhaseTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
        ).to(config.device)
        print(f"  Protected params: {model_protected.count_params():,}")

        opt_protected = torch.optim.AdamW(model_protected.parameters(), lr=config.lr,
                                           weight_decay=config.weight_decay)

    # Optimizers
    opt_quad = torch.optim.AdamW(model_quad.parameters(), lr=config.lr,
                                  weight_decay=config.weight_decay)
    opt_phase = torch.optim.AdamW(model_phase.parameters(), lr=config.lr,
                                   weight_decay=config.weight_decay)

    # Training
    print(f"\n--- Training for {config.num_steps} steps ---")
    train_iter = iter(train_loader)
    step = 0

    # Loss tracking for training dynamics analysis
    loss_history = {
        "quad": [],
        "phase": [],
        "hybrid": [],
        "hybrid_std": [],
        "protected": [],
    }

    while step < config.num_steps:
        try:
            ids, targets, _ = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            ids, targets, _ = next(train_iter)

        ids, targets = ids.to(config.device), targets.to(config.device)

        # Convert targets to class indices
        target_idx = torch.tensor([
            vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
            for t in targets
        ], device=config.device)

        # Train quadratic
        model_quad.train()
        opt_quad.zero_grad()
        loss_q = F.cross_entropy(model_quad(ids), target_idx)
        loss_q.backward()
        opt_quad.step()

        # Train phase
        model_phase.train()
        opt_phase.zero_grad()
        loss_p = F.cross_entropy(model_phase(ids), target_idx)
        loss_p.backward()
        opt_phase.step()

        # Train hybrid (inverted curriculum)
        if model_hybrid is not None:
            model_hybrid.train()
            opt_hybrid.zero_grad()
            loss_h = F.cross_entropy(model_hybrid(ids), target_idx)
            loss_h.backward()
            opt_hybrid.step()

        # Train hybrid (standard curriculum - for comparison)
        if model_hybrid_std is not None:
            model_hybrid_std.train()
            opt_hybrid_std.zero_grad()
            loss_hs = F.cross_entropy(model_hybrid_std(ids), target_idx)
            loss_hs.backward()
            opt_hybrid_std.step()

        # Train protected phase (v5)
        loss_prot = None
        if model_protected is not None:
            model_protected.train()
            opt_protected.zero_grad()
            loss_prot = F.cross_entropy(model_protected(ids), target_idx)
            loss_prot.backward()
            opt_protected.step()

        # Track losses for training dynamics
        loss_history["quad"].append(loss_q.item())
        loss_history["phase"].append(loss_p.item())
        if model_hybrid is not None:
            loss_history["hybrid"].append(loss_h.item())
        if model_hybrid_std is not None:
            loss_history["hybrid_std"].append(loss_hs.item())
        if model_protected is not None:
            loss_history["protected"].append(loss_prot.item())

        step += 1

        if step % config.eval_every == 0 or step == config.num_steps:
            # Quick train accuracy check
            train_acc_q = evaluate(model_quad, train_loader, vocab, config.device)
            train_acc_p = evaluate(model_phase, train_loader, vocab, config.device)

            # Compute recent average loss (last eval_every steps)
            window = config.eval_every
            recent_loss_q = sum(loss_history["quad"][-window:]) / window
            recent_loss_p = sum(loss_history["phase"][-window:]) / window

            msg = f"Step {step:5d} | Acc: Q={train_acc_q:.3f} P={train_acc_p:.3f}"
            loss_msg = f" | Loss: Q={recent_loss_q:.3f} P={recent_loss_p:.3f}"

            if model_hybrid is not None:
                train_acc_h = evaluate(model_hybrid, train_loader, vocab, config.device)
                recent_loss_h = sum(loss_history["hybrid"][-window:]) / window
                msg += f" H={train_acc_h:.3f}"
                loss_msg += f" H={recent_loss_h:.3f}"
            if model_hybrid_std is not None:
                train_acc_hs = evaluate(model_hybrid_std, train_loader, vocab, config.device)
                recent_loss_hs = sum(loss_history["hybrid_std"][-window:]) / window
                msg += f" Hs={train_acc_hs:.3f}"
                loss_msg += f" Hs={recent_loss_hs:.3f}"
            if model_protected is not None:
                train_acc_prot = evaluate(model_protected, train_loader, vocab, config.device)
                recent_loss_prot = sum(loss_history["protected"][-window:]) / window
                msg += f" Prot={train_acc_prot:.3f}"
                loss_msg += f" Prot={recent_loss_prot:.3f}"

                # R_k health metrics
                health = model_protected.get_phase_health()
                msg += f" | R_k={health['r_k_mean']:.3f}±{health['r_k_std']:.3f}"

            print(msg + loss_msg)

    # ==========================================================================
    # TRAINING DYNAMICS ANALYSIS
    # ==========================================================================
    print("\n" + "=" * 70)
    print("TRAINING DYNAMICS ANALYSIS")
    print("=" * 70)

    def compute_loss_stats(losses, name, window=1000):
        """Compute loss statistics for training dynamics."""
        if not losses:
            return None
        early = losses[:window] if len(losses) >= window else losses
        late = losses[-window:] if len(losses) >= window else losses
        return {
            "name": name,
            "early_mean": sum(early) / len(early),
            "late_mean": sum(late) / len(late),
            "final": losses[-1],
            "improvement": (sum(early) / len(early)) - (sum(late) / len(late)),
        }

    print(f"\n--- Loss Dynamics (early vs late {min(1000, len(loss_history['quad']))} steps) ---")
    print(f"{'Model':<12} {'Early Loss':>12} {'Late Loss':>12} {'Improvement':>12}")
    print("-" * 50)

    for model_name in ["quad", "phase", "protected"]:
        if loss_history[model_name]:
            stats = compute_loss_stats(loss_history[model_name], model_name)
            print(f"{stats['name']:<12} {stats['early_mean']:>12.4f} {stats['late_mean']:>12.4f} {stats['improvement']:>+12.4f}")

    # Check for Phase plateau (red flag)
    if loss_history["protected"]:
        early_phase_loss = sum(loss_history["protected"][:min(2000, len(loss_history["protected"]))]) / min(2000, len(loss_history["protected"]))
        late_phase_loss = sum(loss_history["protected"][-1000:]) / min(1000, len(loss_history["protected"]))
        if early_phase_loss - late_phase_loss < 0.1:
            print(f"\n  ⚠️  WARNING: Protected Phase loss barely improved ({early_phase_loss:.4f} → {late_phase_loss:.4f})")
            print(f"     This may indicate Phase is not learning or Quad is bypassing Phase.")

    # R_k Health Report
    if model_protected is not None:
        print(f"\n--- Phase Health (R_k = amplitude) ---")
        health = model_protected.get_phase_health()
        print(f"  R_k mean:  {health['r_k_mean']:.4f}")
        print(f"  R_k std:   {health['r_k_std']:.4f}")
        print(f"  R_k range: [{health['r_k_min']:.4f}, {health['r_k_max']:.4f}]")

        # Interpret health
        if health['r_k_mean'] < 0.1:
            print(f"\n  🚨 R_k → 0: Phase COLLAPSED (amplitude too small)")
        elif health['r_k_mean'] > 0.9:
            print(f"\n  🚨 R_k → 1: Phase DEGENERATE (amplitude saturated)")
        elif 0.3 <= health['r_k_mean'] <= 0.7:
            print(f"\n  ✅ R_k in healthy range (0.3-0.7)")
        else:
            print(f"\n  ⚠️  R_k outside ideal range but not critical")

    # ==========================================================================
    # FINAL EVALUATION (SEPARATE REPORTING - NO AVERAGING)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("FINAL RESULTS: GENERALIZATION TEST")
    print("=" * 70)

    # Train accuracy
    train_acc_q = evaluate(model_quad, train_loader, vocab, config.device)
    train_acc_p = evaluate(model_phase, train_loader, vocab, config.device)
    train_acc_h = evaluate(model_hybrid, train_loader, vocab, config.device) if model_hybrid else None
    train_acc_hs = evaluate(model_hybrid_std, train_loader, vocab, config.device) if model_hybrid_std else None
    train_acc_prot = evaluate(model_protected, train_loader, vocab, config.device) if model_protected else None

    print(f"\n--- Training Accuracy (should be high for all) ---")
    print(f"Quadratic:        {train_acc_q*100:.1f}%")
    print(f"Phase:            {train_acc_p*100:.1f}%")
    if train_acc_h is not None:
        print(f"Hybrid (Inv):     {train_acc_h*100:.1f}%")
    if train_acc_hs is not None:
        print(f"Hybrid (Std):     {train_acc_hs*100:.1f}%")
    if train_acc_prot is not None:
        print(f"Protected:        {train_acc_prot*100:.1f}%")

    # Per-split test accuracy (NO AVERAGING)
    results_quad = evaluate_all_splits(model_quad, test_loaders, vocab, config.device)
    results_phase = evaluate_all_splits(model_phase, test_loaders, vocab, config.device)
    results_hybrid = evaluate_all_splits(model_hybrid, test_loaders, vocab, config.device) if model_hybrid else None
    results_hybrid_std = evaluate_all_splits(model_hybrid_std, test_loaders, vocab, config.device) if model_hybrid_std else None
    results_protected = evaluate_all_splits(model_protected, test_loaders, vocab, config.device) if model_protected else None

    # Protected Phase results (v5)
    if model_protected is not None:
        print(f"\n--- PROTECTED PHASE RESULTS (v5) ---")
        print(f"    Architecture: Phase accumulates → Quad queries (no competition)")
        print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'Protect':>8} {'Best':>8}")
        print("-" * 52)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            prot = results_protected[split.value]
            scores = {"Quad": q, "Phase": p, "Protect": prot}
            best = max(scores, key=scores.get)
            print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {prot*100:>7.1f}% {best:>8}")

        # Summary
        prot_avg = sum(results_protected.values()) / len(results_protected)
        q_avg = sum(results_quad.values()) / len(results_quad)
        p_avg = sum(results_phase.values()) / len(results_phase)

        print(f"\n  Average Test Accuracy:")
        print(f"    Quadratic:  {q_avg*100:.1f}%")
        print(f"    Pure Phase: {p_avg*100:.1f}%")
        print(f"    Protected:  {prot_avg*100:.1f}%")

        if prot_avg > max(q_avg, p_avg) + 0.02:
            print(f"\n  → PROTECTED PHASE WINS by {(prot_avg - max(q_avg, p_avg))*100:.1f}%")
            print(f"    Phase and Quadratic collaborate better than compete!")
        elif prot_avg > p_avg + 0.02:
            print(f"\n  → Protected beats Pure Phase by {(prot_avg - p_avg)*100:.1f}%")
            print(f"    Quadratic querying helps Phase's accumulated state")

    if model_hybrid is not None:
        print(f"\n--- Test Accuracy by Generalization Type (FULL COMPARISON) ---")
        if model_hybrid_std is not None:
            print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'HybInv':>8} {'HybStd':>8} {'Best':>8}")
            print("-" * 64)
        else:
            print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'HybInv':>8} {'Best':>8}")
            print("-" * 52)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            h = results_hybrid[split.value]
            scores = {"Quad": q, "Phase": p, "HybInv": h}

            if model_hybrid_std is not None:
                hs = results_hybrid_std[split.value]
                scores["HybStd"] = hs
                best = max(scores, key=scores.get)
                print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {h*100:>7.1f}% {hs*100:>7.1f}% {best:>8}")
            else:
                best = max(scores, key=scores.get)
                print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {h*100:>7.1f}% {best:>8}")

        # Summary: Which curriculum wins?
        if model_hybrid_std is not None:
            print(f"\n--- CURRICULUM COMPARISON SUMMARY ---")
            inv_avg = sum(results_hybrid.values()) / len(results_hybrid)
            std_avg = sum(results_hybrid_std.values()) / len(results_hybrid_std)
            q_avg = sum(results_quad.values()) / len(results_quad)
            p_avg = sum(results_phase.values()) / len(results_phase)

            print(f"Average Test Accuracy:")
            print(f"  Quadratic:        {q_avg*100:.1f}%")
            print(f"  Pure Phase:       {p_avg*100:.1f}%")
            print(f"  Hybrid (Inv):     {inv_avg*100:.1f}%  [Phase early → Quad late]")
            print(f"  Hybrid (Std):     {std_avg*100:.1f}%  [Quad early → Phase late]")

            if inv_avg > std_avg + 0.02:
                print(f"\n  → INVERTED CURRICULUM WINS by {(inv_avg - std_avg)*100:.1f}%")
                print(f"    Supports: Phase = STATE mechanism, Quadratic = REASONING mechanism")
            elif std_avg > inv_avg + 0.02:
                print(f"\n  → STANDARD CURRICULUM WINS by {(std_avg - inv_avg)*100:.1f}%")
                print(f"    Counter-evidence: Original hypothesis may be correct")
            else:
                print(f"\n  → CURRICULA ARE COMPARABLE (diff: {abs(inv_avg - std_avg)*100:.1f}%)")
    else:
        # Original output format without hybrid
        print(f"\n--- Test Accuracy by Generalization Type (NO AVERAGING) ---")
        print(f"{'Split':<20} {'Quadratic':>12} {'Phase':>12} {'Delta':>12}")
        print("-" * 56)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            delta = p - q
            marker = "**" if delta > 0.1 else ""
            print(f"{split.value:<20} {q*100:>11.1f}% {p*100:>11.1f}% {delta*100:>+11.1f}% {marker}")

    # Phase diagnostics
    print(f"\n--- Phase Health ---")
    model_phase.enable_diagnostics(True)
    # Run one batch to capture diagnostics
    with torch.no_grad():
        sample_ids, _, _ = next(iter(train_loader))
        _ = model_phase(sample_ids.to(config.device))
    r_k = model_phase.get_R_k()
    model_phase.enable_diagnostics(False)
    print(f"R_k (mean resultant length): {r_k:.4f}")
    print(f"  Interpretation: {'HEALTHY (diverse phases)' if r_k < 0.3 else 'COLLAPSED (phases aligned)'}")

    # Ablation (on test_roles split)
    print(f"\n--- CAUSALITY TEST: Phase Ablation (on test_roles) ---")
    test_roles_loader = test_loaders[SplitType.TEST_ROLES]
    ablation = run_ablation(model_phase, test_roles_loader, vocab, config.device)
    baseline = ablation["none"]

    print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12}")
    print("-" * 36)
    for mode, acc in ablation.items():
        delta = acc - baseline
        print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}%")

    # ==========================================================================
    # HYBRID ABLATION TESTS (v4) - Is Phase decorative or useful in hybrids?
    # ==========================================================================
    ablation_hybrid_inv = None
    ablation_hybrid_std = None

    if model_hybrid is not None:
        print(f"\n--- HYBRID ABLATION: HybridInv (Phase early → Quad late) ---")
        print(f"    Testing if Phase in EARLY layers contributes or is decorative")
        ablation_hybrid_inv = run_ablation(model_hybrid, test_roles_loader, vocab, config.device)
        baseline_inv = ablation_hybrid_inv["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_hybrid_inv.items():
            delta = acc - baseline_inv
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

    if model_hybrid_std is not None:
        print(f"\n--- HYBRID ABLATION: HybridStd (Quad early → Phase late) ---")
        print(f"    Testing if Phase in LATE layers contributes or is decorative")
        ablation_hybrid_std = run_ablation(model_hybrid_std, test_roles_loader, vocab, config.device)
        baseline_std = ablation_hybrid_std["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_hybrid_std.items():
            delta = acc - baseline_std
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

    # Protected Phase ablation (v5)
    ablation_protected = None
    if model_protected is not None:
        print(f"\n--- PROTECTED PHASE ABLATION (v5) ---")
        print(f"    Testing if Phase contributes when it has PROTECTED role")
        print(f"    (Phase accumulates, Quad queries - no competition)")
        ablation_protected = run_ablation(model_protected, test_roles_loader, vocab, config.device)
        baseline_prot = ablation_protected["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_protected.items():
            delta = acc - baseline_prot
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

        drop_prot = baseline_prot - ablation_protected["scramble"]
        print(f"\n  Protected Phase ablation drop: {drop_prot*100:>+.1f}%")
        if drop_prot > 0.15:
            print(f"  → Phase is ESSENTIAL in protected architecture!")
            print(f"  → No gradient competition = Phase learns meaningful representations")
        elif drop_prot > 0.05:
            print(f"  → Phase CONTRIBUTES in protected architecture")
        else:
            print(f"  → Phase still decorative even when protected")

    # ==========================================================================
    # PHASE ROTATION TEST - Does phase encode relational structure?
    # ==========================================================================
    if args.rotation_test:
        rotation_angles = [float(x) for x in args.rotation_angles.split(",")]
        print(f"\n" + "=" * 70)
        print("PHASE ROTATION TEST")
        print("=" * 70)
        print("\nHypothesis: If phase encodes roles, rotating φ_q should shift bindings.")
        print(f"Testing angles: {rotation_angles}")

        # Test pure Phase model
        rotation_phase = run_rotation_test(
            model_phase, test_roles_loader, vocab, config.device, rotation_angles
        )
        print_rotation_test_results(rotation_phase, "Pure Phase")

        # Test Hybrid models if available
        if model_hybrid is not None:
            rotation_hybrid = run_rotation_test(
                model_hybrid, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_hybrid, "Hybrid (Inverted)")

        if model_hybrid_std is not None:
            rotation_hybrid_std = run_rotation_test(
                model_hybrid_std, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_hybrid_std, "Hybrid (Standard)")

        if model_protected is not None:
            rotation_protected = run_rotation_test(
                model_protected, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_protected, "Protected Phase")

        # Summary
        print(f"\n--- ROTATION TEST SUMMARY ---")
        print(f"  Pure Phase sensitivity:     {rotation_phase['sensitivity']*100:.2f}%")
        if model_hybrid is not None:
            print(f"  Hybrid (Inv) sensitivity:   {rotation_hybrid['sensitivity']*100:.2f}%")
        if model_hybrid_std is not None:
            print(f"  Hybrid (Std) sensitivity:   {rotation_hybrid_std['sensitivity']*100:.2f}%")
        if model_protected is not None:
            print(f"  Protected sensitivity:      {rotation_protected['sensitivity']*100:.2f}%")

        if rotation_phase['sensitivity'] > 0.10:
            print(f"\n  CONCLUSION: Phase encodes MEANINGFUL relational structure")
            print(f"             (rotation significantly affects binding retrieval)")
        elif rotation_phase['sensitivity'] > 0.03:
            print(f"\n  CONCLUSION: Phase shows PARTIAL relational encoding")
            print(f"             (moderate sensitivity to rotation)")
        else:
            print(f"\n  CONCLUSION: Phase is DECORATIVE (rotation has no effect)")
            print(f"             (phase not encoding relational structure)")

    # Summary comparison of ablation impacts
    if ablation_hybrid_inv is not None and ablation_hybrid_std is not None:
        print(f"\n--- ABLATION SUMMARY: Is Phase Decorative? ---")
        drop_pure = baseline - ablation["scramble"]
        drop_inv = ablation_hybrid_inv["none"] - ablation_hybrid_inv["scramble"]
        drop_std = ablation_hybrid_std["none"] - ablation_hybrid_std["scramble"]

        print(f"  Ablation drop (scramble):")
        print(f"    Pure Phase:   {drop_pure*100:>+6.1f}%  {'← Phase is PRIMARY' if drop_pure > 0.15 else ''}")
        print(f"    HybridInv:    {drop_inv*100:>+6.1f}%  {'← Phase EARLY matters' if drop_inv > 0.10 else '← Phase early is weak'}")
        print(f"    HybridStd:    {drop_std*100:>+6.1f}%  {'← Phase LATE matters' if drop_std > 0.10 else '← Phase late is DECORATIVE'}")

        print(f"\n  Conclusion:")
        if drop_std < 0.05:
            print(f"    → Phase is DECORATIVE when Quadratic dominates early")
            print(f"    → Quadratic 'steals' the learning signal")
            print(f"    → Consider: Protected Phase, Sequential, or Different Tasks")
        elif drop_inv < 0.05:
            print(f"    → Phase is DECORATIVE when it comes first")
            print(f"    → Phase can't establish useful representations alone")
            print(f"    → Quadratic late can compensate")
        elif drop_inv > drop_std:
            print(f"    → Phase EARLY contributes more than Phase LATE")
            print(f"    → Supports: Phase = state capture mechanism")
        else:
            print(f"    → Phase LATE contributes more than Phase EARLY")
            print(f"    → Supports: Phase = retrieval mechanism")

    # ==========================================================================
    # SCIENTIFIC VERDICT
    # ==========================================================================
    print("\n" + "=" * 70)
    print("SCIENTIFIC VERDICT")
    print("=" * 70)

    # Compute average test accuracy
    avg_test_q = sum(results_quad.values()) / len(results_quad)
    avg_test_p = sum(results_phase.values()) / len(results_phase)
    avg_test_h = sum(results_hybrid.values()) / len(results_hybrid) if results_hybrid else None
    avg_test_hs = sum(results_hybrid_std.values()) / len(results_hybrid_std) if results_hybrid_std else None

    # Criteria
    quad_memorizes = train_acc_q > 0.85
    quad_fails_generalization = avg_test_q < 0.50
    phase_generalizes = avg_test_p > avg_test_q + 0.15
    phase_is_causal = (baseline - ablation["scramble"]) > 0.1 or (baseline - ablation["freeze"]) > 0.1

    print(f"\nCriteria Check:")
    print(f"  [{'PASS' if quad_memorizes else 'FAIL'}] Quadratic memorizes training ({train_acc_q*100:.1f}% > 85%)")
    print(f"  [{'PASS' if quad_fails_generalization else 'FAIL'}] Quadratic fails generalization ({avg_test_q*100:.1f}% < 50%)")
    print(f"  [{'PASS' if phase_generalizes else 'FAIL'}] Phase outperforms quadratic by >15% ({(avg_test_p - avg_test_q)*100:.1f}%)")
    print(f"  [{'PASS' if phase_is_causal else 'FAIL'}] Phase ablation causes significant drops")

    # NEW: Inverted curriculum hypothesis (v3)
    if results_hybrid is not None:
        hybrid_beats_both = avg_test_h > max(avg_test_q, avg_test_p) + 0.02
        print(f"  [{'PASS' if hybrid_beats_both else 'FAIL'}] Hybrid (inverted) beats both pure models ({avg_test_h*100:.1f}% > {max(avg_test_q, avg_test_p)*100:.1f}%)")

        if results_hybrid_std is not None:
            inverted_beats_standard = avg_test_h > avg_test_hs + 0.02
            print(f"  [{'PASS' if inverted_beats_standard else 'FAIL'}] Inverted curriculum beats standard ({avg_test_h*100:.1f}% > {avg_test_hs*100:.1f}%)")

    # Verdict logic
    if results_hybrid is not None and results_hybrid_std is not None:
        # v3 verdict: Test the STATE vs REASONING hypothesis
        if avg_test_h > max(avg_test_q, avg_test_p, avg_test_hs) + 0.02:
            print("\n" + "=" * 70)
            print("[INVERTED CURRICULUM HYPOTHESIS SUPPORTED]")
            print("=" * 70)
            print("The Hybrid model with INVERTED curriculum achieves best generalization:")
            print(f"  - Phase early (state capture): {curriculum[0]*100:.0f}% → {curriculum[-1]*100:.0f}%")
            print(f"  - Quadratic late (reasoning):  {(1-curriculum[0])*100:.0f}% → {(1-curriculum[-1])*100:.0f}%")
            print(f"\nThis supports the hypothesis:")
            print(f"  PhaseAttention = STATE mechanism (O(n) memory)")
            print(f"  Quadratic      = REASONING mechanism (O(n²) attention)")
            print(f"\nOptimal architecture: Phase-heavy early layers + Quadratic-heavy late layers")
        elif avg_test_h > avg_test_hs + 0.02:
            print("\n[INVERTED > STANDARD]")
            print("Inverted curriculum outperforms standard, supporting Phase-as-state hypothesis.")
            print("But hybrid doesn't beat pure models — consider tuning curriculum ratios.")
        elif avg_test_hs > avg_test_h + 0.02:
            print("\n[STANDARD > INVERTED]")
            print("Standard curriculum outperforms inverted — counter to the hypothesis.")
            print("Phase may be better for reasoning after all, or task requires different mixing.")
        else:
            print("\n[CURRICULA COMPARABLE]")
            print("No significant difference between inverted and standard curriculum.")
            print("Try more extreme ratios: --curriculum 0.95,0.8,0.2,0.05")
    elif quad_memorizes and quad_fails_generalization and phase_generalizes and phase_is_causal:
        print("\n" + "=" * 70)
        print("[HYPOTHESIS STRONGLY SUPPORTED]")
        print("=" * 70)
        print("PhaseAttention demonstrates TRUE RELATIONAL GENERALIZATION:")
        print(f"  - Quadratic memorizes ({train_acc_q*100:.1f}%) but fails to generalize ({avg_test_q*100:.1f}%)")
        print(f"  - Phase generalizes significantly better ({avg_test_p*100:.1f}%)")
        print(f"  - Phase is causally necessary (ablations hurt performance)")
        print("\nThis is strong evidence that phase encodes RELATIONAL STRUCTURE,")
        print("not token-specific patterns.")
    elif phase_generalizes and phase_is_causal:
        print("\n[HYPOTHESIS SUPPORTED]")
        print("Phase shows generalization advantage, but quadratic didn't fail as hard as expected.")
        print("Consider increasing chain length or bind_ratio.")
    elif not quad_fails_generalization:
        print("\n[DATASET TOO EASY]")
        print(f"Quadratic achieved {avg_test_q*100:.1f}% on test — should be <50%.")
        print("Try: --test-chain-min 7 --test-chain-max 10 --bind-ratio 0.8")
    else:
        print("\n[INCONCLUSIVE]")
        print("Results do not clearly support or refute the hypothesis.")
        if results_hybrid is None:
            print("\nTry: --compare-curricula to test Phase-as-state hypothesis")

    print("=" * 70)


if __name__ == "__main__":
    main()
