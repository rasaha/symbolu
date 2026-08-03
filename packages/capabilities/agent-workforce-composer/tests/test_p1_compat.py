"""P1 compatibility regression (§31 P1 regression; P2-A2)."""
from __future__ import annotations

import ugence_agent_workforce_composer as pkg
from ugence_agent_workforce_composer import fixtures


def test_p1_contract_versions_preserved():
    assert pkg.CONTRACT_VERSION == "awc.v1"
    info = pkg.version_info().to_dict()
    assert "workflow_ir.v1" in info["supported_ir_versions"]
    assert info["composition_contract_version"] == "awc.composition.v1"


def test_p1_snapshot_digest_unchanged():
    # The P1-era synthetic snapshot digest must be byte-identical (no P1 fingerprint drift).
    assert fixtures.registry_snapshot().snapshot_digest == (
        "sha256:2cc59b17db4e93fd340f07b153bdf5cf7f9400333958db7e4e4522319b2f693f")


def test_p1_policy_digests_unchanged():
    assert fixtures.enterprise_policy().policy_digest == (
        "sha256:0526a8c1eef78330e07cb37d067337788c3b5e3210e6746f0240262aa2b077f3")


def test_p1_public_names_still_available():
    import ugence_agent_workforce_composer.api as api
    for name in ("adapt_compiled_workflow", "WorkflowRoleRequirement", "AgentProfile",
                 "AgentRegistrySnapshot", "EnterpriseAgentPolicy", "EligibilityPolicy",
                 "evaluate_registry_for_role", "EligibilityState", "EliminationReason"):
        assert name in api.__all__ and hasattr(api, name)


def test_p1_eligibility_still_deterministic():
    a1, r1 = fixtures.run_demo("procurement")
    a2, r2 = fixtures.run_demo("procurement")
    assert a1.adaptation_fingerprint == a2.adaptation_fingerprint
    assert r1.workflow_fingerprint == r2.workflow_fingerprint
