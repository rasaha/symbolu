"""Explicit, versioned, digest-bound recommendation policy + deterministic score breakdown.

The policy makes every weight and threshold that influences ranking EXPLICIT — there is no
opaque model and no silently-selected weight. It distinguishes (per the Phase-3 contract):

  * hard-constraint filtering — handled BEFORE scoring (see :mod:`.constraints`); not a weight;
  * forecast coverage — how well a plan's capacity meets the forecast (+ preferred);
  * dependency / bottleneck risk — a plan that merely moves the bottleneck is penalized;
  * SLO / reliability risk — a plan that raises reliability risk is penalized;
  * cost delta — added cost is penalized (cost is a preference, never an authorizer);
  * change magnitude / stability — larger disruptive changes are mildly penalized;
  * uncertainty / confidence penalty — low forecast confidence dampens aggressive scaling;
  * operator preferences — an explicit extra weight on holding (NO_CHANGE bias).

All weights are finite, validated, versioned, and serialized; the policy digest is bound
into the recommendation evidence. Scoring is a pure, deterministic function of a candidate's
derived features and this policy, so a stored :class:`ScoreBreakdown` can be recomputed
exactly (which the recommendation record does at construction, rejecting a forged score).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from ..canonical.serialization import content_digest

RECOMMENDATION_POLICY_SCHEMA_VERSION = "capacity-recommendation-policy-1"
SCORE_BREAKDOWN_SCHEMA_VERSION = "capacity-score-breakdown-1"

_TOL = 1e-9

# The ordered feature names a score breakdown carries. Fixed so serialization is stable.
FEATURE_NAMES = (
    "coverage",             # in [0, 1]; 1.0 == fully covers required capacity (higher better)
    "bottleneck_risk",      # in [0, 1]; 1.0 == bottleneck merely transferred (higher worse)
    "reliability_risk",     # in [0, 1]; 1.0 == raises reliability/SLO risk (higher worse)
    "cost_increase_ratio",  # >= 0; added cost / baseline cost unit (higher worse)
    "change_magnitude",     # >= 0; |primary delta| / max(current, 1) (higher worse)
    "uncertainty",          # in [0, 1]; 1.0 == maximally uncertain forecast (higher worse)
    "hold_bias",            # 1.0 for NO_CHANGE else 0.0 (operator preference to hold)
)


class PolicyError(ValueError):
    """Raised when a recommendation policy or score breakdown is malformed (fail closed)."""


def _finite_nonneg(name: str, v: Any) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise PolicyError(f"{name} must be a finite number")
    if v < 0:
        raise PolicyError(f"{name} must be >= 0")
    return float(v)


@dataclass(frozen=True)
class RecommendationPolicy:
    """Explicit, versioned weights + thresholds governing candidate ranking."""

    policy_id: str = "recommend-baseline-default"
    # Weights (all >= 0). Coverage and hold_bias reward; the rest penalize.
    w_coverage: float = 4.0
    w_bottleneck_risk: float = 3.0
    w_reliability_risk: float = 3.0
    w_cost: float = 1.0
    w_change_magnitude: float = 0.5
    w_uncertainty: float = 1.0
    w_hold_bias: float = 0.25
    # Thresholds.
    min_forecast_confidence: float = 0.0     # abstain below this forecast confidence
    coverage_floor: float = 1.0              # feasible plans must cover >= this fraction
    tie_epsilon: float = 1e-6                # score gap <= this => semantic tie
    schema_version: str = RECOMMENDATION_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or self.policy_id == "":
            raise PolicyError("policy_id must be a non-empty string")
        for name in ("w_coverage", "w_bottleneck_risk", "w_reliability_risk", "w_cost",
                     "w_change_magnitude", "w_uncertainty", "w_hold_bias"):
            _finite_nonneg(name, getattr(self, name))
        for name in ("min_forecast_confidence", "coverage_floor"):
            v = _finite_nonneg(name, getattr(self, name))
            if v > 1.0 + _TOL:
                raise PolicyError(f"{name} must be in [0, 1]")
        if _finite_nonneg("tie_epsilon", self.tie_epsilon) > 1.0:
            raise PolicyError("tie_epsilon must be small (<= 1.0)")

    def weight_for(self, feature: str) -> float:
        return {
            "coverage": self.w_coverage,
            "bottleneck_risk": self.w_bottleneck_risk,
            "reliability_risk": self.w_reliability_risk,
            "cost_increase_ratio": self.w_cost,
            "change_magnitude": self.w_change_magnitude,
            "uncertainty": self.w_uncertainty,
            "hold_bias": self.w_hold_bias,
        }[feature]

    def sign_for(self, feature: str) -> float:
        """+1 for reward features, -1 for penalty features (fixed by the policy schema)."""
        return {
            "coverage": 1.0,
            "bottleneck_risk": -1.0,
            "reliability_risk": -1.0,
            "cost_increase_ratio": -1.0,
            "change_magnitude": -1.0,
            "uncertainty": -1.0,
            "hold_bias": 1.0,
        }[feature]

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "w_coverage": self.w_coverage,
            "w_bottleneck_risk": self.w_bottleneck_risk,
            "w_reliability_risk": self.w_reliability_risk,
            "w_cost": self.w_cost,
            "w_change_magnitude": self.w_change_magnitude,
            "w_uncertainty": self.w_uncertainty,
            "w_hold_bias": self.w_hold_bias,
            "min_forecast_confidence": self.min_forecast_confidence,
            "coverage_floor": self.coverage_floor,
            "tie_epsilon": self.tie_epsilon,
        }

    def digest(self) -> str:
        return content_digest("capacity_recommendation_policy", self.schema_version,
                              self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "RecommendationPolicy":
        if not isinstance(data, Mapping):
            raise PolicyError("policy must be a mapping")
        known = set(cls().to_canonical_dict())
        unknown = set(data) - known
        if unknown:
            raise PolicyError(f"unknown policy field(s): {sorted(unknown)}")
        d = cls().to_canonical_dict()
        d.update(data)
        return cls(
            policy_id=d["policy_id"],
            w_coverage=d["w_coverage"],
            w_bottleneck_risk=d["w_bottleneck_risk"],
            w_reliability_risk=d["w_reliability_risk"],
            w_cost=d["w_cost"],
            w_change_magnitude=d["w_change_magnitude"],
            w_uncertainty=d["w_uncertainty"],
            w_hold_bias=d["w_hold_bias"],
            min_forecast_confidence=d["min_forecast_confidence"],
            coverage_floor=d["coverage_floor"],
            tie_epsilon=d["tie_epsilon"],
            schema_version=d["schema_version"],
        )


@dataclass(frozen=True)
class ScoreBreakdown:
    """Deterministic per-feature score contributions + total (exactly recomputable)."""

    features: Mapping[str, float]
    contributions: Mapping[str, float]
    total_score: float
    policy_id: str
    policy_digest: str
    schema_version: str = SCORE_BREAKDOWN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label, m in (("features", self.features), ("contributions", self.contributions)):
            if not isinstance(m, Mapping):
                raise PolicyError(f"{label} must be a mapping")
            for k, v in m.items():
                if k not in FEATURE_NAMES:
                    raise PolicyError(f"unknown {label} feature: {k!r}")
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                    raise PolicyError(f"{label}[{k}] must be finite")
        if set(self.features) != set(FEATURE_NAMES) or set(self.contributions) != set(FEATURE_NAMES):
            raise PolicyError("features/contributions must cover exactly the fixed feature set")
        if isinstance(self.total_score, bool) or not isinstance(self.total_score, (int, float)) or not math.isfinite(self.total_score):
            raise PolicyError("total_score must be finite")
        recomputed = sum(self.contributions[f] for f in FEATURE_NAMES)
        if abs(recomputed - self.total_score) > 1e-6:
            raise PolicyError("total_score must equal the sum of contributions")
        object.__setattr__(self, "features", {k: float(self.features[k]) for k in FEATURE_NAMES})
        object.__setattr__(self, "contributions", {k: float(self.contributions[k]) for k in FEATURE_NAMES})

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "policy_digest": self.policy_digest,
            "features": {k: self.features[k] for k in FEATURE_NAMES},
            "contributions": {k: self.contributions[k] for k in FEATURE_NAMES},
            "total_score": self.total_score,
        }

    def digest(self) -> str:
        return content_digest("capacity_score_breakdown", self.schema_version, self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "ScoreBreakdown":
        if not isinstance(data, Mapping):
            raise PolicyError("score breakdown must be a mapping")
        known = {"schema_version", "policy_id", "policy_digest", "features", "contributions", "total_score"}
        unknown = set(data) - known
        if unknown:
            raise PolicyError(f"unknown score breakdown field(s): {sorted(unknown)}")
        for req in ("policy_id", "policy_digest", "features", "contributions", "total_score"):
            if req not in data:
                raise PolicyError(f"score breakdown requires '{req}'")
        return cls(
            features=dict(data["features"]),
            contributions=dict(data["contributions"]),
            total_score=data["total_score"],
            policy_id=data["policy_id"],
            policy_digest=data["policy_digest"],
            schema_version=data.get("schema_version", SCORE_BREAKDOWN_SCHEMA_VERSION),
        )


__all__ = [
    "RECOMMENDATION_POLICY_SCHEMA_VERSION",
    "SCORE_BREAKDOWN_SCHEMA_VERSION",
    "FEATURE_NAMES",
    "PolicyError",
    "RecommendationPolicy",
    "ScoreBreakdown",
]
