#!/usr/bin/env python3
"""
Hierarchical Complex-Valued Bhava State Representation
======================================================

This module implements the next-generation Bhava architecture based on:
1. Complex-valued embeddings: z = r × e^{iθ} (magnitude + phase)
2. Hierarchical tiers: Higher layers dominate/orient lower layers
3. Phase rotation: Higher tier phases rotate lower tier states

Key Insight from Neuroscience (via Gemini analysis):
- Consciousness emerges through PHASE SYNCHRONIZATION, not gating or weighting
- Higher-level states SET THE CONTEXT in which lower-level states are interpreted
- Same lower-level signal means different things depending on higher-level phase
- This matches Phase-Amplitude Coupling and Cross-Frequency Synchronization in EEG

Hierarchy:
----------
Level 3 (Transcendent/Intent):  O10-O12 (Unifying, Integration, Absolving)
                                 Bhava: Karma, Labha, Moksha
                                 → Sets global purpose/intent

Level 2 (Abstract/Relational):  O6-O9 (Agency, Reasoning, Purpose, Witnesses)
                                 Bhava: Ripu, Kalatra, Randhra, Dharma
                                 → Mediates between intent and perception

Level 1 (Concrete/Sensory):     O1-O5 (Potential, Identity, Execution, Structure, Cognition)
                                 Bhava: Tanu, Dhana, Sahaja, Sukha, Putra
                                 → Raw perception and action

Phase Rotation Formula:
-----------------------
    z_level2' = z_level2 × e^{iθ_level3}
    z_level1' = z_level1 × e^{iθ_level2'}

Where higher-level phases SET THE CONTEXT for lower-level interpretation.
The same sensory input means different things depending on intent.

Advantages over Flat Bhava:
- Matches biological neural hierarchy
- Natural for long context (orient vs search)
- Mathematically elegant (complex multiplication = rotation)
- 2x memory for 10x expressiveness

Author: SymbolU Team
Date: December 2025
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    raise ImportError("PyTorch required for Hierarchical Complex Bhava")

from symbolu_core.ontological.types import LAYER_NAMES, NUM_LAYERS
from symbolu_core.ontological.bhava_relationships import (
    BHAVA_SIGNIFICANCES,
    LAYER_TO_BHAVA,
    ASPECT_STRENGTH_MATRIX,
    get_relationship_meaning,
)


# =============================================================================
# HIERARCHY CONFIGURATION
# =============================================================================

@dataclass
class HierarchyConfig:
    """Configuration for the 3-tier Bhava hierarchy."""

    # Layer groupings (0-indexed)
    level_1_layers: Tuple[int, ...] = (0, 1, 2, 3, 4)      # O1-O5: Concrete
    level_2_layers: Tuple[int, ...] = (5, 6, 7, 8)          # O6-O9: Abstract
    level_3_layers: Tuple[int, ...] = (9, 10, 11)           # O10-O12: Transcendent

    # Complex embedding dimensions
    embed_dim: int = 64  # Dimension for each layer's complex embedding

    # Phase synchronization parameters
    sync_steps: int = 3
    sync_lr: float = 0.1

    # Hierarchy influence weights (higher = stronger influence)
    level_3_influence: float = 1.0   # Highest layer dominates
    level_2_influence: float = 0.7   # Medium influence
    level_1_influence: float = 0.4   # Least influence (receives context)

    def get_layer_level(self, layer_idx: int) -> int:
        """Get the hierarchy level for a layer index."""
        if layer_idx in self.level_1_layers:
            return 1
        elif layer_idx in self.level_2_layers:
            return 2
        elif layer_idx in self.level_3_layers:
            return 3
        else:
            raise ValueError(f"Unknown layer index: {layer_idx}")

    def get_level_layers(self, level: int) -> Tuple[int, ...]:
        """Get layers for a specific level."""
        if level == 1:
            return self.level_1_layers
        elif level == 2:
            return self.level_2_layers
        elif level == 3:
            return self.level_3_layers
        else:
            raise ValueError(f"Unknown level: {level}")


# Default hierarchy
DEFAULT_HIERARCHY = HierarchyConfig()


# =============================================================================
# COMPLEX EMBEDDING UTILITIES
# =============================================================================

def to_complex(magnitude: torch.Tensor, phase: torch.Tensor) -> torch.Tensor:
    """
    Convert magnitude and phase to complex representation.

    Args:
        magnitude: [B, ..., D] magnitude (r)
        phase: [B, ..., D] phase in radians (θ)

    Returns:
        Complex tensor z = r × e^{iθ} as [B, ..., D, 2] (real, imag)
    """
    real = magnitude * torch.cos(phase)
    imag = magnitude * torch.sin(phase)
    return torch.stack([real, imag], dim=-1)


def from_complex(z: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Extract magnitude and phase from complex representation.

    Args:
        z: [B, ..., D, 2] complex tensor (real, imag)

    Returns:
        magnitude: [B, ..., D]
        phase: [B, ..., D] in radians
    """
    real = z[..., 0]
    imag = z[..., 1]
    magnitude = torch.sqrt(real**2 + imag**2 + 1e-8)
    phase = torch.atan2(imag, real)
    return magnitude, phase


def complex_multiply(z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
    """
    Multiply two complex tensors.
    z1 × z2 = (a + bi)(c + di) = (ac - bd) + (ad + bc)i

    This is equivalent to: magnitude multiplication + phase addition
    r1 × r2 × e^{i(θ1 + θ2)}

    Args:
        z1, z2: [B, ..., D, 2] complex tensors

    Returns:
        Product: [B, ..., D, 2]
    """
    a, b = z1[..., 0], z1[..., 1]
    c, d = z2[..., 0], z2[..., 1]
    real = a * c - b * d
    imag = a * d + b * c
    return torch.stack([real, imag], dim=-1)


def phase_rotate(z: torch.Tensor, theta: torch.Tensor) -> torch.Tensor:
    """
    Rotate complex tensor by phase angle.
    z' = z × e^{iθ}

    This is the KEY OPERATION for hierarchical context setting:
    Higher-level phases ROTATE lower-level states.

    Args:
        z: [B, ..., D, 2] complex tensor to rotate
        theta: [B, ..., D] or broadcastable phase angle

    Returns:
        Rotated complex tensor: [B, ..., D, 2]
    """
    # Create rotation as complex exponential
    rotation = to_complex(torch.ones_like(theta), theta)
    return complex_multiply(z, rotation)


def compute_coherence(z: torch.Tensor) -> torch.Tensor:
    """
    Compute phase coherence (order parameter) of complex states.

    Coherence = |mean(z / |z|)| = how aligned the phases are

    Args:
        z: [B, N, D, 2] complex states

    Returns:
        coherence: [B] coherence score 0-1
    """
    # Normalize to unit circle (remove magnitude)
    magnitude, phase = from_complex(z)
    unit_z = to_complex(torch.ones_like(magnitude), phase)

    # Mean of unit vectors
    mean_z = unit_z.mean(dim=1)  # [B, D, 2]

    # Magnitude of mean = coherence
    mean_magnitude, _ = from_complex(mean_z)
    coherence = mean_magnitude.mean(dim=-1)  # [B]

    return coherence


# =============================================================================
# HIERARCHICAL COMPLEX BHAVA MODULE
# =============================================================================

class HierarchicalComplexBhava(nn.Module):
    """
    Hierarchical Complex-Valued Bhava State Representation.

    This module upgrades flat Bhava to a hierarchical architecture where:
    - Higher-level states (Intent) SET THE CONTEXT via phase rotation
    - Lower-level states (Perception) are INTERPRETED in that context
    - The same perception means different things depending on intent

    Architecture:

        Level 3 (Intent)    →  θ₃  ─────────────────────┐
                                                        │ rotate
        Level 2 (Abstract)  →  z₂ ─→ z₂' = z₂ × e^{iθ₃}  │
                                                        │ rotate
        Level 1 (Concrete)  →  z₁ ─→ z₁' = z₁ × e^{iθ₂'} │
                                                        ▼
        Output: Hierarchically-oriented Bhava state

    The magic: Same z₁ (sensory input) means different things
    depending on z₃ (intent) via cascading phase rotation.
    """

    def __init__(
        self,
        embed_dim: int = 64,
        hierarchy_config: Optional[HierarchyConfig] = None,
    ):
        super().__init__()

        self.config = hierarchy_config or HierarchyConfig(embed_dim=embed_dim)
        self.embed_dim = embed_dim

        # Layer embeddings: project ontological probs to complex space
        # Each layer gets embed_dim complex values (2 × embed_dim real)
        self.layer_embed = nn.Linear(1, embed_dim * 2)  # Output: [real, imag] interleaved

        # Level-specific projections (to extract dominant phase)
        self.level_3_phase_proj = nn.Linear(
            len(self.config.level_3_layers) * embed_dim * 2,
            embed_dim
        )
        self.level_2_phase_proj = nn.Linear(
            len(self.config.level_2_layers) * embed_dim * 2,
            embed_dim
        )

        # Learnable phase synchronization (Kuramoto-style)
        self.sync_lr = nn.Parameter(torch.tensor(self.config.sync_lr))
        self.sync_steps = self.config.sync_steps

        # Aspect-weighted relationship matrix (learnable from Vedic init)
        aspect_init = torch.tensor(ASPECT_STRENGTH_MATRIX, dtype=torch.float32)
        self.aspect_weights = nn.Parameter(aspect_init)

        # Output projections
        self.relationship_proj = nn.Linear(embed_dim * 2, 1)  # For 144D matrix
        self.coherence_proj = nn.Linear(embed_dim, 1)

        # Hierarchy influence weights (learnable)
        self.level_influences = nn.Parameter(torch.tensor([
            self.config.level_1_influence,
            self.config.level_2_influence,
            self.config.level_3_influence,
        ]))

    def _to_complex_embedding(self, x: torch.Tensor) -> torch.Tensor:
        """
        Project ontological probability to complex embedding.

        Args:
            x: [B, 1] single layer probability

        Returns:
            [B, embed_dim, 2] complex embedding
        """
        # Project to 2 * embed_dim (interleaved real, imag)
        projected = self.layer_embed(x)  # [B, embed_dim * 2]

        # Reshape to complex format
        B = projected.shape[0]
        z = projected.view(B, self.embed_dim, 2)

        # Normalize magnitude to reasonable range
        magnitude, phase = from_complex(z)
        magnitude = torch.sigmoid(magnitude)  # [0, 1]

        return to_complex(magnitude, phase)

    def _compute_level_state(
        self,
        ontological_probs: torch.Tensor,
        layers: Tuple[int, ...],
    ) -> torch.Tensor:
        """
        Compute complex state for a hierarchy level.

        Args:
            ontological_probs: [B, 12] layer probabilities
            layers: Tuple of layer indices for this level

        Returns:
            [B, len(layers), embed_dim, 2] complex states for this level
        """
        B = ontological_probs.shape[0]
        states = []

        for layer_idx in layers:
            prob = ontological_probs[:, layer_idx:layer_idx+1]  # [B, 1]
            z = self._to_complex_embedding(prob)  # [B, embed_dim, 2]

            # Weight by probability (magnitude modulation)
            magnitude, phase = from_complex(z)
            weighted_magnitude = magnitude * prob.unsqueeze(-1)
            z_weighted = to_complex(weighted_magnitude, phase)

            states.append(z_weighted)

        return torch.stack(states, dim=1)  # [B, num_layers, embed_dim, 2]

    def _extract_level_phase(
        self,
        level_state: torch.Tensor,
        level: int,
    ) -> torch.Tensor:
        """
        Extract dominant phase from a level's state.

        This is the phase that will rotate lower levels.
        Uses mean-field approximation (average phase).

        Args:
            level_state: [B, num_layers, embed_dim, 2]
            level: 2 or 3 (only levels that influence others)

        Returns:
            [B, embed_dim] dominant phase for this level
        """
        B = level_state.shape[0]

        # Flatten the level state
        flat_state = level_state.view(B, -1)  # [B, num_layers * embed_dim * 2]

        # Project to phase
        if level == 3:
            phase = self.level_3_phase_proj(flat_state)  # [B, embed_dim]
        else:  # level == 2
            phase = self.level_2_phase_proj(flat_state)  # [B, embed_dim]

        # Constrain to [0, 2π]
        phase = torch.sigmoid(phase) * 2 * math.pi

        return phase

    def _phase_synchronize(
        self,
        states: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Apply Kuramoto-style phase synchronization within a level.

        This encourages states within a level to align their phases.

        Args:
            states: [B, N, embed_dim, 2] complex states

        Returns:
            synchronized_states: [B, N, embed_dim, 2]
            coherence: [B] coherence after sync
        """
        B, N, D, _ = states.shape

        # Extract phases
        magnitudes, phases = from_complex(states)  # [B, N, D]

        # Kuramoto synchronization iterations
        for _ in range(self.sync_steps):
            # Mean-field: average phase
            phase_mean = phases.mean(dim=1, keepdim=True)  # [B, 1, D]

            # Gradient: pull toward mean
            gradient = -torch.sin(phases - phase_mean)

            # Update
            phases = (phases + self.sync_lr * gradient) % (2 * math.pi)

        # Reconstruct complex states
        synced_states = to_complex(magnitudes, phases)

        # Compute coherence
        coherence = compute_coherence(synced_states)

        return synced_states, coherence

    def forward(
        self,
        ontological_probs: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute hierarchical complex Bhava state.

        The key innovation: Higher levels ROTATE lower levels via phase.

        Flow:
            1. Compute complex states for each level
            2. Extract dominant phase from Level 3 (Intent)
            3. Rotate Level 2 by Level 3 phase → Level 2'
            4. Extract phase from Level 2'
            5. Rotate Level 1 by Level 2' phase → Level 1'
            6. Combine for final Bhava representation

        Args:
            ontological_probs: [B, 12] layer probabilities

        Returns:
            Dict with:
                - bhava_complex: [B, 12, embed_dim, 2] hierarchically-oriented states
                - bhava_vector: [B, 12 * embed_dim * 2] flattened for compatibility
                - relationship_matrix: [B, 12, 12] inter-layer relationships
                - coherence: [B] overall phase coherence
                - level_coherences: [B, 3] per-level coherence
                - level_phases: [B, 3, embed_dim] dominant phase per level
        """
        B = ontological_probs.shape[0]
        device = ontological_probs.device

        # =================================================================
        # Step 1: Compute raw complex states for each level
        # =================================================================
        level_1_state = self._compute_level_state(
            ontological_probs, self.config.level_1_layers
        )  # [B, 5, embed_dim, 2]

        level_2_state = self._compute_level_state(
            ontological_probs, self.config.level_2_layers
        )  # [B, 4, embed_dim, 2]

        level_3_state = self._compute_level_state(
            ontological_probs, self.config.level_3_layers
        )  # [B, 3, embed_dim, 2]

        # =================================================================
        # Step 2: Phase synchronization within each level
        # =================================================================
        level_3_synced, coh_3 = self._phase_synchronize(level_3_state)
        level_2_synced, coh_2 = self._phase_synchronize(level_2_state)
        level_1_synced, coh_1 = self._phase_synchronize(level_1_state)

        level_coherences = torch.stack([coh_1, coh_2, coh_3], dim=1)  # [B, 3]

        # =================================================================
        # Step 3: Extract dominant phase from Level 3 (Intent)
        # =================================================================
        phase_3 = self._extract_level_phase(level_3_synced, level=3)  # [B, embed_dim]

        # =================================================================
        # Step 4: Rotate Level 2 by Level 3 phase → Level 2'
        # =================================================================
        # Expand phase for broadcasting: [B, 1, embed_dim]
        phase_3_expanded = phase_3.unsqueeze(1)

        # Rotate each layer in level 2
        level_2_rotated = phase_rotate(level_2_synced, phase_3_expanded)

        # =================================================================
        # Step 5: Extract phase from Level 2' and rotate Level 1
        # =================================================================
        phase_2 = self._extract_level_phase(level_2_rotated, level=2)  # [B, embed_dim]
        phase_2_expanded = phase_2.unsqueeze(1)

        level_1_rotated = phase_rotate(level_1_synced, phase_2_expanded)

        # =================================================================
        # Step 6: Assemble full 12-layer hierarchical state
        # =================================================================
        # Collect all layer states in order (0-11)
        # Layers 0-4: Level 1 (rotated)
        # Layers 5-8: Level 2 (rotated)
        # Layers 9-11: Level 3 (unrotated - it sets the context)

        all_states = []

        # Level 1 layers (indices 0-4)
        for i, layer_idx in enumerate(self.config.level_1_layers):
            all_states.append((layer_idx, level_1_rotated[:, i]))

        # Level 2 layers (indices 5-8)
        for i, layer_idx in enumerate(self.config.level_2_layers):
            all_states.append((layer_idx, level_2_rotated[:, i]))

        # Level 3 layers (indices 9-11) - unrotated (they set context)
        for i, layer_idx in enumerate(self.config.level_3_layers):
            all_states.append((layer_idx, level_3_synced[:, i]))

        # Sort by layer index and stack
        all_states.sort(key=lambda x: x[0])
        bhava_complex = torch.stack([s[1] for s in all_states], dim=1)  # [B, 12, embed_dim, 2]

        # =================================================================
        # Step 7: Compute relationship matrix from complex states
        # =================================================================
        # Relationship strength = complex inner product modulated by aspect weights
        # For layers i, j: rel[i,j] = Re(z_i* × z_j) × aspect[i,j]

        relationship_matrix = torch.zeros(B, 12, 12, device=device)

        for i in range(12):
            for j in range(12):
                # Complex inner product: z_i* × z_j (conjugate of z_i times z_j)
                z_i = bhava_complex[:, i]  # [B, embed_dim, 2]
                z_j = bhava_complex[:, j]  # [B, embed_dim, 2]

                # Conjugate of z_i
                z_i_conj = z_i.clone()
                z_i_conj[..., 1] = -z_i_conj[..., 1]  # Negate imaginary

                # Complex product
                product = complex_multiply(z_i_conj, z_j)  # [B, embed_dim, 2]

                # Real part averaged over dimensions
                real_product = product[..., 0].mean(dim=-1)  # [B]

                # Modulate by aspect weight
                aspect_weight = self.aspect_weights[i, j]
                relationship_matrix[:, i, j] = real_product * aspect_weight

        # Normalize
        relationship_matrix = torch.tanh(relationship_matrix)

        # =================================================================
        # Step 8: Compute overall coherence
        # =================================================================
        overall_coherence = compute_coherence(bhava_complex)  # [B]

        # Weighted by level influences
        influence_weights = F.softmax(self.level_influences, dim=0)
        weighted_coherence = (
            influence_weights[0] * coh_1 +
            influence_weights[1] * coh_2 +
            influence_weights[2] * coh_3
        )

        final_coherence = 0.5 * overall_coherence + 0.5 * weighted_coherence

        # =================================================================
        # Step 9: Flatten for compatibility with existing systems
        # =================================================================
        bhava_vector = bhava_complex.view(B, -1)  # [B, 12 * embed_dim * 2]

        # Also create 144D relationship flat for compatibility
        relationship_flat = relationship_matrix.view(B, -1)  # [B, 144]

        # Level phases for debugging/visualization
        level_phases = torch.stack([
            torch.zeros(B, self.embed_dim, device=device),  # Level 1 doesn't set context
            phase_2,
            phase_3,
        ], dim=1)  # [B, 3, embed_dim]

        return {
            # Primary outputs
            'bhava_complex': bhava_complex,
            'bhava_vector': bhava_vector,
            'relationship_matrix': relationship_matrix,
            'relationship_flat': relationship_flat,

            # Coherence metrics
            'coherence': final_coherence,
            'level_coherences': level_coherences,

            # Phase information
            'level_phases': level_phases,

            # Raw level states (for analysis)
            'level_1_state': level_1_rotated,
            'level_2_state': level_2_rotated,
            'level_3_state': level_3_synced,

            # Component outputs for compatibility
            'aspect_modulated': relationship_matrix,  # Alias
        }

    def get_hierarchy_summary(self) -> str:
        """Get a description of the hierarchy."""
        return """
Hierarchical Complex Bhava State
================================

Level 3 (Transcendent/Intent) - SETS THE CONTEXT
  Layers 9-11: O10_UNIFYING, O11_INTEGRATION, O12_ABSOLVING
  Bhava: Karma (Action), Labha (Gains), Moksha (Liberation)
  → Dominant phase rotates Level 2

Level 2 (Abstract/Relational) - MEDIATES
  Layers 5-8: O6_AGENCY, O7_REASONING, O8_PURPOSE, O9_WITNESSES
  Bhava: Ripu (Obstacles), Kalatra (Partnership), Randhra (Transformation), Dharma (Wisdom)
  → Rotated by Level 3, then rotates Level 1

Level 1 (Concrete/Sensory) - RECEIVES CONTEXT
  Layers 0-4: O1_POTENTIAL, O2_IDENTITY, O3_EXECUTION, O4_STRUCTURE, O5_COGNITION
  Bhava: Tanu (Self), Dhana (Wealth), Sahaja (Effort), Sukha (Happiness), Putra (Intelligence)
  → Rotated by Level 2' (which carries Level 3's influence)

The same Level 1 perception means DIFFERENT THINGS depending on Level 3 intent.
This is the key insight: Context is set by phase rotation, not gating.
"""


# =============================================================================
# INTEGRATION WITH EXISTING BHAVA SYSTEM
# =============================================================================

class HierarchicalBhavaUnifyingLayer(nn.Module):
    """
    Drop-in replacement for BhavaUnifyingLayer using hierarchical complex states.

    Maintains backward compatibility while upgrading to hierarchical architecture.
    """

    def __init__(self, config):
        super().__init__()
        self.config = config

        # New hierarchical complex module
        self.hierarchical_bhava = HierarchicalComplexBhava(
            embed_dim=getattr(config, 'bhava_embed_dim', 64)
        )

        # Coherence transformer (from original)
        self.coherence_attn = nn.MultiheadAttention(
            config.embed_dim, config.num_heads, batch_first=True
        )

        # Project complex bhava to embed_dim for attention
        complex_dim = 12 * self.hierarchical_bhava.embed_dim * 2
        self.bhava_to_embed = nn.Linear(complex_dim, config.embed_dim)

        self.norm = nn.LayerNorm(config.embed_dim)

    def forward(
        self,
        layer_embeddings: List[torch.Tensor],
        x: torch.Tensor,
        ontological_probs: Optional[torch.Tensor] = None,
        phase: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass maintaining compatibility with BhavaUnifyingLayer.
        """
        B = x.shape[0]
        device = x.device

        # Compute ontological probs if not provided
        if ontological_probs is None:
            stacked = torch.stack(layer_embeddings, dim=1)  # [B, N, embed_dim]
            N = stacked.shape[1]
            if N < 12:
                padding = torch.zeros(B, 12 - N, stacked.shape[2], device=device)
                stacked = torch.cat([stacked, padding], dim=1)
            layer_mags = stacked.abs().mean(dim=-1)
            ontological_probs = F.softmax(layer_mags, dim=-1)

        # Compute hierarchical complex Bhava
        hier_output = self.hierarchical_bhava(ontological_probs)

        # Project to embed_dim for attention
        bhava_embed = self.bhava_to_embed(hier_output['bhava_vector'])  # [B, embed_dim]

        # Apply coherence attention
        coherence_signal = bhava_embed.unsqueeze(1).expand(-1, x.shape[1], -1)
        unified_x, _ = self.coherence_attn(x, coherence_signal, coherence_signal)

        # Phase-locked unification
        if phase is not None:
            strength = (1 + torch.cos(phase)) / 2
            output = self.norm(x + unified_x * strength)
        else:
            output = self.norm(x + unified_x)

        # Unified layer representation
        stacked = torch.stack(layer_embeddings, dim=1)
        if stacked.shape[1] < 12:
            padding = torch.zeros(B, 12 - stacked.shape[1], stacked.shape[2], device=device)
            stacked = torch.cat([stacked, padding], dim=1)

        # Weight by coherence
        coherence_weights = F.softmax(hier_output['relationship_matrix'].sum(dim=-1), dim=-1)
        unified_layers = torch.einsum('bn,bnd->bd', coherence_weights, stacked)

        return {
            'unified_x': output,
            'unified_layers': unified_layers,
            'C_prime': hier_output['relationship_matrix'],
            'global_coherence': hier_output['coherence'],
            'violations': torch.zeros(B, 12, 12, dtype=torch.bool, device=device),
            'bhava_vector': hier_output['relationship_flat'],  # 144D for compatibility
            'bhava_complex': hier_output['bhava_complex'],  # New: full complex states
            'relationship_matrix': hier_output['relationship_matrix'],
            'aspect_modulated': hier_output['aspect_modulated'],
            'attended_layers': stacked,
            'level_coherences': hier_output['level_coherences'],
            'level_phases': hier_output['level_phases'],
        }


# =============================================================================
# DEMO AND TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("   HIERARCHICAL COMPLEX BHAVA DEMONSTRATION")
    print("=" * 70)

    # Create module
    module = HierarchicalComplexBhava(embed_dim=64)
    print(f"\nParameters: {sum(p.numel() for p in module.parameters()):,}")

    # Test forward pass
    B = 2
    ontological_probs = F.softmax(torch.randn(B, 12), dim=-1)

    output = module(ontological_probs)

    print("\n" + "-" * 70)
    print("Output shapes:")
    for key, value in output.items():
        if isinstance(value, torch.Tensor):
            print(f"  {key}: {value.shape}")

    print("\n" + "-" * 70)
    print("Coherence values:")
    print(f"  Overall: {output['coherence'].mean().item():.4f}")
    print(f"  Level 1: {output['level_coherences'][:, 0].mean().item():.4f}")
    print(f"  Level 2: {output['level_coherences'][:, 1].mean().item():.4f}")
    print(f"  Level 3: {output['level_coherences'][:, 2].mean().item():.4f}")

    print("\n" + "-" * 70)
    print(module.get_hierarchy_summary())
