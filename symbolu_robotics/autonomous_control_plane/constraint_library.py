"""Deterministic hard-constraint library (Phase 1).

Concrete ``HardConstraintEvaluator``-style constraints for ONLY the data the
three production BCVF call sites actually provide. Physical constraints for which
no call-site data exists (collision-margin-in-metres, stopping distance, actuator
limits, stability) are deliberately NOT implemented here — see
``ACP_HARD_CONSTRAINTS.md`` for the availability matrix. Nothing is fabricated.

Threshold provenance is recorded per constraint: ``PROD`` = taken from existing
production code; ``POLICY`` = a frozen ACP policy threshold justified from
semantics (frozen in ``ACP_PHASE1_PREREGISTRATION.md``).

Missing-data policy: if a constraint applies to a candidate but its required
feature is absent, the constraint emits a HARD **failing** result with reason
``MISSING_<feature>`` (fail closed). It never silently passes.

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .constraints import ConstraintKind, ConstraintResult
from .envelopes import ActionType, CanonicalActionCandidate

_COMPARE: dict = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def _feature(candidate: CanonicalActionCandidate, key: str) -> Optional[float]:
    raw = candidate.metadata.get(key)
    if raw is None:
        return None
    return float(raw)


@dataclass(frozen=True)
class ThresholdConstraint:
    """A HARD threshold on one numeric candidate feature (from metadata)."""
    constraint_id: str
    feature_key: str
    comparator: str            # one of _COMPARE
    bound: float
    reason_code: str
    provenance: str            # "PROD" | "POLICY"
    applies_to: Optional[Callable[[CanonicalActionCandidate], bool]] = None

    def evaluate(self, candidate: CanonicalActionCandidate,
                 world_version: str) -> Optional[ConstraintResult]:
        if self.applies_to is not None and not self.applies_to(candidate):
            return None  # not applicable to this candidate
        value = _feature(candidate, self.feature_key)
        if value is None:
            # required data missing -> fail closed
            return ConstraintResult(
                constraint_id=self.constraint_id, kind=ConstraintKind.HARD,
                passed=False, observed_value=0.0, required_bound=self.bound,
                comparator=self.comparator,
                reason_code=f"MISSING_{self.feature_key}",
                evidence_ref=world_version)
        passed = bool(_COMPARE[self.comparator](value, self.bound))
        return ConstraintResult(
            constraint_id=self.constraint_id, kind=ConstraintKind.HARD,
            passed=passed, observed_value=value, required_bound=self.bound,
            comparator=self.comparator, reason_code=self.reason_code,
            evidence_ref=world_version)


@dataclass(frozen=True)
class SafeFallbackConstraint:
    """STOP/HOLD-type actions are inherently admissible (cannot collide).

    Justified from semantics: an emergency stop / hold reduces kinetic risk and
    is the safe posture. This lets a call site always retain a safe fallback
    rather than spuriously returning REQUEST_MORE_OBSERVATION when only a stop
    is available.
    """
    constraint_id: str = "SAFE_FALLBACK"

    def evaluate(self, candidate: CanonicalActionCandidate,
                 world_version: str) -> Optional[ConstraintResult]:
        is_fallback = (candidate.action_type in (ActionType.STOP, ActionType.HOLD)
                       or candidate.metadata.get("safe_fallback") == "true")
        if not is_fallback:
            return None
        return ConstraintResult(
            constraint_id=self.constraint_id, kind=ConstraintKind.HARD,
            passed=True, observed_value=1.0, required_bound=1.0,
            comparator="==", reason_code="SAFE_FALLBACK",
            evidence_ref=world_version)


def evaluate_constraint_set(candidate: CanonicalActionCandidate,
                            constraints: List,
                            world_version: str) -> Tuple[ConstraintResult, ...]:
    """Evaluate every applicable constraint; skip non-applicable ones."""
    out = []
    for c in constraints:
        r = c.evaluate(candidate, world_version)
        if r is not None:
            out.append(r)
    return tuple(out)


# ---- Per-call-site frozen constraint sets --------------------------------
# Thresholds are frozen in ACP_PHASE1_PREREGISTRATION.md.

def _is_move(c: CanonicalActionCandidate) -> bool:
    return c.action_type is ActionType.MOVE


def deliberative_constraints() -> List:
    """Available: obstacle clearance (MOVE) + safe fallback (WAIT/STOP).

    UNAVAILABLE at this call site (NOT implemented): stopping distance, actuator
    limits, stability, trajectory validity — no candidate/world data provides
    them.
    """
    return [
        SafeFallbackConstraint(),
        ThresholdConstraint(
            constraint_id="OBSTACLE_CLEARANCE", feature_key="min_obstacle_distance_m",
            comparator=">=", bound=0.5, reason_code="OBSTACLE_CLEARANCE",
            provenance="PROD",  # deliberative._compute_forward_score uses 0.5
            applies_to=_is_move),
    ]


def conflict_constraints() -> List:
    """Available: per-candidate safety_score floor + feasibility floor + safe
    fallback (MUTUAL_STOP). UNAVAILABLE: physical collision margin (metres),
    stopping, actuator — strategy scores are abstract."""
    return [
        SafeFallbackConstraint(),
        ThresholdConstraint(
            constraint_id="SAFETY_SCORE_FLOOR", feature_key="safety_score",
            comparator=">=", bound=0.5, reason_code="SAFETY_SCORE_BELOW_FLOOR",
            provenance="POLICY"),
        ThresholdConstraint(
            constraint_id="FEASIBILITY_FLOOR", feature_key="feasibility",
            comparator=">=", bound=0.3, reason_code="FEASIBILITY_BELOW_FLOOR",
            provenance="POLICY"),
    ]


def task_allocation_constraints() -> List:
    """Available: capability / load / coherence (all mirror existing PROD
    pre-filters). UNAVAILABLE: collision, stopping, actuator, stability."""
    return [
        ThresholdConstraint(
            constraint_id="CAPABILITY_MATCH", feature_key="capability_match",
            comparator=">=", bound=0.5, reason_code="CAPABILITY_BELOW_FLOOR",
            provenance="PROD"),   # submit_bid: capability_match < 0.5 -> reject
        ThresholdConstraint(
            constraint_id="LOAD_LIMIT", feature_key="current_load",
            comparator="<=", bound=0.9, reason_code="OVERLOADED",
            provenance="PROD"),   # submit_bid: current_load > 0.9 -> reject
        ThresholdConstraint(
            constraint_id="COHERENCE_FLOOR", feature_key="coherence",
            comparator=">=", bound=0.4, reason_code="COHERENCE_BELOW_FLOOR",
            provenance="PROD"),   # receive_bid: coherence_threshold = 0.4
    ]
