"""The four scenarios must actually demonstrate the pedagogical outcomes P3A
promises — verified against the real engine, not asserted in prose.
"""
import pytest

import ugence_agent_workforce_composer.api as awc
import _loader as L

# Domain vocabulary used to check that selected agents are domain-credible and
# that cross-domain specialists are never assigned outside their domain.
_DOMAIN_TOKENS = {
    "procurement": ("supplier", "procurement", "general_analyst"),
    "customer_support": ("support", "knowledge", "response", "multilingual", "general_analyst"),
    "cybersecurity_success": ("security", "threat", "incident", "general_analyst"),
    "cybersecurity_no_feasible_team": ("threat", "incident"),
}
_FOREIGN_SPECIALIST = "threat_analysis"  # a cyber specialist must never draft support


def _plan(sid):
    return L.run_pipeline(L.load_inputs(sid))["plan"]


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_non_agent_dispositions_preserved(sid):
    out = L.run_pipeline(L.load_inputs(sid))
    adaptation, plan = out["adaptation"], out["plan"]
    # every non-agent node from the adaptation is carried into the plan verbatim
    adapt_ids = sorted(d.node_id for d in adaptation.non_agent_dispositions)
    plan_ids = sorted(na["node_id"] for na in plan.non_agent_dispositions)
    assert adapt_ids == plan_ids
    # and total node accounting holds (roles + non-agent == all nodes)
    assert adaptation.accounting_holds()


def test_procurement_is_non_greedy():
    """The individually top-ranked candidate for a role is NOT the one selected,
    because the provider-concentration limit forbids the greedy all-Anthropic team."""
    s = L.load_inputs("procurement")
    out = L.run_pipeline(s)
    plan = out["plan"]
    assert plan.plan_state.value == "COMPLETE"

    rankings = {rk.role_id: rk for rk in out["rankings"]}
    selected = {a.role_id: (a.primary_agent_id, a.primary_agent_version)
                for a in plan.role_assignments}

    non_greedy_roles = []
    for role_id, rk in rankings.items():
        top = rk.ranked_candidates[0]
        if (top.agent_id, top.agent_version) != selected[role_id]:
            non_greedy_roles.append(role_id)
    assert non_greedy_roles, "expected at least one role where the top-ranked agent is not selected"

    # and the selected team spans >1 provider (the reason the swap happened)
    providers = set()
    for (aid, ver) in selected.values():
        providers.add(s["registry"].profile(aid, ver).provider_id)
    assert len(providers) >= 2


def test_cybersecurity_success_is_complete():
    plan = _plan("cybersecurity_success")
    assert plan.plan_state.value == "COMPLETE"
    assert not plan.unfilled_roles
    assert len(plan.role_assignments) == 4


def test_cybersecurity_no_feasible_team():
    plan = _plan("cybersecurity_no_feasible_team")
    assert plan.plan_state.value == "NO_FEASIBLE_TEAM"
    assert not plan.role_assignments
    # credible reason: each role IS individually eligible (so this is a genuine
    # team-level infeasibility, not merely an empty registry)
    out = L.run_pipeline(L.load_inputs("cybersecurity_no_feasible_team"))
    for rep in out["eligibility"].reports:
        assert rep.eligible_agent_ids, f"role {rep.role_id} had no eligible agent at all"


def test_at_least_one_role_has_no_fallback_available():
    seen = False
    for sid in L.SCENARIOS:
        for fp in _plan(sid).role_fallback_plans:
            if fp.fallback_state.value == "NO_FALLBACK_AVAILABLE":
                seen = True
    assert seen, "no scenario demonstrates NO_FALLBACK_AVAILABLE"


@pytest.mark.parametrize("sid", ["procurement", "customer_support", "cybersecurity_success"])
def test_selected_agents_are_domain_credible(sid):
    plan = _plan(sid)
    tokens = _DOMAIN_TOKENS[sid]
    for a in plan.role_assignments:
        assert any(t in a.primary_agent_id for t in tokens), (
            f"{sid}: selected agent {a.primary_agent_id} is not domain-credible")


def test_cyber_specialist_not_assigned_to_support_drafting():
    """A cybersecurity specialist present in the support registry must be
    eliminated for the drafting role, never mis-assigned to it."""
    out = L.run_pipeline(L.load_inputs("customer_support"))
    # the threat specialist is assigned to no role
    assigned = {a.primary_agent_id for a in out["plan"].role_assignments}
    assert not any(_FOREIGN_SPECIALIST in aid for aid in assigned)
    # and it is explicitly eliminated (ineligible) on the drafting role
    draft = [rep for rep in out["eligibility"].reports if rep.role_id.endswith("sup_draft")][0]
    assert any(_FOREIGN_SPECIALIST in aid for aid in draft.eliminated_agent_ids)


def test_residency_elimination_is_visible_in_procurement():
    out = L.run_pipeline(L.load_inputs("procurement"))
    reasons = set()
    for rep in out["eligibility"].reports:
        for res in rep.results:
            reasons.update(res.elimination_reasons)
    assert "RESIDENCY_MISMATCH" in reasons
