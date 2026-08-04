"""Routing policy: soft weighting, presets, deterministic tie-breaking.

Policy is explicit and inspectable. The hard constraints in ``constraints.py`` decide
*eligibility*; policy decides only the *ranking* of already-eligible candidates. A soft
weight can never restore a disqualified candidate.

Scoring dimensions (each a fit score in [0, 1], higher is better):

    capability_fit, policy_fit, context_fit, quality_score, latency_score,
    cost_score, privacy_score, reliability_score, availability_score

The quality-preference preset changes only the ``quality`` / ``cost`` / ``latency``
weights; the remaining base weights are held fixed so presets are comparable. The total
is a weight-normalized average, so it always lies in [0, 1].

Tie-break rule (deterministic, documented): candidates with an equal total score
(compared at 6-decimal precision) are ordered by ``model_id`` ascending, then
``provider_id`` ascending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .contracts import PolicyViolation, QualityPreference

ROUND = 6
TIE_BREAK_RULE = "equal total score → order by (model_id asc, provider_id asc)"

# Fixed base weights (independent of the quality preference).
_BASE_WEIGHTS: Dict[str, float] = {
    "capability_fit": 1.0,
    "policy_fit": 0.5,
    "context_fit": 0.5,
    "privacy_score": 0.5,
    "reliability_score": 0.6,
    "availability_score": 0.4,
}

# Preset weights for the three preference-sensitive dimensions.
_PREFERENCE_WEIGHTS: Dict[str, Dict[str, float]] = {
    QualityPreference.QUALITY_FIRST.value: {"quality_score": 1.4, "cost_score": 0.3, "latency_score": 0.2},
    QualityPreference.BALANCED.value:      {"quality_score": 1.0, "cost_score": 0.6, "latency_score": 0.5},
    QualityPreference.COST_FIRST.value:    {"quality_score": 0.7, "cost_score": 1.4, "latency_score": 0.3},
    QualityPreference.LATENCY_FIRST.value: {"quality_score": 0.8, "cost_score": 0.3, "latency_score": 1.4},
}

ALL_DIMENSIONS = tuple(sorted(set(_BASE_WEIGHTS) | {"quality_score", "cost_score", "latency_score"}))


@dataclass(frozen=True)
class RoutingPolicy:
    """A concrete, validated policy: a preference preset plus optional weight overrides."""

    preference: QualityPreference = QualityPreference.BALANCED
    weight_overrides: Dict[str, float] = field(default_factory=dict)
    policy_version: str = ""  # filled by the controller from the request / package default

    def __post_init__(self) -> None:
        if not isinstance(self.preference, QualityPreference):
            object.__setattr__(self, "preference", QualityPreference(str(self.preference)))
        for k, v in (self.weight_overrides or {}).items():
            if k not in ALL_DIMENSIONS:
                raise PolicyViolation(f"unknown scoring dimension in weight_overrides: '{k}'")
            if not isinstance(v, (int, float)) or v < 0:
                raise PolicyViolation(f"weight for '{k}' must be a non-negative number, got {v!r}")

    def weights(self) -> Dict[str, float]:
        """Resolve the full weight vector for this policy (deterministic)."""
        w = dict(_BASE_WEIGHTS)
        w.update(_PREFERENCE_WEIGHTS[self.preference.value])
        w.update({k: float(v) for k, v in (self.weight_overrides or {}).items()})
        total = sum(w.values())
        if total <= 0:
            raise PolicyViolation("resolved policy weights sum to zero; no ranking is possible")
        return w

    def fingerprint(self) -> str:
        import hashlib
        import json
        payload = json.dumps(
            {"preference": self.preference.value,
             "weights": {k: round(v, ROUND) for k, v in sorted(self.weights().items())},
             "policy_version": self.policy_version},
            sort_keys=True, separators=(",", ":"))
        return "pol-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def weight_preset_name(preference: QualityPreference) -> str:
    return f"{preference.value}"


__all__ = ["RoutingPolicy", "ROUND", "TIE_BREAK_RULE", "ALL_DIMENSIONS", "weight_preset_name"]
