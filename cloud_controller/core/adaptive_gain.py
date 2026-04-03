"""Adaptive Gain — action magnitude controller.

Ported from AdaptiveGain.compute() (minimal_controller.py:274-302).
Direct port — original was already pure math with no torch dependency.

G_t = clip(G_base * f_phase * f_coh, G_min, G_max)

Rate-limited: max 10% of G_base change per cycle.

Cloud adaptations:
- f_phase uses time-of-day context instead of training warmup
- G_base reduced from 3.0 to 1.0 (conservative)
- G_min set to 0.0 (allow "do nothing")
"""

import math
from dataclasses import dataclass
from typing import Optional


# Phase multipliers for time-of-day context
PHASE_MULTIPLIERS = {
    "peak": 1.0,       # Full responsiveness during peak hours
    "normal": 0.8,     # Moderate during normal hours
    "off_peak": 0.6,   # Conservative during off-peak
    "maintenance": 0.3, # Minimal during maintenance windows
}


@dataclass
class GainResult:
    gain: float         # G_t (rate-limited, clamped)
    f_phase: float      # Phase factor
    f_coh: float        # Coherence factor
    target: float       # Pre-rate-limited target
    rate_limited: bool  # Whether rate limiting was applied


class AdaptiveGain:
    """Controls how aggressively the system should respond.

    Rate limiting (max 10% of G_base per cycle) prevents oscillation.
    With G_base=1.0, gain changes by at most +/-0.1 per cycle.
    """

    def __init__(
        self,
        G_base: float = 1.0,
        G_min: float = 0.0,
        G_max: float = 3.0,
    ):
        self.G_base = G_base
        self.G_min = G_min
        self.G_max = G_max
        self._prev_gain: Optional[float] = None
        self._bootstrapped = False

    def compute(
        self,
        coherence: Optional[float] = None,
        phase: str = "normal",
        step: int = 0,
        warmup_steps: int = 100,
    ) -> GainResult:
        """Compute rate-limited adaptive gain.

        Args:
            coherence: Multi-signal agreement score in [0, 1]. None = use default.
            phase: Time context — "peak", "normal", "off_peak", "maintenance".
            step: Current cycle number (for initial warmup ramp).
            warmup_steps: Cycles for initial warmup (controller startup, not training).

        Returns:
            GainResult with gain value and component factors.
        """
        # f_phase: ramp from 0.5 to phase target over warmup
        # Matches minimal_controller.py line 282
        # When bootstrapped, skip warmup ramp (system already characterized)
        phase_target = PHASE_MULTIPLIERS.get(phase, 0.8)
        if self.bootstrapped:
            warmup_factor = 1.0
        else:
            warmup_factor = min(1.0, 0.5 + 0.5 * step / max(warmup_steps, 1))
        f_phase = phase_target * warmup_factor

        # f_coh: sigmoid-based coherence factor centered at 0.5
        # Coefficient 4.0 controls sharpness of transition
        # Matches minimal_controller.py line 286
        if coherence is not None:
            f_coh = 0.5 + 0.5 / (1.0 + math.exp(-(coherence - 0.5) * 4.0))
        else:
            f_coh = 0.75  # Default when no coherence signal

        # Clip to [G_min, G_max]
        # Matches minimal_controller.py lines 290-293
        target = max(self.G_min, min(
            self.G_max,
            self.G_base * f_phase * f_coh,
        ))

        # Rate limiting: max 10% of G_base per cycle (min 0.01 to prevent deadlock when G_base=0)
        # Matches minimal_controller.py lines 296-299
        rate_limited = False
        if self._prev_gain is not None:
            max_delta = max(self.G_base * 0.1, 0.01)
            clamped = max(
                self._prev_gain - max_delta,
                min(self._prev_gain + max_delta, target),
            )
            if clamped != target:
                rate_limited = True
            target_final = clamped
        else:
            target_final = target

        self._prev_gain = target_final

        return GainResult(
            gain=target_final,
            f_phase=f_phase,
            f_coh=f_coh,
            target=target,
            rate_limited=rate_limited,
        )

    def bootstrap(self) -> None:
        """Mark gain as bootstrapped so warmup ramp starts at 100%.

        When historical data has been replayed, the controller doesn't
        need a conservative ramp — it already knows the system.
        """
        self._bootstrapped = True
        self._prev_gain = None

    @property
    def bootstrapped(self) -> bool:
        return getattr(self, '_bootstrapped', False)

    def reset(self) -> None:
        self._prev_gain = None
        self._bootstrapped = False
