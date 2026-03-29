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
from typing import Dict, Optional


@dataclass
class CoherenceResult:
    coherence: float        # C_t overall in [0, 1]
    c_infra: float          # Infrastructure signal agreement
    c_app: float            # Application signal agreement
    c_business: float       # Business signal agreement
    instability: float      # 1 - coherence (for damping input)
    elevated_count: int     # How many signals are above baseline


class CoherenceModel:
    """Computes multi-signal agreement for infrastructure metrics.

    V1: Rule-based agreement scoring.
    A signal is "elevated" if it's above a threshold (default 0.5 on normalized [0,1]).
    Coherence is high when elevated signals agree across groups.
    """

    def __init__(
        self,
        w_infra: float = 0.4,
        w_app: float = 0.4,
        w_business: float = 0.2,
        elevation_threshold: float = 0.5,
    ):
        self.w_infra = w_infra
        self.w_app = w_app
        self.w_business = w_business
        self.elevation_threshold = elevation_threshold

    def compute(
        self,
        metrics: Dict[str, float],
        infra_keys: tuple = ("cpu", "memory"),
        app_keys: tuple = ("latency_p99", "error_rate"),
        business_keys: tuple = ("queue_depth",),
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

        # Weighted coherence
        total_weight = self.w_infra + self.w_app
        if any(k in metrics for k in business_keys):
            total_weight += self.w_business
            coherence = (
                self.w_infra * c_infra
                + self.w_app * c_app
                + self.w_business * c_business
            ) / total_weight
        else:
            coherence = (
                self.w_infra * c_infra
                + self.w_app * c_app
            ) / total_weight

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
            instability=1.0 - coherence,
            elevated_count=elevated,
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
