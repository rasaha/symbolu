"""Composition tests (§31 Composition; invariants P2-I7,I8,I9,I10)."""
from __future__ import annotations

from ugence_agent_workforce_composer import fixtures
from ugence_agent_workforce_composer.composition import (
    TeamCompositionPolicy,
    _Ctx,
    bruteforce_optimum,
    compose_agent_team,
)
from ugence_agent_workforce_composer.composition_contracts import CompositionState, OptimalityStatus
from ugence_agent_workforce_composer.dependency import build_role_dependency_graph
from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
from ugence_agent_workforce_composer.ranking import rank_workflow_candidates
from ._p2 import default_policies, adaptation


def _compose(name="procurement", composition_policy=None):
    adapt = adaptation(name)
    pol = default_policies()
    comp_policy = composition_policy or pol["composition"]
    snap = fixtures.registry_snapshot()
    rankings = rank_workflow_candidates(adapt, snap, pol["enterprise"], pol["eligibility"],
                                        pol["ranking"], fixtures.LOGICAL_TIME)
    roles = tuple(sorted(adapt.role_requirements, key=lambda r: r.role_id))
    dep = build_role_dependency_graph(roles)
    result = compose_agent_team(roles, rankings, snap, pol["enterprise"], comp_policy,
                                pol["permission"], dep,
                                ranking_policy_digest=pol["ranking"].policy_digest)
    ctx = _Ctx(roles, rankings, snap, pol["enterprise"], comp_policy, pol["permission"], dep)
    return adapt, result, ctx


def test_exact_optimum_matches_bruteforce_oracle():
    for name in ("procurement", "support"):
        _a, result, ctx = _compose(name)
        best, _stats = bruteforce_optimum(ctx)
        assert result.composition_state is CompositionState.COMPLETE
        assert result.optimality_status is OptimalityStatus.EXACT_OPTIMUM
        # branch-and-bound optimum equals full-enumeration optimum (score + assignment)
        assert result.total_team_score == best["score"]
        bb_tuple = tuple((a.role_id, a.primary_agent_id, a.primary_agent_version)
                         for a in result.role_assignments)
        assert bb_tuple == best["tuple"]


def test_no_feasible_team_typed():
    _a, result, _ctx = _compose("security")
    assert result.composition_state is CompositionState.NO_FEASIBLE_TEAM
    assert result.optimality_status is OptimalityStatus.NO_FEASIBLE_TEAM
    assert "role::sec_evidence_collection" in result.unfilled_roles
    assert result.role_assignments == ()  # partial team never emitted as complete


def test_provider_concentration_forces_non_greedy_team():
    # With a 67% provider cap, procurement cannot use anthropic for all three roles;
    # the supplier-evidence role is filled by a non-anthropic (openai) agent.
    _a, result, _ctx = _compose("procurement")
    by_role = {a.role_id: a.primary_agent_id for a in result.role_assignments}
    providers = {a.role_id: fixtures.registry_snapshot().profile(a.primary_agent_id,
                 a.primary_agent_version).provider_id for a in result.role_assignments}
    # provider concentration constraint recorded and satisfied
    conc = next(c for c in result.hard_constraint_results if c.constraint == "provider_concentration")
    assert conc.satisfied
    assert len(set(providers.values())) >= 2  # not all one provider


def test_maximum_roles_per_agent_enforced():
    pol = default_policies()
    strict = stamp_fingerprint(
        TeamCompositionPolicy(policy_id="c", policy_version="1", maximum_roles_per_agent=1,
                              provider_concentration_limit_pct=100), "policy_digest")
    _a, result, _ctx = _compose("procurement", composition_policy=strict)
    # supplier_risk and recommendation both require the single procurement specialist →
    # with max 1 role/agent there is no feasible team.
    assert result.composition_state is CompositionState.NO_FEASIBLE_TEAM


def test_search_statistics_deterministic():
    _a, r1, _c = _compose("support")
    _a2, r2, _c2 = _compose("support")
    assert r1.search_statistics.model_dump() == r2.search_statistics.model_dump()
    assert r1.search_statistics.feasible_team_count >= 1
    assert r1.search_statistics.assignments_explored >= 1


def test_total_role_and_non_agent_accounting():
    adapt, result, _ctx = _compose("procurement")
    ai_roles = {r.role_id for r in adapt.role_requirements}
    assigned = {a.role_id for a in result.role_assignments}
    assert assigned | set(result.unfilled_roles) == ai_roles
    # non-agent nodes never appear as assignments (P2-I9)
    non_agent_nodes = {n.node_id for n in adapt.non_agent_dispositions}
    assert not (assigned & non_agent_nodes)


def test_interface_compatibility_constraint_present():
    _a, result, _ctx = _compose("procurement")
    names = {c.constraint for c in result.hard_constraint_results}
    assert "interface_compatibility" in names
    assert all(c.satisfied for c in result.hard_constraint_results)


def test_composition_deterministic_fingerprint():
    _a, r1, _c = _compose("procurement")
    _a2, r2, _c2 = _compose("procurement")
    assert r1.composition_fingerprint == r2.composition_fingerprint
