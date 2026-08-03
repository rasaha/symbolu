"""Bounded exact multi-role team composition (deterministic branch-and-bound).

Composes one primary agent per AI-agent role, subject to team-level HARD
constraints, maximizing a deterministic team objective. Hard constraints are never
offset by objective score (P2-I2). The search is exact within declared bounds: an
admissible upper bound prunes only branches that cannot beat the incumbent, and a
brute-force oracle (`bruteforce_optimum`) proves equality in tests (P2-I7). When the
assignment space exceeds the policy limit, a typed `SEARCH_SPACE_EXCEEDED` result is
returned — candidates are never silently truncated.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .agents import AgentProfile, AgentRegistrySnapshot
from .canonical import AwcModel
from .composition_contracts import CompositionState, OptimalityStatus
from .dependency import RoleDependencyGraph
from .failure_domains import build_failure_domain_set
from .fingerprint import stamp_fingerprint
from .permissions import PermissionBoundProposal, PermissionBoundingPolicy, propose_permission_bound
from .policy import EnterpriseAgentPolicy
from .ranking import RoleCandidateRanking
from .version import COMPOSITION_CONTRACT_VERSION
from .workflow import WorkflowRoleRequirement


class TeamCompositionPolicy(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    policy_id: str
    policy_version: str
    # -- objective weights (basis points) --
    weight_ranking_bp: int = 8000
    weight_provider_diversity_bp: int = 1000
    weight_failure_domain_diversity_bp: int = 1000
    # -- hard team constraints --
    require_interface_compatibility: bool = True
    provider_concentration_limit_pct: int = 67      # max % of roles to one provider
    failure_domain_concentration_limit_pct: int = 67
    authority_concentration_limit_pct: int = 67     # max % of team authority to one agent
    maximum_roles_per_agent: int = 2
    minimum_provider_diversity: int = 1
    minimum_deployment_diversity: int = 1
    team_cost_hard_ceiling: Optional[float] = None
    team_latency_hard_ceiling: Optional[float] = None
    team_reliability_floor: Optional[float] = None
    # -- search bounds --
    maximum_ai_roles: int = 12
    maximum_candidates_per_role: int = 16
    maximum_assignment_combinations: int = 100_000
    tie_break: str = "lexical_assignment"
    policy_digest: str = ""


class RoleAssignment(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    role_id: str
    primary_agent_id: str
    primary_agent_version: str
    total_score: int = 0
    rank_result_fingerprint: str = ""
    eligibility_result_fingerprint: str = ""
    required_interface_refs: Tuple[str, ...] = ()
    proposed_permission_bound_ref: str = ""
    fallback_plan_ref: str = ""
    assignment_explanation: str = ""
    assignment_fingerprint: str = ""


class TeamConstraintResult(AwcModel):
    constraint: str
    satisfied: bool
    measured_value: str = ""
    limit_value: str = ""
    detail: str = ""


class TeamObjectiveResult(AwcModel):
    objective: str
    raw_value: str
    normalized_value: int
    weight: int
    weighted_contribution: int
    evidence_refs: Tuple[str, ...] = ()
    explanation: str = ""


class SearchStatistics(AwcModel):
    algorithm: str = "deterministic_branch_and_bound"
    search_space_size: int = 0
    assignments_explored: int = 0
    assignments_pruned: int = 0
    feasible_team_count: int = 0
    max_roles: int = 0
    max_candidates_per_role: int = 0
    max_combinations_limit: int = 0
    optimality_status: OptimalityStatus = OptimalityStatus.INVALID_INPUT
    termination_reason: str = ""


class TeamCompositionResult(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    composition_state: CompositionState
    role_assignments: Tuple[RoleAssignment, ...] = ()
    unfilled_roles: Tuple[str, ...] = ()
    hard_constraint_results: Tuple[TeamConstraintResult, ...] = ()
    objective_results: Tuple[TeamObjectiveResult, ...] = ()
    total_team_score: int = 0
    search_statistics: SearchStatistics
    optimality_status: OptimalityStatus
    registry_snapshot_digest: str = ""
    enterprise_policy_digest: str = ""
    eligibility_policy_digest: str = ""
    ranking_policy_digest: str = ""
    composition_policy_digest: str = ""
    workflow_fingerprint: str = ""
    composition_fingerprint: str = ""


# --------------------------------------------------------------------------- #
# feasibility + objective over a full assignment (agent per role)
# --------------------------------------------------------------------------- #

class _Ctx:
    def __init__(self, roles, rankings, snapshot, enterprise, policy, permission_policy, dep_graph):
        self.roles: Dict[str, WorkflowRoleRequirement] = {r.role_id: r for r in roles}
        self.role_ids: List[str] = sorted(self.roles)
        self.snapshot: AgentRegistrySnapshot = snapshot
        self.enterprise: EnterpriseAgentPolicy = enterprise
        self.policy: TeamCompositionPolicy = policy
        self.permission_policy: PermissionBoundingPolicy = permission_policy
        self.dep_graph: RoleDependencyGraph = dep_graph
        # per-role assignable candidates = ranked eligible & permission-feasible
        self.candidates: Dict[str, List[dict]] = {}
        self.proposals: Dict[Tuple[str, str, str], PermissionBoundProposal] = {}
        for ranking in rankings:
            role = self.roles[ranking.role_id]
            lst = []
            for rr in ranking.ranked_candidates:
                prof = snapshot.profile(rr.agent_id, rr.agent_version)
                if prof is None:
                    continue
                prop = propose_permission_bound(role, prof, enterprise, permission_policy)
                self.proposals[(role.role_id, rr.agent_id, rr.agent_version)] = prop
                if not prop.feasible:
                    continue
                lst.append({"rr": rr, "profile": prof, "proposal": prop,
                            "fd": build_failure_domain_set(prof)})
            self.candidates[ranking.role_id] = lst


def _num(x, default=0.0):
    return default if x is None else x


def _team_feasibility(ctx: _Ctx, assignment: Dict[str, dict]) -> Tuple[bool, List[TeamConstraintResult]]:
    results: List[TeamConstraintResult] = []
    n = len(ctx.role_ids)
    profiles = [assignment[r]["profile"] for r in ctx.role_ids]
    ok = True

    def add(name, satisfied, measured="", limit="", detail=""):
        nonlocal ok
        results.append(TeamConstraintResult(constraint=name, satisfied=satisfied,
                                            measured_value=str(measured), limit_value=str(limit),
                                            detail=detail))
        ok = ok and satisfied

    # roles per agent
    counts: Dict[Tuple[str, str], int] = {}
    for p in profiles:
        counts[(p.agent_id, p.agent_version)] = counts.get((p.agent_id, p.agent_version), 0) + 1
    max_roles_per_agent = max(counts.values())
    add("max_roles_per_agent", max_roles_per_agent <= ctx.policy.maximum_roles_per_agent,
        max_roles_per_agent, ctx.policy.maximum_roles_per_agent)

    # provider concentration (max share of roles to one provider)
    prov_counts: Dict[str, int] = {}
    for p in profiles:
        prov_counts[p.provider_id] = prov_counts.get(p.provider_id, 0) + 1
    max_prov = max(prov_counts.values())
    add("provider_concentration", max_prov * 100 <= ctx.policy.provider_concentration_limit_pct * n,
        f"{max_prov}/{n}", f"{ctx.policy.provider_concentration_limit_pct}%")

    # failure-domain concentration (provider failure domain)
    fd_counts: Dict[str, int] = {}
    for a in assignment.values():
        for v in a["fd"].values_by_kind_provider():
            fd_counts[v] = fd_counts.get(v, 0) + 1
    max_fd = max(fd_counts.values()) if fd_counts else 0
    add("failure_domain_concentration",
        max_fd * 100 <= ctx.policy.failure_domain_concentration_limit_pct * n,
        f"{max_fd}/{n}", f"{ctx.policy.failure_domain_concentration_limit_pct}%")

    # authority concentration (max share of team proposed authority to one agent)
    auth_by_agent: Dict[Tuple[str, str], int] = {}
    total_auth = 0
    for r in ctx.role_ids:
        a = assignment[r]
        auth = a["proposal"].proposed_authority_scope
        total_auth += auth
        key = (a["profile"].agent_id, a["profile"].agent_version)
        auth_by_agent[key] = auth_by_agent.get(key, 0) + auth
    max_auth = max(auth_by_agent.values()) if auth_by_agent else 0
    auth_ok = total_auth == 0 or max_auth * 100 <= ctx.policy.authority_concentration_limit_pct * total_auth
    add("authority_concentration", auth_ok, f"{max_auth}/{total_auth}",
        f"{ctx.policy.authority_concentration_limit_pct}%")

    # provider / deployment diversity minimums
    add("min_provider_diversity", len(prov_counts) >= ctx.policy.minimum_provider_diversity,
        len(prov_counts), ctx.policy.minimum_provider_diversity)
    deployments = {p.deployment_environment for p in profiles}
    add("min_deployment_diversity", len(deployments) >= ctx.policy.minimum_deployment_diversity,
        len(deployments), ctx.policy.minimum_deployment_diversity)

    # cost / latency / reliability
    if ctx.policy.team_cost_hard_ceiling is not None:
        total_cost = sum(_num(p.cost_evidence) for p in profiles)
        add("team_cost_ceiling", total_cost <= ctx.policy.team_cost_hard_ceiling,
            total_cost, ctx.policy.team_cost_hard_ceiling)
    if ctx.policy.team_latency_hard_ceiling is not None:
        team_latency = max((_num(p.latency_evidence) for p in profiles), default=0.0)
        add("team_latency_ceiling", team_latency <= ctx.policy.team_latency_hard_ceiling,
            team_latency, ctx.policy.team_latency_hard_ceiling)
    if ctx.policy.team_reliability_floor is not None:
        team_rel = min((_num(p.reliability_evidence, 1.0) for p in profiles), default=1.0)
        add("team_reliability_floor", team_rel >= ctx.policy.team_reliability_floor,
            team_rel, ctx.policy.team_reliability_floor)

    # interface compatibility (each dependency edge's linking contract supported by both agents)
    if ctx.policy.require_interface_compatibility:
        iface_ok = True
        for d in ctx.dep_graph.dependencies:
            up = assignment.get(d.upstream_role_id)
            dn = assignment.get(d.downstream_role_id)
            if up is None or dn is None:
                continue
            if (d.required_output_contract not in up["profile"].output_contracts
                    or d.required_input_contract not in dn["profile"].input_contracts):
                iface_ok = False
        add("interface_compatibility", iface_ok)

    return ok, results


def _objective(ctx: _Ctx, assignment: Dict[str, dict]) -> Tuple[int, List[TeamObjectiveResult]]:
    profiles = [assignment[r]["profile"] for r in ctx.role_ids]
    ranking_sum = sum(assignment[r]["rr"].total_score for r in ctx.role_ids)
    providers = {p.provider_id for p in profiles}
    fds = set()
    for a in assignment.values():
        fds |= set(a["fd"].values_by_kind_provider())
    prov_div = len(providers)
    fd_div = len(fds)
    results = [
        TeamObjectiveResult(objective="aggregate_ranking_quality", raw_value=str(ranking_sum),
                            normalized_value=ranking_sum, weight=ctx.policy.weight_ranking_bp,
                            weighted_contribution=ranking_sum,
                            explanation="sum of primary ranking scores"),
        TeamObjectiveResult(objective="provider_diversity", raw_value=str(prov_div),
                            normalized_value=prov_div, weight=ctx.policy.weight_provider_diversity_bp,
                            weighted_contribution=prov_div * ctx.policy.weight_provider_diversity_bp,
                            explanation="distinct providers"),
        TeamObjectiveResult(objective="failure_domain_diversity", raw_value=str(fd_div),
                            normalized_value=fd_div,
                            weight=ctx.policy.weight_failure_domain_diversity_bp,
                            weighted_contribution=fd_div * ctx.policy.weight_failure_domain_diversity_bp,
                            explanation="distinct provider failure domains"),
    ]
    total = (ranking_sum
             + prov_div * ctx.policy.weight_provider_diversity_bp
             + fd_div * ctx.policy.weight_failure_domain_diversity_bp)
    return total, results


def _enumerate(ctx: _Ctx, branch_and_bound: bool):
    """Yield (score, assignment_tuple, assignment, constraints, objectives) for every
    FEASIBLE full assignment. Returns stats counters via the returned dict."""
    role_ids = ctx.role_ids
    cand_lists = [ctx.candidates[r] for r in role_ids]
    # best-possible remaining ranking score for the admissible bound
    best_remaining = [0] * (len(role_ids) + 1)
    for i in range(len(role_ids) - 1, -1, -1):
        top = cand_lists[i][0]["rr"].total_score if cand_lists[i] else 0
        best_remaining[i] = best_remaining[i + 1] + top
    max_div_bonus = (ctx.policy.weight_provider_diversity_bp
                     + ctx.policy.weight_failure_domain_diversity_bp) * len(role_ids)

    stats = {"explored": 0, "pruned": 0, "feasible": 0}
    best = {"score": None, "tuple": None, "payload": None}

    def dfs(i: int, partial: Dict[str, dict], partial_score: int):
        if i == len(role_ids):
            stats["explored"] += 1
            ok, cres = _team_feasibility(ctx, partial)
            if not ok:
                return
            stats["feasible"] += 1
            score, ores = _objective(ctx, partial)
            atuple = tuple((r, partial[r]["profile"].agent_id, partial[r]["profile"].agent_version)
                           for r in role_ids)
            better = (best["score"] is None or score > best["score"]
                      or (score == best["score"] and atuple < best["tuple"]))
            if better:
                best["score"] = score
                best["tuple"] = atuple
                best["payload"] = (dict(partial), cres, ores, score)
            return
        role = role_ids[i]
        # admissible bound: nothing below here can beat the incumbent
        if branch_and_bound and best["score"] is not None:
            bound = partial_score + best_remaining[i] + max_div_bonus
            if bound < best["score"]:
                stats["pruned"] += 1
                return
        for cand in cand_lists[i]:
            partial[role] = cand
            dfs(i + 1, partial, partial_score + cand["rr"].total_score)
        partial.pop(role, None)

    dfs(0, {}, 0)
    return best, stats


def bruteforce_optimum(ctx: _Ctx):
    """Full Cartesian enumeration oracle (no pruning) — used to prove B&B exactness."""
    return _enumerate(ctx, branch_and_bound=False)


def compose_agent_team(
    roles: Tuple[WorkflowRoleRequirement, ...],
    rankings: Tuple[RoleCandidateRanking, ...],
    snapshot: AgentRegistrySnapshot,
    enterprise_policy: EnterpriseAgentPolicy,
    composition_policy: TeamCompositionPolicy,
    permission_policy: PermissionBoundingPolicy,
    dep_graph: RoleDependencyGraph,
    *,
    eligibility_policy_digest: str = "",
    ranking_policy_digest: str = "",
    workflow_fingerprint: str = "",
) -> TeamCompositionResult:
    ctx = _Ctx(roles, rankings, snapshot, enterprise_policy, composition_policy,
               permission_policy, dep_graph)
    n = len(ctx.role_ids)

    def _result(state, opt, assignments=(), unfilled=(), cres=(), ores=(), total=0, stats=None):
        stats = stats or SearchStatistics(
            max_roles=n, max_candidates_per_role=composition_policy.maximum_candidates_per_role,
            max_combinations_limit=composition_policy.maximum_assignment_combinations,
            optimality_status=opt, termination_reason=state.value)
        res = TeamCompositionResult(
            composition_state=state, role_assignments=tuple(assignments),
            unfilled_roles=tuple(unfilled), hard_constraint_results=tuple(cres),
            objective_results=tuple(ores), total_team_score=total, search_statistics=stats,
            optimality_status=opt, registry_snapshot_digest=snapshot.snapshot_digest,
            enterprise_policy_digest=enterprise_policy.policy_digest,
            eligibility_policy_digest=eligibility_policy_digest,
            ranking_policy_digest=ranking_policy_digest,
            composition_policy_digest=composition_policy.policy_digest,
            workflow_fingerprint=workflow_fingerprint)
        return stamp_fingerprint(res, "composition_fingerprint")

    # bound checks (fail closed; never truncate)
    if n > composition_policy.maximum_ai_roles:
        return _result(CompositionState.SEARCH_SPACE_EXCEEDED, OptimalityStatus.SEARCH_SPACE_EXCEEDED)
    for r in ctx.role_ids:
        # candidate count is measured over ranked eligible (pre permission filter)
        ranked = next((rk for rk in rankings if rk.role_id == r), None)
        if ranked and len(ranked.ranked_candidates) > composition_policy.maximum_candidates_per_role:
            return _result(CompositionState.SEARCH_SPACE_EXCEEDED, OptimalityStatus.SEARCH_SPACE_EXCEEDED)

    unfilled = [r for r in ctx.role_ids if not ctx.candidates[r]]
    space = 1
    for r in ctx.role_ids:
        space *= max(1, len(ctx.candidates[r]))
    if not unfilled and space > composition_policy.maximum_assignment_combinations:
        return _result(CompositionState.SEARCH_SPACE_EXCEEDED, OptimalityStatus.SEARCH_SPACE_EXCEEDED)
    if unfilled:
        return _result(CompositionState.NO_FEASIBLE_TEAM, OptimalityStatus.NO_FEASIBLE_TEAM,
                       unfilled=unfilled,
                       stats=SearchStatistics(search_space_size=space, max_roles=n,
                                              optimality_status=OptimalityStatus.NO_FEASIBLE_TEAM,
                                              termination_reason="role(s) with no permission-feasible candidate"))

    best, stats = _enumerate(ctx, branch_and_bound=True)
    search_stats = SearchStatistics(
        search_space_size=space, assignments_explored=stats["explored"],
        assignments_pruned=stats["pruned"], feasible_team_count=stats["feasible"],
        max_roles=n, max_candidates_per_role=composition_policy.maximum_candidates_per_role,
        max_combinations_limit=composition_policy.maximum_assignment_combinations,
        optimality_status=(OptimalityStatus.EXACT_OPTIMUM if best["payload"]
                           else OptimalityStatus.NO_FEASIBLE_TEAM),
        termination_reason="exhaustive bounded search complete")

    if not best["payload"]:
        return _result(CompositionState.NO_FEASIBLE_TEAM, OptimalityStatus.NO_FEASIBLE_TEAM,
                       stats=search_stats)

    assignment, cres, ores, total = best["payload"]
    assignments = []
    for r in ctx.role_ids:
        a = assignment[r]
        iface_refs = tuple(sorted(
            d.required_output_contract for d in dep_graph.edges_for(r)))
        ra = RoleAssignment(
            role_id=r, primary_agent_id=a["profile"].agent_id,
            primary_agent_version=a["profile"].agent_version, total_score=a["rr"].total_score,
            rank_result_fingerprint=a["rr"].result_fingerprint,
            eligibility_result_fingerprint=a["rr"].eligibility_result_fingerprint,
            required_interface_refs=iface_refs,
            proposed_permission_bound_ref=a["proposal"].proposal_fingerprint,
            assignment_explanation=(f"selected rank #{a['rr'].rank} score {a['rr'].total_score}bp; "
                                    f"provider {a['profile'].provider_id}"))
        assignments.append(stamp_fingerprint(ra, "assignment_fingerprint"))

    return _result(CompositionState.COMPLETE, OptimalityStatus.EXACT_OPTIMUM,
                   assignments=assignments, cres=cres, ores=ores, total=total, stats=search_stats)


__all__ = [
    "TeamCompositionPolicy",
    "RoleAssignment",
    "TeamConstraintResult",
    "TeamObjectiveResult",
    "SearchStatistics",
    "TeamCompositionResult",
    "compose_agent_team",
    "bruteforce_optimum",
]
