"""AgentTeamPlan — the immutable, content-addressed P2 output, plus deterministic
selection explanation, replay, and plan comparison.

The plan is a PROPOSAL: it pre-approves a primary agent and an ordered fallback set
per role, with least-privilege permission-bound proposals. It grants nothing,
authorizes nothing, and executes nothing. A runtime may later select from the
approved set, narrow permissions, escalate, or fail closed — never introduce an
unapproved agent or broaden authority (see docs/H16_RUNTIME_BOUNDARY.md).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .agents import AgentRegistrySnapshot
from .canonical import AwcModel, digest
from .composition import (
    RoleAssignment,
    SearchStatistics,
    TeamCompositionPolicy,
    TeamCompositionResult,
    TeamConstraintResult,
    TeamObjectiveResult,
    compose_agent_team,
)
from .composition_contracts import AgentTeamPlanState, CompositionState, SelectionState
from .dependency import build_role_dependency_graph
from .eligibility import evaluate_registry_for_role
from .fallback import (
    AgentFallbackPolicy,
    RoleFallbackPlan,
    build_fallback_plan,
    build_team_fallback_plan,
)
from .fingerprint import stamp_fingerprint
from .permissions import (
    PermissionBoundProposal,
    PermissionBoundingPolicy,
    propose_permission_bound,
)
from .policy import EligibilityPolicy, EnterpriseAgentPolicy
from .ranking import AgentRankingPolicy, RoleCandidateRanking, rank_eligible_candidates
from .version import COMPOSITION_CONTRACT_VERSION
from .workflow import Provenance

_PLAN_STATE = {
    CompositionState.COMPLETE: AgentTeamPlanState.COMPLETE,
    CompositionState.PARTIAL: AgentTeamPlanState.PARTIAL,
    CompositionState.NO_FEASIBLE_TEAM: AgentTeamPlanState.NO_FEASIBLE_TEAM,
    CompositionState.SEARCH_SPACE_EXCEEDED: AgentTeamPlanState.SEARCH_SPACE_EXCEEDED,
    CompositionState.INVALID_INPUT: AgentTeamPlanState.INVALID_INPUT,
}


class RoleSelectionExplanation(AwcModel):
    role_id: str
    selected_primary: str = ""
    candidate_states: Tuple[Tuple[str, str, str], ...] = ()   # (agent@ver, state, reason)
    team_tradeoffs: Tuple[str, ...] = ()


class TeamSelectionExplanation(AwcModel):
    workflow_identity: str
    role_explanations: Tuple[RoleSelectionExplanation, ...] = ()
    narrative: Tuple[str, ...] = ()


class AgentTeamPlan(AwcModel):
    plan_contract_version: str = COMPOSITION_CONTRACT_VERSION
    plan_id: str
    workflow_identity: str
    workflow_fingerprint: str
    compiler_source_digest: str
    registry_snapshot_id: str
    registry_snapshot_digest: str
    enterprise_policy_digest: str
    eligibility_policy_digest: str
    ranking_policy_digest: str
    composition_policy_digest: str
    permission_policy_digest: str
    fallback_policy_digest: str
    role_assignments: Tuple[RoleAssignment, ...] = ()
    non_agent_dispositions: Tuple[dict, ...] = ()
    permission_bound_proposals: Tuple[PermissionBoundProposal, ...] = ()
    role_fallback_plans: Tuple[RoleFallbackPlan, ...] = ()
    team_constraint_results: Tuple[TeamConstraintResult, ...] = ()
    team_objective_results: Tuple[TeamObjectiveResult, ...] = ()
    search_statistics: SearchStatistics
    total_team_score: int = 0
    unfilled_roles: Tuple[str, ...] = ()
    human_review_requirements: Tuple[str, ...] = ()
    governance_boundary_refs: Tuple[str, ...] = ()
    selection_explanation: TeamSelectionExplanation
    provenance: Provenance
    created_at: float = 0.0
    plan_state: AgentTeamPlanState
    plan_fingerprint: str = ""


class CompositionReplayRecord(AwcModel):
    plan_contract_version: str = COMPOSITION_CONTRACT_VERSION
    workflow_adaptation_fingerprint: str
    role_fingerprints: Tuple[str, ...]
    non_agent_disposition_fingerprints: Tuple[str, ...]
    registry_snapshot_digest: str
    enterprise_policy_digest: str
    eligibility_policy_digest: str
    ranking_policy_digest: str
    composition_policy_digest: str
    permission_policy_digest: str
    fallback_policy_digest: str
    logical_time: float
    contract_versions: Tuple[str, ...]
    expected_plan_fingerprint: str
    replay_fingerprint: str = ""


class AgentTeamPlanDiff(AwcModel):
    plan_contract_version: str = COMPOSITION_CONTRACT_VERSION
    same_workflow: bool
    workflow_mismatch: bool = False
    plan_a_fingerprint: str = ""
    plan_b_fingerprint: str = ""
    assignment_changes: Tuple[str, ...] = ()
    score_delta: int = 0
    constraint_changes: Tuple[str, ...] = ()
    permission_changes: Tuple[str, ...] = ()
    fallback_changes: Tuple[str, ...] = ()
    policy_digest_changes: Tuple[str, ...] = ()
    snapshot_changed: bool = False
    diff_fingerprint: str = ""


# --------------------------------------------------------------------------- #

def build_agent_team_plan(
    adaptation_result,
    snapshot: AgentRegistrySnapshot,
    enterprise_policy: EnterpriseAgentPolicy,
    eligibility_policy: EligibilityPolicy,
    ranking_policy: AgentRankingPolicy,
    composition_policy: TeamCompositionPolicy,
    permission_policy: PermissionBoundingPolicy,
    fallback_policy: AgentFallbackPolicy,
    logical_time: float,
) -> AgentTeamPlan:
    roles = tuple(sorted(adaptation_result.role_requirements, key=lambda r: r.role_id))
    roles_by_id = {r.role_id: r for r in roles}

    reports = {}
    rankings: List[RoleCandidateRanking] = []
    for role in roles:
        rep = evaluate_registry_for_role(role, snapshot, enterprise_policy,
                                         eligibility_policy, logical_time)
        reports[role.role_id] = rep
        rankings.append(rank_eligible_candidates(role, rep, snapshot, ranking_policy, logical_time))
    rankings_t = tuple(rankings)
    dep_graph = build_role_dependency_graph(roles)

    comp: TeamCompositionResult = compose_agent_team(
        roles, rankings_t, snapshot, enterprise_policy, composition_policy, permission_policy,
        dep_graph, eligibility_policy_digest=eligibility_policy.policy_digest,
        ranking_policy_digest=ranking_policy.policy_digest,
        workflow_fingerprint=adaptation_result.adaptation_fingerprint)

    proposals: List[PermissionBoundProposal] = []
    fallback_plans: List[RoleFallbackPlan] = []
    human_review: List[str] = []
    if comp.composition_state is CompositionState.COMPLETE:
        by_role_ranking = {rk.role_id: rk for rk in rankings_t}
        assignments = []
        for a in comp.role_assignments:
            role = roles_by_id[a.role_id]
            profile = snapshot.profile(a.primary_agent_id, a.primary_agent_version)
            prop = propose_permission_bound(role, profile, enterprise_policy, permission_policy)
            proposals.append(prop)
            if prop.requires_human_review or role.human_review_requirement:
                human_review.append(a.role_id)
            fp = build_fallback_plan(role, by_role_ranking[a.role_id], a.primary_agent_id,
                                     a.primary_agent_version, snapshot, enterprise_policy,
                                     permission_policy, fallback_policy)
            fallback_plans.append(fp)
            assignments.append(a.model_copy(update={
                "proposed_permission_bound_ref": prop.proposal_fingerprint,
                "fallback_plan_ref": fp.plan_fingerprint}))
        role_assignments = tuple(assignments)
    else:
        role_assignments = comp.role_assignments

    explanation = _explain(adaptation_result.workflow_identity, roles, reports, rankings_t,
                           comp, fallback_plans)
    non_agent = tuple(na.canonical_dict() for na in adaptation_result.non_agent_dispositions)
    governance_refs = tuple(sorted(
        na["node_id"] for na in non_agent
        if na.get("disposition") in ("HUMAN_AUTHORITY_REQUIRED", "HUMAN_REVIEW_REQUIRED",
                                     "EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP")))

    plan_state = _PLAN_STATE[comp.composition_state]
    plan_id = "plan::" + digest({
        "wf": adaptation_result.workflow_identity, "snap": snapshot.snapshot_digest,
        "ent": enterprise_policy.policy_digest, "elig": eligibility_policy.policy_digest,
        "rank": ranking_policy.policy_digest, "comp": composition_policy.policy_digest,
        "perm": permission_policy.policy_digest, "fb": fallback_policy.policy_digest,
        "t": logical_time}).split(":", 1)[1][:16]

    plan = AgentTeamPlan(
        plan_id=plan_id, workflow_identity=adaptation_result.workflow_identity,
        workflow_fingerprint=adaptation_result.adaptation_fingerprint,
        compiler_source_digest=adaptation_result.source_package_digest,
        registry_snapshot_id=snapshot.snapshot_id, registry_snapshot_digest=snapshot.snapshot_digest,
        enterprise_policy_digest=enterprise_policy.policy_digest,
        eligibility_policy_digest=eligibility_policy.policy_digest,
        ranking_policy_digest=ranking_policy.policy_digest,
        composition_policy_digest=composition_policy.policy_digest,
        permission_policy_digest=permission_policy.policy_digest,
        fallback_policy_digest=fallback_policy.policy_digest,
        role_assignments=role_assignments, non_agent_dispositions=non_agent,
        permission_bound_proposals=tuple(proposals), role_fallback_plans=tuple(fallback_plans),
        team_constraint_results=comp.hard_constraint_results,
        team_objective_results=comp.objective_results,
        search_statistics=comp.search_statistics, total_team_score=comp.total_team_score,
        unfilled_roles=comp.unfilled_roles, human_review_requirements=tuple(sorted(set(human_review))),
        governance_boundary_refs=governance_refs, selection_explanation=explanation,
        provenance=Provenance(source_kind="p2_composition",
                              synthetic=any(r.provenance.synthetic for r in roles) if roles else False),
        created_at=logical_time, plan_state=plan_state)
    return stamp_fingerprint(plan, "plan_fingerprint")


def _explain(workflow_identity, roles, reports, rankings, comp, fallback_plans) -> TeamSelectionExplanation:
    assigned = {a.role_id: (a.primary_agent_id, a.primary_agent_version)
                for a in comp.role_assignments}
    fb_agents: Dict[str, set] = {}
    for fp in fallback_plans:
        fb_agents[fp.role_id] = {(c.agent_id, c.agent_version) for c in fp.candidates}
    role_expls = []
    for rk in rankings:
        primary = assigned.get(rk.role_id)
        states: List[Tuple[str, str, str]] = []
        for rr in rk.ranked_candidates:
            ident = (rr.agent_id, rr.agent_version)
            if ident == primary:
                st = SelectionState.SELECTED_PRIMARY
                reason = f"highest feasible team fit; rank #{rr.rank}, {rr.total_score}bp"
            elif ident in fb_agents.get(rk.role_id, set()):
                st = SelectionState.SELECTED_FALLBACK
                reason = f"pre-approved fallback; rank #{rr.rank}"
            else:
                st = SelectionState.ELIGIBLE_NOT_SELECTED
                reason = f"eligible, not selected; rank #{rr.rank}, {rr.total_score}bp"
            states.append((f"{rr.agent_id}@{rr.agent_version}", st.value, reason))
        # ineligible candidates from the P1 report
        rep = reports[rk.role_id]
        for r in rep.results:
            if r.state.value != "ELIGIBLE":
                states.append((f"{r.agent_id}@{r.agent_version}", SelectionState.INELIGIBLE.value,
                               "P1-ineligible: " + ", ".join(r.elimination_reasons)))
        tradeoffs = tuple(f"{c.constraint}={c.measured_value} (limit {c.limit_value})"
                          for c in comp.hard_constraint_results if not c.satisfied) or (
                          "highest-ranked individuals may differ from best feasible team due to "
                          "provider/failure-domain/authority concentration and interface constraints",)
        role_expls.append(RoleSelectionExplanation(
            role_id=rk.role_id, selected_primary=(f"{primary[0]}@{primary[1]}" if primary else ""),
            candidate_states=tuple(states), team_tradeoffs=tradeoffs))
    narrative = (
        f"workflow {workflow_identity}: composition {comp.composition_state.value}, "
        f"{comp.optimality_status.value}; {len(assigned)} role(s) assigned, "
        f"team score {comp.total_team_score}bp",)
    return TeamSelectionExplanation(workflow_identity=workflow_identity,
                                    role_explanations=tuple(role_expls), narrative=narrative)


def build_replay_record(plan: AgentTeamPlan, adaptation_result, logical_time: float,
                        contract_versions: Tuple[str, ...]) -> CompositionReplayRecord:
    rec = CompositionReplayRecord(
        workflow_adaptation_fingerprint=plan.workflow_fingerprint,
        role_fingerprints=tuple(r.role_fingerprint for r in adaptation_result.role_requirements),
        non_agent_disposition_fingerprints=tuple(
            na.fingerprint for na in adaptation_result.non_agent_dispositions),
        registry_snapshot_digest=plan.registry_snapshot_digest,
        enterprise_policy_digest=plan.enterprise_policy_digest,
        eligibility_policy_digest=plan.eligibility_policy_digest,
        ranking_policy_digest=plan.ranking_policy_digest,
        composition_policy_digest=plan.composition_policy_digest,
        permission_policy_digest=plan.permission_policy_digest,
        fallback_policy_digest=plan.fallback_policy_digest,
        logical_time=logical_time, contract_versions=contract_versions,
        expected_plan_fingerprint=plan.plan_fingerprint)
    return stamp_fingerprint(rec, "replay_fingerprint")


def replay_agent_team_plan(
    adaptation_result, snapshot, enterprise_policy, eligibility_policy, ranking_policy,
    composition_policy, permission_policy, fallback_policy, logical_time,
    expected: Optional[AgentTeamPlan] = None,
) -> AgentTeamPlan:
    """Deterministically rebuild the plan. If ``expected`` is given, the rebuilt
    plan's fingerprint must equal it (raises AssertionError otherwise)."""
    plan = build_agent_team_plan(adaptation_result, snapshot, enterprise_policy, eligibility_policy,
                                 ranking_policy, composition_policy, permission_policy,
                                 fallback_policy, logical_time)
    if expected is not None and plan.plan_fingerprint != expected.plan_fingerprint:
        raise AssertionError("replay produced a different plan fingerprint")
    return plan


def compare_agent_team_plans(a: AgentTeamPlan, b: AgentTeamPlan) -> AgentTeamPlanDiff:
    if a.workflow_identity != b.workflow_identity:
        d = AgentTeamPlanDiff(same_workflow=False, workflow_mismatch=True,
                              plan_a_fingerprint=a.plan_fingerprint, plan_b_fingerprint=b.plan_fingerprint)
        return stamp_fingerprint(d, "diff_fingerprint")
    a_assign = {x.role_id: (x.primary_agent_id, x.primary_agent_version) for x in a.role_assignments}
    b_assign = {x.role_id: (x.primary_agent_id, x.primary_agent_version) for x in b.role_assignments}
    changes = []
    for role in sorted(set(a_assign) | set(b_assign)):
        if a_assign.get(role) != b_assign.get(role):
            changes.append(f"{role}: {a_assign.get(role)} -> {b_assign.get(role)}")
    pol = []
    for name, x, y in (("enterprise", a.enterprise_policy_digest, b.enterprise_policy_digest),
                       ("eligibility", a.eligibility_policy_digest, b.eligibility_policy_digest),
                       ("ranking", a.ranking_policy_digest, b.ranking_policy_digest),
                       ("composition", a.composition_policy_digest, b.composition_policy_digest),
                       ("permission", a.permission_policy_digest, b.permission_policy_digest),
                       ("fallback", a.fallback_policy_digest, b.fallback_policy_digest)):
        if x != y:
            pol.append(name)
    fb = []
    a_fb = {p.role_id: p.plan_fingerprint for p in a.role_fallback_plans}
    b_fb = {p.role_id: p.plan_fingerprint for p in b.role_fallback_plans}
    for role in sorted(set(a_fb) | set(b_fb)):
        if a_fb.get(role) != b_fb.get(role):
            fb.append(role)
    perm = []
    a_perm = {p.role_id: p.proposal_fingerprint for p in a.permission_bound_proposals}
    b_perm = {p.role_id: p.proposal_fingerprint for p in b.permission_bound_proposals}
    for role in sorted(set(a_perm) | set(b_perm)):
        if a_perm.get(role) != b_perm.get(role):
            perm.append(role)
    d = AgentTeamPlanDiff(
        same_workflow=True, plan_a_fingerprint=a.plan_fingerprint, plan_b_fingerprint=b.plan_fingerprint,
        assignment_changes=tuple(changes), score_delta=b.total_team_score - a.total_team_score,
        constraint_changes=(), permission_changes=tuple(perm), fallback_changes=tuple(fb),
        policy_digest_changes=tuple(pol),
        snapshot_changed=a.registry_snapshot_digest != b.registry_snapshot_digest)
    return stamp_fingerprint(d, "diff_fingerprint")


__all__ = [
    "RoleSelectionExplanation",
    "TeamSelectionExplanation",
    "AgentTeamPlan",
    "CompositionReplayRecord",
    "AgentTeamPlanDiff",
    "build_agent_team_plan",
    "build_replay_record",
    "replay_agent_team_plan",
    "compare_agent_team_plans",
]
