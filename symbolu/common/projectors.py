"""
Shared Projector Modules for Phase-based Architectures.

Contains projectors used by both Sovereign AGI and Phase-JEPA models.

References:
    - HYBRID_PHASE_JEPA_DESIGN.md §22.4
"""

import math
import torch
import torch.nn as nn
from typing import Optional

# Import IntentPhaseProjector from existing module
try:
    from symbolu.phase_transformer import IntentPhaseProjector
except ImportError:
    # Fallback implementation if import fails
    IntentPhaseProjector = None


class DualSourcePhaseProjector(nn.Module):
    """
    Combines Text-derived geometric rotation with State-derived intent rotation.

    Implements: θ_total = θ_text + θ_intent

    This projector is used when both visual (text instruction) and cognitive
    (sovereign state) sources need to influence attention patterns simultaneously.

    The additive composition follows from phasor multiplication:
        e^{iθ_1} × e^{iθ_2} = e^{i(θ_1 + θ_2)}

    Args:
        text_dim: Dimension of text embeddings
        state_dim: Dimension of Sovereign State (default 32)
        num_heads: Number of attention heads
        head_dim: Optional dimension per head (for per-head-dim projection)
        project_per_head_dim: If True, project to [H, D_h], else [H]
    """

    def __init__(
        self,
        text_dim: int,
        state_dim: int = 32,
        num_heads: int = 12,
        head_dim: Optional[int] = None,
        project_per_head_dim: bool = False,
    ):
        super().__init__()

        self.text_dim = text_dim
        self.state_dim = state_dim
        self.num_heads = num_heads
        self.head_dim = head_dim or 64
        self.project_per_head_dim = project_per_head_dim

        # Output dimension
        self.output_dim = num_heads * self.head_dim if project_per_head_dim else num_heads

        # Text Phase Projector (geometric rotation from instructions)
        self.text_proj = nn.Sequential(
            nn.Linear(text_dim, text_dim),
            nn.GELU(),
            nn.Linear(text_dim, self.output_dim),
        )

        # State Phase Projector (intent rotation from cognitive state)
        self.state_proj = nn.Sequential(
            nn.Linear(state_dim, state_dim * 2),
            nn.GELU(),
            nn.Linear(state_dim * 2, self.output_dim),
        )

        # Learnable scalars to balance sources (default 1.0)
        self.text_scale = nn.Parameter(torch.ones(1))
        self.state_scale = nn.Parameter(torch.ones(1))

        # Initialize to near-zero for stable start
        self._init_weights()

    def _init_weights(self):
        """Initialize to produce small rotations initially."""
        with torch.no_grad():
            self.text_proj[-1].weight.fill_(0.01)
            self.text_proj[-1].bias.fill_(0.0)
            self.state_proj[-1].weight.fill_(0.01)
            self.state_proj[-1].bias.fill_(0.0)

    def forward(
        self,
        text_emb: torch.Tensor,
        state_delta: torch.Tensor,
        text_only: bool = False,
        state_only: bool = False,
    ) -> torch.Tensor:
        """
        Combine phase rotations from text and state.

        Args:
            text_emb: [B, D_text] or [B, T, D_text] from Text Encoder
            state_delta: [B, 32] or [B, T, 32] from Sovereign State Delta
            text_only: Only use text phase (ignore state)
            state_only: Only use state phase (ignore text)

        Returns:
            theta_total: Combined rotation angle
                - [B, H] if not project_per_head_dim
                - [B, H, D_h] if project_per_head_dim
                - [B, T, H, D_h] if input has sequence dimension
        """
        # Calculate individual rotations
        theta_text = self.text_proj(text_emb)  # [B, output_dim] or [B, T, output_dim]
        theta_state = self.state_proj(state_delta)  # [B, output_dim] or [B, T, output_dim]

        # Apply tanh and scale to [-π, π]
        theta_text = torch.tanh(theta_text) * math.pi
        theta_state = torch.tanh(theta_state) * math.pi

        # Additive Phase Composition
        if text_only:
            theta_total = self.text_scale * theta_text
        elif state_only:
            theta_total = self.state_scale * theta_state
        else:
            theta_total = (self.text_scale * theta_text) + (self.state_scale * theta_state)

        # Reshape if project_per_head_dim
        if self.project_per_head_dim:
            if theta_total.dim() == 2:
                # [B, H*D_h] -> [B, H, D_h]
                B = theta_total.shape[0]
                theta_total = theta_total.view(B, self.num_heads, self.head_dim)
            else:
                # [B, T, H*D_h] -> [B, T, H, D_h]
                B, T = theta_total.shape[:2]
                theta_total = theta_total.view(B, T, self.num_heads, self.head_dim)

        return theta_total

    def get_text_phase(self, text_emb: torch.Tensor) -> torch.Tensor:
        """Get phase rotation from text only."""
        return self.forward(text_emb, torch.zeros(text_emb.shape[0], self.state_dim, device=text_emb.device), text_only=True)

    def get_state_phase(self, state_delta: torch.Tensor) -> torch.Tensor:
        """Get phase rotation from state only."""
        return self.forward(torch.zeros(state_delta.shape[0], self.text_dim, device=state_delta.device), state_delta, state_only=True)


class GatedKarmaProjector(nn.Module):
    """
    Gated blend for external karma injection.

    Used when SRK (Master) injects karma state into JEPA (Sensor).
    Implements: effective_karma = gate × external + (1-gate) × internal

    Args:
        state_dim: Sovereign State dimension
    """

    def __init__(self, state_dim: int = 32):
        super().__init__()

        self.state_dim = state_dim

        # Gate projection: determines how much external karma to accept
        self.gate_proj = nn.Sequential(
            nn.Linear(state_dim * 2, state_dim),
            nn.Sigmoid(),
        )

    def forward(
        self,
        external_karma: torch.Tensor,
        internal_karma: torch.Tensor,
    ) -> torch.Tensor:
        """
        Blend external and internal karma states.

        Args:
            external_karma: [B, 32] from SRK (Master)
            internal_karma: [B, 32] from JEPA (internal state)

        Returns:
            effective_karma: [B, 32] blended karma state
        """
        # Concatenate for gate computation
        combined = torch.cat([external_karma, internal_karma], dim=-1)  # [B, 64]

        # Compute gate (how much to accept from external)
        gate = self.gate_proj(combined)  # [B, 32]

        # Blend
        effective_karma = gate * external_karma + (1 - gate) * internal_karma

        return effective_karma

    def get_gate_values(
        self,
        external_karma: torch.Tensor,
        internal_karma: torch.Tensor,
    ) -> torch.Tensor:
        """Get the gate values (for diagnostics)."""
        combined = torch.cat([external_karma, internal_karma], dim=-1)
        return self.gate_proj(combined)


# Fallback IntentPhaseProjector if import failed
if IntentPhaseProjector is None:
    class IntentPhaseProjector(nn.Module):
        """
        Fallback IntentPhaseProjector (simplified version).

        V11.0.0: Defaults to 12D Bhava-only input (was 32D).
        Projects Bhava State Delta to phase rotation offsets.
        """
        def __init__(
            self,
            state_dim: int = 12,  # V11.0.0: 12D Bhava-only (was 32D)
            num_heads: int = 12,
            head_dim: int = 64,
            project_per_head_dim: bool = False,
        ):
            super().__init__()
            self.state_dim = state_dim
            self.num_heads = num_heads
            self.head_dim = head_dim
            self.project_per_head_dim = project_per_head_dim

            output_dim = num_heads * head_dim if project_per_head_dim else num_heads

            self.phase_proj = nn.Sequential(
                nn.Linear(state_dim, state_dim),
                nn.GELU(),
                nn.Linear(state_dim, output_dim),
            )

            # Initialize near-zero
            with torch.no_grad():
                self.phase_proj[-1].weight.fill_(0.01)
                self.phase_proj[-1].bias.fill_(0.0)

        def forward(self, delta_S: torch.Tensor) -> torch.Tensor:
            theta = self.phase_proj(delta_S)
            theta = torch.tanh(theta) * math.pi
            return theta
