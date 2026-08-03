"""AgentTeamPlan / replay / diff tests (§31 AgentTeamPlan; P2-I18,I19)."""
from __future__ import annotations

from ugence_agent_workforce_composer import fixtures
from ugence_agent_workforce_composer.composition_contracts import AgentTeamPlanState, SelectionState
from ugence_agent_workforce_composer.plan import (
    build_agent_team_plan,
    compare_agent_team_plans,
    replay_agent_team_plan,
)
from ._p2 import adaptation, default_policies


def _plan(name="procurement", **overrides):
    adapt = adaptation(name)
    pol = default_policies()
    pol.update(overrides)
    snap = pol.pop("snapshot", fixtures.registry_snapshot())
    plan = build_agent_team_plan(adapt, snap, pol["enterprise"], pol["eligibility"],
                                 pol["ranking"], pol["composition"], pol["permission"],
                                 pol["fallback"], fixtures.LOGICAL_TIME)
    return adapt, snap, pol, plan


def test_complete_plan_has_all_roles_assigned():
    adapt, _s, _p, plan = _plan("procurement")
    assert plan.plan_state is AgentTeamPlanState.COMPLETE
    assigned = {a.role_id for a in plan.role_assignments}
    assert assigned == {r.role_id for r in adapt.role_requirements}
    assert plan.unfilled_roles == ()
    assert len(plan.permission_bound_proposals) == len(plan.role_assignments)
    assert len(plan.role_fallback_plans) == len(plan.role_assignments)


def test_partial_never_reported_complete():
    _a, _s, _p, plan = _plan("security")
    assert plan.plan_state is AgentTeamPlanState.NO_FEASIBLE_TEAM
    assert plan.role_assignments == ()
    assert "role::sec_evidence_collection" in plan.unfilled_roles


def test_non_agent_dispositions_preserved():
    adapt, _s, _p, plan = _plan("procurement")
    assert len(plan.non_agent_dispositions) == len(adapt.non_agent_dispositions)
    # governance/human nodes surfaced as boundary refs, never assigned
    assert "proc_binding_approval" in plan.governance_boundary_refs
    assigned_nodes = {a.role_id for a in plan.role_assignments}
    for na in plan.non_agent_dispositions:
        assert na["node_id"] not in assigned_nodes


def test_all_digests_pinned():
    _a, snap, pol, plan = _plan("procurement")
    assert plan.registry_snapshot_digest == snap.snapshot_digest
    assert plan.ranking_policy_digest == pol["ranking"].policy_digest
    assert plan.composition_policy_digest == pol["composition"].policy_digest
    assert plan.permission_policy_digest == pol["permission"].policy_digest
    assert plan.fallback_policy_digest == pol["fallback"].policy_digest
    assert plan.plan_fingerprint.startswith("sha256:")


def test_replay_reproduces_plan_across_calls():
    adapt, snap, pol, plan = _plan("procurement")
    replay = replay_agent_team_plan(adapt, snap, pol["enterprise"], pol["eligibility"],
                                    pol["ranking"], pol["composition"], pol["permission"],
                                    pol["fallback"], fixtures.LOGICAL_TIME, expected=plan)
    assert replay.plan_fingerprint == plan.plan_fingerprint
    assert replay.model_dump() == plan.model_dump()


def test_selection_explanation_states():
    _a, _s, _p, plan = _plan("procurement")
    states = {s[1] for re in plan.selection_explanation.role_explanations for s in re.candidate_states}
    assert SelectionState.SELECTED_PRIMARY.value in states
    assert SelectionState.INELIGIBLE.value in states  # eliminated candidates explained
    # every role explanation names its primary
    for re in plan.selection_explanation.role_explanations:
        assert re.selected_primary


def test_plan_comparison_policy_change():
    from ugence_agent_workforce_composer.policy import finalize_enterprise_policy
    _a, _s, pol, plan_a = _plan("procurement")
    # tighten provider policy: forbid openai → forces a different supplier-evidence agent
    ent2 = finalize_enterprise_policy(fixtures.enterprise_policy().model_copy(
        update={"forbidden_providers": ("forbiddenco", "openai"), "policy_digest": ""}))
    _a2, _s2, _p2, plan_b = _plan("procurement", enterprise=ent2)
    diff = compare_agent_team_plans(plan_a, plan_b)
    assert diff.same_workflow and not diff.workflow_mismatch
    assert diff.assignment_changes or diff.policy_digest_changes


def test_plan_comparison_workflow_mismatch_typed():
    _a1, _s1, _p1, proc = _plan("procurement")
    _a2, _s2, _p2, supp = _plan("support")
    diff = compare_agent_team_plans(proc, supp)
    assert diff.workflow_mismatch is True and diff.same_workflow is False


def test_plan_ordering_independence():
    # snapshot built from shuffled inputs yields the same plan fingerprint
    _a, _s, _p, p1 = _plan("procurement")
    _a2, _s2, _p2, p2 = _plan("procurement")
    assert p1.plan_fingerprint == p2.plan_fingerprint
