"""Hard-constraint eligibility tests (§24 — Eligibility constraints; I1, I3, I11, I12)."""
from __future__ import annotations

from ugence_agent_workforce_composer.agents import AgentStatus
from ugence_agent_workforce_composer.contracts import NO_ELIGIBLE_AGENT, EligibilityState
from ugence_agent_workforce_composer.eligibility import (
    evaluate_agent_eligibility,
    evaluate_registry_for_role,
)
from ugence_agent_workforce_composer.reasons import EliminationReason
from ugence_agent_workforce_composer import fixtures
from ._helpers import (
    NOW,
    eligibility,
    enterprise,
    make_evidence,
    make_profile,
    make_role,
    make_snapshot,
)


def _eval(profile, role, *, evidence=None, ent=None, elig=None):
    evidence = evidence if evidence is not None else [
        make_evidence(profile.agent_id, profile.agent_version, "evidence_extraction", "MEASURED")]
    snap = make_snapshot([profile], evidence)
    return evaluate_agent_eligibility(role, profile, snap, ent or enterprise(),
                                      elig or eligibility(), NOW)


def test_missing_capability():
    p = make_profile(caps=("something_else",))
    r = _eval(p, make_role(required_capabilities=("evidence_extraction",)),
              evidence=[])
    assert r.state is EligibilityState.INELIGIBLE
    assert EliminationReason.MISSING_REQUIRED_CAPABILITY.value in r.elimination_reasons


def test_incompatible_input_schema():
    p = make_profile(input_contracts=("x",))
    r = _eval(p, make_role(input_contract_refs=("needed_input",)))
    assert EliminationReason.INPUT_CONTRACT_INCOMPATIBLE.value in r.elimination_reasons


def test_incompatible_output_schema():
    p = make_profile(output_contracts=("x",))
    r = _eval(p, make_role(output_contract_refs=("needed_output",)))
    assert EliminationReason.OUTPUT_CONTRACT_INCOMPATIBLE.value in r.elimination_reasons


def test_required_tool_unavailable():
    p = make_profile(supported_tools=())
    r = _eval(p, make_role(required_tools=("special_tool",)))
    assert EliminationReason.REQUIRED_TOOL_UNAVAILABLE.value in r.elimination_reasons


def test_prohibited_tool_required():
    p = make_profile(supported_tools=("shell_exec",))
    r = _eval(p, make_role(required_tools=("shell_exec",)),
              ent=enterprise(forbidden_tools=("shell_exec",)))
    assert EliminationReason.PROHIBITED_TOOL_REQUIRED.value in r.elimination_reasons


def test_forbidden_provider():
    p = make_profile(provider="forbiddenco")
    r = _eval(p, make_role(), ent=enterprise(forbidden_providers=("forbiddenco",)))
    assert EliminationReason.PROVIDER_FORBIDDEN.value in r.elimination_reasons


def test_provider_not_approved():
    p = make_profile(provider="randomco")
    r = _eval(p, make_role(), ent=enterprise(allowed_providers=("anthropic",)))
    assert EliminationReason.PROVIDER_NOT_APPROVED.value in r.elimination_reasons


def test_wrong_residency():
    p = make_profile(residency="IN")
    r = _eval(p, make_role(), ent=enterprise(required_residencies=("US",)))
    assert EliminationReason.RESIDENCY_MISMATCH.value in r.elimination_reasons


def test_wrong_deployment_environment():
    p = make_profile(deployment_environment="edge")
    r = _eval(p, make_role(), ent=enterprise(allowed_deployment_environments=("cloud",)))
    assert EliminationReason.DEPLOYMENT_ENVIRONMENT_MISMATCH.value in r.elimination_reasons


def test_insufficient_security_classification():
    p = make_profile(security_classification=1)
    r = _eval(p, make_role(), ent=enterprise(minimum_security_classification=3))
    assert EliminationReason.SECURITY_CLASSIFICATION_INSUFFICIENT.value in r.elimination_reasons


def test_missing_audit_support():
    p = make_profile(audit_capabilities=())
    r = _eval(p, make_role(), ent=enterprise(required_audit_capabilities=("trace",)))
    assert EliminationReason.AUDIT_CAPABILITY_INSUFFICIENT.value in r.elimination_reasons


def test_excessive_permission_requirement():
    p = make_profile(requested_permissions=("read", "delete_all"))
    r = _eval(p, make_role(), ent=enterprise(maximum_permission_scope=("read",)))
    assert EliminationReason.PERMISSION_REQUIREMENT_EXCEEDS_POLICY.value in r.elimination_reasons


def test_excessive_authority_requirement():
    p = make_profile(maximum_authority_scope=9)
    r = _eval(p, make_role(authority_ceiling=2))
    assert EliminationReason.AUTHORITY_REQUIREMENT_EXCEEDS_CEILING.value in r.elimination_reasons


def test_hard_cost_breach():
    p = make_profile(cost_evidence=999.0)
    r = _eval(p, make_role(), ent=enterprise(maximum_cost_hard_limit=10.0))
    assert EliminationReason.COST_HARD_LIMIT_EXCEEDED.value in r.elimination_reasons


def test_hard_latency_breach():
    p = make_profile(latency_evidence=99999.0)
    r = _eval(p, make_role(), ent=enterprise(maximum_latency_hard_limit=1000.0))
    assert EliminationReason.LATENCY_HARD_LIMIT_EXCEEDED.value in r.elimination_reasons


def test_quality_floor_failure():
    p = make_profile(quality_evidence=0.1)
    r = _eval(p, make_role(), ent=enterprise(minimum_quality_hard_limit=0.8))
    assert EliminationReason.QUALITY_FLOOR_NOT_MET.value in r.elimination_reasons


def test_inactive_and_revoked_agent():
    r1 = _eval(make_profile(status=AgentStatus.INACTIVE), make_role())
    assert EliminationReason.AGENT_INACTIVE.value in r1.elimination_reasons
    r2 = _eval(make_profile(status=AgentStatus.REVOKED), make_role())
    assert EliminationReason.AGENT_VERSION_REVOKED.value in r2.elimination_reasons


def test_agent_version_not_approved():
    p = make_profile("a", "3.0.0")
    r = _eval(p, make_role(), ent=enterprise(approved_agent_versions=("a@1.0.0",)))
    assert EliminationReason.AGENT_VERSION_NOT_APPROVED.value in r.elimination_reasons


def test_constraint_supremacy_no_partial_pass(_role=None):
    # I1: any hard failure => not eligible, regardless of other passes
    p = make_profile(security_classification=1)  # fails security only
    r = _eval(p, make_role(), ent=enterprise(minimum_security_classification=5))
    assert r.state is EligibilityState.INELIGIBLE
    assert r.eligible is False


def test_empty_eligible_set_is_typed():
    # I12: a role with zero eligible agents yields NO_ELIGIBLE_AGENT
    p = make_profile(provider="forbiddenco")
    snap = make_snapshot([p], [make_evidence("agent_x", "1.0.0", "evidence_extraction", "MEASURED")])
    rep = evaluate_registry_for_role(make_role(), snap, enterprise(forbidden_providers=("forbiddenco",)),
                                     eligibility(), NOW)
    assert rep.outcome == NO_ELIGIBLE_AGENT
    assert rep.eligible_agent_ids == ()


def test_total_agent_accounting():
    # I3: every agent in the snapshot gets exactly one result for the role
    snap = fixtures.registry_snapshot()
    adapt, _ = fixtures.run_demo("procurement")
    role = adapt.role_requirements[0]
    rep = evaluate_registry_for_role(role, snap, fixtures.enterprise_policy(),
                                     fixtures.eligibility_policy(), fixtures.LOGICAL_TIME)
    result_agents = [(r.agent_id, r.agent_version) for r in rep.results]
    snap_agents = [(p.agent_id, p.agent_version) for p in snap.agent_profiles]
    assert sorted(result_agents) == sorted(snap_agents)
    assert len(result_agents) == len(set(result_agents))


def test_no_score_or_rank_in_results():
    # I4: results carry no score/rank/winner field
    adapt, res = fixtures.run_demo("procurement")
    for rep in res.reports:
        for r in rep.results:
            keys = set(r.model_dump().keys())
            for banned in ("score", "rank", "weight", "winner", "recommended", "selected"):
                assert banned not in keys
