"""HPA interaction analysis.

Classifies how an operations-package shadow recommendation would relate to any
HorizontalPodAutoscaler that manages the same workload. The shadow phase never claims
control over an HPA-managed resource and never simulates patching, disabling, or
overriding an HPA — it only reports the relationship so contention risk is visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contracts import HpaInteraction, HorizontalPodAutoscalerObservation


@dataclass(frozen=True)
class HpaInteractionResult:
    classification: HpaInteraction
    detail: str
    within_bounds: Optional[bool] = None
    contention_risk: bool = False

    def to_dict(self) -> dict:
        return {
            "classification": self.classification.value,
            "detail": self.detail,
            "within_bounds": self.within_bounds,
            "contention_risk": self.contention_risk,
        }


class HpaInteractionAnalyzer:
    def analyze(
        self,
        *,
        hpa: Optional[HorizontalPodAutoscalerObservation],
        current_replicas: int,
        recommended_replicas: int,
    ) -> HpaInteractionResult:
        if hpa is None:
            return HpaInteractionResult(HpaInteraction.NO_HPA, "no HPA manages this target")

        # Incomplete HPA state -> cannot evaluate compatibility.
        if hpa.min_replicas is None or hpa.max_replicas is None:
            return HpaInteractionResult(HpaInteraction.HPA_STATE_INCOMPLETE,
                                        "HPA bounds unavailable")

        within = hpa.min_replicas <= recommended_replicas <= hpa.max_replicas
        if not within:
            return HpaInteractionResult(
                HpaInteraction.HPA_BOUNDS_CONFLICT,
                f"recommended {recommended_replicas} outside HPA bounds "
                f"[{hpa.min_replicas},{hpa.max_replicas}]",
                within_bounds=False, contention_risk=True)

        # Direction check: does the recommendation push opposite to the HPA's own
        # desired trajectory? If so, executing it could create controller contention.
        rec_dir = _sign(recommended_replicas - current_replicas)
        hpa_dir = _sign(hpa.desired_replicas - current_replicas)
        if rec_dir != 0 and hpa_dir != 0 and rec_dir != hpa_dir:
            return HpaInteractionResult(
                HpaInteraction.HPA_OBSERVED_CONFLICT,
                f"recommendation direction {rec_dir} opposes HPA direction {hpa_dir}",
                within_bounds=True, contention_risk=True)

        return HpaInteractionResult(
            HpaInteraction.HPA_OBSERVED_COMPATIBLE,
            "recommendation within HPA bounds and not opposing HPA direction",
            within_bounds=True, contention_risk=False)


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


__all__ = ["HpaInteractionResult", "HpaInteractionAnalyzer"]
