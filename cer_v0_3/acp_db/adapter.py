"""Database ACP shadow adapter (V0.3 §7).

Composes the deterministic database operational-safety recommendation with an
externally-supplied ActionGate verdict using the FROZEN ACP ``compose()`` — the
same composition, invariants, and outcome set as the Kubernetes adapter. Reuses
``compose``, ``AuthorizationVerdict``, ``CombinedOutcome``, ``CloudRecommendation``
verbatim; adds no decision state and modifies no ACP-core file.

Shadow-only: never actuates, never mints an execution token, contained errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from . import safety
from .envelopes import DbActionCandidate, DbOperationalEvidence, DbWorldState

# FROZEN ACP composition core — reused unchanged.
from symbolu_robotics.autonomous_control_plane.cloud.composition import (
    AuthorizationVerdict, CombinedOutcome, CompositionResult, compose,
)
from symbolu_robotics.autonomous_control_plane.cloud.outcomes import CloudRecommendation


@dataclass(frozen=True)
class DbShadowResult:
    decision_id: str
    acp_recommendation: CloudRecommendation
    composition: Optional[CompositionResult]
    evidence: DbOperationalEvidence
    shadow_only: bool = True

    @property
    def acp_decision(self) -> str:
        return self.acp_recommendation.value

    @property
    def cloud_recommendation(self) -> str:
        return self.acp_recommendation.value

    @property
    def combined_outcome(self) -> Optional[str]:
        return self.composition.combined.value if self.composition else None

    @property
    def reason_codes(self) -> Tuple[str, ...]:
        return self.evidence.reason_codes


class DbShadowAdapter:
    """OFF-capable, shadow-only database operational-safety adapter."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def observe(self, *, decision_id: str, world: Optional[DbWorldState],
                candidate: DbActionCandidate, now_s: float, freshness_s: float,
                authorization: AuthorizationVerdict) -> Optional[DbShadowResult]:
        if not self.enabled:
            return None
        try:
            evidence, rec = safety.evaluate(candidate, world, now_s=now_s,
                                            freshness_s=freshness_s)
        except Exception:  # pragma: no cover - contained, fail closed
            evidence = DbOperationalEvidence(False, False, False, False, False, False,
                                             False, False, reason_codes=("EVALUATOR_FAILED",),
                                             validity="EVALUATOR_FAILED")
            rec = CloudRecommendation.HOLD
        composition = compose(authorization, rec)
        return DbShadowResult(decision_id=decision_id, acp_recommendation=rec,
                              composition=composition, evidence=evidence)
