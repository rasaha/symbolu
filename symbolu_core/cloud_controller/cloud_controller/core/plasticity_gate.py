"""Plasticity Gate — permission to act.

Ported from PlasticityGate.forward() (minimal_controller.py:211-261).
Removed: nn.Module, nn.Sequential resistance projector, torch tensors.
Kept: double-smoothed EMA, sigmoid gate, all constants.

P_t = sigmoid(k_r * R_t - k_m * M_t + b_p)

Where:
    R_t = system stability/readiness (double-smoothed)
    M_t = misalignment of proposed action from current identity
    b_p = -1.0 ensures sigmoid floor at 0.27 (gate never fully closes)
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class PlasticityResult:
    plasticity: float       # P_t in [sigmoid(b_p), 1.0]
    resistance: float       # R_t (smoothed stability)
    misalignment: float     # M_t
    logit: float            # Raw logit before sigmoid


class PlasticityGate:
    """Determines whether the system is open to change right now.

    Double-smoothed resistance prevents gate flicker:
    - Fast EMA (alpha=0.1): blend instantaneous R with persistent state
    - Slow EMA (alpha=0.05): update persistent state gradually
    """

    def __init__(self, k_r: float = 2.0, k_m: float = 2.0, b_p: float = -1.0):
        self.k_r = k_r
        self.k_m = k_m
        self.b_p = b_p
        self._persistent_resistance = 0.5  # Initial midpoint

    def compute(
        self,
        resistance: float,
        misalignment: float = 0.0,
    ) -> PlasticityResult:
        """Compute plasticity gate value.

        Args:
            resistance: System stability score in [0, 1].
                1.0 = fully stable, 0.0 = highly fragile.
            misalignment: How far proposed action is from current state [0, inf).
                0.0 = minor change, 1.0 = doubling capacity.

        Returns:
            PlasticityResult with gate value, smoothed resistance, misalignment.
        """
        # Guard against NaN/infinity propagation
        if not math.isfinite(resistance):
            resistance = 0.5
        if not math.isfinite(misalignment):
            misalignment = 0.0

        # First smoothing: fast EMA against persistent state
        # Matches minimal_controller.py line 231
        r_smoothed = 0.9 * self._persistent_resistance + 0.1 * resistance

        # Second smoothing: slow update of persistent state from RAW r_smoothed
        # CG (line 254) updates from R_t.mean(dim=0), not from the already-smoothed value.
        # Using r_smoothed here (not self._persistent_resistance blended again)
        # prevents triple-smoothing that would over-dampen responsiveness.
        self._persistent_resistance = (
            0.95 * self._persistent_resistance + 0.05 * resistance
        )

        # P_t = sigmoid(k_r * R_t - k_m * M_t + b_p)
        # Matches minimal_controller.py lines 244-249
        logit = self.k_r * r_smoothed - self.k_m * misalignment + self.b_p

        # Numerically stable sigmoid — avoids overflow for large negative logits
        # (torch.sigmoid handles this internally; we must do it explicitly)
        if logit >= 0:
            plasticity = 1.0 / (1.0 + math.exp(-logit))
        else:
            exp_logit = math.exp(logit)
            plasticity = exp_logit / (1.0 + exp_logit)

        return PlasticityResult(
            plasticity=plasticity,
            resistance=r_smoothed,
            misalignment=misalignment,
            logit=logit,
        )

    def reset(self) -> None:
        self._persistent_resistance = 0.5
