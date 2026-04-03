"""
GateMixer: Phase-controlled integration of Quad proposals.

Implements temperature-scaled sigmoid gating (NOT softmax).
Temperature schedule: τ starts high (2.0) → decays to 1.0 during training.
This prevents early gate collapse and improves gradient flow.
"""

from typing import Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.contracts import assert_control_shape
from symbolu.vision.controls import GateControl


class GateMixer(nn.Module):
    """
    Phase-controlled integration of Quad proposals.

    Implements temperature-scaled sigmoid gating (NOT softmax).
    Temperature schedule: τ starts high (2.0) → decays to 1.0 during training.
    This prevents early gate collapse and improves gradient flow.

    Optionally applies alignment-based clamping (V10.6 dual-channel).

    Key difference from softmax attention:
    - Sigmoid allows multiple proposals to contribute
    - No winner-take-all dynamics
    - Phase decides via accumulated context

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        default_gamma: EMA decay for state update.
        default_alpha: Alignment authority coefficient.
        clamp_min: Minimum clamp value for alignment modulation.
        clamp_max: Maximum clamp value for alignment modulation.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        default_gamma: float = 0.9,
        default_alpha: float = 0.1,
        clamp_min: float = 0.8,
        clamp_max: float = 1.2,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads

        # Learned EMA gamma (per-head)
        self.gamma = nn.Parameter(torch.full((num_heads,), default_gamma))

        # Alignment authority
        self.alpha = nn.Parameter(torch.tensor(default_alpha))
        self.clamp_min = clamp_min
        self.clamp_max = clamp_max

        # Output projection
        self.proj = nn.Linear(embed_dim, embed_dim)

        # Layer norm for input
        self.norm = nn.LayerNorm(embed_dim)

        # Instrumentation
        self.register_buffer("_last_gate_saturation", torch.tensor(0.0))
        self.register_buffer("_last_gate_entropy", torch.tensor(0.0))
        self.register_buffer("_last_gate_mean", torch.tensor(0.0))

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Tensor,
        control: Optional[GateControl] = None,
    ) -> Tensor:
        """
        Integrate proposals via Phase-controlled gating.

        Args:
            x: Current tokens [B, N, D].
            proposals: [B, N, K, D] from QuadRetriever2D.
            scores: [B, N, K] retrieval scores (raw).
            control: Optional GateControl containing:
                - tau: [] temperature for sigmoid (default 1.0)
                - s_align: [] or [H] or [B, H] alignment score (contract-safe)
                - clamp_min: scalar override
                - clamp_max: scalar override

        Returns:
            x_out: [B, N, D] integrated output.

        Raises:
            ContractViolationError: If s_align violates no-write contract.
        """
        B, N, K, D = proposals.shape

        # Get temperature (default 1.0, higher early in training)
        tau = 1.0
        if control is not None and control.tau is not None:
            tau = control.tau

        # Validate alignment contract
        s_align = None
        if control is not None and control.s_align is not None:
            assert_control_shape(control.s_align, "s_align", self.num_heads)
            s_align = control.s_align

        # Temperature-scaled sigmoid gating
        # Higher tau makes gates softer, more proposals get gradient
        gate_weights_raw = torch.sigmoid(scores / tau)  # [B, N, K]

        # Normalize (sum to 1, but NOT softmax - allows multiple high values)
        gate_sum = gate_weights_raw.sum(dim=-1, keepdim=True) + 1e-8
        gate_weights = gate_weights_raw / gate_sum  # [B, N, K]

        # Weighted sum of proposals
        # gate_weights: [B, N, K] -> [B, N, K, 1]
        # proposals: [B, N, K, D]
        p = (gate_weights.unsqueeze(-1) * proposals).sum(dim=2)  # [B, N, D]

        # Optional alignment modulation (contract-safe)
        if s_align is not None:
            # s_align is [] or [H] or [B, H] - compute scalar modulator
            s_align_mean = s_align.mean() if s_align.numel() > 1 else s_align

            clamp_min = control.clamp_min if control else self.clamp_min
            clamp_max = control.clamp_max if control else self.clamp_max

            # Compute modulator: 1 + alpha * s_align, clamped
            modulator = torch.clamp(
                1.0 + self.alpha * s_align_mean,
                clamp_min,
                clamp_max,
            )
            p = p * modulator

        # Project
        p = self.proj(p)

        # EMA integration with input
        # gamma: [H] -> scalar average for simplicity
        gamma = torch.sigmoid(self.gamma).mean()
        x_norm = self.norm(x)
        x_out = gamma * x_norm + (1 - gamma) * p

        # Track diagnostics
        with torch.no_grad():
            # Saturation: % of positions where max gate > 0.9
            max_gate = gate_weights.max(dim=-1)[0]
            self._last_gate_saturation = (max_gate > 0.9).float().mean()

            # Entropy of gate distribution
            entropy = -(gate_weights * (gate_weights + 1e-8).log()).sum(dim=-1).mean()
            self._last_gate_entropy = entropy

            # Mean gate weight
            self._last_gate_mean = gate_weights.max(dim=-1)[0].mean()

        return x_out

    def get_instrumentation(self) -> dict:
        """Get diagnostic metrics."""
        return {
            "gate_saturation": self._last_gate_saturation.item(),
            "gate_entropy": self._last_gate_entropy.item(),
            "gate_mean": self._last_gate_mean.item(),
        }
