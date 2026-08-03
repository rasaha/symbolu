"""Deterministic evidence-backed ranking of P1-eligible candidates.

Ranking operates **only** over candidates whose P1 `AgentEligibilityResult.state`
is `ELIGIBLE`. Hard constraints and ranking are strictly separate: a high score can
never compensate for failed P1 eligibility (P2-I2). Every eligible candidate appears
exactly once (P2-I3). Scores are integer basis points, exactly reconstructable from
their per-criterion contributions (P2-I5). Ordering is a deterministic total order
under a frozen tie-break sequence (P2-I6), independent of input ordering.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .agents import AgentProfile, AgentRegistrySnapshot
from .canonical import AwcModel
from .composition_contracts import SelectionState  # noqa: F401 (re-exported convenience)
from .contracts import EVIDENCE_PRECEDENCE, EligibilityState, EvidenceClass
from .eligibility import RoleEligibilityReport, evaluate_registry_for_role
from .fingerprint import stamp_fingerprint
from .scoring import (
    SCORE_PRECISION,
    SCORE_REPRESENTATION,
    SCORE_ROUNDING,
    normalize_higher_better,
    normalize_lower_better,
    weighted_contribution,
)
from .version import COMPOSITION_CONTRACT_VERSION
from .workflow import WorkflowRoleRequirement


class RankingCriterion(AwcModel):
    """One ranking criterion: how a profile metric maps to weighted basis points."""

    key: str
    metric: str                 # evidence_strength | evidence_freshness | quality |
                                # reliability | latency | cost | security | audit
    direction: str              # "higher_better" | "lower_better"
    lo: float
    hi: float
    weight_bp: int              # integer basis-point weight


class AgentRankingPolicy(AwcModel):
    """Immutable, versioned ranking policy-as-data (contract awc.composition.v1)."""

    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    policy_id: str
    policy_version: str
    criteria: Tuple[RankingCriterion, ...]
    missing_value_rule: str = "zero"          # a missing metric contributes 0 bp
    evidence_precedence: Tuple[str, ...] = ("OBSERVED", "MEASURED", "DECLARED")
    score_representation: str = SCORE_REPRESENTATION
    score_precision: str = SCORE_PRECISION
    score_rounding: str = SCORE_ROUNDING
    tie_break_sequence: Tuple[str, ...] = (
        "total_score", "evidence_strength", "evidence_freshness", "reliability",
        "cost", "latency", "provider_id", "agent_id", "agent_version",
    )
    policy_digest: str = ""


class RankingCriterionResult(AwcModel):
    criterion: str
    metric: str
    raw_value: str              # exact string form (never a lossy float in a digest)
    normalized_bp: int
    weight_bp: int
    weighted_contribution_bp: int
    evidence_refs: Tuple[str, ...] = ()
    explanation: str = ""


class AgentRankResult(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    role_id: str
    agent_id: str
    agent_version: str
    eligibility_result_fingerprint: str
    criterion_results: Tuple[RankingCriterionResult, ...]
    total_score: int            # basis points
    rank: int
    tie_group: int
    tie_break_values: Tuple[str, ...]
    evidence_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    snapshot_digest: str = ""
    ranking_policy_digest: str = ""
    result_fingerprint: str = ""

    def reconstruct_total(self) -> int:
        return sum(c.weighted_contribution_bp for c in self.criterion_results)


class RoleCandidateRanking(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    role_id: str
    ranked_candidates: Tuple[AgentRankResult, ...]
    eligible_candidate_count: int
    excluded_candidate_count: int
    ranking_policy_digest: str = ""
    snapshot_digest: str = ""
    role_fingerprint: str = ""
    ranking_fingerprint: str = ""


# --------------------------------------------------------------------------- #
# metric extraction (from P1 profile + evidence; never runtime state)
# --------------------------------------------------------------------------- #

def _role_evidence(role: WorkflowRoleRequirement, profile: AgentProfile,
                   snapshot: AgentRegistrySnapshot, now: float):
    """Return (min_precedence_rank, freshness_ratio, evidence_ref_ids) for the
    strongest non-expired evidence backing each required capability (weakest link)."""
    ev = snapshot.evidence_set()
    if not role.required_capabilities:
        return 0, 0.0, ()
    ranks: List[int] = []
    freshness: List[float] = []
    refs: List[str] = []
    for cap in role.required_capabilities:
        items = [e for e in ev.for_capability(profile.agent_id, profile.agent_version, cap)
                 if not e.is_expired(now)]
        if not items:
            return 0, 0.0, ()  # weakest link has no live evidence
        best = max(items, key=lambda e: EVIDENCE_PRECEDENCE[e.evidence_class])
        ranks.append(EVIDENCE_PRECEDENCE[best.evidence_class])
        refs.append(best.evidence_id)
        if best.valid_until is not None and best.valid_until > best.measured_at:
            ratio = (best.valid_until - now) / (best.valid_until - best.measured_at)
            freshness.append(max(0.0, min(1.0, ratio)))
        else:
            freshness.append(0.0)
    return min(ranks), (min(freshness) if freshness else 0.0), tuple(sorted(set(refs)))


def _metric_value(metric: str, role, profile, snapshot, now) -> Tuple[Optional[float], Tuple[str, ...]]:
    if metric == "evidence_strength":
        rank, _, refs = _role_evidence(role, profile, snapshot, now)
        return float(rank), refs
    if metric == "evidence_freshness":
        _, fresh, refs = _role_evidence(role, profile, snapshot, now)
        return fresh, refs
    if metric == "quality":
        return profile.quality_evidence, ()
    if metric == "reliability":
        return profile.reliability_evidence, ()
    if metric == "latency":
        return profile.latency_evidence, ()
    if metric == "cost":
        return profile.cost_evidence, ()
    if metric == "security":
        return float(profile.security_classification), ()
    if metric == "audit":
        return float(len(profile.audit_capabilities)), ()
    return None, ()


def _criterion_result(c: RankingCriterion, role, profile, snapshot, now) -> RankingCriterionResult:
    raw, refs = _metric_value(c.metric, role, profile, snapshot, now)
    if c.direction == "lower_better":
        norm = normalize_lower_better(raw, c.lo, c.hi)
    else:
        norm = normalize_higher_better(raw, c.lo, c.hi)
    contrib = weighted_contribution(norm, c.weight_bp)
    return RankingCriterionResult(
        criterion=c.key, metric=c.metric,
        raw_value=("none" if raw is None else str(raw)),
        normalized_bp=norm, weight_bp=c.weight_bp, weighted_contribution_bp=contrib,
        evidence_refs=refs,
        explanation=f"{c.metric}={raw} → {norm}bp × {c.weight_bp}bp = {contrib}bp")


def _tie_break_key(rr: AgentRankResult, by_metric: Dict[str, int]):
    """A total-order key: higher-is-better fields negated so ascending sort is correct."""
    return (
        -rr.total_score,
        -by_metric.get("evidence_strength", 0),
        -by_metric.get("evidence_freshness", 0),
        -by_metric.get("reliability", 0),
        -by_metric.get("cost", 0),      # cost normalized lower_better: higher bp = cheaper
        -by_metric.get("latency", 0),   # latency normalized lower_better: higher bp = faster
        rr.agent_id,  # provider handled via tie_break_values ordering below
    )


def rank_eligible_candidates(
    role: WorkflowRoleRequirement,
    report: RoleEligibilityReport,
    snapshot: AgentRegistrySnapshot,
    ranking_policy: AgentRankingPolicy,
    logical_time: float,
) -> RoleCandidateRanking:
    """Rank exactly the P1-ELIGIBLE candidates in ``report`` for ``role``."""
    eligible = [r for r in report.results if r.state is EligibilityState.ELIGIBLE]
    excluded = len(report.results) - len(eligible)

    scored: List[Tuple[tuple, AgentRankResult, Dict[str, int]]] = []
    for res in eligible:
        profile = snapshot.profile(res.agent_id, res.agent_version)
        if profile is None:  # snapshot pinning guarantee; defensive
            continue
        crits = tuple(_criterion_result(c, role, profile, snapshot, logical_time)
                      for c in ranking_policy.criteria)
        by_metric = {c.metric: cr.normalized_bp for c, cr in zip(ranking_policy.criteria, crits)}
        total = sum(cr.weighted_contribution_bp for cr in crits)
        tie_vals = (
            str(total),
            str(by_metric.get("evidence_strength", 0)),
            str(by_metric.get("evidence_freshness", 0)),
            str(by_metric.get("reliability", 0)),
            str(by_metric.get("cost", 0)),
            str(by_metric.get("latency", 0)),
            profile.provider_id, res.agent_id, res.agent_version,
        )
        rr = AgentRankResult(
            role_id=role.role_id, agent_id=res.agent_id, agent_version=res.agent_version,
            eligibility_result_fingerprint=res.result_fingerprint,
            criterion_results=crits, total_score=total, rank=0, tie_group=0,
            tie_break_values=tie_vals,
            evidence_refs=tuple(sorted({r for cr in crits for r in cr.evidence_refs})),
            policy_refs=(ranking_policy.policy_id,),
            snapshot_digest=snapshot.snapshot_digest,
            ranking_policy_digest=ranking_policy.policy_digest)
        # full deterministic sort key incl. lexical identity as the final total-order guarantee
        key = (-total,
               -by_metric.get("evidence_strength", 0),
               -by_metric.get("evidence_freshness", 0),
               -by_metric.get("reliability", 0),
               -by_metric.get("cost", 0),
               -by_metric.get("latency", 0),
               profile.provider_id, res.agent_id, res.agent_version)
        scored.append((key, rr, by_metric))

    scored.sort(key=lambda t: t[0])

    ranked: List[AgentRankResult] = []
    prev_score: Optional[int] = None
    tie_group = 0
    for i, (_key, rr, _bm) in enumerate(scored, start=1):
        if rr.total_score != prev_score:
            tie_group += 1
            prev_score = rr.total_score
        rr = rr.model_copy(update={"rank": i, "tie_group": tie_group})
        ranked.append(stamp_fingerprint(rr, "result_fingerprint"))

    out = RoleCandidateRanking(
        role_id=role.role_id, ranked_candidates=tuple(ranked),
        eligible_candidate_count=len(eligible), excluded_candidate_count=excluded,
        ranking_policy_digest=ranking_policy.policy_digest,
        snapshot_digest=snapshot.snapshot_digest, role_fingerprint=role.role_fingerprint)
    return stamp_fingerprint(out, "ranking_fingerprint")


def rank_workflow_candidates(
    adaptation_result,
    snapshot: AgentRegistrySnapshot,
    enterprise_policy,
    eligibility_policy,
    ranking_policy: AgentRankingPolicy,
    logical_time: float,
) -> Tuple[RoleCandidateRanking, ...]:
    """Evaluate P1 eligibility then rank every AI-agent role in the adaptation."""
    out: List[RoleCandidateRanking] = []
    for role in sorted(adaptation_result.role_requirements, key=lambda r: r.role_id):
        report = evaluate_registry_for_role(role, snapshot, enterprise_policy,
                                            eligibility_policy, logical_time)
        out.append(rank_eligible_candidates(role, report, snapshot, ranking_policy, logical_time))
    return tuple(out)


__all__ = [
    "RankingCriterion",
    "AgentRankingPolicy",
    "RankingCriterionResult",
    "AgentRankResult",
    "RoleCandidateRanking",
    "rank_eligible_candidates",
    "rank_workflow_candidates",
]
