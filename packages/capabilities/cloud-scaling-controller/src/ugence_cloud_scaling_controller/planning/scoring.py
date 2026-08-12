"""Deterministic candidate evaluation — hard-constraint filtering + policy scoring.

This module is the single, pure, deterministic evaluation core shared by the recommendation
pipeline (:mod:`.pipeline`) AND the recommendation record's construction-time re-validation
(:mod:`.recommendation`). Because both callers evaluate through the SAME functions over the
SAME derived :class:`EvaluationContext`, a stored score/feasibility/cost figure can be
recomputed exactly, and a forged one is rejected at construction.

Two stages, in order (hard filtering ALWAYS before scoring):

  1. :func:`evaluate_feasibility` — apply hard operating constraints; a candidate that
     violates any of them is infeasible and is NEVER scored (non-compensatory).
  2. :func:`score_candidate` — for a feasible candidate, compute the explicit, policy-weighted
     :class:`~.policy.ScoreBreakdown` from deterministic, derived features.

Nothing here fetches a price, reads a clock, or calls a provider. Every input is a canonical
object; ``recommendation_time`` is an explicit caller-supplied timestamp.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..canonical.identity import CapacitySubject
from ..canonical.state import CanonicalCapacityState
from ..forecasting.evidence import CapacityForecastEvidence
from ..forecasting.series import _as_utc
from ..forecasting.targets import ForecastTarget
from .candidates import ActionKind, CandidateActionPlan, ResourceChange
from .constraints import ConstraintViolationKind, OperatingConstraints
from .cost import CostBasis, CostBook
from .policy import FEATURE_NAMES, RecommendationPolicy, ScoreBreakdown
from .topology import DependencyEdge, DependencyTopology


class ScoringError(ValueError):
    """Raised when scoring inputs are inconsistent (fail closed)."""


@dataclass(frozen=True)
class EvaluationContext:
    """Derived, deterministic scalars needed to evaluate candidates.

    Every field is DERIVED from the embedded authoritative inputs by :func:`build_context`,
    so the recommendation record can reconstruct an identical context and recompute the same
    feasibility/score — closing the integrity gap between stored and derived claims.
    """

    primary_subject: CapacitySubject
    current_capacity: int
    required_capacity: int
    forecast_confidence: float
    forecast_uncertainty: float
    reliability_stressed: bool
    baseline_cost_minor: int
    currency: str
    unit_price_minor: Mapping[str, int]     # workload_id -> per-unit price (minor units)
    dependency_subject: Optional[CapacitySubject]
    dependency_current: Optional[int]
    dependency_required: Optional[int]
    dependency_ceiling: Mapping[str, int]
    constraints: OperatingConstraints
    recommendation_time: datetime

    def price_for(self, subject: CapacitySubject) -> Optional[int]:
        return self.unit_price_minor.get(subject.workload_id)


# Phase 3 plans capacity in replica units; the forecast target that directly predicts the
# primary's required replica count is RUNNING_REPLICAS. Other targets (utilization, latency)
# would require a separately-governed capacity model to convert into replicas and are out of
# scope for this baseline (the pipeline abstains UNSUPPORTED_FORECAST_TARGET for them).
PLANNING_TARGET = ForecastTarget.RUNNING_REPLICAS


def _forecast_confidence(fc) -> float:
    unc = fc.uncertainty
    return float(unc.requested_coverage) if unc.available else 0.0


def _forecast_uncertainty(fc) -> float:
    unc = fc.uncertainty
    point = float(fc.point_estimate) if fc.point_estimate is not None else 0.0
    if unc.available and unc.lower is not None and unc.upper is not None:
        width = float(unc.upper) - float(unc.lower)
        return max(0.0, min(1.0, width / max(2.0 * abs(point), 1.0)))
    # Point-only forecast: treat as moderately uncertain (conservative, disclosed).
    return 0.5


def _reliability_stressed(state: CanonicalCapacityState) -> bool:
    """Heuristic, disclosed: a strictly positive observed error rate marks reliability stress
    for the SOFT reliability-risk feature (hard SLO/error-budget protection is a separate,
    operator-set constraint). No hidden threshold beyond ``error_rate > 0``."""
    r = state.reliability
    if r is not None and r.error_rate is not None and r.error_rate.value > 0.0:
        return True
    return False


def primary_capacity_dependency(
    topology: Optional[DependencyTopology], primary: CapacitySubject
) -> Optional[DependencyEdge]:
    """Deterministically select the single primary capacity-bound dependency edge, if any.

    When several capacity-coupling edges leave the primary, the one with the lexicographically
    smallest downstream ``workload_id`` is chosen (order-independent). Coordinated planning in
    this baseline addresses one downstream dependency at a time (bounded)."""
    if topology is None:
        return None
    deps = topology.capacity_dependencies_of(primary)
    if not deps:
        return None
    return sorted(deps, key=lambda e: e.downstream.workload_id)[0]


def build_context(
    forecast_evidence: CapacityForecastEvidence,
    current_state: CanonicalCapacityState,
    topology: Optional[DependencyTopology],
    cost_book: CostBook,
    constraints: OperatingConstraints,
    *,
    recommendation_time: datetime,
) -> EvaluationContext:
    """Derive the deterministic :class:`EvaluationContext` from authoritative inputs.

    Shared by the pipeline and by the recommendation record's construction-time
    re-validation, so both evaluate candidates identically. Raises :class:`ScoringError`
    on any inconsistency the pipeline is expected to have already gated (a validly
    constructed record never triggers these)."""
    fc = forecast_evidence.forecast
    if not fc.is_forecast or fc.point_estimate is None:
        raise ScoringError("planning requires a point forecast")
    if fc.target is not PLANNING_TARGET:
        raise ScoringError("planning requires the RUNNING_REPLICAS forecast target")
    primary = current_state.subject
    if current_state.capacity is None or current_state.capacity.running_replicas is None:
        raise ScoringError("current_state must carry capacity.running_replicas")
    current_capacity = int(current_state.capacity.running_replicas)

    margin = 1.0 + constraints.safety_margin_fraction
    required_capacity = int(math.ceil(float(fc.point_estimate) * margin - 1e-9))
    required_capacity = max(required_capacity, 0)

    dep_edge = primary_capacity_dependency(topology, primary)
    dep_subject = dep_current = dep_required = None
    if dep_edge is not None:
        if not dep_edge.has_capacity_evidence:
            raise ScoringError("capacity-bound dependency edge lacks capacity evidence")
        dep_subject = dep_edge.downstream
        dep_current = int(dep_edge.downstream_current_capacity)
        dep_required = int(math.ceil(required_capacity * float(dep_edge.required_per_upstream_unit) - 1e-9))

    # Prices (exact integer minor units) keyed by workload_id; single shared currency.
    prices: Dict[str, int] = {}
    currency = ""
    for entry in cost_book.entries:
        prices[entry.subject.workload_id] = entry.unit_price.amount_minor
        currency = entry.currency
    primary_price = prices.get(primary.workload_id)
    if primary_price is None:
        raise ScoringError("cost book lacks the primary subject's unit price")
    baseline_cost_minor = current_capacity * primary_price

    return EvaluationContext(
        primary_subject=primary,
        current_capacity=current_capacity,
        required_capacity=required_capacity,
        forecast_confidence=_forecast_confidence(fc),
        forecast_uncertainty=_forecast_uncertainty(fc),
        reliability_stressed=_reliability_stressed(current_state),
        baseline_cost_minor=baseline_cost_minor,
        currency=currency,
        unit_price_minor=prices,
        dependency_subject=dep_subject,
        dependency_current=dep_current,
        dependency_required=dep_required,
        dependency_ceiling=dict(constraints.dependency_capacity_ceiling),
        constraints=constraints,
        recommendation_time=recommendation_time,
    )


def _capacity_cost_minor(change_current: int, change_proposed: int, price_minor: int) -> int:
    """Exact integer cost delta for one resource change (minor units)."""
    return (change_proposed - change_current) * price_minor


def plan_cost_delta_minor(plan: CandidateActionPlan, ctx: EvaluationContext) -> int:
    """Deterministic, exact cost delta (minor units) for ``plan`` vs current capacity."""
    total = 0
    for change in plan.changes:
        price = ctx.price_for(change.subject)
        if price is None:
            raise ScoringError("missing unit price for a changed resource (pipeline must gate)")
        total += _capacity_cost_minor(change.current_capacity, change.proposed_capacity, price)
    return total


def evaluate_feasibility(
    plan: CandidateActionPlan, ctx: EvaluationContext
) -> Tuple[ConstraintViolationKind, ...]:
    """Apply hard constraints; return the tuple of violations (empty == feasible)."""
    c = ctx.constraints
    violations: List[ConstraintViolationKind] = []
    primary = plan.primary_change

    if primary.proposed_capacity < c.min_capacity:
        violations.append(ConstraintViolationKind.BELOW_MIN_CAPACITY)
    if primary.proposed_capacity > c.max_capacity:
        violations.append(ConstraintViolationKind.ABOVE_MAX_CAPACITY)
    ceiling = c.effective_ceiling()
    if primary.proposed_capacity > ceiling:
        violations.append(ConstraintViolationKind.QUOTA_EXCEEDED)

    # Step alignment: every non-zero change must be a multiple of allowed_step.
    for change in plan.changes:
        if change.delta != 0 and (abs(change.delta) % c.allowed_step != 0):
            violations.append(ConstraintViolationKind.INVALID_STEP)
            break

    # Cooldown / minimum change interval (a real change during cooldown is infeasible).
    if plan.action_kind is not ActionKind.NO_CHANGE and c.cooldown_seconds > 0 and c.last_change_at is not None:
        elapsed = (_as_utc(ctx.recommendation_time) - _as_utc(c.last_change_at)).total_seconds()
        if elapsed < c.cooldown_seconds:
            violations.append(ConstraintViolationKind.COOLDOWN_ACTIVE)

    # Reliability protections forbid a scale-DOWN of the primary resource.
    if primary.delta < 0:
        if c.protect_slo:
            violations.append(ConstraintViolationKind.SLO_PROTECTED)
        if c.protect_error_budget:
            violations.append(ConstraintViolationKind.ERROR_BUDGET_PROTECTED)

    # Dependency capacity ceiling on any changed resource (keyed by workload_id).
    for change in plan.changes:
        cap = c.dependency_capacity_ceiling.get(change.subject.workload_id)
        if cap is not None and change.proposed_capacity > cap:
            violations.append(ConstraintViolationKind.DEPENDENCY_CEILING_EXCEEDED)
            break

    # Prohibited / unavailable action kinds.
    if plan.action_kind.value in c.prohibited_actions:
        violations.append(ConstraintViolationKind.PROHIBITED_ACTION)

    # Maximum permitted cost increase.
    if c.max_cost_increase_minor is not None:
        if plan_cost_delta_minor(plan, ctx) > c.max_cost_increase_minor:
            violations.append(ConstraintViolationKind.MAX_COST_INCREASE_EXCEEDED)

    return tuple(violations)


def _coverage(plan: CandidateActionPlan, ctx: EvaluationContext) -> float:
    if ctx.required_capacity <= 0:
        return 1.0
    ratio = plan.primary_change.proposed_capacity / ctx.required_capacity
    return max(0.0, min(1.0, ratio))


def _bottleneck_risk(plan: CandidateActionPlan, ctx: EvaluationContext) -> float:
    """1.0 when scaling the primary merely transfers the bottleneck downstream; else 0.0.

    A downstream capacity-bound dependency needs ``dependency_required`` capacity to keep up
    with the scaled primary. If the plan raises the primary but does NOT raise the dependency
    to at least that level, the bottleneck is transferred (risk 1.0). A coordinated plan that
    raises the dependency removes it (0.0). No dependency pressure => 0.0."""
    if ctx.dependency_subject is None or ctx.dependency_required is None or ctx.dependency_current is None:
        return 0.0
    if plan.primary_change.delta <= 0:
        return 0.0  # not scaling up the primary => no new downstream pressure introduced
    if ctx.dependency_required <= ctx.dependency_current:
        return 0.0  # dependency already has the capacity
    # Does this plan raise the dependency to its required level?
    for change in plan.dependency_changes:
        if change.subject == ctx.dependency_subject and change.proposed_capacity >= ctx.dependency_required:
            return 0.0
    return 1.0


def _reliability_risk(plan: CandidateActionPlan, ctx: EvaluationContext) -> float:
    return 1.0 if (plan.primary_change.delta < 0 and ctx.reliability_stressed) else 0.0


def _cost_increase_ratio(plan: CandidateActionPlan, ctx: EvaluationContext) -> float:
    """Signed cost-delta ratio: (plan cost delta) / baseline; positive == more expensive."""
    base = max(ctx.baseline_cost_minor, 1)
    return plan_cost_delta_minor(plan, ctx) / base


def _change_magnitude(plan: CandidateActionPlan, ctx: EvaluationContext) -> float:
    return abs(plan.primary_change.delta) / max(ctx.current_capacity, 1)


def _uncertainty(plan: CandidateActionPlan, ctx: EvaluationContext) -> float:
    """Uncertainty penalizes larger changes: forecast uncertainty x normalized magnitude."""
    return ctx.forecast_uncertainty * min(1.0, _change_magnitude(plan, ctx))


def compute_features(plan: CandidateActionPlan, ctx: EvaluationContext) -> Dict[str, float]:
    return {
        "coverage": _coverage(plan, ctx),
        "bottleneck_risk": _bottleneck_risk(plan, ctx),
        "reliability_risk": _reliability_risk(plan, ctx),
        "cost_increase_ratio": _cost_increase_ratio(plan, ctx),
        "change_magnitude": _change_magnitude(plan, ctx),
        "uncertainty": _uncertainty(plan, ctx),
        "hold_bias": 1.0 if plan.action_kind is ActionKind.NO_CHANGE else 0.0,
    }


def select_best(evaluated_scores, policy: RecommendationPolicy):
    """Two-tier, lexicographic, deterministic selection over evaluated candidates.

    ``evaluated_scores`` is an iterable of ``(candidate_id, coverage, total_score)`` triples
    for FEASIBLE candidates only. Selection is coverage-first: candidates meeting
    ``policy.coverage_floor`` form the preferred tier; only if none do is the full feasible set
    used (best partial coverage). Within the active tier the highest ``total_score`` wins, with
    ``candidate_id`` as the deterministic final tiebreak for ordering. If two or more distinct
    candidates tie within ``policy.tie_epsilon`` at the top of the active tier, the selection is
    AMBIGUOUS (no authoritative tie-break) and the caller must abstain rather than pick by list
    or digest order.

    Returns ``(selected_id, is_ambiguous)`` — ``selected_id`` is ``None`` when there are no
    feasible candidates."""
    feasible = list(evaluated_scores)
    if not feasible:
        return None, False
    covering = [t for t in feasible if t[1] >= policy.coverage_floor - 1e-9]
    tier = covering if covering else feasible
    tier_sorted = sorted(tier, key=lambda t: (-t[2], t[0]))
    best_score = tier_sorted[0][2]
    top = [t for t in tier_sorted if (best_score - t[2]) <= policy.tie_epsilon]
    if len(top) > 1:
        return None, True
    return tier_sorted[0][0], False


def score_candidate(
    plan: CandidateActionPlan, ctx: EvaluationContext, policy: RecommendationPolicy
) -> ScoreBreakdown:
    """Deterministic policy score of a FEASIBLE candidate (pure fn of features + policy)."""
    features = compute_features(plan, ctx)
    contributions = {
        f: policy.sign_for(f) * policy.weight_for(f) * features[f] for f in FEATURE_NAMES
    }
    total = sum(contributions[f] for f in FEATURE_NAMES)
    return ScoreBreakdown(
        features=features,
        contributions=contributions,
        total_score=total,
        policy_id=policy.policy_id,
        policy_digest=policy.digest(),
    )


__all__ = [
    "ScoringError",
    "EvaluationContext",
    "PLANNING_TARGET",
    "build_context",
    "primary_capacity_dependency",
    "plan_cost_delta_minor",
    "evaluate_feasibility",
    "compute_features",
    "score_candidate",
    "select_best",
]
