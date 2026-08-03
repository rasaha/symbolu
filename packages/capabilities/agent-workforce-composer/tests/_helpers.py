"""Shared test builders for the Agent Workforce Composer suite."""
from __future__ import annotations

from typing import List

from ugence_agent_workforce_composer.agents import (
    AgentCapability,
    AgentCapabilityEvidence,
    AgentProfile,
    AgentStatus,
    build_registry_snapshot,
)
from ugence_agent_workforce_composer.contracts import (
    AuthorityDisposition,
    CapabilityOwner,
    EvidenceClass,
    NodeKind,
)
from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
from ugence_agent_workforce_composer.policy import (
    EligibilityPolicy,
    EnterpriseAgentPolicy,
    finalize_eligibility_policy,
    finalize_enterprise_policy,
)
from ugence_agent_workforce_composer.workflow import (
    AuthorityContext,
    Provenance,
    WorkflowRoleRequirement,
)

NOW = 1_000_000.0
SYNTH = Provenance(source_kind="test_fixture", synthetic=True)
AUTH_CTX = AuthorityContext(owning_capability=CapabilityOwner.COMPILER,
                            authority_disposition=AuthorityDisposition.ADVISORY)


def make_role(role_id="role::test", *, required_capabilities=("evidence_extraction",),
              required_evidence_classes=(), **kw) -> WorkflowRoleRequirement:
    role = WorkflowRoleRequirement(
        role_id=role_id, workflow_id="wf_test", workflow_version=1,
        source_node_id="n_test", source_node_kind=NodeKind.EVIDENCE_REQUIREMENT,
        role_name="test role", required_capabilities=tuple(required_capabilities),
        required_evidence_classes=tuple(required_evidence_classes),
        authority_context=AUTH_CTX, provenance=SYNTH,
        source_package_digest="sha256:deadbeef", **kw)
    return stamp_fingerprint(role, "role_fingerprint")


def make_profile(agent_id="agent_x", version="1.0.0", *, provider="anthropic",
                 caps=("evidence_extraction",), **kw) -> AgentProfile:
    defaults = dict(
        provider_id=provider, agent_type="analysis", status=AgentStatus.ACTIVE,
        declared_capabilities=tuple(AgentCapability(capability_id=c) for c in caps),
        supported_tools=(), input_contracts=(), output_contracts=(),
        requested_permissions=(), maximum_authority_scope=1,
        residency="US", deployment_environment="cloud", security_classification=3,
        latency_evidence=100.0, cost_evidence=1.0, quality_evidence=0.9,
        audit_capabilities=("trace",), provenance=SYNTH)
    defaults.update(kw)
    return AgentProfile(agent_id=agent_id, agent_version=version, **defaults)


def make_evidence(agent_id, version, cap, cls, *, valid_until=2_000_000.0):
    return AgentCapabilityEvidence(
        evidence_id=f"ev::{agent_id}::{version}::{cap}::{cls}",
        agent_id=agent_id, agent_version=version, capability_id=cap,
        evidence_class=EvidenceClass(cls), measured_at=900_000.0,
        valid_until=valid_until, provenance=SYNTH)


def make_snapshot(profiles: List[AgentProfile], evidence: List[AgentCapabilityEvidence]):
    return build_registry_snapshot(
        snapshot_id="test_snap", registry_version="test.v1", logical_time=NOW,
        agent_profiles=profiles, capability_evidence=evidence, provenance=SYNTH)


def enterprise(**kw) -> EnterpriseAgentPolicy:
    defaults = dict(policy_id="ent", policy_version="1.0",
                    required_evidence_classes=("MEASURED",), fail_closed_on_unknown=True)
    defaults.update(kw)
    return finalize_enterprise_policy(EnterpriseAgentPolicy(**defaults))


def eligibility(**kw) -> EligibilityPolicy:
    defaults = dict(policy_id="elig", policy_version="1.0")
    defaults.update(kw)
    return finalize_eligibility_policy(EligibilityPolicy(**defaults))
