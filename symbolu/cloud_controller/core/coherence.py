"""Coherence Model — multi-signal agreement scoring.

New for cloud controller (no direct CG equivalent — CG uses CSR/Vritti/Guna
which are domain-specific). This implements the coherence concept in
infrastructure terms.

Coherence = do the signals agree that something is happening?
- All signals elevated and agreeing -> C_t ~ 1.0 (coherent pressure)
- Only CPU elevated, rest flat -> C_t ~ 0.3 (incoherent, probably false alarm)

Three signal groups:
    c_infra:    CPU, memory, disk I/O, network
    c_app:      latency p99, error rate, throughput
    c_business: queue depth, conversions (optional)
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from symbolu.cloud_controller.config import INFRA_KEYS, APP_KEYS, BUSINESS_KEYS


@dataclass
class CoherenceResult:
    coherence: float        # C_t overall in [0, 1]
    c_infra: float          # Infrastructure signal agreement
    c_app: float            # Application signal agreement
    c_business: float       # Business signal agreement
    c_cross: float          # Cross-group agreement (infra vs app vs business)
    instability: float      # 1 - coherence (for damping input)
    elevated_count: int     # How many signals are above baseline
    missing_signal_count: int = 0  # How many expected signals are absent
    signal_health: float = 1.0     # 1.0 = all present, degrades with missing


class CoherenceModel:
    """Computes multi-signal agreement for infrastructure metrics.

    V1: Rule-based agreement scoring.
    A signal is "elevated" if it's above a threshold (default 0.5 on normalized [0,1]).
    Coherence is high when elevated signals agree across groups.

    V2: Hysteresis band prevents oscillation when coherence hovers near
    a decision threshold. Uses a small dead-band around the previous value
    so minor fluctuations don't cause the output to flicker.
    """

    def __init__(
        self,
        w_infra: float = 0.4,
        w_app: float = 0.4,
        w_business: float = 0.2,
        elevation_threshold: float = 0.5,
        hysteresis_band: float = 0.05,
        ema_beta: float = 0.7,
    ):
        self.w_infra = w_infra
        self.w_app = w_app
        self.w_business = w_business
        self.elevation_threshold = elevation_threshold
        self.hysteresis_band = hysteresis_band
        self.ema_beta = ema_beta  # Temporal smoothing factor (0=no smoothing, 1=frozen)
        self._prev_coherence: Optional[float] = None

    def compute(
        self,
        metrics: Dict[str, float],
        infra_keys: Tuple[str, ...] = INFRA_KEYS,
        app_keys: Tuple[str, ...] = APP_KEYS,
        business_keys: Tuple[str, ...] = BUSINESS_KEYS,
    ) -> CoherenceResult:
        """Compute coherence across signal groups.

        Args:
            metrics: Dict of metric_name -> normalized value in [0, 1].
            infra_keys: Which metric keys belong to infrastructure group.
            app_keys: Which metric keys belong to application group.
            business_keys: Which metric keys belong to business group.

        Returns:
            CoherenceResult with per-group and overall coherence.
        """
        c_infra = self._group_agreement(metrics, infra_keys)
        c_app = self._group_agreement(metrics, app_keys)
        c_business = self._group_agreement(metrics, business_keys)

        # Signal health: count missing signals from primary groups
        expected_count = len(infra_keys) + len(app_keys)
        present_count = sum(1 for k in (*infra_keys, *app_keys) if k in metrics)
        missing_signal_count = expected_count - present_count
        # Each missing signal degrades health by 15% — partial observability penalty
        signal_health = max(0.3, 1.0 - 0.15 * missing_signal_count)

        # Cross-group coherence: do infra and app signals agree in direction?
        # E.g., if infra says high load but app says latency is fine, cross-group
        # coherence is low — signals are contradicting across layers.
        group_means = []
        for keys_group in (infra_keys, app_keys, business_keys):
            vals = [metrics[k] for k in keys_group if k in metrics]
            if vals:
                group_means.append(sum(vals) / len(vals))
        if len(group_means) >= 2:
            c_cross = 1.0 - min(float(np.var(group_means)) / 0.25, 1.0)
        else:
            c_cross = 0.5

        # Weighted coherence — includes both within-group and cross-group
        total_weight = self.w_infra + self.w_app
        if any(k in metrics for k in business_keys):
            total_weight += self.w_business
            within_coherence = (
                self.w_infra * c_infra
                + self.w_app * c_app
                + self.w_business * c_business
            ) / total_weight
        else:
            within_coherence = (
                self.w_infra * c_infra
                + self.w_app * c_app
            ) / total_weight

        # Blend within-group (70%) and cross-group (30%) for final coherence
        coherence = 0.7 * within_coherence + 0.3 * c_cross

        # Apply signal health degradation — missing signals reduce confidence
        coherence *= signal_health

        # Temporal EMA smoothing — prevents noisy coherence from causing
        # decision paralysis. Smooths out rapid oscillations while still
        # tracking genuine regime changes.
        if self._prev_coherence is not None and self.ema_beta > 0:
            coherence = self.ema_beta * self._prev_coherence + (1.0 - self.ema_beta) * coherence

        # Hysteresis: if coherence is within the dead-band of the previous
        # value, hold the previous value to prevent flicker.
        if self._prev_coherence is not None and self.hysteresis_band > 0:
            delta = coherence - self._prev_coherence
            if abs(delta) < self.hysteresis_band:
                coherence = self._prev_coherence
        self._prev_coherence = coherence

        # Count elevated signals
        elevated = sum(
            1 for v in metrics.values()
            if v > self.elevation_threshold
        )

        return CoherenceResult(
            coherence=coherence,
            c_infra=c_infra,
            c_app=c_app,
            c_business=c_business,
            c_cross=c_cross,
            instability=1.0 - coherence,
            elevated_count=elevated,
            missing_signal_count=missing_signal_count,
            signal_health=signal_health,
        )

    def _group_agreement(
        self,
        metrics: Dict[str, float],
        keys: tuple,
    ) -> float:
        """Compute agreement within a signal group.

        Agreement is high when signals are all elevated or all calm.
        Agreement is low when signals disagree (some up, some down).

        Returns value in [0, 1].
        """
        values = [metrics[k] for k in keys if k in metrics]
        if not values:
            return 0.5  # No data — neutral
        if len(values) == 1:
            # Single signal = incomplete information, not "agreement"
            # Return neutral 0.5 regardless of value — one signal can't agree with itself
            return 0.5

        # Clamp to [0, 1] to prevent variance formula from breaking on non-normalized input
        arr = np.clip(np.array(values), 0.0, 1.0)

        # Agreement = 1 - normalized variance
        # When all signals are similar (all high or all low), variance is low -> agreement high
        # When signals disagree, variance is high -> agreement low
        variance = float(np.var(arr))
        # Max possible variance for [0,1] signals is 0.25 (half at 0, half at 1)
        agreement = 1.0 - min(variance / 0.25, 1.0)

        return agreement
