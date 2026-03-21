#!/usr/bin/env python3
"""
Phase Coherence Signal — Appendix F Stage 7F
==============================================

Extracts per-head phase coherence from PhaseAttentionBlock and aggregates
it across layers into a phase_coherence_vector that joins the interpretive
state in Stage 2's InterpretiveConditioner.

Phase coherence measures how well U3/U4 rotations maintained constructive
interference across attention heads. High coherence = phases aligned;
low coherence = phases scattered.

Architecture::

    PhaseAttentionBlock
        ├──→ attention_output (into residual stream → hidden_state)
        └──→ phase_coherence_per_head ──→ aggregate across layers
                                              ↓
                                         phase_coherence_vector [B, H]
                                              ↓
                                         InterpretiveConditioner
                                           (joins interpretive state)
                                              ↓
                                         conditioned_hidden → lm_head → logits

Bounded introduction: Phase coherence is computed and logged before
activation. The InterpretiveConditioner gate starts at 0, so phase
coherence has no effect until the gate trains up.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.10.6.6

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 7F — Phase Synchronization → Generation Path
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import torch
import torch.nn as nn


@dataclass
class PhaseCoherenceConfig:
    """Configuration for phase coherence signal extraction.

    Attributes:
        enable: Master switch for Stage 7F. When False, returns zeros.
        num_heads: Number of attention heads per layer.
        num_layers: Number of transformer layers.
        aggregation: How to aggregate across layers. 'mean' or 'last'.
    """
    enable: bool = True
    num_heads: int = 8
    num_layers: int = 12
    aggregation: str = "mean"


class PhaseCoherenceExtractor(nn.Module):
    """Extracts phase coherence per head from phase angle data.

    Computes coherence as 1 - std(phase_angles) for each head,
    measuring how aligned the phase rotations are.

    Args:
        config: PhaseCoherenceConfig.
    """

    def __init__(self, config: PhaseCoherenceConfig = None):
        super().__init__()
        self.config = config or PhaseCoherenceConfig()

    def compute_per_head(self, phase_angles: torch.Tensor) -> torch.Tensor:
        """Compute per-head phase coherence from phase angle tensor.

        Args:
            phase_angles: Phase angles from attention rotation.
                Shape [B, H, T, D_half] where D_half = head_dim // 2.

        Returns:
            phase_coherence_per_head: [B, H] where high = aligned phases.
        """
        if not self.config.enable:
            B = phase_angles.shape[0]
            H = phase_angles.shape[1] if phase_angles.dim() > 1 else self.config.num_heads
            return torch.zeros(B, H, device=phase_angles.device)

        # std across the last dimension (D_half), then mean across T
        # High std = scattered phases = low coherence
        phase_std = phase_angles.std(dim=-1)  # [B, H, T]
        mean_std = phase_std.mean(dim=-1)     # [B, H]

        # Coherence = 1 - normalized_std (clamp to [0, 1])
        # Normalize by pi since phase angles are in [-pi, pi]
        coherence = 1.0 - (mean_std / 3.14159).clamp(0.0, 1.0)

        return coherence


class PhaseCoherenceAggregator:
    """Aggregates per-layer, per-head phase coherence into a vector.

    Collects phase_coherence_per_head from each transformer layer
    and produces a single phase_coherence_vector for the interpretive state.

    Usage::

        aggregator = PhaseCoherenceAggregator()

        # During forward pass:
        for layer_idx, layer in enumerate(model.layers):
            hidden, phase_angles = layer(hidden)
            per_head = extractor.compute_per_head(phase_angles)
            aggregator.record_layer(layer_idx, per_head)

        # After all layers:
        phase_vector = aggregator.get_phase_coherence_vector()  # [B, H]

    Attributes:
        config: PhaseCoherenceConfig.
        layer_coherences: Per-layer phase coherence tensors.
    """

    def __init__(self, config: PhaseCoherenceConfig = None):
        self.config = config or PhaseCoherenceConfig()
        self.layer_coherences: List[Optional[torch.Tensor]] = [None] * self.config.num_layers

    def record_layer(self, layer_idx: int, phase_coherence_per_head: torch.Tensor) -> None:
        """Record per-head phase coherence for a specific layer.

        Args:
            layer_idx: Layer index (0-based).
            phase_coherence_per_head: [B, H] coherence per head.
        """
        if 0 <= layer_idx < len(self.layer_coherences):
            self.layer_coherences[layer_idx] = phase_coherence_per_head

    def get_phase_coherence_vector(self) -> Optional[torch.Tensor]:
        """Aggregate across layers into a single phase coherence vector.

        Returns:
            phase_coherence_vector: [B, H] aggregated across layers.
            None if no layer data has been recorded.
        """
        if not self.config.enable:
            return None

        valid = [c for c in self.layer_coherences if c is not None]
        if not valid:
            return None

        # Stack: [num_valid_layers, B, H]
        stacked = torch.stack(valid, dim=0)

        if self.config.aggregation == "last":
            return stacked[-1]  # [B, H]
        else:
            return stacked.mean(dim=0)  # [B, H]

    def reset(self) -> None:
        """Reset per-token layer data."""
        self.layer_coherences = [None] * self.config.num_layers


class PhaseCoherenceProjection(nn.Module):
    """Projects phase coherence vector to match interpretive state dimensions.

    Maps [B, H] phase coherence to [B, T, phase_out_dim] for concatenation
    with the interpretive state in InterpretiveStateBuilder.

    Args:
        num_heads: Number of attention heads (input dimension).
        phase_out_dim: Output dimension to add to interpretive state.
    """

    def __init__(self, num_heads: int = 8, phase_out_dim: int = 8):
        super().__init__()
        self.num_heads = num_heads
        self.phase_out_dim = phase_out_dim
        self.projection = nn.Sequential(
            nn.Linear(num_heads, phase_out_dim),
            nn.Tanh(),
        )
        # Zero-init for bounded introduction
        nn.init.zeros_(self.projection[0].weight)
        nn.init.zeros_(self.projection[0].bias)

    def forward(
        self,
        phase_coherence_vector: torch.Tensor,
        seq_len: int = 1,
    ) -> torch.Tensor:
        """Project and expand phase coherence to sequence length.

        Args:
            phase_coherence_vector: [B, H] aggregated phase coherence.
            seq_len: Sequence length to broadcast to.

        Returns:
            Projected phase signal: [B, T, phase_out_dim].
        """
        projected = self.projection(phase_coherence_vector)  # [B, phase_out_dim]
        # Expand to sequence length
        return projected.unsqueeze(1).expand(-1, seq_len, -1)  # [B, T, phase_out_dim]
