"""
Agentic Plasticity Gate — Sigmoid permission-to-act gate.

Computes a smooth, flicker-resistant gate value [~0.27, 1.0] that
indicates how open the system is to taking action.  High stability
(low drift) opens the gate; high misalignment closes it.

    P_t = sigmoid(k_r * R_t - k_m * M_t + b_p)

Uses double-EMA smoothing to prevent gate oscillation from noisy
input signals.

OLM mapping: O5_COGNITION (perceptual trust), O10_UNIFYING (coherence)

Pattern extracted from cloud_controller.core.plasticity_gate.PlasticityGate,
rewritten for AI agent governance (no K8s dependencies).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlasticityResult:
    """Outcome of a plasticity gate computation.

    Attributes:
        plasticity: Final gate value [~0.27, 1.0].  Higher = more open.
        resistance: Smoothed stability input after EMA blending.
        misalignment: Raw misalignment (drift) input.
        logit: Pre-sigmoid logit value.
    """
    plasticity: float
    resistance: float
    misalignment: float
    logit: float


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

class PlasticityGate:
    """Double-smoothed sigmoid gate controlling permission to act.

    Parameters:
        k_r: Resistance (stability) weight.  Higher = stability opens gate faster.
        k_m: Misalignment weight.  Higher = drift closes gate faster.
        b_p: Bias.  Negative bias ensures a floor (~0.27 at b_p=-1.0).
        fast_alpha: EMA factor for instantaneous blending (default 0.1).
        slow_alpha: EMA factor for persistent state update (default 0.05).

    Usage::

        gate = PlasticityGate()
        result = gate.compute(resistance=0.8, misalignment=0.1)
        if result.plasticity > 0.5:
            proceed_with_action()
    """

    def __init__(
        self,
        *,
        k_r: float = 2.0,
        k_m: float = 2.0,
        b_p: float = -1.0,
        fast_alpha: float = 0.1,
        slow_alpha: float = 0.05,
    ) -> None:
        self.k_r = k_r
        self.k_m = k_m
        self.b_p = b_p
        self._fast_alpha = fast_alpha
        self._slow_alpha = slow_alpha
        self._persistent_resistance: float = 0.5

    def compute(
        self,
        resistance: float,
        misalignment: float = 0.0,
    ) -> PlasticityResult:
        """Compute the plasticity gate value.

        Args:
            resistance: System stability signal [0, 1].
                High stability = system ready for action.
            misalignment: Drift / divergence signal [0, 1].
                High misalignment = system drifting from goals.

        Returns:
            PlasticityResult with the gate value and intermediates.
        """
        # Fast EMA: blend instantaneous resistance with persistent state
        blended = (
            self._fast_alpha * resistance
            + (1 - self._fast_alpha) * self._persistent_resistance
        )

        # Slow EMA: gradually update persistent state
        self._persistent_resistance = (
            self._slow_alpha * blended
            + (1 - self._slow_alpha) * self._persistent_resistance
        )

        # Logit → sigmoid
        logit = self.k_r * blended - self.k_m * misalignment + self.b_p
        plasticity = 1.0 / (1.0 + math.exp(-logit))

        return PlasticityResult(
            plasticity=plasticity,
            resistance=blended,
            misalignment=misalignment,
            logit=logit,
        )

    def reset(self) -> None:
        """Reset persistent state to neutral (0.5)."""
        self._persistent_resistance = 0.5
