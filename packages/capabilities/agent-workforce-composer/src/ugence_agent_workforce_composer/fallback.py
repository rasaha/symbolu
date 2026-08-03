"""Deterministic offline primary + fallback planning.

Fallbacks are drawn ONLY from the pinned P1-eligible, ranked candidate set for the
same role (P2-I14), never the primary (P2-I15), are permission-feasible, preserve
residency/security/authority equivalence, and are deterministically ordered
(preferring failure-domain diversity vs the primary). Fallback planning is offline:
it never observes live availability and never performs runtime reassignment. A
missing fallback is reported honestly — coverage is never manufactured.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .agents import AgentProfile, AgentRegistrySnapshot
from .canonical import AwcModel
from .composition_contracts import FallbackState
from .failure_domains import build_failure_domain_set
from .fingerprint import stamp_fingerprint
from .permissions import PermissionBoundingPolicy, propose_permission_bound
from .policy import EnterpriseAgentPolicy
from .ranking import RoleCandidateRanking
from .version import COMPOSITION_CONTRACT_VERSION
from .workflow import WorkflowRoleRequirement


class AgentFallbackPolicy(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    policy_id: str
    policy_version: str
    maximum_fallback_depth: int = 2
    minimum_fallback_rank_quality_bp: int = 0
    require_contract_equivalence: bool = True
    require_permission_feasibility: bool = True
    prefer_provider_diversity: bool = True
    prefer_failure_domain_diversity: bool = True
    require_residency_equivalence: bool = True
    require_security_equivalence: bool = True
    require_authority_equivalence: bool = True
    policy_digest: str = ""


class FallbackCandidate(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    agent_id: str
    agent_version: str
    rank: int
    ranking_score: int
    fallback_order: int
    eligibility_fingerprint: str
    rank_fingerprint: str
    permission_bound_ref: str = ""
    failure_domain_comparison: str = ""   # "different_provider" | "same_provider"
    selection_reason: str = ""
    fallback_fingerprint: str = ""


class RoleFallbackPlan(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    role_id: str
    primary_agent_id: str
    primary_agent_version: str
    fallback_state: FallbackState
    candidates: Tuple[FallbackCandidate, ...] = ()
    policy_digest: str = ""
    plan_fingerprint: str = ""


class TeamFallbackPlan(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    role_fallback_plans: Tuple[RoleFallbackPlan, ...] = ()
    fully_covered_roles: int = 0
    uncovered_roles: Tuple[str, ...] = ()
    plan_fingerprint: str = ""


def _equivalent(primary: AgentProfile, cand: AgentProfile, policy: AgentFallbackPolicy) -> bool:
    if policy.require_residency_equivalence and primary.residency != cand.residency:
        return False
    if policy.require_security_equivalence and cand.security_classification < primary.security_classification:
        return False
    if policy.require_authority_equivalence and cand.maximum_authority_scope > primary.maximum_authority_scope + 0:
        # a fallback must not exceed the primary's authority envelope
        if cand.maximum_authority_scope > primary.maximum_authority_scope:
            return False
    return True


def build_fallback_plan(
    role: WorkflowRoleRequirement,
    ranking: RoleCandidateRanking,
    primary_agent_id: str,
    primary_agent_version: str,
    snapshot: AgentRegistrySnapshot,
    enterprise_policy: EnterpriseAgentPolicy,
    permission_policy: PermissionBoundingPolicy,
    fallback_policy: AgentFallbackPolicy,
) -> RoleFallbackPlan:
    primary = snapshot.profile(primary_agent_id, primary_agent_version)
    primary_fd = set(build_failure_domain_set(primary).values_by_kind_provider()) if primary else set()

    alternatives = [rr for rr in ranking.ranked_candidates
                    if (rr.agent_id, rr.agent_version) != (primary_agent_id, primary_agent_version)]

    if fallback_policy.maximum_fallback_depth <= 0:
        return _finish(role, primary_agent_id, primary_agent_version, [], FallbackState.NOT_REQUIRED,
                       fallback_policy)
    if not alternatives:
        return _finish(role, primary_agent_id, primary_agent_version, [],
                       FallbackState.NO_FALLBACK_AVAILABLE, fallback_policy)

    feasible: List[dict] = []
    for rr in alternatives:
        prof = snapshot.profile(rr.agent_id, rr.agent_version)
        if prof is None:
            continue
        if rr.total_score < fallback_policy.minimum_fallback_rank_quality_bp:
            continue
        if fallback_policy.require_permission_feasibility:
            prop = propose_permission_bound(role, prof, enterprise_policy, permission_policy)
            if not prop.feasible:
                continue
            perm_ref = prop.proposal_fingerprint
        else:
            perm_ref = ""
        if not _equivalent(primary, prof, fallback_policy) if primary else False:
            continue
        diverse = not (set(build_failure_domain_set(prof).values_by_kind_provider()) & primary_fd)
        feasible.append({"rr": rr, "perm_ref": perm_ref, "diverse": diverse})

    if not feasible:
        return _finish(role, primary_agent_id, primary_agent_version, [],
                       FallbackState.NO_FALLBACK_AVAILABLE, fallback_policy)

    # deterministic order: prefer failure-domain-diverse first (if configured), else by rank.
    if fallback_policy.prefer_failure_domain_diversity or fallback_policy.prefer_provider_diversity:
        feasible.sort(key=lambda f: (0 if f["diverse"] else 1, f["rr"].rank))
    else:
        feasible.sort(key=lambda f: f["rr"].rank)

    chosen = feasible[: fallback_policy.maximum_fallback_depth]
    cands = []
    for order, f in enumerate(chosen, start=1):
        rr = f["rr"]
        fc = FallbackCandidate(
            agent_id=rr.agent_id, agent_version=rr.agent_version, rank=rr.rank,
            ranking_score=rr.total_score, fallback_order=order,
            eligibility_fingerprint=rr.eligibility_result_fingerprint,
            rank_fingerprint=rr.result_fingerprint, permission_bound_ref=f["perm_ref"],
            failure_domain_comparison="different_provider" if f["diverse"] else "same_provider",
            selection_reason=f"rank #{rr.rank}, score {rr.total_score}bp, "
                             f"{'diverse' if f['diverse'] else 'same'} failure domain")
        cands.append(stamp_fingerprint(fc, "fallback_fingerprint"))

    state = (FallbackState.COMPLETE
             if len(chosen) >= min(fallback_policy.maximum_fallback_depth, len(feasible))
             and len(chosen) == fallback_policy.maximum_fallback_depth
             else FallbackState.PARTIAL)
    if len(feasible) < fallback_policy.maximum_fallback_depth:
        state = FallbackState.PARTIAL if chosen else FallbackState.NO_FALLBACK_AVAILABLE
    return _finish(role, primary_agent_id, primary_agent_version, cands, state, fallback_policy)


def _finish(role, pid, pver, cands, state, policy) -> RoleFallbackPlan:
    plan = RoleFallbackPlan(
        role_id=role.role_id, primary_agent_id=pid, primary_agent_version=pver,
        fallback_state=state, candidates=tuple(cands), policy_digest=policy.policy_digest)
    return stamp_fingerprint(plan, "plan_fingerprint")


def build_team_fallback_plan(role_plans: List[RoleFallbackPlan]) -> TeamFallbackPlan:
    covered = sum(1 for p in role_plans if p.fallback_state is FallbackState.COMPLETE)
    uncovered = tuple(p.role_id for p in role_plans
                      if p.fallback_state in (FallbackState.NO_FALLBACK_AVAILABLE,
                                              FallbackState.INVALID))
    plan = TeamFallbackPlan(role_fallback_plans=tuple(role_plans),
                            fully_covered_roles=covered, uncovered_roles=uncovered)
    return stamp_fingerprint(plan, "plan_fingerprint")


__all__ = [
    "AgentFallbackPolicy",
    "FallbackCandidate",
    "RoleFallbackPlan",
    "TeamFallbackPlan",
    "build_fallback_plan",
    "build_team_fallback_plan",
]
