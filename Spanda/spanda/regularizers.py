"""
Spanda trajectory regularizers.

Phase 1: Cross-entropy only (no regularizers).
Phase 2: Add L_step (alpha=1e-4) -- penalize large Psi jumps.
Phase 3: Add L_smooth (beta=1e-4) -- penalize jerk (change in Delta).

Regularizers are NOT enabled by default. Enable via set_phase().
"""

import torch
import torch.nn as nn


class SpandaRegularizers(nn.Module):
    """
    Trajectory smoothness regularizers for Spanda Psi state.

    L_step   = alpha * mean(||Delta_t||^2)
    L_smooth = beta  * mean(||Delta_t - Delta_{t-1}||^2)

    Args:
        alpha: Weight for L_step (default 1e-4).
        beta: Weight for L_smooth (default 1e-4).
    """

    def __init__(self, alpha: float = 1e-4, beta: float = 1e-4):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self._phase = 1  # Start in phase 1 (CE only)

    def set_phase(self, phase: int):
        """Set regularizer phase (1=CE only, 2=+L_step, 3=+L_step+L_smooth)."""
        assert phase in (1, 2, 3), f"Phase must be 1, 2, or 3, got {phase}"
        self._phase = phase

    @property
    def phase(self) -> int:
        return self._phase

    def forward(self, delta: torch.Tensor) -> dict:
        """
        Compute regularization losses based on current phase.

        Args:
            delta: [B, T, psi_dim] -- Delta sequence from SpandaState.

        Returns:
            Dict with:
                'l_step': L_step loss (0 if phase < 2)
                'l_smooth': L_smooth loss (0 if phase < 3)
                'total_reg': Combined regularization loss
        """
        device = delta.device
        dtype = delta.dtype

        l_step = torch.tensor(0.0, device=device, dtype=dtype)
        l_smooth = torch.tensor(0.0, device=device, dtype=dtype)

        if self._phase >= 2:
            # L_step: penalize large Delta magnitudes
            l_step = self.alpha * (delta ** 2).sum(dim=-1).mean()

        if self._phase >= 3:
            # L_smooth: penalize jerk (change in consecutive Deltas)
            if delta.size(1) > 1:
                delta_diff = delta[:, 1:, :] - delta[:, :-1, :]
                l_smooth = self.beta * (delta_diff ** 2).sum(dim=-1).mean()

        return {
            "l_step": l_step,
            "l_smooth": l_smooth,
            "total_reg": l_step + l_smooth,
        }
