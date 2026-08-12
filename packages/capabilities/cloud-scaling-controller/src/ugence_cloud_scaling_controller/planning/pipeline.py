"""The deterministic Phase-3 recommendation pipeline (shadow / advisory entry point).

``recommend_capacity_action`` is the single controlled service path that turns a Phase-2
forecast plus supplied dependency, cost, and constraint evidence into either a
:class:`~.recommendation.CapacityActionRecommendation` or a typed
:class:`~.recommendation.RecommendationAbstention`. It is:

  * deterministic and clock-free — ``recommendation_time`` is injected explicitly;
  * fail-closed — every insufficient/contradictory-evidence branch is a TYPED abstention,
    never a fabricated plan and never a generic exception;
  * bounded — a small, explicit candidate set (always incl. NO_CHANGE) is generated;
  * hard-before-soft — hard operating constraints filter candidates BEFORE any scoring;
  * shadow-only — it recommends; it never executes, authorizes, or verifies an effect.

Pipeline order (matches the Phase-3 contract):
  1. validate + scope-bind forecast / state / topology / cost / constraints / policy;
  2. reject future information and expired inputs;
  3. generate a bounded candidate set including NO_CHANGE;
  4. evaluate dependency impact via the supplied topology;
  5. apply hard constraints (feasibility) BEFORE scoring;
  6. estimate cost only from supplied cost evidence;
  7. score feasible candidates under the explicit policy;
  8. compare the selected candidate against NO_CHANGE (emergent via hold-bias + penalties);
  9. return a selected recommendation, ranked alternatives, typed rejections — or abstain;
 10. the returned record carries deterministic, revalidatable evidence for the whole decision.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import List, Optional, Union

from ..canonical.state import CanonicalCapacityState
from ..forecasting.evidence import CapacityForecastEvidence
from ..forecasting.series import _as_utc
from .abstention import RecommendationAbstentionReason as R
from .candidates import ActionKind, CandidateActionPlan, generate_candidates
from .constraints import OperatingConstraints
from .cost import CostBasis, CostBook
from .policy import RecommendationPolicy
from .recommendation import (
    CapacityActionRecommendation,
    EvaluatedCandidate,
    RecommendationAbstention,
)
from .scoring import (
    PLANNING_TARGET,
    ScoringError,
    build_context,
    evaluate_feasibility,
    plan_cost_delta_minor,
    primary_capacity_dependency,
    score_candidate,
    select_best,
    _forecast_confidence,
)
from .topology import DependencyKind, DependencyTopology

RecommendationOutcome = Union[CapacityActionRecommendation, RecommendationAbstention]

_TOL = 1e-6


class PipelineError(ValueError):
    """Raised on a programming/type misuse of the pipeline (NOT an evidence abstention)."""


def _abstain(subject, reason, *, recommendation_time, detail="", **digests) -> RecommendationAbstention:
    return RecommendationAbstention(
        subject=subject,
        reason=reason,
        recommendation_time=recommendation_time,
        detail=detail,
        forecast_evidence_digest=digests.get("forecast_evidence_digest"),
        canonical_state_digest=digests.get("canonical_state_digest"),
        topology_digest=digests.get("topology_digest"),
        cost_evidence_digest=digests.get("cost_evidence_digest"),
        constraint_digest=digests.get("constraint_digest"),
        policy_digest=digests.get("policy_digest"),
    )


def recommend_capacity_action(
    forecast_evidence: Optional[CapacityForecastEvidence],
    current_state: Optional[CanonicalCapacityState],
    cost_book: Optional[CostBook],
    constraints: Optional[OperatingConstraints],
    policy: Optional[RecommendationPolicy] = None,
    *,
    recommendation_time: datetime,
    validity_seconds: float,
    topology: Optional[DependencyTopology] = None,
    require_topology: bool = False,
    max_topology_age_seconds: Optional[float] = None,
    recommendation_id: Optional[str] = None,
    diagnostic_annotation: str = "",
) -> RecommendationOutcome:
    """Produce a capacity-action recommendation or a typed abstention (shadow / advisory)."""
    if not isinstance(recommendation_time, datetime):
        raise PipelineError("recommendation_time must be a datetime")
    policy = policy or RecommendationPolicy()
    if not isinstance(policy, RecommendationPolicy):
        raise PipelineError("policy must be a RecommendationPolicy")
    rec_t = _as_utc(recommendation_time)

    # --- canonical state -----------------------------------------------------------
    if current_state is None:
        # Bind the abstention to the forecast subject when available; otherwise this is a
        # programming misuse (no subject to bind at all).
        if isinstance(forecast_evidence, CapacityForecastEvidence):
            return _abstain(forecast_evidence.forecast.subject, R.MISSING_CANONICAL_STATE,
                            recommendation_time=recommendation_time,
                            detail="no current canonical state supplied",
                            forecast_evidence_digest=forecast_evidence.digest())
        raise PipelineError("current_state or forecast_evidence is required to bind a subject")
    if not isinstance(current_state, CanonicalCapacityState):
        raise PipelineError("current_state must be a CanonicalCapacityState")
    subject = current_state.subject
    state_digest = current_state.digest()

    def ab(reason, detail=""):
        return _abstain(subject, reason, recommendation_time=recommendation_time, detail=detail,
                        canonical_state_digest=state_digest)

    if _as_utc(current_state.observed_at) > rec_t:
        return ab(R.FUTURE_DATA_LEAKAGE, "current_state.observed_at is after recommendation_time")

    # --- forecast ------------------------------------------------------------------
    if forecast_evidence is None:
        return ab(R.MISSING_FORECAST, "no forecast evidence supplied")
    if not isinstance(forecast_evidence, CapacityForecastEvidence):
        raise PipelineError("forecast_evidence must be a CapacityForecastEvidence")
    fc = forecast_evidence.forecast
    fe_digest = forecast_evidence.digest()

    def abf(reason, detail=""):
        return _abstain(subject, reason, recommendation_time=recommendation_time, detail=detail,
                        canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest)

    if fc.subject != subject:
        return abf(R.SUBJECT_SCOPE_MISMATCH, "forecast subject != current_state subject")
    if fc.is_abstained:
        return abf(R.FORECAST_ABSTAINED, "forecast is a typed abstention")
    if fc.target is not PLANNING_TARGET:
        return abf(R.UNSUPPORTED_FORECAST_TARGET, f"target {fc.target.value} is not RUNNING_REPLICAS")
    if fc.point_estimate is None or not math.isfinite(float(fc.point_estimate)):
        return abf(R.NON_FINITE_INPUT, "forecast point estimate is missing or non-finite")

    cutoff = _as_utc(fc.forecast_cutoff)
    forecast_for = _as_utc(fc.forecast_for)
    if cutoff > rec_t:
        return abf(R.FUTURE_DATA_LEAKAGE, "forecast cutoff is after recommendation_time")
    if forecast_for <= rec_t:
        return abf(R.EXPIRED_FORECAST, "forecast horizon already elapsed at recommendation_time")

    # --- current capacity ----------------------------------------------------------
    if current_state.capacity is None or current_state.capacity.running_replicas is None:
        return abf(R.MISSING_CURRENT_CAPACITY, "current_state lacks capacity.running_replicas")

    # --- constraints ---------------------------------------------------------------
    if constraints is None:
        return abf(R.MISSING_CONSTRAINTS, "no operating constraints supplied")
    if not isinstance(constraints, OperatingConstraints):
        raise PipelineError("constraints must be an OperatingConstraints")
    con_digest = constraints.digest()

    def abc(reason, detail=""):
        return _abstain(subject, reason, recommendation_time=recommendation_time, detail=detail,
                        canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest,
                        constraint_digest=con_digest, policy_digest=policy.digest())

    # Expired forecast per the operator-set validity window.
    if constraints.forecast_validity_seconds is not None:
        age = (rec_t - cutoff).total_seconds()
        if age > constraints.forecast_validity_seconds:
            return abc(R.EXPIRED_FORECAST, "forecast age exceeds forecast_validity_seconds")

    # Recommendation validity window must lie within the forecast horizon.
    if isinstance(validity_seconds, bool) or not isinstance(validity_seconds, (int, float)) \
            or not math.isfinite(validity_seconds) or validity_seconds <= 0:
        raise PipelineError("validity_seconds must be a finite number > 0")
    if rec_t.timestamp() + float(validity_seconds) > forecast_for.timestamp() + _TOL:
        return abc(R.CONTRADICTORY_EVIDENCE, "recommendation validity window exceeds forecast horizon")

    # Forecast confidence gate (explicit policy threshold).
    if _forecast_confidence(fc) < policy.min_forecast_confidence - _TOL:
        return abc(R.INSUFFICIENT_FORECAST_CONFIDENCE, "forecast confidence below policy threshold")

    # Quota vs min conflict already blocked at OperatingConstraints construction; re-affirm.
    if constraints.regional_quota is not None and constraints.regional_quota < constraints.min_capacity:
        return abc(R.QUOTA_CONFLICT, "regional_quota is below min_capacity")

    # --- cost evidence -------------------------------------------------------------
    if cost_book is None:
        return abc(R.MISSING_COST_EVIDENCE, "no cost book supplied")
    if not isinstance(cost_book, CostBook):
        raise PipelineError("cost_book must be a CostBook")
    if cost_book.subject != subject:
        return abf(R.SUBJECT_SCOPE_MISMATCH, "cost_book subject != recommendation subject")
    cost_digest = cost_book.digest()

    def abcost(reason, detail=""):
        return _abstain(subject, reason, recommendation_time=recommendation_time, detail=detail,
                        canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest,
                        constraint_digest=con_digest, cost_evidence_digest=cost_digest,
                        policy_digest=policy.digest())

    primary_cost = cost_book.for_subject(subject)
    if primary_cost is None:
        return abcost(R.MISSING_COST_EVIDENCE, "no cost evidence for the primary subject")
    if primary_cost.basis is not CostBasis.PER_REPLICA_HOUR:
        return abcost(R.INCOMPATIBLE_COST_EVIDENCE, "primary cost basis is not per_replica_hour")
    currencies = {e.currency for e in cost_book.entries}
    if len(currencies) > 1:
        return abcost(R.CURRENCY_MISMATCH, f"multiple currencies in cost book: {sorted(currencies)}")
    for entry in cost_book.entries:
        if not entry.is_effective_at(recommendation_time):
            return abcost(R.STALE_COST_EVIDENCE, "cost evidence is not effective at recommendation_time")

    # --- topology / dependency evidence --------------------------------------------
    topo_digest = None
    if topology is None:
        if require_topology:
            return abcost(R.MISSING_TOPOLOGY, "topology required but none supplied")
    else:
        if not isinstance(topology, DependencyTopology):
            raise PipelineError("topology must be a DependencyTopology or None")
        if topology.subject != subject:
            return abf(R.SUBJECT_SCOPE_MISMATCH, "topology subject != recommendation subject")
        topo_digest = topology.digest()
        if _as_utc(topology.as_of) > rec_t:
            return _abstain(subject, R.FUTURE_DATA_LEAKAGE, recommendation_time=recommendation_time,
                            detail="topology as_of is after recommendation_time",
                            canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest,
                            topology_digest=topo_digest, constraint_digest=con_digest,
                            cost_evidence_digest=cost_digest, policy_digest=policy.digest())
        if max_topology_age_seconds is not None:
            if (rec_t - _as_utc(topology.as_of)).total_seconds() > max_topology_age_seconds:
                return _abstain(subject, R.STALE_TOPOLOGY, recommendation_time=recommendation_time,
                                detail="topology older than max_topology_age_seconds",
                                canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest,
                                topology_digest=topo_digest, constraint_digest=con_digest,
                                cost_evidence_digest=cost_digest, policy_digest=policy.digest())
        if topology.has_cycle():
            return _abstain(subject, R.DEPENDENCY_CYCLE, recommendation_time=recommendation_time,
                            detail="dependency topology contains a cycle",
                            canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest,
                            topology_digest=topo_digest, constraint_digest=con_digest,
                            cost_evidence_digest=cost_digest, policy_digest=policy.digest())
        # Every capacity-coupling dependency of the primary must carry capacity evidence.
        for edge in topology.capacity_dependencies_of(subject):
            if not edge.has_capacity_evidence:
                return _abstain(subject, R.MISSING_DEPENDENCY_CAPACITY,
                                recommendation_time=recommendation_time,
                                detail="capacity-bound dependency lacks capacity evidence",
                                canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest,
                                topology_digest=topo_digest, constraint_digest=con_digest,
                                cost_evidence_digest=cost_digest, policy_digest=policy.digest())

    # --- build deterministic context ------------------------------------------------
    try:
        ctx = build_context(forecast_evidence, current_state, topology, cost_book, constraints,
                            recommendation_time=recommendation_time)
    except ScoringError as exc:
        return abcost(R.CONTRADICTORY_EVIDENCE, f"inconsistent evidence: {exc}")

    # A dependency change needs its own cost evidence too (coordinated plans price it).
    if ctx.dependency_subject is not None and cost_book.for_subject(ctx.dependency_subject) is None:
        return abcost(R.MISSING_COST_EVIDENCE, "no cost evidence for the coordinated dependency")

    # --- bounded candidate generation ----------------------------------------------
    plans = generate_candidates(
        subject, ctx.current_capacity, ctx.required_capacity,
        allowed_step=constraints.allowed_step,
        min_capacity=constraints.min_capacity,
        max_capacity=constraints.effective_ceiling(),
        dependency=ctx.dependency_subject,
        dependency_current=ctx.dependency_current,
        dependency_required=ctx.dependency_required,
    )

    # --- evaluate: hard constraints BEFORE scoring ---------------------------------
    evaluated: List[EvaluatedCandidate] = []
    for plan in plans:
        violations = evaluate_feasibility(plan, ctx)
        cost_delta = plan_cost_delta_minor(plan, ctx)
        if violations:
            evaluated.append(EvaluatedCandidate(
                plan=plan, feasible=False,
                violations=tuple(v.value for v in violations),
                cost_delta_minor=cost_delta, score_breakdown=None))
        else:
            sb = score_candidate(plan, ctx, policy)
            evaluated.append(EvaluatedCandidate(
                plan=plan, feasible=True, violations=(),
                cost_delta_minor=cost_delta, score_breakdown=sb))

    feasible = [ec for ec in evaluated if ec.feasible]
    if not feasible:
        return abcost(R.NO_FEASIBLE_ACTION, "no candidate satisfies the hard constraints")

    # --- selection: coverage-first, then policy score, with typed ambiguity --------
    triples = [(ec.plan.plan_id, ec.score_breakdown.features["coverage"], ec.total_score)
               for ec in feasible]
    selected_id, ambiguous = select_best(triples, policy)
    if ambiguous:
        return _abstain(subject, R.AMBIGUOUS_BEST_PLAN, recommendation_time=recommendation_time,
                        detail="feasible candidates tie within policy tie_epsilon in the best tier",
                        canonical_state_digest=state_digest, forecast_evidence_digest=fe_digest,
                        topology_digest=topo_digest, constraint_digest=con_digest,
                        cost_evidence_digest=cost_digest, policy_digest=policy.digest())
    selected = next(ec for ec in feasible if ec.plan.plan_id == selected_id)

    reason_codes, dep_explanation = _explain(selected.plan, ctx, evaluated)

    rid = recommendation_id or f"rec-{fe_digest[7:19]}-{selected.plan.plan_id}"
    return CapacityActionRecommendation(
        recommendation_id=rid,
        forecast_evidence=forecast_evidence,
        current_state=current_state,
        cost_book=cost_book,
        constraints=constraints,
        policy=policy,
        evaluated_candidates=tuple(evaluated),
        selected_plan_id=selected.plan.plan_id,
        recommendation_time=recommendation_time,
        validity_seconds=float(validity_seconds),
        topology=topology,
        reason_codes=reason_codes,
        dependency_explanation=dep_explanation,
        diagnostic_annotation=diagnostic_annotation,
    )


def _explain(plan, ctx, evaluated):
    """Deterministic reason codes + a dependency-impact explanation for the selected plan."""
    codes: List[str] = []
    if plan.action_kind is ActionKind.NO_CHANGE:
        codes.append("hold_preferred")
        if ctx.current_capacity >= ctx.required_capacity:
            codes.append("current_capacity_covers_forecast")
    else:
        codes.append(f"{plan.action_kind.value}_selected")
        if plan.primary_change.proposed_capacity >= ctx.required_capacity:
            codes.append("forecast_coverage_met")
        else:
            codes.append("forecast_coverage_partial")
    # Dependency explanation.
    if ctx.dependency_subject is None:
        codes.append("no_capacity_dependency_considered")
        dep = "No capacity-bound dependency was supplied; the recommendation concerns the primary resource only."
    else:
        moved = False
        removed = False
        if plan.primary_change.delta > 0 and ctx.dependency_required > ctx.dependency_current:
            raises_dep = any(c.subject == ctx.dependency_subject
                             and c.proposed_capacity >= ctx.dependency_required
                             for c in plan.dependency_changes)
            if raises_dep:
                removed = True
                codes.append("bottleneck_removed_by_coordination")
            else:
                moved = True
                codes.append("bottleneck_transferred_to_dependency")
        dep = (
            f"Considered downstream dependency '{ctx.dependency_subject.workload_id}' "
            f"(current {ctx.dependency_current}, required ~{ctx.dependency_required}). "
            + ("The coordinated plan raises the dependency, so the bottleneck is removed. "
               if removed else
               "This plan does not raise the dependency, so the bottleneck may transfer to it. "
               if moved else
               "The dependency already has sufficient capacity or the primary is not scaled up. ")
            + "Structural dependency evidence does not prove runtime causality; residual "
              "uncertainty remains."
        )
    return tuple(codes), dep


__all__ = [
    "RecommendationOutcome",
    "PipelineError",
    "recommend_capacity_action",
]
