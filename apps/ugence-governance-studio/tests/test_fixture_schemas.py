"""Every committed fixture parses under the real AWC schemas and all internal
references resolve."""
import json
import os

import pytest

import ugence_agent_workforce_composer.api as awc
import _loader as L


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_all_input_fixtures_present(sid):
    base = os.path.join(L.DEMO_DATA, sid)
    required = {
        "compiled_workflow.json", "enterprise_role_overlay.json",
        "agent_registry_snapshot.json", "enterprise_agent_policy.json",
        "eligibility_policy.json", "ranking_policy.json", "composition_policy.json",
        "permission_policy.json", "fallback_policy.json", "scenario_manifest.json",
    }
    assert required <= set(os.listdir(base))


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_inputs_validate_against_awc_schemas(sid):
    s = L.load_inputs(sid)  # model_validate would raise on any schema violation
    assert isinstance(s["registry"], awc.AgentRegistrySnapshot)
    assert isinstance(s["enterprise_policy"], awc.EnterpriseAgentPolicy)
    assert isinstance(s["ranking_policy"], awc.AgentRankingPolicy)
    assert isinstance(s["composition_policy"], awc.TeamCompositionPolicy)
    assert isinstance(s["permission_policy"], awc.PermissionBoundingPolicy)
    assert isinstance(s["fallback_policy"], awc.AgentFallbackPolicy)


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_workflow_is_workflow_ir_v1(sid):
    wf = L.load_inputs(sid)["workflow"]
    assert wf["workflow_ir"]["ir_version"] == "workflow_ir.v1"
    assert wf["release_metadata"]["synthetic"] is True


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_overlay_node_ids_exist_in_workflow(sid):
    s = L.load_inputs(sid)
    node_ids = {n["node_id"] for n in s["workflow"]["workflow_ir"]["nodes"]}
    for node_id in s["overlay"]:
        assert node_id in node_ids, f"overlay references unknown node {node_id!r}"


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_evidence_references_resolve_to_profiles(sid):
    snap = L.load_inputs(sid)["registry"]
    identities = {(p.agent_id, p.agent_version) for p in snap.agent_profiles}
    for ev in snap.capability_evidence:
        assert (ev.agent_id, ev.agent_version) in identities, (
            f"evidence {ev.evidence_id} references an unregistered agent")


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_provider_and_residency_are_policy_consistent(sid):
    """Every registered agent's provider is either allowed or explicitly forbidden
    by the enterprise policy — no dangling providers outside the policy vocabulary."""
    s = L.load_inputs(sid)
    ent = s["enterprise_policy"]
    known = set(ent.allowed_providers) | set(ent.forbidden_providers)
    for p in s["registry"].agent_profiles:
        assert p.provider_id in known, f"{p.agent_id}: provider {p.provider_id} not in policy"


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_fixtures_are_marked_synthetic(sid):
    s = L.load_inputs(sid)
    assert s["registry"].provenance.synthetic is True
    for p in s["registry"].agent_profiles:
        assert p.provenance.synthetic is True
    assert L.scenario_manifest(sid)["synthetic"] is True
