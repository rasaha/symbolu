"""Frozen synthetic fixtures — workflows, registry, policies, and demos.

Everything here is UNMISTAKABLY SYNTHETIC (``provenance.synthetic = True`` /
``release_metadata.synthetic = True``). No fixture asserts real empirical
evidence, a live registry, or a production claim. The synthetic workflows are
serialized ``workflow_ir.v1`` documents (data-only), authored to exercise every
node disposition and every important elimination reason.

Logical time is fixed (:data:`LOGICAL_TIME`) so demos and tests are replayable.
"""
from __future__ import annotations

from typing import Dict, Mapping, Tuple

from .adapter import adapt_compiled_workflow
from .agents import (
    AgentCapability,
    AgentCapabilityEvidence,
    AgentProfile,
    AgentRegistrySnapshot,
    AgentStatus,
    build_registry_snapshot,
)
from .canonical import digest
from .contracts import EvidenceClass
from .eligibility import evaluate_workflow_eligibility
from .policy import (
    EnterpriseAgentPolicy,
    EligibilityPolicy,
    finalize_eligibility_policy,
    finalize_enterprise_policy,
)
from .workflow import Provenance

#: The fixed injected logical time for all fixtures (arbitrary epoch seconds).
LOGICAL_TIME = 1_000_000.0

_SYNTH = Provenance(source_kind="synthetic_fixture", synthetic=True,
                    source_ref="ugence_agent_workforce_composer.fixtures")


# --------------------------------------------------------------------------- #
# serialized workflow_ir.v1 helpers
# --------------------------------------------------------------------------- #

def _node(node_id, kind, owner, disposition, *, authority_type="", label="",
          public_contract_target="", input_object_ids=(), output_contract="",
          audit_requirements=()):
    return {
        "node_id": node_id, "kind": kind, "owning_capability": owner,
        "authority_type": authority_type, "disposition": disposition,
        "public_contract_target": public_contract_target,
        "input_object_ids": list(input_object_ids), "output_contract": output_contract,
        "failure_behavior": "BLOCK", "audit_requirements": list(audit_requirements),
        "label": label,
    }


def _edges(node_ids) -> list:
    edges = []
    for i in range(len(node_ids) - 1):
        edges.append({"edge_id": f"edge_{i}", "kind": "NEXT",
                      "source_id": node_ids[i], "target_id": node_ids[i + 1], "order": i})
    return edges


def _package(pack_id: str, version: int, nodes: list) -> dict:
    node_ids = [n["node_id"] for n in nodes]
    ir = {
        "policy_pack_id": pack_id, "policy_pack_version": version,
        "ir_version": "workflow_ir.v1", "nodes": nodes, "edges": _edges(node_ids),
        "referenced_capabilities": sorted({n["owning_capability"] for n in nodes}),
    }
    structural = digest(ir)
    return {
        "manifest": {"policy_pack_id": pack_id, "policy_pack_version": version,
                     "structural_digest": structural},
        "workflow_ir": ir, "structural_digest": structural,
        "release_metadata": {"synthetic": True},
    }


# --------------------------------------------------------------------------- #
# the three synthetic workflows
# --------------------------------------------------------------------------- #

def procurement_workflow() -> dict:
    nodes = [
        _node("proc_request_validation", "DECISION_RULE", "COMPILER", "ADVISORY",
              label="request schema validation", output_contract="validated_request"),
        _node("proc_supplier_evidence", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="supplier evidence collection", input_object_ids=("validated_request",),
              output_contract="supplier_evidence"),
        _node("proc_supplier_risk", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="supplier-risk analysis", input_object_ids=("supplier_evidence",),
              output_contract="supplier_risk_report"),
        _node("proc_budget_validation", "DECISION_RULE", "COMPILER", "ADVISORY",
              label="budget validation", output_contract="budget_ok"),
        _node("proc_recommendation", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="recommendation drafting", input_object_ids=("supplier_risk_report",),
              output_contract="recommendation_draft"),
        _node("proc_binding_approval", "APPROVAL_GATE", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_APPROVER", label="binding approval"),
        _node("proc_purchase_auth", "ACTION_CONSTRAINT", "ACTION_GATE", "AUTHORITATIVE",
              label="purchase action authorization"),
        _node("proc_commit_clearance", "ACTION_CLEARANCE_REQUIREMENT", "ACTION_CLEARANCE",
              "AUTHORITATIVE", label="commit-time clearance"),
        _node("proc_audit", "AUDIT_EMISSION", "COMPILER", "ADVISORY", label="audit emission"),
        _node("proc_terminal", "TERMINAL_OUTCOME", "COMPILER", "ADVISORY", label="terminal outcome"),
    ]
    return _package("synthetic_procurement", 1, nodes)


def support_workflow() -> dict:
    nodes = [
        _node("sup_classification", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="ticket classification", output_contract="ticket_class"),
        _node("sup_retrieval", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="knowledge retrieval", input_object_ids=("ticket_class",),
              output_contract="retrieved_context"),
        _node("sup_draft", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="draft response", input_object_ids=("retrieved_context",),
              output_contract="draft_response"),
        _node("sup_escalation_decision", "AUTHORITY_CHECK", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_REVIEWER", label="escalation decision"),
        _node("sup_human_approval", "APPROVAL_GATE", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_APPROVER", label="human approval"),
        _node("sup_terminal", "TERMINAL_OUTCOME", "COMPILER", "ADVISORY", label="terminal outcome"),
    ]
    return _package("synthetic_support", 1, nodes)


def security_workflow() -> dict:
    nodes = [
        _node("sec_evidence_collection", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="incident evidence collection", output_contract="incident_evidence"),
        _node("sec_threat_analysis", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="threat analysis", input_object_ids=("incident_evidence",),
              output_contract="threat_assessment"),
        _node("sec_sequence_risk", "SEQUENCE_RISK_CHECK", "STORYGRAPH", "ADVISORY",
              label="sequence-risk advisory input", output_contract="sequence_risk_signal"),
        _node("sec_human_escalation", "OVERRIDE_GATE", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_APPROVER", label="human escalation"),
        _node("sec_action_boundary", "ACTION_CONSTRAINT", "ACTION_GATE", "AUTHORITATIVE",
              label="action authorization boundary"),
        _node("sec_audit", "AUDIT_EMISSION", "COMPILER", "ADVISORY", label="audit emission"),
        _node("sec_terminal", "TERMINAL_OUTCOME", "COMPILER", "ADVISORY", label="terminal outcome"),
    ]
    return _package("synthetic_security", 1, nodes)


WORKFLOWS: Dict[str, "callable"] = {
    "procurement": procurement_workflow,
    "support": support_workflow,
    "security": security_workflow,
}


def role_overlay() -> Dict[str, Mapping]:
    """Enterprise-policy-derived role constraints for the AI-agent-eligible nodes."""
    return {
        "proc_supplier_risk": {
            "role_name": "supplier-risk analyst",
            "required_capabilities": ("risk_analysis",),
            "required_evidence_classes": ("MEASURED",),
            "data_classification": "confidential",
        },
        "proc_recommendation": {
            "role_name": "recommendation drafter",
            "required_capabilities": ("recommendation_drafting",),
            "required_evidence_classes": ("MEASURED",),
        },
        "sup_classification": {
            "role_name": "support classifier",
            "required_capabilities": ("classification",),
            "required_evidence_classes": ("MEASURED",),
        },
        "sec_threat_analysis": {
            "role_name": "threat analyst",
            "required_capabilities": ("threat_analysis",),
            "required_evidence_classes": ("MEASURED",),
            "required_security_classification": 3,
        },
    }


# --------------------------------------------------------------------------- #
# synthetic agent registry
# --------------------------------------------------------------------------- #

def _prof(agent_id, version, provider, caps, *, status=AgentStatus.ACTIVE, residency="US",
          deployment="cloud", security=3, agent_type="analysis", tools=("web_search",),
          input_contracts=("validated_request", "supplier_evidence", "supplier_risk_report",
                            "retrieved_context", "ticket_class", "incident_evidence"),
          output_contracts=("supplier_evidence", "supplier_risk_report", "recommendation_draft",
                             "retrieved_context", "draft_response", "ticket_class",
                             "threat_assessment"),
          permissions=("read_context",), authority=1, quality=0.9, latency=800.0, cost=2.0,
          audit=("trace", "replay"), valid_until=None):
    return AgentProfile(
        agent_id=agent_id, agent_version=version, provider_id=provider, agent_type=agent_type,
        status=status,
        declared_capabilities=tuple(AgentCapability(capability_id=c) for c in caps),
        supported_domains=("procurement", "support", "security"), supported_tools=tools,
        input_contracts=input_contracts, output_contracts=output_contracts,
        requested_permissions=permissions, maximum_authority_scope=authority,
        supported_data_classifications=("public", "confidential"),
        residency=residency, deployment_environment=deployment, security_classification=security,
        latency_evidence=latency, cost_evidence=cost, quality_evidence=quality,
        reliability_evidence=0.99, audit_capabilities=audit, state_model="stateless",
        valid_until=valid_until, provenance=_SYNTH)


def _ev(agent_id, version, cap, cls, *, valid_until=2_000_000.0, value=0.95):
    return AgentCapabilityEvidence(
        evidence_id=f"ev::{agent_id}::{version}::{cap}::{cls}",
        agent_id=agent_id, agent_version=version, capability_id=cap,
        evidence_class=EvidenceClass(cls), measurement_type="benchmark_score", value=value,
        unit="score", benchmark_id=f"bench_{cap}", benchmark_version="1.0",
        sample_size=500, measured_at=900_000.0, valid_until=valid_until,
        issuer="synthetic_benchmark", provenance=_SYNTH)


def registry_snapshot() -> AgentRegistrySnapshot:
    profiles = []
    evidence = []

    def add(prof, evs):
        profiles.append(prof)
        evidence.extend(evs)

    # 1. general-purpose analysis agent (broadly eligible)
    add(_prof("agent_general_analyst", "1.0.0", "anthropic",
              ("evidence_extraction", "analysis", "summarization")),
        [_ev("agent_general_analyst", "1.0.0", "evidence_extraction", "MEASURED")])
    # 2. procurement specialist (measured risk + recommendation)
    add(_prof("agent_procurement_specialist", "2.1.0", "anthropic",
              ("evidence_extraction", "risk_analysis", "recommendation_drafting")),
        [_ev("agent_procurement_specialist", "2.1.0", "evidence_extraction", "OBSERVED"),
         _ev("agent_procurement_specialist", "2.1.0", "risk_analysis", "MEASURED"),
         _ev("agent_procurement_specialist", "2.1.0", "recommendation_drafting", "MEASURED")])
    # 3. customer-support specialist
    add(_prof("agent_support_specialist", "1.3.0", "openai",
              ("evidence_extraction", "classification", "retrieval", "drafting")),
        [_ev("agent_support_specialist", "1.3.0", "evidence_extraction", "MEASURED"),
         _ev("agent_support_specialist", "1.3.0", "classification", "MEASURED")])
    # 4. cybersecurity analyst (high security)
    add(_prof("agent_cyber_analyst", "1.0.0", "anthropic",
              ("evidence_extraction", "threat_analysis"), security=4),
        [_ev("agent_cyber_analyst", "1.0.0", "evidence_extraction", "OBSERVED"),
         _ev("agent_cyber_analyst", "1.0.0", "threat_analysis", "MEASURED")])
    # 5. evidence extraction agent
    add(_prof("agent_evidence_extractor", "1.0.0", "anthropic", ("evidence_extraction",)),
        [_ev("agent_evidence_extractor", "1.0.0", "evidence_extraction", "MEASURED")])
    # 6. deterministic validator represented as a deliberately ineligible "agent"
    add(_prof("agent_deterministic_validator", "1.0.0", "internal",
              ("evidence_extraction",), agent_type="deterministic_validator"),
        [_ev("agent_deterministic_validator", "1.0.0", "evidence_extraction", "DECLARED")])
    # 7. India-resident deployment
    add(_prof("agent_india_resident", "1.0.0", "anthropic", ("evidence_extraction",),
              residency="IN", deployment="cloud_in"),
        [_ev("agent_india_resident", "1.0.0", "evidence_extraction", "MEASURED")])
    # 8. US-only on-prem deployment
    add(_prof("agent_us_only", "1.0.0", "anthropic", ("evidence_extraction",),
              deployment="on_prem_us"),
        [_ev("agent_us_only", "1.0.0", "evidence_extraction", "MEASURED")])
    # 9. forbidden provider
    add(_prof("agent_forbidden_provider", "1.0.0", "forbiddenco", ("evidence_extraction",)),
        [_ev("agent_forbidden_provider", "1.0.0", "evidence_extraction", "MEASURED")])
    # 10. declared-only capability (no measured evidence)
    add(_prof("agent_declared_only", "1.0.0", "anthropic", ("evidence_extraction",)),
        [_ev("agent_declared_only", "1.0.0", "evidence_extraction", "DECLARED")])
    # 11. expired benchmark evidence
    add(_prof("agent_expired_evidence", "1.0.0", "anthropic", ("evidence_extraction",)),
        [_ev("agent_expired_evidence", "1.0.0", "evidence_extraction", "MEASURED",
             valid_until=500_000.0)])
    # 12. insufficient security classification
    add(_prof("agent_low_security", "1.0.0", "anthropic", ("evidence_extraction", "threat_analysis"),
              security=1),
        [_ev("agent_low_security", "1.0.0", "evidence_extraction", "MEASURED"),
         _ev("agent_low_security", "1.0.0", "threat_analysis", "MEASURED")])
    # 13. excessive permission requirement
    add(_prof("agent_over_permission", "1.0.0", "anthropic", ("evidence_extraction",),
              permissions=("read_context", "delete_all")),
        [_ev("agent_over_permission", "1.0.0", "evidence_extraction", "MEASURED")])
    # 14. incompatible input schema
    add(_prof("agent_bad_input", "1.0.0", "anthropic", ("evidence_extraction",),
              input_contracts=("unrelated_input",)),
        [_ev("agent_bad_input", "1.0.0", "evidence_extraction", "MEASURED")])
    # 15. incompatible output schema + inactive status (exercises two reasons)
    add(_prof("agent_bad_output", "1.0.0", "anthropic", ("evidence_extraction",),
              output_contracts=("unrelated_output",)),
        [_ev("agent_bad_output", "1.0.0", "evidence_extraction", "MEASURED")])
    # 16. inactive agent version
    add(_prof("agent_inactive", "1.0.0", "anthropic", ("evidence_extraction",),
              status=AgentStatus.INACTIVE),
        [_ev("agent_inactive", "1.0.0", "evidence_extraction", "MEASURED")])
    # 17. audit-incapable + high cost/latency
    add(_prof("agent_high_cost", "1.0.0", "anthropic", ("evidence_extraction",),
              cost=99.0, latency=99000.0, quality=0.1, audit=()),
        [_ev("agent_high_cost", "1.0.0", "evidence_extraction", "MEASURED")])

    return build_registry_snapshot(
        snapshot_id="synthetic_registry_v1", registry_version="awc_synth.v1",
        logical_time=LOGICAL_TIME, agent_profiles=profiles, capability_evidence=evidence,
        provenance=_SYNTH, source_refs=("synthetic",))


# --------------------------------------------------------------------------- #
# synthetic policies
# --------------------------------------------------------------------------- #

def enterprise_policy() -> EnterpriseAgentPolicy:
    return finalize_enterprise_policy(EnterpriseAgentPolicy(
        policy_id="synthetic_enterprise_policy", policy_version="1.0",
        allowed_providers=("anthropic", "openai", "internal"),
        forbidden_providers=("forbiddenco",),
        allowed_residencies=("US",), required_residencies=("US",),
        allowed_deployment_environments=("cloud", "on_prem_us"),
        minimum_security_classification=2,
        forbidden_tools=("shell_exec",),
        maximum_permission_scope=("read_context", "write_draft", "call_tool"),
        maximum_authority_scope=2,
        required_evidence_classes=("MEASURED",),
        maximum_cost_hard_limit=50.0, maximum_latency_hard_limit=10000.0,
        minimum_quality_hard_limit=0.5,
        required_audit_capabilities=("trace",),
        fail_closed_on_unknown=True))


def eligibility_policy() -> EligibilityPolicy:
    return finalize_eligibility_policy(EligibilityPolicy(
        policy_id="synthetic_eligibility_policy", policy_version="1.0"))


# --------------------------------------------------------------------------- #
# demo pipeline
# --------------------------------------------------------------------------- #

def run_demo(name: str):
    """Run the full offline pipeline for a named synthetic workflow.

    Returns ``(adaptation_result, workflow_eligibility_result)``.
    """
    if name not in WORKFLOWS:
        raise KeyError(f"unknown demo workflow {name!r}; choose one of {sorted(WORKFLOWS)}")
    package = WORKFLOWS[name]()
    adaptation = adapt_compiled_workflow(package, role_overlay=role_overlay())
    snapshot = registry_snapshot()
    result = evaluate_workflow_eligibility(
        adaptation, snapshot, enterprise_policy(), eligibility_policy(), LOGICAL_TIME)
    return adaptation, result


__all__ = [
    "LOGICAL_TIME",
    "procurement_workflow",
    "support_workflow",
    "security_workflow",
    "WORKFLOWS",
    "role_overlay",
    "registry_snapshot",
    "enterprise_policy",
    "eligibility_policy",
    "run_demo",
]
