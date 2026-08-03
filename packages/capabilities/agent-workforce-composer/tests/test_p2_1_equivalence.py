"""v1/v2 outcome equivalence over the four merged Governance Studio P3A scenarios.

For each scenario the v1+full-overlay and v2+reduced-overlay paths must produce
the SAME workforce-planning outcome (dispositions, assignments, fallbacks,
permissions), classified SEMANTICALLY_EQUIVALENT — the raw fingerprints differ
because v2 carries richer provenance and a different source contract.
"""
from __future__ import annotations

import pytest

import ugence_agent_workforce_composer.api as awc
import ugence_agent_workforce_composer.adapter_v2 as a2
import ugence_agent_workforce_composer.compatibility as compat
from . import _conformance as C


def _both(sid):
    s = C.load(sid)
    v1_ad = awc.adapt_compiled_workflow(s["v1_workflow"], role_overlay=s["v1_overlay"])
    env = a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])
    return s, v1_ad, env


@pytest.mark.parametrize("sid", C.SCENARIOS)
def test_node_dispositions_byte_identical(sid):
    _, v1_ad, env = _both(sid)
    a = {d.node_id: (d.disposition.value, d.is_agent_role) for d in v1_ad.node_dispositions}
    b = {d.node_id: (d.disposition.value, d.is_agent_role) for d in env.adaptation_result.node_dispositions}
    assert a == b


@pytest.mark.parametrize("sid", C.SCENARIOS)
def test_adaptation_semantically_equivalent(sid):
    _, v1_ad, env = _both(sid)
    rep = compat.compare_adaptations(compat._wrap_v1(v1_ad), env)
    assert rep.state == compat.AdaptationEquivalenceState.SEMANTICALLY_EQUIVALENT.value
    assert not rep.differences


@pytest.mark.parametrize("sid", C.SCENARIOS)
def test_plan_outcome_equivalent(sid):
    s, v1_ad, env = _both(sid)
    v1_plan = C.plan(v1_ad, s)
    v2_plan = C.plan(env.adaptation_result, s)
    rep = compat.compare_workforce_plans(v1_plan, v2_plan)
    assert rep.state == compat.AdaptationEquivalenceState.SEMANTICALLY_EQUIVALENT.value
    assert not rep.differences
    # same state and assignments; different raw fingerprints
    assert v1_plan.plan_state.value == v2_plan.plan_state.value
    assert {a.role_id: a.primary_agent_id for a in v1_plan.role_assignments} == \
           {a.role_id: a.primary_agent_id for a in v2_plan.role_assignments}


@pytest.mark.parametrize("sid", C.SCENARIOS)
def test_manifest_matches_recomputation(sid):
    s, v1_ad, env = _both(sid)
    m = C.manifest()["scenarios"][sid]
    assert m["adaptation_equivalence"] == "SEMANTICALLY_EQUIVALENT"
    assert m["plan_equivalence"] == "SEMANTICALLY_EQUIVALENT"
    # the committed v1 adaptation fingerprint must reproduce (v1 path frozen)
    assert v1_ad.adaptation_fingerprint == m["v1_adaptation_fingerprint"]


def test_all_four_scenarios_present():
    assert set(C.manifest()["scenarios"]) == set(C.SCENARIOS)


@pytest.mark.parametrize("sid", C.SCENARIOS)
def test_eligibility_and_ranking_unchanged(sid):
    s, v1_ad, env = _both(sid)
    v1_el = awc.evaluate_workflow_eligibility(v1_ad, s["registry"], s["enterprise_policy"],
                                              s["eligibility_policy"], C.LT)
    v2_el = awc.evaluate_workflow_eligibility(env.adaptation_result, s["registry"],
                                              s["enterprise_policy"], s["eligibility_policy"], C.LT)
    a = {r.role_id.split("::")[1]: sorted(r.eligible_agent_ids) for r in v1_el.reports}
    b = {r.role_id.split("::")[1]: sorted(r.eligible_agent_ids) for r in v2_el.reports}
    assert a == b
