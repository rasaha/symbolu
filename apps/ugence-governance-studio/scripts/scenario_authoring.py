"""Author the Governance Studio demo scenarios using the REAL Agent Workforce
Composer (AWC) P1/P2 public API.

This module is the *single source of truth* for how the committed demo fixtures
under ``apps/ugence-governance-studio/demo_data/`` were produced. It builds every
scenario's inputs — a serialized ``workflow_ir.v1`` document, an enterprise role
overlay, an agent registry snapshot, and the six governance policies — entirely
out of AWC's own public schema classes. It never re-implements adaptation, node
disposition, eligibility, ranking, composition, permission bounding, fallback
planning, or fingerprinting: those all come from :mod:`ugence_agent_workforce_composer`.

The scenarios are deliberately synthetic (``provenance.synthetic = True`` /
``release_metadata.synthetic = True``) and are authored so that the *real* engine
produces these demonstrations:

* ``procurement`` — the individually top-ranked candidate for a role is NOT the
  one the team selects, because a team-level provider-concentration limit forbids
  routing every role to one provider (a non-greedy team selection).
* ``customer_support`` — a clean, feasible support team; a cybersecurity
  specialist in the registry is eliminated rather than mis-assigned to drafting.
* ``cybersecurity_success`` — a feasible incident-response team; specialist roles
  whose capability is held by a single cleared agent yield ``NO_FALLBACK_AVAILABLE``.
* ``cybersecurity_no_feasible_team`` — a credible ``NO_FEASIBLE_TEAM``: only one
  approved provider fields level-4-cleared agents, so the provider-concentration
  policy cannot be satisfied for a two-role incident-response team.

Logical time is fixed so every scenario is replayable.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Tuple

import ugence_agent_workforce_composer.api as awc

# The single fixed logical time for every scenario (arbitrary epoch seconds).
# Chosen to match the AWC package fixtures so freshness/expiry math is comparable.
LOGICAL_TIME = 1_000_000.0

_SYNTH = awc.Provenance(
    source_kind="synthetic_fixture",
    synthetic=True,
    source_ref="ugence_governance_studio.demo_data",
)


# --------------------------------------------------------------------------- #
# serialized workflow_ir.v1 helpers (data-only; identical shape to the compiler)
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
    from ugence_agent_workforce_composer.canonical import digest
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
# agent / evidence helpers
# --------------------------------------------------------------------------- #

# The union of contract objects that flow through the demo workflows. Agents that
# should be interface-compatible declare (a subset of) these on input/output.
_ALL_INPUTS = (
    "validated_request", "supplier_evidence", "supplier_risk_report",
    "ticket_class", "retrieved_context",
    "incident_evidence", "threat_assessment", "correlated_incident",
)
_ALL_OUTPUTS = (
    "supplier_evidence", "supplier_risk_report", "recommendation_draft",
    "ticket_class", "retrieved_context", "draft_response",
    "incident_evidence", "threat_assessment", "correlated_incident",
    "security_recommendation",
)


def _prof(agent_id, version, provider, caps, *, status=awc.AgentStatus.ACTIVE,
          residency="US", deployment="cloud", security=3, agent_type="analysis",
          domains=("procurement", "support", "security"),
          tools=("web_search",), input_contracts=_ALL_INPUTS,
          output_contracts=_ALL_OUTPUTS, permissions=("read_context",),
          authority=1, quality=0.9, latency=800.0, cost=2.0,
          reliability=0.99, audit=("trace", "replay"), valid_until=None):
    return awc.AgentProfile(
        agent_id=agent_id, agent_version=version, provider_id=provider,
        agent_type=agent_type, status=status,
        declared_capabilities=tuple(awc.AgentCapability(capability_id=c) for c in caps),
        supported_domains=domains, supported_tools=tools,
        input_contracts=input_contracts, output_contracts=output_contracts,
        requested_permissions=permissions, maximum_authority_scope=authority,
        supported_data_classifications=("public", "confidential", "restricted"),
        residency=residency, deployment_environment=deployment,
        security_classification=security, latency_evidence=latency,
        cost_evidence=cost, quality_evidence=quality, reliability_evidence=reliability,
        audit_capabilities=audit, state_model="stateless",
        valid_until=valid_until, provenance=_SYNTH)


def _ev(agent_id, version, cap, cls, *, valid_until=2_000_000.0, value=0.95):
    return awc.AgentCapabilityEvidence(
        evidence_id=f"ev::{agent_id}::{version}::{cap}::{cls}",
        agent_id=agent_id, agent_version=version, capability_id=cap,
        evidence_class=awc.EvidenceClass(cls), measurement_type="benchmark_score",
        value=value, unit="score", benchmark_id=f"bench_{cap}", benchmark_version="1.0",
        sample_size=500, measured_at=900_000.0, valid_until=valid_until,
        issuer="synthetic_benchmark", provenance=_SYNTH)


def _snapshot(snapshot_id, entries) -> awc.AgentRegistrySnapshot:
    """entries: list of (AgentProfile, [AgentCapabilityEvidence, ...]).

    Every EVIDENCE_REQUIREMENT node carries the compiler-derived base capability
    ``evidence_extraction`` (the AWC adapter unions it with any enterprise-overlay
    capabilities), and AWC's hard-constraint engine requires MEASURED/OBSERVED
    evidence for every required capability. So for any agent that *declares*
    ``evidence_extraction`` but ships no evidence for it, we attach a MEASURED
    benchmark record. This keeps each fixture's explicit evidence focused on the
    specialist capability while satisfying the base requirement — it never masks
    an intended elimination, which in these scenarios is always residency,
    clearance, provider or capability, not the generic evidence-extraction bar.
    """
    profiles: List[awc.AgentProfile] = []
    evidence: List[awc.AgentCapabilityEvidence] = []
    for prof, evs in entries:
        profiles.append(prof)
        evs = list(evs)
        declared = set(prof.declared_capability_ids())
        have = {e.capability_id for e in evs if e.agent_id == prof.agent_id
                and e.agent_version == prof.agent_version}
        if "evidence_extraction" in declared and "evidence_extraction" not in have:
            evs.append(_ev(prof.agent_id, prof.agent_version, "evidence_extraction",
                           "MEASURED", value=0.95))
        evidence.extend(evs)
    return awc.build_registry_snapshot(
        snapshot_id=snapshot_id, registry_version="governance_studio_demo.v1",
        logical_time=LOGICAL_TIME, agent_profiles=profiles,
        capability_evidence=evidence, provenance=_SYNTH,
        source_refs=("synthetic_demo",))


# --------------------------------------------------------------------------- #
# shared policy builders (finalized / digest-stamped so fingerprints are stable)
# --------------------------------------------------------------------------- #

def _eligibility_policy(policy_id="gs_eligibility_policy"):
    return awc.finalize_eligibility_policy(
        awc.EligibilityPolicy(policy_id=policy_id, policy_version="1.0"))


def _enterprise_policy(policy_id, *, allowed_providers, forbidden_providers=(),
                       required_residencies=("US",), allowed_residencies=("US",),
                       allowed_deployments=("cloud", "on_prem_us"),
                       min_security=2, max_permission_scope=("read_context", "write_draft", "call_tool"),
                       max_authority=2, max_cost=50.0, max_latency=10000.0, min_quality=0.5):
    return awc.finalize_enterprise_policy(awc.EnterpriseAgentPolicy(
        policy_id=policy_id, policy_version="1.0",
        allowed_providers=tuple(allowed_providers),
        forbidden_providers=tuple(forbidden_providers),
        allowed_residencies=tuple(allowed_residencies),
        required_residencies=tuple(required_residencies),
        allowed_deployment_environments=tuple(allowed_deployments),
        minimum_security_classification=min_security,
        forbidden_tools=("shell_exec",),
        maximum_permission_scope=tuple(max_permission_scope),
        maximum_authority_scope=max_authority,
        required_evidence_classes=("MEASURED",),
        maximum_cost_hard_limit=max_cost, maximum_latency_hard_limit=max_latency,
        minimum_quality_hard_limit=min_quality,
        required_audit_capabilities=("trace",),
        fail_closed_on_unknown=True))


_DEFAULT_CRITERIA = (
    ("evidence_strength", "evidence_strength", "higher_better", 1, 3, 2000),
    ("evidence_freshness", "evidence_freshness", "higher_better", 0, 1, 1000),
    ("measured_quality", "quality", "higher_better", 0, 1, 2000),
    ("observed_reliability", "reliability", "higher_better", 0.9, 1.0, 1500),
    ("latency_headroom", "latency", "lower_better", 0, 5000, 1500),
    ("cost_efficiency", "cost", "lower_better", 0, 10, 1000),
    ("security_headroom", "security", "higher_better", 0, 5, 500),
    ("audit_strength", "audit", "higher_better", 0, 4, 500),
)


def _ranking_policy(policy_id="gs_ranking_policy"):
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    crits = tuple(
        awc.RankingCriterion(key=k, metric=m, direction=d, lo=lo, hi=hi, weight_bp=w)
        for (k, m, d, lo, hi, w) in _DEFAULT_CRITERIA)
    return stamp_fingerprint(
        awc.AgentRankingPolicy(policy_id=policy_id, policy_version="1.0", criteria=crits),
        "policy_digest")


def _composition_policy(policy_id="gs_composition_policy", *,
                        provider_concentration_limit_pct=67,
                        failure_domain_concentration_limit_pct=67,
                        authority_concentration_limit_pct=67,
                        maximum_roles_per_agent=2, minimum_provider_diversity=1,
                        minimum_deployment_diversity=1, team_cost_hard_ceiling=50.0,
                        team_latency_hard_ceiling=10000.0, team_reliability_floor=0.9):
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    return stamp_fingerprint(
        awc.TeamCompositionPolicy(
            policy_id=policy_id, policy_version="1.0",
            provider_concentration_limit_pct=provider_concentration_limit_pct,
            failure_domain_concentration_limit_pct=failure_domain_concentration_limit_pct,
            authority_concentration_limit_pct=authority_concentration_limit_pct,
            maximum_roles_per_agent=maximum_roles_per_agent,
            minimum_provider_diversity=minimum_provider_diversity,
            minimum_deployment_diversity=minimum_deployment_diversity,
            team_cost_hard_ceiling=team_cost_hard_ceiling,
            team_latency_hard_ceiling=team_latency_hard_ceiling,
            team_reliability_floor=team_reliability_floor),
        "policy_digest")


def _permission_policy(policy_id="gs_permission_policy", *,
                       governance_owned=("authorize_purchase", "approve_binding",
                                         "authorize_action"),
                       human_review=("write_draft",)):
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    return stamp_fingerprint(
        awc.PermissionBoundingPolicy(
            policy_id=policy_id, policy_version="1.0",
            governance_owned_permissions=tuple(governance_owned),
            human_review_permissions=tuple(human_review)),
        "policy_digest")


def _fallback_policy(policy_id="gs_fallback_policy", *, maximum_fallback_depth=2,
                     require_security_equivalence=False):
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    return stamp_fingerprint(
        awc.AgentFallbackPolicy(
            policy_id=policy_id, policy_version="1.0",
            maximum_fallback_depth=maximum_fallback_depth,
            require_security_equivalence=require_security_equivalence),
        "policy_digest")


# --------------------------------------------------------------------------- #
# scenario 1: procurement — non-greedy team selection (provider concentration)
# --------------------------------------------------------------------------- #

def _procurement_workflow() -> dict:
    nodes = [
        _node("proc_request_validation", "DECISION_RULE", "COMPILER", "ADVISORY",
              label="request schema validation", output_contract="validated_request"),
        _node("proc_supplier_evidence", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="supplier evidence collection",
              input_object_ids=("validated_request",), output_contract="supplier_evidence"),
        _node("proc_supplier_risk", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="supplier-risk analysis",
              input_object_ids=("supplier_evidence",), output_contract="supplier_risk_report"),
        _node("proc_recommendation", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="procurement recommendation drafting",
              input_object_ids=("supplier_risk_report",), output_contract="recommendation_draft"),
        _node("proc_binding_approval", "APPROVAL_GATE", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_APPROVER", label="binding approval"),
        _node("proc_purchase_auth", "ACTION_CONSTRAINT", "ACTION_GATE", "AUTHORITATIVE",
              label="purchase action authorization"),
        _node("proc_commit_clearance", "ACTION_CLEARANCE_REQUIREMENT", "ACTION_CLEARANCE",
              "AUTHORITATIVE", label="commit-time clearance"),
        _node("proc_audit", "AUDIT_EMISSION", "COMPILER", "ADVISORY", label="audit emission"),
        _node("proc_terminal", "TERMINAL_OUTCOME", "COMPILER", "ADVISORY", label="terminal outcome"),
    ]
    return _package("gs_procurement", 1, nodes)


def _procurement_overlay() -> Dict[str, Mapping]:
    return {
        "proc_supplier_evidence": {
            "role_name": "supplier evidence collection",
            "required_capabilities": ("supplier_evidence_collection",),
            "required_evidence_classes": ("MEASURED",),
            "data_classification": "confidential",
            "required_permissions": ("read_context",),
        },
        "proc_supplier_risk": {
            "role_name": "procurement risk analysis",
            "required_capabilities": ("procurement_risk_analysis",),
            "required_evidence_classes": ("MEASURED",),
            "data_classification": "confidential",
            "required_permissions": ("read_context",),
        },
        "proc_recommendation": {
            "role_name": "procurement recommendation",
            "required_capabilities": ("procurement_recommendation",),
            "required_evidence_classes": ("MEASURED",),
            "required_permissions": ("read_context",),
        },
    }


def _procurement_registry() -> awc.AgentRegistrySnapshot:
    # Three Anthropic specialists top their respective role rankings. A single
    # OpenAI generalist is eligible for every role but ranks below each specialist.
    # Greedy per-role selection would put all three roles on Anthropic (100%),
    # which violates the 67% provider-concentration limit, so the composer must
    # move exactly one role to the OpenAI generalist — a non-greedy team.
    entries = [
        (_prof("agent_supplier_evidence", "1.4.0", "anthropic",
               ("supplier_evidence_collection", "evidence_extraction"),
               quality=0.96, cost=2.0, latency=700.0),
         [_ev("agent_supplier_evidence", "1.4.0", "supplier_evidence_collection", "MEASURED", value=0.97)]),
        (_prof("agent_procurement_risk", "2.1.0", "anthropic",
               ("procurement_risk_analysis", "evidence_extraction"),
               quality=0.95, cost=3.0, latency=900.0),
         [_ev("agent_procurement_risk", "2.1.0", "procurement_risk_analysis", "MEASURED", value=0.96)]),
        (_prof("agent_procurement_recommendation", "1.2.0", "anthropic",
               ("procurement_recommendation", "evidence_extraction"),
               quality=0.94, cost=3.0, latency=1000.0),
         [_ev("agent_procurement_recommendation", "1.2.0", "procurement_recommendation", "MEASURED", value=0.95)]),
        # General Enterprise Analyst (OpenAI): measured only for generic supplier
        # evidence collection, and ranks BELOW the Anthropic evidence specialist.
        # It is the enterprise's only non-Anthropic procurement agent, so it is the
        # sole way to satisfy the provider-concentration limit — which is exactly
        # why the composer must drop the top-ranked evidence specialist for it.
        (_prof("agent_general_analyst", "1.0.0", "openai",
               ("supplier_evidence_collection", "evidence_extraction"),
               quality=0.90, cost=2.5, latency=850.0),
         [_ev("agent_general_analyst", "1.0.0", "supplier_evidence_collection", "MEASURED", value=0.90)]),
        # India-resident procurement agent: capable and measured, but residency IN
        # violates the US residency requirement -> a notable, honest elimination.
        (_prof("agent_india_procurement", "1.0.0", "anthropic",
               ("supplier_evidence_collection", "procurement_risk_analysis", "evidence_extraction"),
               residency="IN", deployment="cloud_in", quality=0.95),
         [_ev("agent_india_procurement", "1.0.0", "supplier_evidence_collection", "MEASURED", value=0.95),
          _ev("agent_india_procurement", "1.0.0", "procurement_risk_analysis", "MEASURED", value=0.95)]),
    ]
    return _snapshot("gs_procurement_registry", entries)


def scenario_procurement() -> dict:
    return {
        "scenario_id": "procurement",
        "workflow": _procurement_workflow(),
        "overlay": _procurement_overlay(),
        "registry": _procurement_registry(),
        "enterprise_policy": _enterprise_policy(
            "gs_procurement_enterprise_policy",
            allowed_providers=("anthropic", "openai", "internal")),
        "eligibility_policy": _eligibility_policy(),
        "ranking_policy": _ranking_policy(),
        "composition_policy": _composition_policy(provider_concentration_limit_pct=67),
        "permission_policy": _permission_policy(),
        "fallback_policy": _fallback_policy(),
    }


# --------------------------------------------------------------------------- #
# scenario 2: customer support — clean feasible team; specialist mis-fit eliminated
# --------------------------------------------------------------------------- #

def _support_workflow() -> dict:
    nodes = [
        _node("sup_triage", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="ticket triage / classification", output_contract="ticket_class"),
        _node("sup_retrieval", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="customer knowledge retrieval",
              input_object_ids=("ticket_class",), output_contract="retrieved_context"),
        _node("sup_draft", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="customer response drafting",
              input_object_ids=("retrieved_context",), output_contract="draft_response"),
        _node("sup_escalation_decision", "AUTHORITY_CHECK", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_REVIEWER", label="escalation decision"),
        _node("sup_human_approval", "APPROVAL_GATE", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_APPROVER", label="human approval"),
        _node("sup_terminal", "TERMINAL_OUTCOME", "COMPILER", "ADVISORY", label="terminal outcome"),
    ]
    return _package("gs_support", 1, nodes)


def _support_overlay() -> Dict[str, Mapping]:
    return {
        "sup_triage": {
            "role_name": "support triage",
            "required_capabilities": ("support_triage",),
            "required_evidence_classes": ("MEASURED",),
            "required_permissions": ("read_context",),
        },
        "sup_retrieval": {
            "role_name": "customer knowledge retrieval",
            "required_capabilities": ("knowledge_retrieval",),
            "required_evidence_classes": ("MEASURED",),
            "required_permissions": ("read_context",),
        },
        "sup_draft": {
            "role_name": "customer response drafting",
            "required_capabilities": ("response_drafting",),
            "required_evidence_classes": ("MEASURED",),
            "required_permissions": ("read_context",),
        },
    }


def _support_registry() -> awc.AgentRegistrySnapshot:
    entries = [
        (_prof("agent_support_triage", "1.1.0", "anthropic",
               ("support_triage", "evidence_extraction"), quality=0.94, cost=1.5, latency=600.0),
         [_ev("agent_support_triage", "1.1.0", "support_triage", "MEASURED", value=0.95)]),
        (_prof("agent_knowledge_retrieval", "1.0.0", "openai",
               ("knowledge_retrieval", "evidence_extraction"), quality=0.92, cost=1.8, latency=650.0),
         [_ev("agent_knowledge_retrieval", "1.0.0", "knowledge_retrieval", "MEASURED", value=0.93)]),
        (_prof("agent_response_drafting", "2.0.0", "anthropic",
               ("response_drafting", "evidence_extraction"), quality=0.93, cost=2.0, latency=700.0),
         [_ev("agent_response_drafting", "2.0.0", "response_drafting", "MEASURED", value=0.94)]),
        # Multilingual support agent: a credible second candidate for triage and
        # drafting, providing ranked fallback coverage. Same provider as retrieval
        # so it does not perturb the clean greedy team selection.
        (_prof("agent_multilingual_support", "1.0.0", "openai",
               ("support_triage", "response_drafting", "knowledge_retrieval", "evidence_extraction"),
               quality=0.88, cost=2.2, latency=900.0),
         [_ev("agent_multilingual_support", "1.0.0", "support_triage", "MEASURED", value=0.86),
          _ev("agent_multilingual_support", "1.0.0", "response_drafting", "MEASURED", value=0.85),
          _ev("agent_multilingual_support", "1.0.0", "knowledge_retrieval", "MEASURED", value=0.84)]),
        # General Enterprise Analyst: eligible for retrieval, fallback candidate.
        (_prof("agent_general_analyst", "1.0.0", "openai",
               ("knowledge_retrieval", "evidence_extraction"), quality=0.85, cost=2.5, latency=850.0),
         [_ev("agent_general_analyst", "1.0.0", "knowledge_retrieval", "MEASURED", value=0.82)]),
        # A cybersecurity specialist is present in the registry but holds no support
        # capability -> it is ELIMINATED for the drafting role, never mis-assigned.
        (_prof("agent_threat_analysis", "1.0.0", "anthropic",
               ("threat_analysis",), security=4, quality=0.97, cost=4.0, latency=1200.0),
         [_ev("agent_threat_analysis", "1.0.0", "threat_analysis", "MEASURED", value=0.98)]),
    ]
    return _snapshot("gs_support_registry", entries)


def scenario_customer_support() -> dict:
    return {
        "scenario_id": "customer_support",
        "workflow": _support_workflow(),
        "overlay": _support_overlay(),
        "registry": _support_registry(),
        "enterprise_policy": _enterprise_policy(
            "gs_support_enterprise_policy",
            allowed_providers=("anthropic", "openai", "google", "internal")),
        "eligibility_policy": _eligibility_policy(),
        "ranking_policy": _ranking_policy(),
        "composition_policy": _composition_policy(provider_concentration_limit_pct=67),
        "permission_policy": _permission_policy(),
        "fallback_policy": _fallback_policy(),
    }


# --------------------------------------------------------------------------- #
# scenario 3: cybersecurity — feasible team; single-holder roles => no fallback
# --------------------------------------------------------------------------- #

def _security_workflow() -> dict:
    nodes = [
        _node("sec_evidence_collection", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="security evidence collection", output_contract="incident_evidence"),
        _node("sec_threat_analysis", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="threat analysis",
              input_object_ids=("incident_evidence",), output_contract="threat_assessment"),
        _node("sec_incident_correlation", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="incident correlation",
              input_object_ids=("threat_assessment",), output_contract="correlated_incident"),
        _node("sec_recommendation", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="security recommendation",
              input_object_ids=("correlated_incident",), output_contract="security_recommendation"),
        _node("sec_sequence_risk", "SEQUENCE_RISK_CHECK", "STORYGRAPH", "ADVISORY",
              label="sequence-risk advisory input", output_contract="sequence_risk_signal"),
        _node("sec_human_escalation", "OVERRIDE_GATE", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_APPROVER", label="human escalation"),
        _node("sec_action_boundary", "ACTION_CONSTRAINT", "ACTION_GATE", "AUTHORITATIVE",
              label="action authorization boundary"),
        _node("sec_audit", "AUDIT_EMISSION", "COMPILER", "ADVISORY", label="audit emission"),
        _node("sec_terminal", "TERMINAL_OUTCOME", "COMPILER", "ADVISORY", label="terminal outcome"),
    ]
    return _package("gs_security", 1, nodes)


def _security_overlay() -> Dict[str, Mapping]:
    return {
        "sec_evidence_collection": {
            "role_name": "security evidence collection",
            "required_capabilities": ("security_evidence_collection",),
            "required_evidence_classes": ("MEASURED",),
            "required_security_classification": 4,
            "required_permissions": ("read_context",),
        },
        "sec_threat_analysis": {
            "role_name": "threat analysis",
            "required_capabilities": ("threat_analysis",),
            "required_evidence_classes": ("MEASURED",),
            "required_security_classification": 4,
            "required_permissions": ("read_context",),
        },
        "sec_incident_correlation": {
            "role_name": "incident correlation",
            "required_capabilities": ("incident_correlation",),
            "required_evidence_classes": ("MEASURED",),
            "required_security_classification": 4,
            "required_permissions": ("read_context",),
        },
        "sec_recommendation": {
            "role_name": "security recommendation",
            "required_capabilities": ("security_recommendation",),
            "required_evidence_classes": ("MEASURED",),
            "required_security_classification": 4,
            "required_permissions": ("read_context",),
        },
    }


def _security_success_registry() -> awc.AgentRegistrySnapshot:
    # Four cleared specialists spanning two providers (so the primary team meets
    # the provider-concentration limit). Evidence collection has a second cleared
    # candidate (General Enterprise Analyst) => a real fallback. The three other
    # roles are each held by a single cleared agent => NO_FALLBACK_AVAILABLE.
    entries = [
        (_prof("agent_security_evidence", "1.2.0", "anthropic",
               ("security_evidence_collection", "evidence_extraction"),
               security=4, quality=0.95, cost=3.0, latency=900.0),
         [_ev("agent_security_evidence", "1.2.0", "security_evidence_collection", "MEASURED", value=0.95)]),
        (_prof("agent_threat_analysis", "2.0.0", "anthropic",
               ("threat_analysis", "evidence_extraction"),
               security=4, quality=0.96, cost=3.5, latency=950.0),
         [_ev("agent_threat_analysis", "2.0.0", "threat_analysis", "MEASURED", value=0.96)]),
        (_prof("agent_incident_correlation", "1.0.0", "openai",
               ("incident_correlation", "evidence_extraction"),
               security=4, quality=0.94, cost=3.5, latency=1000.0),
         [_ev("agent_incident_correlation", "1.0.0", "incident_correlation", "MEASURED", value=0.94)]),
        (_prof("agent_security_recommendation", "1.1.0", "openai",
               ("security_recommendation", "evidence_extraction"),
               security=4, quality=0.93, cost=3.0, latency=1050.0),
         [_ev("agent_security_recommendation", "1.1.0", "security_recommendation", "MEASURED", value=0.93)]),
        # General Enterprise Analyst: cleared, but only generic evidence collection
        # -> eligible for the evidence role only, where it serves as the ranked
        # fallback (same provider as two specialists, so the greedy specialist team
        # remains the feasible optimum rather than being perturbed for diversity).
        (_prof("agent_general_analyst", "1.0.0", "openai",
               ("security_evidence_collection", "evidence_extraction"),
               security=4, quality=0.88, cost=2.8, latency=1100.0),
         [_ev("agent_general_analyst", "1.0.0", "security_evidence_collection", "MEASURED", value=0.86)]),
        # A low-clearance analyst: capable on paper but clearance 2 < required 4
        # -> honest elimination on every security role.
        (_prof("agent_low_clearance", "1.0.0", "anthropic",
               ("threat_analysis", "incident_correlation", "evidence_extraction"),
               security=2, quality=0.9),
         [_ev("agent_low_clearance", "1.0.0", "threat_analysis", "MEASURED", value=0.9),
          _ev("agent_low_clearance", "1.0.0", "incident_correlation", "MEASURED", value=0.9)]),
    ]
    return _snapshot("gs_security_success_registry", entries)


def scenario_cybersecurity_success() -> dict:
    return {
        "scenario_id": "cybersecurity_success",
        "workflow": _security_workflow(),
        "overlay": _security_overlay(),
        "registry": _security_success_registry(),
        "enterprise_policy": _enterprise_policy(
            "gs_security_enterprise_policy",
            allowed_providers=("anthropic", "openai", "google", "internal"),
            min_security=3),
        "eligibility_policy": _eligibility_policy(),
        "ranking_policy": _ranking_policy(),
        "composition_policy": _composition_policy(provider_concentration_limit_pct=67),
        "permission_policy": _permission_policy(),
        "fallback_policy": _fallback_policy(),
    }


# --------------------------------------------------------------------------- #
# scenario 4: cybersecurity — NO_FEASIBLE_TEAM (provider concentration)
# --------------------------------------------------------------------------- #

def _security_infeasible_workflow() -> dict:
    # Exactly TWO AI-agent-eligible nodes (threat analysis + incident correlation)
    # so the team-level provider-concentration math is unambiguous.
    nodes = [
        _node("sec_evidence_intake", "DECISION_RULE", "COMPILER", "ADVISORY",
              label="incident intake validation", output_contract="incident_evidence"),
        _node("sec_threat_analysis", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="threat analysis",
              input_object_ids=("incident_evidence",), output_contract="threat_assessment"),
        _node("sec_incident_correlation", "EVIDENCE_REQUIREMENT", "COMPILER", "ADVISORY",
              label="incident correlation",
              input_object_ids=("threat_assessment",), output_contract="correlated_incident"),
        _node("sec_human_escalation", "OVERRIDE_GATE", "DECISION_AUTHORITY", "AUTHORITATIVE",
              authority_type="HUMAN_APPROVER", label="human escalation"),
        _node("sec_action_boundary", "ACTION_CONSTRAINT", "ACTION_GATE", "AUTHORITATIVE",
              label="action authorization boundary"),
        _node("sec_audit", "AUDIT_EMISSION", "COMPILER", "ADVISORY", label="audit emission"),
        _node("sec_terminal", "TERMINAL_OUTCOME", "COMPILER", "ADVISORY", label="terminal outcome"),
    ]
    return _package("gs_security_infeasible", 1, nodes)


def _security_infeasible_overlay() -> Dict[str, Mapping]:
    return {
        "sec_threat_analysis": {
            "role_name": "threat analysis",
            "required_capabilities": ("threat_analysis",),
            "required_evidence_classes": ("MEASURED",),
            "required_security_classification": 4,
            "required_permissions": ("read_context",),
        },
        "sec_incident_correlation": {
            "role_name": "incident correlation",
            "required_capabilities": ("incident_correlation",),
            "required_evidence_classes": ("MEASURED",),
            "required_security_classification": 4,
            "required_permissions": ("read_context",),
        },
    }


def _security_infeasible_registry() -> awc.AgentRegistrySnapshot:
    # Each of the two roles has exactly one eligible (level-4-cleared) candidate,
    # and BOTH are the same single approved provider (anthropic). Other providers'
    # agents fail the clearance bar. A two-role team is therefore 100% one provider,
    # which the 67% provider-concentration limit forbids => NO_FEASIBLE_TEAM.
    entries = [
        (_prof("agent_threat_analysis", "2.0.0", "anthropic",
               ("threat_analysis", "evidence_extraction"), security=4, quality=0.96),
         [_ev("agent_threat_analysis", "2.0.0", "threat_analysis", "MEASURED", value=0.96)]),
        (_prof("agent_incident_correlation", "1.0.0", "anthropic",
               ("incident_correlation", "evidence_extraction"), security=4, quality=0.95),
         [_ev("agent_incident_correlation", "1.0.0", "incident_correlation", "MEASURED", value=0.95)]),
        # OpenAI agents exist and are capable, but are only cleared to level 2/3,
        # below the required level 4 -> eliminated, so no second provider qualifies.
        (_prof("agent_openai_threat", "1.0.0", "openai",
               ("threat_analysis", "incident_correlation", "evidence_extraction"),
               security=2, quality=0.9),
         [_ev("agent_openai_threat", "1.0.0", "threat_analysis", "MEASURED", value=0.9),
          _ev("agent_openai_threat", "1.0.0", "incident_correlation", "MEASURED", value=0.9)]),
        (_prof("agent_google_threat", "1.0.0", "google",
               ("threat_analysis", "incident_correlation", "evidence_extraction"),
               security=3, quality=0.9),
         [_ev("agent_google_threat", "1.0.0", "threat_analysis", "MEASURED", value=0.9),
          _ev("agent_google_threat", "1.0.0", "incident_correlation", "MEASURED", value=0.9)]),
    ]
    return _snapshot("gs_security_infeasible_registry", entries)


def scenario_cybersecurity_no_feasible_team() -> dict:
    return {
        "scenario_id": "cybersecurity_no_feasible_team",
        "workflow": _security_infeasible_workflow(),
        "overlay": _security_infeasible_overlay(),
        "registry": _security_infeasible_registry(),
        "enterprise_policy": _enterprise_policy(
            "gs_security_infeasible_enterprise_policy",
            allowed_providers=("anthropic", "openai", "google", "internal"),
            min_security=3),
        "eligibility_policy": _eligibility_policy(),
        "ranking_policy": _ranking_policy(),
        # A strict 60% concentration limit on a 2-role team forbids a single-provider
        # incident-response team (both roles on one provider = 100%).
        "composition_policy": _composition_policy(provider_concentration_limit_pct=60,
                                                  minimum_provider_diversity=2),
        "permission_policy": _permission_policy(),
        "fallback_policy": _fallback_policy(),
    }


SCENARIOS = {
    "procurement": scenario_procurement,
    "customer_support": scenario_customer_support,
    "cybersecurity_success": scenario_cybersecurity_success,
    "cybersecurity_no_feasible_team": scenario_cybersecurity_no_feasible_team,
}

# Deterministic presentation order for the studio.
SCENARIO_ORDER = (
    "procurement",
    "customer_support",
    "cybersecurity_success",
    "cybersecurity_no_feasible_team",
)


def build_scenario(scenario_id: str) -> dict:
    if scenario_id not in SCENARIOS:
        raise KeyError(f"unknown scenario {scenario_id!r}; choose one of {sorted(SCENARIOS)}")
    return SCENARIOS[scenario_id]()
