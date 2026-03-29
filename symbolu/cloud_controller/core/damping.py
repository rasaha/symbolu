"""Damping — volatility suppression.

Ported from Damping.compute() (minimal_controller.py:331-379).
Direct port — original was already pure math.

d_t = exp(-k_dv * V_excess - k_dc * U_ema)

Key properties preserved from CG:
1. Asymmetric EMA (alpha_up=0.10, alpha_down=0.20) — fast detect, fast recover
2. Baseline-relative variance — self-calibrating, won't permanently damp high-variance systems
3. Hard floor at 0.01 — never fully suppresses action
4. Rate limited +/-0.1 per cycle — damping can't slam on/off

Cloud adaptation: "grad_variance" renamed to "metric_variance".
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class DampingResult:
    damping: float          # d_t in [0.01, 1.0]
    v_ema: float            # Smoothed variance (asymmetric EMA)
    v_baseline: float       # Slow-moving variance baseline
    v_excess: float         # Variance above baseline
    u_ema: float            # Smoothed coherence instability
    rate_limited: bool      # Whether rate limiting was applied


class Damping:
    """Suppresses action when system is volatile.

    Uses baseline-relative variance: a system with naturally high metric
    variance (e.g., batch processing cluster) won't be permanently damped.
    Only variance ABOVE its own normal triggers damping.

    Asymmetric EMA:
    - Rising signal: alpha=0.10 (detect spikes in ~10 cycles)
    - Falling signal: alpha=0.20 (recover in ~5 cycles)
    """

    def __init__(self, k_dv: float = 1.0, k_dc: float = 0.5, warmup_steps: int = 0):
        self.k_dv = k_dv
        self.k_dc = k_dc
        self._V_ema = 0.0
        self._U_ema = 0.0
        self._V_baseline = 0.0
        self._baseline_initialized = False
        self._prev_d_t: Optional[float] = None
        self._warmup_remaining = warmup_steps  # Hold d=1.0 to let EMAs stabilize

    def compute(
        self,
        metric_variance: float,
        coherence_instability: float = 0.0,
    ) -> DampingResult:
        """Compute damping factor.

        Args:
            metric_variance: Variance of primary metrics over recent window.
                Higher = more volatile system.
            coherence_instability: How much signals disagree. 0 = full agreement.

        Returns:
            DampingResult with damping factor and internal state.
        """
        # Initialize baseline from first observation
        # Matches minimal_controller.py lines 338-341
        if not self._baseline_initialized:
            self._V_baseline = metric_variance
            self._V_ema = metric_variance
            self._baseline_initialized = True

        # Asymmetric EMA: fast rise (detect spikes) but fast decay (recover quickly)
        # Matches minimal_controller.py lines 344-351
        if metric_variance > self._V_ema:
            self._V_ema = 0.90 * self._V_ema + 0.10 * metric_variance
        else:
            self._V_ema = 0.80 * self._V_ema + 0.20 * metric_variance

        if coherence_instability > self._U_ema:
            self._U_ema = 0.90 * self._U_ema + 0.10 * coherence_instability
        else:
            self._U_ema = 0.80 * self._U_ema + 0.20 * coherence_instability

        # Update slow baseline (0.999 decay = adapts over ~1000 cycles)
        # Matches minimal_controller.py line 354
        self._V_baseline = 0.999 * self._V_baseline + 0.001 * metric_variance

        # Warmup after startup/resume: hold d=1.0 while EMAs stabilize
        # Matches minimal_controller.py lines 357-360
        if self._warmup_remaining > 0:
            self._warmup_remaining -= 1
            self._prev_d_t = 1.0
            return DampingResult(
                damping=1.0,
                v_ema=self._V_ema,
                v_baseline=self._V_baseline,
                v_excess=0.0,
                u_ema=self._U_ema,
                rate_limited=False,
            )

        # Baseline-relative damping
        # Matches minimal_controller.py lines 366-372
        V_base = max(self._V_baseline, 1e-8)
        V_ratio = self._V_ema / V_base
        V_excess = max(0.0, V_ratio - 1.0)

        exponent = -(self.k_dv * V_excess + self.k_dc * self._U_ema)
        d_t = math.exp(max(exponent, -10.0))
        d_t = max(d_t, 0.01)  # Hard floor

        # Rate limit: max +/-0.1 per cycle
        # Matches minimal_controller.py lines 375-376
        rate_limited = False
        if self._prev_d_t is not None:
            clamped = max(
                self._prev_d_t - 0.1,
                min(self._prev_d_t + 0.1, d_t),
            )
            if clamped != d_t:
                rate_limited = True
            d_t = clamped

        self._prev_d_t = d_t

        return DampingResult(
            damping=d_t,
            v_ema=self._V_ema,
            v_baseline=self._V_baseline,
            v_excess=V_excess,
            u_ema=self._U_ema,
            rate_limited=rate_limited,
        )

    def reset(self, warmup_steps: int = 0) -> None:
        self._V_ema = 0.0
        self._U_ema = 0.0
        self._V_baseline = 0.0
        self._baseline_initialized = False
        self._prev_d_t = None
        self._warmup_remaining = warmup_steps
