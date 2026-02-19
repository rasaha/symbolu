"""
SpandaState: Psi state evolution module.

Computes Delta_t = MLP(h_t) and evolves Psi via leaky integration + norm clamping.
Psi is computed per-sequence (no module-level mutable state).

For T <= 512: sequential loop with per-step norm clamping.
For T > 512: parallel discounted cumsum with output-only norm clamping.
"""

import math
import torch
import torch.nn as nn


class SpandaState(nn.Module):
    """
    Spanda state evolution: Delta computation + Psi recurrence.

    Psi_raw_t = gamma * Psi_{t-1} + Delta_t
    Psi_t = Psi_raw_t / max(1, ||Psi_raw_t|| / c)

    Args:
        embed_dim: Dimension of input hidden states h_t.
        psi_dim: Dimension of Psi state vector (default 256).
        decay_gamma: Leaky integration factor (default 0.99).
    """

    # Threshold for switching from sequential loop to parallel discounted cumsum.
    PARALLEL_THRESHOLD = 512

    def __init__(self, embed_dim: int, psi_dim: int = 256, decay_gamma: float = 0.99):
        super().__init__()
        self.psi_dim = psi_dim
        self.decay_gamma = decay_gamma
        self.norm_clamp_c = math.sqrt(psi_dim)

        # Delta MLP: h_t -> Delta_t
        self.delta_mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, psi_dim),
        )

    def _norm_clamp(self, psi: torch.Tensor) -> torch.Tensor:
        """Clamp Psi norm to ceiling c, preserving direction and magnitude below c.

        psi / max(1, ||psi|| / c)  -- identity when ||psi|| <= c, scales down otherwise.
        """
        norms = psi.norm(dim=-1, keepdim=True)
        scale = torch.clamp(norms / self.norm_clamp_c, min=1.0)
        return psi / scale

    def _sequential_forward(self, delta: torch.Tensor) -> torch.Tensor:
        """Sequential loop with per-step norm clamping. Used for T <= 512."""
        B, T, D = delta.shape
        psi = torch.zeros(B, 1, D, device=delta.device, dtype=delta.dtype)
        psi_seq = []
        for t in range(T):
            psi = self.decay_gamma * psi + delta[:, t : t + 1, :]
            psi = self._norm_clamp(psi)
            psi_seq.append(psi)
        return torch.cat(psi_seq, dim=1)  # [B, T, psi_dim]

    def _parallel_forward(self, delta: torch.Tensor) -> torch.Tensor:
        """Parallel discounted cumsum with output-only norm clamping. Used for T > 512.

        Closed form: Psi_t = sum_{s=0}^{t} gamma^{t-s} * Delta_s
        Computed via: scale delta by gamma^{-t}, cumsum, rescale by gamma^t.
        Norm clamping applied only at output (not per-step).
        """
        B, T, D = delta.shape
        gamma = self.decay_gamma

        # Geometric weights: gamma^0, gamma^1, ..., gamma^{T-1}
        powers = gamma ** torch.arange(T, device=delta.device, dtype=delta.dtype)
        powers = powers.unsqueeze(0).unsqueeze(-1)  # [1, T, 1]

        # Guard against division by very small powers at long sequences
        inv_powers = 1.0 / powers.clamp(min=1e-30)

        # Multiply delta by gamma^{-t}, cumsum, then re-apply gamma^t
        delta_scaled = delta * inv_powers
        cumsum = torch.cumsum(delta_scaled, dim=1)
        psi = cumsum * powers

        # Output-only norm clamping
        psi = self._norm_clamp(psi)
        return psi

    def forward(self, h: torch.Tensor) -> tuple:
        """
        Compute Psi state sequence from hidden states.

        Args:
            h: [B, T, embed_dim] -- full sequence of hidden states from backbone.

        Returns:
            psi: [B, T, psi_dim] -- Psi state trajectory.
            delta: [B, T, psi_dim] -- Delta sequence (for regularizers).
        """
        delta = self.delta_mlp(h)  # [B, T, psi_dim]
        T = delta.size(1)

        if T <= self.PARALLEL_THRESHOLD:
            psi = self._sequential_forward(delta)
        else:
            psi = self._parallel_forward(delta)

        return psi, delta
